"""Tests for repository inventory, validation, and routing-evaluation tooling."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Never write bytecode next to the sources under test: executing helpers that
# live inside generated package trees must not drop __pycache__/*.pyc into
# those outputs and contaminate package-currentness validation.
sys.dont_write_bytecode = True

from repository_inventory import (  # noqa: E402
    REVIEW_CANDIDATES,
    collect_inventory,
    parse_skill_frontmatter,
    render_inventory,
    require_repository_path,
)
from host_toolbox import (  # noqa: E402
    build_report,
    evaluate_readiness,
    inspect_codex,
    inspect_luna,
    load_profile,
    main as host_toolbox_main,
    parse_mcp_list,
    parse_mcp_output,
)
from routing_evals import (  # noqa: E402
    _plugin_preflight,
    _report_contains_sensitive_data,
    build_provenance,
    load_eval_data,
    main as routing_main,
    plugin_is_ready,
    run_case,
    select_cases,
    validate_eval_data,
)
from work_mode_packages import build_packages, packages_are_current, validate_packages  # noqa: E402
import work_mode_packages
import agent_skill_packages  # noqa: E402
import claude_app_packages
from claude_app_packages import (  # noqa: E402
    active_skill_names as claude_app_active_skill_names,
)
from claude_app_packages import (  # noqa: E402
    build_packages as claude_app_build_packages,
)
from claude_app_packages import (
    discover_canonical_skills as claude_app_discover_canonical_skills,
)
from agent_skill_packages import (
    build_packages as agent_skill_build_packages,
    packages_are_current as agent_skill_packages_are_current,
    validate_packages as agent_skill_validate_packages,
)
from claude_app_packages import (
    packages_are_current as claude_app_packages_are_current,
)
from claude_app_packages import (
    validate_packages as claude_app_validate_packages,
)
from claude_app_packages import _validate_zip_package


VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "coding_agents_validate_repository", ROOT / "scripts" / "validate-repository.py"
)
if VALIDATOR_SPEC is None or VALIDATOR_SPEC.loader is None:  # pragma: no cover - import setup invariant
    raise RuntimeError("Could not load repository validator")
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)

GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "coding_agents_generate_inventory", ROOT / "scripts" / "generate-inventory.py"
)
if GENERATOR_SPEC is None or GENERATOR_SPEC.loader is None:  # pragma: no cover - import setup invariant
    raise RuntimeError("Could not load inventory generator")
GENERATOR = importlib.util.module_from_spec(GENERATOR_SPEC)
GENERATOR_SPEC.loader.exec_module(GENERATOR)


def load_cli_module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORK_MODE_CLI = load_cli_module("package-work-mode")
CLAUDE_APP_CLI = load_cli_module("package-claude-app")
AGENT_SKILLS_CLI = load_cli_module("package-agent-skills")
DIFF_CHECK_SPEC = importlib.util.spec_from_file_location(
    "coding_agents_check_diff_whitespace", ROOT / "scripts" / "check-diff-whitespace.py"
)
if DIFF_CHECK_SPEC is None or DIFF_CHECK_SPEC.loader is None:
    raise RuntimeError("Could not load diff-check tooling")
DIFF_CHECK = importlib.util.module_from_spec(DIFF_CHECK_SPEC)
DIFF_CHECK_SPEC.loader.exec_module(DIFF_CHECK)


def fast_validate(root, tracked_files=None):
    """TEST-ONLY fast path: validator without generated-package rebuilds.

    Structural package checks still run; only the rebuild comparisons are
    skipped. Package integration tests must keep the default enabled checks.
    """

    return VALIDATOR.validate(
        root,
        tracked_files=[] if tracked_files is None else tracked_files,
        check_generated_packages=False,
    )


def fast_inventory(root):
    """TEST-ONLY fast path: inventory without generated-package rebuilds."""

    return collect_inventory(root, check_generated_packages=False)


def fast_generated(root, check=True):
    """TEST-ONLY fast path: inventory generation without package rebuilds."""

    return GENERATOR.generate_inventory(root, check=check, check_generated_packages=False)


EXPECTED_SKILLS = {
    "anti-slop",
    "browser-proof",
    "context-first",
    "diff-judge",
    "improved-design",
    "live-research",
    "repo-xray",
    "root-cause-debugging",
    "system-designer",
    "test-writer",
    "verification-gate",
    "action-mode",
    "skill-supply-audit",
    "spec-trace",
    "repo-instructions",
    "ci-trust-review",
    "dependency-risk",
    "session-checkpoint",
    "patch-proof",
    "public-release-audit",
}


class RepositoryInventoryTests(unittest.TestCase):
    def make_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        fixture = Path(temporary.name) / "repo"
        shutil.copytree(
            ROOT,
            fixture,
            ignore=shutil.ignore_patterns(".git", ".artifacts", "__pycache__", "*.pyc"),
        )
        return temporary, fixture

    def symlink_or_skip(self, link: Path, target: Path, *, target_is_directory: bool) -> None:
        try:
            link.symlink_to(target, target_is_directory=target_is_directory)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink creation is unavailable or denied: {exc}")

    def snapshot_package(self, output: Path) -> dict[str, bytes]:
        return {
            path.relative_to(output).as_posix(): b"" if path.is_dir() else path.read_bytes()
            for path in output.rglob("*")
        }

    def enable_work_mode_adaptation(self, fixture: Path, name: str = "browser-proof") -> Path:
        manifest_path = fixture / "plugins/coding-workflows/work-mode/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(item for item in manifest["skills"] if item["name"] == name)
        entry["work_mode"]["adaptation"] = "surface-adapted"
        entry["work_mode"]["adaptation_source"] = f"plugins/coding-workflows/work-mode/adaptations/{name}"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        overlay = fixture / "plugins/coding-workflows/work-mode/adaptations" / name
        overlay.mkdir(parents=True)
        source = fixture / "plugins/coding-workflows/skills" / name / "SKILL.md"
        text = source.read_text(encoding="utf-8")
        text = text.replace("# Browser Proof", "# Browser Proof\n\nWork Mode overlay.", 1)
        overlay.joinpath("SKILL.md").write_text(text, encoding="utf-8", newline="\n")
        return overlay

    def assert_invalid_skill_path(self, value: object) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            shutil.copytree(
                ROOT,
                fixture,
                ignore=shutil.ignore_patterns(".git", ".artifacts", "__pycache__", "*.pyc"),
            )
            manifest_path = fixture / "plugins" / "coding-workflows" / ".codex-plugin" / "plugin.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["skills"] = value
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "skills path"):
                fast_inventory(fixture)
            with self.assertRaisesRegex(ValueError, "skills path"):
                fast_generated(fixture, check=True)
            errors = fast_validate(fixture)
            self.assertTrue(any("skills path" in error for error in errors), errors)

    def test_inventory_contains_only_active_capabilities(self) -> None:
        inventory = fast_inventory(ROOT)
        self.assertEqual(["coding-workflows"], [item["name"] for item in inventory["plugins"]])
        self.assertEqual(EXPECTED_SKILLS, {item["name"] for item in inventory["skills"]})
        self.assertEqual("plugins/coding-workflows/skills", inventory["work_mode"]["canonical_source"])
        self.assertEqual(len(EXPECTED_SKILLS), inventory["work_mode"]["skill_count"])
        self.assertIsNotNone(inventory["claude_app"])
        self.assertEqual("plugins/coding-workflows/skills", inventory["claude_app"]["canonical_source"])
        self.assertEqual(len(EXPECTED_SKILLS), inventory["claude_app"]["skill_count"])
        self.assertEqual({"reviewer", "verifier"}, {item["name"] for item in inventory["agents"]})
        self.assertEqual([], inventory["local_mcps"])
        self.assertEqual(12, len(inventory["scripts"]))
        self.assertEqual(
            [
                "docs/tools/context7.md",
                "docs/workflows/codex-task-templates.md",
            ],
            [item["path"] for item in inventory["review_candidates"]],
        )

    def test_review_candidate_paths_exist(self) -> None:
        self.assertGreaterEqual(len(REVIEW_CANDIDATES), 1)
        for path, reason in REVIEW_CANDIDATES:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), path)
                self.assertTrue(reason.strip(), path)

    def test_inventory_render_is_deterministic(self) -> None:
        inventory = fast_inventory(ROOT)
        self.assertEqual(render_inventory(inventory), render_inventory(inventory))
        self.assertIn("| Local MCP servers | 0 |", render_inventory(inventory))
        self.assertIn("## Possible Unused or Optional Material", render_inventory(inventory))
        self.assertIn("## Installation Surfaces", render_inventory(inventory))
        self.assertIn("| Claude Code |", render_inventory(inventory))
        self.assertIn("| Claude app (claude.ai) |", render_inventory(inventory))
        self.assertIn("| Gemini CLI |", render_inventory(inventory))
        self.assertIn("| Kimi Code CLI |", render_inventory(inventory))

    def test_inventory_never_discovers_unowned_mcp_directories(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        rogue = fixture / "mcp-servers" / "rogue"
        rogue.mkdir(parents=True)
        (rogue / "server.txt").write_text("unowned\n", encoding="utf-8")
        inventory = fast_inventory(fixture)
        self.assertEqual([], inventory["local_mcps"])
        self.assertNotIn("rogue", render_inventory(inventory))

    def test_inventory_requires_current_generated_package_outputs(self) -> None:
        # Intentionally slow: real end-to-end collect_inventory() -> generated
        # package currentness for every package family.
        mutations = (
            (
                "missing-work-mode",
                lambda fixture: shutil.rmtree(fixture / "plugins/coding-workflows/work-mode/dist/repo-xray"),
                "Work Mode",
            ),
            (
                "stale-work-mode",
                lambda fixture: (fixture / "plugins/coding-workflows/work-mode/dist/repo-xray/SKILL.md").write_text(
                    (fixture / "plugins/coding-workflows/work-mode/dist/repo-xray/SKILL.md").read_text(encoding="utf-8")
                    + "\ndrift\n",
                    encoding="utf-8",
                ),
                "Work Mode",
            ),
            (
                "stale-claude-app",
                lambda fixture: (fixture / "plugins/coding-workflows/claude-app/dist/repo-xray.zip").write_bytes(
                    b"stale"
                ),
                "Claude app",
            ),
            (
                "stale-agent-skills",
                lambda fixture: (fixture / "plugins/coding-workflows/agent-skills/dist/skills/repo-xray/SKILL.md").write_text(
                    (fixture / "plugins/coding-workflows/agent-skills/dist/skills/repo-xray/SKILL.md").read_text(encoding="utf-8")
                    + "\ndrift\n",
                    encoding="utf-8",
                ),
                "Agent Skills",
            ),
        )
        for label, mutate, expected in mutations:
            with self.subTest(label=label):
                temporary, fixture = self.make_fixture()
                self.addCleanup(temporary.cleanup)
                mutate(fixture)
                with self.assertRaisesRegex(ValueError, expected):
                    collect_inventory(fixture)

    def test_claude_plugin_reuses_canonical_skill_source(self) -> None:
        inventory = fast_inventory(ROOT)
        self.assertIsNotNone(inventory["claude_code"])
        self.assertEqual("plugins/coding-workflows/skills", inventory["claude_code"]["canonical_source"])
        self.assertEqual(len(EXPECTED_SKILLS), inventory["claude_code"]["skill_count"])
        codex_version = next(item["version"] for item in inventory["plugins"] if item["name"] == "coding-workflows")
        self.assertEqual(codex_version, inventory["claude_code"]["version"])
        self.assertTrue(all(agent["claude_subagent"] for agent in inventory["agents"]))

    def test_package_clis_return_concise_errors_without_tracebacks(self) -> None:
        clis = (WORK_MODE_CLI, CLAUDE_APP_CLI, AGENT_SKILLS_CLI)
        for module in clis:
            with self.subTest(module=module.__name__):
                stderr = io.StringIO()
                with mock.patch.object(module, "build_packages", side_effect=ValueError("malformed input")), contextlib.redirect_stderr(stderr):
                    result = module.main([])
                self.assertEqual(1, result)
                self.assertIn("ERROR:", stderr.getvalue())
                self.assertIn("malformed input", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())
                self.assertEqual(1, len(stderr.getvalue().splitlines()))

    def test_agent_skills_cli_reports_stale_output(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(AGENT_SKILLS_CLI, "validate_packages", return_value=[]), mock.patch.object(
            AGENT_SKILLS_CLI, "packages_are_current", return_value=False
        ), contextlib.redirect_stderr(stderr):
            result = AGENT_SKILLS_CLI.main(["--check"])
        self.assertEqual(1, result)
        self.assertIn("Agent Skills, Gemini, and Kimi packages are stale", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_package_currentness_distinguishes_build_failure_from_stale(self) -> None:
        families = (
            ("work-mode", WORK_MODE_CLI, work_mode_packages),
            ("claude-app", CLAUDE_APP_CLI, claude_app_packages),
        )
        for label, cli, module in families:
            with self.subTest(label=label):
                details: dict[str, str] = {}
                with mock.patch.object(module, "build_packages", side_effect=ValueError("injected rebuild failure")):
                    self.assertFalse(module.packages_are_current(ROOT, details=details))
                self.assertEqual("build_failed", details.get("status"))
                self.assertIn("injected rebuild failure", details.get("error", ""))

                stderr = io.StringIO()
                with mock.patch.object(cli, "validate_packages", return_value=[]), mock.patch.object(
                    cli, "packages_are_current", return_value=False
                ), contextlib.redirect_stderr(stderr):
                    # A wrapper that cannot see failure details keeps the stale contract.
                    result = cli.main(["--check"])
                self.assertEqual(1, result)
                self.assertIn("stale", stderr.getvalue())

                stderr = io.StringIO()
                def record_failure(*args, **kwargs) -> bool:
                    kwargs.get("details", {}).update(
                        {"status": "build_failed", "error": "injected rebuild failure"}
                    )
                    return False

                with mock.patch.object(cli, "validate_packages", return_value=[]), mock.patch.object(
                    cli, "packages_are_current", side_effect=record_failure
                ), contextlib.redirect_stderr(stderr):
                    result = cli.main(["--check"])
                self.assertEqual(1, result)
                self.assertIn("packaging failed", stderr.getvalue())
                self.assertIn("injected rebuild failure", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        stale = fixture / "plugins/coding-workflows/work-mode/dist/repo-xray/SKILL.md"
        stale.write_text(stale.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
        details = {}
        self.assertFalse(work_mode_packages.packages_are_current(fixture, details=details))
        self.assertEqual("stale", details.get("status"))
        self.assertNotIn("error", details)

    def test_work_mode_manifest_maps_every_plugin_skill_once(self) -> None:
        path = ROOT / "plugins" / "coding-workflows" / "work-mode" / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(1, manifest["version"])
        self.assertEqual("plugins/coding-workflows/skills", manifest["canonical_source"])
        self.assertEqual(EXPECTED_SKILLS, {entry["name"] for entry in manifest["skills"]})
        for entry in manifest["skills"]:
            name = entry["name"]
            self.assertEqual("coding-workflows", entry["codex"]["plugin"])
            self.assertEqual(f"plugins/coding-workflows/skills/{name}", entry["codex"]["source_path"])
            self.assertEqual(name, entry["work_mode"]["personal_skill"])
            self.assertEqual(f"plugins/coding-workflows/skills/{name}", entry["work_mode"]["generated_from"])
            self.assertEqual(f"plugins/coding-workflows/work-mode/dist/{name}", entry["work_mode"]["package_path"])
            self.assertEqual("shared-core", entry["work_mode"]["adaptation"])
            self.assertEqual("generated-and-validated", entry["work_mode"]["package_state"])

    def test_work_mode_packages_are_self_contained_and_deterministic(self) -> None:
        self.assertEqual([], validate_packages(ROOT))
        self.assertTrue(packages_are_current(ROOT))
        with tempfile.TemporaryDirectory() as temporary:
            generated = build_packages(ROOT, Path(temporary) / "dist")
            self.assertEqual(
                sorted(path.relative_to(generated) for path in generated.rglob("SKILL.md")),
                sorted(
                    Path(name) / "SKILL.md"
                    for name in EXPECTED_SKILLS
                ),
            )

    def test_work_mode_package_determinism_normalizes_text_newlines(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        path = fixture / "plugins/coding-workflows/work-mode/dist/browser-proof/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8", newline="\r\n")
        self.assertTrue(packages_are_current(fixture))

    def test_claude_app_packages_are_self_contained_and_deterministic(self) -> None:
        self.assertEqual([], claude_app_validate_packages(ROOT))
        self.assertTrue(claude_app_packages_are_current(ROOT))
        self.assertEqual(EXPECTED_SKILLS, set(claude_app_discover_canonical_skills(ROOT)))
        dist = ROOT / "plugins" / "coding-workflows" / "claude-app" / "dist"
        self.assertEqual(EXPECTED_SKILLS, {path.stem for path in dist.glob("*.zip")})
        with tempfile.TemporaryDirectory() as temporary:
            generated = claude_app_build_packages(ROOT, Path(temporary) / "dist")
            self.assertEqual(EXPECTED_SKILLS, {path.stem for path in generated.glob("*.zip")})
            for zip_path in generated.glob("*.zip"):
                with zipfile.ZipFile(zip_path) as archive:
                    names = archive.namelist()
                    self.assertEqual({zip_path.stem}, {name.split("/", 1)[0] for name in names})
                    self.assertIn(f"{zip_path.stem}/SKILL.md", names)
                    self.assertTrue(all(info.create_system == 3 for info in archive.infolist()))
                    self.assertFalse(any("agents/openai.yaml" in name for name in names), names)

        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        reference = fixture / "plugins/coding-workflows/references/evidence-contract.md"
        reference.write_text(reference.read_text(encoding="utf-8"), encoding="utf-8", newline="\r\n")
        self.assertTrue(claude_app_packages_are_current(fixture))

    def test_claude_app_manifest_has_no_per_skill_list(self) -> None:
        path = ROOT / "plugins" / "coding-workflows" / "claude-app" / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(1, manifest["version"])
        self.assertEqual("plugins/coding-workflows/skills", manifest["canonical_source"])
        self.assertEqual("plugins/coding-workflows/claude-app/dist", manifest["package_root"])
        self.assertEqual(".zip", manifest["package_suffix"])
        self.assertEqual([], manifest["excluded_skills"])
        self.assertNotIn("skills", manifest)

    def test_claude_app_package_regeneration_detects_staleness(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        stale_path = fixture / "plugins/coding-workflows/claude-app/dist/repo-xray.zip"
        stale_path.write_bytes(b"stale")
        self.assertFalse(claude_app_packages_are_current(fixture))
        claude_app_build_packages(fixture)
        self.assertTrue(claude_app_packages_are_current(fixture))
        self.assertEqual([], claude_app_validate_packages(fixture))

    def test_claude_app_valid_exclusion_updates_packages_and_inventory(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        manifest_path = fixture / "plugins/coding-workflows/claude-app/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["excluded_skills"] = ["repo-xray"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        claude_app_build_packages(fixture)

        self.assertEqual(len(EXPECTED_SKILLS) - 1, len(claude_app_active_skill_names(fixture)))
        self.assertNotIn("repo-xray", claude_app_active_skill_names(fixture))
        self.assertEqual([], claude_app_validate_packages(fixture))
        self.assertTrue(claude_app_packages_are_current(fixture))
        self.assertEqual(len(EXPECTED_SKILLS) - 1, fast_inventory(fixture)["claude_app"]["skill_count"])

    def test_claude_app_rejects_unknown_and_duplicate_exclusions(self) -> None:
        for exclusions, expected in ((["missing-skill"], "unknown skills"), (["repo-xray", "repo-xray"], "unique")):
            with self.subTest(exclusions=exclusions):
                temporary, fixture = self.make_fixture()
                self.addCleanup(temporary.cleanup)
                manifest_path = fixture / "plugins/coding-workflows/claude-app/manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["excluded_skills"] = exclusions
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                errors = claude_app_validate_packages(fixture)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_declared_surface_adaptation_is_exported(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        manifest_path = fixture / "plugins/coding-workflows/work-mode/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(item for item in manifest["skills"] if item["name"] == "browser-proof")
        entry["work_mode"]["adaptation"] = "surface-adapted"
        entry["work_mode"]["adaptation_source"] = "plugins/coding-workflows/work-mode/adaptations/browser-proof"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        overlay = fixture / "plugins/coding-workflows/work-mode/adaptations/browser-proof"
        overlay.mkdir(parents=True)
        source = fixture / "plugins/coding-workflows/skills/browser-proof/SKILL.md"
        overlay_skill = source.read_text(encoding="utf-8").replace("# Browser Proof", "# Browser Proof\n\nWork Mode overlay.", 1)
        overlay_skill = overlay_skill.replace("`../../references/workflow-coordination.md`", "`references/workflow-coordination.md`")
        overlay.joinpath("SKILL.md").write_text(overlay_skill, encoding="utf-8")
        build_packages(fixture)
        self.assertEqual([], validate_packages(fixture))

    def test_work_mode_rejects_nested_overlay_symlinks_before_copying(self) -> None:
        for linked_kind in ("file", "directory"):
            with self.subTest(linked_kind=linked_kind):
                temporary, fixture = self.make_fixture()
                self.addCleanup(temporary.cleanup)
                overlay = self.enable_work_mode_adaptation(fixture)
                output = fixture / "plugins/coding-workflows/work-mode/dist"
                before = self.snapshot_package(output)
                outside = Path(temporary.name) / f"outside-{linked_kind}"
                if linked_kind == "file":
                    outside.write_text("external sentinel", encoding="utf-8")
                else:
                    outside.mkdir()
                    (outside / "sentinel.txt").write_text("external sentinel", encoding="utf-8")
                link = overlay / "nested" / "external-link"
                link.parent.mkdir()
                self.symlink_or_skip(link, outside, target_is_directory=linked_kind == "directory")
                with self.assertRaisesRegex(ValueError, "symlink|reparse"):
                    build_packages(fixture)
                self.assertEqual(before, self.snapshot_package(output))
                self.assertEqual("external sentinel", (outside / "sentinel.txt").read_text(encoding="utf-8") if linked_kind == "directory" else outside.read_text(encoding="utf-8"))

    @unittest.skipUnless(sys.platform == "win32", "Windows overlay junction regression")
    def test_work_mode_rejects_nested_overlay_junction_before_copying(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        overlay = self.enable_work_mode_adaptation(fixture)
        output = fixture / "plugins/coding-workflows/work-mode/dist"
        before = self.snapshot_package(output)
        outside = Path(temporary.name) / "outside-junction"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_text("external sentinel", encoding="utf-8")
        junction = overlay / "nested" / "external-junction"
        junction.parent.mkdir()
        command = f"New-Item -ItemType Junction -Path '{junction}' -Target '{outside}' | Out-Null"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.skipTest(f"Windows junction creation is unavailable: {result.stderr or result.stdout}")
        with self.assertRaisesRegex(ValueError, "junction|reparse|symlink"):
            build_packages(fixture)
        self.assertEqual(before, self.snapshot_package(output))
        self.assertEqual("external sentinel", sentinel.read_text(encoding="utf-8"))

    def test_work_mode_and_claude_app_replacement_failures_preserve_outputs(self) -> None:
        families = (
            ("work-mode", build_packages),
            ("claude-app", claude_app_build_packages),
        )
        for label, builder in families:
            with self.subTest(label=label):
                temporary, fixture = self.make_fixture()
                self.addCleanup(temporary.cleanup)
                extra = fixture / "plugins/coding-workflows/skills/repo-xray/new-support.txt"
                extra.write_text("new canonical content", encoding="utf-8")
                output = fixture / (
                    "plugins/coding-workflows/work-mode/dist"
                    if label == "work-mode"
                    else "plugins/coding-workflows/claude-app/dist"
                )
                before = self.snapshot_package(output)
                original_replace = work_mode_packages.os.replace

                def fail_install(source, destination) -> None:
                    if Path(destination) == output and ".stage-" in Path(source).name:
                        raise OSError("injected package replacement failure")
                    original_replace(source, destination)

                with mock.patch.object(work_mode_packages.os, "replace", side_effect=fail_install):
                    with self.assertRaisesRegex(OSError, "injected package replacement failure"):
                        builder(fixture)
                self.assertEqual(before, self.snapshot_package(output))
                self.assertEqual([], list(output.parent.glob(f".{output.name}.stage-*")))
                self.assertEqual([], list(output.parent.glob(f".{output.name}.backup-*")))

    def test_work_mode_mid_build_failure_preserves_existing_output(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        output = fixture / "plugins/coding-workflows/work-mode/dist"
        before = self.snapshot_package(output)
        original_copytree = work_mode_packages.shutil.copytree

        def fail_mid_render(source, destination, *args, **kwargs):
            if Path(source).name == "browser-proof":
                raise OSError("injected mid-build failure")
            return original_copytree(source, destination, *args, **kwargs)

        with mock.patch.object(work_mode_packages.shutil, "copytree", side_effect=fail_mid_render):
            with self.assertRaisesRegex(OSError, "injected mid-build failure"):
                build_packages(fixture)
        self.assertEqual(before, self.snapshot_package(output))
        self.assertEqual([], list(output.parent.glob(f".{output.name}.stage-*")))

    def test_work_mode_and_claude_app_reject_external_output_symlinks(self) -> None:
        families = (
            ("work-mode", build_packages, "plugins/coding-workflows/work-mode/dist"),
            ("claude-app", claude_app_build_packages, "plugins/coding-workflows/claude-app/dist"),
        )
        for label, builder, relative in families:
            with self.subTest(label=label):
                temporary, fixture = self.make_fixture()
                self.addCleanup(temporary.cleanup)
                output = fixture / relative
                prior = output.with_name(f"{output.name}-prior")
                output.rename(prior)
                before = self.snapshot_package(prior)
                outside = Path(temporary.name) / f"outside-{label}"
                outside.mkdir()
                sentinel = outside / "sentinel.txt"
                sentinel.write_text("external sentinel", encoding="utf-8")
                self.symlink_or_skip(output, outside, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "symlink|reparse|regular directory"):
                    builder(fixture)
                self.assertEqual(before, self.snapshot_package(prior))
                self.assertEqual("external sentinel", sentinel.read_text(encoding="utf-8"))

    def _directory_link_or_skip(self, link: Path, target: Path) -> None:
        """Create a directory link, or skip when unavailable.

        Windows uses an NTFS junction (the reported PKG-B shape, which needs
        no symlink privilege); other platforms use a symlink.
        """

        if sys.platform == "win32":
            command = f"New-Item -ItemType Junction -Path '{link}' -Target '{target}' | Out-Null"
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest(f"Windows junction creation is unavailable: {result.stderr or result.stdout}")
        else:
            self.symlink_or_skip(link, target, target_is_directory=True)

    def _linked_temporary_root(self, temporary: tempfile.TemporaryDirectory[str]) -> Path:
        """Return a temp root reached through a link, or skip when unavailable."""

        parent = Path(temporary.name)
        real = parent / "real-temporary"
        real.mkdir()
        linked = parent / "linked-temporary"
        self._directory_link_or_skip(linked, real)
        return linked

    def test_generated_packages_accept_trusted_linked_temporary_root(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        linked = self._linked_temporary_root(temporary)
        # `tempfile` caches its directory after first use, so environment
        # variables alone would not reach the builders; patch the cache itself.
        with mock.patch.object(tempfile, "tempdir", str(linked)):
            with tempfile.TemporaryDirectory() as probe:
                self.assertTrue(Path(probe).is_relative_to(linked), probe)
            self.assertTrue(packages_are_current(ROOT))
            self.assertTrue(claude_app_packages_are_current(ROOT))
            self.assertTrue(agent_skill_packages_are_current(ROOT))
            current, _ = fast_generated(ROOT, check=True)
            self.assertTrue(current)
        # The destination itself being a link must still be rejected.
        real_destination = Path(temporary.name) / "real-destination"
        real_destination.mkdir()
        direct = linked / "direct-link-destination"
        self._directory_link_or_skip(direct, real_destination)
        with self.assertRaisesRegex(ValueError, "symlink|reparse"):
            work_mode_packages._preflight_output_destination(
                direct,
                repository_root=ROOT,
                protected_roots=(),
            )

    def test_folded_skill_description_is_parsed(self) -> None:
        path = ROOT / "plugins" / "coding-workflows" / "skills" / "system-designer" / "SKILL.md"
        metadata = parse_skill_frontmatter(path)
        self.assertEqual("system-designer", metadata["name"])
        self.assertIn("Design or review a software system", metadata["description"])

    def test_generator_detects_and_repairs_inventory_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            shutil.copytree(
                ROOT,
                fixture,
                ignore=shutil.ignore_patterns(".git", ".artifacts", "__pycache__", "*.pyc"),
            )
            current, _ = fast_generated(fixture, check=True)
            self.assertTrue(current)
            inventory_path = fixture / "docs" / "inventory.md"
            inventory_path.write_text("stale\n", encoding="utf-8")
            current, _ = fast_generated(fixture, check=True)
            self.assertFalse(current)
            fast_generated(fixture, check=False)
            current, _ = fast_generated(fixture, check=True)
            self.assertTrue(current)

    def test_generator_rejects_docs_directory_symlink_outside_fixture(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        outside = Path(temporary.name) / "outside-docs"
        outside.mkdir()
        external_inventory = outside / "inventory.md"
        external_inventory.write_text("external sentinel\n", encoding="utf-8")
        docs = fixture / "docs"
        shutil.rmtree(docs)
        self.symlink_or_skip(docs, outside, target_is_directory=True)
        before = external_inventory.read_text(encoding="utf-8")

        raised = False
        try:
            fast_generated(fixture, check=False)
        except (OSError, ValueError):
            raised = True

        self.assertEqual(before, external_inventory.read_text(encoding="utf-8"))
        self.assertTrue(raised, "generator followed a docs directory symlink outside the fixture")

    def test_generator_rejects_inventory_file_symlink_outside_fixture(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        outside = Path(temporary.name) / "outside-inventory.md"
        outside.write_text("external sentinel\n", encoding="utf-8")
        inventory_path = fixture / "docs" / "inventory.md"
        inventory_path.unlink()
        self.symlink_or_skip(inventory_path, outside, target_is_directory=False)
        before = outside.read_text(encoding="utf-8")

        raised = False
        try:
            fast_generated(fixture, check=False)
        except (OSError, ValueError):
            raised = True

        self.assertEqual(before, outside.read_text(encoding="utf-8"))
        self.assertTrue(raised, "generator followed an inventory-file symlink outside the fixture")

    def test_inventory_rejects_plugin_directory_symlink_outside_fixture(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        outside_plugin = Path(temporary.name) / "outside-plugin"
        shutil.copytree(ROOT / "plugins" / "coding-workflows", outside_plugin)
        plugin_link = fixture / "plugins" / "outside-plugin"
        self.symlink_or_skip(plugin_link, outside_plugin, target_is_directory=True)

        with self.assertRaises((OSError, ValueError)):
            fast_inventory(fixture)

    def test_repository_path_rejects_symlink_loop_without_runtime_error(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        first = fixture / "loop-a"
        second = fixture / "loop-b"
        self.symlink_or_skip(first, second, target_is_directory=False)
        self.symlink_or_skip(second, first, target_is_directory=False)

        with self.assertRaises(ValueError):
            require_repository_path(first, fixture, label="Loop fixture")

    def test_inventory_rejects_malformed_skill_paths(self) -> None:
        with self.subTest(path_type="non-string"):
            self.assert_invalid_skill_path(123)
        with self.subTest(path_type="empty"):
            self.assert_invalid_skill_path("")
        with self.subTest(path_type="absolute"):
            self.assert_invalid_skill_path(str((ROOT / "outside-skills").resolve()))
        with self.subTest(path_type="escaping"):
            self.assert_invalid_skill_path("../outside-skills")
        with self.subTest(path_type="non-normalized"):
            self.assert_invalid_skill_path("./skills/../skills")


class HostToolboxTests(unittest.TestCase):
    def test_default_readiness_profile_matches_repository_policy(self) -> None:
        profile = load_profile(ROOT / "config" / "host-readiness.json")
        self.assertEqual("coding-agents", profile["name"])
        self.assertEqual(
            ["required", "required", "required", "recommended", "optional"],
            [item["severity"] for item in profile["requirements"]],
        )

    def test_mcp_table_parser_keeps_safe_fields_only(self) -> None:
        output = """Name       Command                  Args  Env  Cwd  Status  Auth
