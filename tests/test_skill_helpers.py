"""Tests for the skill-helper boundary, shared Python modules, and their packaging."""

from __future__ import annotations

import sys
import textwrap
import unittest
import zipfile
from pathlib import Path

from repo_support import ROOT, SKILLS, VALIDATOR, make_repo_fixture, run_python, temp_dir

# Never write bytecode next to the sources under test: executing helpers that
# live inside generated package trees must not drop __pycache__/*.pyc into
# those outputs and contaminate package-currentness validation.
sys.dont_write_bytecode = True

import agent_skill_packages
import claude_app_packages
import work_mode_packages
from repository_inventory import HELPER_SUBPROCESS_POLICY, collect_inventory, render_inventory


COMPLIANT_HELPER = textwrap.dedent(
    '''
    """Probe helper used by repository tests."""

    import argparse
    import json
    import sys
    from pathlib import Path

    _HERE = Path(__file__).resolve().parent
    for _candidate in (_HERE.parent / "references", _HERE.parents[2] / "references"):
        if (_candidate / "sharedmod.py").is_file():
            sys.path.insert(0, str(_candidate))
            break
    import sharedmod  # noqa: E402


    def main() -> int:
        argparse.ArgumentParser(description=__doc__).parse_args()
        print(json.dumps({"marker": sharedmod.MARKER}))
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    '''
).lstrip()

SHARED_MODULE = textwrap.dedent(
    '''
    """Shared probe module used by repository tests."""

    # A Markdown shared reference with this text would be treated as a nested link: ../marker
    MARKER = "shared-module-ok"
    '''
).lstrip()


def policy_errors(source: str, *, policy: tuple[str, ...] = (), is_helper: bool = True) -> list[str]:
    return VALIDATOR._helper_policy_errors(
        "probe",
        textwrap.dedent(source).lstrip(),
        policy=policy,
        shared_modules={"sharedmod"},
        skill_text="`scripts/probe.py` uses `../../references/sharedmod.py`",
        is_helper=is_helper,
    )


GUARD = '\nif __name__ == "__main__":\n    pass\n'


