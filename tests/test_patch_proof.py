"""Tests for the patch-proof plan runner: validation, dry run, isolation, verdicts, and cleanup."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import unittest
from unittest import mock
from pathlib import Path

import extension_fixtures as fx
from repo_support import SKILLS, git, load_helper, make_git_repo, run_python, temp_dir


RUNNER = SKILLS / "patch-proof" / "scripts" / "proof_run.py"
PY = sys.executable

CHECK = """import sys
from calc import divide
case = sys.argv[1]
try:
    if case == "repro":
        ok = divide(1, 0) is None
    elif case == "variant":
        ok = divide(-5, 0) is None
    else:
        ok = divide(6, 3) == 2
except ZeroDivisionError:
    ok = False
print("PASS" if ok else "BUG", case)
sys.exit(0 if ok else 1)
"""
BUGGY = "def divide(a, b):\n    try:\n        return a // b\n    except ZeroDivisionError:\n        raise\n"
FIXED = "def divide(a, b):\n    if b == 0:\n        return None\n    return a // b\n"
REGRESSED = "def divide(a, b):\n    return None\n"


def case(case_id: str, role: str, arg: str, base: dict, patched: dict) -> dict:
    return {"id": case_id, "role": role, "argv": [PY, "check.py", arg], "timeout_s": 60,
            "expect": {"base": base, "patched": patched}}


FAIL = {"exit": "nonzero", "stdout_contains": ["BUG"]}
PASS = {"exit": 0, "stdout_contains": ["PASS"]}


class PatchProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo, self.env = make_git_repo(self, {"calc.py": BUGGY, "check.py": CHECK})
        self.base = git(self.repo, "rev-parse", "HEAD", env=self.env)
        self.work = temp_dir(self)
        self.env["TMPDIR"] = str(self.work)
        self.env["TEMP"] = str(self.work)
        self.env["TMP"] = str(self.work)

    def commit(self, calc: str, message: str) -> str:
        (self.repo / "calc.py").write_text(calc, encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", message, env=self.env)
        return git(self.repo, "rev-parse", "HEAD", env=self.env)

    def plan(self, patched: dict | None, cases: list[dict], mode: str = "differential", **extra) -> Path:
        body = {"schema": "coding-workflows/proof-plan", "schema_version": 1, "mode": mode,
                "base": {"rev": self.base}, "cases": cases, "network": "not-controlled", **extra}
        if patched is not None:
            body["patched"] = patched
        path = self.work / f"plan-{len(list(self.work.glob('plan-*')))}.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def run_plan(self, plan: Path, *args: str) -> tuple[int, dict, str]:
        result = run_python(RUNNER, str(plan), "--repo", str(self.repo), *args, env=self.env, timeout=300)
        return result.returncode, json.loads(result.stdout) if result.stdout.strip() else {}, result.stderr

    def standard_cases(self) -> list[dict]:
        return [case("repro", "original_reproduction", "repro", FAIL, PASS),
                case("variant", "root_cause_variant", "variant", FAIL, PASS),
                case("legit", "legitimate_behavior", "legit", PASS, PASS)]

    def test_dry_run_prints_the_plan_and_executes_nothing(self) -> None:
        marker = self.work / "ran.marker"
        cases = [{"id": "m", "role": "reproduction", "argv": [PY, "-c", f"open({str(marker)!r}, 'w')"],
                  "expect": {"revision": {"exit": 0}}}]
        code, report, _ = self.run_plan(self.plan(None, cases, mode="single_revision"))
        self.assertEqual(0, code)
        self.assertFalse(report["executed"])
        self.assertEqual(self.base, report["revisions"]["base"])
        self.assertEqual([PY, "-c"], report["commands"][0]["argv"][:2])
        self.assertIn("approval", report["authorization_required"])
        self.assertFalse(marker.exists())
        self.assertEqual([], [p for p in self.work.iterdir() if p.name.startswith("patch-proof-")])

    def test_invalid_plans_are_rejected(self) -> None:
        fixed = {"rev": self.base}
        bad = {
            "shell string": [dict(case("r", "original_reproduction", "repro", FAIL, PASS), argv="python check.py repro")],
            "shell wrapper": [dict(case("r", "original_reproduction", "repro", FAIL, PASS), argv=["bash", "-c", "true"])],
            "missing legit": [case("r", "original_reproduction", "repro", FAIL, PASS),
                              case("v", "root_cause_variant", "variant", FAIL, PASS)],
            "missing variant": [case("r", "original_reproduction", "repro", FAIL, PASS),
                                case("l", "legitimate_behavior", "legit", PASS, PASS)],
            "wrong role": [dict(case("r", "original_reproduction", "repro", FAIL, PASS), role="reproduction")],
        }
        for label, cases in bad.items():
            with self.subTest(label=label):
                code, _, stderr = self.run_plan(self.plan(fixed, cases))
                self.assertEqual(2, code, stderr)
        body = json.loads(self.plan(fixed, self.standard_cases()).read_text(encoding="utf-8"))
        del body["network"]
        path = self.work / "no-network.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        code, _, stderr = self.run_plan(path)
        self.assertEqual(2, code)
        self.assertIn("not-controlled", stderr)
        waived = self.plan(fixed, self.standard_cases()[::2], waiver={"root_cause_variant": "no independent variant exists"})
        self.assertEqual(0, self.run_plan(waived)[0])

    def test_differential_proof_is_verified_in_isolation(self) -> None:
        (self.repo / "notes.txt").write_text("uncommitted user work\n", encoding="utf-8")
        patched = self.commit(FIXED, "fix divide")
        git(self.repo, "checkout", "-q", self.base, env=self.env)
        (self.repo / "notes.txt").write_text("uncommitted user work\n", encoding="utf-8")
        before = (self.repo / "calc.py").read_text(encoding="utf-8")
        code, report, stderr = self.run_plan(self.plan({"rev": patched}, self.standard_cases()), "--execute")
        self.assertEqual(0, code, stderr)
        self.assertEqual("verified", report["result"]["status"])
        self.assertEqual({"verified"}, {item["status"] for item in report["cases"]})
        repro = next(item for item in report["cases"] if item["id"] == "repro")
        self.assertNotEqual(0, repro["sides"]["base"]["exit_code"])
        self.assertEqual(0, repro["sides"]["patched"]["exit_code"])
        self.assertTrue(report["source_worktree_unchanged"])
        self.assertEqual("removed", report["cleanup"])
        self.assertEqual(before, (self.repo / "calc.py").read_text(encoding="utf-8"))
        self.assertEqual("uncommitted user work\n", (self.repo / "notes.txt").read_text(encoding="utf-8"))
        self.assertEqual([], [p for p in self.work.iterdir() if p.name.startswith("patch-proof-")])
        self.assertNotIn("proven", json.dumps(report))

    def test_failed_verdicts_name_the_reason(self) -> None:
        regressed = self.commit(REGRESSED, "break divide")
        code, report, _ = self.run_plan(self.plan({"rev": regressed}, self.standard_cases()), "--execute")
        self.assertEqual(1, code)
        reasons = {item["id"]: item["reason"] for item in report["cases"]}
        self.assertEqual("regressed", reasons["legit"])
        wrong = [case("repro", "original_reproduction", "legit", FAIL, PASS),
                 case("variant", "root_cause_variant", "variant", FAIL, PASS),
                 case("legit", "legitimate_behavior", "legit", PASS, PASS)]
        _, report, _ = self.run_plan(self.plan({"rev": regressed}, wrong), "--execute")
        self.assertEqual("not-reproduced-on-base", {i["id"]: i["reason"] for i in report["cases"]}["repro"])
        self.assertEqual("failed", report["result"]["status"])

    def test_controlled_diff_is_hash_pinned(self) -> None:
        diff = self.work / "fix.patch"
        (self.repo / "calc.py").write_text(FIXED, encoding="utf-8")
        diff.write_text(git(self.repo, "diff", env=self.env) + "\n", encoding="utf-8")
        git(self.repo, "checkout", "-q", "--", "calc.py", env=self.env)
        digest = hashlib.sha256(diff.read_bytes()).hexdigest()
        code, _, stderr = self.run_plan(self.plan({"diff": str(diff), "diff_sha256": "0" * 64}, self.standard_cases()))
        self.assertEqual(2, code)
        self.assertIn("diff_sha256", stderr)
        code, report, stderr = self.run_plan(self.plan({"diff": str(diff), "diff_sha256": digest}, self.standard_cases()), "--execute")
        self.assertEqual(0, code, stderr)
        self.assertEqual(digest, report["revisions"]["diff_sha256"])

    def test_timeout_terminates_the_process_group(self) -> None:
        marker = self.work / "grandchild.marker"
        child = f"import time; time.sleep(2); open({str(marker)!r}, 'w')"
        parent = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(30)"
        cases = [{"id": "hang", "role": "reproduction", "argv": [PY, "-c", parent], "timeout_s": 1,
                  "expect": {"revision": {"exit": 0}}}]
        started = time.monotonic()
        code, report, stderr = self.run_plan(self.plan(None, cases, mode="single_revision"), "--execute")
        self.assertLess(time.monotonic() - started, 45)
        self.assertEqual(2, code, stderr)
        self.assertEqual(("blocked", "timeout"), (report["cases"][0]["status"], report["cases"][0]["reason"]))
        self.assertTrue(report["cases"][0]["sides"]["revision"]["timed_out"])
        self.assertTrue(report["source_worktree_unchanged"])
        # Wait past the grandchild's sleep so a surviving grandchild would
        # have written the marker by the time we assert it is absent.
        time.sleep(3)
        if os.name == "nt":
            # A surviving grandchild may hold the scratch clone; cleanup is retried and reported, never raised.
            self.assertTrue(report["cleanup"] == "removed" or report["cleanup"].startswith("removal failed"), report["cleanup"])
            self.assertTrue(any("Windows" in item for item in report["limitations"]))
        else:
            self.assertEqual("removed", report["cleanup"])
            self.assertFalse(marker.exists(), "grandchild survived the timeout")

    def test_output_is_capped_and_redacted(self) -> None:
        canary = fx.secret_canary()
        script = f"print({canary!r}); print('x' * 300000); print('END-MARKER')"
        cases = [{"id": "loud", "role": "reproduction", "argv": [PY, "-c", script],
                  "expect": {"revision": {"exit": 0, "stdout_contains": ["END-MARKER"]}}}]
        code, report, _ = self.run_plan(self.plan(None, cases, mode="single_revision", limits={"output_bytes": 4096}), "--execute")
        self.assertEqual(0, code)
        side = report["cases"][0]["sides"]["revision"]
        self.assertTrue(side["output_truncated"])
        self.assertGreater(side["output_bytes"], 300000)
        self.assertTrue(side["markers"]["END-MARKER"])
        self.assertNotIn(canary, json.dumps(report))
        self.assertIn("not a patch proof", report["result"]["note"])


class RemoveTreeTests(unittest.TestCase):
    """Cleanup failures are reported, never raised, whatever the platform."""

    def test_locked_tree_is_retried_then_reported_without_raising(self) -> None:
        runner = load_helper("patch-proof", "proof_run.py")
        tree = temp_dir(self) / "scratch"
        tree.mkdir()
        locked = PermissionError(32, "The process cannot access the file because it is being used by another process")
        with mock.patch.object(runner.shutil, "rmtree", side_effect=locked) as rmtree, \
                mock.patch.object(runner.time, "sleep") as sleep:
            self.assertFalse(runner.remove_tree(tree, attempts=3, delay_s=0.01))
        self.assertEqual(3, rmtree.call_count)
        self.assertEqual(2, sleep.call_count)
        self.assertTrue(tree.exists())

    def test_tree_released_after_a_retry_is_removed(self) -> None:
        runner = load_helper("patch-proof", "proof_run.py")
        tree = temp_dir(self) / "scratch"
        (tree / "clone").mkdir(parents=True)
        real_rmtree = runner.shutil.rmtree
        calls = []

        def released_on_second_call(path, **kwargs):
            calls.append(path)
            if len(calls) == 1:
                raise PermissionError(32, "in use")
            real_rmtree(path, **kwargs)

        with mock.patch.object(runner.shutil, "rmtree", side_effect=released_on_second_call), \
                mock.patch.object(runner.time, "sleep"):
            self.assertTrue(runner.remove_tree(tree, attempts=3, delay_s=0.01))
        self.assertEqual(2, len(calls))
        self.assertFalse(tree.exists())


if __name__ == "__main__":
    unittest.main()
