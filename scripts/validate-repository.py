"""Validate the active Codex plugin, skills, agents, files, and source-of-truth rules."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote

import tomllib
from agent_skill_packages import validate_packages as validate_agent_skill_packages
from claude_app_packages import active_skill_names as active_claude_app_skills
from claude_app_packages import load_manifest as load_claude_app_manifest
from claude_app_packages import validate_packages as validate_claude_app_packages
from repository_inventory import (
    HELPER_SUBPROCESS_POLICY,
    PLUGIN_SHARED_ROOT,
    PLUGIN_SKILLS_ROOT,
    ROOT,
    collect_inventory,
    load_json,
    parse_skill_frontmatter,
    require_repository_path,
    resolve_skill_root,
    resolve_within,
    walk_repository,
)
from routing_evals import validate_eval_data
from work_mode_packages import SECRET_MATERIAL, validate_packages
from work_mode_packages import load_manifest as load_work_mode_manifest

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
PLUGIN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
AGENT_SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
AGENT_PLUGIN_NAME = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
AGENT_PLUGINS_SCHEMA_URI = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AGENT_PLUGIN_ALLOWED_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
AGENT_PLUGIN_AUTHOR_FIELDS = {"name", "email", "url"}
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
REQUIRED_PLUGIN_INTERFACE = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
}
CLAUDE_MARKETPLACE_FIELDS = {"name", "description", "owner", "plugins"}
CLAUDE_MARKETPLACE_ENTRY_FIELDS = {"name", "source", "description"}
CLAUDE_MARKETPLACE_OWNER_FIELDS = {"name", "url"}
CLAUDE_PLUGIN_FIELDS = {
    "name",
    "description",
    "version",
    "author",
    "homepage",
    "repository",
    "license",
}
CLAUDE_PLUGIN_AUTHOR_FIELDS = {"name", "url"}
CLAUDE_PLUGIN_FORBIDDEN_FIELDS = {
    "agents",
    "commands",
    "components",
    "context",
    "hooks",
    "lsp",
    "mcp",
    "mcpservers",
    "permissions",
    "prompts",
    "rules",
    "scripts",
    "settings",
    "skills",
    "statusline",
}
CLAUDE_PLUGIN_ALLOWED_TOP_LEVEL = {
    ".claude-plugin",
    ".codex-plugin",
    "agent-skills",
    "assets",
    "claude-app",
    "evals",
    "gemini",
    "kimi",
    "plugin.json",
    "references",
    "skills",
    "work-mode",
}
CLAUDE_PLUGIN_FORBIDDEN_COMPONENT_DIRECTORIES = {
    "agents",
    "commands",
    "components",
    "context",
    "hooks",
    "installables",
    "lsp",
    "mcp",
    "prompts",
    "rules",
    "scripts",
    "settings",
    "statusline",
    "status-line",
}
CLAUDE_PLUGIN_FORBIDDEN_COMPONENT_FILES = {
    ".mcp.json",
    "mcp.json",
    "settings.json",
    "settings.local.json",
}
HELPER_DENIED_MODULES = {
    "asyncio",
    "code",
    "codeop",
    "ctypes",
    "ftplib",
    "http",
    "imaplib",
    "importlib",
    "multiprocessing",
    "nntplib",
    "poplib",
    "pty",
    "runpy",
    "smtplib",
    "socket",
    "socketserver",
    "ssl",
    "telnetlib",
    "urllib.request",
    "urllib.robotparser",
    "webbrowser",
    "wsgiref",
    "xmlrpc",
}
HELPER_DENIED_OS_CALLS = {
    "system",
    "popen",
    "startfile",
    "fork",
    "forkpty",
    "posix_spawn",
    "posix_spawnp",
    *(f"exec{suffix}" for suffix in ("l", "le", "lp", "lpe", "v", "ve", "vp", "vpe")),
    *(f"spawn{suffix}" for suffix in ("l", "le", "lp", "lpe", "v", "ve", "vp", "vpe")),
}
HELPER_DENIED_BUILTINS = {"eval", "exec", "__import__"}
SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}
SHARED_REFERENCE_SUFFIXES = {".md", ".py"}
CLAUDE_AGENT_TOOLS = {"Read", "Grep", "Glob"}
PROJECT_AGENT_NAMES = {"reviewer", "verifier"}
AGENT_ROLE_CONTRACTS = {
    "reviewer": {
        "description": "Read-only change reviewer focused on correctness, security, regression risk, scope, and missing tests.",
        "role": ("Review the complete identified diff or change artifact", "diff-judge"),
        "authority": ("Do not edit files, commit, push, publish",),
    },
    "verifier": {
        "description": "Read-only completion verifier that maps acceptance criteria to direct evidence and exposes remaining gaps.",
        "role": ("Translate the requested outcome into observable acceptance checks", "verification-gate"),
        "authority": ("Do not repair failures, edit files, commit, push, publish", "inferred pass"),
    },
}
CODEX_AGENT_FIELDS = {"name", "description", "developer_instructions", "sandbox_mode"}
AGENT_MUTATION_AUTHORITY = re.compile(
    r"(?i)\b(?:may|can|allowed\s+to|authorized\s+to|permission\s+to|you\s+should)\s+(?:edit|write|run|execute|repair|commit|push|publish|deploy|merge)\b"
)
CURSOR_ENVIRONMENT_FIELDS = {"name", "install"}
CURSOR_ENVIRONMENT_NAME = "coding-agents"
CURSOR_ENVIRONMENT_INSTALL = "python3 -c 'import sys; assert sys.version_info >= (3, 11)' && python3 -m compileall -q scripts tests"
REMOVED_ROOTS = (
    "ai-research",
    "prompts",
    "mcp-servers",
    ("plugin" "-marketplace"),
    "docs/archive",
    "docs/archive-notes",
)
STALE_MARKERS = tuple(
    "".join(parts)
    for parts in (
        ("grok", "-memory-skill"),
        ("dario", "-core"),
        (".grok", "-plugin"),
        ("plugin", "-marketplace"),
    )
)
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HOST_SUPPORT_VERSION = re.compile(r"\*\*Package version:\*\* `([^`]+)`")
METADATA_SECTIONS = {
    "interface": {"display_name", "short_description", "default_prompt", "icon_small", "icon_large", "brand_color"},
    "policy": {"allow_implicit_invocation"},
}
REQUIRED_REPOSITORY_FILES = {
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    ".github/pull_request_template.md",
    "scripts/check-diff-whitespace.py",
    "docs/evaluations.md",
    "docs/releasing.md",
    "CLAUDE.md",
    "docs/claude-code.md",
    "docs/audit-findings.md",
    "docs/host-contracts/agent-plugins.md",
}
AUDIT_LEDGER_PATH = "docs/audit-findings.md"
AUDIT_STATUS_VALUES = {
    "open",
    "in_progress",
    "fixed_pending_regression",
    "verified_repository",
    "verified_live",
    "blocked",
    "deferred_with_evidence",
    "not_reproduced",
}
AUDIT_SEVERITY_VALUES = {"high", "medium", "low", "candidate"}
AUDIT_REQUIRED_IDS = {
    "PKG-01",
    "PKG-02",
    "PKG-03",
    "PKG-04",
    "PKG-05",
    "PKG-06",
    "INV-01",
    "AUTH-01",
    "AUTH-02",
    "AUTH-03",
    "AUTH-04",
    "AUTH-05",
    "AUTH-06",
    "EVAL-01",
    "EVAL-02",
    "EVAL-03",
    "EVAL-04",
    "EVAL-05",
    "EVAL-06",
    "SKILL-01",
    "SKILL-02",
    "SKILL-03",
    "SKILL-04",
    "SKILL-05",
    "SKILL-06",
    "SKILL-07",
    "HOST-01",
    "DOC-01",
    "DOC-02",
    "DOC-03",
    "CI-01",
    "CI-02",
    "CI-03",
    "CAP-01",
    "CAP-02",
    "CAP-03",
    "CAP-04",
    "CAP-05",
    "CAP-06",
    "CAP-07",
    "CAP-08",
    "CAP-09",
    "CAP-10",
    "CAP-11",
    "AUTH-07",
}
AUDIT_SECTIONS = (
    "Packaging and inventory",
    "Authority and trust boundaries",
    "Evaluation and diagnostics",
    "Skill contracts",
    "Host, documentation, and CI",
    "Evidence-gated candidates",
)
AUDIT_COLUMNS = (
    "ID",
    "Severity",
    "Status",
    "Target",
    "Evidence",
    "Affected files/components",
    "Intended fix",
    "Required regression test",
    "Verification",
    "Updated",
)
AUDIT_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d{2}$")
WORKFLOW_REQUIRED_STEPS = {
    "Check out repository",
    "Set up Python",
    "Validate repository contracts",
    "Check generated inventory",
    "Check Work Mode packages",
    "Check claude.ai packages",
    "Check Agent Skills and host packages",
    "Run repository-tool tests",
    "Compile Python tooling",
    "Check diff whitespace",
}
WORKFLOW_REQUIRED_COMMANDS = {
    "Validate repository contracts": "python scripts/validate-repository.py",
    "Check generated inventory": "python scripts/generate-inventory.py --check",
    "Check Work Mode packages": "python scripts/package-work-mode.py --check",
    "Check claude.ai packages": "python scripts/package-claude-app.py --check",
    "Check Agent Skills and host packages": "python scripts/package-agent-skills.py --check",
    "Run repository-tool tests": "python -m unittest discover -s tests -v",
    "Compile Python tooling": "python -m compileall -q scripts tests",
    "Check diff whitespace": "python scripts/check-diff-whitespace.py",
}
WORKFLOW_ACTION_PIN = re.compile(r"@[0-9a-fA-F]{40}$")
WORKFLOW_USES = re.compile(r"^\s*uses:\s*(\S+)")
WORKFLOW_VERSION = re.compile(r"\b(3\.\d+)\b")
WORKFLOW_STEP = re.compile(r"(?m)^(?P<indent>[ ]*)-[ ]+name:[ ]*(?P<name>[^\r\n#]+?)[ \t]*$")
# The reviewed trigger and strategy blocks are compared exactly (after comment
# and blank-line removal) so equivalent YAML spellings such as flow mappings,
# quoted keys, or alternative indentation cannot add filters or matrix
# mutations that the line-oriented checks would not recognize.
WORKFLOW_EXPECTED_TRIGGERS = (
    "on:",
    "  pull_request:",
    "  push:",
    "    branches: [main]",
    "  workflow_dispatch:",
)
WORKFLOW_EXPECTED_STRATEGY = (
    "    strategy:",
    "      fail-fast: false",
    "      matrix:",
    "        os: [ubuntu-latest, windows-latest]",
    '        python-version: ["3.11", "3.14"]',
)
WORKFLOW_SHELL_OVERRIDE = re.compile(r"""(?m)^\s*(?:-\s+)?["']?(?:shell|defaults)["']?\s*:""")
REPOSITORY_SECRET_MATERIAL = re.compile(
    r"(?i)(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|(?<![A-Za-z0-9_-])(?:sk-|gh[pousr]_|xox[baprs]-)[A-Za-z0-9_-]{16,}|(?<![A-Za-z0-9_-])AKIA[0-9A-Z]{16}(?![A-Za-z0-9_-]))"
)
DOC_COMMAND_FILES = (
    "AGENTS.md",
    "WORKFLOWS.md",
    "CONTRIBUTING.md",
    ".github/pull_request_template.md",
    "docs/coding-agents-program.md",
)
DOC_PACKAGE_COMMANDS = (
    "python scripts/package-work-mode.py --check",
    "python scripts/package-claude-app.py --check",
    "python scripts/package-agent-skills.py --check",
)
DOC_GENERATED_SURFACES = (
    "work-mode/dist/",
    "claude-app/dist/",
    "agent-skills/dist/",
    "gemini/dist/",
    "kimi/dist/",
)
MAX_VALIDATED_FILES = 1_000
MAX_VALIDATED_FILE_BYTES = 2_000_000
MAX_VALIDATED_TOTAL_BYTES = 20_000_000
MAX_VALIDATED_DIRECTORIES = 1_000
MAX_VALIDATED_ENTRIES = 5_000

# TEST-ONLY seam: generated-package currentness checks rebuild every package
# family, so each validate() call costs ~10-20s. Tests whose subject is
# unrelated to package currency may pass check_generated_packages=False.
# None and True keep full validation. Structural package checks still run on
# the fast path; only the rebuild comparisons are skipped.


def _package_currentness_enabled(check_generated_packages: bool | None) -> bool:
    return check_generated_packages is not False


def _unquote_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_openai_metadata(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Parse the deliberately small YAML subset used by this repository."""

    data: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    section: str | None = None
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if "\t" in raw_line:
            errors.append(f"{path.name}:{line_number} contains a tab; use two-space indentation.")
            continue
        if not raw_line.startswith(" "):
            if not raw_line.endswith(":"):
                errors.append(f"{path.name}:{line_number} must declare a top-level section.")
                section = None
                continue
            section = raw_line[:-1].strip()
            if section not in METADATA_SECTIONS:
                errors.append(f"{path.name}:{line_number} has unsupported section {section!r}.")
                section = None
                continue
            if section in data:
                errors.append(f"{path.name}:{line_number} duplicates section {section!r}.")
            data.setdefault(section, {})
            continue
        if not raw_line.startswith("  ") or raw_line.startswith("   ") or ":" not in raw_line:
            errors.append(f"{path.name}:{line_number} must use one two-space key level.")
            continue
        if section is None:
            errors.append(f"{path.name}:{line_number} has a key outside a supported section.")
            continue
        key, raw_value = raw_line.strip().split(":", 1)
        if key not in METADATA_SECTIONS[section]:
            errors.append(f"{path.name}:{line_number} has unsupported {section} key {key!r}.")
            continue
        if key in data[section]:
            errors.append(f"{path.name}:{line_number} duplicates {section}.{key}.")
            continue
        value = _unquote_yaml_scalar(raw_value)
        if not value:
            errors.append(f"{path.name}:{line_number} has an empty {section}.{key}.")
        data[section][key] = value
    return data, errors


def _read_text_artifact(
    root: Path,
    relative: str,
    reserve_file,
    errors: list[str],
    *,
    label: str | None = None,
) -> str | None:
    path = root / relative
    try:
        require_repository_path(path, root, label=label or relative)
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if not path.is_file():
        errors.append(f"Required text artifact is missing: {relative}")
        return None
    if not reserve_file(path):
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"Could not read text artifact {relative}: {exc}")
        return None


def _table_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _validate_audit_ledger(root: Path, reserve_file, errors: list[str]) -> None:
    text = _read_text_artifact(root, AUDIT_LEDGER_PATH, reserve_file, errors, label="Audit finding ledger")
    test_source = _read_text_artifact(
        root, "tests/test_repository_tools.py", reserve_file, errors, label="Repository regression tests"
    )
    if test_source is not None:
        # Verified findings may cite regression tests from any repository test module.
        for test_path in sorted((root / "tests").glob("test_*.py")):
            if test_path.name == "test_repository_tools.py":
                continue
            extra = _read_text_artifact(
                root, test_path.relative_to(root).as_posix(), reserve_file, errors, label="Repository regression tests"
            )
            if extra is not None:
                test_source += "\n" + extra
    if text is None:
        return
    for heading in ("## Status vocabulary", "## Baseline", *(f"## {section}" for section in AUDIT_SECTIONS)):
        if heading not in text:
            errors.append(f"Audit ledger is missing required section: {heading}")
    if not re.search(r"(?m)^- Baseline revision: `[0-9a-f]{40}`$", text):
        errors.append("Audit ledger baseline revision must be a full commit SHA.")
    if not re.search(r"(?m)^- Baseline date: \d{4}-\d{2}-\d{2}$", text):
        errors.append("Audit ledger baseline date must be ISO-8601.")
    if not re.search(r"(?m)^- Repository validator: .+$", text):
        errors.append("Audit ledger must record repository validator evidence.")
    if not re.search(r"(?m)^- Tests: .+$", text):
        errors.append("Audit ledger must record test evidence.")

    seen: dict[str, str] = {}
    for section in AUDIT_SECTIONS:
        heading = f"## {section}"
        start = text.find(heading)
        if start < 0:
            continue
        next_heading = text.find("\n## ", start + len(heading))
        end = len(text) if next_heading < 0 else next_heading
        section_text = text[start:end]
        table_lines = [line for line in section_text.splitlines() if line.strip().startswith("|")]
        if len(table_lines) < 2:
            errors.append(f"Audit ledger section has no finding table: {section}")
            continue
        header = _table_cells(table_lines[0])
        if header != list(AUDIT_COLUMNS):
            errors.append(f"Audit ledger table header is invalid in section: {section}")
        for line in table_lines[2:]:
            cells = _table_cells(line)
            if cells is None or len(cells) != len(AUDIT_COLUMNS):
                errors.append(f"Audit ledger row has an invalid column count in section: {section}")
                continue
            values = [cell.strip().strip("`") for cell in cells]
            finding_id, severity, status, target, evidence, affected, fix, regression, verification, updated = values
            if not AUDIT_ID_PATTERN.fullmatch(finding_id):
                errors.append(f"Audit ledger has an invalid finding ID: {finding_id!r}")
                continue
            if finding_id in seen:
                errors.append(f"Audit ledger has duplicate finding ID: {finding_id}")
            else:
                seen[finding_id] = section
            if severity not in AUDIT_SEVERITY_VALUES:
                errors.append(f"Audit ledger finding {finding_id} has an invalid severity: {severity!r}")
            if status not in AUDIT_STATUS_VALUES:
                errors.append(f"Audit ledger finding {finding_id} has an invalid status: {status!r}")
            if not target.startswith("Phase "):
                errors.append(f"Audit ledger finding {finding_id} has an invalid target: {target!r}")
            for field, value in (
                ("evidence", evidence),
                ("affected", affected),
                ("fix", fix),
                ("regression", regression),
                ("verification", verification),
            ):
                if not value:
                    errors.append(f"Audit ledger finding {finding_id} has an empty {field}.")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
                errors.append(f"Audit ledger finding {finding_id} has an invalid updated date: {updated!r}")
            if status in {"verified_repository", "verified_live", "deferred_with_evidence", "not_reproduced"} and verification.casefold() == "pending":
                errors.append(f"Audit ledger finding {finding_id} is verified without verification evidence.")
            if status in {"verified_repository", "verified_live"}:
                test_names = re.findall(r"`(test_[A-Za-z0-9_]+)`", verification)
                if not test_names:
                    errors.append(f"Audit ledger finding {finding_id} must name a committed regression test.")
                elif test_source is not None:
                    missing_tests = sorted(
                        name for name in test_names if f"def {name}(" not in test_source
                    )
                    if missing_tests:
                        errors.append(f"Audit ledger finding {finding_id} names missing tests: {missing_tests}.")
    missing = sorted(AUDIT_REQUIRED_IDS - seen.keys())
    if missing:
        errors.append(f"Audit ledger is missing required finding IDs: {missing}")


def _validate_cursor_environment(root: Path, reserve_file, errors: list[str]) -> None:
    path = root / ".cursor" / "environment.json"
    try:
        require_repository_path(path, root, label="Cursor environment")
        if not path.is_file():
            errors.append("Cursor environment is missing: .cursor/environment.json")
            return
        if not reserve_file(path):
            return
        data = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid Cursor environment: {exc}")
        return
    if not isinstance(data, dict):
        errors.append("Cursor environment must be a JSON object.")
        return
    fields = set(data)
    unknown = sorted(fields - CURSOR_ENVIRONMENT_FIELDS)
    missing = sorted(CURSOR_ENVIRONMENT_FIELDS - fields)
    if unknown:
        errors.append(f"Cursor environment has unsupported fields: {unknown}")
    if missing:
        errors.append(f"Cursor environment is missing fields: {missing}")
    if data.get("name") != CURSOR_ENVIRONMENT_NAME:
        errors.append("Cursor environment name must be coding-agents.")
    if data.get("install") != CURSOR_ENVIRONMENT_INSTALL:
        errors.append("Cursor environment install must be the reviewed compileall command.")


def _normalize_contract_text(text: str) -> str:
    return " ".join(text.casefold().split())


def _validate_agent_role_parity(
    name: str,
    codex_agent: dict[str, object] | None,
    claude_agent: dict[str, object] | None,
    errors: list[str],
) -> None:
    contract = AGENT_ROLE_CONTRACTS.get(name)
    if contract is None or codex_agent is None or claude_agent is None:
        return
    surfaces = {
        "Codex": (
            f"{codex_agent.get('description', '')}\n{codex_agent.get('developer_instructions', '')}",
            str(codex_agent.get("description", "")),
        ),
        "Claude": (
            f"{claude_agent.get('description', '')}\n{claude_agent.get('body', '')}",
            str(claude_agent.get("description", "")),
        ),
    }
    expected_description = str(contract["description"])
    for surface, (combined, description) in surfaces.items():
        normalized_combined = _normalize_contract_text(combined)
        normalized_description = _normalize_contract_text(description)
        if normalized_description != _normalize_contract_text(expected_description) and not (
            surface == "Claude" and normalized_description.startswith(_normalize_contract_text(expected_description))
        ):
            errors.append(f"{surface} project agent {name} has an invalid role description.")
        missing = [
            fragment
            for fragment in (*contract["role"], *contract["authority"])
            if _normalize_contract_text(fragment) not in normalized_combined
        ]
        if missing:
            errors.append(f"{surface} project agent {name} is missing required role or authority text: {missing}.")
        if AGENT_MUTATION_AUTHORITY.search(combined):
            errors.append(f"{surface} project agent {name} grants a mutating authority term.")


GENERATED_SKILL_ROOTS = (
    ("agent-skills", "dist", "skills"),
    ("gemini", "dist", "skills"),
    ("kimi", "dist", "skills"),
    ("work-mode", "dist"),
)


def _is_generated_skill_helper(parts: tuple[str, ...]) -> bool:
    """A generated package's copy of a canonical `skills/<name>/scripts/<file>.py` helper."""

    for prefix in GENERATED_SKILL_ROOTS:
        rest = parts[len(prefix):]
        if parts[: len(prefix)] == prefix and len(rest) == 3 and rest[1] == "scripts" and rest[2].endswith(".py"):
            return True
    return False


def _validate_claude_component_layout(
    root: Path,
    plugin_root: Path,
    repository_files: list[Path],
    errors: list[str],
) -> None:
    try:
        entries = {path.name for path in plugin_root.iterdir()}
    except OSError as exc:
        errors.append(f"Could not inspect Claude plugin root: {exc}")
        return
    unknown = sorted(entries - CLAUDE_PLUGIN_ALLOWED_TOP_LEVEL)
    missing = sorted(CLAUDE_PLUGIN_ALLOWED_TOP_LEVEL - entries)
    if unknown:
        errors.append(f"Claude plugin has unsupported top-level entries: {unknown}")
    if missing:
        errors.append(f"Claude plugin is missing required top-level entries: {missing}")
    for directory, expected in (
        (root / ".claude-plugin", {"marketplace.json"}),
        (plugin_root / ".claude-plugin", {"plugin.json"}),
    ):
        try:
            actual = {path.name for path in directory.iterdir()}
        except OSError as exc:
            errors.append(f"Could not inspect Claude metadata directory: {exc}")
            continue
        if actual != expected:
            errors.append(f"Claude metadata directory has unexpected entries: {sorted(actual)}")
    for path in repository_files:
        try:
            relative = path.relative_to(plugin_root)
        except ValueError:
            continue
        parts = tuple(part.casefold() for part in relative.parts)
        if not parts:
            continue
        if parts[0] == "skills":
            allowed_codex_metadata = len(parts) == 4 and parts[2] == "agents" and parts[3] == "openai.yaml"
            # Reviewed Python helpers live exactly one level below a skill's scripts/
            # directory; the helper policy below governs their content.
            allowed_skill_helper = len(parts) == 4 and parts[2] == "scripts" and relative.suffix == ".py"
            skill_parts = parts[2:]
            if not (
                len(parts) == 2
                or parts[-1] == "skill.md"
                or allowed_codex_metadata
                or allowed_skill_helper
                or not any(part in CLAUDE_PLUGIN_FORBIDDEN_COMPONENT_DIRECTORIES for part in skill_parts)
            ):
                errors.append(f"Claude plugin skill has an unexpected component path: {relative.as_posix()}")
            if parts[-1] in CLAUDE_PLUGIN_FORBIDDEN_COMPONENT_FILES:
                errors.append(f"Claude plugin contains a forbidden component file: {relative.as_posix()}")
            continue
        if _is_generated_skill_helper(parts):
            continue
        if any(part in CLAUDE_PLUGIN_FORBIDDEN_COMPONENT_DIRECTORIES for part in parts[:-1]):
            errors.append(f"Claude plugin contains a forbidden component path: {relative.as_posix()}")
        if parts[-1] in CLAUDE_PLUGIN_FORBIDDEN_COMPONENT_FILES:
            errors.append(f"Claude plugin contains a forbidden component file: {relative.as_posix()}")


def _imported_module_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return ["."]
        base = node.module or ""
        return [base, *(f"{base}.{alias.name}" for alias in node.names)]
    return []


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    return (
        isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _helper_policy_errors(
    label: str,
    source: str,
    *,
    policy: tuple[str, ...],
    shared_modules: set[str],
    skill_text: str | None,
    is_helper: bool,
) -> list[str]:
    """Check one shipped Python helper or shared module against the helper policy."""

    errors: list[str] = []
    try:
        module = ast.parse(source, feature_version=(3, 11))
    except SyntaxError as exc:
        return [f"{label} is not valid Python 3.11 source: {exc.msg} (line {exc.lineno})."]
    if not ast.get_docstring(module):
        errors.append(f"{label} must start with a module docstring.")
    if is_helper and not any(_is_main_guard(node) for node in module.body):
        errors.append(f"{label} must run only behind an if __name__ == \"__main__\" guard.")
    subprocess_aliases: set[str] = set()
    subprocess_functions: dict[str, str] = {}
    for node in ast.walk(module):
        for name in _imported_module_names(node):
            if name == ".":
                errors.append(f"{label} must not use relative imports.")
                continue
            if not name:
                continue
            top = name.split(".", 1)[0]
            if any(name == denied or name.startswith(f"{denied}.") for denied in HELPER_DENIED_MODULES):
                errors.append(f"{label} imports a denied network or dynamic-execution module: {name}.")
            if isinstance(node, ast.ImportFrom) and node.module == "os" and name.split(".")[-1] in HELPER_DENIED_OS_CALLS:
                errors.append(f"{label} imports a denied process function: {name}.")
            if top in shared_modules:
                if not is_helper:
                    errors.append(f"{label} is a shared module and may import only the standard library.")
                elif skill_text is not None and f"../../references/{top}.py" not in skill_text:
                    errors.append(
                        f"{label} imports shared module {top} that its SKILL.md does not name as ../../references/{top}.py."
                    )
            elif top not in sys.stdlib_module_names:
                errors.append(f"{label} imports a non-standard-library module: {top}.")
            if top == "subprocess":
                if not policy:
                    errors.append(f"{label} imports subprocess without a helper-specific allowance.")
                if isinstance(node, ast.Import):
                    subprocess_aliases.update(alias.asname or alias.name for alias in node.names if alias.name == "subprocess")
                elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                    subprocess_functions.update((alias.asname or alias.name, alias.name) for alias in node.names)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os" and node.attr in HELPER_DENIED_OS_CALLS:
            errors.append(f"{label} uses a denied process function: os.{node.attr} (line {node.lineno}).")
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in HELPER_DENIED_BUILTINS:
            errors.append(f"{label} calls {node.func.id} (line {node.lineno}).")
        for keyword in node.keywords:
            if keyword.arg == "shell" and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is False):
                errors.append(f"{label} requests shell execution (line {node.lineno}).")
        called = None
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id in subprocess_aliases:
            called = node.func.attr
        elif isinstance(node.func, ast.Name) and node.func.id in subprocess_functions:
            called = subprocess_functions[node.func.id]
        if called is None:
            continue
        if called not in SUBPROCESS_CALLS - {"getoutput", "getstatusoutput"}:
            errors.append(f"{label} uses an unsupported subprocess entry point: {called} (line {node.lineno}).")
            continue
        if "approved-plan" in policy:
            continue
        argv = node.args[0] if node.args else None
        if not (
            isinstance(argv, (ast.List, ast.Tuple))
            and argv.elts
            and isinstance(argv.elts[0], ast.Constant)
            and argv.elts[0].value == "git"
        ):
            errors.append(f"{label} may start only git with a literal argv list (line {node.lineno}).")
    return errors


def _validate_skill_helpers(root: Path, repository_files: list[Path], reserve_file, errors: list[str]) -> None:
    """Validate the narrow executable-helper boundary and orphaned skill support files."""

    skills_root = root.joinpath(*PLUGIN_SKILLS_ROOT)
    shared_root = root.joinpath(*PLUGIN_SHARED_ROOT)
    skill_texts: dict[str, str] = {}
    skill_support: dict[str, list[Path]] = {}
    shared_files: list[Path] = []
    for path in repository_files:
        try:
            relative = path.relative_to(skills_root)
        except ValueError:
            if path.parent == shared_root:
                shared_files.append(path)
            continue
        if len(relative.parts) < 2:
            continue
        skill = relative.parts[0]
        if relative.parts[1:] == ("SKILL.md",):
            try:
                if reserve_file(path):
                    skill_texts[skill] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"Could not read {path.relative_to(root).as_posix()}: {exc}")
        elif relative.parts[1] in {"references", "scripts"}:
            skill_support.setdefault(skill, []).append(path)
    shared_modules = {path.stem for path in shared_files if path.suffix == ".py"}
    all_skill_text = "\n".join(skill_texts.values())
    shared_markdown: dict[Path, str] = {}
    for path in shared_files:
        name = path.relative_to(root).as_posix()
        if path.suffix not in SHARED_REFERENCE_SUFFIXES:
            errors.append(f"Shared reference has an unsupported type: {name}")
            continue
        try:
            if not reserve_file(path):
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"Could not read shared reference {name}: {exc}")
            continue
        if path.suffix == ".md":
            shared_markdown[path] = text
            continue
        errors.extend(
            _helper_policy_errors(
                f"Shared module {name}", text, policy=(), shared_modules=shared_modules, skill_text=None, is_helper=False
            )
        )
    for path in shared_files:
        if path.suffix not in SHARED_REFERENCE_SUFFIXES:
            continue
        mentioned_by_skill = f"references/{path.name}" in all_skill_text
        mentioned_by_reference = path.suffix == ".md" and any(
            f"./{path.name}" in text for other, text in shared_markdown.items() if other != path
        )
        if not mentioned_by_skill and not mentioned_by_reference:
            errors.append(f"Shared reference has no consumer: {path.relative_to(root).as_posix()}")
    for skill, paths in sorted(skill_support.items()):
        skill_text = skill_texts.get(skill, "")
        for path in sorted(paths):
            local = path.relative_to(skills_root / skill).as_posix()
            name = path.relative_to(root).as_posix()
            if local not in skill_text:
                errors.append(f"Skill support file is not referenced by its SKILL.md: {name}")
            if not local.startswith("scripts/"):
                continue
            if path.suffix != ".py" or len(path.relative_to(skills_root / skill).parts) != 2:
                continue  # rejected by the Claude component layout check
            try:
                if not reserve_file(path):
                    continue
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"Could not read skill helper {name}: {exc}")
                continue
            errors.extend(
                _helper_policy_errors(
                    f"Skill helper {name}",
                    source,
                    policy=HELPER_SUBPROCESS_POLICY.get(f"{skill}/{local}", ()),
                    shared_modules=shared_modules,
                    skill_text=skill_text,
                    is_helper=True,
                )
            )


