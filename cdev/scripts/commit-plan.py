#!/usr/bin/env python3
"""commit-plan.py — split the changes from a base B to a target T into a planned series of
commits: list the changed paths, check a plan, and build or make its commits.

Usage:
    python3 commit-plan.py paths  (--base <B> --head <H> | --worktree [--exclude <path>]...)
    python3 commit-plan.py check  (--base <B> --head <H> | --worktree [--exclude <path>]...)
                                  --plan <plan.jsonl>
    python3 commit-plan.py build  --base <B> --head <H> --plan <plan.jsonl>
    python3 commit-plan.py commit --worktree [--exclude <path>]... --plan <plan.jsonl>

Run it from inside the work tree; every git command runs at the top of the work tree.
--plan and --exclude take an absolute path or one relative to the current directory.

Base and target:
    --base B --head H  B and H name commits and B is an ancestor of H; T is H's tree.
    --worktree         B is HEAD; T is the work tree as `git add -A` would stage it, with
                       everything under .claude/tmp, .claude/worktrees, and each --exclude
                       path kept as it is in B. An --exclude directory covers everything
                       under it, and one outside the work tree is ignored. Refused when the
                       index has staged changes or a merge, cherry-pick, or revert is in
                       progress.

A changed path is one that only B or only T has, or whose mode or object differs between
them. Paths are compared as exact strings.

Plan file: JSON Lines, one commit per line, in the order the commits are stacked:
    {"message": "<commit message>", "paths": ["<path>", ...]}
    - exactly these two keys, with no "type" key and no metadata line;
    - "message": a string whose first line is not blank and that holds no NUL; a
      multi-line message is one JSON string with \\n in it, never several lines;
    - "paths": a non-empty array of the repository-relative paths `paths` prints;
    - every changed path is on exactly one line and no other path is on any;
    - the paths of each "together" group that `paths` prints are on one line.
    Lines end at \\n with one trailing \\r removed, blank lines are skipped, and line
    numbers count every physical line from 1.

Each commit gets the T state of its line's paths, so the last commit's tree is T. The
message is stored with its trailing whitespace replaced by one newline.

Output: one JSON object on one line of stdout.
    paths   {"paths": [{"path": "a/b.py", "status": "A|M|D"}],
             "together": [{"reason": "rename|dir-switch", "paths": ["<path>", ...]}]}
            Empty "paths": there is nothing to commit.
    check   {"ok": true, "count": <plan lines>}
    build   {"commit": "<last>", "count": n, "commits": [{"commit": "<sha>", "subject": "..."}]}
            Stacks the commits on B with a temporary index and commit-tree, signed when
            commit.gpgSign is true, and changes no ref, index, or work tree.
    commit  {"commit": "<HEAD>", "count": n, "commits": [...], "tree_match": true|false,
             "snapshot": "<tree of T>"}
            Stages each line's paths and runs `git commit` on the current branch, hooks and
            signing included. tree_match is false when HEAD's tree differs from T at the end.

Exit codes:
    0  success
    1  refused: {"error": "<one-line summary>"}, with "errors": ["<check>", ...] only when
       the plan fails its checks, which the planner can fix. check adds "ok": false; commit
       adds "count", "commits", and "snapshot" (null when refused before T was made). When
       commit stops partway, it resets the index to HEAD and the rest stays in the work tree.
    2  usage error: usage on stderr and nothing on stdout
"""

import argparse
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile

ALWAYS_EXCLUDED = (".claude/tmp", ".claude/worktrees")
IN_PROGRESS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD")
LINE_SEPARATORS = {ord(c): f"\\u{ord(c):04x}" for c in "\u2028\u2029\u0085"}

GIT = None
TOP = None
# The signals received while their handling is deferred, or None while it is not.
DEFERRED_SIGNALS = None


class Error(Exception):
    """A refusal: exit 1 with {"error": ...}."""


class PlanError(Error):
    def __init__(self, errors):
        super().__init__(f"the plan fails {plural(len(errors), 'check')}")
        self.errors = errors


class Range:
    def __init__(self, base, base_tree, target_tree, base_map=None):
        self.base = base
        self.base_tree = base_tree
        self.target_tree = target_tree
        self.base_map = entries(base_tree) if base_map is None else base_map
        self.target_map = entries(target_tree)
        self.changed = changed_paths(self.base_map, self.target_map)
        self.together = (renames(base_tree, target_tree, self.changed)
                         + dir_switches(self.base_map, self.target_map, self.changed))


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def quote(value):
    text = json.dumps(value, ensure_ascii=False)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        text = json.dumps(value)
    return text


