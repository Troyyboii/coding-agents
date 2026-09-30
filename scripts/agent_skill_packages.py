"""Generate and validate shared Agent Skills and host plugin packages."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from repository_inventory import ROOT, parse_skill_frontmatter, require_repository_path, resolve_within
from work_mode_packages import (
    DEBRIS_NAMES,
    DEBRIS_SUFFIXES,
    IGNORED_SOURCE_DIRECTORIES,
    MAX_PACKAGE_BYTES,
    MAX_PACKAGE_FILE_BYTES,
    MAX_PACKAGE_FILES,
    RELATIVE_REFERENCE,
    SECRET_MATERIAL,
    SKILL_NAME,
    TEXT_ARTIFACT_SUFFIXES,
    VERBATIM_SHARED_SUFFIXES,
    WINDOWS_PATH,
    _copy_shared_reference,
    _create_sibling_stage,
    _is_reparse_point,
    _iter_package_entries,
    _path_overlaps,
    _preflight_output_destination,
    _preflight_source_tree,
    _remove_stage,
    _relative_path,
    _safe_copy_file,
    _replace_staged_outputs,
    _require_no_reparse_components,
    _rewrite_skill_markdown,
    _root_relative,
    _same_file,
    _shared_references,
    _validate_package_references,
    package_material_errors,
)


PLUGIN_ROOT = "plugins/coding-workflows"
CANONICAL_SOURCE = f"{PLUGIN_ROOT}/skills"
SHARED_SOURCE = f"{PLUGIN_ROOT}/references"
BASE = Path(PLUGIN_ROOT) / "agent-skills"
PORTABLE_DIST = BASE / "dist"
GEMINI_DIST = Path(PLUGIN_ROOT) / "gemini" / "dist"
KIMI_DIST = Path(PLUGIN_ROOT) / "kimi" / "dist"
OUTPUTS = (PORTABLE_DIST, GEMINI_DIST, KIMI_DIST)


def _preflight_output_destinations(root: Path = ROOT) -> None:
    destinations: list[Path] = []
    for target in OUTPUTS:
        destination = root / target
        destination = _preflight_output_destination(
            destination,
            repository_root=root,
            protected_roots=(root / CANONICAL_SOURCE, root / SHARED_SOURCE),
        )
        for previous in destinations:
            if _path_overlaps(destination.resolve(strict=False), previous.resolve(strict=False)):
                raise ValueError(f"Generated package outputs alias or overlap: {previous} and {destination}")
        destinations.append(destination)


def _validate_canonical_package_inputs(root: Path, names: list[str]) -> list[str]:
    """Bound all material that would be copied into a generated package before staging."""
    errors: list[str] = []
    package_files = 0
    package_bytes = 0
    shared_root = (root / SHARED_SOURCE).resolve()

    def account_file(path: Path, package_name: str) -> int | None:
        nonlocal package_files, package_bytes
        try:
            _require_no_reparse_components(path, root, label=f"Canonical package input for {package_name}")
            if not path.is_file():
                errors.append(f"Canonical package input is not a regular file: {_root_relative(path, root)}")
                return None
            if path.suffix.lower() not in TEXT_ARTIFACT_SUFFIXES:
                errors.append(f"Canonical package contains a non-text artifact: {_root_relative(path, root)}")
                return None
            size = path.stat().st_size
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            return None
        if size > MAX_PACKAGE_FILE_BYTES:
            errors.append(f"Canonical package file exceeds the size limit: {_root_relative(path, root)}")
            return None
        package_files += 1
        package_bytes += size
        if package_files > MAX_PACKAGE_FILES:
            errors.append(f"Canonical package exceeds the {MAX_PACKAGE_FILES}-file limit.")
            return None
        if package_bytes > MAX_PACKAGE_BYTES:
            errors.append(f"Canonical package exceeds the {MAX_PACKAGE_BYTES}-byte size limit.")
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"Canonical package text artifact is invalid: {_root_relative(path, root)} ({exc})")
            return None
        if WINDOWS_PATH.search(text):
            errors.append(f"Canonical package contains a local machine path: {_root_relative(path, root)}")
        if SECRET_MATERIAL.search(text):
            errors.append(f"Canonical package contains secret material: {_root_relative(path, root)}")
        return size

    for name in names:
        source = root / CANONICAL_SOURCE / name
        try:
            _require_no_reparse_components(source, root, label=f"Canonical skill {name}")
            if not source.is_dir():
                errors.append(f"Canonical skill {name} is not a regular directory.")
                continue
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue

        canonical_text = ""
        ignored = {name.casefold() for name in IGNORED_SOURCE_DIRECTORIES}
        for current, directories, file_names in os.walk(source, topdown=True, followlinks=False):
            current_path = Path(current)
            for directory in list(directories):
                directory_path = current_path / directory
                try:
                    _require_no_reparse_components(directory_path, root, label=f"Canonical skill {name} source")
                except (OSError, ValueError) as exc:
                    errors.append(str(exc))
                    directories.remove(directory)
                    continue
                folded = directory.casefold()
                if folded in DEBRIS_NAMES and folded not in ignored:
                    errors.append(f"Canonical package contains forbidden debris: {_root_relative(directory_path, root)}")
                    directories.remove(directory)
            directories[:] = [directory for directory in directories if directory.casefold() not in ignored]
            for file_name in file_names:
                path = current_path / file_name
                try:
                    _require_no_reparse_components(path, root, label=f"Canonical skill {name} source")
                except (OSError, ValueError) as exc:
                    errors.append(str(exc))
                    continue
                if file_name.casefold().endswith(DEBRIS_SUFFIXES) or any(
                    part.casefold() in ignored for part in path.relative_to(source).parts
                ):
                    continue
                size = account_file(path, name)
                if size is None:
                    continue
                if path == source / "SKILL.md":
                    try:
                        canonical_text = path.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError) as exc:
                        errors.append(f"Canonical skill {name} SKILL.md is invalid: {exc}")

                if package_files > MAX_PACKAGE_FILES or package_bytes > MAX_PACKAGE_BYTES:
                    return errors

        if not canonical_text:
            continue
        copied_reference_names: set[str] = set()
        pending = []
        for relative in _shared_references(canonical_text):
            candidate = source / relative
            try:
                _require_no_reparse_components(candidate, root, label=f"Canonical shared reference for {name}")
                resolved = resolve_within(candidate, shared_root, label=f"Canonical shared reference for {name}")
                if not resolved.is_file():
                    errors.append(f"Canonical skill {name} shared reference is missing: {relative}")
                    continue
            except ValueError as exc:
                errors.append(str(exc))
                continue
            pending.append(resolved)
        while pending:
            reference = pending.pop()
            reference_name = reference.relative_to(shared_root).as_posix()
            if reference_name in copied_reference_names:
                continue
            copied_reference_names.add(reference_name)
            size = account_file(reference, name)
            if size is None:
                if package_files > MAX_PACKAGE_FILES or package_bytes > MAX_PACKAGE_BYTES:
                    return errors
                continue
            if reference.suffix.lower() in VERBATIM_SHARED_SUFFIXES:
                continue
            try:
                reference_text = reference.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"Canonical shared reference is invalid: {_root_relative(reference, root)} ({exc})")
                continue
            for match in RELATIVE_REFERENCE.finditer(reference_text):
                relative = _relative_path(match.group("path"))
                nested_candidate = reference.parent / relative
                try:
                    _require_no_reparse_components(nested_candidate, root, label=f"Canonical nested reference for {name}")
                    nested = resolve_within(nested_candidate, shared_root, label=f"Canonical nested reference for {name}")
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                if not nested.is_file():
                    errors.append(f"Canonical shared reference is missing: {_root_relative(nested_candidate, root)}")
                    continue
                pending.append(nested)
            if package_files > MAX_PACKAGE_FILES or package_bytes > MAX_PACKAGE_BYTES:
                return errors

    wrapper_bytes = len((json.dumps({"name": "coding-workflows", "version": load_plugin_version(root),
                                    "description": "Evidence-first reusable coding-agent workflow skills.",
                                    "skills": "./skills/"}, indent=2) + "\n").encode("utf-8"))
    if package_files + 1 > MAX_PACKAGE_FILES:
        errors.append(f"Generated package exceeds the {MAX_PACKAGE_FILES}-file limit after its manifest.")
    if package_bytes + wrapper_bytes > MAX_PACKAGE_BYTES:
        errors.append(f"Generated package exceeds the {MAX_PACKAGE_BYTES}-byte size limit after its manifest.")
    return errors


def load_plugin_version(root: Path = ROOT) -> str:
    manifest = json.loads((root / PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
    version = manifest.get("version") if isinstance(manifest, dict) else None
    if not isinstance(version, str) or not version:
        raise ValueError("Canonical Agent Plugins manifest has no version.")
    return version


def discover_skills(root: Path = ROOT) -> list[str]:
    skills_root = root / CANONICAL_SOURCE
    require_repository_path(skills_root, root, label="Canonical skill root")
    if not skills_root.is_dir():
        raise ValueError("Canonical skill root is missing.")
    result: list[str] = []
    for entry in sorted(skills_root.iterdir()):
        if not entry.is_dir() or not (entry / "SKILL.md").is_file():
            continue
        if not SKILL_NAME.fullmatch(entry.name) or len(entry.name) > 64:
            raise ValueError(f"Canonical skill directory has an invalid name: {entry.name}")
        result.append(entry.name)
    if not result:
        raise ValueError("Canonical skill root contains no skills.")
    return result


def _stage_skill(skill_name: str, root: Path, destination: Path) -> None:
    source = root / CANONICAL_SOURCE / skill_name
    _require_no_reparse_components(source, root, label=f"Canonical skill {skill_name}")
    if not source.is_dir():
        raise ValueError(f"Canonical skill {skill_name} is not a regular directory.")
    _preflight_source_tree(source, label=f"Canonical skill {skill_name} package source", ignored_directories=IGNORED_SOURCE_DIRECTORIES)
    skill_path = source / "SKILL.md"
    if not skill_path.is_file():
        raise ValueError(f"Canonical skill {skill_name} is missing SKILL.md.")
    canonical_text = skill_path.read_text(encoding="utf-8")
    metadata = parse_skill_frontmatter(skill_path)
    if set(metadata) != {"name", "description"} or metadata.get("name") != skill_name:
        raise ValueError(f"Canonical skill {skill_name} has unsupported or mismatched Agent Skills metadata.")
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise ValueError(f"Canonical skill {skill_name} has an invalid Agent Skills description.")

    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("agents", "__pycache__", "*.pyc"),
        copy_function=_safe_copy_file,
    )
    staged_skill = destination / "SKILL.md"
    staged_text = staged_skill.read_text(encoding="utf-8")
    staged_skill.write_text(_rewrite_skill_markdown(staged_text), encoding="utf-8", newline="\n")

    shared_root = root / SHARED_SOURCE
    copied: set[str] = set()
    for reference_text in (canonical_text, staged_text):
        for relative in _shared_references(reference_text):
            shared_source = source / relative
            _require_no_reparse_components(shared_source, root, label=f"Skill {skill_name} shared reference")
            resolved = resolve_within(shared_source, shared_root, label=f"Skill {skill_name} shared reference")
            if not resolved.is_file():
                raise ValueError(f"Skill {skill_name} shared reference is missing: {relative}")
            _copy_shared_reference(resolved, shared_root, destination, copied, input_root=root)


def _copy_skill_tree(root: Path, destination: Path) -> None:
    names = discover_skills(root)
    destination.mkdir(parents=True)
    for name in names:
        _stage_skill(name, root, destination / name)


def _render_packages(root: Path, stage: Path) -> dict[Path, Path]:
    version = load_plugin_version(root)
    names = discover_skills(root)
    source_errors = _validate_canonical_package_inputs(root, names)
    if source_errors:
        raise ValueError("Invalid canonical Agent Skills package inputs: " + "; ".join(source_errors))
    portable = stage / "portable"
    skills = portable / "skills"
    _copy_skill_tree(root, skills)

    gemini = stage / "gemini"
    gemini.mkdir()
    (gemini / "gemini-extension.json").write_text(
        json.dumps(
            {"name": "coding-workflows", "version": version,
             "description": "Evidence-first reusable coding-agent workflow skills."},
            indent=2,
        ) + "\n", encoding="utf-8", newline="\n"
    )
    shutil.copytree(skills, gemini / "skills")

    kimi = stage / "kimi"
    kimi.mkdir()
    (kimi / "kimi.plugin.json").write_text(
        json.dumps(
            {"name": "coding-workflows", "version": version,
             "description": "Evidence-first reusable coding-agent workflow skills.", "skills": "./skills/"},
            indent=2,
        ) + "\n", encoding="utf-8", newline="\n"
    )
    shutil.copytree(skills, kimi / "skills")
    return {PORTABLE_DIST: portable, GEMINI_DIST: gemini, KIMI_DIST: kimi}


def _same_tree(left: Path, right: Path) -> bool:
    if not left.is_dir() or not right.is_dir():
        return False
    left_entries = {
        path.relative_to(left).as_posix(): path.is_dir()
        for path in _iter_package_entries(left)
    }
    right_entries = {
        path.relative_to(right).as_posix(): path.is_dir()
        for path in _iter_package_entries(right)
    }
    if left_entries != right_entries:
        return False
    return all(
        is_directory or _same_file(left / name, right / name)
        for name, is_directory in left_entries.items()
    )


def _validate_output(path: Path, kind: str, version: str, names: list[str], errors: list[str]) -> bool:
    initial_error_count = len(errors)
    expected_manifest = {
        "portable": None,
        "gemini": {"name": "coding-workflows", "version": version,
                   "description": "Evidence-first reusable coding-agent workflow skills."},
        "kimi": {"name": "coding-workflows", "version": version,
                 "description": "Evidence-first reusable coding-agent workflow skills.", "skills": "./skills/"},
    }[kind]
    manifest_name = {"portable": None, "gemini": "gemini-extension.json", "kimi": "kimi.plugin.json"}[kind]
    allowed_top = {"skills"} | ({manifest_name} if manifest_name else set())
    if {p.name for p in path.iterdir()} != allowed_top:
        errors.append(f"{kind.title()} package has an incorrect root shape or forbidden debris.")
    material_errors = package_material_errors(path, f"{kind.title()} package")
    errors.extend(material_errors)
    if material_errors:
        return False

    if manifest_name:
        try:
            manifest = json.loads((path / manifest_name).read_text(encoding="utf-8"))
            if manifest != expected_manifest:
                errors.append(f"{kind.title()} package has a malformed or unsupported manifest.")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{kind.title()} package manifest is invalid: {exc}")

    skill_root = path / "skills"
    actual = sorted(p.name for p in skill_root.iterdir() if p.is_dir()) if skill_root.is_dir() else []
    if actual != names:
        errors.append(f"{kind.title()} package skill set mismatch.")

    if skill_root.is_dir():
        for name in names:
            package = skill_root / name
            skill = package / "SKILL.md"
            if not skill.is_file():
                errors.append(f"{kind.title()} package is missing {name}/SKILL.md.")
                continue
            try:
                metadata = parse_skill_frontmatter(skill)
            except (OSError, ValueError) as exc:
                errors.append(f"{kind.title()} package {name} metadata is invalid: {exc}")
                continue
            if metadata.get("name") != name or set(metadata) != {"name", "description"}:
                errors.append(f"{kind.title()} package {name} has unsupported metadata or mismatched name.")
            _validate_package_references(package, errors, scan_sensitive_text=False)
    return len(errors) == initial_error_count


def validate_packages(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        version = load_plugin_version(root)
        names = discover_skills(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"Invalid Agent Skills package source: {exc}"]
    errors.extend(_validate_canonical_package_inputs(root, names))
    if errors:
        return errors
    try:
        _preflight_output_destinations(root)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    comparable: dict[Path, bool] = {}
    for path, kind in zip(OUTPUTS, ("portable", "gemini", "kimi"), strict=True):
        package = root / path
        if package.is_symlink():
            errors.append(f"{kind.title()} package output is a symlink.")
            comparable[path] = False
            continue
        if not package.is_dir():
            errors.append(f"{kind.title()} package output is missing.")
            comparable[path] = False
            continue
        try:
            resolve_within(package, root, label=f"{kind.title()} package output")
        except ValueError as exc:
            errors.append(str(exc))
            comparable[path] = False
            continue
        comparable[path] = _validate_output(package, kind, version, names, errors)
    if any(comparable.values()):
        with tempfile.TemporaryDirectory() as temporary:
            try:
                expected = _render_packages(root, Path(temporary))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"Could not reproduce Agent Skills packages: {exc}")
            else:
                for target, generated in expected.items():
                    if comparable.get(target, False) and not _same_tree(root / target, generated):
                        errors.append(f"Stale generated Agent Skills package: {target.as_posix()}")
    return errors


def build_packages(root: Path = ROOT) -> None:
    _preflight_output_destinations(root)
    with tempfile.TemporaryDirectory() as temporary:
        stage_root = Path(temporary)
        expected = _render_packages(root, stage_root)
        staged: dict[Path, Path] = {}
        try:
            for target, generated in expected.items():
                destination = root / target
                destination.parent.mkdir(parents=True, exist_ok=True)
                stage = _create_sibling_stage(destination)
                staged[target] = stage
                shutil.copytree(generated, stage, dirs_exist_ok=True)
            version = load_plugin_version(root)
            names = discover_skills(root)
            staged_errors: list[str] = []
            for (_, generated), kind in zip(expected.items(), ("portable", "gemini", "kimi"), strict=True):
                _validate_output(generated, kind, version, names, staged_errors)
            if staged_errors:
                raise ValueError("Invalid staged Agent Skills packages: " + "; ".join(staged_errors))
            _preflight_output_destinations(root)
            _replace_staged_outputs(
                [(root / target, staged[target]) for target in expected],
                replace=os.replace,
            )
        except BaseException:
            for stage in staged.values():
                _remove_stage(stage)
            raise


def packages_are_current(root: Path = ROOT, *, details: dict[str, str] | None = None) -> bool:
    """Report whether Agent Skills, Gemini, and Kimi outputs are current.

    Records ``current`` or ``stale`` in ``details`` when provided. Rebuild
    problems surface through :func:`validate_packages`; this comparison itself
    has no separate build-failure mode.
    """

    current = not validate_packages(root)
    if details is not None:
        details["status"] = "current" if current else "stale"
        details.pop("error", None)
    return current