def _validate_plugin_interface(plugin_root: Path, manifest: dict[str, object], errors: list[str]) -> None:
    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append(f"Plugin {plugin_root.name} interface must be an object.")
        return
    missing = REQUIRED_PLUGIN_INTERFACE - set(interface)
    if missing:
        errors.append(f"Plugin {plugin_root.name} is missing interface fields: {sorted(missing)}")
    limits = {
        "displayName": 30,
        "shortDescription": 30,
        "longDescription": 4000,
        "developerName": 80,
    }
    for field, maximum in limits.items():
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Plugin {plugin_root.name} interface.{field} must be a non-empty string.")
        elif field != "longDescription" and ("\n" in value or "\r" in value):
            errors.append(f"Plugin {plugin_root.name} interface.{field} must be one line.")
        elif len(value) > maximum:
            errors.append(f"Plugin {plugin_root.name} interface.{field} exceeds {maximum} characters.")
    capabilities = interface.get("capabilities")
    if not isinstance(capabilities, list) or not 1 <= len(capabilities) <= 20 or not all(
        isinstance(item, str) and item.strip() and "\n" not in item and len(item) <= 120 for item in capabilities
    ):
        errors.append(f"Plugin {plugin_root.name} interface.capabilities is invalid.")
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3 or not all(
        isinstance(item, str) and item.strip() and "\n" not in item and len(item) <= 128 for item in prompts
    ):
        errors.append(f"Plugin {plugin_root.name} interface.defaultPrompt must contain one to three one-line prompts of at most 128 characters.")
    elif len({" ".join(item.split()).casefold() for item in prompts}) != len(prompts):
        errors.append(f"Plugin {plugin_root.name} interface.defaultPrompt contains duplicates.")
    brand_color = interface.get("brandColor")
    if not isinstance(brand_color, str) or HEX_COLOR.fullmatch(brand_color) is None:
        errors.append(f"Plugin {plugin_root.name} interface.brandColor must use #RRGGBB.")
    for field in ("composerIcon", "logo"):
        raw_path = interface.get(field)
        if not isinstance(raw_path, str) or not raw_path.startswith("./"):
            errors.append(f"Plugin {plugin_root.name} interface.{field} must be a ./-relative asset path.")
            continue
        try:
            resolved = resolve_within(
                plugin_root / raw_path[2:],
                plugin_root,
                label=f"Plugin {plugin_root.name} interface.{field}",
            )
        except ValueError:
            errors.append(f"Plugin {plugin_root.name} interface.{field} escapes the plugin root.")
            continue
        if not resolved.is_file():
            errors.append(f"Plugin {plugin_root.name} interface.{field} does not exist: {raw_path}")
    screenshots = interface.get("screenshots")
    if screenshots and "mcpServers" not in manifest:
        errors.append(f"Plugin {plugin_root.name} is skills-only and must not declare screenshots.")


