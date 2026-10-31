#!/usr/bin/env python3
"""gh-review-test.py — self-test for cgh/scripts/gh-review.py with GitHub and git faked.

Usage: python3 tests/gh-review-test.py
"""

import glob
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = importlib.util.spec_from_file_location(
    "gh_review", os.path.join(ROOT, "cgh", "scripts", "gh-review.py"))
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

URL = "https://github.com/acme/app/pull/7"
HEAD = "a" * 40
BASE = "b" * 40

DOCUMENT = f"""# Parallel Code Review Report

- **日付:** 2026-10-31
- **PR:** {URL} (head {HEAD}, base {BASE})
- **Trust:** off
- **対象範囲:** PR #7
- **レビュアー:** a, b

## Critical

### C-1 — `src/a.py:10` [Bug]

- **レビュアー:** a

**指摘:**

null を参照する。
@alice に確認済み。

<!-- METADATA(C-1) -->
- **Triage:** 🔧 Will Fix (assignee: py) — 妥当
- **Estimate:** ▶️ Maintain — Cost: M, Future: S, Signals: b,d — ADR: x-adr-C-1.md — Plan: (1) src/a.py:10 — null を確認 (2) src/a.py:12 — ログを追加
<!-- /METADATA(C-1) -->

---

## Major

### M-1 — `src/a.py:99` [Bug]

- **レビュアー:** a

**指摘:**

差分外の行を壊す。

<!-- METADATA(M-1) -->
- **Triage:** 🔧 Will Fix (assignee: py) — 妥当
- **Estimate:** 🔻 Downgrade — Cost: L, Future: S, Signals: b — 別 PR を推奨
<!-- /METADATA(M-1) -->

---

### M-2 — `docs/other.md:3`

**指摘:**

差分外のファイルに影響する。

<!-- METADATA(M-2) -->
- **Triage:** 🚫 Won't Fix — 誤検知
<!-- /METADATA(M-2) -->

---

## Minor

### mi-1 — `src/b.py:2` [Style]

**指摘:**

命名が揺れている。

<!-- METADATA(mi-1) -->
- **Triage:** 🔧 Will Fix (assignee: py) — 妥当
- **Estimate:** 🚧 Alternative — Cost: S, Future: S, Signals: d — FIXME insertion: 後で直す — Plan: (1) src/b.py:2 — FIXME を追加
<!-- /METADATA(mi-1) -->

---

### mi-2 — `src/b.py:3`

**指摘:**

価値が低い。

<!-- METADATA(mi-2) -->
- **Triage:** 🔧 Will Fix (assignee: py) — 妥当
- **Estimate:** 🔻 Downgrade — Cost: S, Future: S, Signals: none — 不要
<!-- /METADATA(mi-2) -->

---

## Info

### I-1 — `PR`

**指摘:**

参考情報。

<!-- METADATA(I-1) -->
<!-- /METADATA(I-1) -->

---

## Summary

- **Critical:** 1
"""

PATCH_A = "@@ -8,3 +8,4 @@ def f():\n a\n+b\n c\n d\n@@ -20,2 +21,2 @@\n-x\n+y\n z"
FILES = [
    {"filename": "src/a.py", "status": "modified", "patch": PATCH_A},
    {"filename": "src/b.py", "status": "modified", "patch": "@@ -1,3 +1,3 @@\n p\n-q\n+r\n s"},
    {"filename": "big.bin", "status": "modified"},
]


def view(head=HEAD, author="author", viewer="me", mergeable="MERGEABLE", state="OPEN",
         head_ref="feature"):
    return {"data": {"viewer": {"login": viewer}, "repository": {"pullRequest": {
        "id": "PR_1", "number": 7, "state": state, "author": {"login": author},
        "title": "Title", "body": "Description",
        "headRefOid": head, "headRefName": head_ref, "baseRefOid": "c" * 40,
        "mergeable": mergeable,
        "headRepository": {"nameWithOwner": "acme/app"},
    }}}}


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def outside_code_spans(text):
    """What CommonMark's inline parser leaves of the text outside code spans."""
    kept, i = [], 0
    while i < len(text):
        if text[i] == "\\":
            kept.append(text[i:i + 2])
            i += 2
        elif text[i] != "`":
            kept.append(text[i])
            i += 1
        else:
            run = re.match(r"`+", text[i:]).group(0)
            rest = text[i + len(run):]
            closer = next((m for m in re.finditer(r"`+", rest) if m.group(0) == run), None)
            if not closer:
                kept.append(run)
            i += len(run) + (closer.end() if closer else 0)
    return "".join(kept)


class FakeGitHub:
    """Answers the gh and git commands of gh-review.py, recording every call."""

    def __init__(self, **view_args):
        self.view = view(**view_args)
        self.calls = []
        self.mutations = []
        self.posts = []
        self.reviews = []
        self.review_comments = []
        self.issue_comments = []
        self.objects = {}
        self.fail_threads = set()
        self.fail_submit = False
        self.submit_applies = False
        self.fail_state = False
        self.fail_delete = False
        self.review_state = "PENDING"
        self.git = {}
        self.remote_url = "https://github.com/acme/app.git"
        self.ssh_config = ""
        self.compare_status = {}
        self.mergeable = []

    def __call__(self, cmd, input=None, **_):
        self.calls.append(cmd)
        if cmd[0] == "git":
            return self.git_answer(cmd)
        if cmd[0] == "ssh":
            return self.ssh_config
        if cmd[:3] == ["gh", "api", "graphql"]:
            return self.graphql(json.loads(input))
        method = "GET"
        if "-X" in cmd:
            method = cmd[cmd.index("-X") + 1]
        path = next(a for a in cmd[2:] if a.startswith("repos/"))
        if method == "POST":
            self.posts.append((path, json.loads(input)))
            return json.dumps({"html_url": f"https://github.com/{path}#new"})
        return json.dumps(self.rest(path))

    def git_answer(self, cmd):
        key = cmd[1]
        default = ""
        if key == "remote":
            default = self.remote_url if "get-url" in cmd else "origin\n"
        answer = self.git.get(key, default)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def rest(self, path):
        if path in self.objects:
            return self.objects[path]
        if "/compare/" in path:
            status = self.compare_status.get(path.rsplit("/", 1)[1].split("...")[0], "ahead")
            if isinstance(status, Exception):
                raise status
            return {"status": status, "merge_base_commit": {"sha": BASE}}
        query = dict(re.findall(r"[?&](\w+)=([0-9]+)", path))
        page, size = int(query.get("page", 1)), int(query.get("per_page", mod.PAGE_SIZE))
        for tail, items in (("/files", FILES), ("/pulls/7/reviews", self.reviews),
                            ("/pulls/7/comments", self.review_comments),
                            ("/issues/7/comments", self.issue_comments)):
            if tail in path:
                return items[(page - 1) * size:page * size]
        raise mod.Error(f"unexpected path {path}")

    def graphql(self, body):
        query, variables = body["query"], body.get("variables", {})
        if "mutation" not in query:
            if "node(" not in query:
                if self.mergeable:
                    pull = self.view["data"]["repository"]["pullRequest"]
                    pull["mergeable"] = self.mergeable.pop(0)
                return json.dumps(self.view)
            if self.fail_state:
                raise mod.Error("state refused")
            return json.dumps({"data": {"node": {
                "state": self.review_state, "url": f"{URL}#pullrequestreview-1"}}})
        self.mutations.append((query, variables))
        input_ = variables["input"]
        if "addPullRequestReview(" in query:
            return json.dumps({"data": {"addPullRequestReview": {
                "pullRequestReview": {"id": "R_1"}}}})
        if "addPullRequestReviewThread" in query:
            key = (input_["path"], input_.get("subjectType"))
            if key in self.fail_threads:
                raise mod.Error("thread refused")
            return json.dumps({"data": {"addPullRequestReviewThread": {"thread": {"id": "T"}}}})
        if "submitPullRequestReview" in query:
            if self.fail_submit:
                if self.submit_applies:
                    self.review_state = "COMMENTED"
                raise mod.Error("submit refused")
            self.review_state = "COMMENTED"
            return json.dumps({"data": {"submitPullRequestReview": {
                "pullRequestReview": {"url": f"{URL}#pullrequestreview-1"}}}})
        if self.fail_delete or self.review_state != "PENDING":
            raise mod.Error("Can not delete a non-pending pull request review")
        return json.dumps({"data": {"deletePullRequestReview": {"clientMutationId": None}}})

    def named(self, name):
        return [v["input"] for q, v in self.mutations if name + "(" in q]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.doc = os.path.join(self.dir, "doc.md")
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write(DOCUMENT)
        self.real_run = mod.run
        self.addCleanup(lambda: setattr(mod, "run", self.real_run))

    def fake(self, **view_args):
        gh = FakeGitHub(**view_args)
        mod.run = gh
        return gh

    def draft(self, kind="review", lang="ja", prior_doc=None):
        result = mod.cmd_draft(URL, self.dir, self.doc, kind, lang, prior_doc)
        with open(os.path.join(self.dir, "draft.json"), encoding="utf-8") as f:
            draft = json.load(f)
        draft["comment_lang"] = lang
        for finding in draft["findings"]:
            finding["worded"] = True
            if finding["recommendation"]:
                finding["summary"] = " / ".join(finding["recommendation"])
        for entry in draft["prior"]:
            entry["worded"] = True
        self.save(draft)
        return result, draft

    def save(self, data, name="draft.json"):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return path

    def preview(self, path):
        result = mod.cmd_preview(URL, path)
        with open(result["preview_path"], encoding="utf-8") as f:
            return result, f.read()


