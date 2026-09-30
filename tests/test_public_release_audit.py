"""Tests for the public-release-audit repository scanner."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import extension_fixtures as fx
from repo_support import ROOT, SKILLS, git, make_git_repo, run_python


SCANNER = SKILLS / "public-release-audit" / "scripts" / "release_scan.py"
MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\n"


def gates(report: dict) -> dict[str, dict]:
    return {item["gate"]: item for item in report["gates"]}


class ReleaseScanTests(unittest.TestCase):
    def repo(self, files: dict[str, str]) -> tuple[Path, dict[str, str]]:
        base = {"LICENSE": MIT, "README.md": "# App\n", "SECURITY.md": "Report privately.\n"}
        return make_git_repo(self, {**base, **files})

    def scan(self, repo: Path, env: dict[str, str], *args: str) -> tuple[int, dict, str]:
        result = run_python(SCANNER, str(repo), *args, env=env)
        self.assertIn(result.returncode, {0, 1, 2}, result.stderr)
        return result.returncode, json.loads(result.stdout), result.stdout

    def commit(self, repo: Path, env: dict[str, str], message: str) -> None:
        git(repo, "add", "-A", env=env)
        git(repo, "commit", "-q", "-m", message, env=env)

    def test_clean_repository_has_no_failed_gate_and_changes_nothing(self) -> None:
        repo, env = self.repo({"app.py": "print(1)\n"})
        before = git(repo, "status", "--porcelain", env=env)
        code, report, _ = self.scan(repo, env, "--history")
        self.assertEqual(0, code, [g for g in report["gates"] if g["status"] == "failed"])
        found = gates(report)
        self.assertEqual("verified", found["secrets in history"]["status"])
        self.assertEqual("verified", found["licence"]["status"])
        self.assertEqual("blocked", found["platform settings"]["status"])
        self.assertEqual("not applicable", found["CI exposure when public"]["status"])
        self.assertEqual(before, git(repo, "status", "--porcelain", env=env))

    def test_deleted_secret_is_found_in_history_without_its_value(self) -> None:
        canary = fx.secret_canary()
        repo, env = self.repo({"config.py": f"TOKEN = '{canary}'\n"})
        (repo / "config.py").write_text("TOKEN = None\n", encoding="utf-8")
        self.commit(repo, env, "remove token")
        code, report, stdout = self.scan(repo, env)
        self.assertEqual("verified", gates(report)["secrets in tracked files"]["status"])
        self.assertEqual("not checked", gates(report)["secrets in history"]["status"])
        code, report, stdout = self.scan(repo, env, "--history")
        self.assertEqual(1, code)
        history = gates(report)["secrets in history"]
        self.assertEqual("failed", history["status"])
        self.assertEqual(["config.py"], [item["path"] for item in history["evidence"]["locations"]])
        self.assertNotIn(canary, stdout)
        self.assertNotIn(canary[4:16], stdout)

    def test_sensitive_debris_ignored_and_large_files_fail(self) -> None:
        repo, env = self.repo({".env": "A=1\n", ".env.example": "A=\n", "node_modules/x/index.js": "x\n",
                               "big.txt": "y" * 200, "build.log": "old\n"})
        fx.write(repo / ".gitignore", "*.log\n")
        self.commit(repo, env, "ignore logs")
        code, report, _ = self.scan(repo, env, "--large-file-bytes", "100")
        self.assertEqual(1, code)
        found = gates(report)
        self.assertEqual([".env"], found["sensitive files"]["evidence"]["tracked"])
        self.assertEqual(["build.log"], found["files tracked despite ignore rules"]["evidence"]["paths"])
        artifacts = found["generated, large, and debris artifacts"]["evidence"]
        self.assertEqual(["node_modules/x/index.js"], artifacts["debris"])
        self.assertEqual(["big.txt"], [item["path"] for item in artifacts["large"]])

    def test_licence_missing_or_mismatched_fails(self) -> None:
        repo, env = self.repo({"package.json": '{"name": "a", "license": "Apache-2.0"}'})
        _, report, _ = self.scan(repo, env)
        self.assertEqual({"package.json": "Apache-2.0"}, gates(report)["licence"]["evidence"]["mismatched"])
        (repo / "LICENSE").unlink()
        self.commit(repo, env, "drop licence")
        _, report, _ = self.scan(repo, env)
        self.assertEqual("failed", gates(report)["licence"]["status"])

    def test_generic_pattern_hits_need_review_and_placeholders_are_ignored(self) -> None:
        repo, env = self.repo({"docs.md": 'api_key = "your-api-key-here"\n'})
        _, report, _ = self.scan(repo, env)
        self.assertEqual("verified", gates(report)["secrets in tracked files"]["status"])
        value = "Zq" + "9vT4mW2rX8"
        fx.write(repo / "settings.py", f'password = "{value}"\n')
        self.commit(repo, env, "settings")
        code, report, stdout = self.scan(repo, env)
        gate = gates(report)["secrets in tracked files"]
        self.assertEqual("not checked", gate["status"])
        self.assertEqual([("settings.py", "credential-assignment")],
                         [(item["path"], item["rule"]) for item in gate["evidence"]["locations"]])
        self.assertNotIn(value, stdout)

    def test_author_emails_are_counted_not_listed(self) -> None:
        repo, env = self.repo({})
        _, report, stdout = self.scan(repo, env, "--history")
        self.assertEqual({"distinct": 1, "not_noreply": 1}, gates(report)["personal data in history"]["evidence"]["author_emails"])
        self.assertNotIn("fixture@example.invalid", stdout)

    def test_this_repository_has_no_failed_file_gates(self) -> None:
        result = run_python(SCANNER, str(ROOT))
        report = json.loads(result.stdout)
        failed = [item["gate"] for item in report["gates"] if item["status"] == "failed"]
        self.assertEqual([], failed)


if __name__ == "__main__":
    unittest.main()