def _validate_claude_distribution(
    root: Path,
    reserve_file,
    codex_manifests: dict[str, dict[str, object]],
    codex_agent_names: set[str],
    errors: list[str],
    codex_agents: dict[str, dict[str, object]] | None = None,
    repository_files: list[Path] | None = None,
) -> None:
    """Validate the closed Claude marketplace/plugin and project-agent contracts."""

    plugin_root = root / "plugins" / "coding-workflows"
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    try:
        require_repository_path(marketplace_path, root, label="Claude marketplace")
        if not reserve_file(marketplace_path):
            return
        marketplace = load_json(marketplace_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid Claude marketplace: {exc}")
        return
    if not isinstance(marketplace, dict):
        errors.append("Invalid Claude marketplace: expected a JSON object.")
        return
    marketplace_fields = set(marketplace)
    unknown = sorted(marketplace_fields - CLAUDE_MARKETPLACE_FIELDS)
    missing = sorted(CLAUDE_MARKETPLACE_FIELDS - marketplace_fields)
    if unknown:
        errors.append(f"Claude marketplace has unsupported top-level fields: {unknown}")
    if missing:
        errors.append(f"Claude marketplace is missing required top-level fields: {missing}")
    if marketplace.get("name") != "coding-agents":
        errors.append("Claude marketplace name must be coding-agents.")
    if not isinstance(marketplace.get("description"), str) or not marketplace.get("description", "").strip():
        errors.append("Claude marketplace is missing a description.")
    owner = marketplace.get("owner")
    if not isinstance(owner, dict) or set(owner) != CLAUDE_MARKETPLACE_OWNER_FIELDS:
        errors.append("Claude marketplace owner must contain exactly name and url.")
    elif not all(isinstance(owner.get(field), str) and owner[field].strip() for field in CLAUDE_MARKETPLACE_OWNER_FIELDS):
        errors.append("Claude marketplace owner fields must be non-empty strings.")
    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or len(entries) != 1:
        errors.append("Claude marketplace must contain exactly one coding-workflows plugin entry.")
        entries = entries if isinstance(entries, list) else []
    entry_names: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("Claude marketplace plugin entry must be an object.")
            continue
        entry_fields = set(entry)
        unknown_entry = sorted(entry_fields - CLAUDE_MARKETPLACE_ENTRY_FIELDS)
        missing_entry = sorted(CLAUDE_MARKETPLACE_ENTRY_FIELDS - entry_fields)
        if unknown_entry:
            errors.append(f"Claude marketplace coding-workflows entry has unsupported fields: {unknown_entry}")
        if missing_entry:
            errors.append(f"Claude marketplace coding-workflows entry is missing fields: {missing_entry}")
        name = entry.get("name")
        if not isinstance(name, str):
            errors.append("Claude marketplace plugin entry is missing a name.")
        else:
            entry_names.append(name)
            if name != "coding-workflows":
                errors.append(f"Claude marketplace contains an unknown plugin entry: {name!r}.")
        if entry.get("source") != "./plugins/coding-workflows":
            errors.append("Claude marketplace coding-workflows source must be ./plugins/coding-workflows.")
        if not isinstance(entry.get("description"), str) or not entry.get("description", "").strip():
            errors.append("Claude marketplace coding-workflows entry is missing a description.")
    if entry_names.count("coding-workflows") > 1:
        errors.append("Claude marketplace contains duplicate coding-workflows entries.")
    if "coding-workflows" not in entry_names:
        errors.append("Claude marketplace is missing the coding-workflows plugin entry.")

    plugin_manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
    try:
        require_repository_path(plugin_manifest_path, root, label="Claude plugin manifest")
        if not reserve_file(plugin_manifest_path):
            return
        plugin_manifest = load_json(plugin_manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid Claude plugin manifest: {exc}")
        return
    if not isinstance(plugin_manifest, dict):
        errors.append("Invalid Claude plugin manifest: expected a JSON object.")
        return
    manifest_fields = set(plugin_manifest)
    unknown = sorted(manifest_fields - CLAUDE_PLUGIN_FIELDS)
    missing = sorted(CLAUDE_PLUGIN_FIELDS - manifest_fields)
    if unknown:
        errors.append(f"Claude plugin manifest has unsupported top-level fields: {unknown}")
    if missing:
        errors.append(f"Claude plugin manifest is missing required metadata fields: {missing}")
    forbidden_fields = sorted(
        field for field in plugin_manifest if str(field).casefold() in CLAUDE_PLUGIN_FORBIDDEN_FIELDS
    )
    if forbidden_fields:
        errors.append(f"Claude plugin manifest declares forbidden component fields: {forbidden_fields}")
    if plugin_manifest.get("name") != "coding-workflows":
        errors.append("Claude plugin manifest name must be coding-workflows.")
    if not isinstance(plugin_manifest.get("description"), str) or not plugin_manifest.get("description", "").strip():
        errors.append("Claude plugin manifest is missing a description.")
    if not isinstance(plugin_manifest.get("version"), str) or SEMVER.fullmatch(plugin_manifest.get("version", "")) is None:
        errors.append("Claude plugin manifest has invalid semver.")
    if plugin_manifest.get("license") != "MIT":
        errors.append("Claude plugin manifest must declare the MIT license.")
    for field in ("homepage", "repository"):
        if not isinstance(plugin_manifest.get(field), str) or not plugin_manifest[field].strip():
            errors.append(f"Claude plugin manifest is missing {field}.")
    author = plugin_manifest.get("author")
    if not isinstance(author, dict) or set(author) != CLAUDE_PLUGIN_AUTHOR_FIELDS:
        errors.append("Claude plugin manifest author must contain exactly name and url.")
    elif not all(isinstance(author.get(field), str) and author[field].strip() for field in CLAUDE_PLUGIN_AUTHOR_FIELDS):
        errors.append("Claude plugin manifest author fields must be non-empty strings.")
    if "skills" in plugin_manifest:
        errors.append(
            "Claude plugin manifest must not declare a skills path; it relies on the default "
            "skills/ directory shared with the Codex plugin."
        )
    codex_manifest = codex_manifests.get("coding-workflows")
    if codex_manifest is not None and plugin_manifest.get("version") != codex_manifest.get("version"):
        errors.append(
            "Claude plugin manifest version must match plugins/coding-workflows/.codex-plugin/plugin.json."
        )
    if repository_files is None:
        repository_files = [path for path in plugin_root.rglob("*") if path.is_file()]
    _validate_claude_component_layout(root, plugin_root, repository_files, errors)

    claude_agent_root = root / ".claude" / "agents"
    claude_agent_names: set[str] = set()
    claude_agents: dict[str, dict[str, object]] = {}
    if not claude_agent_root.is_dir():
        errors.append("Claude project agent directory is missing.")
    else:
        try:
            agent_paths = sorted(claude_agent_root.iterdir())
        except OSError as exc:
            errors.append(f"Could not inspect Claude project agents: {exc}")
            agent_paths = []
        for path in agent_paths:
            if path.suffix.casefold() != ".md":
                errors.append(f"Claude project agent directory contains an unsupported file: {path.name}.")
                continue
            try:
                require_repository_path(path, root, label=f"Claude subagent {path.name}")
                if not reserve_file(path):
                    continue
                source = path.read_text(encoding="utf-8")
                metadata = parse_skill_frontmatter(path)
            except (OSError, ValueError, UnicodeDecodeError) as exc:
                errors.append(str(exc))
                continue
            metadata_fields = set(metadata)
            unknown_metadata = sorted(metadata_fields - {"name", "description", "tools"})
            if unknown_metadata:
                errors.append(f"Claude subagent {path.name} has unsupported frontmatter fields: {unknown_metadata}")
            name = metadata.get("name", "")
            if name != path.stem:
                errors.append(f"Claude subagent file {path.name} does not match name {name!r}.")
            if name in claude_agent_names:
                errors.append(f"Duplicate Claude project agent name: {name!r}.")
            claude_agent_names.add(name)
            description = metadata.get("description", "")
            if not isinstance(description, str) or not description.strip():
                errors.append(f"Claude subagent {name or path.name} is missing a description.")
            tools_raw = metadata.get("tools", "")
            tool_items = [item.strip() for item in tools_raw.split(",")] if isinstance(tools_raw, str) else []
            tools = {item for item in tool_items if item}
            if (
                not tools
                or any(not item for item in tool_items)
                or len(tools) != len(tool_items)
                or tools != CLAUDE_AGENT_TOOLS
            ):
                errors.append(
                    f"Claude subagent {name or path.name} must stay read-only and use the exact Read, Grep, and Glob allowlist; "
                    f"remove {sorted(tools - CLAUDE_AGENT_TOOLS)} and declare no other tools."
                )
            claude_agents[name] = {
                "description": description,
                "body": source,
            }
            if name not in PROJECT_AGENT_NAMES:
                errors.append(f"Unsupported Claude project agent: {name!r}.")

    if claude_agent_names != codex_agent_names:
        errors.append(
            "Claude/Codex project agent mismatch: "
            f"claude={sorted(claude_agent_names)}, codex={sorted(codex_agent_names)}"
        )
    if claude_agent_names != PROJECT_AGENT_NAMES or codex_agent_names != PROJECT_AGENT_NAMES:
        errors.append(
            "Project agent names must be exactly reviewer and verifier: "
            f"claude={sorted(claude_agent_names)}, codex={sorted(codex_agent_names)}"
        )
    if codex_agents is not None:
        for name in sorted(PROJECT_AGENT_NAMES & set(codex_agents) & set(claude_agents)):
            _validate_agent_role_parity(name, codex_agents[name], claude_agents[name], errors)


def _validate_agent_plugins_distribution(
    root: Path,
    reserve_file,
    skill_names: set[str],
    codex_manifests: dict[str, dict[str, object]],
    errors: list[str],
) -> None:
    """Validate the Agent Plugins 1.0.0 portable floor for coding-workflows.

    This checks repository structure against the fetched Agent Plugins
    Specification 1.0.0 closed ``plugin.json`` schema and fixed ``skills/``
    discovery rules. It does not claim that any client has loaded the plugin.
    MCP packaging is out of scope: a present ``mcp.json`` is a contract
    violation here even though the specification treats a missing file as
    optional.
    """

    plugin_dir = root / "plugins" / "coding-workflows"
    try:
        require_repository_path(plugin_dir, root, label="Agent Plugins plugin root")
    except ValueError as exc:
        errors.append(str(exc))
        return
    if not plugin_dir.is_dir():
        errors.append("Agent Plugins plugin root is missing: plugins/coding-workflows")
        return

    manifest_path = plugin_dir / "plugin.json"
    try:
        require_repository_path(manifest_path, root, label="Agent Plugins plugin.json")
        if not reserve_file(manifest_path):
            return
        manifest = load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid or missing Agent Plugins plugin.json: {exc}")
        manifest = None
    else:
        if not isinstance(manifest, dict):
            errors.append("Agent Plugins plugin.json must be a JSON object.")
            manifest = None

    if isinstance(manifest, dict):
        unknown = set(manifest) - AGENT_PLUGIN_ALLOWED_FIELDS
        if unknown:
            errors.append(
                "Agent Plugins plugin.json has unknown top-level fields: "
                f"{sorted(unknown)}"
            )
        if manifest.get("$schema") != AGENT_PLUGINS_SCHEMA_URI:
            errors.append(
                "Agent Plugins plugin.json $schema must be "
                f"{AGENT_PLUGINS_SCHEMA_URI}."
            )
        name = manifest.get("name")
        if not isinstance(name, str) or AGENT_PLUGIN_NAME.fullmatch(name) is None or not 1 <= len(name) <= 64:
            errors.append("Agent Plugins plugin.json has an invalid name.")
        elif name != plugin_dir.name:
            errors.append(
                f"Agent Plugins plugin.json name {name!r} does not match plugin folder {plugin_dir.name}."
            )
        version = manifest.get("version")
        if not isinstance(version, str) or not version:
            errors.append("Agent Plugins plugin.json is missing a version string.")
        else:
            codex_manifest = codex_manifests.get(plugin_dir.name)
            if codex_manifest is not None and version != codex_manifest.get("version"):
                errors.append(
                    "Agent Plugins plugin.json version must match "
                    "plugins/coding-workflows/.codex-plugin/plugin.json."
                )
            claude_manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
            if claude_manifest_path.is_file():
                try:
                    require_repository_path(
                        claude_manifest_path, root, label="Claude plugin manifest for Agent Plugins version check"
                    )
                    if reserve_file(claude_manifest_path):
                        claude_manifest = load_json(claude_manifest_path)
                        if isinstance(claude_manifest, dict) and version != claude_manifest.get("version"):
                            errors.append(
                                "Agent Plugins plugin.json version must match "
                                "plugins/coding-workflows/.claude-plugin/plugin.json."
                            )
                except (OSError, ValueError, json.JSONDecodeError):
                    pass
        description = manifest.get("description")
        if description is not None and not isinstance(description, str):
            errors.append("Agent Plugins plugin.json description must be a string.")
        author = manifest.get("author")
        if author is not None:
            if not isinstance(author, dict):
                errors.append("Agent Plugins plugin.json author must be an object.")
            else:
                extra_author = set(author) - AGENT_PLUGIN_AUTHOR_FIELDS
                if extra_author:
                    errors.append(
                        "Agent Plugins plugin.json author has unknown fields: "
                        f"{sorted(extra_author)}"
                    )
                for field in AGENT_PLUGIN_AUTHOR_FIELDS:
                    value = author.get(field)
                    if field in author and not isinstance(value, str):
                        errors.append(f"Agent Plugins plugin.json author.{field} must be a string.")
        for field in ("homepage", "repository", "license"):
            value = manifest.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(f"Agent Plugins plugin.json {field} must be a string.")
        keywords = manifest.get("keywords")
        if keywords is not None and (
            not isinstance(keywords, list) or not all(isinstance(item, str) for item in keywords)
        ):
            errors.append("Agent Plugins plugin.json keywords must be an array of strings.")
        if "extensions" in manifest:
            errors.append(
                "Agent Plugins plugin.json must not declare extensions; this portable floor stays client-neutral."
            )

    mcp_path = plugin_dir / "mcp.json"
    if mcp_path.exists():
        errors.append(
            "Agent Plugins portable floor must not include mcp.json; MCP packaging is out of scope."
        )

    skills_dir = plugin_dir / "skills"
    if not skills_dir.is_dir():
        errors.append("Agent Plugins skills/ must be a directory under plugins/coding-workflows.")
        return
    try:
        require_repository_path(skills_dir, root, label="Agent Plugins skills directory")
    except ValueError as exc:
        errors.append(str(exc))
        return

    discovered: set[str] = set()
    try:
        children = sorted(skills_dir.iterdir())
    except OSError as exc:
        errors.append(f"Could not inspect Agent Plugins skills/: {exc}")
        return
    for child in children:
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if skill_md.is_file():
            try:
                require_repository_path(skill_md, root, label=f"Agent Plugins skill {child.name}")
            except ValueError as exc:
                errors.append(str(exc))
                continue
            discovered.add(child.name)
        else:
            errors.append(f"Agent Plugins skill directory {child.name} is missing SKILL.md.")

    if discovered != skill_names:
        errors.append(
            "Agent Plugins/skill mismatch: "
            f"discovered={sorted(discovered)}, canonical={sorted(skill_names)}"
        )


def _active_workflow_text(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
    )


def _workflow_step_blocks(text: str) -> dict[str, list[list[str]]]:
    active = _active_workflow_text(text)
    matches = list(WORKFLOW_STEP.finditer(active))
    blocks: dict[str, list[list[str]]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(active)
        name = match.group("name").strip().strip("'\"")
        blocks.setdefault(name, []).append(active[match.start() : end].splitlines())
    return blocks


def _workflow_triggers_block(text: str) -> str | None:
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if re.match(r"^on:\s*$", line.strip())),
        None,
    )
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line.startswith((" ", "\t")):
            end = index
            break
    return "\n".join(lines[start:end])


def _workflow_trigger_filters(triggers_block: str) -> dict[str, list[str]]:
    """Map each event trigger to the filter lines declared beneath it."""

    filters: dict[str, list[str]] = {}
    current: str | None = None
    for line in triggers_block.splitlines()[1:]:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        name_match = re.match(r"^\s{2}(\S+?):\s*(.*)$", line)
        if indent == 2 and name_match:
            current = name_match.group(1)
            filters.setdefault(current, [])
            if name_match.group(2).strip():
                filters[current].append(name_match.group(2).strip())
            continue
        if current is not None and indent > 2:
            filters[current].append(line.strip())
    return filters


def _workflow_strategy_block(job_text: str) -> str | None:
    lines = job_text.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^\s{4}strategy:\s*$", line)
        ),
        None,
    )
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and len(line) - len(line.lstrip(" ")) < 6:
            end = index
            break
    return "\n".join(lines[start:end])


