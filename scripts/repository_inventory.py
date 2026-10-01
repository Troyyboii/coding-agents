"""Build the source-backed inventory for the active coding-agents repository."""

from __future__ import annotations

import ast
import json
import os
import re
import stat
import tomllib
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_PATH = ROOT / ".agents" / "plugins" / "marketplace.json"

EXTERNAL_INTEGRATIONS = (
    ("Codex built-ins", "Files, shell, Git, and subagents", "Runtime-provided; not vendored"),
    ("GitHub plugin", "Repository, issue, pull-request, and Actions access", "Host-provided; authenticate separately"),
    ("Context7 plugin", "Current library and framework documentation", "Host-provided; optional"),
    ("OpenAI Developers docs", "Current Codex and OpenAI product documentation", "Host-provided; optional"),
)

REVIEW_CANDIDATES = (
    (
        "docs/tools/context7.md",
        "Host-integration note only; remove if Context7 is no longer used in the coding workflow.",
    ),
    (
        "docs/workflows/codex-task-templates.md",
        "Convenience prompt templates with no runtime dependency; remove if they are not reused.",
    ),
)
DEFAULT_SKILLS_PATH = "./skills/"
DEFAULT_MAX_INVENTORY_ENTRIES = 5_000
DEFAULT_MAX_INVENTORY_DIRECTORIES = 1_000
IGNORED_INVENTORY_DIRECTORIES = {".git", ".artifacts", "__pycache__", ".codex-home"}
OWNED_LOCAL_MCPS: tuple[str, ...] = ()
PLUGIN_SKILLS_ROOT = ("plugins", "coding-workflows", "skills")
PLUGIN_SHARED_ROOT = ("plugins", "coding-workflows", "references")
# Skill helpers are deny-by-default for subprocess use. Each exception is tied to
# one helper path and names the only executables it may start: "git" means argv
# lists whose first element is the literal "git"; "approved-plan" additionally
# allows the exact argv of a validated, user-authorized proof plan.
#
# TEST-ONLY seam: generated-package currentness checks rebuild every package
# family from scratch, which makes each validate()/collect_inventory() call
# cost ~10-20s. Ordinary validator tests do not need that proof, so they may
# pass check_generated_packages=False. The default (None) keeps full
# validation. Dedicated package integration tests keep the default enabled.
HELPER_SUBPROCESS_POLICY: dict[str, tuple[str, ...]] = {
    "session-checkpoint/scripts/checkpoint.py": ("git",),
    "public-release-audit/scripts/release_scan.py": ("git",),
    "patch-proof/scripts/proof_run.py": ("git", "approved-plan"),
}


def walk_repository(
    root: Path,
    *,
    max_entries: int = DEFAULT_MAX_INVENTORY_ENTRIES,
    max_directories: int = DEFAULT_MAX_INVENTORY_DIRECTORIES,
) -> tuple[list[Path], list[Path]]:
    """Enumerate a repository once with pruning and hard entry/directory limits."""

    files: list[Path] = []
    directories: list[Path] = []
    inspected_entries = 0

    def raise_walk_error(exc: OSError) -> None:
        raise ValueError(f"Could not inspect repository tree: {exc}") from exc

    for current, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False, onerror=raise_walk_error
    ):
        directory_names[:] = sorted(
            name for name in directory_names if name not in IGNORED_INVENTORY_DIRECTORIES
        )
        file_names.sort()
        current_entries = len(directory_names) + len(file_names)
        if inspected_entries + current_entries > max_entries:
            directory_names.clear()
            raise ValueError(f"Repository exceeds the {max_entries}-entry validation limit.")
        inspected_entries += current_entries

        current_path = Path(current)
        discovered_directories = [current_path / name for name in directory_names]
        if len(directories) + len(discovered_directories) > max_directories:
            directory_names.clear()
            raise ValueError(f"Repository exceeds the {max_directories}-directory validation limit.")
        directories.extend(discovered_directories)
        files.extend(current_path / name for name in file_names)

    return files, directories


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_reparse_point(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(metadata, "st_file_attributes", 0) & reparse_attribute)


