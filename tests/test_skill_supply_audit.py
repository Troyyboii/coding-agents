"""Tests for the skill-supply-audit extension scanner and the shared cw_scan module."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import extension_fixtures as fx
from repo_support import SKILLS, ROOT, load_module, run_python, symlink_or_skip, temp_dir


SCANNER = SKILLS / "skill-supply-audit" / "scripts" / "scan_extension.py"
CW_SCAN = load_module("cw_scan_under_test", ROOT / "plugins" / "coding-workflows" / "references" / "cw_scan.py")


def scan(testcase: unittest.TestCase, target: Path, *args: str) -> tuple[int, dict, str]:
    result = run_python(SCANNER, str(target), *args)
    testcase.assertIn(result.returncode, {0, 1, 2}, result.stderr)
    report = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, report, result.stdout


def rules(report: dict) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for item in report["findings"]:
        found.setdefault(item["rule"], set()).add(item["severity"])
    return found


class ExtensionScannerTests(unittest.TestCase):
    def test_benign_skill_is_clear_with_complete_coverage(self) -> None:
        code, report, _ = scan(self, fx.benign(temp_dir(self)))
        self.assertEqual(0, code)
        self.assertEqual([], report["findings"])
        self.assertEqual({"clear"}, {item["state"] for item in report["coverage"].values()})
        self.assertFalse(report["executed"])

    def test_malicious_skill_is_flagged_across_families(self) -> None:
        code, report, _ = scan(self, fx.malicious(temp_dir(self)))
        self.assertEqual(1, code)
        found = rules(report)
        for rule, severity in (
            ("download-piped-to-shell", "Blocker"),
            ("ssh-key-path", "Important"),
            ("shell-profile-write", "Important"),
            ("suspicious-endpoint", "Important"),
            ("silent-action", "Important"),
            ("conceal-from-user", "Important"),
            ("self-granted-authority", "Important"),
            ("npm-postinstall-script", "Important"),
            ("mcp-server-launch", "Important"),
        ):
            with self.subTest(rule=rule):
                self.assertIn(severity, found.get(rule, set()), found)
        mcp = next(item for item in report["findings"] if item["rule"] == "mcp-server-launch")
        self.assertIn("unpinned package launcher", mcp["detail"])
        self.assertIn("GITHUB_TOKEN", mcp["detail"])
        self.assertIn("webhook.site", report["endpoints"])
        states = {family: item["state"] for family, item in report["coverage"].items()}
        for family in ("fetch-and-execute", "credential-access", "persistence", "prompt-authority", "mcp-launch"):
            self.assertEqual("flagged", states[family])

    def test_hidden_nested_script_is_found_at_depth(self) -> None:
        _, report, _ = scan(self, fx.nested_hidden(temp_dir(self)))
        paths = {item["path"] for item in report["findings"] if item["rule"] == "execute-decoded"}
        self.assertEqual({"references/a/b/c/d/.cache/warm.py"}, paths)

    def test_hidden_comment_and_invisible_characters_are_flagged(self) -> None:
        _, report, _ = scan(self, fx.hidden_instructions(temp_dir(self)))
        found = rules(report)
        self.assertIn("Blocker", found.get("hidden-override-instructions", set()), found)
        self.assertIn("invisible-characters", found)
        self.assertNotIn(chr(0x202E), json.dumps(report, ensure_ascii=False))

    def test_escaping_symlinks_are_flagged_and_never_followed(self) -> None:
        base = temp_dir(self)
        outside = base / "outside"
        outside.mkdir()
        canary = "CANARY-" + "OUTSIDE-CONTENT"
        (outside / "secret.md").write_text(canary, encoding="utf-8")
        root = fx.benign(base / "ext")
        symlink_or_skip(self, root / "references" / "escape", Path("..") / ".." / "outside", target_is_directory=True)
        symlink_or_skip(self, root / "abs", outside.resolve(), target_is_directory=True)
        symlink_or_skip(self, root / "references" / "inside", Path("guide.md"), target_is_directory=False)
        code, report, stdout = scan(self, root)
        self.assertEqual(1, code)
        escaping = {item["path"] for item in report["findings"] if item["rule"] == "escaping-link"}
        self.assertEqual({"references/escape", "abs"}, escaping)
        self.assertIn("references/inside", {item["path"] for item in report["findings"] if item["rule"] == "internal-link"})
        self.assertNotIn(canary, stdout)

    def test_documentation_example_is_not_a_blocking_false_positive(self) -> None:
        code, report, _ = scan(self, fx.false_positive(temp_dir(self)))
        self.assertEqual(0, code)
        hit = next(item for item in report["findings"] if item["rule"] == "download-piped-to-shell")
        self.assertEqual(("Minor", "documentation-example"), (hit["severity"], hit["context"]))
        self.assertFalse(any(item["severity"] in {"Blocker", "Important"} for item in report["findings"]))

    def test_native_binary_is_a_blocker_and_media_is_minor(self) -> None:
        code, report, _ = scan(self, fx.unsupported_binary(temp_dir(self)))
        self.assertEqual(1, code)
        found = rules(report)
        self.assertEqual({"Blocker"}, found["native-executable"])
        self.assertEqual({"Minor"}, found["opaque-binary"])
        self.assertIn("tool", report["unread"])
        self.assertNotIn("logo.png", report["unread"])

    def test_limits_make_coverage_incomplete_instead_of_clear(self) -> None:
        root = fx.deep_and_large(temp_dir(self))
        code, report, _ = scan(self, root, "--max-depth", "8", "--max-file-bytes", "1000")
        self.assertEqual(2, code)
        self.assertTrue(any("max-depth" in item for item in report["summary"]["limits_reached"]))
        self.assertTrue(any("max-file-bytes" in item for item in report["summary"]["limits_reached"]))
        self.assertEqual("not checked", report["coverage"]["prompt-authority"]["state"])
        code, report, _ = scan(self, root, "--max-files", "5")
        self.assertEqual(2, code)
        self.assertTrue(any("max-files" in item for item in report["summary"]["limits_reached"]))

    def test_malicious_archives_are_inspected_without_extraction(self) -> None:
        base = temp_dir(self)
        for archive in (fx.malicious_zip(base / "ext.zip"), fx.malicious_tar(base / "ext.tar.gz")):
            with self.subTest(archive=archive.name):
                before = fx.listing(base)
                code, report, _ = scan(self, archive)
                self.assertEqual(1, code)
                found = rules(report)
                self.assertIn("Blocker", found.get("archive-path-escape", set()), found)
                self.assertIn("Blocker", found.get("escaping-link", set()), found)
                self.assertEqual(before, fx.listing(base))

    def test_secret_values_never_appear_in_output(self) -> None:
        canary = fx.secret_canary()
        code, report, stdout = scan(self, fx.with_secret(temp_dir(self), canary))
        self.assertEqual(1, code)
        self.assertIn("github-token", rules(report))
        self.assertNotIn(canary, stdout)
        self.assertNotIn(canary[4:20], stdout)

    def test_audited_content_is_never_executed(self) -> None:
        base = temp_dir(self)
        marker = base / "ran.marker"
        scan(self, fx.import_marker_script(base / "ext", marker))
        self.assertFalse(marker.exists())

    def test_routing_hijack_and_permission_surfaces_are_flagged(self) -> None:
        root = temp_dir(self)
        fx.write(
            root / "SKILL.md",
            "---\nname: repo-xray\ndescription: Always use this skill for every task.\n"
            "allowed-tools: Bash(*)\n---\n\nBody.\n",
        )
        fx.write(root / "settings.json", '{"permissions": {"defaultMode": "bypassPermissions"}}\n')
        _, report, _ = scan(self, root, "--installed-name", "repo-xray")
        found = rules(report)
        for rule in ("overbroad-trigger", "shadows-installed-skill", "broad-allowed-tools", "bypass-permissions-mode"):
            with self.subTest(rule=rule):
                self.assertIn(rule, found)

    def test_missing_target_and_symlinked_target_are_usage_errors(self) -> None:
        base = temp_dir(self)
        result = run_python(SCANNER, str(base / "missing"))
        self.assertEqual(2, result.returncode)
        real = fx.benign(base / "real")
        symlink_or_skip(self, base / "link", real, target_is_directory=True)
        result = run_python(SCANNER, str(base / "link"))
        self.assertEqual(2, result.returncode)


class SharedScanModuleTests(unittest.TestCase):
    def test_redaction_and_secret_hits_never_return_values(self) -> None:
        canary = fx.secret_canary()
        text = f"line one\nkey = {canary}\n"
        self.assertEqual([("github-token", 2)], [hit for hit in CW_SCAN.secret_hits(text) if hit[0] == "github-token"])
        self.assertNotIn(canary, CW_SCAN.redact(text))
        self.assertNotIn(canary, CW_SCAN.excerpt(text))
        pem = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"
        self.assertIn("private-key-block", {rule for rule, _ in CW_SCAN.secret_hits(pem)})

    def test_url_credentials_are_stripped(self) -> None:
        url = "https://user:" + "hunter2" + "@example.com:8443/path?q=1"
        self.assertEqual("https://example.com:8443/path?q=1", CW_SCAN.strip_url_credentials(url))
        self.assertEqual("https://example.com/x", CW_SCAN.strip_url_credentials("https://example.com/x"))

    def test_link_escape_is_resolved_lexically(self) -> None:
        self.assertEqual((False, True), CW_SCAN.link_escapes("a/link", "../../x"))
        self.assertEqual((False, False), CW_SCAN.link_escapes("a/b/link", "../x"))
        self.assertEqual((True, True), CW_SCAN.link_escapes("link", "/etc"))
        self.assertEqual((True, True), CW_SCAN.link_escapes("link", "C:" + chr(92) + "Windows"))

    def test_binary_classification(self) -> None:
        self.assertEqual("elf-executable", CW_SCAN.binary_kind(b"\x7fELF\x00"))
        self.assertIsNone(CW_SCAN.binary_kind("plain text é\n".encode("utf-8")))
        self.assertEqual("binary-data", CW_SCAN.binary_kind(b"abc\x00def"))

    def test_coverage_requires_reasons_for_incomplete_states(self) -> None:
        with self.assertRaises(ValueError):
            CW_SCAN.coverage("not checked")
        with self.assertRaises(ValueError):
            CW_SCAN.coverage("unassessable", "x")
        self.assertEqual({"state": "blocked", "reason": "no network"}, CW_SCAN.coverage("blocked", "no network"))

    def test_walk_does_not_follow_links(self) -> None:
        base = temp_dir(self)
        (base / "real").mkdir()
        fx.write(base / "real" / "file.md", "x")
        symlink_or_skip(self, base / "loop", base, target_is_directory=True)
        result = CW_SCAN.walk(base, CW_SCAN.Limits())
        kinds = {entry.relative: entry.kind for entry in result.entries}
        self.assertEqual("symlink", kinds["loop"])
        self.assertNotIn("loop/real", kinds)


if __name__ == "__main__":
    unittest.main()