def _workflow_job_text(text: str, job_name: str) -> str | None:
    lines = _active_workflow_text(text).splitlines()
    marker = f"  {job_name}:"
    matches = [index for index, line in enumerate(lines) if line == marker]
    if len(matches) != 1:
        return None
    start = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line.startswith("    "):
            end = index
            break
    return "\n".join(lines[start:end])


def _workflow_run_lines(block: list[str]) -> list[str]:
    if not block:
        return []
    step_indent = len(block[0]) - len(block[0].lstrip(" "))
    runs: list[str] = []
    in_block = False
    for line in block[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip(" "))
        run_match = re.match(r"run:\s*(.*)$", stripped)
        if run_match and indent > step_indent:
            value = run_match.group(1).strip()
            if value in {"|", ">", "|-", ">-", "|+", ">+"}:
                in_block = True
            else:
                runs.append(value.strip("'\""))
            continue
        if in_block:
            if indent <= step_indent:
                in_block = False
            else:
                runs.append(stripped)
    return runs


def _validate_workflow_contract(root: Path, reserve_file, errors: list[str]) -> None:
    relative = ".github/workflows/validate-repository.yml"
    text = _read_text_artifact(root, relative, reserve_file, errors, label="Validation workflow")
    if text is None:
        return
    if "\t" in text:
        errors.append("Validation workflow contains a tab; YAML indentation must use spaces.")
    active = _active_workflow_text(text)
    job_text = _workflow_job_text(text, "validate")
    if job_text is None:
        errors.append("Validation workflow must contain exactly one validate job.")
        return
    job_active = _active_workflow_text(job_text)
    if re.search(r"(?m)^    if:", job_active):
        errors.append("Validation workflow validate job must be unconditional.")
    active_folded = active.casefold()
    if "continue-on-error:" in active_folded:
        errors.append("Validation workflow must not make a required check non-blocking.")
    if re.search(r"(?im)^\s*if:\s*(?:false|\$\{\{\s*false\s*\}\})\s*$", active):
        errors.append("Validation workflow contains a disabled required step.")
    for trigger in ("pull_request:", "push:", "workflow_dispatch:"):
        if trigger not in active:
            errors.append(f"Validation workflow is missing the {trigger[:-1]} trigger.")
    triggers_block = _workflow_triggers_block(active)
    if triggers_block is None:
        errors.append("Validation workflow has an unreadable event trigger block.")
    else:
        trigger_filters = _workflow_trigger_filters(triggers_block)
        pull_request_filters = trigger_filters.get("pull_request", [])
        if any(
            re.match(r"(paths|paths-ignore|branches|branches-ignore|tags|tags-ignore|types)\s*:", item)
            for item in pull_request_filters
        ):
            errors.append(
                "Validation workflow must not filter pull_request events; required validation must run for every pull request."
            )
        for item in trigger_filters.get("push", []):
            normalized = re.sub(r"\s+", "", item)
            if re.match(r"(paths|paths-ignore)\s*:", item):
                errors.append(
                    "Validation workflow must not filter push events by path; required validation must see every changed file."
                )
            elif normalized != "branches:[main]":
                errors.append(f"Validation workflow has an unsupported push event filter: {item}.")
        if any(
            re.match(r"(paths|paths-ignore|branches|branches-ignore|tags|tags-ignore|types)\s*:", item)
            for item in trigger_filters.get("workflow_dispatch", [])
        ):
            errors.append("Validation workflow must not filter workflow_dispatch events.")
        if tuple(triggers_block.splitlines()) != WORKFLOW_EXPECTED_TRIGGERS:
            errors.append(
                "Validation workflow event triggers must match the reviewed contract exactly: "
                "unfiltered pull_request, push to main only, and unfiltered workflow_dispatch."
            )
    if WORKFLOW_SHELL_OVERRIDE.search(active):
        # A custom shell template (for example `pwsh -command "& '{0}'; exit 0"`)
        # can discard a required validator's exit status, so required steps
        # must run under the runner's default shell.
        errors.append("Validation workflow must not override the default run shell.")
    if "permissions:" not in active or "contents: read" not in active:
        errors.append("Validation workflow must keep contents read-only.")
    if "actions/checkout@" not in active or "actions/setup-python@" not in active:
        errors.append("Validation workflow must use pinned checkout and Python setup actions.")
    for line in job_active.splitlines():
        match = WORKFLOW_USES.match(line)
        if match and not WORKFLOW_ACTION_PIN.search(match.group(1)):
            errors.append(f"Validation workflow action is not pinned to a full commit SHA: {match.group(1)}")

    blocks = _workflow_step_blocks(job_text)
    for name in sorted(WORKFLOW_REQUIRED_STEPS):
        if name not in blocks:
            errors.append(f"Validation workflow is missing required step: {name}.")
        elif len(blocks[name]) > 1:
            errors.append(f"Validation workflow has duplicate required step: {name}.")
        else:
            block = blocks[name][0]
            if re.search(r"(?m)^\s*if:", "\n".join(block)):
                errors.append(f"Validation workflow required step must be unconditional: {name}.")
            if "continue-on-error:" in "\n".join(block).casefold():
                errors.append(f"Validation workflow required step must be blocking: {name}.")

    for step_name, command in WORKFLOW_REQUIRED_COMMANDS.items():
        occurrences = blocks.get(step_name, [])
        block = occurrences[0] if len(occurrences) == 1 else []
        run_lines = _workflow_run_lines(block)
        if run_lines.count(command) != 1:
            errors.append(f"Validation workflow step {step_name} must run exactly once: {command}.")
        elif len(run_lines) != 1:
            # On Windows/pwsh a trailing command (for example `echo done`)
            # can mask the required validator's failure, so required steps
            # must run only their validator command.
            errors.append(
                f"Validation workflow step {step_name} must run only its required command "
                f"so no trailing command can mask a failure: {command}."
            )

    checkout_occurrences = blocks.get("Check out repository", [])
    checkout = "\n".join(checkout_occurrences[0] if len(checkout_occurrences) == 1 else [])
    if "persist-credentials: false" not in checkout or "fetch-depth: 0" not in checkout:
        errors.append("Validation workflow checkout must disable credentials and fetch the full base history.")
    setup_occurrences = blocks.get("Set up Python", [])
    setup = "\n".join(setup_occurrences[0] if len(setup_occurrences) == 1 else [])
    if "python-version:" not in setup:
        errors.append("Validation workflow Python setup must use the declared matrix.")
    if "python-version: ${{ matrix.python-version }}" not in setup:
        errors.append("Validation workflow Python setup must use the matrix version expression.")
    if "runs-on: ${{ matrix.os }}" not in job_active:
        errors.append("Validation workflow must run on the declared operating-system matrix.")
    matrix_match = re.search(r"(?ms)^\s{6}matrix:\s*\n(?P<body>(?:^[ \t]{8,}.*\n?)*)", job_active)
    if matrix_match is None:
        errors.append("Validation workflow is missing a structured matrix.")
    else:
        matrix = matrix_match.group("body")
        if re.search(r"(?m)^\s*(include|exclude)\s*:", matrix):
            errors.append("Validation workflow matrix must not silently add or remove required combinations.")
        if "ubuntu-latest" not in matrix or "windows-latest" not in matrix:
            errors.append("Validation workflow matrix must retain Ubuntu and Windows.")
        if "python-version:" not in matrix:
            errors.append("Validation workflow matrix must declare Python versions.")
        versions = {
            tuple(int(part) for part in version.split("."))
            for version in WORKFLOW_VERSION.findall(matrix)
        }
        if versions != {(3, 11), (3, 14)}:
            errors.append("Validation workflow matrix must contain exactly Python 3.11 and 3.14.")
    strategy_block = _workflow_strategy_block(job_active)
    if strategy_block is not None and re.search(r"(?m)^\s{6}(include|exclude)\s*:", strategy_block):
        errors.append("Validation workflow strategy must not silently add or remove required combinations.")
    if strategy_block is None or tuple(strategy_block.splitlines()) != WORKFLOW_EXPECTED_STRATEGY:
        errors.append(
            "Validation workflow strategy must match the reviewed Ubuntu/Windows by Python 3.11/3.14 "
            "matrix exactly and must not silently add or remove required combinations."
        )
    whitespace_occurrences = blocks.get("Check diff whitespace", [])
    whitespace = "\n".join(whitespace_occurrences[0] if len(whitespace_occurrences) == 1 else [])
    for token in (
        "EVENT_NAME: ${{ github.event_name }}",
        "EVENT_BEFORE: ${{ github.event.before }}",
        "PULL_REQUEST_BASE: ${{ github.event.pull_request.base.sha }}",
        "HEAD_SHA: ${{ github.sha }}",
    ):
        if token not in whitespace:
            errors.append(f"Validation workflow whitespace step is missing {token}.")
    if "git diff --check HEAD^" in job_active or "git rev-parse" in whitespace:
        errors.append("Validation workflow must delegate complete event-base selection to the tested script.")


