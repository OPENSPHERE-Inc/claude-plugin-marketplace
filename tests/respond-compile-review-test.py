#!/usr/bin/env python3
"""respond-compile-review-test.py — self-test for creview/skills/respond/scripts/compile-review.py
on temporary review documents.

Usage: python3 tests/respond-compile-review-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "creview", "skills", "respond", "scripts", "compile-review.py")

DOCUMENT = """# Parallel Code Review Report

## Major

### M-1 — `src/a.py:10` [Bug]

The function returns early.

<!-- METADATA(M-1) -->
- **Triage:** 🔧 Will Fix
- **Estimate:** ▶️ Maintain
<!-- /METADATA(M-1) -->

### M-2 — `README.md:3` [Docs]

The README names a removed option.

<!-- METADATA(M-2) -->
- **Triage:** 🔧 Will Fix
- **Estimate:** 🚧 Alternative
<!-- /METADATA(M-2) -->
"""


MISSING = object()


def item(finding_id, stages, estimate="Maintain", text_only=MISSING):
    target = {"id": finding_id, "assignee": "general-purpose", "stages": stages}
    if text_only is not MISSING:
        target["text_only"] = text_only
    target.update({"estimate": estimate, "adr": None, "fix_plan": []})
    return target


class CompileReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="respond-compile-review-test.")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.doc = self.write("review.md", DOCUMENT)
        os.makedirs(os.path.join(self.tmp, "statuses"))

    def write(self, rel, data):
        path = os.path.join(self.tmp, *rel.split("/"))
        with open(path, "wb") as f:
            f.write(data.encode("utf-8") if isinstance(data, str) else data)
        return path

    def status(self, finding_id, verdict="Maintain", text_only=MISSING, name=None):
        status = {
            "id": finding_id, "specialist": "general-purpose", "verdict": verdict,
            "description": f"Fixed {finding_id}.",
            "memo_value": f"🟢 Fixed ({verdict}) — fixed {finding_id}",
            "files": ["README.md"],
        }
        if text_only is not MISSING:
            status["text_only"] = text_only
        self.write(f"statuses/{name or finding_id}.jsonl",
                   json.dumps(status, ensure_ascii=False))

    def targets(self, *items):
        self.write("targets.jsonl", json.dumps(
            {"items": list(items), "fix_count": len(items), "not_ready": []}))

    def run_compile(self):
        proc = subprocess.run([sys.executable, SCRIPT, self.tmp, self.doc],
                              capture_output=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def read(self, rel):
        with open(os.path.join(self.tmp, *rel.split("/")), encoding="utf-8") as f:
            return f.read()

    def test_docs_stage_only_fixes_are_docs_only(self):
        self.status("M-1")
        self.status("M-2")
        self.targets(item("M-1", ["docs"]), item("M-2", ["docs"]))
        result = self.run_compile()
        self.assertIs(result["docs_only"], True)
        self.assertEqual(result["fixed_count"], 2)
        self.assertIs(result["code_changed"], True)

    def test_docs_stage_targets_without_a_status_keep_docs_only(self):
        self.status("M-2")
        self.targets(item("M-1", ["docs"]), item("M-2", ["docs"]))
        self.assertIs(self.run_compile()["docs_only"], True)

    def test_a_code_stage_target_without_a_status_is_not_docs_only(self):
        for stages in (["code"], ["code", "docs"]):
            with self.subTest(stages=stages):
                self.setUp()
                self.status("M-2")
                self.targets(item("M-1", stages), item("M-2", ["docs"]))
                self.assertIs(self.run_compile()["docs_only"], False)

    def test_a_fix_with_a_code_stage_is_not_docs_only(self):
        for stages in (["code"], ["code", "docs"], ["docs", "code"], []):
            with self.subTest(stages=stages):
                self.setUp()
                self.status("M-1")
                self.status("M-2")
                self.targets(item("M-1", stages), item("M-2", ["docs"]))
                self.assertIs(self.run_compile()["docs_only"], False)

    def test_no_fix_is_not_docs_only(self):
        self.targets(item("M-1", ["docs"]))
        result = self.run_compile()
        self.assertIs(result["docs_only"], False)
        self.assertEqual(result["fixed_count"], 0)
        self.assertIs(result["code_changed"], False)
        self.assertEqual(result["summary_line"], "0 fixed")

    def test_missing_targets_is_not_docs_only(self):
        self.status("M-1")
        result = self.run_compile()
        self.assertIs(result["docs_only"], False)
        self.assertEqual(result["fixed_count"], 1)

    def test_malformed_targets_is_not_docs_only(self):
        cases = {
            "truncated": "{\"items\": [",
            "not JSON": "items",
            "empty": "",
            "two lines": json.dumps({"items": [item("M-1", ["docs"])]}) + "\n{}\n",
            "not UTF-8": b"\xff\xfe{}",
            "array": json.dumps([item("M-1", ["docs"])]),
            "no items": "{}",
            "items not a list": json.dumps({"items": {"M-1": item("M-1", ["docs"])}}),
            "item not an object": json.dumps({"items": ["M-1"]}),
            "id not a string": json.dumps({"items": [item(["M-1"], ["docs"])]}),
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                self.setUp()
                self.status("M-1")
                self.write("targets.jsonl", data)
                result = self.run_compile()
                self.assertIs(result["docs_only"], False)
                self.assertEqual(result["fixed_count"], 1)

    def test_unmatched_id_is_not_docs_only(self):
        self.status("M-1")
        self.status("M-2")
        self.targets(item("M-1", ["docs"]))
        self.assertIs(self.run_compile()["docs_only"], False)

    def test_stages_not_a_list_is_not_docs_only(self):
        for stages in ("docs", None, {"docs": True}):
            with self.subTest(stages=stages):
                self.setUp()
                self.status("M-1")
                self.targets(item("M-1", stages))
                self.assertIs(self.run_compile()["docs_only"], False)
        self.setUp()
        self.status("M-1")
        target = item("M-1", ["docs"])
        del target["stages"]
        self.targets(target)
        self.assertIs(self.run_compile()["docs_only"], False)

    def test_duplicate_id_with_a_code_stage_is_not_docs_only(self):
        self.status("M-1")
        self.targets(item("M-1", ["docs"]), item("M-1", ["code"]))
        self.assertIs(self.run_compile()["docs_only"], False)

    def test_text_only_code_stage_fixes_are_docs_only(self):
        cases = {
            "code stages alone": (item("M-1", ["code"], text_only=True),
                                  item("M-2", ["code", "docs"], text_only=True)),
            "mixed with a docs stage": (item("M-1", ["code", "docs"], text_only=True),
                                        item("M-2", ["docs"])),
        }
        for name, targets in cases.items():
            with self.subTest(case=name):
                self.setUp()
                self.status("M-1", text_only=True)
                self.status("M-2", text_only=True)
                self.targets(*targets)
                result = self.run_compile()
                self.assertIs(result["docs_only"], True)
                self.assertEqual(result["fixed_count"], 2)

    def test_a_code_stage_target_not_marked_text_only_is_not_docs_only(self):
        for text_only in (False, MISSING):
            with self.subTest(text_only=text_only):
                self.setUp()
                self.status("M-1", text_only=True)
                self.targets(item("M-1", ["code"], text_only=text_only))
                self.assertIs(self.run_compile()["docs_only"], False)

    def test_a_code_stage_status_not_marked_text_only_is_not_docs_only(self):
        for text_only in (False, MISSING):
            with self.subTest(text_only=text_only):
                self.setUp()
                self.status("M-1", text_only=text_only)
                self.targets(item("M-1", ["code"], text_only=True))
                self.assertIs(self.run_compile()["docs_only"], False)

    def test_a_text_only_code_stage_target_without_a_status_is_not_docs_only(self):
        for stages in (["code"], ["code", "docs"]):
            with self.subTest(stages=stages):
                self.setUp()
                self.status("M-2", text_only=True)
                self.targets(item("M-1", stages, text_only=True), item("M-2", ["docs"]))
                self.assertIs(self.run_compile()["docs_only"], False)

    def test_text_only_other_than_the_boolean_true_is_not_docs_only(self):
        for value in ("true", 1, 1.0, None, [True]):
            for side in ("target", "status"):
                with self.subTest(value=value, side=side):
                    self.setUp()
                    self.status("M-1", text_only=value if side == "status" else True)
                    self.targets(item("M-1", ["code"],
                                      text_only=value if side == "target" else True))
                    self.assertIs(self.run_compile()["docs_only"], False)

    def test_every_status_of_a_code_stage_target_must_be_text_only(self):
        for second, expected in ((True, True), (False, False), (MISSING, False)):
            with self.subTest(second=second):
                self.setUp()
                self.status("M-1", text_only=True)
                self.status("M-1", text_only=second, name="M-1-docs")
                self.targets(item("M-1", ["code", "docs"], text_only=True))
                self.assertIs(self.run_compile()["docs_only"], expected)

    def test_a_docs_stage_target_ignores_text_only(self):
        for text_only in (False, "true", MISSING):
            with self.subTest(text_only=text_only):
                self.setUp()
                self.status("M-2", text_only=False)
                self.targets(item("M-2", ["docs"], text_only=text_only))
                self.assertIs(self.run_compile()["docs_only"], True)

    def test_a_target_with_neither_stage_is_not_docs_only_even_if_text_only(self):
        for stages in ([], ["review"]):
            with self.subTest(stages=stages):
                self.setUp()
                self.status("M-1", text_only=True)
                self.targets(item("M-1", stages, text_only=True))
                self.assertIs(self.run_compile()["docs_only"], False)

    def test_existing_output_is_unchanged(self):
        for with_targets in (False, True):
            with self.subTest(targets=with_targets):
                self.setUp()
                self.status("M-1", "Maintain")
                self.status("M-2", "Alternative")
                if with_targets:
                    self.targets(item("M-1", ["docs"]), item("M-2", ["docs"], "Alternative"))
                result = self.run_compile()
                self.assertEqual(list(result), ["fixed_count", "code_changed", "docs_only",
                                                "summary_line", "maintain", "alternative"])
                self.assertEqual(result["fixed_count"], 2)
                self.assertIs(result["code_changed"], True)
                self.assertIs(result["docs_only"], with_targets)
                self.assertEqual(result["summary_line"], "2 fixed (1 Maintain + 1 Alternative)")
                self.assertEqual(result["maintain"], 1)
                self.assertEqual(result["alternative"], 1)
                events = [json.loads(line) for line in self.read("events.jsonl").splitlines()]
                self.assertEqual(events, [
                    {"id": "M-1", "field": "status", "value": "🟢 Fixed (Maintain) — fixed M-1"},
                    {"id": "M-2", "field": "status",
                     "value": "🟢 Fixed (Alternative) — fixed M-2"},
                ])
                document = self.read("review.md")
                self.assertIn("- **Status:** 🟢 Fixed (Maintain) — fixed M-1\n"
                              "<!-- /METADATA(M-1) -->", document)
                self.assertIn("- **Status:** 🟢 Fixed (Alternative) — fixed M-2\n"
                              "<!-- /METADATA(M-2) -->", document)


if __name__ == "__main__":
    unittest.main()
