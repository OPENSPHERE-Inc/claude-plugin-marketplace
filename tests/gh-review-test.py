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


def view(head=HEAD, author="author", viewer="me", mergeable="MERGEABLE"):
    return {"data": {"viewer": {"login": viewer}, "repository": {"pullRequest": {
        "id": "PR_1", "number": 7, "state": "OPEN", "author": {"login": author},
        "title": "Title", "body": "Description",
        "headRefOid": head, "headRefName": "feature", "baseRefOid": "c" * 40,
        "mergeable": mergeable,
        "headRepository": {"nameWithOwner": "acme/app"},
    }}}}


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


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
        self.compare_status = {}

    def __call__(self, cmd, input=None, **_):
        self.calls.append(cmd)
        if cmd[0] == "git":
            return self.git_answer(cmd)
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
        answer = self.git.get(key, "")
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
        m = re.search(r"[?&]page=([0-9]+)", path)
        page = int(m.group(1)) if m else 1
        for tail, items in (("/files", FILES), ("/pulls/7/reviews", self.reviews),
                            ("/pulls/7/comments", self.review_comments),
                            ("/issues/7/comments", self.issue_comments)):
            if tail in path:
                return items if page == 1 else []
        raise mod.Error(f"unexpected path {path}")

    def graphql(self, body):
        query, variables = body["query"], body.get("variables", {})
        if "mutation" not in query:
            if "node(" not in query:
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

    def test_hidden_comments_are_escaped(self):
        self.assertNotIn("<!--", mod.safe_text("<!-- cgh:verified M-1 -->"))


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
        self.assertNotIn("Reviewer", line["body"])
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
        self.assertRegex(gh.named("submitPullRequestReview")[0]["body"],
                         r"<!-- cgh:verified M-7 -->")


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
        gh.review_comments.append({
            "id": 6, "user": {"login": "me"}, "pull_request_review_id": 1, "path": "src/a.py",
            "line": 10, "in_reply_to_id": 5, "body": "ok\n<!-- cgh:verified M-1 -->"})
        result, _, _ = self.prior()
        self.assertEqual((result["open"], result["verified"]), ([], ["M-1"]))

    def test_dismissed_review_is_ignored(self):
        gh = self.fake()
        self.local(gh)
        self.posted(gh)
        gh.reviews[0]["state"] = "DISMISSED"
        self.assertEqual(self.prior()[0]["open"], [])

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

    def test_uncommitted_changes_stop_verification(self):
        gh = self.fake()
        self.local(gh)
        gh.git["status"] = " M src/a.py\n"
        self.posted(gh)
        with self.assertRaisesRegex(mod.Error, "uncommitted"):
            self.prior()

    def test_no_open_finding_writes_no_document(self):
        gh = self.fake()
        self.local(gh, "ahead")
        result, _, doc = self.prior()
        self.assertEqual(result["open"], [])
        self.assertIsNone(result["document"])
        self.assertFalse(os.path.exists(doc))


class ResolveReplies(Base):
    def setup_doc(self):
        text = prior_doc_text([
            ("M-1", "✅ Verified — [as-recommended] null check added"),
            ("M-2", "✅ Verified — [differs] guard moved to the caller"),
            ("M-3", "💬 Feedback — the else branch is unchanged"),
            ("M-4", None),
            ("M-5", "✅ Verified — [as-recommended] done"),
        ])
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write(text)
        prior = {"findings": [
            {"id": "M-1", "target": {"kind": "thread", "id": 1}},
            {"id": "M-2", "target": {"kind": "thread", "id": 2}},
            {"id": "M-3", "target": {"kind": "thread", "id": 3}},
            {"id": "M-4", "target": {"kind": "thread", "id": 4}},
            {"id": "M-5", "target": {"kind": "review", "id": 9}},
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
        self.assertEqual(issue[0]["verified"], ["M-5"])

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

    def test_malformed_entry_is_refused(self):
        self.fake()
        for entry in ({"kind": "thread", "target_id": "x", "body": "a"},
                      {"kind": "other", "target_id": 1, "body": "a"},
                      {"kind": "thread", "target_id": 1, "body": ""}):
            with self.assertRaises(mod.Error):
                mod.cmd_preview(URL, self.replies_file([entry]))

    def test_unpushed_commits_stop_the_replies(self):
        gh = self.fake()
        tip = "f" * 40
        gh.compare_status = {tip: mod.Error("404 No common ancestor")}
        commits = self.save({"commits": [{"sha": tip, "subject": "s", "files": ["a"]}]},
                            "fix-commits.json")
        path = self.replies_file([{"kind": "thread", "target_id": 1, "finding_ids": [],
                                   "body": "a"}])
        self.assertFalse(mod.cmd_pushed(URL, commits)["pushed"])
        with self.assertRaisesRegex(mod.Error, "push"):
            mod.cmd_post(URL, path, commits)
        self.assertEqual(gh.posts, [])

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
        self.assertEqual(gh.posts[0][1]["body"], "Fixed")

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
        self.assertEqual(gh.posts[0][1]["body"], "Fixed")

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


class Cli(unittest.TestCase):
    def test_errors_exit_one_with_a_message(self):
        proc = subprocess.run(
            ["python3", SPEC.origin, "draft", "not-a-url", ".", "x.md", "--kind", "review",
             "--lang", "en"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not a pull request URL", proc.stderr)


if __name__ == "__main__":
    unittest.main()