class Parsing(Base):
    def test_rejects_other_urls(self):
        with self.assertRaises(mod.Error):
            mod.parse_pr_url("https://github.com/acme/app/issues/7")

    def test_normalizes_url(self):
        pr = mod.parse_pr_url("https://GitHub.com/acme/app/pull/7/files?w=1")
        self.assertEqual(pr.url, URL)
        self.assertEqual((pr.repo, pr.number), ("acme/app", 7))

    def test_diff_lines_are_new_side_context_and_additions(self):
        self.assertEqual(mod.diff_lines(PATCH_A), {8, 9, 10, 11, 21, 22})

    def test_document_findings(self):
        header, findings = mod.parse_document(self.doc)
        self.assertEqual(header["head_sha"], HEAD)
        self.assertEqual([f["id"] for f in findings], ["C-1", "M-1", "M-2", "mi-1", "mi-2", "I-1"])
        first = findings[0]
        self.assertEqual(first["severity"], "Critical")
        self.assertEqual(first["location"], "src/a.py:10")
        self.assertEqual(first["text"], "null を参照する。\n@alice に確認済み。")

    def write_document(self, *lines):
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write("\n".join([f"- **PR:** {URL} (head {HEAD}, base {BASE})", "", *lines, ""]))

    def test_malformed_heading_is_refused(self):
        for heading in ("### M-1 — `src/a`b.py:1`", "### M-1 — `src/a.py:1` [Bug] trailing"):
            self.write_document(heading, "", "<!-- METADATA(M-1) -->", "<!-- /METADATA(M-1) -->")
            with self.assertRaisesRegex(mod.Error, "heading.*M-1"):
                mod.parse_document(self.doc)

    def test_metadata_without_its_heading_is_refused(self):
        for lines in ((), ("### M-2 — `src/a.py:1`", "")):
            self.write_document(*lines, "<!-- METADATA(M-1) -->", "<!-- /METADATA(M-1) -->")
            with self.assertRaisesRegex(mod.Error, r"METADATA\(M-1\)"):
                mod.parse_document(self.doc)

    def test_recommendation_leaves_out_cost_signals_and_adr(self):
        _, findings = mod.parse_document(self.doc)
        by_id = {f["id"]: f for f in findings}
        self.assertEqual(mod.recommendation(by_id["C-1"]),
                         ["src/a.py:10 — null を確認", "src/a.py:12 — ログを追加"])
        self.assertEqual(mod.recommendation(by_id["M-1"]), ["別 PR を推奨"])
        self.assertEqual(mod.recommendation(by_id["mi-1"]), ["src/b.py:2 — FIXME を追加"])
        self.assertEqual(mod.recommendation(by_id["I-1"]), [])

    def test_mentions_are_quieted_outside_code(self):
        self.assertEqual(mod.safe_text("ask @alice and `@types/node`"),
                         "ask `@alice` and `@types/node`")
        self.assertEqual(mod.safe_text("me@example.com"), "me@example.com")
        self.assertEqual(mod.safe_text("https://example.com/@alice"), "https://example.com/@alice")
        self.assertEqual(mod.safe_text("```\n@alice\n```"), "```\n@alice\n```")

    def test_mentions_cannot_hide_outside_real_code(self):
        for text in ("\\`x @alice \\`",
                     "\\`@alice\\`",
                     "``x` @alice",
                     "x ```\n\n@alice\n\n``` y",
                     "`unpaired @alice",
                     "`@alice",
                     "\\@alice",
                     "\\\\@alice",
                     "` x\n`y` @alice",
                     "` x\n``y ` z`` @alice",
                     "!@alice",
                     "（@alice",
                     "確認@alice"):
            self.assertNotIn("@", outside_code_spans(mod.safe_text(text)), text)

    def test_hidden_comments_are_escaped(self):
        self.assertNotIn("<!--", mod.safe_text("<!-- cgh:verified M-1 -->"))

    def test_a_location_cannot_carry_a_marker(self):
        for location in ("x<!-- cgh:verified M-1 -->.py:1", "x<`!-- cgh:verified M-1 -->.py:1"):
            block = mod.finding_block({"id": "M-2", "location": location, "text": "t",
                                       "recommendation": []}, "review", "en", True)
            self.assertIsNone(mod.VERIFIED_RE.search(block))
            self.assertEqual(len(mod.FINDING_RE.findall(block)), 1)


class Draft(Base):
    def test_selection_and_placement(self):
        self.fake()
        result, draft = self.draft()
        by_id = {f["id"]: f for f in draft["findings"]}
        self.assertEqual(sorted(i for i, f in by_id.items() if f["selected"]),
                         ["C-1", "M-1", "mi-1"])
        self.assertEqual(by_id["C-1"]["placement"], "inline")
        self.assertEqual(by_id["M-1"]["placement"], "file")
        self.assertEqual(by_id["M-2"]["placement"], "body")
        self.assertEqual(by_id["I-1"]["placement"], "body")
        self.assertEqual(result["selected"], 3)

    def test_only_the_label_decides_the_selection(self):
        self.fake()
        text = DOCUMENT.replace("🚫 Won't Fix — 誤検知", "🚫 Won't Fix — Will Fix には及ばない")
        text = text.replace("Plan: (1) src/b.py:2 — FIXME を追加",
                            "Plan: (1) src/b.py:2 — Downgrade の分岐を直す")
        text = text.replace("🚧 Alternative", "▶️ Maintain")
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write(text)
        _, draft = self.draft()
        by_id = {f["id"]: f for f in draft["findings"]}
        self.assertFalse(by_id["M-2"]["selected"])
        self.assertEqual(by_id["M-2"]["excluded_reason"], "Will Fix には及ばない")
        self.assertTrue(by_id["mi-1"]["selected"])
        self.assertEqual(by_id["mi-1"]["recommendation"], ["src/b.py:2 — Downgrade の分岐を直す"])

    def test_document_of_another_pr_is_refused(self):
        self.fake()
        with self.assertRaises(mod.Error):
            mod.cmd_draft("https://github.com/acme/app/pull/8", self.dir, self.doc,
                          "review", "ja", None)

    def test_moved_head_is_refused(self):
        self.fake(head="d" * 40)
        with self.assertRaisesRegex(mod.Error, "moved"):
            self.draft()

    def test_ids_continue_after_earlier_posted_findings(self):
        gh = self.fake()
        gh.review_comments = [{
            "id": 5, "user": {"login": "me"}, "pull_request_review_id": 1,
            "path": "x", "line": 1, "in_reply_to_id": None,
            "body": mod.finding_block({"id": "C-3", "location": "x:1", "text": "t",
                                       "recommendation": []}, "review", "en", False),
        }]
        gh.reviews = [{"id": 1, "state": "COMMENTED", "user": {"login": "me"}, "body": ""}]
        _, draft = self.draft()
        by_doc = {f["doc_id"]: f["id"] for f in draft["findings"]}
        self.assertEqual(by_doc["C-1"], "C-4")
        self.assertEqual(by_doc["M-1"], "M-1")


class ReviewPosting(Base):
    def test_request_changes_with_major(self):
        gh = self.fake()
        self.draft()
        result = mod.cmd_post(URL, os.path.join(self.dir, "draft.json"), None)
        self.assertEqual(result["event"], "REQUEST_CHANGES")
        self.assertEqual(gh.named("submitPullRequestReview")[0]["event"], "REQUEST_CHANGES")
        add = gh.named("addPullRequestReview")[0]
        self.assertEqual(add["commitOID"], HEAD)
        threads = gh.named("addPullRequestReviewThread")
        line = next(t for t in threads if t["path"] == "src/a.py" and t["subjectType"] == "LINE")
        self.assertEqual((line["line"], line["side"]), (10, "RIGHT"))
        self.assertIn("**Critical C-1**", line["body"])
        self.assertIn("null を確認", line["body"])
        self.assertNotIn("Cost", line["body"])
        self.assertNotIn("レビュアー", line["body"])
        self.assertNotIn("x-adr", line["body"])
        self.assertIn("`@alice`", line["body"])
        file_level = next(t for t in threads if t["subjectType"] == "FILE")
        self.assertEqual(file_level["path"], "src/a.py")
        self.assertNotIn("line", file_level)
        self.assertIn("`src/a.py:99`", file_level["body"])

    def test_comment_without_critical_or_major(self):
        gh = self.fake()
        _, draft = self.draft()
        for f in draft["findings"]:
            f["selected"] = f["id"] == "mi-1"
        result = mod.cmd_post(URL, self.save(draft), None)
        self.assertEqual(result["event"], "COMMENT")
        self.assertEqual(gh.named("submitPullRequestReview")[0]["event"], "COMMENT")

    def test_never_approves(self):
        self.assertNotIn("APPROVE", read_text(SPEC.origin))

    def test_info_goes_out_only_when_selected(self):
        gh = self.fake()
        _, draft = self.draft()
        for f in draft["findings"]:
            f["selected"] = f["id"] == "I-1"
        result = mod.cmd_post(URL, self.save(draft), None)
        self.assertEqual(result["event"], "COMMENT")
        self.assertIn("**Info I-1**", gh.named("submitPullRequestReview")[0]["body"])

    def test_out_of_diff_goes_to_the_review_body(self):
        gh = self.fake()
        _, draft = self.draft()
        for f in draft["findings"]:
            f["selected"] = f["id"] == "M-2"
        mod.cmd_post(URL, self.save(draft), None)
        body = gh.named("submitPullRequestReview")[0]["body"]
        self.assertIn("**Major M-2** `docs/other.md:3`", body)
        self.assertEqual(gh.named("addPullRequestReviewThread"), [])

    def test_nothing_selected_is_refused(self):
        self.fake()
        _, draft = self.draft()
        for f in draft["findings"]:
            f["selected"] = False
        with self.assertRaises(mod.Error):
            mod.cmd_post(URL, self.save(draft), None)

    def test_moved_head_is_refused_at_post(self):
        gh = self.fake()
        self.draft()
        gh.view = view(head="d" * 40)
        with self.assertRaisesRegex(mod.Error, "moved"):
            mod.cmd_post(URL, os.path.join(self.dir, "draft.json"), None)
        self.assertEqual(gh.mutations, [])

    def test_own_pull_request_cannot_request_changes(self):
        gh = self.fake(author="me")
        self.draft()
        path = os.path.join(self.dir, "draft.json")
        result, text = self.preview(path)
        self.assertEqual(result["event"], "COMMENT")
        self.assertTrue(result["own_pr"])
        mod.cmd_post(URL, path, None)
        self.assertEqual(gh.named("submitPullRequestReview")[0]["event"], "COMMENT")

    def test_refused_line_falls_back_to_file_then_body(self):
        gh = self.fake()
        gh.fail_threads = {("src/a.py", "LINE")}
        self.draft()
        result = mod.cmd_post(URL, os.path.join(self.dir, "draft.json"), None)
        self.assertEqual(result["fallbacks"], ["C-1"])
        gh2 = self.fake()
        gh2.fail_threads = {("src/a.py", "LINE"), ("src/a.py", "FILE")}
        self.draft()
        mod.cmd_post(URL, os.path.join(self.dir, "draft.json"), None)
        self.assertIn("**Critical C-1**", gh2.named("submitPullRequestReview")[0]["body"])

    def test_failed_submit_deletes_the_pending_review(self):
        gh = self.fake()
        gh.fail_submit = True
        self.draft()
        with self.assertRaises(mod.Error):
            mod.cmd_post(URL, os.path.join(self.dir, "draft.json"), None)
        self.assertEqual(gh.named("deletePullRequestReview"), [{"pullRequestReviewId": "R_1"}])

    def test_a_second_post_is_refused(self):
        self.fake()
        self.draft()
        path = os.path.join(self.dir, "draft.json")
        mod.cmd_post(URL, path, None)
        with self.assertRaisesRegex(mod.Error, "already"):
            mod.cmd_post(URL, path, None)