node_repl  /runtime/node_repl.exe  -     -    -    enabled Unsupported

Name    Url                                 Bearer Token Env Var  Status   Auth
github  https://api.githubcopilot.com/mcp/  GITHUB_PAT_TOKEN      enabled  Bearer
context7  https://mcp.context7.com/mcp       -                     enabled  Not logged in
"""
        self.assertEqual(
            [
                {
                    "name": "node_repl",
                    "transport": "local",
                    "status": "enabled",
                    "auth_state": "unsupported",
                },
                {
                    "name": "github",
                    "transport": "remote",
                    "status": "enabled",
                    "auth_state": "authenticated",
                },
                {
                    "name": "context7",
                    "transport": "remote",
                    "status": "enabled",
                    "auth_state": "not_authenticated",
                },
            ],
            parse_mcp_list(output),
        )

    def test_mcp_parser_distinguishes_empty_list_from_unparsed_output(self) -> None:
        empty = parse_mcp_output("Name  Command  Args  Env  Cwd  Status  Auth\n")
        self.assertEqual("configured", empty["status"])
        self.assertEqual([], empty["servers"])
        self.assertIn("empty_list", {item["code"] for item in empty["diagnostics"]})

        unparsed = parse_mcp_output("A future Codex format with no known table headers\n")
        self.assertEqual("listed_unparsed", unparsed["status"])
        self.assertEqual([], unparsed["servers"])
        self.assertIn("missing_headers", {item["code"] for item in unparsed["diagnostics"]})

        blank = parse_mcp_output("")
        self.assertEqual("listed_unparsed", blank["status"])
        self.assertIn("empty_output", {item["code"] for item in blank["diagnostics"]})

    def test_mcp_parser_reports_duplicate_and_unrecognized_rows(self) -> None:
        duplicate = """Name  Command  Args  Env  Cwd  Status  Auth