def _validate_documentation_contract(root: Path, reserve_file, errors: list[str]) -> None:
    texts: dict[str, str] = {}
    for relative in DOC_COMMAND_FILES:
        text = _read_text_artifact(root, relative, reserve_file, errors, label=f"Documentation {relative}")
        if text is not None:
            texts[relative] = text.replace("\\", "/")
    for relative in (
        "docs/README.md",
        "docs/research/agent-skill-ecosystem-raid.md",
        "CLOUD_CODING_SETUP.md",
    ):
        text = _read_text_artifact(root, relative, reserve_file, errors, label=f"Documentation {relative}")
        if text is not None:
            texts[relative] = text.replace("\\", "/")
    for relative in DOC_COMMAND_FILES:
        text = texts.get(relative, "")
        for command in DOC_PACKAGE_COMMANDS:
            if command not in text:
                errors.append(f"Documentation omits generated-package check: {relative} ({command}).")
        for surface in DOC_GENERATED_SURFACES:
            if surface not in text:
                errors.append(f"Documentation omits generated surface: {relative} ({surface}).")

    for relative in ("AGENTS.md", "CONTRIBUTING.md"):
        text = " ".join(texts.get(relative, "").casefold().split())
        if "codex cli" not in text or "does not provide" not in text:
            errors.append(f"{relative} must state that the Codex CLI has no plugin validator.")
        if "claude code cli" not in text or "if" not in text:
            errors.append(f"{relative} must make the Claude CLI validator conditional.")

    cloud = " ".join(texts.get("CLOUD_CODING_SETUP.md", "").casefold().split())
    for phrase in (
        "python3 -m compileall -q scripts tests",
        "does not install packages",
        "mutate system paths",
        "start services",
        "no cursor cloud installation or invocation was run",
    ):
        if phrase not in cloud:
            errors.append(f"Cursor setup documentation is missing the reviewed boundary: {phrase}.")

    index = texts.get("docs/README.md", "")
    if "audit-findings.md" not in index or "agent-skill-ecosystem-raid.md" not in index:
        errors.append("docs/README.md must link the audit ledger and bounded research ledger.")
    research = " ".join(texts.get("docs/research/agent-skill-ecosystem-raid.md", "").casefold().split())
    for phrase in ("bounded", "raw model output", "credentials", "private paths", "refresh only"):
        if phrase not in research:
            errors.append(f"Research ledger policy must define bounded handling for: {phrase}.")
    contract = texts.get("docs/host-contracts/agent-plugins.md", "")
    if re.search(r"(?i)(?:sets\s+version|version\s+to)\s+`?\d+\.\d+\.\d+", contract):
        errors.append("Agent Plugins contract must derive its version from canonical metadata.")
    program = texts.get("docs/coding-agents-program.md", "")
    if "PR #7" in program:
        errors.append("The program must not retain volatile pull-request state.")