def prior_doc_text(entries):
    lines = [f"- **PR:** {URL} (head {HEAD}, base {BASE})", "## Major", ""]
    for fid, verification in entries:
        lines += [f"### {fid} — `src/a.py:10`", "", "**Finding:**", "", "text", "",
                  f"<!-- METADATA({fid}) -->"]
        if verification:
            lines.append(f"- **Verification:** {verification}")
        lines += [f"<!-- /METADATA({fid}) -->", "", "---", ""]
    return "\n".join(lines)


class Gate(Base):
    def gate_draft(self, entries=None, selected=(), **view_args):
        gh = self.fake(**view_args)
        prior = None
        if entries is not None:
            prior = os.path.join(self.dir, "prior.md")
            with open(prior, "w", encoding="utf-8") as f:
                f.write(prior_doc_text(entries))
        _, draft = self.draft("gate", "en", prior)
        for f in draft["findings"]:
            f["selected"] = f["doc_id"] in selected
        return gh, self.save(draft)

    def test_document_without_findings_passes(self):
        gh = self.fake()
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write(f"# Report\n\n- **PR:** {URL} (head {HEAD}, base {BASE})\n- **Trust:** off\n")
        result, _ = self.draft("gate", "en")
        self.assertEqual(result["total"], 0)
        post = mod.cmd_post(URL, os.path.join(self.dir, "draft.json"), None)
        self.assertEqual((post["verdict"], post["event"]), ("PASS", "COMMENT"))
        self.assertIn("PASS", gh.named("submitPullRequestReview")[0]["body"])

    def test_block_on_major(self):
        gh, path = self.gate_draft(selected=("M-1",))
        result = mod.cmd_post(URL, path, None)
        self.assertEqual((result["verdict"], result["event"]), ("BLOCK", "REQUEST_CHANGES"))
        self.assertIn("BLOCK", gh.named("submitPullRequestReview")[0]["body"])

    def test_pass_posts_a_comment_without_findings(self):
        gh, path = self.gate_draft()
        result = mod.cmd_post(URL, path, None)
        self.assertEqual((result["verdict"], result["event"]), ("PASS", "COMMENT"))
        self.assertIn("PASS", gh.named("submitPullRequestReview")[0]["body"])

    def test_minor_does_not_block(self):
        _, path = self.gate_draft(selected=("mi-1",))
        self.assertEqual(mod.cmd_post(URL, path, None)["verdict"], "PASS")

    def test_conflict_blocks(self):
        _, path = self.gate_draft(mergeable="CONFLICTING")
        self.assertEqual(mod.cmd_post(URL, path, None)["verdict"], "BLOCK")

    def no_wait(self):
        waits = []
        self.addCleanup(setattr, mod.time, "sleep", mod.time.sleep)
        mod.time.sleep = waits.append
        return waits

    def test_unknown_mergeable_never_settling_stops_the_post(self):
        waits = self.no_wait()
        gh, path = self.gate_draft(mergeable="UNKNOWN")
        with self.assertRaisesRegex(mod.Error, "merges"):
            mod.cmd_post(URL, path, None)
        self.assertEqual(gh.mutations, [])
        self.assertEqual(waits, [mod.MERGEABLE_WAIT] * (mod.MERGEABLE_TRIES - 1))

    def test_unknown_mergeable_settling_as_conflict_blocks(self):
        self.no_wait()
        gh, path = self.gate_draft()
        gh.mergeable = ["UNKNOWN", "UNKNOWN", "CONFLICTING"]
        self.assertEqual(mod.cmd_post(URL, path, None)["verdict"], "BLOCK")

    def test_a_verdict_changed_since_the_preview_stops_the_post(self):
        gh, path = self.gate_draft()
        result, _ = self.preview(path)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(json.loads(read_text(path))["previewed_verdict"], "PASS")
        gh.view = view(mergeable="CONFLICTING")
        with self.assertRaisesRegex(mod.Error, "preview"):
            mod.cmd_post(URL, path, None)
        self.assertEqual(gh.mutations, [])
        self.assertEqual(self.preview(path)[0]["verdict"], "BLOCK")
        self.assertEqual(mod.cmd_post(URL, path, None)["verdict"], "BLOCK")

    def test_a_review_does_not_wait_for_mergeable(self):
        waits = self.no_wait()
        self.fake(mergeable="UNKNOWN")
        self.draft()
        path = os.path.join(self.dir, "draft.json")
        self.preview(path)
        self.assertEqual(mod.cmd_post(URL, path, None)["event"], "REQUEST_CHANGES")
        self.assertEqual(waits, [])

    def test_feedback_that_mentions_verified_stays_open(self):
        gh, path = self.gate_draft([("M-7", "💬 Feedback — Verified とあるが未修正")])
        self.assertEqual(mod.cmd_post(URL, path, None)["verdict"], "BLOCK")
        self.assertNotIn("cgh:verified", gh.named("submitPullRequestReview")[0]["body"])

    def test_prior_document_of_another_head_is_refused(self):
        self.fake()
        prior = os.path.join(self.dir, "prior.md")
        with open(prior, "w", encoding="utf-8") as f:
            f.write(prior_doc_text([("M-7", "✅ Verified — fixed")]).replace(HEAD, "d" * 40))
        with self.assertRaisesRegex(mod.Error, "/cgh:gate again"):
            self.draft("gate", "en", prior)

    def test_prior_document_of_another_pr_is_refused(self):
        self.fake()
        prior = os.path.join(self.dir, "prior.md")
        with open(prior, "w", encoding="utf-8") as f:
            f.write(prior_doc_text([("M-7", "✅ Verified — fixed")]).replace("/pull/7", "/pull/8"))
        with self.assertRaisesRegex(mod.Error, "not a review document"):
            self.draft("gate", "en", prior)

    def test_open_prior_major_blocks_and_verified_is_recorded(self):
        gh, path = self.gate_draft([("M-7", "💬 Feedback — still broken"),
                                    ("M-8", "✅ Verified — fixed")])
        result = mod.cmd_post(URL, path, None)
        self.assertEqual(result["verdict"], "BLOCK")
        body = gh.named("submitPullRequestReview")[0]["body"]
        self.assertIn("still broken", body)
        self.assertRegex(body, r"<!-- cgh:verified M-8 -->")

    def test_prior_without_verification_stays_open(self):
        _, path = self.gate_draft([("M-7", None)])
        self.assertEqual(mod.cmd_post(URL, path, None)["verdict"], "BLOCK")

    def test_waived_prior_passes(self):
        gh, path = self.gate_draft([("M-7", "💬 Feedback — still broken")])
        with open(path, encoding="utf-8") as f:
            draft = json.load(f)
        draft["prior"][0]["state"] = "waived"
        result = mod.cmd_post(URL, self.save(draft), None)
        self.assertEqual(result["verdict"], "PASS")
        body = gh.named("submitPullRequestReview")[0]["body"]
        self.assertRegex(body, r"<!-- cgh:waived M-7 -->")
        self.assertNotIn("cgh:verified", body)


class PriorBase(Base):
    def posted(self, gh, fid="M-1", kind="review", reviewer="me", review_id=1, comment_id=5):
        block = mod.finding_block({
            "id": fid, "location": "src/a.py:10", "text": "text @bob",
            "recommendation": ["src/a.py:10 — fix it"]}, kind, "en", False)
        gh.reviews.append({"id": review_id, "state": "COMMENTED", "user": {"login": reviewer},
                           "body": ""})
        gh.review_comments.append({
            "id": comment_id, "user": {"login": reviewer}, "pull_request_review_id": review_id,
            "path": "src/a.py", "line": 10, "in_reply_to_id": None, "body": block})

    def prior(self, kind="review"):
        doc = os.path.join(self.dir, "prior.md")
        result = mod.cmd_prior(URL, self.dir, kind, doc)
        with open(os.path.join(self.dir, "prior.json"), encoding="utf-8") as f:
            return result, json.load(f), doc

    def local(self, gh, at="head"):
        gh.git = {"rev-parse": HEAD + "\n" if at == "head" else "e" * 40 + "\n",
                  "status": "", "merge-base": "", "branch": "feature\n"}
        if at == "elsewhere":
            gh.git["merge-base"] = mod.Error("not an ancestor")