github  first.exe  -  -  -  enabled  Bearer
github  second.exe  -  -  -  enabled  Bearer
"""
        result = parse_mcp_output(duplicate)
        self.assertEqual("listed_unparsed", result["status"])
        self.assertIn("duplicate_name", {item["code"] for item in result["diagnostics"]})
        self.assertEqual(2, len(result["servers"]))

        prefixed = parse_mcp_output(
            "warning: unexpected output\nName  Command  Args  Env  Cwd  Status  Auth\n"
            "github  tool.exe  -  -  -  enabled  Bearer\n"
        )
        self.assertEqual("listed_unparsed", prefixed["status"])
        self.assertIn("unrecognized_row", {item["code"] for item in prefixed["diagnostics"]})

    def test_mcp_reports_reduce_targets_and_auth_to_safe_categories(self) -> None:
        hostile = """Name  Url  Bearer Token Env Var  Status  Auth
github  https://user:target-secret@example.test/mcp  TOKEN_ENV  enabled  Bearer auth-secret
"""
        parsed = parse_mcp_output(hostile)
        encoded = json.dumps(parsed)
        self.assertEqual("configured", parsed["status"])
        self.assertEqual("unknown", parsed["servers"][0]["auth_state"])
        self.assertNotIn("target-secret", encoded)
        self.assertNotIn("auth-secret", encoded)
        self.assertNotIn("TOKEN_ENV", encoded)
        self.assertNotIn("target", parsed["servers"][0])

        with tempfile.TemporaryDirectory() as temporary:
            stream = io.StringIO()
            plugin_output = json.dumps({"installed": []})
            with mock.patch(
                "host_toolbox._command_result", side_effect=[(plugin_output, None), (hostile, None)]
            ), contextlib.redirect_stdout(stream):
                result = host_toolbox_main(["--codex-home", temporary])
        self.assertEqual(0, result)
        self.assertIn("unknown", stream.getvalue())
        self.assertNotIn("target-secret", stream.getvalue())
        self.assertNotIn("auth-secret", stream.getvalue())

    def test_unknown_auth_label_cannot_satisfy_required_authentication(self) -> None:
        for label in ("Bearer", "Bearer token", "OAuth"):
            with self.subTest(known_authenticated_label=label):
                known = parse_mcp_output(
                    "Name  Url  Bearer Token Env Var  Status  Auth\n"
                    f"github  https://example.invalid/mcp  -  enabled  {label}\n"
                )
                self.assertEqual("authenticated", known["servers"][0]["auth_state"])

        failed_auth = """Name  Url  Bearer Token Env Var  Status  Auth