class HelperPolicyTests(unittest.TestCase):
    def test_compliant_helper_has_no_policy_errors(self) -> None:
        self.assertEqual([], policy_errors(COMPLIANT_HELPER))
        self.assertEqual([], policy_errors(SHARED_MODULE, is_helper=False))

    def test_policy_rejects_network_dynamic_shell_and_third_party_code(self) -> None:
        cases = {
            "import socket": "denied network",
            "from urllib import request": "denied network",
            "import urllib.request": "denied network",
            "import http.client": "denied network",
            "import importlib": "dynamic-execution",
            "import ctypes": "dynamic-execution",
            "import requests": "non-standard-library",
            "from . import sibling": "relative imports",
            "import os\nos.system('x')": "denied process function",
            "from os import popen": "denied process function",
            "import os\nos.execv('x', [])": "denied process function",
            "eval('1')": "calls eval",
            "exec('1')": "calls exec",
            "__import__('os')": "calls __import__",
            "import subprocess": "without a helper-specific allowance",
        }
        for body, expected in cases.items():
            with self.subTest(body=body):
                errors = policy_errors(f'"""Doc."""\n{body}\n{GUARD}')
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_policy_requires_docstring_main_guard_and_python_311_syntax(self) -> None:
        self.assertTrue(any("docstring" in e for e in policy_errors(f"import json\n{GUARD}")))
        self.assertTrue(any("__main__" in e for e in policy_errors('"""Doc."""\nimport json\n')))
        self.assertFalse(any("__main__" in e for e in policy_errors('"""Doc."""\n', is_helper=False)))
        errors = policy_errors(f'"""Doc."""\ntype Alias = int\n{GUARD}')
        self.assertTrue(any("Python 3.11" in e for e in errors), errors)

    def test_subprocess_allowances_are_narrow(self) -> None:
        git_ok = f'"""Doc."""\nimport subprocess\nsubprocess.run(["git", "status"], check=False)\n{GUARD}'
        self.assertEqual([], policy_errors(git_ok, policy=("git",)))
        rejected = {
            'subprocess.run(["curl", "x"])': "only git",
            "subprocess.run(argv)": "only git",
            'subprocess.run(["git", "status"], shell=True)': "shell execution",
            'subprocess.getoutput("git status")': "unsupported subprocess entry point",
        }
        for call, expected in rejected.items():
            with self.subTest(call=call):
                errors = policy_errors(f'"""Doc."""\nimport subprocess\n{call}\n{GUARD}', policy=("git",))
                self.assertTrue(any(expected in e for e in errors), errors)
        aliased = f'"""Doc."""\nfrom subprocess import run as go\ngo(["curl"])\n{GUARD}'
        self.assertTrue(any("only git" in e for e in policy_errors(aliased, policy=("git",))))
        plan = f'"""Doc."""\nimport subprocess\nsubprocess.Popen(argv)\n{GUARD}'
        self.assertEqual([], policy_errors(plan, policy=("git", "approved-plan")))
        plan_shell = f'"""Doc."""\nimport subprocess\nsubprocess.Popen(argv, shell=True)\n{GUARD}'
        self.assertTrue(any("shell" in e for e in policy_errors(plan_shell, policy=("git", "approved-plan"))))

    def test_shared_modules_may_import_only_the_standard_library(self) -> None:
        errors = policy_errors('"""Doc."""\nimport sharedmod\n', is_helper=False)
        self.assertTrue(any("only the standard library" in e for e in errors), errors)
        errors = policy_errors('"""Doc."""\nimport subprocess\n', is_helper=False)
        self.assertTrue(any("helper-specific allowance" in e for e in errors), errors)

    def test_subprocess_policy_names_only_reviewed_helpers(self) -> None:
        self.assertEqual(
            {
                "session-checkpoint/scripts/checkpoint.py": ("git",),
                "public-release-audit/scripts/release_scan.py": ("git",),
                "patch-proof/scripts/proof_run.py": ("git", "approved-plan"),
            },
            HELPER_SUBPROCESS_POLICY,
        )