class Prior(PriorBase):
    def test_recovers_finding_and_writes_a_document_creview_can_read(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        result, prior, doc = self.prior()
        self.assertEqual(result["open"], ["M-1"])
        self.assertEqual(prior["findings"][0]["target"], {"kind": "thread", "id": 5})
        _, findings = mod.parse_document(doc)
        self.assertEqual(findings[0]["id"], "M-1")
        self.assertIn("fix it", findings[0]["text"])
        text = read_text(doc)
        self.assertIn(f"- **PR:** {URL} (head {HEAD}, base {BASE})\n", text)
        self.assertIn("- **Branch:** feature\n", text)
        self.assertIn("- **Trust:** on\n", text)
        self.assertIn("- **Source:** pr-comments\n", text)

    def test_trust_records_on_away_from_the_head(self):
        gh = self.fake()
        self.local(gh, "elsewhere")
        self.posted(gh)
        doc = os.path.join(self.dir, "prior.md")
        mod.cmd_prior(URL, self.dir, "review", doc, True)
        text = read_text(doc)
        self.assertIn("- **Trust:** on\n", text)
        self.assertNotIn("**Branch:**", text)
        header = load_script("gh_pr", ("creview", "scripts", "gh-pr.py")).parse_header(doc)
        self.assertEqual(header["trust"], "on")

    def test_elsewhere_has_no_branch_and_no_trust(self):
        gh = self.fake()
        self.local(gh, "elsewhere")
        self.posted(gh)
        _, _, doc = self.prior()
        text = read_text(doc)
        self.assertNotIn("**Branch:**", text)
        self.assertIn("- **Trust:** off\n", text)

    def test_another_authors_marker_is_ignored(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh, reviewer="mallory")
        result, _, _ = self.prior()
        self.assertEqual(result["open"], [])

    def test_another_authors_verified_marker_is_ignored(self):
        mallory = {"login": "mallory"}
        for marker in ("<!-- cgh:verified M-1 -->", "<!-- cgh:waived M-1 -->"):
            for add in (lambda gh: gh.reviews.append(
                            {"id": 2, "state": "COMMENTED", "user": mallory, "body": marker}),
                        lambda gh: gh.review_comments.append(
                            {"id": 6, "user": mallory, "pull_request_review_id": 1,
                             "in_reply_to_id": 5, "body": marker}),
                        lambda gh: gh.issue_comments.append(
                            {"id": 6, "user": mallory, "body": marker})):
                gh = self.fake()
                self.local(gh)
                self.posted(gh)
                add(gh)
                self.assertEqual(self.prior()[0]["open"], ["M-1"])

    def test_own_verified_markers_outside_a_thread_close_a_finding(self):
        marker = "<!-- cgh:verified M-1 -->"
        me = {"login": "me"}
        for add in (lambda gh: gh.reviews.append(
                        {"id": 2, "state": "COMMENTED", "user": me, "body": marker}),
                    lambda gh: gh.issue_comments.append({"id": 6, "user": me, "body": marker})):
            gh = self.fake()
            self.local(gh)
            self.posted(gh)
            add(gh)
            result, _, _ = self.prior()
            self.assertEqual((result["open"], result["verified"]), ([], ["M-1"]))

    def test_kind_filter(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh, kind="gate")
        self.assertEqual(self.prior("review")[0]["open"], [])
        self.assertEqual(self.prior("gate")[0]["open"], ["M-1"])

    def test_verified_marker_closes_a_finding(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        self.verified_reply(gh)
        result, _, _ = self.prior()
        self.assertEqual((result["open"], result["verified"]), ([], ["M-1"]))

    def verified_reply(self, gh):
        gh.reviews.append({"id": 2, "state": "COMMENTED", "user": {"login": "me"}, "body": ""})
        gh.review_comments.append({
            "id": 6, "user": {"login": "me"}, "pull_request_review_id": 2, "path": "src/a.py",
            "line": 10, "in_reply_to_id": 5, "body": "ok\n<!-- cgh:verified M-1 -->"})

    def test_dismissed_review_is_ignored(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        gh.reviews[0]["state"] = "DISMISSED"
        self.assertEqual(self.prior()[0]["open"], [])

    def test_a_new_finding_does_not_reuse_a_dismissed_verified_id(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        gh.reviews[0]["state"] = "DISMISSED"
        self.verified_reply(gh)
        _, draft = self.draft()
        new_id = {f["doc_id"]: f["id"] for f in draft["findings"]}["M-1"]
        self.assertEqual(new_id, "M-2")
        self.posted(gh, fid=new_id, review_id=3, comment_id=7)
        self.assertEqual(self.prior()[0]["open"], ["M-2"])

    def test_a_dismissed_finding_still_advances_the_numbers(self):
        gh = self.fake()
        self.posted(gh)
        gh.reviews[0]["state"] = "DISMISSED"
        _, draft = self.draft()
        self.assertEqual({f["doc_id"]: f["id"] for f in draft["findings"]}["M-1"], "M-2")

    def test_a_marker_with_something_other_than_ids_is_ignored(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        gh.issue_comments.append({"id": 6, "user": {"login": "me"},
                                  "body": "<!-- cgh:verified M-1,abc -->"})
        self.assertEqual(self.prior()[0]["open"], ["M-1"])
        _, draft = self.draft()
        self.assertEqual({f["doc_id"]: f["id"] for f in draft["findings"]}["M-1"], "M-2")

    def test_a_waived_finding_leaves_open_and_reaches_the_waived_document(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        self.posted(gh, fid="M-2", review_id=2, comment_id=6)
        gh.reviews.append({"id": 3, "state": "COMMENTED", "user": {"login": "me"},
                           "body": "<!-- cgh:waived M-1 -->"})
        result, prior, _ = self.prior()
        self.assertEqual((result["open"], result["waived"]), (["M-2"], ["M-1"]))
        self.assertEqual([f["id"] for f in prior["findings"]], ["M-2"])
        self.assertEqual(result["waived_document"], os.path.join(self.dir, "waived.md"))
        text = read_text(result["waived_document"])
        self.assertIn("M-1", text)
        self.assertIn("src/a.py:10", text)
        self.assertIn("text `@bob`", text)
        self.assertNotIn("M-2", text)
        _, draft = self.draft()
        self.assertEqual({f["doc_id"]: f["id"] for f in draft["findings"]}["M-1"], "M-3")

    def test_no_waived_finding_writes_no_waived_document(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        result, _, _ = self.prior()
        self.assertEqual(result["waived"], [])
        self.assertIsNone(result["waived_document"])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "waived.md")))

    def test_finding_in_a_review_body(self):
        gh = self.fake()
        self.local(gh)
        block = mod.finding_block({"id": "M-2", "location": "PR", "text": "t",
                                   "recommendation": []}, "review", "en", True)
        gh.reviews.append({"id": 9, "state": "CHANGES_REQUESTED", "user": {"login": "me"},
                           "body": f"summary\n\n{block}\n"})
        _, prior, _ = self.prior()
        self.assertEqual(prior["findings"][0]["target"], {"kind": "review", "id": 9})
        self.assertEqual(prior["findings"][0]["location"], "PR")

    def test_local_commits_stop_verification(self):
        gh = self.fake()
        self.local(gh, "ahead")
        self.posted(gh)
        with self.assertRaisesRegex(mod.Error, "push"):
            self.prior()
        self.assertIn(["git", "merge-base", "--is-ancestor", HEAD, "HEAD"], gh.calls)

    def test_uncommitted_changes_stop_verification(self):
        gh = self.fake()
        self.local(gh)
        gh.git["status"] = " M src/a.py\n"
        self.posted(gh)
        with self.assertRaisesRegex(mod.Error, "uncommitted"):
            self.prior()
        status = next(c for c in gh.calls if c[:2] == ["git", "status"])
        for argument in ("--untracked-files=no", ":(top,exclude).claude/tmp",
                         ":(top,exclude).claude/worktrees"):
            self.assertIn(argument, status)

    def test_no_open_finding_writes_no_document(self):
        gh = self.fake()
        self.local(gh, "ahead")
        result, _, doc = self.prior()
        self.assertEqual(result["open"], [])
        self.assertIsNone(result["document"])
        self.assertFalse(os.path.exists(doc))

    def test_detached_head_has_no_branch_bullet(self):
        gh = self.fake()
        self.local(gh)
        gh.git["branch"] = "\n"
        self.posted(gh)
        _, _, doc = self.prior()
        self.assertNotIn("**Branch:**", read_text(doc))

    def test_markers_past_the_first_page_are_read(self):
        self.addCleanup(setattr, mod, "PAGE_SIZE", mod.PAGE_SIZE)
        mod.PAGE_SIZE = 2
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        gh.issue_comments = [{"id": i, "user": {"login": "me"}, "body": "x"} for i in (6, 7)]
        gh.issue_comments.append({"id": 8, "user": {"login": "me"},
                                  "body": "<!-- cgh:verified M-1 -->"})
        result, _, _ = self.prior()
        self.assertEqual((result["open"], result["verified"]), ([], ["M-1"]))

    def test_info_is_not_verified(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh, fid="I-1")
        result, prior, doc = self.prior()
        self.assertEqual((result["open"], prior["findings"]), ([], []))
        self.assertIsNone(result["document"])
        self.assertFalse(os.path.exists(doc))
        self.posted(gh, fid="M-1", review_id=2, comment_id=6)
        result, prior, doc = self.prior()
        self.assertEqual(result["open"], ["M-1"])
        self.assertEqual([f["id"] for f in prior["findings"]], ["M-1"])
        self.assertNotIn("I-1", read_text(doc))


class ResolveReplies(Base):
    def setup_doc(self):
        text = prior_doc_text([
            ("M-1", "✅ Verified — [as-recommended] null check added"),
            ("M-2", "✅ Verified — [differs] guard moved to the caller"),
            ("M-3", "💬 Feedback — the else branch is unchanged"),
            ("M-4", None),
            ("M-5", "✅ Verified — [as-recommended] done"),
            ("M-6", "💬 Feedback — the review body is unchanged"),
        ])
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write(text)
        prior = {"findings": [
            {"id": "M-1", "target": {"kind": "thread", "id": 1}},
            {"id": "M-2", "target": {"kind": "thread", "id": 2}},
            {"id": "M-3", "target": {"kind": "thread", "id": 3}},
            {"id": "M-4", "target": {"kind": "thread", "id": 4}},
            {"id": "M-5", "target": {"kind": "review", "id": 9}},
            {"id": "M-6", "target": {"kind": "review", "id": 9}},
        ]}
        self.save(prior, "prior.json")

    def replies(self):
        result = mod.cmd_replies(URL, self.dir, self.doc, "en")
        with open(os.path.join(self.dir, "replies.json"), encoding="utf-8") as f:
            return result, json.load(f)["replies"]

    def test_detail_only_when_the_fix_differs(self):
        self.fake()
        self.setup_doc()
        result, replies = self.replies()
        by_target = {r["target_id"]: r for r in replies if r["kind"] == "thread"}
        short = HEAD[:mod.SHORT_SHA]
        self.assertIn(short, by_target[1]["body"])
        self.assertNotIn("null check added", by_target[1]["body"])
        self.assertIn("guard moved", by_target[2]["body"])
        self.assertNotIn("[differs]", by_target[2]["body"])
        self.assertIn("else branch", by_target[3]["body"])
        self.assertNotIn(4, by_target)
        self.assertEqual(result["unverified"], ["M-4"])
        self.assertEqual(by_target[1]["verified"], ["M-1"])
        self.assertEqual(by_target[3]["verified"], [])

    def test_review_body_findings_share_one_issue_comment(self):
        self.fake()
        self.setup_doc()
        _, replies = self.replies()
        issue = [r for r in replies if r["kind"] == "issue"]
        self.assertEqual(len(issue), 1)
        self.assertEqual(issue[0]["finding_ids"], ["M-5", "M-6"])
        self.assertEqual(issue[0]["verified"], ["M-5"])
        self.assertIn("**Major M-5**", issue[0]["body"])
        self.assertIn("the review body is unchanged", issue[0]["body"])

    def test_feedback_that_mentions_verified_gets_no_confirmation(self):
        self.fake()
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write(prior_doc_text([("M-1", "💬 Feedback — Verified とあるが未修正")]))
        self.save({"findings": [{"id": "M-1", "target": {"kind": "thread", "id": 1}}]},
                  "prior.json")
        _, replies = self.replies()
        self.assertEqual(replies[0]["verified"], [])
        self.assertNotIn("✅", replies[0]["body"])

    def test_post_appends_verified_marker_and_quiets_body(self):
        gh = self.fake()
        self.setup_doc()
        self.replies()
        gh.objects = {f"repos/acme/app/pulls/comments/{i}": {
            "id": i, "in_reply_to_id": None,
            "pull_request_url": "https://api.github.com/repos/acme/app/pulls/7",
            "user": {"login": "me"}} for i in (1, 2, 3)}
        mod.cmd_post(URL, os.path.join(self.dir, "replies.json"), None)
        first = next(b for p, b in gh.posts if p.endswith("/comments/1/replies"))
        self.assertIn("<!-- cgh:verified M-1 -->", first["body"])
        issue = next(b for p, b in gh.posts if p.endswith("/issues/7/comments"))
        self.assertIn("<!-- cgh:verified M-5 -->", issue["body"])


class Replies(Base):
    def replies_file(self, entries):
        return self.save({"replies": entries}, "replies.json")

    def test_reply_targets_the_thread_root(self):
        gh = self.fake()
        gh.objects = {"repos/acme/app/pulls/comments/11": {
            "id": 11, "in_reply_to_id": 10,
            "pull_request_url": "https://api.github.com/repos/acme/app/pulls/7",
            "user": {"login": "rev"}}}
        path = self.replies_file([{"kind": "thread", "target_id": 11, "finding_ids": ["M-1"],
                                   "body": "fixed in abc1234"}])
        mod.cmd_post(URL, path, None)
        self.assertEqual(gh.posts[0][0], "repos/acme/app/pulls/7/comments/10/replies")

    def test_comment_of_another_pr_is_refused(self):
        gh = self.fake()
        gh.objects = {"repos/acme/app/pulls/comments/11": {
            "id": 11, "in_reply_to_id": None,
            "pull_request_url": "https://api.github.com/repos/acme/app/pulls/8",
            "user": {"login": "rev"}}}
        path = self.replies_file([{"kind": "thread", "target_id": 11, "finding_ids": [],
                                   "body": "x"}])
        with self.assertRaises(mod.Error):
            mod.cmd_post(URL, path, None)
        self.assertEqual(gh.posts, [])

    def test_urls_compare_ignoring_case(self):
        pr = mod.parse_pr_url("https://github.com/ACME/App/pull/7")
        self.assertTrue(mod.belongs(pr, "https://api.github.com/repos/acme/app/pulls/7", "pulls"))
        self.assertFalse(mod.belongs(pr, "https://api.github.com/repos/acme/app/pulls/8", "pulls"))
        self.assertEqual(mod.checked_document(pr, self.doc)[0]["url"], URL)
        other = mod.parse_pr_url("https://github.com/ACME/App/pull/8")
        with self.assertRaises(mod.Error):
            mod.checked_document(other, self.doc)

    def test_review_body_reply_mentions_the_reviewer(self):
        gh = self.fake()
        gh.objects = {"repos/acme/app/pulls/7/reviews/4": {
            "id": 4, "user": {"login": "coderabbitai[bot]"}}}
        path = self.replies_file([{"kind": "review", "target_id": 4, "finding_ids": ["M-1"],
                                   "body": "fixed, thanks @other"}])
        mod.cmd_post(URL, path, None)
        self.assertEqual(gh.posts[0][0], "repos/acme/app/issues/7/comments")
        body = gh.posts[0][1]["body"]
        self.assertTrue(body.startswith("@coderabbitai "))
        self.assertIn("`@other`", body)

    def test_issue_comment_reply_checks_its_pull_request(self):
        gh = self.fake()
        gh.objects = {"repos/acme/app/issues/comments/4": {
            "id": 4, "user": {"login": "rev"},
            "issue_url": "https://api.github.com/repos/acme/app/issues/8"}}
        path = self.replies_file([{"kind": "issue_comment", "target_id": 4, "finding_ids": [],
                                   "body": "x"}])
        with self.assertRaises(mod.Error):
            mod.cmd_post(URL, path, None)

    def test_deselected_and_posted_entries_are_skipped_on_a_rerun(self):
        gh = self.fake()
        gh.objects = {"repos/acme/app/pulls/comments/1": {
            "id": 1, "in_reply_to_id": None,
            "pull_request_url": "https://api.github.com/repos/acme/app/pulls/7",
            "user": {"login": "rev"}}}
        path = self.replies_file([
            {"kind": "thread", "target_id": 1, "finding_ids": [], "body": "a"},
            {"kind": "thread", "target_id": 2, "finding_ids": [], "body": "b", "selected": False},
        ])
        self.assertEqual(mod.cmd_post(URL, path, None)["posted"], 1)
        self.assertEqual(mod.cmd_post(URL, path, None)["posted"], 0)
        self.assertEqual(len(gh.posts), 1)

    def test_a_rerun_after_a_failure_sends_only_the_rest(self):
        gh = self.fake()
        comment = {"in_reply_to_id": None, "user": {"login": "rev"},
                   "pull_request_url": "https://api.github.com/repos/acme/app/pulls/7"}
        gh.objects = {"repos/acme/app/pulls/comments/1": {"id": 1, **comment}}
        path = self.replies_file([
            {"kind": "thread", "target_id": 1, "finding_ids": [], "body": "a"},
            {"kind": "thread", "target_id": 2, "finding_ids": [], "body": "b"},
        ])
        with self.assertRaises(mod.Error):
            mod.cmd_post(URL, path, None)
        saved = json.loads(read_text(path))["replies"]
        self.assertEqual([e["posted"] for e in saved], [True, False])
        self.assertEqual(len(gh.posts), 1)
        gh.objects["repos/acme/app/pulls/comments/2"] = {"id": 2, **comment}
        self.assertEqual(mod.cmd_post(URL, path, None)["posted"], 1)
        self.assertEqual(len(gh.posts), 2)

    def test_malformed_entry_is_refused(self):
        self.fake()
        thread = {"kind": "thread", "target_id": 1, "body": "a"}
        for entry in ({"kind": "thread", "target_id": "x", "body": "a"},
                      {"kind": "other", "target_id": 1, "body": "a"},
                      {"kind": "thread", "target_id": 1, "body": ""},
                      {**thread, "finding_ids": ["M-1"], "verified": "M-1"},
                      {**thread, "finding_ids": ["M-1"], "verified": ["M-2"]},
                      {**thread, "finding_ids": "M-1"},
                      {**thread, "finding_ids": ["M-1 --><img src=x>"],
                       "verified": ["M-1 --><img src=x>"]}):
            with self.assertRaises(mod.Error):
                mod.cmd_preview(URL, self.replies_file([entry]))

    def test_preview_shows_what_a_reply_marks_verified(self):
        self.fake()
        path = self.replies_file([{"kind": "thread", "target_id": 1, "finding_ids": ["M-1", "M-2"],
                                   "verified": ["M-1"], "body": "a"},
                                  {"kind": "thread", "target_id": 2, "finding_ids": ["M-3"],
                                   "body": "b"}])
        _, preview = self.preview(path)
        self.assertEqual(re.findall(r"^Verified: .*$", preview, re.M), ["Verified: M-1"])

    def test_commits_path_refuses_what_a_drafter_cannot_send(self):
        gh = self.fake()
        commits = self.save({"commits": []}, "fix-commits.json")
        thread = {"kind": "thread", "target_id": 1, "finding_ids": ["M-1"], "body": "a"}
        for data in ({"findings": [], "replies": [thread]},
                     {"replies": [{**thread, "verified": ["M-1"]}]}):
            path = self.save(data, "replies.json")
            with self.assertRaisesRegex(mod.Error, "--commits"):
                mod.cmd_post(URL, path, commits)
        self.assertEqual((gh.posts, gh.mutations), ([], []))

    def test_unpushed_commits_stop_the_replies(self):
        gh = self.fake()
        tip = "f" * 40
        gh.compare_status = {tip: mod.Error("gh: Not Found (HTTP 404)")}
        commits = self.save({"commits": [{"sha": tip, "subject": "s", "files": ["a"]}]},
                            "fix-commits.json")
        path = self.replies_file([{"kind": "thread", "target_id": 1, "finding_ids": [],
                                   "body": "a"}])
        self.assertFalse(mod.cmd_pushed(URL, commits)["pushed"])
        with self.assertRaisesRegex(mod.Error, "push"):
            mod.cmd_post(URL, path, commits)
        self.assertEqual(gh.posts, [])

    def test_other_compare_failures_are_not_a_missing_push(self):
        gh = self.fake()
        tip = "f" * 40
        gh.compare_status = {tip: mod.Error("gh: Server Error (HTTP 500)")}
        commits = self.save({"commits": [{"sha": tip, "subject": "s", "files": ["a"]}]},
                            "fix-commits.json")
        path = self.replies_file([{"kind": "thread", "target_id": 1, "finding_ids": [],
                                   "body": "a"}])
        with self.assertRaisesRegex(mod.Error, "HTTP 500"):
            mod.cmd_pushed(URL, commits)
        with self.assertRaisesRegex(mod.Error, "HTTP 500"):
            mod.cmd_post(URL, path, commits)
        self.assertEqual(gh.posts, [])

    def test_a_merged_pull_request_still_takes_replies_but_no_review(self):
        gh = self.fake(state="MERGED")
        gh.objects = {"repos/acme/app/pulls/comments/1": {
            "id": 1, "in_reply_to_id": None,
            "pull_request_url": "https://api.github.com/repos/acme/app/pulls/7",
            "user": {"login": "rev"}}}
        commits = self.save({"commits": [{"sha": HEAD, "subject": "s", "files": []}]},
                            "fix-commits.json")
        self.assertTrue(mod.cmd_pushed(URL, commits)["pushed"])
        path = self.replies_file([{"kind": "thread", "target_id": 1, "finding_ids": [],
                                   "body": "a"}])
        self.assertEqual(mod.cmd_post(URL, path, commits)["posted"], 1)
        with self.assertRaisesRegex(mod.Error, "not open"):
            self.draft()
        gh.view = view()
        self.draft()
        gh.view = view(state="MERGED")
        with self.assertRaisesRegex(mod.Error, "not open"):
            mod.cmd_post(URL, os.path.join(self.dir, "draft.json"), None)
        self.assertEqual(gh.mutations, [])

    def test_pushed_when_the_head_contains_the_tip(self):
        gh = self.fake()
        tip = "f" * 40
        for status, expected in (("ahead", True), ("identical", True), ("behind", False),
                                 ("diverged", False)):
            gh.compare_status = {tip: status}
            commits = self.save({"commits": [{"sha": tip, "subject": "s", "files": []}]},
                                "fix-commits.json")
            self.assertEqual(mod.cmd_pushed(URL, commits)["pushed"], expected, status)

    def test_no_fix_commits_need_no_push(self):
        self.fake()
        commits = self.save({"commits": []}, "fix-commits.json")
        self.assertTrue(mod.cmd_pushed(URL, commits)["pushed"])


class Fixes(Base):
    def test_lists_commits_on_the_recorded_branch(self):
        gh = self.fake()
        text = DOCUMENT.replace("- **Trust:** off", "- **Branch:** creview-pr-7\n- **Trust:** off")
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write(text)
        tip = "f" * 40
        gh.git = {"log": f"{tip}\x00fix: add check\n\nsrc/a.py\nsrc/b.py\n"}
        result = mod.cmd_fixes(URL, self.dir, self.doc)
        self.assertEqual((result["branch"], result["head_ref"]), ("creview-pr-7", "feature"))
        self.assertEqual(result["tip"], tip)
        log = next(c for c in gh.calls if c[:2] == ["git", "log"])
        self.assertIn(f"{HEAD}..creview-pr-7", log)
        with open(os.path.join(self.dir, "fix-commits.json"), encoding="utf-8") as f:
            commits = json.load(f)["commits"]
        self.assertEqual(commits[0]["files"], ["src/a.py", "src/b.py"])

    def test_head_when_no_branch_bullet(self):
        gh = self.fake()
        gh.git = {"log": ""}
        result = mod.cmd_fixes(URL, self.dir, self.doc)
        self.assertIsNone(result["tip"])
        log = next(c for c in gh.calls if c[:2] == ["git", "log"])
        self.assertIn(f"{HEAD}..HEAD", log)

    def test_head_ref_with_shell_metacharacters_is_not_passed_on(self):
        for name in ("x;rm -rf ~", "$(touch /tmp/x)", "a`b`", "a b"):
            gh = self.fake(head_ref=name)
            gh.git = {"log": ""}
            self.assertIsNone(mod.cmd_fixes(URL, self.dir, self.doc)["head_ref"], name)


class Comments(Base):
    def test_writes_ids_for_the_drafter(self):
        gh = self.fake()
        gh.reviews = [{"id": 3, "state": "COMMENTED", "user": {"login": "r"}, "body": "b"},
                      {"id": 4, "state": "PENDING", "user": {"login": "r"}, "body": "hidden"},
                      {"id": 5, "state": "COMMENTED", "user": {"login": "r"}, "body": ""}]
        gh.review_comments = [{"id": 1, "user": {"login": "r"}, "pull_request_review_id": 3,
                               "path": "a", "line": 2, "in_reply_to_id": None, "body": "c"},
                              {"id": 2, "user": {"login": "r"}, "pull_request_review_id": 4,
                               "path": "a", "line": 2, "in_reply_to_id": None, "body": "p"}]
        gh.issue_comments = [{"id": 8, "user": {"login": "i"}, "body": "d"}]
        mod.cmd_comments(URL, self.dir)
        with open(os.path.join(self.dir, "comments.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual([c["id"] for c in data["review_comments"]], [1])
        self.assertEqual([r["id"] for r in data["reviews"]], [3])
        self.assertEqual(data["issue_comments"][0]["id"], 8)

    def test_answered_comes_only_from_the_viewers_markers(self):
        gh = self.fake()
        rev, me = {"login": "r"}, {"login": "me"}
        gh.reviews = [{"id": 3, "state": "COMMENTED", "user": rev, "body": "b"},
                      {"id": 4, "state": "COMMENTED", "user": rev, "body": "b"}]
        comment = {"user": rev, "pull_request_review_id": 3, "in_reply_to_id": None, "body": "c"}
        gh.review_comments = [
            {**comment, "id": 1},
            {**comment, "id": 2, "in_reply_to_id": 1},
            {**comment, "id": 5},
            {**comment, "id": 6, "user": me, "pull_request_review_id": 4, "in_reply_to_id": 1,
             "body": "ok\n\n<!-- cgh:reply thread 1 -->"},
            {**comment, "id": 7, "in_reply_to_id": 5, "body": "<!-- cgh:reply thread 5 -->"}]
        gh.issue_comments = [
            {"id": 8, "user": rev, "body": "d"},
            {"id": 9, "user": rev, "body": "d"},
            {"id": 10, "user": me, "body": "<!-- cgh:reply issue_comment 8 -->"},
            {"id": 11, "user": me, "body": "<!-- cgh:reply review 3 -->"}]
        mod.cmd_comments(URL, self.dir)
        data = json.loads(read_text(os.path.join(self.dir, "comments.json")))
        answered = {key: {e["id"]: e["answered"] for e in data[key]}
                    for key in ("review_comments", "reviews", "issue_comments")}
        self.assertEqual(answered["review_comments"],
                         {1: True, 2: True, 5: False, 6: True, 7: False})
        self.assertEqual(answered["reviews"], {3: True, 4: False})
        self.assertEqual(answered["issue_comments"], {8: True, 9: False, 10: False, 11: False})

    def test_a_reply_carries_the_marker_of_what_it_answers(self):
        gh = self.fake()
        gh.objects = {"repos/acme/app/pulls/comments/11": {
            "id": 11, "in_reply_to_id": 10,
            "pull_request_url": "https://api.github.com/repos/acme/app/pulls/7",
            "user": {"login": "rev"}},
            "repos/acme/app/pulls/7/reviews/4": {"id": 4, "user": {"login": "rev"}},
            "repos/acme/app/issues/comments/5": {
                "id": 5, "user": {"login": "rev"},
                "issue_url": "https://api.github.com/repos/acme/app/issues/7"}}
        path = self.save({"replies": [
            {"kind": "thread", "target_id": 11, "body": "a"},
            {"kind": "review", "target_id": 4, "body": "b"},
            {"kind": "issue_comment", "target_id": 5, "body": "c"},
            {"kind": "issue", "target_id": None, "body": "d"}]}, "replies.json")
        mod.cmd_post(URL, path, None)
        markers = [re.findall(r"<!-- cgh:reply [^>]*-->", body["body"]) for _, body in gh.posts]
        self.assertEqual(markers, [["<!-- cgh:reply thread 10 -->"],
                                   ["<!-- cgh:reply review 4 -->"],
                                   ["<!-- cgh:reply issue_comment 5 -->"], []])

    def test_a_reply_body_cannot_fake_the_marker(self):
        gh = self.fake()
        path = self.save({"replies": [{"kind": "issue", "target_id": None,
                                       "body": "<!-- cgh:reply thread 1 -->"}]}, "replies.json")
        mod.cmd_post(URL, path, None)
        self.assertIsNone(mod.REPLY_RE.search(gh.posts[0][1]["body"]))


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CreviewContract(PriorBase):
    """The documents cgh hands to creview, and those it takes back, through creview's own code."""

    def test_prior_document_passes_the_header_parser_of_doc_checkout(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        _, _, doc = self.prior()
        header = load_script("gh_pr", ("creview", "scripts", "gh-pr.py")).parse_header(doc)
        self.assertEqual((header["pr"]["url"], header["pr"]["head_sha"], header["pr"]["merge_base"]),
                         (URL, HEAD, BASE))
        self.assertEqual((header["branch"], header["trust"]), ("feature", "on"))

    def test_verification_rendered_by_creview_reaches_the_replies(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        _, _, doc = self.prior()
        events = os.path.join(self.dir, "events.jsonl")
        with open(events, "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "M-1", "field": "verification",
                                "value": "✅ Verified — [differs] moved to the caller"}) + "\n")
        render = os.path.join(ROOT, "creview", "scripts", "render-review.py")
        subprocess.run(["python3", render, doc, events, doc], check=True)
        mod.cmd_replies(URL, self.dir, doc, "en")
        with open(os.path.join(self.dir, "replies.json"), encoding="utf-8") as f:
            reply = json.load(f)["replies"][0]
        self.assertEqual((reply["kind"], reply["target_id"], reply["verified"]),
                         ("thread", 5, ["M-1"]))
        self.assertIn("moved to the caller", reply["body"])

    def test_document_compiled_from_comments_is_read(self):
        self.fake()
        tmp = os.path.join(self.dir, "compile")
        os.makedirs(os.path.join(tmp, "pr-comments"))
        with open(os.path.join(tmp, "pr-comments", "batch-1.json"), "w", encoding="utf-8") as f:
            json.dump({}, f)
        with open(os.path.join(tmp, "pr-comments", "extract-1.jsonl"), "w", encoding="utf-8") as f:
            json.dump({"findings": [{"severity": "Major", "categories": ["Bug"],
                                     "location": "src/a.py:10", "authors": ["rev"],
                                     "description": "壊れている"}]}, f)
        doc = os.path.join(self.dir, "compiled.md")
        subprocess.run(["python3", os.path.join(ROOT, "creview", "scripts", "compile-pr-comments.py"),
                        tmp, doc, "--pr-url", URL, "--head", HEAD, "--merge-base", BASE,
                        "--branch", "(none)", "--trust", "off", "--lang", "ja"], check=True,
                       capture_output=True)
        header, findings = mod.parse_document(doc)
        self.assertEqual(header["head_sha"], HEAD)
        self.assertEqual((findings[0]["id"], findings[0]["location"], findings[0]["text"]),
                         ("M-1", "src/a.py:10", "壊れている"))

    def test_finding_shape_of_the_aggregator_template(self):
        template = read_text(os.path.join(ROOT, "creview", "skills", "start", "templates",
                                          "review-doc.md"))
        path = os.path.join(self.dir, "skeleton.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(template.replace("{url}", URL).replace("{head_sha}", HEAD)
                    .replace("{merge_base}", BASE))
        header, findings = mod.parse_document(path)
        self.assertEqual(header["url"], URL)
        self.assertEqual([f["id"] for f in findings], ["C-1", "M-1", "mi-1"])
        self.assertEqual(findings[0]["location"], "file.cpp:42")
        self.assertEqual(findings[0]["text"], "{description of the issue}")


class PostFailure(Base):
    def posting(self, **attributes):
        gh = self.fake()
        gh.fail_submit = True
        for name, value in attributes.items():
            setattr(gh, name, value)
        self.draft()
        return gh, os.path.join(self.dir, "draft.json")

    def test_a_submit_that_went_through_counts_as_posted(self):
        gh, path = self.posting(submit_applies=True)
        result = mod.cmd_post(URL, path, None)
        self.assertEqual(result["review_url"], f"{URL}#pullrequestreview-1")
        self.assertEqual(result["recovered_from"], "submit refused")
        self.assertEqual(gh.named("deletePullRequestReview"), [])
        with self.assertRaisesRegex(mod.Error, "already"):
            mod.cmd_post(URL, path, None)

    def test_a_failed_delete_keeps_the_original_error(self):
        _, path = self.posting(fail_delete=True)
        with self.assertRaisesRegex(mod.Error, "submit refused.*could not be deleted"):
            mod.cmd_post(URL, path, None)

    def test_an_unknown_outcome_refuses_a_second_post(self):
        gh, path = self.posting(fail_state=True)
        with self.assertRaisesRegex(mod.Error, "submit refused.*unknown.*check"):
            mod.cmd_post(URL, path, None)
        self.assertEqual(gh.named("deletePullRequestReview"), [])
        with self.assertRaisesRegex(mod.Error, "already"):
            mod.cmd_post(URL, path, None)

    def test_an_unexpected_exception_deletes_the_pending_review(self):
        gh = self.fake()
        _, draft = self.draft()
        next(f for f in draft["findings"] if f["selected"])["text"] = None
        with self.assertRaises(AttributeError):
            mod.cmd_post(URL, self.save(draft), None)
        self.assertEqual(gh.named("deletePullRequestReview"), [{"pullRequestReviewId": "R_1"}])


class Wording(Base):
    def raw_draft(self):
        self.fake()
        result = mod.cmd_draft(URL, self.dir, self.doc, "review", "ja", None)
        return result, os.path.join(self.dir, "draft.json")

    def wording(self, data, n=1):
        return self.save(data, f"wording-{n}.json")

    def test_draft_gives_the_ids_and_the_description(self):
        result, _ = self.raw_draft()
        self.assertEqual(result["selected_ids"], ["C-1", "M-1", "mi-1"])
        self.assertEqual(result["prior_ids"], [])
        body = json.loads(read_text(result["pr_body_path"]))
        self.assertEqual(body, {"title": "Title", "body": "Description"})

    def test_merge_reports_what_is_missing_and_touches_nothing_else(self):
        _, path = self.raw_draft()
        self.wording({"comment_lang": "en", "findings": [
            {"id": "C-1", "summary": "要約", "post_text": "Null deref", "post_summary": "Guard it",
             "selected": False, "text": "changed"},
        ]})
        result = mod.cmd_wording(URL, path)
        self.assertEqual((result["comment_lang"], result["missing"]), ("en", ["M-1", "mi-1"]))
        finding = json.loads(read_text(path))["findings"][0]
        self.assertEqual((finding["summary"], finding["post_text"], finding["post_summary"]),
                         ("要約", "Null deref", "Guard it"))
        self.assertTrue(finding["selected"])
        self.assertIn("null を参照", finding["text"])

    def test_a_later_merge_keeps_what_the_user_reworded(self):
        _, path = self.raw_draft()
        self.wording({"comment_lang": "en", "findings": [
            {"id": "C-1", "summary": "s", "post_summary": "old"}]})
        mod.cmd_wording(URL, path)
        self.assertEqual(glob.glob(os.path.join(self.dir, "wording-*.json")), [])
        draft = json.loads(read_text(path))
        draft["findings"][0]["post_summary"] = "reworded"
        self.save(draft)
        self.wording({"comment_lang": "en", "findings": [{"id": "M-1", "summary": "s"}]}, 2)
        mod.cmd_wording(URL, path)
        finding = json.loads(read_text(path))["findings"][0]
        self.assertEqual(finding["post_summary"], "reworded")

    def test_a_finding_with_no_recommendation_needs_no_summary(self):
        _, path = self.raw_draft()
        draft = json.loads(read_text(path))
        for f in draft["findings"]:
            f["selected"] = f["id"] == "I-1"
        self.save(draft)
        self.wording({"comment_lang": "en", "findings": []})
        self.assertEqual(mod.cmd_wording(URL, path)["missing"], ["I-1"])
        self.wording({"comment_lang": "en", "findings": [{"id": "I-1", "post_text": "t"}]})
        self.assertEqual(mod.cmd_wording(URL, path)["missing"], [])

    def test_an_earlier_finding_with_a_note_needs_its_wording(self):
        self.fake()
        prior = os.path.join(self.dir, "prior.md")
        with open(prior, "w", encoding="utf-8") as f:
            f.write(prior_doc_text([("M-7", "💬 Feedback — まだ壊れている"), ("M-8", None)]))
        mod.cmd_draft(URL, self.dir, self.doc, "gate", "ja", prior)
        path = os.path.join(self.dir, "draft.json")
        draft = json.loads(read_text(path))
        self.wording({"comment_lang": "en", "findings": [
            {"id": f["id"]} for f in draft["findings"] if f["selected"]]})
        self.assertEqual(mod.cmd_wording(URL, path)["missing"], ["M-7"])

    def test_malformed_wording_is_refused(self):
        _, path = self.raw_draft()
        for data in ({"comment_lang": "not a language", "findings": []},
                     {"comment_lang": "en", "findings": [{"id": "X-9", "summary": "s"}]},
                     {"comment_lang": "en", "findings": [{"id": "C-1", "summary": 1}]},
                     {"comment_lang": "en", "findings": "C-1"}):
            self.wording(data)
            with self.assertRaises(mod.Error):
                mod.cmd_wording(URL, path)

    def test_two_comment_languages_are_refused(self):
        _, path = self.raw_draft()
        self.wording({"comment_lang": "en", "findings": []}, 1)
        self.wording({"comment_lang": "ja", "findings": []}, 2)
        with self.assertRaisesRegex(mod.Error, "language"):
            mod.cmd_wording(URL, path)

    def test_post_needs_the_wording(self):
        _, path = self.raw_draft()
        with self.assertRaisesRegex(mod.Error, "wording"):
            mod.cmd_post(URL, path, None)
        self.wording({"comment_lang": "en", "findings": [{"id": "C-1", "summary": "s"}]})
        mod.cmd_wording(URL, path)
        with self.assertRaisesRegex(mod.Error, "M-1"):
            mod.cmd_post(URL, path, None)

    def fully_worded(self, path, **extra):
        draft = json.loads(read_text(path))
        self.wording({"comment_lang": "en", "findings": [
            {"id": f["id"], "summary": f"要約 {f['id']}", "post_text": f"Text {f['id']}",
             "post_summary": f"Summary {f['id']}"}
            for f in draft["findings"] if f["selected"]]})
        mod.cmd_wording(URL, path)

    def test_preview_stays_in_the_users_language_and_post_uses_the_translation(self):
        _, path = self.raw_draft()
        self.fully_worded(path)
        result, preview = self.preview(path)
        self.assertEqual((result["comment_lang"], result["wording_missing"]), ("en", []))
        self.assertIn("null を参照", preview)
        self.assertIn("要約 C-1", preview)
        self.assertIn("**推奨**", preview)
        self.assertNotIn("null を確認", preview)
        self.assertNotIn("Summary C-1", preview)
        posted = read_text(result["post_preview_path"])
        self.assertIn("Text C-1", posted)
        self.assertIn("Summary C-1", posted)
        self.assertIn("**Recommendation**", posted)
        self.assertNotIn("null を参照", posted)
        gh = mod.run
        mod.cmd_post(URL, path, None)
        line = next(t for t in gh.named("addPullRequestReviewThread") if t["subjectType"] == "LINE")
        self.assertIn("**Critical C-1**", line["body"])
        self.assertIn("Text C-1", line["body"])
        self.assertIn("Summary C-1", line["body"])
        self.assertIn("**Recommendation**", line["body"])
        self.assertNotIn("null を参照", line["body"])
        self.assertIn("Findings:", gh.named("submitPullRequestReview")[0]["body"])

    def test_without_a_translation_the_post_uses_the_preview_wording(self):
        _, path = self.raw_draft()
        draft = json.loads(read_text(path))
        self.wording({"comment_lang": "ja", "findings": [
            {"id": f["id"], "summary": f"要約 {f['id']}"}
            for f in draft["findings"] if f["selected"]]})
        mod.cmd_wording(URL, path)
        gh = mod.run
        mod.cmd_post(URL, path, None)
        line = next(t for t in gh.named("addPullRequestReviewThread") if t["subjectType"] == "LINE")
        self.assertIn("null を参照", line["body"])
        self.assertIn("要約 C-1", line["body"])
        self.assertIn("**推奨**", line["body"])

    def test_a_translation_cannot_notify_anyone(self):
        _, path = self.raw_draft()
        draft = json.loads(read_text(path))
        self.wording({"comment_lang": "en", "findings": [
            {"id": f["id"], "summary": "s", "post_text": "ask @mallory",
             "post_summary": "<!-- cgh:verified C-1 -->"}
            for f in draft["findings"] if f["selected"]]})
        mod.cmd_wording(URL, path)
        gh = mod.run
        mod.cmd_post(URL, path, None)
        line = gh.named("addPullRequestReviewThread")[0]["body"]
        self.assertIn("`@mallory`", line)
        self.assertNotIn("cgh:verified", line.replace("&lt;!-- cgh:verified", ""))

    def test_earlier_gate_notes_are_posted_translated(self):
        gh = self.fake()
        prior = os.path.join(self.dir, "prior.md")
        with open(prior, "w", encoding="utf-8") as f:
            f.write(prior_doc_text([("M-7", "💬 Feedback — まだ壊れている")]))
        result = mod.cmd_draft(URL, self.dir, self.doc, "gate", "ja", prior)
        self.assertEqual(result["prior_ids"], ["M-7"])
        path = os.path.join(self.dir, "draft.json")
        draft = json.loads(read_text(path))
        self.wording({"comment_lang": "en", "findings": [
            {"id": "M-7", "post_note": "still broken"},
            *({"id": f["id"], "summary": "s"} for f in draft["findings"] if f["selected"])]})
        mod.cmd_wording(URL, path)
        _, preview = self.preview(path)
        self.assertIn("まだ壊れている", preview)
        mod.cmd_post(URL, path, None)
        body = gh.named("submitPullRequestReview")[0]["body"]
        self.assertIn("still broken", body)
        self.assertNotIn("まだ壊れている", body)
        self.assertIn("Merge gate: BLOCK", body)

    def test_replies_merge_by_index_and_post_the_translation(self):
        gh = self.fake()
        gh.objects = {"repos/acme/app/pulls/comments/1": {
            "id": 1, "in_reply_to_id": None,
            "pull_request_url": "https://api.github.com/repos/acme/app/pulls/7",
            "user": {"login": "rev"}}}
        path = self.save({"replies": [{"kind": "thread", "target_id": 1, "finding_ids": ["M-1"],
                                       "body": "修正しました"}]}, "replies.json")
        self.wording({"comment_lang": "en", "replies": [{"index": 0, "post_body": "Fixed"}]})
        self.assertEqual(mod.cmd_wording(URL, path)["comment_lang"], "en")
        result, preview = self.preview(path)
        self.assertIn("修正しました", preview)
        self.assertIn("Fixed", read_text(result["post_preview_path"]))
        mod.cmd_post(URL, path, None)
        self.assertEqual(gh.posts[0][1]["body"], "Fixed\n\n<!-- cgh:reply thread 1 -->")

    def test_a_drafted_translation_goes_out_without_a_wording_step(self):
        gh = self.fake()
        gh.objects = {"repos/acme/app/pulls/comments/1": {
            "id": 1, "in_reply_to_id": None,
            "pull_request_url": "https://api.github.com/repos/acme/app/pulls/7",
            "user": {"login": "rev"}}}
        path = self.save({"comment_lang": "en", "replies": [
            {"kind": "thread", "target_id": 1, "finding_ids": ["M-1"], "body": "修正しました",
             "post_body": "Fixed"}]}, "replies.json")
        mod.cmd_post(URL, path, None)
        self.assertEqual(gh.posts[0][1]["body"], "Fixed\n\n<!-- cgh:reply thread 1 -->")

    def test_reply_wording_out_of_range_is_refused(self):
        self.fake()
        path = self.save({"replies": [{"kind": "thread", "target_id": 1, "body": "a"}]},
                         "replies.json")
        self.wording({"comment_lang": "en", "replies": [{"index": 3, "post_body": "x"}]})
        with self.assertRaises(mod.Error):
            mod.cmd_wording(URL, path)

    def test_comments_and_replies_write_the_description(self):
        self.fake()
        mod.cmd_comments(URL, self.dir)
        self.assertIn("Description", read_text(os.path.join(self.dir, "pr-body.json")))


class Remote(Base):
    OTHER = "https://github.com/other/app/pull/7"

    def test_every_subcommand_refuses_a_pull_request_of_another_repository(self):
        path = self.save({"replies": []}, "replies.json")
        for call in (
            lambda u: mod.cmd_prior(u, self.dir, "review", os.path.join(self.dir, "p.md")),
            lambda u: mod.cmd_draft(u, self.dir, self.doc, "review", "ja", None),
            lambda u: mod.cmd_wording(u, path),
            lambda u: mod.cmd_comments(u, self.dir),
            lambda u: mod.cmd_fixes(u, self.dir, self.doc),
            lambda u: mod.cmd_pushed(u, path),
            lambda u: mod.cmd_replies(u, self.dir, self.doc, "en"),
            lambda u: mod.cmd_preview(u, path),
            lambda u: mod.cmd_post(u, path, None),
        ):
            gh = self.fake()
            with self.assertRaisesRegex(mod.Error, "not a remote of this repository"):
                call(self.OTHER)
            self.assertEqual([c for c in gh.calls if c[0] == "gh"], [])

    def accepted(self, remote, url=URL, ssh_config=""):
        gh = self.fake()
        gh.remote_url = remote
        gh.ssh_config = ssh_config
        try:
            mod.checked_pr(url)
        except mod.Error:
            return False
        return True

    def test_remote_forms(self):
        for remote, expected in (
            ("https://github.com/acme/app.git", True),
            ("https://github.com/ACME/App.git", True),
            ("git@github.com:acme/app.git", True),
            ("ssh://git@ssh.github.com:443/acme/app.git", True),
            ("https://github.com/acme/other.git", False),
            ("https://gitlab.com/acme/app.git", False),
            ("file:///srv/github.com/acme/app.git", False),
            ("/srv/acme/app.git", False),
        ):
            self.assertEqual(self.accepted(remote), expected, remote)

    def test_an_ssh_alias_resolves_to_its_host(self):
        config = "user git\nhostname github.com\n"
        self.assertTrue(self.accepted("git@work:acme/app.git", ssh_config=config))
        self.assertFalse(self.accepted("git@work:acme/app.git", ssh_config="hostname other.test\n"))

    def test_a_host_of_another_case_and_a_port_are_compared_by_name(self):
        self.assertTrue(self.accepted("https://github.com/acme/app.git",
                                      "https://GitHub.com/ACME/app/pull/7"))
        self.assertFalse(self.accepted("https://github.com/acme/app.git",
                                       "https://ghe.example.test:8443/acme/app/pull/7"))

    def test_no_remote_is_refused(self):
        gh = self.fake()
        gh.git["remote"] = mod.Error("not a git repository")
        with self.assertRaisesRegex(mod.Error, "not a remote"):
            mod.checked_pr(URL)


class ReplyTemplate(unittest.TestCase):
    def test_a_declined_finding_opens_with_the_fixed_phrase(self):
        self.assertIn("`Not making this change.`", read_text(os.path.join(
            ROOT, "cgh", "skills", "respond", "templates", "reply-draft.md")))
        self.assertIn("`変更を見送ります。`", read_text(os.path.join(
            ROOT, "src", "cgh", "skills", "respond", "templates", "reply-draft.md")))


class Cli(unittest.TestCase):
    def test_errors_exit_one_with_a_message(self):
        proc = subprocess.run(
            ["python3", SPEC.origin, "draft", "not-a-url", ".", "x.md", "--kind", "review",
             "--lang", "en"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not a pull request URL", proc.stderr)


if __name__ == "__main__":
    unittest.main()