github  https://example.invalid/mcp  -  enabled  Authentication failed
"""
        mcp = parse_mcp_output(failed_auth)
        self.assertEqual("configured", mcp["status"])
        self.assertEqual("unknown", mcp["servers"][0]["auth_state"])

        report = {
            "codex": {
                "plugins": {"status": "configured", "plugins": []},
                "mcp": mcp,
            },
            "luna": {"workers": {}},
        }
        profile = {
            "name": "required-auth",
            "requirements": [
                {
                    "kind": "mcp",
                    "name": "github",
                    "severity": "required",
                    "enabled": True,
                    "authenticated": True,
                }
            ],
        }
        evaluated = evaluate_readiness(report, profile)
        self.assertEqual("invalid", evaluated["requirements"][0]["status"])
        self.assertEqual("not_ready", evaluated["readiness"]["status"])

    def test_luna_contracts_are_verified_without_returning_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            agents = home / "agents"
            agents.mkdir()
            for filename, name, effort in (
                ("luna-worker.toml", "luna_worker", "high"),
                ("luna-max-worker.toml", "luna_max_worker", "max"),
            ):
                (agents / filename).write_text(
                    "\n".join(
                        [
                            f'name = "{name}"',
                            'model = "gpt-5.6-luna"',
                            f'model_reasoning_effort = "{effort}"',
                            'sandbox_mode = "workspace-write"',
                            'developer_instructions = "bounded work"',
                        ]
                    ),
                    encoding="utf-8",
                )
            result = inspect_luna(home)
            self.assertEqual("verified", result["workers"]["luna_worker"]["status"])
            self.assertEqual("verified", result["workers"]["luna_max_worker"]["status"])
            self.assertNotIn("developer_instructions", json.dumps(result))

            (agents / "luna-worker.toml").write_text(
                'name = "luna_worker"\nmodel = "wrong-model"\n', encoding="utf-8"
            )
            result = inspect_luna(home)
            self.assertEqual("invalid", result["workers"]["luna_worker"]["status"])
            self.assertEqual("not_checked", result["workers"]["luna_worker"]["evidence"])

    def test_malformed_plugin_json_is_invalid_without_raw_output(self) -> None:
        empty_mcp = "Name  Command  Args  Env  Cwd  Status  Auth\n"
        with mock.patch(
            "host_toolbox._command_result", side_effect=[("{secret-token", None), (empty_mcp, None)]
        ):
            result = inspect_codex("codex")
        encoded = json.dumps(result)
        self.assertEqual("invalid", result["plugins"]["status"])
        self.assertEqual("malformed_output", result["plugins"]["failure_code"])
        self.assertNotIn("secret-token", encoded)

    def test_report_handles_missing_host_command_and_workers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = build_report(codex_command="definitely-not-a-codex", codex_home=Path(temporary))
        self.assertEqual("not checked", report["codex"]["plugins"]["status"])
        self.assertEqual("missing", report["luna"]["workers"]["luna_worker"]["status"])
        self.assertNotIn("GITHUB_PAT_TOKEN", json.dumps(report))

    def test_report_schema_v3_never_claims_callability_or_leaks_sensitive_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = build_report(codex_command="definitely-not-a-codex", codex_home=Path(temporary))
        encoded = json.dumps(report)
        self.assertEqual(3, report["schema_version"])
        self.assertEqual("not_evaluated", report["readiness"]["status"])
        self.assertEqual([], report["requirements"])
        self.assertNotIn("callable", encoded.casefold())
        self.assertNotIn("developer_instructions", encoded)
        self.assertNotIn("raw_stderr", encoded)

    def test_cli_reports_missing_host_state_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                result = host_toolbox_main(
                    ["--codex-command", "definitely-not-a-codex", "--codex-home", temporary]
                )
        self.assertEqual(0, result)
        self.assertIn("Host toolbox report", stream.getvalue())
        self.assertIn("luna_worker: missing", stream.getvalue())

    def test_profile_validation_and_readiness_aggregation(self) -> None:
        profile_data = {
            "schema_version": 1,
            "name": "fixture",
            "requirements": [
                {
                    "kind": "plugin",
                    "name": "coding-workflows",
                    "severity": "required",
                    "enabled": True,
                    "match_repository_version": True,
                },
                {"kind": "worker", "name": "luna_worker", "severity": "required"},
                {
                    "kind": "mcp",
                    "name": "github",
                    "severity": "recommended",
                    "enabled": True,
                    "authenticated": True,
                },
                {
                    "kind": "mcp",
                    "name": "context7",
                    "severity": "optional",
                    "enabled": True,
                    "authenticated": True,
                },
            ],
        }
        report = {
            "codex": {
                "plugins": {
                    "status": "configured",
                    "plugins": [
                        {
                            "name": "coding-workflows",
                            "version": "1.5.0",
                            "installed": True,
                            "enabled": True,
                        }
                    ],
                },
                "mcp": {"status": "configured", "servers": []},
            },
            "luna": {"workers": {"luna_worker": {"status": "verified"}}},
        }
        evaluated = evaluate_readiness(report, profile_data, repository_root=ROOT)
        self.assertEqual("degraded", evaluated["readiness"]["status"])
        self.assertEqual(
            ["satisfied", "satisfied", "missing", "missing"],
            [item["status"] for item in evaluated["requirements"]],
        )
        self.assertFalse(evaluated["readiness"]["required_failure"])

        report["codex"]["plugins"]["plugins"][0]["enabled"] = False
        evaluated = evaluate_readiness(report, profile_data, repository_root=ROOT)
        plugin_result = evaluated["requirements"][0]
        self.assertEqual("invalid", plugin_result["status"])
        self.assertEqual("not_ready", evaluated["readiness"]["status"])

        report["codex"]["plugins"]["plugins"] = []
        evaluated = evaluate_readiness(report, profile_data, repository_root=ROOT)
        self.assertEqual("missing", evaluated["requirements"][0]["status"])

        report["codex"]["plugins"]["plugins"] = [
            {
                "name": "coding-workflows",
                "version": "0.0.0",
                "installed": True,
                "enabled": True,
            }
        ]
        evaluated = evaluate_readiness(report, profile_data, repository_root=ROOT)
        self.assertEqual("not_ready", evaluated["readiness"]["status"])
        self.assertTrue(evaluated["readiness"]["required_failure"])

    def test_plugin_readiness_requires_exact_identity_and_rejects_ambiguity(self) -> None:
        profile = {
            "schema_version": 1,
            "name": "exact-plugin",
            "requirements": [
                {
                    "kind": "plugin",
                    "name": "coding-workflows",
                    "severity": "required",
                    "enabled": True,
                    "match_repository_version": True,
                    "plugin_id": "coding-workflows@coding-agents",
                    "marketplace_name": "coding-agents",
                }
            ],
        }
        exact_plugin = {
            "name": "coding-workflows",
            "plugin_id": "coding-workflows@coding-agents",
            "marketplace_name": "coding-agents",
            "version": "1.5.0",
            "installed": True,
            "enabled": True,
        }
        exact_report = {
            "codex": {"plugins": {"status": "configured", "plugins": [exact_plugin]}, "mcp": {}},
            "luna": {"workers": {}},
        }
        evaluated = evaluate_readiness(exact_report, profile, repository_root=ROOT)
        self.assertEqual("satisfied", evaluated["requirements"][0]["status"])

        foreign_plugin = dict(exact_plugin, plugin_id="coding-workflows@other-marketplace")
        foreign_report = {
            "codex": {"plugins": {"status": "configured", "plugins": [foreign_plugin]}, "mcp": {}},
            "luna": {"workers": {}},
        }
        evaluated = evaluate_readiness(foreign_report, profile, repository_root=ROOT)
        self.assertEqual("invalid", evaluated["requirements"][0]["status"])

        ambiguous_report = {
            "codex": {
                "plugins": {"status": "configured", "plugins": [exact_plugin, dict(exact_plugin)]},
                "mcp": {},
            },
            "luna": {"workers": {}},
        }
        evaluated = evaluate_readiness(ambiguous_report, profile, repository_root=ROOT)
        self.assertEqual("invalid", evaluated["requirements"][0]["status"])

    def test_profile_rejects_unknown_fields_and_duplicate_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile_path = Path(temporary) / "profile.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "bad",
                        "requirements": [
                            {"kind": "worker", "name": "luna_worker", "severity": "required"},
                            {"kind": "worker", "name": "luna_worker", "severity": "optional"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate requirement"):
                load_profile(profile_path)

            profile_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "bad",
                        "requirements": [
                            {
                                "kind": "worker",
                                "name": "luna_worker",
                                "severity": "required",
                                "unexpected": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unsupported fields"):
                load_profile(profile_path)

    def test_check_mode_exit_codes_and_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            profile_path = Path(temporary) / "profile.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "required-worker",
                        "requirements": [
                            {"kind": "worker", "name": "luna_worker", "severity": "required"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                result = host_toolbox_main(
                    [
                        "--check",
                        "--json",
                        "--profile",
                        str(profile_path),
                        "--codex-command",
                        "definitely-not-a-codex",
                        "--codex-home",
                        str(home),
                    ]
                )
            payload = json.loads(stream.getvalue())
            self.assertEqual(1, result)
            self.assertEqual("not_ready", payload["readiness"]["status"])

            error_stream = io.StringIO()
            invalid_path = Path(temporary) / "invalid.json"
            invalid_path.write_text("not json", encoding="utf-8")
            with contextlib.redirect_stderr(error_stream):
                result = host_toolbox_main(["--check", "--profile", str(invalid_path)])
            self.assertEqual(2, result)
            self.assertIn("invalid readiness profile", error_stream.getvalue())

    def test_check_mode_degraded_is_exit_zero_and_human_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            agents = home / "agents"
            agents.mkdir(parents=True)
            (agents / "luna-worker.toml").write_text(
                "\n".join(
                    [
                        'name = "luna_worker"',
                        'model = "gpt-5.6-luna"',
                        'model_reasoning_effort = "high"',
                        'sandbox_mode = "workspace-write"',
                        'developer_instructions = "bounded work"',
                    ]
                ),
                encoding="utf-8",
            )
            profile_path = Path(temporary) / "profile.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "degraded",
                        "requirements": [
                            {"kind": "worker", "name": "luna_worker", "severity": "required"},
                            {
                                "kind": "mcp",
                                "name": "github",
                                "severity": "recommended",
                                "enabled": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                result = host_toolbox_main(
                    [
                        "--check",
                        "--profile",
                        str(profile_path),
                        "--codex-command",
                        "definitely-not-a-codex",
                        "--codex-home",
                        str(home),
                    ]
                )
        self.assertEqual(0, result)
        self.assertIn("Readiness: degraded", stream.getvalue())
        self.assertIn("external tool callability was not tested", stream.getvalue())


class RoutingEvaluationTests(unittest.TestCase):
    def test_golden_set_has_valid_unique_cases(self) -> None:
        data = load_eval_data()
        self.assertEqual([], validate_eval_data(data, EXPECTED_SKILLS))
        cases = select_cases(data)
        self.assertEqual(171, len(cases))
        self.assertEqual(171, len({case["id"] for case in cases}))

    def test_routing_case_fields_are_closed(self) -> None:
        data = load_eval_data()
        modified = {
            "version": 2,
            "skills": [
                {**skill, "cases": [dict(case, unexpected_field=True) for case in skill["cases"]]}
                for skill in data["skills"]
                if skill["name"] == "context-first"
            ],
        }
        errors = validate_eval_data(modified, {"context-first"})
        self.assertTrue(any("unsupported fields" in error for error in errors), errors)

    def test_case_selection_filters_by_skill_and_id(self) -> None:
        data = load_eval_data()
        selected = select_cases(data, skills={"repo-xray"})
        self.assertEqual(9, len(selected))
        selected = select_cases(data, case_ids={"repo-xray-edge-1"})
        self.assertEqual(["repo-xray-edge-1"], [case["id"] for case in selected])

    def test_plugin_readiness_rejects_non_object_json_shapes(self) -> None:
        for payload in ([], {"installed": [[]]}):
            with self.subTest(payload=payload):
                completed = mock.Mock(returncode=0, stdout=json.dumps(payload), stderr="")
                with mock.patch("routing_evals.shutil.which", return_value="codex.exe"), mock.patch(
                    "routing_evals.subprocess.run", return_value=completed
                ):
                    ready, message = plugin_is_ready("codex")
                self.assertFalse(ready)
                self.assertIsInstance(message, str)
                self.assertTrue(message)
                self.assertNotIn("AttributeError", message)

    def routing_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        fixture = Path(temporary.name) / "repo"
        marketplace = fixture / ".agents" / "plugins"
        marketplace.mkdir(parents=True)
        marketplace.joinpath("marketplace.json").write_text(
            json.dumps(
                {
                    "name": "coding-agents",
                    "plugins": [
                        {
                            "name": "coding-workflows",
                            "source": {"source": "local", "path": "./plugins/coding-workflows"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        manifest = fixture / "plugins" / "coding-workflows" / ".codex-plugin"
        manifest.mkdir(parents=True)
        manifest.joinpath("plugin.json").write_text(
            json.dumps({"name": "coding-workflows", "version": "1.4.0"}), encoding="utf-8"
        )
        return temporary, fixture

    def routing_preflight(self, fixture: Path, entry_changes: dict[str, object] | None = None, **overrides: object) -> tuple[bool, str, dict[str, str] | None]:
        entry = {
            "pluginId": "coding-workflows@coding-agents",
            "name": "coding-workflows",
            "marketplaceName": "coding-agents",
            "version": "1.4.0",
            "installed": True,
            "enabled": True,
            "source": {"source": "local", "path": "./plugins/coding-workflows"},
        }
        if entry_changes:
            entry.update(entry_changes)
        payload = {"installed": [entry], "available": []}
        for key, value in overrides.items():
            if key == "without":
                payload.pop(value, None)
            elif key == "duplicate":
                payload["installed"].append(dict(entry))
            elif key == "repeat_in_available":
                if value:
                    payload["available"].append(dict(entry))
            else:
                payload[key] = value
        completed = mock.Mock(returncode=0, stdout=json.dumps(payload), stderr="")
        with mock.patch("routing_evals.shutil.which", return_value="codex"), mock.patch(
            "routing_evals.subprocess.run", return_value=completed
        ):
            ready, message, canonical, observed = _plugin_preflight("codex", repository_root=fixture)
        self.assertIsNotNone(canonical)
        return ready, message, observed

    def test_plugin_preflight_requires_exact_codex_identity(self) -> None:
        temporary, fixture = self.routing_fixture()
        self.addCleanup(temporary.cleanup)
        ready, message, observed = self.routing_preflight(fixture)
        self.assertTrue(ready, message)
        self.assertEqual("coding-workflows@coding-agents", observed["plugin_id"])
        self.assertEqual("canonical_plugin_path", observed["source_evidence"])

        temporary, fixture = self.routing_fixture()
        self.addCleanup(temporary.cleanup)
        ready, _, _ = self.routing_preflight(
            fixture,
            None,
            without="available",
        )
        self.assertFalse(ready)

        cases = (
            ({"marketplaceName": "other-marketplace"}, "marketplace_mismatch"),
            ({"version": "0.0.0"}, "plugin_version_mismatch"),
            ({"pluginId": "coding-workflows@other-marketplace"}, "plugin_id_mismatch"),
            ({"source": {"source": "local", "path": "./elsewhere"}}, "marketplace_source_missing"),
        )
        for changes, code in cases:
            with self.subTest(code=code):
                temporary, fixture = self.routing_fixture()
                self.addCleanup(temporary.cleanup)
                ready, message, _ = self.routing_preflight(fixture, changes)
                self.assertFalse(ready)
                self.assertIn(code, message)

        with self.subTest(code="plugin_identity_ambiguous"):
            temporary, fixture = self.routing_fixture()
            self.addCleanup(temporary.cleanup)
            ready, message, _ = self.routing_preflight(fixture, None, duplicate=True)
            self.assertFalse(ready)
            self.assertIn("plugin_identity_ambiguous", message)

    def test_plugin_preflight_fails_closed_when_available_repeats_installed_identity(self) -> None:
        # The live Codex `available` list schema is unverified repository
        # evidence, so a matching entry there must fail closed rather than
        # authorize a model-backed run.
        temporary, fixture = self.routing_fixture()
        self.addCleanup(temporary.cleanup)
        ready, message, _ = self.routing_preflight(fixture, None, repeat_in_available=True)
        self.assertFalse(ready)
        self.assertIn("plugin_identity_ambiguous", message)

    def test_routing_reports_refuse_sensitive_model_output(self) -> None:
        secret = "gh" + "p_" + ("sensitivecanary" + "0123456789")
        private_path = "/home/" + "report-probe-user" + "/private/output.json"
        sensitive_response = {
            "case_id": "context-first-direct-1",
            "applied_skill": "context-first",
            "boundary_observed": True,
            "evidence": f"contact report-probe-user@example.invalid; reviewed {private_path}",
            "response": f"the failing credential was {secret}",
        }
        self.assertTrue(_report_contains_sensitive_data({"results": [{"observed": sensitive_response}]}))
        self.assertFalse(
            _report_contains_sensitive_data(
                {
                    "results": [
                        {
                            "observed": {
                                "case_id": "context-first-direct-1",
                                "applied_skill": "context-first",
                                "boundary_observed": True,
                                "evidence": "reviewed the repository diff",
                                "response": "completed",
                            }
                        }
                    ]
                }
            )
        )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "refused-report.json"
            completed_case = {
                "case": {"id": "context-first-direct-1", "prompt": "benign fixture prompt"},
                "infrastructure_status": "completed",
                "elapsed_seconds": 1.0,
                "observed": sensitive_response,
                "declared_skill_match": True,
                "review_status": "unreviewed",
            }
            def fixture_preflight(command: str, details: dict[str, object] | None = None) -> tuple[bool, str]:
                identity = {
                    "plugin_id": "coding-workflows@coding-agents",
                    "name": "coding-workflows",
                    "marketplace_name": "coding-agents",
                    "version": "1.4.0",
                    "source": "./plugins/coding-workflows",
                }
                if details is not None:
                    details.update({"canonical": identity, "observed": dict(identity)})
                return True, "fixture preflight"

            with mock.patch("routing_evals.plugin_is_ready", side_effect=fixture_preflight), mock.patch(
                "routing_evals.run_case", return_value=completed_case
            ):
                result = routing_main(
                    [
                        "--run",
                        "--acknowledge-cost",
                        "--case",
                        "context-first-direct-1",
                        "--output",
                        str(output),
                    ]
                )
        self.assertEqual(2, result)
        self.assertFalse(output.exists())

    def test_routing_provenance_records_safe_requested_run_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            identity = {
                "plugin_id": "coding-workflows@coding-agents",
                "name": "coding-workflows",
                "marketplace_name": "coding-agents",
                "version": "1.4.0",
                "source": "./plugins/coding-workflows",
                "source_evidence": "canonical_plugin_path",
            }
            provenance = build_provenance(
                [{"id": "context-first-direct-1"}],
                requested_model="fixture-model",
                canonical_plugin=identity,
                observed_plugin=dict(identity),
                repository_root=Path(temporary),
            )
        self.assertEqual(1, provenance["case_set"]["count"])
        self.assertEqual(64, len(provenance["case_set"]["hash"]))
        self.assertEqual("coding-workflows@coding-agents", provenance["plugin"]["observed"]["plugin_id"])
        self.assertEqual("fixture-model", provenance["model"]["requested"])
        self.assertIsNone(provenance["model"]["resolved"])
        self.assertEqual("not_exposed", provenance["model"]["resolution"])

    def test_run_case_rejects_invalid_structured_response_shapes(self) -> None:
        case = {"id": "test-case", "prompt": "test prompt", "expected_skill": None}
        valid_fields = {
            "case_id": "test-case",
            "applied_skill": None,
            "boundary_observed": True,
            "evidence": "evidence",
            "response": "response",
        }
        payloads = {
            "wrong top-level shape": [],
            "missing required fields": {},
            "missing applied skill": {key: value for key, value in valid_fields.items() if key != "applied_skill"},
            "mistyped required field": {**valid_fields, "boundary_observed": "yes"},
            "case id mismatch": {**valid_fields, "case_id": "other-case"},
            "unexpected field": {**valid_fields, "unexpected": True},
        }

        for label, payload in payloads.items():
            with self.subTest(response_shape=label):
                def write_response(command: list[str], **_: object) -> mock.Mock:
                    response_path = Path(command[command.index("--output-last-message") + 1])
                    response_path.write_text(json.dumps(payload), encoding="utf-8")
                    return mock.Mock(returncode=0, stderr="")

                with mock.patch("routing_evals.subprocess.run", side_effect=write_response):
                    result = run_case(
                        case,
                        codex_command="codex",
                        model=None,
                        timeout_seconds=1,
                    )
                self.assertEqual("failed", result["infrastructure_status"])

    def test_dry_run_prints_cases_without_writing_report(self) -> None:
        from routing_evals import main

        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            result = main(["--case", "context-first-direct-1"])
        self.assertEqual(0, result)
        self.assertIn("Dry run: 1 case(s); no model calls or files written.", stream.getvalue())

    def test_overlap_cases_encode_precedence_and_negative_triggers(self) -> None:
        data = load_eval_data()
        cases = {case["id"]: case for case in select_cases(data)}
        self.assertIsNone(cases["context-first-edge-1"]["expected_skill"])
        self.assertIsNone(cases["test-writer-negative-1"]["expected_skill"])
        self.assertIsNone(cases["root-cause-debugging-negative-1"]["expected_skill"])
        self.assertIn("test-writer", cases["root-cause-debugging-negative-3"]["expected_behavior"])
        self.assertIn("read-only", cases["root-cause-debugging-edge-1"]["expected_behavior"])
        self.assertIn("committing, or pushing", cases["root-cause-debugging-edge-1"]["expected_behavior"])

    def test_unknown_expected_skill_is_rejected(self) -> None:
        data = load_eval_data()
        next(
            case
            for entry in data["skills"]
            for case in entry["cases"]
            if case["id"] == "context-first-edge-1"
        )["expected_skill"] = "not-a-declared-skill"
        for skill_names in (None, EXPECTED_SKILLS):
            with self.subTest(skill_names_supplied=skill_names is not None):
                errors = validate_eval_data(data, skill_names)
                self.assertTrue(any("unknown expected_skill" in error for error in errors), errors)

    def test_cross_skill_edge_expectation_is_allowed(self) -> None:
        data = load_eval_data()
        next(
            case
            for entry in data["skills"]
            for case in entry["cases"]
            if case["id"] == "context-first-edge-1"
        )["expected_skill"] = "repo-xray"
        self.assertEqual([], validate_eval_data(data))
        self.assertEqual([], validate_eval_data(data, EXPECTED_SKILLS))

    def test_coordination_contract_covers_authority_handoffs_and_ceremony(self) -> None:
        text = (
            ROOT
            / "plugins"
            / "coding-workflows"
            / "references"
            / "workflow-coordination.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for required in (
            "## Phase ownership",
            "## Precedence and composition",
            "## Execution and authority",
            "## Stop and completion conditions",
            "Reviewers and verifiers remain read-only",
            "Commit, push, merge, publish, deploy",
            "Do not trigger",
            "map each acceptance claim to fresh direct evidence",
        ):
            self.assertIn(required, normalized)

    def test_plugin_does_not_vendor_distinctive_superpowers_prose(self) -> None:
        plugin_root = ROOT / "plugins" / "coding-workflows"
        text = "\n".join(path.read_text(encoding="utf-8") for path in plugin_root.rglob("*.md"))
        for copied_phrase in (
            "NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE",
            "NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST",
            "You do not have a choice. You must use it.",
            "enthusiastic junior engineer with poor taste",
        ):
            self.assertNotIn(copied_phrase, text)


class RepositoryValidationTests(unittest.TestCase):
    def make_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        fixture = Path(temporary.name) / "repo"
        shutil.copytree(
            ROOT,
            fixture,
            ignore=shutil.ignore_patterns(".git", ".artifacts", "__pycache__", "*.pyc"),
        )
        return temporary, fixture

    def snapshot_package(self, output: Path) -> dict[str, bytes]:
        return {
            path.relative_to(output).as_posix(): path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
        }

    def assert_fixture_error(self, mutate, expected: str, tracked_files: list[str] | None = None) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        mutate(fixture)
        errors = fast_validate(fixture, tracked_files)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_clean_fixture_passes_without_git_metadata(self) -> None:
        # Intentionally slow: real end-to-end validate() -> package validation/currentness.
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        self.assertEqual([], VALIDATOR.validate(fixture, tracked_files=[]))

    def test_host_support_package_version_matches_canonical_plugin(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        matrix = fixture / "docs" / "host-support.md"
        text = matrix.read_text(encoding="utf-8").replace(
            "**Package version:** `1.5.0`", "**Package version:** `9.9.9`", 1
        )
        matrix.write_text(text, encoding="utf-8")
        errors = fast_validate(fixture)
        self.assertTrue(any("Host support matrix package version must match" in error for error in errors), errors)

    def test_rejects_malformed_marketplace(self) -> None:
        self.assert_fixture_error(
            lambda fixture: (fixture / ".agents" / "plugins" / "marketplace.json").write_text("{", encoding="utf-8"),
            "Invalid marketplace",
        )

    def test_rejects_non_object_marketplace_payloads_without_attribute_error(self) -> None:
        for payload in ([], None, "not an object"):
            with self.subTest(payload_type=type(payload).__name__):
                temporary, fixture = self.make_fixture()
                self.addCleanup(temporary.cleanup)
                marketplace_path = fixture / ".agents" / "plugins" / "marketplace.json"
                marketplace_path.write_text(json.dumps(payload), encoding="utf-8")
                try:
                    errors = fast_validate(fixture)
                except Exception as exc:  # pragma: no cover - documents the regression
                    self.fail(f"non-object marketplace payload raised {type(exc).__name__}: {exc}")
                self.assertIsInstance(errors, list)
                self.assertTrue(any("marketplace" in error.casefold() for error in errors), errors)

    def test_rejects_non_object_plugin_manifests_without_attribute_error(self) -> None:
        for payload in ([], None, "not an object"):
            with self.subTest(payload_type=type(payload).__name__):
                temporary, fixture = self.make_fixture()
                self.addCleanup(temporary.cleanup)
                manifest_path = fixture / "plugins" / "coding-workflows" / ".codex-plugin" / "plugin.json"
                manifest_path.write_text(json.dumps(payload), encoding="utf-8")
                try:
                    errors = fast_validate(fixture)
                except Exception as exc:  # pragma: no cover - documents the regression
                    self.fail(f"non-object plugin manifest raised {type(exc).__name__}: {exc}")
                self.assertIsInstance(errors, list)
                self.assertTrue(any("plugin manifest" in error.casefold() for error in errors), errors)

    def test_rejects_marketplace_source_that_escapes_plugin_root(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / ".agents" / "plugins" / "marketplace.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["plugins"][0]["source"]["path"] = "./plugins/../../outside"
            path.write_text(json.dumps(data), encoding="utf-8")

        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        mutate(fixture)
        errors = fast_validate(fixture)
        self.assertTrue(
            any(
                "source" in error.casefold()
                and any(marker in error.casefold() for marker in ("escape", "mismatch", "repo-local"))
                for error in errors
            ),
            errors,
        )

    def test_rejects_oversized_validation_input(self) -> None:
        def mutate(fixture: Path) -> None:
            (fixture / "docs" / "oversized.md").write_bytes(
                b"x" * (VALIDATOR.MAX_VALIDATED_FILE_BYTES + 1)
            )

        self.assert_fixture_error(mutate, "validation limit")

    def test_rejects_oversized_script_during_inventory_collection(self) -> None:
        def mutate(fixture: Path) -> None:
            (fixture / "scripts" / "oversized.py").write_bytes(
                b"x" * (VALIDATOR.MAX_VALIDATED_FILE_BYTES + 1)
            )

        self.assert_fixture_error(mutate, "validation limit")

    def test_rejects_excess_entries_before_extension_filtering(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        bulk = fixture / "docs" / "bulk"
        bulk.mkdir()
        baseline_entries = sum(1 for _ in fixture.rglob("*"))
        for index in range(4):
            (bulk / f"ignored-{index}.bin").write_bytes(b"x")

        with mock.patch.object(VALIDATOR, "MAX_VALIDATED_ENTRIES", baseline_entries + 3):
            errors = fast_validate(fixture)

        self.assertTrue(any("entry validation limit" in error for error in errors), errors)

    def test_rejects_excess_agent_entries_before_agent_discovery(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_root = fixture / ".codex" / "agents"
        baseline_entries = sum(1 for _ in fixture.rglob("*"))
        for index in range(3):
            (agent_root / f"extra-{index}.toml").write_text("name = 'extra'\n", encoding="utf-8")

        with mock.patch.object(VALIDATOR, "MAX_VALIDATED_ENTRIES", baseline_entries + 2):
            errors = fast_validate(fixture)

        self.assertEqual(
            errors,
            [f"Repository exceeds the {baseline_entries + 2}-entry validation limit."],
        )

    def test_rejects_looped_manifest_skill_path_without_runtime_error(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        plugin = fixture / "plugins" / "coding-workflows"
        first = plugin / "loop-a"
        second = plugin / "loop-b"
        try:
            first.symlink_to(second, target_is_directory=True)
            second.symlink_to(first, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink creation is unavailable or denied: {exc}")
        manifest_path = plugin / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["skills"] = "./loop-a"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        try:
            errors = fast_validate(fixture)
        except RuntimeError as exc:  # pragma: no cover - documents the regression
            self.fail(f"looped skills path raised RuntimeError: {exc}")
        self.assertTrue(any("skills path" in error for error in errors), errors)

    def test_rejects_mismatched_plugin_name(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / ".codex-plugin" / "plugin.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["name"] = "wrong-name"
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "does not match manifest name")

    def test_rejects_invalid_semver(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / ".codex-plugin" / "plugin.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["version"] = "latest"
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "invalid semver")

    def test_rejects_public_listing_metadata_overflow(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / ".codex-plugin" / "plugin.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["interface"]["shortDescription"] = "x" * 31
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "shortDescription exceeds 30 characters")

    def test_rejects_unsupported_plugin_component(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / ".codex-plugin" / "plugin.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["mcpServers"] = "./.mcp.json"
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "unsupported unused component mcpServers")

    def test_rejects_duplicate_routing_case_id(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / "evals" / "trigger-routing.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["skills"][0]["cases"][1]["id"] = data["skills"][0]["cases"][0]["id"]
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "Duplicate routing evaluation case id")

    def test_rejects_work_mode_mapping_that_omits_a_plugin_skill(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / "work-mode" / "manifest.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["skills"].pop()
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "Work Mode/skill mismatch")

    def test_rejects_agent_skill_name_contract_violations(self) -> None:
        path_relative = Path("plugins/coding-workflows/skills/repo-xray/SKILL.md")
        invalid_names = ("Repo-xray", "-repo-xray", "repo-xray-", "repo--xray", "x" * 65)
        for invalid_name in invalid_names:
            with self.subTest(invalid_name=invalid_name):
                def mutate(fixture: Path, invalid_name: str = invalid_name) -> None:
                    path = fixture / path_relative
                    path.write_text(
                        path.read_text(encoding="utf-8").replace("name: repo-xray", f"name: {invalid_name}", 1),
                        encoding="utf-8",
                    )

                self.assert_fixture_error(mutate, "invalid Agent Skills name")

    def test_rejects_agent_skill_description_overflow(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/skills/repo-xray/SKILL.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(re.sub(r"description:.*", "description: " + "x" * 1025, text, count=1), encoding="utf-8")

        self.assert_fixture_error(mutate, "invalid Agent Skills description")

    def test_rejects_work_mode_package_reference_escape_and_missing_file(self) -> None:
        for replacement, expected in (("../../outside.md", "escapes package root"), ("references/missing.md", "reference is missing")):
            with self.subTest(replacement=replacement):
                def mutate(fixture: Path, replacement: str = replacement) -> None:
                    path = fixture / "plugins/coding-workflows/work-mode/dist/context-first/SKILL.md"
                    path.write_text(
                        path.read_text(encoding="utf-8").replace("references/workflow-coordination.md", replacement, 1),
                        encoding="utf-8",
                    )

                self.assert_fixture_error(mutate, expected)

    def test_rejects_work_mode_package_local_machine_path(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/work-mode/dist/anti-slop/SKILL.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nC:" + "\\private\\path\n", encoding="utf-8")

        self.assert_fixture_error(mutate, "contains a local machine path")

    def test_rejects_work_mode_package_secret_material(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/work-mode/dist/anti-slop/SKILL.md"
            token = "ghp_" + "abcdefghijklmnopqrstuvwxyz1234567890"
            path.write_text(path.read_text(encoding="utf-8") + f"\n{token}\n", encoding="utf-8")

        self.assert_fixture_error(mutate, "contains secret material")

    def test_rejects_work_mode_package_symlink_escape(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        outside = Path(temporary.name) / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        link = fixture / "plugins/coding-workflows/work-mode/dist/anti-slop/escaped.md"
        try:
            link.symlink_to(outside)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink creation is unavailable or denied: {exc}")
        errors = fast_validate(fixture)
        self.assertTrue(any("Generated package output" in error and "symlink" in error for error in errors), errors)

    def test_rejects_claude_app_package_set_mismatch(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/claude-app/manifest.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["excluded_skills"] = ["repo-xray"]
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "Claude app package set mismatch")

    def test_rejects_claude_app_package_missing_skill_md(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/claude-app/dist/repo-xray.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("repo-xray/README.md", "no skill file here")

        self.assert_fixture_error(mutate, "is missing repo-xray/SKILL.md")

    def test_rejects_claude_app_package_multiple_top_level_directories(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/claude-app/dist/repo-xray.zip"
            with zipfile.ZipFile(path) as old:
                entries = {name: old.read(name) for name in old.namelist()}
            entries["stray/README.md"] = b"stray file at a second top-level directory"
            with zipfile.ZipFile(path, "w") as new:
                for name, data in entries.items():
                    new.writestr(name, data)

        self.assert_fixture_error(mutate, "must contain exactly one top-level directory")

    def test_rejects_claude_app_package_path_escape(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/claude-app/dist/repo-xray.zip"
            with zipfile.ZipFile(path) as old:
                entries = {name: old.read(name) for name in old.namelist()}
            entries["repo-xray/../escape.md"] = b"escape"
            with zipfile.ZipFile(path, "w") as new:
                for name, data in entries.items():
                    new.writestr(name, data)

        self.assert_fixture_error(mutate, "contains an unsafe path")

    def test_rejects_claude_app_package_codex_only_metadata(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/claude-app/dist/repo-xray.zip"
            with zipfile.ZipFile(path) as old:
                entries = {name: old.read(name) for name in old.namelist()}
            entries["repo-xray/agents/openai.yaml"] = b"interface:\n  display_name: x\n"
            with zipfile.ZipFile(path, "w") as new:
                for name, data in entries.items():
                    new.writestr(name, data)

        self.assert_fixture_error(mutate, "contains excluded content")

    def test_rejects_claude_app_package_reference_escape_and_missing_file(self) -> None:
        for replacement, expected in (
            ("../../outside.md", "escapes package root"),
            ("references/missing.md", "reference is missing"),
        ):
            with self.subTest(replacement=replacement):

                def mutate(fixture: Path, replacement: str = replacement) -> None:
                    path = fixture / "plugins/coding-workflows/claude-app/dist/context-first.zip"
                    with zipfile.ZipFile(path) as old:
                        entries = {name: old.read(name) for name in old.namelist()}
                    skill_text = entries["context-first/SKILL.md"].decode("utf-8")
                    entries["context-first/SKILL.md"] = skill_text.replace(
                        "references/workflow-coordination.md", replacement, 1
                    ).encode("utf-8")
                    with zipfile.ZipFile(path, "w") as new:
                        for name, data in entries.items():
                            new.writestr(name, data)

                self.assert_fixture_error(mutate, expected)

    def test_rejects_claude_app_package_secret_material(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/claude-app/dist/anti-slop.zip"
            with zipfile.ZipFile(path) as old:
                entries = {name: old.read(name) for name in old.namelist()}
            entries["anti-slop/SKILL.md"] += b"\n" + b"ghp_" + b"abcdefghijklmnopqrstuvwxyz1234567890" + b"\n"
            with zipfile.ZipFile(path, "w") as new:
                for name, data in entries.items():
                    new.writestr(name, data)

        self.assert_fixture_error(mutate, "contains secret material")

    def test_rejects_claude_app_package_local_machine_path(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/claude-app/dist/anti-slop.zip"
            with zipfile.ZipFile(path) as old:
                entries = {name: old.read(name) for name in old.namelist()}
            entries["anti-slop/SKILL.md"] += b"\nC:" + b"\\private\\path\n"
            with zipfile.ZipFile(path, "w") as new:
                for name, data in entries.items():
                    new.writestr(name, data)

        self.assert_fixture_error(mutate, "contains a local machine path")

    def test_rejects_claude_app_package_name_mismatch(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins/coding-workflows/claude-app/dist/repo-xray.zip"
            with zipfile.ZipFile(path) as old:
                entries = {name: old.read(name) for name in old.namelist()}
            skill_text = entries["repo-xray/SKILL.md"].decode("utf-8")
            entries["repo-xray/SKILL.md"] = skill_text.replace("name: repo-xray", "name: renamed-skill", 1).encode(
                "utf-8"
            )
            with zipfile.ZipFile(path, "w") as new:
                for name, data in entries.items():
                    new.writestr(name, data)

        self.assert_fixture_error(mutate, "does not match folder")

    def test_claude_zip_metadata_limits_fail_before_member_reads(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        zip_path = fixture / "plugins/coding-workflows/claude-app/dist/repo-xray.zip"
        cases = (
            ("archive-size", {"MAX_ZIP_ARCHIVE_BYTES": 1}, "archive limit"),
            ("member-count", {"MAX_ZIP_MEMBERS": 0}, "member limit"),
            ("member-size", {"MAX_ZIP_MEMBER_BYTES": 1}, "size limit"),
            ("total-size", {"MAX_ZIP_TOTAL_BYTES": 1}, "expanded size limit"),
            ("ratio", {"MAX_ZIP_COMPRESSION_RATIO": 0}, "compression ratio"),
            ("encryption", {}, "encrypted"),
            ("compression", {}, "unsupported compression"),
        )
        with zipfile.ZipFile(zip_path) as archive:
            original_infos = archive.infolist()
        for label, limits, expected in cases:
            with self.subTest(label=label):
                errors: list[str] = []
                patches = [mock.patch.object(claude_app_packages, name, value) for name, value in limits.items()]
                if label == "encryption":
                    infos = [zipfile.ZipInfo(info.filename, info.date_time) for info in original_infos]
                    for source_info, info in zip(original_infos, infos, strict=True):
                        info.external_attr = source_info.external_attr
                        info.compress_type = source_info.compress_type
                        info.file_size = source_info.file_size
                        info.compress_size = source_info.compress_size
                        info.flag_bits = 1
                    patches.append(mock.patch.object(zipfile.ZipFile, "infolist", return_value=infos))
                elif label == "compression":
                    infos = [zipfile.ZipInfo(info.filename, info.date_time) for info in original_infos]
                    for source_info, info in zip(original_infos, infos, strict=True):
                        info.external_attr = source_info.external_attr
                        info.file_size = source_info.file_size
                        info.compress_size = source_info.compress_size
                        info.flag_bits = source_info.flag_bits
                        info.compress_type = zipfile.ZIP_BZIP2
                    patches.append(mock.patch.object(zipfile.ZipFile, "infolist", return_value=infos))
                with contextlib.ExitStack() as stack:
                    for patcher in patches:
                        stack.enter_context(patcher)
                    open_members = stack.enter_context(mock.patch.object(zipfile.ZipFile, "open", side_effect=AssertionError("member read")))
                    _validate_zip_package(zip_path, "repo-xray", errors)
                open_members.assert_not_called()
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_claude_zip_metadata_check_fails_fast_on_member_and_name_bounds(self) -> None:
        def make_info(name: str) -> zipfile.ZipInfo:
            info = zipfile.ZipInfo(name)
            info.file_size = 10
            info.compress_size = 10
            info.compress_type = zipfile.ZIP_STORED
            return info

        class UnreadableInfo:
            """Any per-member access proves the member-count bound did not fail fast."""

            def __getattr__(self, attribute: str):
                raise AssertionError(f"per-member work before the member-count bound: {attribute}")

        over_limit = [UnreadableInfo() for _ in range(claude_app_packages.MAX_ZIP_MEMBERS + 1)]
        errors = claude_app_packages._zip_metadata_errors(over_limit)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("member limit", errors[0])

        at_limit = [make_info(f"skill/nested/deep/file{index:05d}.md") for index in range(claude_app_packages.MAX_ZIP_MEMBERS)]
        self.assertEqual([], claude_app_packages._zip_metadata_errors(at_limit))

        # Prefix collision work is O(depth * length) per name, so over-long or
        # over-deep names must be rejected before any prefix is built.
        long_name = "skill/" + "a" * claude_app_packages.MAX_ZIP_NAME_BYTES
        deep_name = "/".join(["skill", *(["a"] * (claude_app_packages.MAX_ZIP_PATH_DEPTH + 1))])
        for label, name in (("long", long_name), ("deep", deep_name)):
            with self.subTest(label=label):
                errors = claude_app_packages._zip_metadata_errors([make_info("skill/SKILL.md"), make_info(name)])
                self.assertEqual(1, len(errors), errors)
                self.assertIn("path components", errors[0])
        within_bounds = "/".join(["skill", *(["a"] * (claude_app_packages.MAX_ZIP_PATH_DEPTH - 1)), "file.md"])
        self.assertEqual([], claude_app_packages._zip_metadata_errors([make_info(within_bounds)]))

        colliding = [
            make_info("skill"),
            make_info("skill/SKILL.md"),
            make_info("other/SKILL.md"),
            make_info("other/SKILL.md"),
        ]
        errors = claude_app_packages._zip_metadata_errors(colliding)
        self.assertTrue(any("duplicate ZIP entries" in error for error in errors), errors)
        self.assertTrue(
            any("file/directory path collision: 'skill'" in error for error in errors), errors
        )
        self.assertTrue(
            any("file/directory path collision: 'skill/SKILL.md'" in error for error in errors), errors
        )

    def test_rejects_claude_marketplace_missing_plugin_entry(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / ".claude-plugin" / "marketplace.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["plugins"] = []
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "missing the coding-workflows plugin entry")

    def test_rejects_claude_plugin_version_mismatch(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / ".claude-plugin" / "plugin.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["version"] = "0.0.1"
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "Claude plugin manifest version must match")

    def test_rejects_claude_plugin_declared_skills_path(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / ".claude-plugin" / "plugin.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["skills"] = "./skills/"
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(mutate, "must not declare a skills path")

    def test_rejects_claude_subagent_write_tool_grant(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / ".claude" / "agents" / "reviewer.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("tools: Read, Grep, Glob", "tools: Read, Grep, Glob, Edit"),
                encoding="utf-8",
            )

        self.assert_fixture_error(mutate, "must stay read-only")

    def test_rejects_claude_subagent_name_mismatch(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / ".claude" / "agents" / "verifier.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("name: verifier", "name: verifier-renamed", 1),
                encoding="utf-8",
            )

        self.assert_fixture_error(mutate, "does not match name")

    def test_rejects_claude_codex_agent_set_mismatch(self) -> None:
        def mutate(fixture: Path) -> None:
            (fixture / ".claude" / "agents" / "reviewer.md").unlink()

        self.assert_fixture_error(mutate, "Claude/Codex project agent mismatch")

    def _agent_plugins_manifest(self, fixture: Path) -> Path:
        return fixture / "plugins" / "coding-workflows" / "plugin.json"

    def _rewrite_agent_plugins_manifest(self, fixture: Path, mutate_data) -> None:
        path = self._agent_plugins_manifest(fixture)
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate_data(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_claude_marketplace_requires_exact_local_catalog(self) -> None:
        def mutate_marketplace(fixture: Path, action) -> None:
            path = fixture / ".claude-plugin" / "marketplace.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            action(data)
            path.write_text(json.dumps(data), encoding="utf-8")

        def duplicate(data: dict) -> None:
            data["plugins"].append(dict(data["plugins"][0]))

        def unknown(data: dict) -> None:
            data["plugins"].append(
                {"name": "other", "source": "./plugins/coding-workflows", "description": "Other."}
            )

        def external(data: dict) -> None:
            data["plugins"][0]["source"] = "https://example.invalid/coding-workflows"

        def unknown_field(data: dict) -> None:
            data["plugins"][0]["updated"] = "unreviewed"

        cases = (
            (duplicate, "duplicate coding-workflows entries"),
            (unknown, "unknown plugin entry"),
            (external, "source must be ./plugins/coding-workflows"),
            (unknown_field, "unsupported fields"),
        )
        for action, expected in cases:
            with self.subTest(expected=expected):
                self.assert_fixture_error(
                    lambda fixture: mutate_marketplace(fixture, action), expected
                )

    def test_claude_plugin_rejects_non_skills_components(self) -> None:
        def mutate_manifest(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / ".claude-plugin" / "plugin.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["hooks"] = "./hooks/hooks.json"
            path.write_text(json.dumps(data), encoding="utf-8")

        def mutate_path(fixture: Path, relative: str) -> None:
            path = fixture / "plugins" / "coding-workflows" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")

        self.assert_fixture_error(mutate_manifest, "forbidden component fields")
        for relative, expected in (
            ("hooks/hooks.json", "unsupported top-level entries"),
            (".mcp.json", "forbidden component file"),
            ("commands/custom.md", "unsupported top-level entries"),
            ("skills/repo-xray/hooks/payload.sh", "unexpected component path"),
        ):
            with self.subTest(relative=relative):
                self.assert_fixture_error(
                    lambda fixture: mutate_path(fixture, relative), expected
                )

    def test_claude_subagents_require_exact_read_only_allowlist(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / ".claude" / "agents" / "reviewer.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("tools: Read, Grep, Glob", "tools: Read, Grep, Glob, Task"),
                encoding="utf-8",
            )

        self.assert_fixture_error(mutate, "exact Read, Grep, and Glob allowlist")

    def test_project_agents_reject_role_or_authority_drift(self) -> None:
        def mutate_claude(fixture: Path) -> None:
            path = fixture / ".claude" / "agents" / "reviewer.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "Do not edit files, commit, push, publish",
                    "You are authorized to edit files, commit, push, or publish",
                ),
                encoding="utf-8",
            )

        def mutate_codex(fixture: Path) -> None:
            path = fixture / ".codex" / "agents" / "verifier.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "Do not repair failures, edit files, commit, push, publish",
                    "You are authorized to repair failures, edit files, commit, push, and publish",
                ),
                encoding="utf-8",
            )

        self.assert_fixture_error(mutate_claude, "grants a mutating authority term")
        self.assert_fixture_error(mutate_codex, "grants a mutating authority term")

    def test_cursor_environment_requires_bounded_setup_command(self) -> None:
        def retain(fixture: Path) -> None:
            path = fixture / ".cursor" / "environment.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["install"] = "npm test"
            path.write_text(json.dumps(data), encoding="utf-8")

        def rename(fixture: Path) -> None:
            path = fixture / ".cursor" / "environment.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["name"] = "other"
            path.write_text(json.dumps(data), encoding="utf-8")

        self.assert_fixture_error(retain, "reviewed compileall command")
        self.assert_fixture_error(rename, "name must be coding-agents")
        errors = fast_validate(ROOT)
        self.assertFalse([error for error in errors if "Cursor environment" in error], errors)

    def test_repository_scan_detects_stale_markers_and_secret_canaries_without_echoing_values(self) -> None:
        marker = "grok" + "-memory-skill"
        token = "gh" + "p_" + ("scanprobe" + "0123456789abcdef")
        path_text = "C:" + "\\private\\scan-probe.txt"

        def mutate(fixture: Path) -> None:
            (fixture / "config" / "scan-probe.txt").write_text(f"legacy marker: {marker}\n", encoding="utf-8")
            (fixture / "scripts" / "scan-probe.py").write_text(
                f"SCAN_TOKEN = {token!r}\nSCAN_PATH = {path_text!r}\n", encoding="utf-8"
            )

        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        mutate(fixture)
        errors = fast_validate(fixture)
        self.assertTrue(any("Stale marker" in error for error in errors), errors)
        self.assertTrue(any("Secret material detected" in error for error in errors), errors)
        encoded = json.dumps(errors)
        self.assertNotIn(token, encoded)
        self.assertNotIn(path_text, encoded)

    def test_rejects_missing_agent_plugins_manifest(self) -> None:
        self.assert_fixture_error(
            lambda fixture: self._agent_plugins_manifest(fixture).unlink(),
            "Invalid or missing Agent Plugins plugin.json",
        )

    def test_rejects_agent_plugins_wrong_schema(self) -> None:
        def mutate(fixture: Path) -> None:
            self._rewrite_agent_plugins_manifest(
                fixture, lambda data: data.update({"$schema": "https://example.com/not-the-schema.json"})
            )

        self.assert_fixture_error(mutate, "Agent Plugins plugin.json $schema must be")

    def test_rejects_agent_plugins_missing_name(self) -> None:
        def mutate(fixture: Path) -> None:
            self._rewrite_agent_plugins_manifest(fixture, lambda data: data.pop("name"))

        self.assert_fixture_error(mutate, "Agent Plugins plugin.json has an invalid name")

    def test_rejects_agent_plugins_invalid_name(self) -> None:
        def mutate(fixture: Path) -> None:
            self._rewrite_agent_plugins_manifest(fixture, lambda data: data.update({"name": "Coding--Workflows"}))

        self.assert_fixture_error(mutate, "Agent Plugins plugin.json has an invalid name")

    def test_rejects_agent_plugins_unknown_field(self) -> None:
        def mutate(fixture: Path) -> None:
            self._rewrite_agent_plugins_manifest(fixture, lambda data: data.update({"skills": "./skills/"}))

        self.assert_fixture_error(mutate, "unknown top-level fields")

    def test_rejects_agent_plugins_version_mismatch(self) -> None:
        def mutate(fixture: Path) -> None:
            self._rewrite_agent_plugins_manifest(fixture, lambda data: data.update({"version": "0.0.1"}))

        self.assert_fixture_error(mutate, "Agent Plugins plugin.json version must match")

    def test_rejects_agent_plugins_mcp_json(self) -> None:
        def mutate(fixture: Path) -> None:
            (fixture / "plugins" / "coding-workflows" / "mcp.json").write_text("{}", encoding="utf-8")

        self.assert_fixture_error(mutate, "must not include mcp.json")

    def test_rejects_agent_plugins_skill_directory_missing_skill_md(self) -> None:
        def mutate(fixture: Path) -> None:
            (fixture / "plugins" / "coding-workflows" / "skills" / "orphan-skill").mkdir()

        self.assert_fixture_error(mutate, "Agent Plugins skill directory orphan-skill is missing SKILL.md")

    def test_rejects_agent_plugins_extensions(self) -> None:
        def mutate(fixture: Path) -> None:
            self._rewrite_agent_plugins_manifest(
                fixture, lambda data: data.update({"extensions": {"com.example.client": {"setting": True}}})
            )

        self.assert_fixture_error(mutate, "must not declare extensions")

    def test_agent_plugins_ignores_nested_skill_md(self) -> None:
        # Intentionally slow: real end-to-end build + validate() across families.
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        nested = fixture / "plugins" / "coding-workflows" / "skills" / "repo-xray" / "nested"
        nested.mkdir()
        (nested / "SKILL.md").write_text("---\nname: nested\ndescription: ignored nested skill\n---\nBody.\n", encoding="utf-8")
        build_packages(fixture)
        claude_app_build_packages(fixture)
        agent_skill_build_packages(fixture)
        self.assertEqual([], VALIDATOR.validate(fixture, tracked_files=[]))

    def test_rejects_broken_internal_link(self) -> None:
        self.assert_fixture_error(
            lambda fixture: (fixture / "docs" / "broken.md").write_text("[missing](./nope.md)\n", encoding="utf-8"),
            "Broken internal link",
        )

    def test_rejects_invalid_skill_metadata_shape(self) -> None:
        def mutate(fixture: Path) -> None:
            path = fixture / "plugins" / "coding-workflows" / "skills" / "repo-xray" / "agents" / "openai.yaml"
            path.write_text("interface:\n  display_name: Repo X-Ray\n  unknown: nope\n", encoding="utf-8")

        self.assert_fixture_error(mutate, "unsupported interface key")

    def test_rejects_tracked_zero_byte_file(self) -> None:
        def mutate(fixture: Path) -> None:
            (fixture / "empty.txt").write_bytes(b"")

        self.assert_fixture_error(mutate, "Tracked zero-byte file", tracked_files=["empty.txt"])

    def test_documentation_contract_requires_synchronized_checks_and_validator_policy(self) -> None:
        errors: list[str] = []
        VALIDATOR._validate_documentation_contract(ROOT, lambda path: True, errors)
        self.assertEqual([], errors)

    def test_rejects_missing_publication_file(self) -> None:
        self.assert_fixture_error(
            lambda fixture: (fixture / "SECURITY.md").unlink(),
            "Required repository file is missing: SECURITY.md",
        )

    def test_rejects_missing_pull_request_template(self) -> None:
        self.assert_fixture_error(
            lambda fixture: (fixture / ".github" / "pull_request_template.md").unlink(),
            "Required repository file is missing: .github/pull_request_template.md",
        )

    def test_documentation_hygiene_covers_all_markdown_roots(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "knowledge-hygiene.yml").read_text(encoding="utf-8")
        link_args = workflow.split("args: >-", 1)[1].split("- name: Check Markdown formatting", 1)[0]
        markdown_globs = workflow.split("globs: |", 1)[1]
        for pattern in ("*.md", ".github/**/*.md", "docs/**/*.md", "plugins/**/*.md", ".claude/**/*.md"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, link_args)
                self.assertIn(pattern, markdown_globs)

    def test_workflow_checkout_steps_disable_persisted_credentials(self) -> None:
        for relative in (".github/workflows/validate-repository.yml", ".github/workflows/knowledge-hygiene.yml"):
            with self.subTest(workflow=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                checkout_steps = re.findall(
                    r"(?ms)^\s*- name: Check out repository\n(.*?)(?=^\s*- name:|\Z)",
                    text,
                )
                self.assertEqual(1, len(checkout_steps), text)
                self.assertIn("persist-credentials: false", checkout_steps[0])

    def test_validation_workflow_contract_rejects_decoy_disabled_and_regression(self) -> None:
        text = (ROOT / ".github" / "workflows" / "validate-repository.yml").read_text(encoding="utf-8")
        errors: list[str] = []
        VALIDATOR._validate_workflow_contract(ROOT, lambda path: True, errors)
        self.assertEqual([], errors)

        decoy = text.replace(
            "jobs:\n  validate:",
            "jobs:\n  decoy:\n    steps:\n      - name: Run repository-tool tests\n        run: echo decoy\n  validate:",
            1,
        )
        with mock.patch.object(VALIDATOR, "_read_text_artifact", return_value=decoy):
            errors = []
            VALIDATOR._validate_workflow_contract(ROOT, lambda path: True, errors)
        self.assertEqual([], errors)

        disabled = text.replace(
            "      - name: Run repository-tool tests\n",
            "      - name: Run repository-tool tests\n        if: false\n",
            1,
        )
        with mock.patch.object(VALIDATOR, "_read_text_artifact", return_value=disabled):
            errors = []
            VALIDATOR._validate_workflow_contract(ROOT, lambda path: True, errors)
        self.assertTrue(any("must be unconditional" in error for error in errors), errors)

        regressed = text.replace(
            "run: python scripts/check-diff-whitespace.py",
            "run: git diff --check HEAD^ HEAD",
            1,
        )
        with mock.patch.object(VALIDATOR, "_read_text_artifact", return_value=regressed):
            errors = []
            VALIDATOR._validate_workflow_contract(ROOT, lambda path: True, errors)
        self.assertTrue(any("must run exactly once" in error or "complete event" in error for error in errors), errors)

    def test_validation_workflow_contract_rejects_masked_commands_event_filters_and_matrix_mutations(self) -> None:
        text = (ROOT / ".github" / "workflows" / "validate-repository.yml").read_text(encoding="utf-8")

        masked = text.replace(
            "run: python scripts/validate-repository.py",
            "run: |\n          python scripts/validate-repository.py\n          echo done",
            1,
        )
        with mock.patch.object(VALIDATOR, "_read_text_artifact", return_value=masked):
            errors = []
            VALIDATOR._validate_workflow_contract(ROOT, lambda path: True, errors)
        self.assertTrue(any("must run only its required command" in error for error in errors), errors)

        filtered_pull_request = text.replace(
            "  pull_request:\n",
            "  pull_request:\n    paths:\n      - docs/**\n",
            1,
        )
        with mock.patch.object(VALIDATOR, "_read_text_artifact", return_value=filtered_pull_request):
            errors = []
            VALIDATOR._validate_workflow_contract(ROOT, lambda path: True, errors)
        self.assertTrue(any("must not filter pull_request events" in error for error in errors), errors)

        filtered_push = text.replace(
            "    branches: [main]\n",
            "    branches: [main]\n    paths-ignore:\n      - docs/**\n",
            1,
        )
        with mock.patch.object(VALIDATOR, "_read_text_artifact", return_value=filtered_push):
            errors = []
            VALIDATOR._validate_workflow_contract(ROOT, lambda path: True, errors)
        self.assertTrue(any("must not filter push events by path" in error for error in errors), errors)

        narrowed_matrix = text.replace(
            '        python-version: ["3.11", "3.14"]\n',
            '        python-version: ["3.11", "3.14"]\n        exclude:\n          - os: windows-latest\n',
            1,
        )
        with mock.patch.object(VALIDATOR, "_read_text_artifact", return_value=narrowed_matrix):
            errors = []
            VALIDATOR._validate_workflow_contract(ROOT, lambda path: True, errors)
        self.assertTrue(any("must not silently add or remove" in error for error in errors), errors)

        # Equivalent YAML spellings must not slip filters, matrix mutations,
        # or failure-masking shells past the line-oriented checks.
        on_block = "on:\n  pull_request:\n  push:\n    branches: [main]\n  workflow_dispatch:\n"
        self.assertIn(on_block, text)
        variants = {
            "pull_request flow mapping": (
                text.replace("  pull_request:\n", "  pull_request: {paths: [docs/**]}\n", 1),
                "event triggers must match the reviewed contract",
            ),
            "pull_request quoted key": (
                text.replace("  pull_request:\n", '  pull_request:\n    "paths": [docs/**]\n', 1),
                "event triggers must match the reviewed contract",
            ),
            "four-space trigger indentation": (
                text.replace(
                    on_block,
                    "on:\n    pull_request:\n        paths: [docs/**]\n    push:\n        branches: [main]\n    workflow_dispatch:\n",
                    1,
                ),
                "event triggers must match the reviewed contract",
            ),
            "quoted matrix exclude": (
                text.replace(
                    '        python-version: ["3.11", "3.14"]\n',
                    '        python-version: ["3.11", "3.14"]\n        "exclude":\n          - os: windows-latest\n',
                    1,
                ),
                "must not silently add or remove",
            ),
            "step shell override": (
                text.replace(
                    "        run: python scripts/validate-repository.py",
                    "        shell: pwsh -command \". '{0}'; exit 0\"\n        run: python scripts/validate-repository.py",
                    1,
                ),
                "must not override the default run shell",
            ),
            "job default shell": (
                text.replace(
                    "    runs-on: ${{ matrix.os }}\n",
                    "    runs-on: ${{ matrix.os }}\n    defaults:\n      run:\n        shell: bash\n",
                    1,
                ),
                "must not override the default run shell",
            ),
        }
        for label, (variant, expected) in variants.items():
            with self.subTest(label=label):
                self.assertNotEqual(text, variant)
                with mock.patch.object(VALIDATOR, "_read_text_artifact", return_value=variant):
                    errors = []
                    VALIDATOR._validate_workflow_contract(ROOT, lambda path: True, errors)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_diff_check_script_covers_full_event_base_and_manual_events(self) -> None:
        def run_git(repository: Path, *arguments: str) -> str:
            completed = subprocess.run(
                ["git", *arguments],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            )
            return completed.stdout.strip()

        def commit(repository: Path, relative: str, content: str, message: str) -> None:
            (repository / relative).write_text(content, encoding="utf-8")
            run_git(repository, "add", relative)
            run_git(repository, "commit", "-m", message)

        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "diff-fixture"
            repository.mkdir()
            run_git(repository, "init")
            run_git(repository, "config", "user.email", "fixture@example.invalid")
            run_git(repository, "config", "user.name", "Fixture")
            commit(repository, "tracked.txt", "clean\n", "base")
            base = run_git(repository, "rev-parse", "HEAD")
            commit(repository, "tracked.txt", "clean\nwhitespace error  \n", "introduce whitespace")
            commit(repository, "tracked.txt", "clean\nwhitespace error  \nother change\n", "extend change")
            head = run_git(repository, "rev-parse", "HEAD")
            script = str(ROOT / "scripts" / "check-diff-whitespace.py")

            push_environment = {
                **os.environ,
                "EVENT_NAME": "push",
                "EVENT_BEFORE": base,
                "PULL_REQUEST_BASE": "",
                "HEAD_SHA": head,
            }
            push = subprocess.run(
                [sys.executable, script],
                cwd=repository,
                env=push_environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, push.returncode, push.stderr)
            self.assertNotIn("invalid or incomplete", push.stderr)

            manual_environment = {
                **os.environ,
                "EVENT_NAME": "workflow_dispatch",
                "EVENT_BEFORE": "",
                "PULL_REQUEST_BASE": "",
                "HEAD_SHA": head,
            }
            manual = subprocess.run(
                [sys.executable, script],
                cwd=repository,
                env=manual_environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, manual.returncode, manual.stderr)
            # A whitespace verdict must come from `git diff --check`, never
            # from the metadata failure path (which now uses exit 3).
            self.assertNotIn("invalid or incomplete", manual.stderr)

            narrow = subprocess.run(
                ["git", "diff", "--check", f"{head}^", head],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, narrow.returncode, narrow.stderr)

    def test_diff_check_script_uses_distinct_metadata_and_whitespace_results(self) -> None:
        def run_git(repository: Path, *arguments: str) -> str:
            completed = subprocess.run(
                ["git", *arguments],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            )
            return completed.stdout.strip()

        def run_script(repository: Path, environment: dict[str, str]):
            full = {**os.environ, **environment}
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check-diff-whitespace.py")],
                cwd=repository,
                env=full,
                capture_output=True,
                text=True,
                check=False,
            )

        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "diff-exit-fixture"
            repository.mkdir()
            run_git(repository, "init")
            run_git(repository, "config", "user.email", "fixture@example.invalid")
            run_git(repository, "config", "user.name", "Fixture")
            (repository / "tracked.txt").write_text("clean\n", encoding="utf-8")
            run_git(repository, "add", "tracked.txt")
            run_git(repository, "commit", "-m", "base")
            clean = run_git(repository, "rev-parse", "HEAD")

            manual_clean = run_script(
                repository,
                {"EVENT_NAME": "workflow_dispatch", "EVENT_BEFORE": "", "PULL_REQUEST_BASE": "", "HEAD_SHA": clean},
            )
            self.assertEqual(0, manual_clean.returncode, manual_clean.stderr)

            root_push_clean = run_script(
                repository,
                {"EVENT_NAME": "push", "EVENT_BEFORE": "0" * 40, "PULL_REQUEST_BASE": "", "HEAD_SHA": clean},
            )
            self.assertEqual(0, root_push_clean.returncode, root_push_clean.stderr)

            for label, environment in (
                ("unsupported-event", {"EVENT_NAME": "schedule", "EVENT_BEFORE": "", "PULL_REQUEST_BASE": "", "HEAD_SHA": clean}),
                ("invalid-head", {"EVENT_NAME": "push", "EVENT_BEFORE": clean, "PULL_REQUEST_BASE": "", "HEAD_SHA": "not-a-revision"}),
                ("missing-pr-base", {"EVENT_NAME": "pull_request", "EVENT_BEFORE": "", "PULL_REQUEST_BASE": "", "HEAD_SHA": clean}),
                ("unreachable-base", {"EVENT_NAME": "push", "EVENT_BEFORE": "a" * 40, "PULL_REQUEST_BASE": "", "HEAD_SHA": clean}),
                ("malformed-push-base", {"EVENT_NAME": "push", "EVENT_BEFORE": "not-a-revision", "PULL_REQUEST_BASE": "", "HEAD_SHA": clean}),
                ("head-is-tree", {"EVENT_NAME": "workflow_dispatch", "EVENT_BEFORE": "", "PULL_REQUEST_BASE": "", "HEAD_SHA": run_git(repository, "rev-parse", "HEAD^{tree}")}),
                ("head-well-formed-missing", {"EVENT_NAME": "workflow_dispatch", "EVENT_BEFORE": "", "PULL_REQUEST_BASE": "", "HEAD_SHA": "d" * 40}),
            ):
                with self.subTest(label=label):
                    completed = run_script(repository, environment)
                    self.assertEqual(DIFF_CHECK.METADATA_EXIT_CODE, completed.returncode, completed.stderr)
                    self.assertNotEqual(2, completed.returncode)
                    self.assertIn("invalid or incomplete", completed.stderr)

            (repository / "tracked.txt").write_text("clean\nwhitespace error  \n", encoding="utf-8")
            run_git(repository, "add", "tracked.txt")
            run_git(repository, "commit", "-m", "dirty")
            dirty = run_git(repository, "rev-parse", "HEAD")
            manual_dirty = run_script(
                repository,
                {"EVENT_NAME": "workflow_dispatch", "EVENT_BEFORE": "", "PULL_REQUEST_BASE": "", "HEAD_SHA": dirty},
            )
            self.assertEqual(2, manual_dirty.returncode, manual_dirty.stderr)
            self.assertNotIn("invalid or incomplete", manual_dirty.stderr)

    def test_repository_tree_passes_full_tree_whitespace_check(self) -> None:
        # workflow_dispatch and initial pushes check the complete tree, so any
        # tracked whitespace error makes those required runs fail. Compare the
        # empty tree with the working tree to catch it before commit.
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            self.skipTest("repository checkout is not a Git work tree")
        empty_tree = subprocess.run(
            ["git", "hash-object", "-t", "tree", "--stdin"],
            cwd=ROOT,
            input="",
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        completed = subprocess.run(
            ["git", "diff", "--check", empty_tree],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_agent_skill_packages_generate_all_host_roots_deterministically(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        self.assertEqual([], agent_skill_validate_packages(fixture))
        self.assertTrue(agent_skill_packages_are_current(fixture))
        targets = (
            "plugins/coding-workflows/agent-skills/dist",
            "plugins/coding-workflows/gemini/dist",
            "plugins/coding-workflows/kimi/dist",
        )
        first = {
            target: {
                path.relative_to(fixture / target).as_posix(): path.read_bytes()
                for path in (fixture / target).rglob("*") if path.is_file()
            }
            for target in targets
        }
        agent_skill_build_packages(fixture)
        second = {
            target: {
                path.relative_to(fixture / target).as_posix(): path.read_bytes()
                for path in (fixture / target).rglob("*") if path.is_file()
            }
            for target in targets
        }
        self.assertEqual(first, second)

    def test_agent_skill_packages_accept_checkout_newlines_but_reject_content_drift(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        targets = (
            fixture / "plugins/coding-workflows/agent-skills/dist",
            fixture / "plugins/coding-workflows/gemini/dist",
            fixture / "plugins/coding-workflows/kimi/dist",
        )
        for target in targets:
            for path in target.rglob("*"):
                if path.is_file():
                    content = path.read_bytes()
                    path.write_bytes(re.sub(rb"(?<!\r)\n", b"\r\n", content))
        self.assertEqual([], agent_skill_validate_packages(fixture))

        skill = targets[0] / "skills/repo-xray/SKILL.md"
        skill.write_bytes(skill.read_bytes() + b"\r\ncontent drift\r\n")
        errors = agent_skill_validate_packages(fixture)
        self.assertTrue(any("Stale generated Agent Skills package" in error for error in errors), errors)

    def test_agent_skill_generation_rejects_symlinked_output_parent_without_external_changes(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        plugin_root = fixture / "plugins/coding-workflows"
        portable = plugin_root / "agent-skills/dist"
        kimi = plugin_root / "kimi/dist"
        snapshots = {
            output: {
                path.relative_to(output).as_posix(): path.read_bytes()
                for path in output.rglob("*") if path.is_file()
            }
            for output in (portable, kimi)
        }

        gemini = plugin_root / "gemini"
        shutil.rmtree(gemini)
        external = Path(temporary.name) / "external-gemini"
        external_dist = external / "dist"
        external_dist.mkdir(parents=True)
        sentinel = external_dist / "keep.txt"
        sentinel.write_text("external sentinel", encoding="utf-8")
        try:
            gemini.symlink_to(external, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink creation is unavailable or denied: {exc}")

        with self.assertRaisesRegex(ValueError, "symlink|resolve inside"):
            agent_skill_build_packages(fixture)

        self.assertEqual("external sentinel", sentinel.read_text(encoding="utf-8"))
        self.assertTrue(gemini.is_symlink())
        for output, expected in snapshots.items():
            actual = {
                path.relative_to(output).as_posix(): path.read_bytes()
                for path in output.rglob("*") if path.is_file()
            }
            self.assertEqual(expected, actual)

    def test_agent_skill_packages_scan_non_markdown_text_for_secrets(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        support = fixture / "plugins/coding-workflows/skills/repo-xray/support.txt"
        support.write_text("token=" + "sk-" + ("x" * 20), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "secret material"):
            agent_skill_build_packages(fixture)
        self.assertFalse((fixture / "plugins/coding-workflows/agent-skills/dist/skills/repo-xray/support.txt").exists())

    def test_agent_skill_packages_scan_non_markdown_text_for_windows_paths(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        support = fixture / "plugins/coding-workflows/skills/repo-xray/support.txt"
        support.write_text("local file: C:" + r"\Users\example\private.txt", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "local machine path"):
            agent_skill_build_packages(fixture)
        self.assertFalse((fixture / "plugins/coding-workflows/agent-skills/dist/skills/repo-xray/support.txt").exists())

    def test_agent_skill_packages_do_not_compare_oversized_files(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        oversized_output = fixture / "plugins/coding-workflows/agent-skills/dist/skills/repo-xray/oversized.txt"
        with oversized_output.open("wb") as stream:
            stream.truncate(agent_skill_packages.MAX_PACKAGE_FILE_BYTES + 1)
        original_same_file = agent_skill_packages._same_file

        def reject_oversized_comparison(expected: Path, actual: Path) -> bool:
            self.assertLessEqual(expected.stat().st_size, agent_skill_packages.MAX_PACKAGE_FILE_BYTES)
            self.assertLessEqual(actual.stat().st_size, agent_skill_packages.MAX_PACKAGE_FILE_BYTES)
            return original_same_file(expected, actual)

        with (
            mock.patch.object(agent_skill_packages, "_same_file", side_effect=reject_oversized_comparison) as compare_file,
        ):
            errors = agent_skill_validate_packages(fixture)

        compare_file.assert_called()
        self.assertTrue(any("package file exceeds the size limit" in error for error in errors), errors)

    def test_agent_skill_packages_reject_oversized_canonical_input_before_reproduction(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        source = fixture / "plugins/coding-workflows/skills/repo-xray/support.txt"
        with source.open("wb") as stream:
            stream.truncate(agent_skill_packages.MAX_PACKAGE_FILE_BYTES + 1)

        with (
            mock.patch.object(
                agent_skill_packages,
                "_render_packages",
                side_effect=AssertionError("oversized canonical input must be rejected before rendering"),
            ) as render_packages,
            mock.patch.object(
                agent_skill_packages,
                "_same_file",
                side_effect=AssertionError("oversized canonical input must not be compared"),
            ) as compare_file,
        ):
            errors = agent_skill_validate_packages(fixture)

        render_packages.assert_not_called()
        compare_file.assert_not_called()
        self.assertTrue(any("Canonical package file exceeds the size limit" in error for error in errors), errors)

    def test_agent_skill_packages_scan_mixed_case_markdown_for_secrets(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        support = fixture / "plugins/coding-workflows/skills/repo-xray/credentials.MD"
        support.write_text("token=" + "sk-" + ("x" * 20), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "secret material"):
            agent_skill_build_packages(fixture)
        self.assertFalse((fixture / "plugins/coding-workflows/agent-skills/dist/skills/repo-xray/credentials.MD").exists())

    def test_agent_skill_packages_scan_mixed_case_markdown_for_windows_paths(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        support = fixture / "plugins/coding-workflows/skills/repo-xray/credentials.MD"
        support.write_text("local file: C:" + r"\Users\example\private.txt", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "local machine path"):
            agent_skill_build_packages(fixture)
        self.assertFalse((fixture / "plugins/coding-workflows/agent-skills/dist/skills/repo-xray/credentials.MD").exists())

    def test_all_package_formats_reject_mixed_case_secret_text_without_replacing_outputs(self) -> None:
        families = (
            ("work-mode", build_packages, "plugins/coding-workflows/work-mode/dist"),
            ("claude-app", claude_app_build_packages, "plugins/coding-workflows/claude-app/dist"),
            ("agent-skills", agent_skill_build_packages, "plugins/coding-workflows/agent-skills/dist"),
        )
        for label, builder, relative in families:
            with self.subTest(label=label):
                temporary, fixture = self.make_fixture()
                self.addCleanup(temporary.cleanup)
                output = fixture / relative
                before = self.snapshot_package(output)
                support = fixture / "plugins/coding-workflows/skills/repo-xray/credentials.MD"
                support.write_text("token=" + "sk-" + ("x" * 20), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "secret material"):
                    builder(fixture)
                self.assertEqual(before, self.snapshot_package(output))

    def test_work_mode_and_claude_app_reject_non_text_and_oversized_sources(self) -> None:
        families = (
            ("work-mode", build_packages, "plugins/coding-workflows/work-mode/dist"),
            ("claude-app", claude_app_build_packages, "plugins/coding-workflows/claude-app/dist"),
        )
        for label, builder, relative in families:
            for artifact_kind in ("non-text", "oversized"):
                with self.subTest(label=label, artifact_kind=artifact_kind):
                    temporary, fixture = self.make_fixture()
                    self.addCleanup(temporary.cleanup)
                    output = fixture / relative
                    before = self.snapshot_package(output)
                    support = fixture / "plugins/coding-workflows/skills/repo-xray/support.bin"
                    if artifact_kind == "non-text":
                        support.write_bytes(b"binary")
                        expected = "non-text"
                    else:
                        with support.open("wb") as stream:
                            stream.truncate(work_mode_packages.MAX_PACKAGE_FILE_BYTES + 1)
                        expected = "size limit"
                    with self.assertRaisesRegex(ValueError, expected):
                        builder(fixture)
                    self.assertEqual(before, self.snapshot_package(output))

    def test_agent_skill_packages_validate_references_in_mixed_case_markdown(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        support = fixture / "plugins/coding-workflows/skills/repo-xray/extra.MD"
        support.write_text("See ./missing-reference.md for details.", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "reference is missing: ./missing-reference.md"):
            agent_skill_build_packages(fixture)

    def test_agent_skill_generation_rejects_output_aliases(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        with mock.patch.object(
            agent_skill_packages,
            "OUTPUTS",
            (agent_skill_packages.PORTABLE_DIST, agent_skill_packages.PORTABLE_DIST, agent_skill_packages.KIMI_DIST),
        ):
            with self.assertRaisesRegex(ValueError, "alias|overlap"):
                agent_skill_packages._preflight_output_destinations(fixture)

    def test_agent_skill_generation_rolls_back_all_outputs_after_replacement_failure(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        targets = tuple(fixture / target for target in agent_skill_packages.OUTPUTS)

        def snapshot() -> dict[Path, dict[str, bytes]]:
            return {
                output: {
                    path.relative_to(output).as_posix(): path.read_bytes()
                    for path in output.rglob("*") if path.is_file()
                }
                for output in targets
            }

        previous = snapshot()
        (fixture / "plugins/coding-workflows/skills/repo-xray/new-file.txt").write_text(
            "new canonical package content", encoding="utf-8"
        )
        original_replace = agent_skill_packages.os.replace
        failing_destination = fixture / agent_skill_packages.KIMI_DIST

        def fail_kimi_install(source, destination) -> None:
            if Path(destination) == failing_destination and ".stage-" in Path(source).name:
                raise OSError("injected final package replacement failure")
            original_replace(source, destination)

        with mock.patch.object(agent_skill_packages.os, "replace", side_effect=fail_kimi_install):
            with self.assertRaisesRegex(OSError, "injected final package replacement failure"):
                agent_skill_build_packages(fixture)

        self.assertEqual(previous, snapshot())
        for output in targets:
            self.assertEqual([], list(output.parent.glob(f".{output.name}.stage-*")))
            self.assertEqual([], list(output.parent.glob(f".{output.name}.backup-*")))

    @unittest.skipUnless(sys.platform == "win32", "Windows junction regression")
    def test_agent_skill_generation_rejects_junctioned_output_parent_before_changes(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        plugin_root = fixture / "plugins/coding-workflows"
        canonical_extra = plugin_root / "skills/repo-xray/new-support.txt"
        canonical_extra.write_text("new canonical package content", encoding="utf-8")
        target_sentinel = plugin_root / "agent-skills/junction-target-sentinel.txt"
        target_sentinel.write_text("preserve target", encoding="utf-8")
        outputs = tuple(fixture / target for target in (
            "plugins/coding-workflows/agent-skills/dist",
            "plugins/coding-workflows/kimi/dist",
        ))
        snapshots = {
            output: {
                path.relative_to(output).as_posix(): path.read_bytes()
                for path in output.rglob("*") if path.is_file()
            }
            for output in outputs
        }

        gemini_parent = plugin_root / "gemini"
        shutil.rmtree(gemini_parent)
        agent_skills_parent = plugin_root / "agent-skills"
        command = f"New-Item -ItemType Junction -Path '{gemini_parent}' -Target '{agent_skills_parent}' | Out-Null"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.skipTest(f"Windows junction creation is unavailable: {result.stderr or result.stdout}")

        with self.assertRaisesRegex(ValueError, "junction|reparse|symlink"):
            agent_skill_build_packages(fixture)

        self.assertTrue(agent_skill_packages._is_reparse_point(gemini_parent))
        self.assertEqual("preserve target", target_sentinel.read_text(encoding="utf-8"))
        for output, expected in snapshots.items():
            actual = {
                path.relative_to(output).as_posix(): path.read_bytes()
                for path in output.rglob("*") if path.is_file()
            }
            self.assertEqual(expected, actual)

    @unittest.skipUnless(sys.platform == "win32", "Windows nested junction regression")
    def test_agent_skill_packages_reject_nested_reparse_point_without_changes(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        targets = tuple(fixture / target for target in agent_skill_packages.OUTPUTS)

        def snapshot() -> dict[Path, dict[str, bytes]]:
            return {
                output: {
                    path.relative_to(output).as_posix(): path.read_bytes()
                    for path in agent_skill_packages._iter_package_entries(output)
                    if path.is_file() and not agent_skill_packages._is_reparse_point(path)
                }
                for output in targets
            }

        previous = snapshot()
        package_root = targets[0] / "skills" / "repo-xray"
        junction = package_root / "nested-junction"
        target = targets[0] / "skills" / "context-first"
        command = f"New-Item -ItemType Junction -Path '{junction}' -Target '{target}' | Out-Null"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.skipTest(f"Windows junction creation is unavailable: {result.stderr or result.stdout}")

        errors = agent_skill_validate_packages(fixture)
        self.assertTrue(any("reparse point" in error.lower() for error in errors), errors)
        with self.assertRaisesRegex(ValueError, "reparse point"):
            agent_skill_build_packages(fixture)
        self.assertEqual(previous, snapshot())

    def test_agent_skill_packages_keep_references_inside_skill_root(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        package = fixture / "plugins/coding-workflows/agent-skills/dist/skills/context-first"
        skill_text = (package / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/workflow-coordination.md", skill_text)
        self.assertTrue((package / "references/workflow-coordination.md").is_file())
        self.assertFalse((package.parent.parent / "references").exists())

    def test_nested_shared_reference_paths_are_preserved_in_all_packages(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        references = fixture / "plugins/coding-workflows/references"
        parent = references / "workflow-coordination.md"
        parent.write_text(
            parent.read_text(encoding="utf-8") + "\nSee [nested guidance](./nested/child.md).\n",
            encoding="utf-8",
        )
        nested = references / "nested" / "child.md"
        nested.parent.mkdir()
        nested.write_text(
            "Nested shared guidance.\n\nUse `../evidence-contract.md` for shared evidence.\n",
            encoding="utf-8",
        )

        build_packages(fixture)
        claude_app_build_packages(fixture)
        agent_skill_build_packages(fixture)

        self.assertTrue(
            (fixture / "plugins/coding-workflows/work-mode/dist/context-first/references/nested/child.md").is_file()
        )
        self.assertIn(
            "../evidence-contract.md",
            (fixture / "plugins/coding-workflows/work-mode/dist/context-first/references/nested/child.md").read_text(
                encoding="utf-8"
            ),
        )
        self.assertTrue(
            (fixture / "plugins/coding-workflows/agent-skills/dist/skills/context-first/references/nested/child.md").is_file()
        )
        self.assertIn(
            "../evidence-contract.md",
            (fixture / "plugins/coding-workflows/agent-skills/dist/skills/context-first/references/nested/child.md").read_text(
                encoding="utf-8"
            ),
        )
        with zipfile.ZipFile(fixture / "plugins/coding-workflows/claude-app/dist/context-first.zip") as archive:
            self.assertIn("context-first/references/nested/child.md", archive.namelist())
            self.assertIn(b"../evidence-contract.md", archive.read("context-first/references/nested/child.md"))
        # Intentionally slow: real end-to-end build + validate() across families.
        self.assertEqual([], VALIDATOR.validate(fixture, tracked_files=[]))
        self.assertEqual([], validate_packages(fixture))
        self.assertEqual([], claude_app_validate_packages(fixture))
        self.assertEqual([], agent_skill_validate_packages(fixture))

    def test_nested_shared_references_cannot_escape_shared_root(self) -> None:
        builders = (build_packages, claude_app_build_packages, agent_skill_build_packages)
        for builder in builders:
            with self.subTest(builder=builder.__module__):
                temporary, fixture = self.make_fixture()
                self.addCleanup(temporary.cleanup)
                reference = fixture / "plugins/coding-workflows/references/workflow-coordination.md"
                reference.write_text(
                    reference.read_text(encoding="utf-8") + "\n[outside](../../../outside.md)\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "inside|resolve"):
                    builder(fixture)

    def test_agent_skill_packages_reject_malformed_host_manifest_and_stale_output(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        manifest = fixture / "plugins/coding-workflows/gemini/dist/gemini-extension.json"
        manifest.write_text('{"name":"wrong","version":"1"}\n', encoding="utf-8")
        errors = agent_skill_validate_packages(fixture)
        self.assertTrue(any("Gemini package has a malformed" in error for error in errors), errors)
        self.assertFalse(any("Stale generated Agent Skills package" in error for error in errors), errors)

    def test_agent_skill_packages_reject_unsupported_source_metadata(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        path = fixture / "plugins/coding-workflows/skills/repo-xray/SKILL.md"
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace("description:", "license: MIT\ndescription:", 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported or mismatched"):
            agent_skill_build_packages(fixture)
        self.assertEqual(original.replace("description:", "license: MIT\ndescription:", 1), path.read_text(encoding="utf-8"))

    def test_agent_skill_packages_reject_broken_shared_reference(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        path = fixture / "plugins/coding-workflows/skills/live-research/SKILL.md"
        text = path.read_text(encoding="utf-8").replace("evidence-contract.md", "missing-contract.md")
        path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "shared reference is missing"):
            agent_skill_build_packages(fixture)

    def test_agent_skill_packages_reject_shared_reference_path_traversal(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        path = fixture / "plugins/coding-workflows/skills/live-research/SKILL.md"
        text = path.read_text(encoding="utf-8").replace(
            "../../references/evidence-contract.md", "../../../../references/evidence-contract.md"
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must resolve inside"):
            agent_skill_build_packages(fixture)

    def test_agent_skill_packages_reject_duplicate_frontmatter_names(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        path = fixture / "plugins/coding-workflows/skills/repo-xray/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8").replace("name: repo-xray", "name: context-first", 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported or mismatched"):
            agent_skill_build_packages(fixture)

    def test_agent_skill_packages_reject_symlink_loop(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        loop = fixture / "plugins/coding-workflows/skills/repo-xray/loop"
        try:
            loop.symlink_to(loop)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink creation is unavailable or denied: {exc}")
        with self.assertRaisesRegex(ValueError, "inside|symlink"):
            agent_skill_build_packages(fixture)

    def test_agent_skill_packages_reject_symlink_escape(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        outside = Path(temporary.name) / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        link = fixture / "plugins/coding-workflows/skills/repo-xray/escape.md"
        try:
            link.symlink_to(outside)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink creation is unavailable or denied: {exc}")
        with self.assertRaisesRegex(ValueError, "symlink"):
            agent_skill_build_packages(fixture)

    def test_agent_skill_packages_do_not_mutate_canonical_source(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        source = fixture / "plugins/coding-workflows/skills/live-research/SKILL.md"
        before = source.read_bytes()
        agent_skill_build_packages(fixture)
        self.assertEqual(before, source.read_bytes())

    def test_agent_skill_packages_reject_version_mismatch_and_incorrect_root_shape(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        kimi = fixture / "plugins/coding-workflows/kimi/dist"
        manifest = kimi / "kimi.plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["version"] = "mismatch"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        (kimi / "unlisted-root.txt").write_text("unexpected", encoding="utf-8")
        errors = agent_skill_validate_packages(fixture)
        self.assertTrue(any("Kimi package has a malformed" in error for error in errors), errors)
        self.assertTrue(any("incorrect root shape" in error for error in errors), errors)

    def test_agent_skill_packages_reject_symlinked_output_root(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        portable = fixture / "plugins/coding-workflows/agent-skills/dist"
        outside = Path(temporary.name) / "outside-package"
        outside.mkdir()
        shutil.rmtree(portable)
        try:
            portable.symlink_to(outside, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink creation is unavailable or denied: {exc}")
        errors = agent_skill_validate_packages(fixture)
        self.assertTrue(any("symlink" in error.lower() or "reparse point" in error.lower() for error in errors), errors)

    def test_agent_skill_packages_reject_forbidden_debris_and_oversized_files(self) -> None:
        temporary, fixture = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        agent_skill_build_packages(fixture)
        package = fixture / "plugins/coding-workflows/agent-skills/dist"
        (package / "skills/repo-xray/node_modules").mkdir()
        oversized = package / "skills/repo-xray/extra.bin"
        oversized.write_bytes(b"x" * 2_000_001)
        errors = agent_skill_validate_packages(fixture)
        self.assertTrue(any("forbidden debris" in error for error in errors), errors)
        self.assertTrue(any("exceeds the size limit" in error for error in errors), errors)
        self.assertTrue(any("non-text artifact" in error for error in errors), errors)

    def test_devcontainer_does_not_run_repository_scripts_on_create(self) -> None:
        data = json.loads((ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8"))
        post_create = data.get("postCreateCommand", "")
        self.assertIsInstance(post_create, str)
        self.assertIsNone(
            re.search(r"(?:scripts[/\\]|unittest|pytest|npm\s+test|cargo\s+test|git\s+diff\s+--check)", post_create),
            post_create,
        )


if __name__ == "__main__":
    unittest.main()
