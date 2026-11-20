#!/usr/bin/env python3
"""commit-plan-test.py — self-test for cdev/scripts/commit-plan.py on temporary git repositories.

Usage: python3 tests/commit-plan-test.py
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "cdev", "scripts", "commit-plan.py")
IS_WINDOWS = os.name == "nt"
ENV = {}
HOME = []

SEPARATORS = "\u2028\u2029\u0085"
TEXT = "".join(f"line {i} of a document long enough for rename detection\n" for i in range(40))


def setUpModule():
    home = tempfile.mkdtemp(prefix="commit-plan-test-home.")
    HOME.append(home)
    config = os.path.join(home, "gitconfig")
    with open(config, "w") as f:
        f.write("[init]\n\tdefaultObjectFormat = sha1\n\tdefaultRefFormat = files\n")
    ENV.update({k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")})
    ENV.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=config, HOME=home,
               XDG_CONFIG_HOME=os.path.join(home, ".config"),
               GIT_CEILING_DIRECTORIES=tempfile.gettempdir())


def tearDownModule():
    for home in HOME:
        remove_tree(home)


def remove_tree(path):
    # git leaves its objects read-only, which blocks their removal on Windows.
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            entry = os.path.join(root, name)
            if not os.path.islink(entry):
                try:
                    os.chmod(entry, stat.S_IRWXU)
                except OSError:
                    pass
    shutil.rmtree(path, ignore_errors=True)


def git(cwd, *args, input=b"", env=None, ok=(0,)):
    proc = subprocess.run(["git", *args], cwd=cwd, input=input, env=env or ENV,
                          capture_output=True)
    if proc.returncode not in ok:
        raise AssertionError(f"git {' '.join(args)} exited with {proc.returncode}: "
                             f"{proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout


def can_symlink(directory):
    probe = os.path.join(directory, "symlink-probe")
    try:
        os.symlink("target", probe)
    except (OSError, NotImplementedError):
        return False
    os.remove(probe)
    return True


class Result:
    def __init__(self, rc, out, stdout, stderr):
        self.rc, self.out, self.stdout, self.stderr = rc, out, stdout, stderr


class RepoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="commit-plan-test.")
        self.addCleanup(remove_tree, self.tmp)
        self.repo = os.path.join(self.tmp, "repo")
        self.init_repo(self.repo)

    def init_repo(self, path, *options):
        os.makedirs(path, exist_ok=True)
        git(path, "init", "-q", *options)
        git(path, "config", "user.name", "Test")
        git(path, "config", "user.email", "test@example.com")

    def git(self, *args, **kwargs):
        return git(self.repo, *args, **kwargs)

    def rev(self, name):
        return self.git("rev-parse", "--verify", name).decode().strip()

    def write(self, rel, data, root=None):
        path = os.path.join(root or self.repo, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data.encode("utf-8") if isinstance(data, str) else data)
        return path

    def remove(self, rel):
        path = os.path.join(self.repo, *rel.split("/"))
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    def commit_all(self, message="base"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.rev("HEAD")

    def make_commit(self, files, parent=None, message="commit"):
        """Commit {path: (mode, data)} without touching the work tree; gitlink data is an oid."""
        index = os.path.join(self.tmp, "make-commit-index")
        if os.path.exists(index):
            os.remove(index)
        env = dict(ENV, GIT_INDEX_FILE=index)
        stream = b""
        for path, (mode, data) in files.items():
            if mode == "160000":
                self.git("update-index", "--add", "--cacheinfo", f"160000,{data},{path}",
                         env=env)
                continue
            raw = data.encode("utf-8") if isinstance(data, str) else data
            oid = self.git("hash-object", "-w", "--no-filters", "--stdin", input=raw)
            stream += f"{mode} blob {oid.decode().strip()}\t{path}\0".encode("utf-8")
        if stream:
            self.git("update-index", "-z", "--index-info", input=stream, env=env)
        tree = self.git("write-tree", env=env).decode().strip()
        args = ["commit-tree", tree, "-m", message]
        if parent:
            args += ["-p", parent]
        return self.git(*args).decode().strip()

    def tree_map(self, rev):
        out = self.git("ls-tree", "-r", "-z", "--full-tree", rev)
        result = {}
        for record in out.split(b"\0"):
            if record:
                meta, path = record.split(b"\t", 1)
                result[path.decode("utf-8")] = tuple(meta.decode().split(" "))
        return result

    def worktree_tree(self):
        index = os.path.join(self.tmp, "worktree-tree-index")
        if os.path.exists(index):
            os.remove(index)
        env = dict(ENV, GIT_INDEX_FILE=index)
        self.git("read-tree", "HEAD", env=env)
        self.git("add", "-A", env=env)
        return self.git("write-tree", env=env).decode().strip()

    def index_bytes(self, repo=None):
        repo = repo or self.repo
        path = git(repo, "rev-parse", "--git-path", "index").decode().strip()
        with open(os.path.join(repo, path), "rb") as f:
            return f.read()

    def worktree_files(self):
        result = {}
        for root, dirs, files in os.walk(self.repo):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in files:
                path = os.path.join(root, name)
                with open(path, "rb") as f:
                    result[os.path.relpath(path, self.repo)] = f.read()
        return result

    def refs(self):
        return (self.git("for-each-ref", "--format=%(refname) %(objectname)"),
                self.git("symbolic-ref", "-q", "HEAD", ok=(0, 1)),
                self.git("rev-parse", "-q", "--verify", "HEAD", ok=(0, 1)))

    def leftovers(self, repo=None):
        git_dir = git(repo or self.repo, "rev-parse", "--absolute-git-dir").decode().strip()
        return [name for name in os.listdir(git_dir) if name.startswith("commit-plan.")]

    def write_plan(self, rows=None, text=None, name="plan.jsonl"):
        if text is None:
            text = "".join(json.dumps({"message": m, "paths": p}) + "\n" for m, p in rows)
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as f:
            f.write(text.encode("utf-8") if isinstance(text, str) else text)
        return path

    def run_cp(self, *args, cwd=None):
        proc = subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd or self.repo, env=ENV,
                              capture_output=True)
        stderr = proc.stderr.decode("utf-8", "replace")
        if proc.returncode == 2:
            self.assertEqual(proc.stdout, b"", "a usage error prints nothing on stdout")
            return Result(2, None, proc.stdout, stderr)
        self.assertIn(proc.returncode, (0, 1), stderr)
        self.assertTrue(proc.stdout.endswith(b"\n"), proc.stdout)
        self.assertEqual(proc.stdout.count(b"\n"), 1, proc.stdout)
        for separator in SEPARATORS:
            self.assertNotIn(separator.encode("utf-8"), proc.stdout)
        out = json.loads(proc.stdout.decode("utf-8"))
        self.assertIsInstance(out, dict)
        if proc.returncode == 1:
            self.assertIsInstance(out.get("error"), str, out)
        return Result(proc.returncode, out, proc.stdout, stderr)

    def assert_refused(self, result, *, plan_error=False):
        self.assertEqual(result.rc, 1, result.out)
        if plan_error:
            self.assertIsInstance(result.out.get("errors"), list, result.out)
        else:
            self.assertNotIn("errors", result.out)

    def assert_error(self, result, *fragments):
        errors = result.out.get("errors") or []
        self.assertTrue(any(all(f in e for f in fragments) for e in errors),
                        f"no error holds {fragments}: {errors}")

    @staticmethod
    def statuses(out):
        return {p["path"]: p["status"] for p in out["paths"]}

    @staticmethod
    def expected_maps(base, target, rows):
        current, maps = dict(base), []
        for _, paths in rows:
            for path in paths:
                if path in target:
                    current[path] = target[path]
                else:
                    current.pop(path, None)
            maps.append(dict(current))
        return maps

    def message_of(self, commit):
        raw = self.git("cat-file", "commit", commit)
        return raw.split(b"\n\n", 1)[1].decode("utf-8")

    def parents_of(self, commit):
        return self.git("rev-list", "--parents", "-n", "1", commit).decode().split()[1:]


class PathsRangeTest(RepoTest):
    def test_lists_each_kind_of_change(self):
        self.git("config", "diff.ignoreSubmodules", "all")
        base = self.make_commit({
            "keep.txt": ("100644", "keep\n"),
            "mod.txt": ("100644", "before\n"),
            "del.txt": ("100644", "deleted content\n"),
            "exe.sh": ("100644", "#!/bin/sh\n"),
            "tolink": ("100644", "plain file\n"),
            "sub": ("160000", "1" * 40),
        })
        head = self.make_commit({
            "keep.txt": ("100644", "keep\n"),
            "mod.txt": ("100644", "after\n"),
            "exe.sh": ("100755", "#!/bin/sh\n"),
            "tolink": ("120000", "keep.txt"),
            "link": ("120000", "mod.txt"),
            "add.txt": ("100644", "added\n"),
            "sub": ("160000", "2" * 40),
            "newsub": ("160000", "3" * 40),
        }, parent=base)
        result = self.run_cp("paths", "--base", base, "--head", head)
        self.assertEqual(result.rc, 0, result.out)
        self.assertEqual(result.out["paths"], [
            {"path": "add.txt", "status": "A"},
            {"path": "del.txt", "status": "D"},
            {"path": "exe.sh", "status": "M"},
            {"path": "link", "status": "A"},
            {"path": "mod.txt", "status": "M"},
            {"path": "newsub", "status": "A"},
            {"path": "sub", "status": "M"},
            {"path": "tolink", "status": "M"},
        ])
        self.assertEqual(result.out["together"], [])

    def test_groups_renames_and_file_directory_switches(self):
        base = self.make_commit({
            "old.md": ("100644", TEXT),
            "a": ("100644", "the file a\n"),
            "c/d.txt": ("100644", "first child of c\n"),
            "c/e.txt": ("100644", "second child of c\n"),
        })
        head = self.make_commit({
            "new.md": ("100644", TEXT),
            "a/b.txt": ("100644", "first child of a\n"),
            "a/c.txt": ("100644", "second child of a\n"),
            "c": ("100644", "the file c\n"),
        }, parent=base)
        result = self.run_cp("paths", "--base", base, "--head", head)
        self.assertEqual(result.rc, 0, result.out)
        self.assertEqual(self.statuses(result.out), {
            "a": "D", "a/b.txt": "A", "a/c.txt": "A", "c": "A", "c/d.txt": "D",
            "c/e.txt": "D", "new.md": "A", "old.md": "D"})
        self.assertEqual(result.out["together"], [
            {"reason": "rename", "paths": ["old.md", "new.md"]},
            {"reason": "dir-switch", "paths": ["a", "a/b.txt", "a/c.txt"]},
            {"reason": "dir-switch", "paths": ["c", "c/d.txt", "c/e.txt"]},
        ])

    def test_escapes_line_separators_in_its_output(self):
        name = "sep" + SEPARATORS + "日.txt"
        base = self.make_commit({"a.txt": ("100644", "a\n")})
        head = self.make_commit({"a.txt": ("100644", "a\n"), name: ("100644", "x\n")},
                                parent=base)
        result = self.run_cp("paths", "--base", base, "--head", head)
        self.assertEqual(result.out["paths"], [{"path": name, "status": "A"}])
        self.assertIn("日".encode("utf-8"), result.stdout)

    def test_same_commit_has_no_paths(self):
        base = self.make_commit({"a.txt": ("100644", "a\n")})
        result = self.run_cp("paths", "--base", base, "--head", base)
        self.assertEqual(result.rc, 0)
        self.assertEqual(result.out, {"paths": [], "together": []})

    def test_refuses_a_bad_range(self):
        base = self.make_commit({"a.txt": ("100644", "a\n")})
        head = self.make_commit({"a.txt": ("100644", "b\n")}, parent=base)
        other = self.make_commit({"x.txt": ("100644", "x\n")})
        for args in (["--base", head, "--head", base],
                     ["--base", other, "--head", head],
                     ["--base", "no-such-ref", "--head", head],
                     ["--base=-x", "--head", head],
                     ["--base", base, "--head", "no-such-ref"]):
            with self.subTest(args=args):
                self.assert_refused(self.run_cp("paths", *args))

    def test_refuses_outside_a_repository(self):
        outside = os.path.join(self.tmp, "outside")
        os.mkdir(outside)
        result = self.run_cp("paths", "--worktree", cwd=outside)
        self.assert_refused(result)


class PathsWorktreeTest(RepoTest):
    def setUp(self):
        super().setUp()
        self.write("keep.txt", "keep\n")
        self.write("mod.txt", "before\n")
        self.write("del.txt", "deleted content\n")
        self.base = self.commit_all()

    def paths(self, *args, cwd=None):
        result = self.run_cp("paths", "--worktree", *args, cwd=cwd)
        self.assertEqual(result.rc, 0, result.out)
        return result.out

    def test_lists_tracked_and_untracked_changes(self):
        self.write("mod.txt", "after\n")
        self.remove("del.txt")
        self.write("add.txt", "added\n")
        before = self.index_bytes()
        out = self.paths()
        self.assertEqual(out["paths"], [
            {"path": "add.txt", "status": "A"},
            {"path": "del.txt", "status": "D"},
            {"path": "mod.txt", "status": "M"},
        ])
        self.assertEqual(self.index_bytes(), before)
        self.assertEqual(self.leftovers(), [])

    def test_lists_a_mode_change(self):
        if self.git("config", "--bool", "core.fileMode").strip() != b"true":
            self.skipTest("the work tree cannot hold the executable bit")
        os.chmod(os.path.join(self.repo, "keep.txt"), 0o755)
        self.assertEqual(self.statuses(self.paths()), {"keep.txt": "M"})

    def test_lists_a_symlink(self):
        if not can_symlink(self.tmp):
            self.skipTest("symbolic links cannot be created here")
        os.symlink("keep.txt", os.path.join(self.repo, "link"))
        self.assertEqual(self.statuses(self.paths()), {"link": "A"})

    def test_lists_a_gitlink_change_that_diff_ignores(self):
        sub = os.path.join(self.repo, "sub")
        self.init_repo(sub)
        git(sub, "commit", "-q", "--allow-empty", "-m", "one")
        self.commit_all("add sub")
        git(sub, "commit", "-q", "--allow-empty", "-m", "two")
        self.git("config", "diff.ignoreSubmodules", "all")
        self.assertEqual(self.statuses(self.paths()), {"sub": "M"})

    def test_leaves_out_ignored_and_excluded_paths(self):
        self.write(".gitignore", "ignored.txt\n")
        self.commit_all("ignore")
        self.write("ignored.txt", "ignored\n")
        self.write(".claude/tmp/scratch.txt", "scratch\n")
        nested = os.path.join(self.repo, ".claude", "worktrees", "wt")
        self.init_repo(nested)
        git(nested, "commit", "-q", "--allow-empty", "-m", "nested")
        self.write("ex/abs.txt", "absolute\n")
        self.write("ex/rel.txt", "relative\n")
        self.write("exdir/x.txt", "x\n")
        self.write("exdir/y/z.txt", "z\n")
        self.write("real.txt", "real\n")
        before = self.index_bytes()
        out = self.paths(
            "--exclude", os.path.join(self.repo, "ex", "abs.txt"),
            "--exclude", "rel.txt",
            "--exclude", os.path.join("..", "exdir"),
            "--exclude", "no-such-path",
            "--exclude", os.path.join(self.tmp, "outside.txt"),
            cwd=os.path.join(self.repo, "ex"))
        self.assertEqual(out, {"paths": [{"path": "real.txt", "status": "A"}], "together": []})
        self.assertEqual(self.index_bytes(), before)

    def test_does_not_read_under_excluded_paths(self):
        for rel in (".claude/tmp/fresh", ".claude/worktrees/wt", "scratch/fresh"):
            nested = os.path.join(self.repo, *rel.split("/"))
            self.init_repo(nested)
            self.write("file.txt", "in a repository with no commit\n", root=nested)
        self.write("real.txt", "real\n")
        out = self.paths("--exclude", "scratch")
        self.assertEqual(out, {"paths": [{"path": "real.txt", "status": "A"}], "together": []})

    def test_excludes_paths_whether_or_not_they_are_ignored(self):
        for ignored in (False, True):
            with self.subTest(ignored=ignored):
                if ignored:
                    self.write(".gitignore", ".claude/tmp/\n")
                    self.commit_all("ignore tmp")
                self.write(".claude/tmp/a.txt", "scratch\n")
                self.write(f"real-{ignored}.txt", "real\n")
                self.assertEqual(self.statuses(self.paths()), {f"real-{ignored}.txt": "A"})
        with self.subTest("a tracked path under an ignored directory"):
            self.write(".gitignore", ".claude/tmp/\nvendor/\n")
            self.write("vendor/lib.txt", "lib\n")
            self.git("add", "-f", "vendor/lib.txt")
            self.commit_all("vendor")
            self.write("vendor/lib.txt", "changed lib\n")
            self.write("real-vendor.txt", "real\n")
            self.assertEqual(self.statuses(self.paths("--exclude", "vendor/lib.txt")),
                             {"real-vendor.txt": "A"})

    def test_excludes_paths_inside_a_submodule(self):
        claude = os.path.join(self.repo, ".claude")
        self.init_repo(claude)
        git(claude, "commit", "-q", "--allow-empty", "-m", "config")
        self.commit_all("add .claude")
        self.write("real.txt", "real\n")
        self.assertEqual(self.statuses(self.paths("--exclude", ".claude/x")), {"real.txt": "A"})

    def test_excludes_paths_beyond_a_symlink(self):
        if not can_symlink(self.tmp):
            self.skipTest("symbolic links cannot be created here")
        self.write("config/tmp/scratch.txt", "scratch\n")
        os.symlink("config", os.path.join(self.repo, ".claude"), target_is_directory=True)
        self.assertEqual(self.statuses(self.paths()),
                         {".claude": "A", "config/tmp/scratch.txt": "A"})

    def test_keeps_the_rename_pair_despite_a_copy_under_an_excluded_path(self):
        self.write("doc.md", TEXT)
        self.commit_all("doc")
        self.remove("doc.md")
        self.write("guide.md", TEXT)
        self.write(".claude/tmp/doc.md", TEXT)
        self.write("scratch/doc.md", TEXT)
        out = self.paths("--exclude", "scratch")
        self.assertEqual(self.statuses(out), {"doc.md": "D", "guide.md": "A"})
        self.assertEqual(out["together"], [{"reason": "rename", "paths": ["doc.md", "guide.md"]}])

    def test_groups_renames_and_file_directory_switches(self):
        self.write("old.md", TEXT)
        self.write("a", "the file a\n")
        self.write("c/d.txt", "first child of c\n")
        self.write("c/e.txt", "second child of c\n")
        self.commit_all("layout")
        self.remove("old.md")
        self.write("new.md", TEXT)
        self.remove("a")
        self.write("a/b.txt", "first child of a\n")
        self.remove("c")
        self.write("c", "the file c\n")
        out = self.paths()
        self.assertEqual(out["together"], [
            {"reason": "rename", "paths": ["old.md", "new.md"]},
            {"reason": "dir-switch", "paths": ["a", "a/b.txt"]},
            {"reason": "dir-switch", "paths": ["c", "c/d.txt", "c/e.txt"]},
        ])

    def test_refuses_staged_changes_but_not_intent_to_add(self):
        self.write("new.txt", "new\n")
        self.git("add", "-N", "new.txt")
        self.assertEqual(self.statuses(self.paths()), {"new.txt": "A"})
        self.write("mod.txt", "after\n")
        self.git("add", "mod.txt")
        plan = self.write_plan([("Change", ["mod.txt", "new.txt"])])
        for args in (["paths", "--worktree"], ["check", "--worktree", "--plan", plan],
                     ["commit", "--worktree", "--plan", plan]):
            with self.subTest(args=args[0]):
                self.assert_refused(self.run_cp(*args))
        self.assertEqual(self.rev("HEAD"), self.base)

    def test_refuses_an_operation_in_progress(self):
        self.write("mod.txt", "after\n")
        for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
            with self.subTest(name=name):
                path = os.path.join(self.repo, ".git", name)
                with open(path, "w") as f:
                    f.write(self.base + "\n")
                try:
                    self.assert_refused(self.run_cp("paths", "--worktree"))
                finally:
                    os.remove(path)

    def test_refuses_an_unborn_head(self):
        fresh = os.path.join(self.tmp, "fresh")
        self.init_repo(fresh)
        self.write("a.txt", "a\n", root=fresh)
        self.assert_refused(self.run_cp("paths", "--worktree", cwd=fresh))

    def test_sees_a_racily_clean_rewrite(self):
        self.git("config", "core.checkStat", "minimal")
        self.git("config", "core.trustctime", "false")
        stamp = int(time.time()) - 100
        path = self.write("racy.txt", "aaaa\n")
        os.utime(path, (stamp, stamp))
        self.commit_all("racy")
        self.write("racy.txt", "bbbb\n")
        os.utime(path, (stamp, stamp))
        os.utime(os.path.join(self.repo, ".git", "index"), (stamp, stamp))
        self.assertEqual(self.statuses(self.paths()), {"racy.txt": "M"})


class CheckTest(RepoTest):
    def setUp(self):
        super().setUp()
        self.base = self.make_commit({
            "old.md": ("100644", TEXT),
            "x": ("100644", "the file x\n"),
            "keep.txt": ("100644", "keep\n"),
        })
        self.head = self.make_commit({
            "new.md": ("100644", TEXT),
            "x/y.txt": ("100644", "child of x\n"),
            "keep.txt": ("100644", "keep\n"),
            "a.md": ("100644", "alpha\n"),
            "b.md": ("100644", "bravo\n"),
        }, parent=self.base)
        self.good = [("Add a", ["a.md"]), ("Add b", ["b.md"]),
                     ("Rename old to new", ["old.md", "new.md"]),
                     ("Turn x into a directory", ["x", "x/y.txt"])]

    def check(self, rows=None, text=None, base=None, head=None):
        plan = self.write_plan(rows, text)
        return self.run_cp("check", "--base", base or self.base, "--head", head or self.head,
                           "--plan", plan)

    def rows_text(self, rows):
        return [json.dumps({"message": m, "paths": p}) for m, p in rows]

    def test_accepts_a_good_plan(self):
        result = self.check(self.good)
        self.assertEqual(result.rc, 0, result.out)
        self.assertEqual(result.out, {"ok": True, "count": 4})

    def test_accepts_blank_lines_and_crlf(self):
        lines = self.rows_text(self.good)
        text = "\r\n" + "\r\n\r\n".join(lines) + "\r\n  \r\n"
        result = self.check(text=text)
        self.assertEqual(result.out, {"ok": True, "count": 4})

    def test_reports_missing_and_extra_paths(self):
        rows = [("Add a", ["a.md", "zzz.md"])] + self.good[2:]
        result = self.check(rows)
        self.assert_refused(result, plan_error=True)
        self.assertIs(result.out["ok"], False)
        self.assert_error(result, "line 1", '"zzz.md"')
        self.assert_error(result, '"b.md"')

    def test_reports_duplicates(self):
        for rows, lines in (([("Add a", ["a.md"]), ("Add a again", ["a.md", "b.md"])] +
                             self.good[2:], ("1", "2")),
                            ([("Add", ["a.md", "b.md", "a.md"])] + self.good[2:], ("1",))):
            with self.subTest(rows=rows[:2]):
                result = self.check(rows)
                self.assert_refused(result, plan_error=True)
                self.assert_error(result, '"a.md"', *lines)

    def test_reports_bad_records(self):
        cases = {
            "empty paths": json.dumps({"message": "m", "paths": []}),
            "paths not an array": json.dumps({"message": "m", "paths": "a.md"}),
            "non-string path": json.dumps({"message": "m", "paths": [1]}),
            "empty message": json.dumps({"message": "", "paths": ["a.md"]}),
            "blank first line": json.dumps({"message": "  \t\nbody", "paths": ["a.md"]}),
            "non-string message": json.dumps({"message": 3, "paths": ["a.md"]}),
            "NUL in message": json.dumps({"message": "a\u0000b", "paths": ["a.md"]}),
            "unknown key": json.dumps({"message": "m", "paths": ["a.md"], "extra": 1}),
            "missing key": json.dumps({"paths": ["a.md"]}),
            "not an object": json.dumps(["a.md"]),
            "not JSON": "{message: m}",
            "unpaired surrogate in paths": json.dumps({"message": "m", "paths": ["\ud800"]}),
            "unpaired surrogate in message": json.dumps({"message": "\ud800", "paths": ["a.md"]}),
        }
        rest = "\n".join(self.rows_text(self.good[1:]))
        for name, line in cases.items():
            with self.subTest(name):
                result = self.check(text="\n" + line + "\n" + rest + "\n")
                self.assert_refused(result, plan_error=True)
                self.assert_error(result, "line 2")
        unknown = self.check(text=cases["unknown key"] + "\n" + rest + "\n")
        self.assert_error(unknown, '"extra"')
        missing = self.check(text=cases["missing key"] + "\n" + rest + "\n")
        self.assert_error(missing, '"message"')

    def test_reports_an_empty_or_missing_plan_file(self):
        for text in ("", "\n  \n"):
            with self.subTest(text=text):
                self.assert_refused(self.check(text=text), plan_error=True)
        result = self.run_cp("check", "--base", self.base, "--head", self.head,
                             "--plan", os.path.join(self.tmp, "no-such-plan.jsonl"))
        self.assert_refused(result, plan_error=True)
        self.assertIs(result.out["ok"], False)

    def test_reports_a_plan_not_in_utf8(self):
        result = self.check(text=b'{"message": "\xff", "paths": ["a.md"]}\n')
        self.assert_refused(result, plan_error=True)

    def test_reports_one_value_across_lines(self):
        text = json.dumps({"message": "All", "paths": [p for _, ps in self.good for p in ps]},
                          indent=2)
        result = self.check(text=text)
        self.assert_refused(result, plan_error=True)
        self.assert_error(result, "one line")

    def test_reports_split_groups(self):
        for rows, reason, lines in (
                (self.good[:2] + [("Remove old", ["old.md"]), ("Add new", ["new.md"]),
                                  self.good[3]], "rename", ("3", "4")),
                (self.good[:3] + [("Remove x", ["x"]), ("Add x/y", ["x/y.txt"])],
                 "dir-switch", ("4", "5"))):
            with self.subTest(reason=reason):
                result = self.check(rows)
                self.assert_refused(result, plan_error=True)
                self.assert_error(result, reason, *lines)

    def test_reports_nothing_to_plan(self):
        result = self.check([("Add a", ["a.md"])], head=self.base)
        self.assert_refused(result, plan_error=True)

    def test_refuses_a_base_that_is_not_an_ancestor(self):
        result = self.check(self.good, base=self.head, head=self.base)
        self.assert_refused(result)
        self.assertIs(result.out["ok"], False)


class BuildTest(RepoTest):
    def setUp(self):
        super().setUp()
        self.write("keep.txt", "keep\n")
        self.write("mod.txt", "before\n")
        self.write("del.txt", "deleted content\n")
        self.write("exe.sh", "#!/bin/sh\necho hi\n")
        self.write("old.md", TEXT)
        self.write("x", "the file x\n")
        self.base = self.commit_all()

    def head_commit(self, extra=None):
        files = {
            "keep.txt": ("100644", "keep\n"),
            "mod.txt": ("100644", "after\n"),
            "exe.sh": ("100755", "#!/bin/sh\necho hi\n"),
            "new.md": ("100644", TEXT),
            "x/y.txt": ("100644", "child of x\n"),
            "crlf.txt": ("100644", b"one\r\ntwo\r\n"),
            "bin.dat": ("100644", bytes(range(256)) * 4),
            "dir with space/日本語 ファイル.txt": ("100644", "x\n"),
        }
        files.update(extra or {})
        return self.make_commit(files, parent=self.base)

    def rows(self):
        return [
            ("Remove the deleted file", ["del.txt"]),
            ("Change mod and make exe executable", ["mod.txt", "exe.sh"]),
            ("Rename old to new", ["old.md", "new.md"]),
            ("Turn x into a directory", ["x", "x/y.txt"]),
            ("Add data files",
             ["crlf.txt", "bin.dat",
              "dir with space/日本語 ファイル.txt"]),
        ]

    def build(self, head, rows=None, text=None):
        plan = self.write_plan(rows, text)
        return self.run_cp("build", "--base", self.base, "--head", head, "--plan", plan)

    def test_builds_the_plan_without_touching_the_repository(self):
        self.git("config", "core.autocrlf", "true")
        head = self.head_commit()
        rows = self.rows()
        refs, index, files = self.refs(), self.index_bytes(), self.worktree_files()
        result = self.build(head, rows)
        self.assertEqual(result.rc, 0, result.out)
        commits = [c["commit"] for c in result.out["commits"]]
        self.assertEqual(result.out["count"], len(rows))
        self.assertEqual(len(commits), len(rows))
        self.assertEqual(result.out["commit"], commits[-1])
        self.assertEqual(self.rev(commits[-1] + "^{tree}"), self.rev(head + "^{tree}"))
        expected = self.expected_maps(self.tree_map(self.base), self.tree_map(head), rows)
        parent = self.base
        for commit, (message, _), want, entry in zip(commits, rows, expected,
                                                     result.out["commits"]):
            self.assertEqual(self.parents_of(commit), [parent])
            self.assertEqual(self.tree_map(commit), want)
            self.assertEqual(self.message_of(commit), message + "\n")
            self.assertEqual(entry["subject"], message)
            parent = commit
        self.assertEqual(self.refs(), refs)
        self.assertEqual(self.index_bytes(), index)
        self.assertEqual(self.worktree_files(), files)
        self.assertEqual(self.leftovers(), [])

    def test_keeps_a_multiline_message_in_its_saved_form(self):
        head = self.head_commit()
        rows = self.rows()
        rows[0] = ("Subject line\n\nBody one\nBody two\n\n \n", rows[0][1])
        result = self.build(head, rows)
        self.assertEqual(result.rc, 0, result.out)
        first = result.out["commits"][0]
        self.assertEqual(self.message_of(first["commit"]), "Subject line\n\nBody one\nBody two\n")
        self.assertEqual(first["subject"], "Subject line")

    def test_one_commit_for_everything(self):
        head = self.head_commit()
        paths = [p for _, ps in self.rows() for p in ps]
        result = self.build(head, [("Everything", paths)])
        self.assertEqual(result.rc, 0, result.out)
        self.assertEqual(result.out["count"], 1)
        self.assertEqual(self.rev(result.out["commit"] + "^{tree}"), self.rev(head + "^{tree}"))

    def test_refuses_a_failing_plan(self):
        head = self.head_commit()
        result = self.build(head, self.rows()[1:])
        self.assert_refused(result, plan_error=True)
        self.assertNotIn("commit", result.out)
        self.assertEqual(self.leftovers(), [])

    def test_signs_when_commit_gpgsign_is_set(self):
        head = self.head_commit()
        self.git("config", "commit.gpgSign", "true")
        self.git("config", "gpg.program", os.path.join(self.tmp, "no-such-gpg"))
        refs = self.refs()
        result = self.build(head, self.rows())
        self.assert_refused(result)
        self.assertEqual(self.refs(), refs)
        self.assertEqual(self.leftovers(), [])

    def test_sha256_repository(self):
        repo = os.path.join(self.tmp, "sha256")
        try:
            self.init_repo(repo, "--object-format=sha256")
        except AssertionError:
            self.skipTest("git does not support --object-format=sha256")
        self.repo = repo
        base = self.make_commit({"a.txt": ("100644", "a\n"), "b.txt": ("100644", "b\n")})
        head = self.make_commit({"a.txt": ("100644", "changed\n")}, parent=base)
        plan = self.write_plan([("Remove b", ["b.txt"]), ("Change a", ["a.txt"])])
        result = self.run_cp("build", "--base", base, "--head", head, "--plan", plan)
        self.assertEqual(result.rc, 0, result.out)
        self.assertEqual(len(result.out["commit"]), 64)
        self.assertEqual(self.rev(result.out["commit"] + "^{tree}"), self.rev(head + "^{tree}"))
        self.assertEqual(self.tree_map(result.out["commits"][0]["commit"]),
                         {"a.txt": self.tree_map(base)["a.txt"]})
        self.assertEqual(self.leftovers(repo), [])


class CommitTest(RepoTest):
    def setUp(self):
        super().setUp()
        self.write("keep.txt", "keep\n")
        self.write("mod.txt", "before\n")
        self.write("del.txt", "deleted content\n")
        self.write("old.md", TEXT)
        self.write("a", "the file a\n")
        self.write("c/d.txt", "first child of c\n")
        self.write("c/e.txt", "second child of c\n")
        self.write("notes.md", "notes\n")
        self.base = self.commit_all()

    def change_layout(self):
        self.write("mod.txt", "after\n")
        self.remove("del.txt")
        self.remove("old.md")
        self.write("new.md", TEXT)
        self.remove("a")
        self.write("a/b.txt", "first child of a\n")
        self.remove("c")
        self.write("c", "the file c\n")
        return [("Change mod", ["mod.txt"]),
                ("Remove del", ["del.txt"]),
                ("Rename old to new", ["old.md", "new.md"]),
                ("Turn a into a directory", ["a", "a/b.txt"]),
                ("Turn c into a file", ["c", "c/d.txt", "c/e.txt"])]

    def commit(self, rows, *excludes):
        plan = self.write_plan(rows)
        args = [arg for e in excludes for arg in ("--exclude", e)]
        return self.run_cp("commit", "--worktree", *args, "--plan", plan)

    def hook(self, body):
        hooks = os.path.join(self.tmp, "hooks")
        os.makedirs(hooks, exist_ok=True)
        path = os.path.join(hooks, "pre-commit")
        with open(path, "wb") as f:
            f.write(("#!/bin/sh\n" + body).encode("utf-8"))
        os.chmod(path, 0o755)
        self.git("config", "core.hooksPath", hooks.replace("\\", "/"))

    def assert_commits(self, result, rows):
        commits = [c["commit"] for c in result.out["commits"]]
        listed = self.git("rev-list", "--reverse", f"{self.base}..HEAD").decode().split()
        self.assertEqual(listed, commits)
        target = self.tree_map(result.out["snapshot"])
        expected = self.expected_maps(self.tree_map(self.base), target, rows)
        for commit, (message, _), want, entry in zip(commits, rows, expected,
                                                     result.out["commits"]):
            self.assertEqual(self.tree_map(commit), want)
            self.assertEqual(self.message_of(commit), message.rstrip() + "\n")
            self.assertEqual(entry["subject"], message.split("\n", 1)[0])

    def test_commits_each_line_in_order(self):
        rows = self.change_layout()
        files = self.worktree_files()
        snapshot = self.worktree_tree()
        result = self.commit(rows)
        self.assertEqual(result.rc, 0, result.out)
        self.assertEqual(result.out["count"], len(rows))
        self.assertEqual(result.out["commit"], self.rev("HEAD"))
        self.assertIs(result.out["tree_match"], True)
        self.assertEqual(result.out["snapshot"], snapshot)
        self.assertEqual(self.rev("HEAD^{tree}"), snapshot)
        self.assert_commits(result, rows)
        self.assertEqual(self.worktree_files(), files)
        self.assertEqual(self.leftovers(), [])
        after = self.run_cp("paths", "--worktree")
        self.assertEqual(after.out, {"paths": [], "together": []})

    def test_stages_only_the_literal_paths_of_each_line(self):
        names = ["[ab].txt", "with space.txt", "日本語.txt"]
        lookalikes = ["a.txt", "with", "日.txt"]
        if not IS_WINDOWS:
            names += ["f*.txt", "q?.txt", ":colon.txt"]
            lookalikes += ["fa.txt", "qa.txt", "colon.txt"]
        for name in names + lookalikes:
            self.write(name, f"content of {name}\n")
        rows = [("Add the odd names", names), ("Add the lookalikes", lookalikes)]
        result = self.commit(rows)
        self.assertEqual(result.rc, 0, result.out)
        self.assertIs(result.out["tree_match"], True)
        self.assert_commits(result, rows)

    def test_stages_tracked_paths_under_an_ignored_directory(self):
        self.write(".gitignore", "vendor/\ngone/\n")
        self.write("vendor/lib.txt", "lib\n")
        self.write("gone", "a file that becomes an ignored directory\n")
        self.git("add", ".gitignore", "gone")
        self.git("add", "-f", "vendor/lib.txt")
        self.git("commit", "-q", "-m", "vendor")
        self.base = self.rev("HEAD")
        self.write("vendor/lib.txt", "changed lib\n")
        self.write("vendor/untracked.txt", "ignored\n")
        self.write("vendor/new.txt", "intent to add\n")
        self.git("add", "-N", "-f", "vendor/new.txt")
        self.remove("gone")
        self.write("gone/ignored.txt", "ignored\n")
        self.write("mod.txt", "after\n")
        rows = [("Change the vendored files", ["vendor/lib.txt", "vendor/new.txt"]),
                ("Remove gone", ["gone"]), ("Change mod", ["mod.txt"])]
        result = self.commit(rows)
        self.assertEqual(result.rc, 0, result.out)
        self.assertEqual(result.out["count"], 3)
        self.assertIs(result.out["tree_match"], True)
        self.assert_commits(result, rows)
        self.assertNotIn("vendor/untracked.txt", self.tree_map("HEAD"))

    def test_leaves_excluded_paths_in_the_work_tree(self):
        self.write("mod.txt", "after\n")
        self.write("notes.md", "edited notes\n")
        self.write(".claude/tmp/x.txt", "scratch\n")
        self.write("scratch/y.txt", "scratch\n")
        result = self.commit([("Change mod", ["mod.txt"])], "notes.md", "scratch")
        self.assertEqual(result.rc, 0, result.out)
        self.assertIs(result.out["tree_match"], True)
        head = self.tree_map("HEAD")
        self.assertEqual(head["notes.md"], self.tree_map(self.base)["notes.md"])
        self.assertNotIn(".claude/tmp/x.txt", head)
        self.assertNotIn("scratch/y.txt", head)
        with open(os.path.join(self.repo, "notes.md"), "rb") as f:
            self.assertEqual(f.read(), b"edited notes\n")
        rest = self.run_cp("paths", "--worktree", "--exclude", "notes.md", "--exclude", "scratch")
        self.assertEqual(rest.out["paths"], [])
        unexcluded = self.run_cp("paths", "--worktree")
        self.assertEqual(self.statuses(unexcluded.out),
                         {"notes.md": "M", "scratch/y.txt": "A"})

    def test_refuses_staged_changes(self):
        self.write("mod.txt", "after\n")
        self.git("add", "mod.txt")
        result = self.commit([("Change mod", ["mod.txt"])])
        self.assert_refused(result)
        self.assertEqual(result.out["count"], 0)
        self.assertEqual(result.out["commits"], [])
        self.assertIsNone(result.out["snapshot"])
        self.assertEqual(self.rev("HEAD"), self.base)

    def test_refuses_a_failing_plan(self):
        self.write("mod.txt", "after\n")
        self.write("other.txt", "other\n")
        result = self.commit([("Change mod", ["mod.txt"])])
        self.assert_refused(result, plan_error=True)
        self.assertEqual(result.out["count"], 0)
        self.assertEqual(result.out["commits"], [])
        self.assertIsInstance(result.out["snapshot"], str)
        self.assertEqual(self.rev("HEAD"), self.base)

    def test_runs_the_pre_commit_hook_per_line(self):
        log = os.path.join(self.tmp, "hook.log").replace("\\", "/")
        self.hook(f"echo ran >> '{log}'\n")
        self.write("mod.txt", "after\n")
        self.write("notes.md", "edited notes\n")
        result = self.commit([("Change mod", ["mod.txt"]), ("Change notes", ["notes.md"])])
        self.assertEqual(result.rc, 0, result.out)
        with open(log) as f:
            self.assertEqual(f.read().split(), ["ran", "ran"])

    def test_stops_where_the_hook_fails(self):
        count = os.path.join(self.tmp, "count").replace("\\", "/")
        self.hook(f"n=$(cat '{count}' 2>/dev/null || echo 0)\nn=$((n + 1))\n"
                  f"echo $n > '{count}'\n[ $n -ne 2 ]\n")
        rows = self.change_layout()
        files = self.worktree_files()
        snapshot = self.worktree_tree()
        result = self.commit(rows)
        self.assert_refused(result)
        self.assertEqual(result.out["count"], 1)
        self.assertEqual(len(result.out["commits"]), 1)
        self.assertEqual(result.out["commits"][0]["commit"], self.rev("HEAD"))
        self.assertEqual(self.rev("HEAD^"), self.base)
        self.assertEqual(result.out["snapshot"], snapshot)
        self.assertEqual(self.worktree_files(), files)
        self.git("diff", "--cached", "--quiet")
        rest = self.run_cp("paths", "--worktree")
        self.assertEqual(sorted(self.statuses(rest.out)),
                         sorted(p for _, ps in rows[1:] for p in ps))

    def test_reports_a_tree_the_hook_changed(self):
        self.hook("printf 'hooked\\n' >> keep.txt && git add keep.txt\n")
        self.write("mod.txt", "after\n")
        result = self.commit([("Change mod", ["mod.txt"])])
        self.assertEqual(result.rc, 0, result.out)
        self.assertIs(result.out["tree_match"], False)
        self.assertNotEqual(self.rev("HEAD^{tree}"), result.out["snapshot"])

    def test_saves_each_message_as_build_does(self):
        self.git("config", "commit.cleanup", "strip")
        self.write("mod.txt", "after\n")
        self.write("notes.md", "edited notes\n")
        rows = [("Subject\n\n\nBody one  \n#123 stays in the body\n\n \n", ["mod.txt"]),
                ("#42 Subject that starts with a hash", ["notes.md"])]
        result = self.commit(rows)
        self.assertEqual(result.rc, 0, result.out)
        self.assert_commits(result, rows)

    def test_stops_between_lines_on_sigterm(self):
        self.stops_between_lines_on("TERM")

    def test_stops_between_lines_on_sigint(self):
        self.stops_between_lines_on("INT")

    def stops_between_lines_on(self, sig):
        if IS_WINDOWS:
            self.skipTest("the script cannot be sent a POSIX signal on Windows")
        # The hook's parent is git commit, whose parent is the script.
        self.hook(f"kill -{sig} $(ps -o ppid= -p $PPID)\n")
        self.write("mod.txt", "after\n")
        self.write("notes.md", "edited notes\n")
        result = self.commit([("Change mod", ["mod.txt"]), ("Change notes", ["notes.md"])])
        self.assert_refused(result)
        self.assertIn("signal", result.out["error"])
        self.assertEqual(result.out["count"], 1)
        self.assertEqual(result.out["commits"][0]["commit"], self.rev("HEAD"))
        self.assertEqual(self.rev("HEAD^"), self.base)
        self.git("diff", "--cached", "--quiet")
        git_dir = self.git("rev-parse", "--absolute-git-dir").decode().strip()
        self.assertFalse(os.path.exists(os.path.join(git_dir, "index.lock")))
        self.assertEqual(self.leftovers(), [])

    def test_commits_in_a_linked_worktree(self):
        self.git("worktree", "add", "-q", "-b", "feature", ".claude/worktrees/wt")
        wt = os.path.join(self.repo, ".claude", "worktrees", "wt")
        self.write("mod.txt", "after\n", root=wt)
        self.write("new.txt", "new\n", root=wt)
        main = (self.git("symbolic-ref", "HEAD"), self.index_bytes())
        listed = self.run_cp("paths", "--worktree", cwd=wt)
        self.assertEqual(listed.rc, 0, listed.out)
        self.assertEqual(self.statuses(listed.out), {"mod.txt": "M", "new.txt": "A"})
        plan = self.write_plan([("Change mod", ["mod.txt"]), ("Add new", ["new.txt"])])
        result = self.run_cp("commit", "--worktree", "--plan", plan, cwd=wt)
        self.assertEqual(result.rc, 0, result.out)
        self.assertIs(result.out["tree_match"], True)
        commits = [c["commit"] for c in result.out["commits"]]
        self.assertEqual(len(commits), 2)
        stacked = self.git("rev-list", "--reverse", f"{self.base}..feature").decode().split()
        self.assertEqual(stacked, commits)
        self.assertEqual(self.parents_of(commits[0]), [self.base])
        self.assertEqual(self.rev("HEAD"), self.base)
        self.assertEqual((self.git("symbolic-ref", "HEAD"), self.index_bytes()), main)
        git(wt, "diff", "--cached", "--quiet")
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(self.leftovers(wt), [])


class UsageTest(RepoTest):
    def setUp(self):
        super().setUp()
        self.write("a.txt", "a\n")
        self.base = self.commit_all()
        self.plan = self.write_plan([("Change", ["a.txt"])])

    def test_usage_errors_exit_2_with_nothing_on_stdout(self):
        b, p = self.base, self.plan
        cases = [
            [],
            ["frobnicate"],
            ["paths"],
            ["paths", "--base", b],
            ["paths", "--head", b],
            ["paths", "--base", b, "--head", b, "--worktree"],
            ["paths", "--worktree", "--plan", p],
            ["paths", "--worktree", "--bogus"],
            ["paths", "--base", b, "--head", b, "--exclude", "x"],
            ["paths", "--worktree", "--exclude", "."],
            ["paths", "--worktree", "--exclude", self.repo],
            ["check", "--worktree"],
            ["check", "--base", b, "--head", b],
            ["build", "--worktree", "--plan", p],
            ["build", "--base", b, "--plan", p],
            ["build", "--base", b, "--head", b],
            ["commit", "--plan", p],
            ["commit", "--worktree"],
            ["commit", "--base", b, "--head", b, "--plan", p],
            ["commit", "--worktree", "--exclude", ".", "--plan", p],
        ]
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cp(*args)
                self.assertEqual(result.rc, 2, result.out)


if __name__ == "__main__":
    unittest.main()