def _tracked_files(root: Path) -> tuple[list[str], str | None]:
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
        ).stdout.decode("utf-8").split("\0")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        return [], str(exc)
    return list(filter(None, tracked)), None


def validate(
    root: Path = ROOT,
    *,
    tracked_files: Iterable[str] | None = None,
    check_generated_packages: bool | None = None,
) -> list[str]:
    errors: list[str] = []
    explicit_tracked_files = tracked_files is not None
    if explicit_tracked_files:
        tracked = list(tracked_files or [])
    else:
        tracked, tracked_error = _tracked_files(root)
        if tracked_error:
            errors.append(f"Could not inspect tracked files: {tracked_error}")
            tracked = []
    budgeted_paths: set[Path] = set()
    budgeted_bytes = 0
    file_limit_reported = False
    total_limit_reported = False

    def reserve_file(path: Path) -> bool:
        nonlocal budgeted_bytes, file_limit_reported, total_limit_reported
        key = path.absolute()
        if key in budgeted_paths:
            return True
        size = path.stat().st_size
        if size > MAX_VALIDATED_FILE_BYTES:
            errors.append(
                f"File exceeds the {MAX_VALIDATED_FILE_BYTES}-byte validation limit: {path.relative_to(root)}"
            )
            return False
        if len(budgeted_paths) >= MAX_VALIDATED_FILES:
            if not file_limit_reported:
                errors.append(f"Repository exceeds the {MAX_VALIDATED_FILES}-file validation limit.")
                file_limit_reported = True
            return False
        if budgeted_bytes + size > MAX_VALIDATED_TOTAL_BYTES:
            if not total_limit_reported:
                errors.append(
                    f"Repository exceeds the {MAX_VALIDATED_TOTAL_BYTES}-byte aggregate validation limit."
                )
                total_limit_reported = True
            return False
        budgeted_paths.add(key)
        budgeted_bytes += size
        return True

    try:
        repository_files, repository_directories = walk_repository(
            root,
            max_entries=MAX_VALIDATED_ENTRIES,
            max_directories=MAX_VALIDATED_DIRECTORIES,
        )
    except ValueError as exc:
        return [str(exc)]

    marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
    try:
        require_repository_path(marketplace_path, root, label="Marketplace")
        if not reserve_file(marketplace_path):
            return errors
        marketplace = load_json(marketplace_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"Invalid marketplace: {exc}"]
    if not isinstance(marketplace, dict):
        return ["Invalid marketplace: expected a JSON object."]

    if marketplace.get("name") != "coding-agents":
        errors.append("Marketplace name must be coding-agents.")
    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or not entries:
        errors.append("Marketplace must contain at least one plugin entry.")
        entries = []

    catalog_names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("Marketplace plugin entry must be an object.")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            errors.append("Marketplace entry is missing a name.")
            continue
        if name in catalog_names:
            errors.append(f"Duplicate marketplace plugin name: {name}")
        catalog_names.add(name)
        source = entry.get("source", {})
        source_path = source.get("path") if isinstance(source, dict) else None
        if not isinstance(source, dict) or source.get("source") != "local" or not isinstance(source_path, str):
            errors.append(f"Plugin {name} must use a repo-local ./plugins/ source.")
        else:
            try:
                expected_source = resolve_within(
                    root / "plugins" / name,
                    root / "plugins",
                    label=f"Plugin {name} expected source",
                )
                resolved_source = resolve_within(
                    root / source_path,
                    root / "plugins",
                    label=f"Plugin {name} marketplace source",
                )
            except ValueError:
                errors.append(f"Plugin {name} source escapes the repo-local plugins directory: {source_path}")
            else:
                if not source_path.startswith("./plugins/") or resolved_source != expected_source:
                    errors.append(f"Plugin {name} source does not match its repo-local plugin directory: {source_path}")
        policy = entry.get("policy", {})
        if not isinstance(policy, dict) or policy.get("installation") not in {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}:
            errors.append(f"Plugin {name} has invalid installation policy.")
        if not isinstance(policy, dict) or policy.get("authentication") not in {"ON_INSTALL", "ON_USE"}:
            errors.append(f"Plugin {name} has invalid authentication policy.")
        if not entry.get("category"):
            errors.append(f"Plugin {name} is missing a category.")

    plugin_root = root / "plugins"
    try:
        require_repository_path(plugin_root, root, label="Plugin root")
    except ValueError as exc:
        errors.append(str(exc))
        plugin_dirs = []
    else:
        plugin_dirs = sorted(path for path in repository_directories if path.parent == plugin_root)
    disk_names: set[str] = set()
    skill_names: set[str] = set()
    codex_manifests: dict[str, dict[str, object]] = {}
    for plugin_dir in plugin_dirs:
        try:
            require_repository_path(plugin_dir, root, label=f"Plugin {plugin_dir.name}")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
        try:
            require_repository_path(manifest_path, root, label=f"Plugin {plugin_dir.name} manifest")
            if not reserve_file(manifest_path):
                continue
            manifest = load_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid plugin manifest for {plugin_dir.name}: {exc}")
            continue
        if not isinstance(manifest, dict):
            errors.append(f"Invalid plugin manifest for {plugin_dir.name}: expected a JSON object.")
            continue
        name = manifest.get("name")
        disk_names.add(plugin_dir.name)
        codex_manifests[plugin_dir.name] = manifest
        if name != plugin_dir.name:
            errors.append(f"Plugin folder {plugin_dir.name} does not match manifest name {name!r}.")
        if not isinstance(name, str) or PLUGIN_NAME.fullmatch(name) is None:
            errors.append(f"Plugin {plugin_dir.name} has an invalid name.")
        if not SEMVER.fullmatch(str(manifest.get("version", ""))):
            errors.append(f"Plugin {plugin_dir.name} has invalid semver.")
        if not manifest.get("description") or not isinstance(manifest.get("author"), dict) or not manifest.get("author", {}).get("name"):
            errors.append(f"Plugin {plugin_dir.name} is missing description or author.name.")
        if manifest.get("license") != "MIT":
            errors.append(f"Plugin {plugin_dir.name} must declare the MIT license.")
        _validate_plugin_interface(plugin_dir, manifest, errors)
        for unsupported in ("apps", "mcpServers", "hooks"):
            if unsupported in manifest:
                errors.append(f"Plugin {plugin_dir.name} declares unsupported unused component {unsupported}.")
        try:
            skill_dir = resolve_skill_root(plugin_dir, manifest)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not skill_dir.is_dir():
            errors.append(f"Plugin {plugin_dir.name} skill path does not exist: {skill_dir}")
            continue
        for skill_path in sorted(
            path
            for path in repository_files
            if path.name == "SKILL.md" and path.parent.parent == skill_dir
        ):
            try:
                require_repository_path(skill_path, root, label=f"Skill file {skill_path.parent.name}")
                if not reserve_file(skill_path):
                    continue
                metadata = parse_skill_frontmatter(skill_path)
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
                continue
            skill_name = metadata.get("name", "")
            if skill_name != skill_path.parent.name:
                errors.append(f"Skill folder {skill_path.parent.name} does not match name {skill_name!r}.")
            if not isinstance(skill_name, str) or AGENT_SKILL_NAME.fullmatch(skill_name) is None or len(skill_name) > 64:
                errors.append(f"Skill {skill_path.parent.name} has an invalid Agent Skills name.")
            if skill_name in skill_names:
                errors.append(f"Duplicate skill name: {skill_name}")
            skill_names.add(skill_name)
            description = metadata.get("description")
            if not isinstance(description, str) or not description.strip() or len(description) > 1024:
                errors.append(f"Skill {skill_name or skill_path} has an invalid Agent Skills description.")
            text = skill_path.read_text(encoding="utf-8")
            if "[TODO:" in text or re.search(r"\b(lorem ipsum|placeholder text)\b", text, re.IGNORECASE):
                errors.append(f"Skill {skill_name} contains placeholder content.")
            metadata_path = skill_path.parent / "agents" / "openai.yaml"
            if not metadata_path.is_file():
                errors.append(f"Skill {skill_name} is missing agents/openai.yaml.")
                continue
            try:
                require_repository_path(metadata_path, root, label=f"Skill {skill_name} metadata")
                if not reserve_file(metadata_path):
                    continue
            except ValueError as exc:
                errors.append(str(exc))
                continue
            parsed_metadata, metadata_errors = parse_openai_metadata(metadata_path)
            errors.extend(f"Skill {skill_name}: {error}" for error in metadata_errors)
            interface = parsed_metadata.get("interface", {})
            if {"display_name", "short_description", "default_prompt"} - set(interface):
                errors.append(f"Skill {skill_name} metadata is missing required interface fields.")
            if f"${skill_name}" not in interface.get("default_prompt", ""):
                errors.append(f"Skill {skill_name} metadata default_prompt does not invoke ${skill_name}.")
            policy = parsed_metadata.get("policy", {})
            if policy.get("allow_implicit_invocation") not in {"true", "false"}:
                errors.append(f"Skill {skill_name} metadata must explicitly set policy.allow_implicit_invocation.")

    if disk_names != catalog_names:
        errors.append(f"Marketplace/plugin directory mismatch: catalog={sorted(catalog_names)}, disk={sorted(disk_names)}")

    routing_path = root / "plugins" / "coding-workflows" / "evals" / "trigger-routing.json"
    try:
        require_repository_path(routing_path, root, label="Routing evaluations")
        if not reserve_file(routing_path):
            routing = None
            raise ValueError("Routing evaluations exceed repository validation limits.")
        routing = load_json(routing_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid routing evaluation file: {exc}")
    else:
        errors.extend(validate_eval_data(routing, skill_names))

    errors.extend(validate_packages(root))
    try:
        work_mode_manifest = load_work_mode_manifest(root)
        entries = work_mode_manifest.get("skills", [])
        work_mode_names = {entry.get("name") for entry in entries if isinstance(entry, dict) and isinstance(entry.get("name"), str)}
        if work_mode_names != skill_names:
            errors.append(
                f"Work Mode/skill mismatch: work-mode={sorted(work_mode_names)}, skills={sorted(skill_names)}"
            )
    except (OSError, ValueError, json.JSONDecodeError):
        # validate_packages reports a precise manifest error above.
        pass

    errors.extend(validate_claude_app_packages(root))
    errors.extend(
        validate_agent_skill_packages(root, check_currentness=_package_currentness_enabled(check_generated_packages))
    )
    try:
        claude_app_manifest = load_claude_app_manifest(root)
        expected_claude_app_names = set(active_claude_app_skills(root, claude_app_manifest))
        claude_app_dist = root / "plugins" / "coding-workflows" / "claude-app" / "dist"
        actual_claude_app_names = {
            path.stem
            for path in claude_app_dist.iterdir()
            if path.is_file() and path.suffix == ".zip"
        }
        if actual_claude_app_names != expected_claude_app_names:
            errors.append(
                "Claude app/skill mismatch: "
                f"claude-app={sorted(actual_claude_app_names)}, expected={sorted(expected_claude_app_names)}"
            )
    except (OSError, ValueError, json.JSONDecodeError):
        # validate_claude_app_packages reports a precise manifest error above.
        pass

    agent_names: set[str] = set()
    codex_agents: dict[str, dict[str, object]] = {}
    agent_root = root / ".codex" / "agents"
    if not agent_root.is_dir():
        errors.append("Codex project agent directory is missing.")
    else:
        try:
            for entry in sorted(agent_root.iterdir()):
                if entry.suffix.casefold() != ".toml":
                    errors.append(f"Codex project agent directory contains an unsupported file: {entry.name}.")
        except OSError as exc:
            errors.append(f"Could not inspect Codex project agents: {exc}")
    for path in sorted(
        candidate
        for candidate in repository_files
        if candidate.parent == agent_root and candidate.suffix.lower() == ".toml"
    ):
        try:
            require_repository_path(path, root, label=f"Agent file {path.name}")
            if not reserve_file(path):
                continue
            agent = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"Invalid agent file {path.relative_to(root)}: {exc}")
            continue
        unknown_agent_fields = sorted(set(agent) - CODEX_AGENT_FIELDS)
        if unknown_agent_fields:
            errors.append(f"Agent {path.name} has unsupported fields: {unknown_agent_fields}")
        missing = {"name", "description", "developer_instructions"} - set(agent)
        if missing:
            errors.append(f"Agent {path.name} is missing fields: {sorted(missing)}")
        name = agent.get("name", "")
        if not isinstance(name, str) or not name:
            errors.append(f"Agent {path.name} has an invalid name.")
            continue
        if name in agent_names:
            errors.append(f"Duplicate agent name: {name}")
        agent_names.add(name)
        if name not in PROJECT_AGENT_NAMES:
            errors.append(f"Unsupported Codex project agent: {name!r}.")
        if agent.get("sandbox_mode") != "read-only":
            errors.append(f"Agent {name or path.name} must be read-only.")
        description = agent.get("description", "")
        instructions = agent.get("developer_instructions", "")
        if not isinstance(description, str) or not description.strip():
            errors.append(f"Agent {name} is missing a description.")
        if not isinstance(instructions, str) or not instructions.strip():
            errors.append(f"Agent {name} is missing developer_instructions.")
        codex_agents[name] = {
            "description": description,
            "developer_instructions": instructions,
        }

    _validate_claude_distribution(
        root,
        reserve_file,
        codex_manifests,
        agent_names,
        errors,
        codex_agents,
        repository_files,
    )
    _validate_agent_plugins_distribution(root, reserve_file, skill_names, codex_manifests, errors)
    _validate_skill_helpers(root, repository_files, reserve_file, errors)

    host_support_path = root / "docs" / "host-support.md"
    try:
        require_repository_path(host_support_path, root, label="Host support matrix")
        if reserve_file(host_support_path):
            host_support = host_support_path.read_text(encoding="utf-8")
            versions = HOST_SUPPORT_VERSION.findall(host_support)
            canonical_version = codex_manifests.get("coding-workflows", {}).get("version")
            if len(versions) != 1:
                errors.append("Host support matrix must declare exactly one package version.")
            elif canonical_version is not None and versions[0] != canonical_version:
                errors.append(
                    "Host support matrix package version must match the canonical coding-workflows plugin version."
                )
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        errors.append(f"Invalid host support matrix version: {exc}")

    for relative in REMOVED_ROOTS:
        if (root / relative).exists():
            errors.append(f"Removed legacy path still exists: {relative}")
    for relative in sorted(REQUIRED_REPOSITORY_FILES):
        if not (root / relative).is_file():
            errors.append(f"Required repository file is missing: {relative}")

    _validate_cursor_environment(root, reserve_file, errors)
    _validate_audit_ledger(root, reserve_file, errors)
    _validate_workflow_contract(root, reserve_file, errors)
    _validate_documentation_contract(root, reserve_file, errors)

    scan_files = (
        sorted(path for path in repository_files if path.is_file())
        if explicit_tracked_files
        else sorted((root / relative for relative in tracked), key=lambda path: path.as_posix())
    )
    for path in scan_files:
        if file_limit_reported or total_limit_reported:
            break
        if not path.is_file():
            continue
        try:
            require_repository_path(path, root, label=f"Scanned file {path.relative_to(root)}")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not reserve_file(path):
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            errors.append(f"Could not read scanned file {path.relative_to(root)}: {exc}")
            continue
        if b"\x00" in data:
            continue
        try:
            source = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        folded = source.casefold()
        for marker in STALE_MARKERS:
            if marker in folded:
                errors.append(f"Stale marker {marker!r} in {path.relative_to(root)}")
        if SECRET_MATERIAL.search(source) or REPOSITORY_SECRET_MATERIAL.search(source):
            errors.append(f"Secret material detected in {path.relative_to(root)}")
        if path.suffix.lower() == ".md":
            for raw_link in MARKDOWN_LINK.findall(source):
                target = raw_link.strip().strip("<>").split("#", 1)[0]
                if not target or target.startswith(("http://", "https://", "mailto:", "codex:")):
                    continue
                target = unquote(target)
                resolved = root / target.lstrip("/") if target.startswith("/") else path.parent / target
                try:
                    require_repository_path(resolved, root, label=f"Markdown link in {path.relative_to(root)}")
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if not resolved.exists():
                        errors.append(f"Broken internal link in {path.relative_to(root)}")

    for relative in tracked:
        path = root / relative
        if path.is_file() and path.stat().st_size == 0:
            errors.append(f"Tracked zero-byte file: {relative}")

    for path in repository_directories:
        try:
            require_repository_path(path, root, label=f"Directory {path.relative_to(root)}")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        try:
            if not any(path.iterdir()):
                errors.append(f"Empty directory: {path.relative_to(root)}")
        except OSError as exc:
            errors.append(f"Could not inspect directory {path.relative_to(root)}: {exc}")

    for path in (candidate for candidate in repository_files if candidate.suffix.lower() == ".json"):
        if file_limit_reported or total_limit_reported:
            break
        try:
            require_repository_path(path, root, label=f"JSON file {path.relative_to(root)}")
            if not reserve_file(path):
                continue
            load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid JSON {path.relative_to(root)}: {exc}")
    for path in (candidate for candidate in repository_files if candidate.suffix.lower() == ".toml"):
        if file_limit_reported or total_limit_reported:
            break
        try:
            require_repository_path(path, root, label=f"TOML file {path.relative_to(root)}")
            if not reserve_file(path):
                continue
            tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"Invalid TOML {path.relative_to(root)}: {exc}")

    try:
        collect_inventory(
            root,
            reserve_file=reserve_file,
            repository_files=repository_files,
            repository_directories=repository_directories,
            check_generated_packages=check_generated_packages,
        )
    except (KeyError, OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"Inventory collection failed: {exc}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Repository validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    inventory = collect_inventory()
    print(
        "Repository validation passed: "
        f"{len(inventory['plugins'])} plugin, {len(inventory['skills'])} skills, "
        f"{len(inventory['agents'])} agents, {len(inventory['local_mcps'])} local MCP servers."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