class HelperLayoutTests(unittest.TestCase):
    def add_probe(self, fixture: Path, *, helper: str = COMPLIANT_HELPER, name: str = "probe.py",
                  mention: bool = True, shared: bool = True) -> Path:
        skill = fixture / "plugins" / "coding-workflows" / "skills" / "repo-xray"
        (skill / "scripts").mkdir(exist_ok=True)
        (skill / "scripts" / name).write_text(helper, encoding="utf-8")
        if shared:
            # Written as bytes: Git stores `*.py` with LF, while write_text would emit CRLF on Windows.
            (fixture / "plugins" / "coding-workflows" / "references" / "sharedmod.py").write_bytes(
                SHARED_MODULE.encode("utf-8")
            )
        if mention:
            skill_md = skill / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text(encoding="utf-8")
                + f"\nHelper: `scripts/{name}` (shared module `../../references/sharedmod.py`).\n",
                encoding="utf-8",
            )
        return skill

    def errors_for(self, fixture: Path) -> list[str]:
        # TEST-ONLY fast path: subject is helper layout/policy, not package currency.
        return VALIDATOR.validate(fixture, tracked_files=[], check_generated_packages=False)

    def test_compliant_helper_layout_is_accepted(self) -> None:
        fixture = make_repo_fixture(self, with_dist=False)
        self.add_probe(fixture)
        errors = self.errors_for(fixture)
        relevant = [e for e in errors if "probe.py" in e or "sharedmod" in e or "component path" in e]
        self.assertEqual([], relevant)

    def test_executable_components_outside_the_helper_path_are_rejected(self) -> None:
        # TEST-PERF: four independent paths share one mini fixture and one
        # validate() instead of four copies+validates. Each error names its
        # path, so subTests keep per-path proof granular.
        relatives = ("scripts/probe.sh", "scripts/nested/probe.py", "hooks/probe.py", "commands/probe.md")
        fixture = make_repo_fixture(self, with_dist=False)
        skill = SKILLS.relative_to(ROOT)
        skill_md = fixture / skill / "repo-xray" / "SKILL.md"
        mentions = skill_md.read_text(encoding="utf-8")
        for relative in relatives:
            path = fixture / skill / "repo-xray" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('"""Doc."""\n', encoding="utf-8")
            mentions += f"\n`{relative}`\n"
        skill_md.write_text(mentions, encoding="utf-8")
        errors = self.errors_for(fixture)
        for relative in relatives:
            with self.subTest(relative=relative):
                self.assertTrue(
                    any("unexpected component path" in e and relative in e for e in errors), errors
                )

    def test_subprocess_allowance_is_tied_to_the_helper_path(self) -> None:
        fixture = make_repo_fixture(self, with_dist=False)
        helper = f'"""Doc."""\nimport subprocess\nsubprocess.run(["git", "status"])\n{GUARD}'
        self.add_probe(fixture, helper=helper, name="checkpoint.py", shared=False)
        errors = self.errors_for(fixture)
        self.assertTrue(any("checkpoint.py imports subprocess without" in e for e in errors), errors)

    def test_orphaned_support_files_and_unconsumed_shared_modules_are_rejected(self) -> None:
        fixture = make_repo_fixture(self, with_dist=False)
        skill = self.add_probe(fixture, mention=False)
        (skill / "references").mkdir(exist_ok=True)
        (skill / "references" / "unused.md").write_text("# Unused\n", encoding="utf-8")
        errors = self.errors_for(fixture)
        for expected in ("repo-xray/scripts/probe.py", "repo-xray/references/unused.md", "references/sharedmod.py"):
            with self.subTest(expected=expected):
                self.assertTrue(
                    any(expected in e and ("not referenced" in e or "no consumer" in e) for e in errors), errors
                )

    def test_helper_importing_unnamed_shared_module_is_rejected(self) -> None:
        fixture = make_repo_fixture(self, with_dist=False)
        skill = self.add_probe(fixture, mention=False)
        skill_md = skill / "SKILL.md"
        skill_md.write_text(skill_md.read_text(encoding="utf-8") + "\nHelper: `scripts/probe.py`.\n", encoding="utf-8")
        with (fixture / "plugins" / "coding-workflows" / "skills" / "diff-judge" / "SKILL.md").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write("\nSee `../../references/sharedmod.py`.\n")
        errors = self.errors_for(fixture)
        self.assertTrue(any("does not name as ../../references/sharedmod.py" in e for e in errors), errors)

    def test_shared_python_module_is_copied_verbatim_and_helper_runs_in_every_layout(self) -> None:
        fixture = make_repo_fixture(self, with_dist=False)
        self.add_probe(fixture)
        source = (fixture / "plugins" / "coding-workflows" / "references" / "sharedmod.py").read_bytes()
        out = temp_dir(self)
        work = work_mode_packages.build_packages(fixture, out / "work-mode")
        claude = claude_app_packages.build_packages(fixture, out / "claude-app")
        agent_skill_packages.build_packages(fixture)
        base = fixture / "plugins" / "coding-workflows"
        package_roots = {
            "work-mode": work / "repo-xray",
            "portable": base / "agent-skills" / "dist" / "skills" / "repo-xray",
            "gemini": base / "gemini" / "dist" / "skills" / "repo-xray",
            "kimi": base / "kimi" / "dist" / "skills" / "repo-xray",
        }
        extracted = out / "zip"
        with zipfile.ZipFile(claude / "repo-xray.zip") as archive:
            self.assertEqual(source, archive.read("repo-xray/references/sharedmod.py"))
            archive.extractall(extracted)
        package_roots["claude-app"] = extracted / "repo-xray"
        layouts = {"canonical": base / "skills" / "repo-xray", **package_roots}
        for label, root in layouts.items():
            with self.subTest(layout=label):
                if label != "canonical":
                    self.assertEqual(source, (root / "references" / "sharedmod.py").read_bytes())
                    skill_text = (root / "SKILL.md").read_text(encoding="utf-8")
                    self.assertIn("`references/sharedmod.py`", skill_text)
                    self.assertNotIn("../../references/sharedmod.py", skill_text)
                result = run_python(root / "scripts" / "probe.py")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("shared-module-ok", result.stdout)
        # A CRLF checkout (Windows with `*.py text`): directory packages keep the checkout's bytes,
        # while claude.ai ZIPs store the canonical LF bytes so they stay identical across platforms.
        shared = base / "references" / "sharedmod.py"
        shared.write_bytes(source.replace(b"\n", b"\r\n"))
        crlf_work = work_mode_packages.build_packages(fixture, out / "work-mode-crlf")
        self.assertEqual(shared.read_bytes(), (crlf_work / "repo-xray" / "references" / "sharedmod.py").read_bytes())
        crlf_claude = claude_app_packages.build_packages(fixture, out / "claude-app-crlf")
        with zipfile.ZipFile(crlf_claude / "repo-xray.zip") as archive:
            self.assertEqual(source, archive.read("repo-xray/references/sharedmod.py"))
        shared.write_bytes(source)
        # Fast path: component-layout checks are structural, not currency checks.
        errors = VALIDATOR.validate(fixture, tracked_files=[], check_generated_packages=False)
        self.assertFalse(any("component path" in e for e in errors), errors)
        nested = base / "gemini" / "dist" / "skills" / "repo-xray" / "scripts" / "extra" / "x.py"
        nested.parent.mkdir()
        nested.write_text('"""Doc."""\n', encoding="utf-8")
        errors = VALIDATOR.validate(fixture, tracked_files=[], check_generated_packages=False)
        self.assertTrue(any("forbidden component path" in e and "extra/x.py" in e for e in errors), errors)

    def test_inventory_lists_helpers_with_their_subprocess_policy(self) -> None:
        fixture = make_repo_fixture(self, with_dist=False)
        self.add_probe(fixture)
        work_mode_packages.build_packages(fixture)
        claude_app_packages.build_packages(fixture)
        agent_skill_packages.build_packages(fixture)
        # Fast path: subject is helper inventory content, not package currency.
        inventory = collect_inventory(fixture, check_generated_packages=False)
        paths = {item["path"]: item for item in inventory["helpers"]}
        self.assertEqual("", paths["plugins/coding-workflows/skills/repo-xray/scripts/probe.py"]["subprocess"])
        self.assertTrue(paths["plugins/coding-workflows/references/sharedmod.py"]["shared"])
        rendered = render_inventory(inventory)
        self.assertIn("`plugins/coding-workflows/skills/repo-xray/scripts/probe.py` | none | Probe helper", rendered)