def resolve_within(path: Path, root: Path, *, label: str) -> Path:
    """Resolve path and convert escapes or resolution failures into ValueError."""

    try:
        root_resolved = root.resolve()
        try:
            # Strict resolution reports symlink loops on every supported
            # Python: 3.11 raises RuntimeError, while 3.13+ non-strict
            # resolution silently returns the unresolved loop path. Fall back
            # to non-strict resolution only for paths that do not exist yet.
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            resolved = path.resolve()
        resolved.relative_to(root_resolved)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"{label} must resolve inside {root}: {path}") from exc
    return resolved


def require_repository_path(path: Path, root: Path, *, label: str) -> Path:
    """Reject paths that are lexical or symlink escapes from a repository root."""

    root_absolute = root.absolute()
    path_absolute = path.absolute()
    if is_reparse_point(root_absolute):
        raise ValueError(f"{label} uses a symlinked or reparse-point repository root: {root}")
    try:
        relative = path_absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise ValueError(f"{label} must remain inside the repository: {path}") from exc
    resolve_within(path_absolute, root_absolute, label=label)
    current = root_absolute
    for part in relative.parts:
        current /= part
        if is_reparse_point(current):
            raise ValueError(f"{label} must not use symlinks or reparse points: {path}")
    return path


def resolve_skill_root(plugin_dir: Path, manifest: dict[str, Any]) -> Path:
    """Resolve and validate the manifest's skills directory within its plugin."""

    raw_path = manifest.get("skills", DEFAULT_SKILLS_PATH)
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError(f"Plugin {plugin_dir.name} skills path must be a non-empty string.")
    relative_path = Path(raw_path)
    if relative_path.is_absolute():
        raise ValueError(f"Plugin {plugin_dir.name} skills path must be relative: {raw_path!r}.")
    if ".." in relative_path.parts:
        raise ValueError(f"Plugin {plugin_dir.name} skills path must be normalized: {raw_path!r}.")
    candidate = plugin_dir / relative_path
    resolve_within(
        candidate,
        plugin_dir,
        label=f"Plugin {plugin_dir.name} skills path {raw_path!r}",
    )
    return candidate


def parse_skill_frontmatter(path: Path) -> dict[str, str]:
    return parse_skill_frontmatter_text(path.read_text(encoding="utf-8"), label=str(path))