def executable(name):
    # Windows looks a bare program name up in the working directory before
    # PATH, and the working directory can hold untrusted checked-out files.
    if os.name == "nt" and not name.lower().endswith(".exe"):
        name += ".exe"
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry = entry.strip('"')
        path = os.path.join(entry, name)
        if os.path.isabs(entry) and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def run_git(args, index=None, input=b""):
    env = None
    if index is not None:
        env = dict(os.environ, GIT_INDEX_FILE=index)
        # A split index would leave sharedindex.* files behind in the git directory.
        args = ["-c", "core.splitIndex=false", *args]
    return subprocess.run([GIT, *args], cwd=TOP, env=env, input=input, capture_output=True)


def failure_text(proc, name):
    lines = [line.strip() for line in proc.stderr.decode("utf-8", "replace").split("\n")]
    text = "; ".join(line for line in lines if line)
    return f"git {name}: {text or f'exited with {proc.returncode}'}"


def git(*args, index=None, input=b"", ok=(0,)):
    proc = run_git(list(args), index, input)
    if proc.returncode not in ok:
        raise Error(failure_text(proc, next(a for a in args if not a.startswith("-"))))
    return proc.stdout


def line_of(output):
    return output.decode("utf-8").rstrip("\n")


def decode_path(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Error(f"a path is not UTF-8: {raw!r}") from None


def entries(tree):
    table = {}
    for record in git("ls-tree", "-r", "-z", "--full-tree", tree).split(b"\0"):
        if record:
            meta, raw = record.split(b"\t", 1)
            mode, kind, oid = meta.decode("ascii").split(" ")
            table[decode_path(raw)] = (mode, kind, oid)
    return table


def changed_paths(base_map, target_map):
    changed = {}
    for path in sorted(base_map.keys() | target_map.keys()):
        if path not in base_map:
            changed[path] = "A"
        elif path not in target_map:
            changed[path] = "D"
        elif base_map[path] != target_map[path]:
            changed[path] = "M"
    return changed


def renames(base_tree, target_tree, changed):
    fields = git("diff", "-M", "--no-ext-diff", "--no-color", "--name-status", "-z",
                 base_tree, target_tree).split(b"\0")
    groups, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i].decode("ascii")
        if status[:1] not in ("R", "C"):
            i += 2
            continue
        old, new = decode_path(fields[i + 1]), decode_path(fields[i + 2])
        i += 3
        if status[0] == "R" and changed.get(old) == "D" and changed.get(new) == "A":
            groups.append({"reason": "rename", "paths": [old, new]})
    return groups


def dir_switches(base_map, target_map, changed):
    prefixes = set()
    for path, status in changed.items():
        if status == "M":
            continue
        other = base_map if status == "A" else target_map
        parts = path.split("/")
        prefixes.update(p for p in ("/".join(parts[:n]) for n in range(1, len(parts)))
                        if p in other)
    return [{"reason": "dir-switch",
             "paths": [x] + [p for p in changed if p.startswith(x + "/")]}
            for x in sorted(prefixes)]


def resolve_commit(value, option):
    if value.startswith("-"):
        raise Error(f"{option} {quote(value)} begins with '-'")
    proc = run_git(["rev-parse", "--verify", "--quiet", value + "^{commit}"])
    if proc.returncode != 0:
        raise Error(f"{option} {quote(value)} does not name a commit")
    return line_of(proc.stdout)


def tree_of(commit):
    return line_of(git("rev-parse", "--verify", commit + "^{tree}"))


def commit_range(base, head):
    base, head = resolve_commit(base, "--base"), resolve_commit(head, "--head")
    proc = run_git(["merge-base", "--is-ancestor", base, head])
    if proc.returncode == 1:
        raise Error("--base is not an ancestor of --head")
    if proc.returncode != 0:
        raise Error(failure_text(proc, "merge-base"))
    return Range(base, tree_of(base), tree_of(head))


def under(path, excluded):
    sep = b"/" if isinstance(path, bytes) else "/"
    return any(path == e or path.startswith(e + sep) for e in excluded)