SHIM_START = "_HERE = Path(__file__).resolve().parent\n"


def shipped_helpers() -> list[Path]:
    return sorted(SKILLS.glob("*/scripts/*.py"))


class ShippedHelperTests(unittest.TestCase):
    """Checks that apply to every helper actually shipped in the canonical tree."""

    def test_every_shipped_helper_compiles_for_python_311(self) -> None:
        import py_compile

        out = temp_dir(self)
        shared = sorted((ROOT / "plugins" / "coding-workflows" / "references").glob("*.py"))
        for path in [*shipped_helpers(), *shared]:
            with self.subTest(helper=path.name):
                py_compile.compile(str(path), cfile=str(out / f"{path.stem}.pyc"), doraise=True)

    def test_shared_module_import_shim_is_identical(self) -> None:
        shims = set()
        for path in shipped_helpers():
            text = path.read_text(encoding="utf-8")
            if "import cw_scan" not in text:
                continue
            start = text.index(SHIM_START)
            shims.add(text[start : text.index("import cw_scan", start)])
        self.assertLessEqual(len(shims), 1, shims)

    def test_every_shipped_helper_runs_from_every_distribution_layout(self) -> None:
        # TEST-PERF: the full helper x layout cross product (7x6=42
        # subprocess launches) dominates Windows time via process creation
        # + AV scanning. Layout rewriting is uniform builder code, so prove
        # the matrix without the cross product: every helper runs in the
        # canonical layout, every layout file exists, and one representative
        # helper (checkpoint.py: cw_scan shared module + git subprocess)
        # runs in every layout.
        base = ROOT / "plugins" / "coding-workflows"
        extracted = temp_dir(self)
        helpers = shipped_helpers()
        for path in helpers:
            skill = path.parent.parent.name
            with zipfile.ZipFile(base / "claude-app" / "dist" / f"{skill}.zip") as archive:
                archive.extractall(extracted)
        representative = next(path for path in helpers if path.name == "checkpoint.py")
        representative_skill = representative.parent.parent.name
        representative_layouts = {
            "canonical": representative,
            "work-mode": base / "work-mode" / "dist" / representative_skill / "scripts" / representative.name,
            "portable": base / "agent-skills" / "dist" / "skills" / representative_skill / "scripts" / representative.name,
            "gemini": base / "gemini" / "dist" / "skills" / representative_skill / "scripts" / representative.name,
            "kimi": base / "kimi" / "dist" / "skills" / representative_skill / "scripts" / representative.name,
            "claude-app": extracted / representative_skill / "scripts" / representative.name,
        }
        for label, helper in representative_layouts.items():
            with self.subTest(helper=f"{representative_skill}/{representative.name}", layout=label):
                self.assertTrue(helper.is_file(), helper)
                result = run_python(helper, "--help")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("usage:", result.stdout)
        for path in helpers:
            skill = path.parent.parent.name
            layouts = {
                "canonical": path,
                "work-mode": base / "work-mode" / "dist" / skill / "scripts" / path.name,
                "portable": base / "agent-skills" / "dist" / "skills" / skill / "scripts" / path.name,
                "gemini": base / "gemini" / "dist" / "skills" / skill / "scripts" / path.name,
                "kimi": base / "kimi" / "dist" / "skills" / skill / "scripts" / path.name,
                "claude-app": extracted / skill / "scripts" / path.name,
            }
            for label, helper in layouts.items():
                with self.subTest(helper=f"{skill}/{path.name}", layout=label):
                    self.assertTrue(helper.is_file(), helper)
            # Distribution contract requires verbatim helper copies: every
            # generated layout must be byte-identical to canonical. Reads
            # only, no extra subprocess execution.
            canonical_bytes = path.read_bytes()
            for label in ("work-mode", "portable", "gemini", "kimi", "claude-app"):
                with self.subTest(helper=f"{skill}/{path.name}", layout=f"{label}-verbatim"):
                    self.assertEqual(canonical_bytes, layouts[label].read_bytes(), layouts[label])
            with self.subTest(helper=f"{skill}/{path.name}", layout="canonical"):
                result = run_python(path, "--help")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("usage:", result.stdout)