def parse_skill_frontmatter_text(text: str, *, label: str = "text") -> dict[str, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        raise ValueError(f"{label} has no YAML frontmatter")

    lines = match.group(1).splitlines()
    result: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.startswith((" ", "\t")) or ":" not in line:
            index += 1
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if value in {">", ">-", "|", "|-"}:
            block: list[str] = []
            index += 1
            while index < len(lines) and (not lines[index].strip() or lines[index].startswith((" ", "\t"))):
                block.append(lines[index].strip())
                index += 1
            result[key.strip()] = " ".join(part for part in block if part)
            continue
        result[key.strip()] = value.strip('"\'')
        index += 1
    return result


def validate_excluded_skill_names(canonical_names: set[str], excluded: object) -> set[str]:
    """Validate and normalize a surface's explicit canonical-skill exclusions."""

    if not isinstance(excluded, list) or not all(isinstance(item, str) for item in excluded):
        raise ValueError("Claude app manifest excluded_skills must be a list of strings.")
    if len(excluded) != len(set(excluded)):
        raise ValueError("Claude app manifest excluded_skills must contain unique skill names.")
    unknown = set(excluded) - canonical_names
    if unknown:
        raise ValueError(f"Claude app manifest excluded_skills contains unknown skills: {sorted(unknown)}")
    return set(excluded)


def package_currentness_enabled(check_generated_packages: bool | None) -> bool:
    """Return whether generated-package currentness checks must run.

    None and True keep full checking; only an explicit False skips the
    expensive reproduction/currentness comparison.
    """

    return check_generated_packages is not False


def _require_current_generated_packages(root: Path) -> None:
    from agent_skill_packages import packages_are_current as agent_packages_are_current
    from agent_skill_packages import validate_packages as validate_agent_packages
    from claude_app_packages import packages_are_current as claude_packages_are_current
    from claude_app_packages import validate_packages as validate_claude_packages
    from work_mode_packages import packages_are_current as work_packages_are_current
    from work_mode_packages import validate_packages as validate_work_packages

    failures: list[str] = []
    package_families = (
        ("Work Mode", validate_work_packages, work_packages_are_current),
        ("Claude app", validate_claude_packages, claude_packages_are_current),
        ("Agent Skills", validate_agent_packages, agent_packages_are_current),
    )
    for label, validate, is_current in package_families:
        errors = validate(root)
        if errors:
            failures.append(f"{label}: {'; '.join(errors)}")
            continue
        details: dict[str, str] = {}
        if is_current(root, details=details):
            continue
        if details.get("status") == "build_failed":
            failures.append(f"{label}: packages could not be rebuilt ({details.get('error', 'unknown error')})")
        else:
            failures.append(f"{label}: stale generated output")
    if failures:
        raise ValueError("Generated package outputs are invalid or stale: " + " | ".join(failures))


def _python_description(path: Path) -> str:
    try:
        module = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return "Repository maintenance script"
    return (ast.get_docstring(module) or "Repository maintenance script").splitlines()[0]


def _workflow_name(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"\'')
    return path.stem


def collect_inventory(
    root: Path = ROOT,
    *,
    reserve_file: Callable[[Path], bool] | None = None,
    repository_files: list[Path] | None = None,
    repository_directories: list[Path] | None = None,
    check_generated_packages: bool | None = None,
) -> dict[str, Any]:
    def prepare_file(path: Path, *, label: str) -> Path:
        require_repository_path(path, root, label=label)
        if reserve_file is not None and not reserve_file(path):
            raise ValueError(f"{label} exceeds repository validation limits: {path}")
        return path

    if repository_files is None or repository_directories is None:
        repository_files, repository_directories = walk_repository(root)

    marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
    prepare_file(marketplace_path, label="Marketplace")
    marketplace = load_json(marketplace_path)
    if not isinstance(marketplace, dict):
        raise ValueError("Marketplace must be a JSON object.")

    plugins: list[dict[str, Any]] = []
    skills: list[dict[str, str]] = []
    plugin_root = require_repository_path(root / "plugins", root, label="Plugin root")
    for plugin_dir in sorted(path for path in repository_directories if path.parent == plugin_root):
        require_repository_path(plugin_dir, root, label=f"Plugin {plugin_dir.name}")
        manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
        prepare_file(manifest_path, label=f"Plugin {plugin_dir.name} manifest")
        manifest = load_json(manifest_path)
        if not isinstance(manifest, dict):
            raise ValueError(f"Plugin manifest for {plugin_dir.name} must be a JSON object.")
        skill_root = resolve_skill_root(plugin_dir, manifest)
        plugin_skills: list[str] = []
        for skill_path in sorted(
            path
            for path in repository_files
            if path.name == "SKILL.md" and path.parent.parent == skill_root
        ):
            prepare_file(skill_path, label=f"Skill file {skill_path.parent.name}")
            metadata = parse_skill_frontmatter(skill_path)
            plugin_skills.append(metadata["name"])
            skills.append(
                {
                    "name": metadata["name"],
                    "description": metadata["description"],
                    "plugin": manifest["name"],
                    "path": skill_path.relative_to(root).as_posix(),
                }
            )
        plugins.append(
            {
                "name": manifest["name"],
                "version": manifest["version"],
                "description": manifest["description"],
                "skills": plugin_skills,
                "path": plugin_dir.relative_to(root).as_posix(),
            }
        )

    if package_currentness_enabled(check_generated_packages):
        _require_current_generated_packages(root)

    agents: list[dict[str, Any]] = []
    agent_root = root / ".codex" / "agents"
    claude_agent_root = root / ".claude" / "agents"
    if agent_root.is_dir():
        require_repository_path(agent_root, root, label="Agent root")
        for path in sorted(
            candidate
            for candidate in repository_files
            if candidate.parent == agent_root and candidate.suffix.lower() == ".toml"
        ):
            prepare_file(path, label=f"Agent file {path.name}")
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            agents.append(
                {
                    "name": data["name"],
                    "description": data["description"],
                    "sandbox": data.get("sandbox_mode", "inherited"),
                    "path": path.relative_to(root).as_posix(),
                    "claude_subagent": (claude_agent_root / f"{data['name']}.md").is_file(),
                }
            )

    work_mode_path = root / "plugins" / "coding-workflows" / "work-mode" / "manifest.json"
    prepare_file(work_mode_path, label="Work Mode manifest")
    work_mode_manifest = load_json(work_mode_path)
    if not isinstance(work_mode_manifest, dict) or not isinstance(work_mode_manifest.get("skills"), list):
        raise ValueError("Work Mode manifest must be an object with a skills array.")
    work_dist = root / "plugins" / "coding-workflows" / "work-mode" / "dist"
    work_mode = {
        "canonical_source": work_mode_manifest.get("canonical_source", ""),
        "skill_count": sum(1 for path in work_dist.glob("*/SKILL.md") if path.is_file()),
        "path": work_mode_path.relative_to(root).as_posix(),
    }

    claude_marketplace_path = root / ".claude-plugin" / "marketplace.json"
    claude_plugin_manifest_path = root / "plugins" / "coding-workflows" / ".claude-plugin" / "plugin.json"
    claude_code: dict[str, Any] | None = None
    if claude_marketplace_path.is_file() and claude_plugin_manifest_path.is_file():
        prepare_file(claude_marketplace_path, label="Claude marketplace")
        prepare_file(claude_plugin_manifest_path, label="Claude plugin manifest")
        claude_plugin_manifest = load_json(claude_plugin_manifest_path)
        if not isinstance(claude_plugin_manifest, dict):
            raise ValueError("Claude plugin manifest must be a JSON object.")
        claude_code = {
            "version": claude_plugin_manifest.get("version", ""),
            "canonical_source": "plugins/coding-workflows/skills",
            "skill_count": len(skills),
            "path": claude_plugin_manifest_path.relative_to(root).as_posix(),
        }

    claude_app_manifest_path = root / "plugins" / "coding-workflows" / "claude-app" / "manifest.json"
    claude_app: dict[str, Any] | None = None
    if claude_app_manifest_path.is_file():
        prepare_file(claude_app_manifest_path, label="Claude app manifest")
        claude_app_manifest = load_json(claude_app_manifest_path)
        if not isinstance(claude_app_manifest, dict):
            raise ValueError("Claude app manifest must be a JSON object.")
        validate_excluded_skill_names(
            {item["name"] for item in skills}, claude_app_manifest.get("excluded_skills", [])
        )
        claude_dist = root / "plugins" / "coding-workflows" / "claude-app" / "dist"
        claude_app = {
            "canonical_source": claude_app_manifest.get("canonical_source", ""),
            "skill_count": sum(1 for path in claude_dist.glob("*.zip") if path.is_file()),
            "path": claude_app_manifest_path.relative_to(root).as_posix(),
        }

    portable_skill_root = root / "plugins" / "coding-workflows" / "agent-skills" / "dist" / "skills"
    agent_skills = {
        "canonical_source": "plugins/coding-workflows/skills",
        "skill_count": sum(1 for path in portable_skill_root.glob("*/SKILL.md") if path.is_file()),
        "package_root": "plugins/coding-workflows/agent-skills/dist/skills",
        "gemini_package": "plugins/coding-workflows/gemini/dist",
        "kimi_package": "plugins/coding-workflows/kimi/dist",
    }

    scripts = []
    for path in sorted(
        candidate
        for candidate in repository_files
        if candidate.parent == root / "scripts" and candidate.suffix.lower() == ".py"
    ):
        prepare_file(path, label=f"Repository script {path.name}")
        scripts.append(
            {
                "name": path.name,
                "description": _python_description(path),
                "path": path.relative_to(root).as_posix(),
            }
        )
    helpers = []
    skills_root = root.joinpath(*PLUGIN_SKILLS_ROOT)
    shared_root = root.joinpath(*PLUGIN_SHARED_ROOT)
    for path in sorted(
        candidate
        for candidate in repository_files
        if candidate.suffix.lower() == ".py"
        and (
            (candidate.parent.name == "scripts" and candidate.parent.parent.parent == skills_root)
            or candidate.parent == shared_root
        )
    ):
        prepare_file(path, label=f"Skill helper {path.name}")
        if path.parent == shared_root:
            key = None
        else:
            key = f"{path.parent.parent.name}/scripts/{path.name}"
        helpers.append(
            {
                "path": path.relative_to(root).as_posix(),
                "description": _python_description(path),
                "subprocess": ", ".join(HELPER_SUBPROCESS_POLICY.get(key, ())) if key else "",
                "shared": key is None,
            }
        )
    workflows = []
    workflow_root = root / ".github" / "workflows"
    workflow_paths = sorted(
        path
        for path in repository_files
        if path.parent == workflow_root and path.suffix.lower() in {".yml", ".yaml"}
    )
    for path in workflow_paths:
        prepare_file(path, label=f"Workflow {path.name}")
        workflows.append(
            {
                "name": _workflow_name(path),
                "path": path.relative_to(root).as_posix(),
            }
        )
    local_mcps = list(OWNED_LOCAL_MCPS)
    review_candidates = [
        {"path": path, "reason": reason}
        for path, reason in REVIEW_CANDIDATES
        if (root / path).is_file()
    ]

    return {
        "marketplace": {
            "name": marketplace["name"],
            "path": marketplace_path.relative_to(root).as_posix(),
        },
        "plugins": plugins,
        "skills": sorted(skills, key=lambda item: item["name"]),
        "work_mode": work_mode,
        "claude_code": claude_code,
        "claude_app": claude_app,
        "agent_skills": agent_skills,
        "agents": agents,
        "scripts": scripts,
        "helpers": helpers,
        "workflows": workflows,
        "local_mcps": local_mcps,
        "external_integrations": EXTERNAL_INTEGRATIONS,
        "review_candidates": review_candidates,
    }


def _cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def render_inventory(inventory: dict[str, Any]) -> str:
    lines = [
        "# Active Repository Inventory",
        "",
        "> Generated by `python scripts/generate-inventory.py`. Do not edit by hand.",
        "",
        "This inventory covers capabilities owned by this repository. Host plugins and runtime",
        "tools are listed separately and are not represented as vendored code.",
        "",
        "## Summary",
        "",
        "| Capability | Count |",
        "| --- | ---: |",
        f"| Codex plugins | {len(inventory['plugins'])} |",
        f"| Workflow skills | {len(inventory['skills'])} |",
        f"| Project agents | {len(inventory['agents'])} |",
        f"| Repository scripts | {len(inventory['scripts'])} |",
        f"| Skill helpers and shared modules | {len(inventory['helpers'])} |",
        f"| CI workflows | {len(inventory['workflows'])} |",
        f"| Local MCP servers | {len(inventory['local_mcps'])} |",
        f"| Optional review candidates | {len(inventory['review_candidates'])} |",
        "",
        "## Codex Plugins",
        "",
        "| Name | Version | Skills | Purpose |",
        "| --- | --- | ---: | --- |",
    ]
    for plugin in inventory["plugins"]:
        lines.append(
            f"| `{plugin['name']}` | `{plugin['version']}` | {len(plugin['skills'])} | {_cell(plugin['description'])} |"
        )

    lines.extend(["", "## Workflow Skills", "", "| Skill | Plugin | Purpose |", "| --- | --- | --- |"])
    for skill in inventory["skills"]:
        lines.append(f"| `{skill['name']}` | `{skill['plugin']}` | {_cell(skill['description'])} |")

    work_mode = inventory["work_mode"]
    claude_code = inventory.get("claude_code")
    lines.extend(
        [
            "",
            "## Installation Surfaces",
            "",
            "| Surface | Delivery | Canonical source | Skills | Validation boundary |",
            "| --- | --- | --- | ---: | --- |",
            f"| Codex | `coding-workflows` plugin | `plugins/coding-workflows/skills/` | {len(inventory['skills'])} | Plugin, skill, routing, and inventory contracts |",
            f"| ChatGPT Work Mode | Generated portable personal Skill packages | `{work_mode['canonical_source']}` | {work_mode['skill_count']} | Package structure and determinism; not account-side installation, enablement, or synchronization |",
        ]
    )
    if claude_code is not None:
        lines.append(
            f"| Claude Code | Local `coding-workflows` plugin (repo marketplace) | `{claude_code['canonical_source']}/` | {claude_code['skill_count']} | Marketplace/plugin manifest and subagent contracts; not account-side installation, enablement, or invocation |"
        )
    claude_app = inventory.get("claude_app")
    if claude_app is not None:
        lines.append(
            f"| Claude app (claude.ai) | Generated uploadable Custom Skill ZIP packages | `{claude_app['canonical_source']}/` | {claude_app['skill_count']} | ZIP structure, single-root layout, and determinism; not account-side upload, enablement, or per-user sync |"
        )
    agent_skills = inventory["agent_skills"]
    lines.extend(
        [
            f"| Agent Plugins 1.0 (Cursor, GitHub Copilot) | Direct portable plugin; no host-specific skill copy | `plugins/coding-workflows/` | {len(inventory['skills'])} | Manifest and skill structure; no live host installation proof |",
            f"| Agent Skills-compatible hosts | Generated portable skill tree | `{agent_skills['canonical_source']}/` | {agent_skills['skill_count']} | Package-local references, frontmatter, containment, and deterministic output |",
            f"| Gemini CLI | Generated extension | `{agent_skills['canonical_source']}/` | {agent_skills['skill_count']} | Extension manifest and bundled Agent Skills; no live host installation proof |",
            f"| Kimi Code CLI | Generated plugin | `{agent_skills['canonical_source']}/` | {agent_skills['skill_count']} | Plugin manifest and bundled Agent Skills; no live host installation proof |",
        ]
    )

    lines.extend(
        [
            "",
            "## Project Agents",
            "",
            "| Agent | Sandbox | Claude Code subagent | Purpose |",
            "| --- | --- | --- | --- |",
        ]
    )
    for agent in inventory["agents"]:
        available = "Yes" if agent.get("claude_subagent") else "No"
        lines.append(f"| `{agent['name']}` | `{agent['sandbox']}` | {available} | {_cell(agent['description'])} |")

    lines.extend(["", "## Repository Scripts", "", "| Script | Purpose |", "| --- | --- |"])
    for script in inventory["scripts"]:
        lines.append(f"| `{script['path']}` | {_cell(script['description'])} |")

    lines.extend(
        [
            "",
            "## Skill Helpers",
            "",
            "Offline Python helpers shipped inside skills, and the shared modules they import. Each runs only",
            "when an agent invokes it; subprocess use is denied unless listed here.",
            "",
        ]
    )
    if inventory["helpers"]:
        lines.extend(["| Path | Subprocess | Purpose |", "| --- | --- | --- |"])
        for helper in inventory["helpers"]:
            policy = "shared module; none" if helper["shared"] else (helper["subprocess"] or "none")
            lines.append(f"| `{helper['path']}` | {_cell(policy)} | {_cell(helper['description'])} |")
    else:
        lines.append("No skill helpers or shared Python modules are shipped.")

    lines.extend(["", "## CI Workflows", "", "| Workflow | Path |", "| --- | --- |"])
    for workflow in inventory["workflows"]:
        lines.append(f"| {_cell(workflow['name'])} | `{workflow['path']}` |")

    lines.extend(["", "## MCP and External Integration Boundaries", ""])
    if inventory["local_mcps"]:
        lines.append("Local MCP servers: " + ", ".join(f"`{name}`" for name in inventory["local_mcps"]) + ".")
    else:
        lines.append("This repository owns no MCP server. File, shell, Git, and subagent operations use Codex built-ins.")
    lines.extend(["", "| Integration | Role | Ownership |", "| --- | --- | --- |"])
    for name, role, ownership in inventory["external_integrations"]:
        lines.append(f"| {_cell(name)} | {_cell(role)} | {_cell(ownership)} |")

    lines.extend(
        [
            "",
            "## Possible Unused or Optional Material",
            "",
            "These files are not runtime capabilities or validation dependencies. They are retained",
            "only as small operational references and are the first candidates for removal if unused.",
            "",
            "| Path | Why it may be removable |",
            "| --- | --- |",
        ]
    )
    for candidate in inventory["review_candidates"]:
        lines.append(f"| `{candidate['path']}` | {_cell(candidate['reason'])} |")

    lines.extend(
        [
            "",
            "## Validation Boundary",
            "",
            "`scripts/validate-repository.py` proves repository structure and contracts. It does not prove that an external plugin is installed, authenticated, or callable in a particular Codex session.",
            "",
        ]
    )
    return "\n".join(lines)