def add_pathspecs(excluded, base_map):
    # git refuses a pathspec beyond a symbolic link or inside a submodule, and an exclude
    # pathspec that names an ignored path or one under an ignored directory fails the add,
    # so those paths are left to the reset after the add.
    top = os.path.realpath(TOP)
    gitlinks = [p for p, (mode, _, _) in base_map.items() if mode == "160000"]
    plain = []
    for path in excluded:
        parent = os.path.dirname(path)
        if parent and (os.path.normcase(os.path.realpath(os.path.join(TOP, parent)))
                       != os.path.normcase(os.path.join(top, parent))):
            continue
        if not any(path.startswith(g + "/") for g in gitlinks):
            plain.append(path)
    ignored = set()
    if plain:
        # A leading "./" keeps a path that begins with ":" from being read as pathspec magic.
        out = git("check-ignore", "--no-index", "-z", "--stdin", ok=(0, 1),
                  input="".join(f"./{p}\0" for p in plain).encode("utf-8"))
        ignored = {raw.decode("utf-8")[2:] for raw in out.split(b"\0") if raw}
    return ["."] + [f":(exclude,literal){p}" for p in plain if p not in ignored]


def worktree_range(excludes, tmp_dir):
    proc = run_git(["rev-parse", "--verify", "--quiet", "HEAD^{commit}"])
    if proc.returncode != 0:
        raise Error("HEAD does not name a commit")
    base = line_of(proc.stdout)
    for name in IN_PROGRESS:
        if run_git(["rev-parse", "-q", "--verify", name]).returncode == 0:
            raise Error(f"{name} exists: a merge, cherry-pick, or revert is in progress")
    base_tree = tree_of(base)
    index = os.path.join(tmp_dir, "index")
    shared = os.path.join(TOP, line_of(git("rev-parse", "--git-path", "index")))
    if os.path.isfile(shared):
        # Keep the mtime: git rereads only the entries not older than the index file,
        # so a fresh mtime would hide a same-size rewrite made right after the last write.
        shutil.copy2(shared, index)
    if line_of(git("write-tree", index=index)) != base_tree:
        raise Error("the index has staged changes")
    excluded = ALWAYS_EXCLUDED + tuple(excludes)
    excluded_raw = tuple(e.encode("utf-8") for e in excluded)
    base_map = entries(base_tree)
    git("add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul", index=index,
        input="\0".join(add_pathspecs(excluded, base_map)).encode("utf-8"))
    null = b"0" * len(base)
    stream = []
    for record in git("ls-files", "-s", "-z", index=index).split(b"\0"):
        raw = record.split(b"\t", 1)[-1]
        if record and under(raw, excluded_raw):
            stream.append(b"0 " + null + b"\t" + raw + b"\0")
    for path, (mode, kind, oid) in base_map.items():
        if under(path, excluded):
            stream.append(f"{mode} {kind} {oid}\t{path}\0".encode("utf-8"))
    if stream:
        git("update-index", "-z", "--index-info", index=index, input=b"".join(stream))
    return Range(base, base_tree, line_of(git("write-tree", index=index)), base_map)


@contextlib.contextmanager
def temp_dir():
    git_dir = line_of(git("rev-parse", "--absolute-git-dir"))
    path = tempfile.mkdtemp(prefix="commit-plan.", dir=git_dir)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def get_range(args):
    if args.worktree:
        with temp_dir() as tmp:
            return worktree_range(args.exclude, tmp)
    return commit_range(args.base, args.head)