class LedgerTestDiscoveryTests(unittest.TestCase):
    def test_verified_findings_may_cite_tests_from_any_test_module(self) -> None:
        fixture = make_repo_fixture(self, with_dist=False)
        ledger = fixture / "docs" / "audit-findings.md"
        text = ledger.read_text(encoding="utf-8")
        lines = text.split("\n")
        index = next(i for i, line in enumerate(lines) if line.startswith("| AUTH-07 "))
        cells = lines[index].split(" | ")
        cells[2] = "verified_repository"
        probe = "test_" + "fixture_only_ledger_probe"
        cells[8] = f"Covered by `{probe}`."
        lines[index] = " | ".join(cells)
        ledger.write_text("\n".join(lines), encoding="utf-8")
        # Fast path: subject is ledger/test discovery, not package currency.
        errors = VALIDATOR.validate(fixture, tracked_files=[], check_generated_packages=False)
        self.assertTrue(any("AUTH-07 names missing tests" in e for e in errors), errors)
        (fixture / "tests" / "test_ledger_probe.py").write_text(
            f'"""Probe."""\n\n\ndef {probe}():\n    pass\n', encoding="utf-8"
        )
        errors = VALIDATOR.validate(fixture, tracked_files=[], check_generated_packages=False)
        self.assertFalse(any("AUTH-07" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
