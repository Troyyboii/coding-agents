"""Tests for the session-checkpoint capture and freshness comparison helper."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

import extension_fixtures as fx
from repo_support import SKILLS, git, make_git_repo, run_python, temp_dir


HELPER = SKILLS / "session-checkpoint" / "scripts" / "checkpoint.py"


class CheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo, self.env = make_git_repo(self, {"app.py": "print(1)\n", "README.md": "x\n"})
        self.out = temp_dir(self)

    def helper(self, *args: str, cwd: Path | None = None) -> tuple[int, str, str]:
        result = run_python(HELPER, *args, cwd=cwd or self.repo, env=self.env)
        return result.returncode, result.stdout, result.stderr

    def capture(self, narrative: dict | None = None, name: str = "cp.json") -> Path:
        args = ["capture"]
        if narrative is not None:
            path = self.out / f"{name}.narrative.json"
            path.write_text(json.dumps(narrative), encoding="utf-8")
            args += ["--narrative", str(path)]
        code, stdout, stderr = self.helper(*args)
        self.assertEqual(0, code, stderr)
        checkpoint = self.out / name
        checkpoint.write_text(stdout, encoding="utf-8")
        return checkpoint

    def compare(self, checkpoint: Path) -> tuple[int, dict]:
        code, stdout, stderr = self.helper("compare", str(checkpoint))
        self.assertIn(code, {0, 1}, stderr)
        return code, json.loads(stdout)

    def test_capture_records_identity_state_and_narrative(self) -> None:
        (self.repo / "app.py").write_text("print(2)\n", encoding="utf-8")
        (self.repo / "new.md").write_text("n\n", encoding="utf-8")
        narrative = {"goal": "Ship the parser", "next_actions": ["run tests"],
                     "evidence": [{"claim": "unit tests", "kind": "executed", "source": "pytest", "result": "3 passed"}]}
        data = json.loads(self.capture(narrative).read_text(encoding="utf-8"))
        self.assertEqual("main", data["git"]["branch"])
        self.assertEqual(git(self.repo, "rev-parse", "HEAD", env=self.env), data["git"]["head"])
        self.assertEqual([git(self.repo, "rev-list", "--max-parents=0", "HEAD", env=self.env)],
                         data["repository"]["root_commits"])
        self.assertEqual({"app.py"}, {item["path"] for item in data["worktree"]["changed"]})
        self.assertEqual({"new.md"}, {item["path"] for item in data["worktree"]["untracked"]})
        self.assertEqual(64, len(data["worktree"]["changed"][0]["sha256"]))
        self.assertEqual("Ship the parser", data["narrative"]["goal"])

    def test_compare_is_current_and_ignores_timestamps(self) -> None:
        (self.repo / "app.py").write_text("print(2)\n", encoding="utf-8")
        checkpoint = self.capture()
        stat = (self.repo / "app.py").stat()
        os.utime(self.repo / "app.py", (stat.st_atime + 3600, stat.st_mtime + 3600))
        code, report = self.compare(checkpoint)
        self.assertEqual(0, code)
        self.assertEqual(["current"], report["comparison"]["freshness"])

    def test_compare_detects_advanced_and_worktree_drift(self) -> None:
        (self.repo / "app.py").write_text("print(2)\n", encoding="utf-8")
        checkpoint = self.capture()
        (self.repo / "app.py").write_text("print(3)\n", encoding="utf-8")
        (self.repo / "other.md").write_text("o\n", encoding="utf-8")
        git(self.repo, "add", "other.md", env=self.env)
        git(self.repo, "commit", "-q", "-m", "add other", env=self.env)
        code, report = self.compare(checkpoint)
        self.assertEqual(1, code)
        comparison = report["comparison"]
        self.assertIn("advanced", comparison["freshness"])
        self.assertIn("worktree-drift", comparison["freshness"])
        self.assertEqual(["app.py"], comparison["details"]["worktree"]["modified_since"])
        self.assertTrue(comparison["details"]["commits_since"][0].endswith("add other"))

    def test_compare_detects_diverged_branch_and_different_repository(self) -> None:
        (self.repo / "second.md").write_text("2\n", encoding="utf-8")
        git(self.repo, "add", "second.md", env=self.env)
        git(self.repo, "commit", "-q", "-m", "second", env=self.env)
        checkpoint = self.capture()
        git(self.repo, "checkout", "-q", "-b", "feature", env=self.env)
        git(self.repo, "commit", "-q", "--amend", "-m", "rewritten", env=self.env)
        _, report = self.compare(checkpoint)
        self.assertIn("diverged", report["comparison"]["freshness"])
        self.assertIn("branch-changed", report["comparison"]["freshness"])
        other, other_env = make_git_repo(self, {"x.md": "x\n"})
        result = run_python(HELPER, "compare", str(checkpoint), cwd=other, env=other_env)
        self.assertEqual(["different-repository"], json.loads(result.stdout)["comparison"]["freshness"])

    def test_secret_narrative_is_refused_without_echo(self) -> None:
        canary = fx.secret_canary()
        path = self.out / "n.json"
        path.write_text(json.dumps({"blockers": [f"token {canary} expired"]}), encoding="utf-8")
        code, stdout, stderr = self.helper("capture", "--narrative", str(path))
        self.assertEqual(3, code)
        self.assertNotIn(canary, stdout + stderr)
        self.assertIn("blockers", stderr)

    def test_output_warnings_and_no_ignore_file_changes(self) -> None:
        narrative = self.out / "n.json"
        narrative.write_text("{}", encoding="utf-8")
        target = self.repo / ".agent-checkpoints" / "cp.json"
        target.parent.mkdir()
        code, _, stderr = self.helper("capture", "--narrative", str(narrative), "--output", str(target))
        self.assertEqual(0, code)
        self.assertTrue(target.is_file())
        self.assertIn("not ignored", stderr)
        self.assertFalse((self.repo / ".gitignore").exists())

    def test_remote_credentials_are_stripped(self) -> None:
        secret = "hunter" + "2"
        git(self.repo, "remote", "add", "origin", f"https://user:{secret}@example.com/org/repo.git", env=self.env)
        data = json.loads(self.capture().read_text(encoding="utf-8"))
        self.assertEqual(["https://example.com/org/repo.git"], data["repository"]["remotes"])
        self.assertNotIn(secret, json.dumps(data))

    def test_narrative_only_outside_a_repository(self) -> None:
        outside = temp_dir(self)
        code, stdout, _ = self.helper("capture", cwd=outside)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertIsNone(data["repository"])
        self.assertIn("unverifiable", data["freshness"])
        checkpoint = outside / "cp.json"
        checkpoint.write_text(stdout, encoding="utf-8")
        result = run_python(HELPER, "compare", str(checkpoint), cwd=self.repo, env=self.env)
        self.assertEqual(2, result.returncode)
        self.assertEqual(["unverifiable"], json.loads(result.stdout)["comparison"]["freshness"])

    def test_invalid_narrative_fields_are_rejected(self) -> None:
        path = self.out / "n.json"
        path.write_text(json.dumps({"command_output": "lots of logs"}), encoding="utf-8")
        code, _, stderr = self.helper("capture", "--narrative", str(path))
        self.assertEqual(2, code)
        self.assertIn("unsupported narrative fields", stderr)


if __name__ == "__main__":
    unittest.main()