def read_lines(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:
        raise PlanError([f"cannot read the plan file {quote(path)}: {exc.strerror}"]) from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlanError([f"the plan file is not UTF-8 (byte {exc.start})"]) from None
    lines = [(n, line[:-1] if line.endswith("\r") else line)
             for n, line in enumerate(text.split("\n"), 1)]
    lines = [(n, line) for n, line in lines if line.strip()]
    if not lines:
        raise PlanError(["the plan file has no non-blank line"])
    return text, lines


def record_errors(n, value):
    if not isinstance(value, dict):
        return [f"line {n}: not a JSON object"]
    errors = [f"line {n}: missing key {quote(k)}" for k in ("message", "paths") if k not in value]
    errors += [f"line {n}: unknown key {quote(k)}" for k in value if k not in ("message", "paths")]
    message = value.get("message")
    if "message" in value:
        if not isinstance(message, str):
            errors.append(f'line {n}: "message" is not a string')
        else:
            if not message.split("\n", 1)[0].strip():
                errors.append(f'line {n}: the first line of "message" is blank')
            if "\0" in message:
                errors.append(f'line {n}: "message" holds a NUL character')
            try:
                message.encode("utf-8")
            except UnicodeEncodeError:
                errors.append(f'line {n}: "message" holds an unpaired surrogate')
    paths = value.get("paths")
    if "paths" in value:
        if not isinstance(paths, list) or not paths:
            errors.append(f'line {n}: "paths" is not a non-empty array')
        elif not all(isinstance(p, str) for p in paths):
            errors.append(f'line {n}: "paths" holds an element that is not a string')
    return errors


def read_plan(path, rng):
    text, lines = read_lines(path)
    errors, plan, unparsed = [], [], False
    for n, line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            unparsed = True
            errors.append(f"line {n}: not valid JSON ({exc.msg} at column {exc.colno})")
            continue
        found = record_errors(n, value)
        errors += found
        if not found:
            plan.append((n, value["message"], value["paths"]))
        elif isinstance(value, dict) and isinstance(value.get("paths"), list):
            plan.append((n, None, [p for p in value["paths"] if isinstance(p, str)]))
    if unparsed:
        try:
            json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            raise PlanError([f"the plan is one JSON value across {plural(len(lines), 'line')}; "
                             "write each commit as one JSON object on one line"])

    where = {}
    for n, _, paths in plan:
        for p in paths:
            where.setdefault(p, []).append(n)
    for p, ns in where.items():
        if len(ns) > 1:
            errors.append(f"{quote(p)} appears {len(ns)} times, on lines "
                          f"{', '.join(map(str, ns))}; put each path on one line only")
    for n, _, paths in plan:
        for p in dict.fromkeys(paths):
            if p not in rng.changed:
                errors.append(f"line {n}: {quote(p)} is not a changed path")
    if not rng.changed:
        errors.append("no path has changed, so there is nothing to commit")
    errors += [f"changed path {quote(p)} is on no line" for p in rng.changed if p not in where]
    for group in rng.together:
        ns = sorted({n for p in group["paths"] for n in where.get(p, [])})
        if len(ns) > 1:
            errors.append(f"{group['reason']} group {', '.join(map(quote, group['paths']))} "
                          f"is split across lines {', '.join(map(str, ns))}; "
                          "put its paths on one line")
    if errors:
        raise PlanError(errors)
    return plan


def saved_message(message):
    return message.rstrip() + "\n"


def subject_of(message):
    first = message.split("\n", 1)[0]
    return first[:-1] if first.endswith("\r") else first


def commit_subject(commit):
    raw = git("cat-file", "commit", commit).split(b"\n\n", 1)
    return subject_of(raw[1].decode("utf-8", "replace")) if len(raw) == 2 else ""


def cmd_paths(args, progress):
    rng = get_range(args)
    return {"paths": [{"path": p, "status": s} for p, s in rng.changed.items()],
            "together": rng.together}


def cmd_check(args, progress):
    return {"ok": True, "count": len(read_plan(args.plan, get_range(args)))}


def cmd_build(args, progress):
    rng = commit_range(args.base, args.head)
    plan = read_plan(args.plan, rng)
    signed = git("config", "--bool", "--get", "commit.gpgSign", ok=(0, 1)).strip() == b"true"
    null = "0" * len(rng.base)
    parent, tree, commits = rng.base, rng.base_tree, []
    with temp_dir() as tmp:
        index = os.path.join(tmp, "index")
        git("read-tree", rng.base, index=index)
        for _, message, paths in plan:
            stream = [f"0 {null}\t{p}\0" for p in paths if p not in rng.target_map]
            stream += ["{} {} {}\t{}\0".format(*rng.target_map[p], p)
                       for p in paths if p in rng.target_map]
            git("update-index", "-z", "--index-info", index=index,
                input="".join(stream).encode("utf-8"))
            tree = line_of(git("write-tree", index=index))
            text = saved_message(message)
            # commit-tree does not read commit.gpgSign.
            sign = ["-S"] if signed else []
            parent = line_of(git("commit-tree", *sign, tree, "-p", parent,
                                 input=text.encode("utf-8")))
            commits.append({"commit": parent, "subject": subject_of(text)})
    if tree != rng.target_tree:
        raise Error("the tree of the last commit does not match the tree of --head")
    return {"commit": parent, "count": len(commits), "commits": commits}


def note_head(progress, head):
    current = line_of(git("rev-parse", "--verify", "HEAD"))
    if current != head:
        progress["commits"].append({"commit": current, "subject": commit_subject(current)})
        progress["count"] = len(progress["commits"])
    return current


def stop_if_signaled():
    if DEFERRED_SIGNALS:
        raise Error(f"stopped by signal {DEFERRED_SIGNALS[0]}")


def cmd_commit(args, progress):
    global DEFERRED_SIGNALS
    with temp_dir() as tmp:
        rng = worktree_range(args.exclude, tmp)
    progress["snapshot"] = rng.target_tree
    plan = read_plan(args.plan, rng)
    # From here a signal takes effect only between git commands, through the reset below,
    # so that no git command is killed while it holds a lock on the index or a ref.
    DEFERRED_SIGNALS = []
    tracked = set(git("ls-files", "-z").split(b"\0"))
    head = rng.base
    for n, message, paths in plan:
        # `add -A` with a pathspec fails on a tracked path under an ignored directory, and
        # `add -u` never looks at untracked files, so the index's own paths go through -u.
        update = [p for p in paths if p.encode("utf-8") in tracked]
        add = [p for p in paths if p.encode("utf-8") not in tracked]
        try:
            stop_if_signaled()
            for option, group in (("-u", update), ("-A", add)):
                if group:
                    git("--literal-pathspecs", "add", option, "--pathspec-from-file=-",
                        "--pathspec-file-nul", input="\0".join(group).encode("utf-8"))
            stop_if_signaled()
            git("commit", "--cleanup=verbatim", "-F", "-",
                input=saved_message(message).encode("utf-8"))
        except Error as exc:
            reason = f"line {n}: {exc}"
            with contextlib.suppress(Error):
                note_head(progress, head)
            proc = run_git(["reset", "-q"])
            if proc.returncode != 0:
                reason += f"; resetting the index to HEAD failed: {failure_text(proc, 'reset')}"
            raise Error(reason) from None
        head = note_head(progress, head)
    return {"commit": head, "count": progress["count"], "commits": progress["commits"],
            "tree_match": tree_of("HEAD") == rng.target_tree, "snapshot": rng.target_tree}


HANDLERS = {"paths": cmd_paths, "check": cmd_check, "build": cmd_build, "commit": cmd_commit}


def build_parser():
    parser = argparse.ArgumentParser(prog="commit-plan.py", allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", metavar="{paths,check,build,commit}",
                                required=True)
    parsers = {}
    for name in HANDLERS:
        p = parsers[name] = sub.add_parser(name, allow_abbrev=False)
        if name != "commit":
            p.add_argument("--base", required=name == "build")
            p.add_argument("--head", required=name == "build")
        if name != "build":
            p.add_argument("--worktree", action="store_true", required=name == "commit")
            p.add_argument("--exclude", action="append", default=[])
        if name != "paths":
            p.add_argument("--plan", required=True)
    return parser, parsers


def validate(parser, args):
    if args.command in ("paths", "check"):
        has_range = args.base is not None or args.head is not None
        if args.worktree and has_range:
            parser.error("give either --base and --head or --worktree, not both")
        if not args.worktree and (args.base is None or args.head is None):
            parser.error("give both --base and --head, or --worktree")
    if getattr(args, "exclude", None) and not args.worktree:
        parser.error("--exclude needs --worktree")


def normalize_excludes(parser, values):
    top = os.path.realpath(TOP)
    result = []
    for value in values:
        parent, name = os.path.split(os.path.abspath(value))
        path = os.path.join(os.path.realpath(parent), name)
        try:
            rel = os.path.relpath(path, top)
        except ValueError:
            continue
        if rel.split(os.sep)[0] == os.pardir:
            continue
        if rel == os.curdir:
            parser.error(f"--exclude {value} names the top of the work tree")
        result.append(rel.replace(os.sep, "/"))
    return result


def emit(value):
    text = json.dumps(value, ensure_ascii=False).translate(LINE_SEPARATORS)
    sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    sys.stdout.flush()


def exit_on_signal(signum, frame):
    if DEFERRED_SIGNALS is None:
        raise SystemExit(128 + signum)
    DEFERRED_SIGNALS.append(signum)


def main(argv=None):
    global GIT, TOP
    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), exit_on_signal)
    parser, parsers = build_parser()
    args = parser.parse_args(argv)
    validate(parsers[args.command], args)
    progress = {"count": 0, "commits": [], "snapshot": None}
    try:
        GIT = executable("git")
        if GIT is None:
            raise Error("git not found on PATH")
        TOP = line_of(git("rev-parse", "--show-toplevel"))
        if getattr(args, "worktree", False):
            args.exclude = normalize_excludes(parsers[args.command], args.exclude)
        out = HANDLERS[args.command](args, progress)
    except Error as exc:
        out = {"error": str(exc)}
        if isinstance(exc, PlanError):
            out["errors"] = exc.errors
        if args.command == "check":
            out = {"ok": False, **out}
        elif args.command == "commit":
            out.update(progress)
        emit(out)
        return 1
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
