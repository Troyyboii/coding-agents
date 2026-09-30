"""Build and validate portable Work Mode Agent Skill packages."""

from __future__ import annotations

import json
import os
import posixpath
import re
import shutil
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from repository_inventory import (
    ROOT,
    is_reparse_point as _is_reparse_point,
    parse_skill_frontmatter,
    require_repository_path,
    resolve_within,
)


WORK_MODE_ROOT = ROOT / "plugins" / "coding-workflows" / "work-mode"
MANIFEST_PATH = WORK_MODE_ROOT / "manifest.json"
DIST_ROOT = WORK_MODE_ROOT / "dist"
CANONICAL_SOURCE = "plugins/coding-workflows/skills"
SHARED_SOURCE = "plugins/coding-workflows/references"
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WINDOWS_PATH = re.compile(r"(?i)(?:[a-z]:\\|\\\\)")
SECRET_MATERIAL = re.compile(
    r"(?i)(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[a-z0-9]{16,}\b|\bgh[pousr]_[a-z0-9]{20,}\b|\bAKIA[0-9A-Z]{16}\b|\bxox[baprs]-[a-z0-9-]{16,}\b)"
)
RELATIVE_REFERENCE = re.compile(r"(?<![\w/])(?P<path>(?:\.\.?/)[^\s`\])>]+)")
PACKAGE_REFERENCE = re.compile(
    r"(?<![\w/])(?P<path>(?:(?:\.\.?/)+|references/)[A-Za-z0-9][A-Za-z0-9._/-]*\.[A-Za-z0-9]{1,16})"
)
SHARED_REFERENCE = re.compile(r"(?P<path>(?:\.\./)+references/[A-Za-z0-9_.-]+\.(?:md|py))")
# Shared Markdown references may link to sibling references and are rewritten for the
# package layout; shared Python modules are copied byte-for-byte and never rewritten.
VERBATIM_SHARED_SUFFIXES = {".py"}
TEXT_ARTIFACT_SUFFIXES = {".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".py", ".ps1", ".sh"}
DEBRIS_NAMES = {
    "__pycache__", ".ds_store", "thumbs.db", ".git", ".venv", ".artifacts",
    ".pytest_cache", ".cache", "node_modules", "agents",
}
DEBRIS_SUFFIXES = (".pyc", ".pyo")
MAX_PACKAGE_FILES = 256
MAX_PACKAGE_BYTES = 5_000_000
MAX_PACKAGE_FILE_BYTES = 2_000_000
IGNORED_SOURCE_DIRECTORIES = {"agents", "__pycache__"}


def load_manifest(root: Path = ROOT) -> dict[str, Any]:
    path = root / "plugins" / "coding-workflows" / "work-mode" / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Work Mode manifest must be a JSON object.")
    return data


def _relative_path(raw: str) -> str:
    return raw.rstrip(".,;:")


def _root_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve()).as_posix()
    except (OSError, RuntimeError, ValueError):
        return path.as_posix()


def _require_no_reparse_components(path: Path, root: Path, *, label: str) -> Path:
    root_absolute = root.absolute()
    path_absolute = path.absolute()
    try:
        relative = path_absolute.relative_to(root_absolute)
        components_root = root_absolute
    except ValueError:
        root_resolved = root.resolve()
        path_resolved = path.resolve(strict=False)
        try:
            relative = path_resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError(f"{label} must resolve inside the repository: {path}") from exc
        components_root = root_resolved
    current = components_root
    for component in (None, *relative.parts):
        if component is not None:
            current /= component
        if _is_reparse_point(current):
            raise ValueError(f"{label} must not use symlinks or reparse points: {current}")
    return resolve_within(path_absolute, root_absolute, label=label)


def _iter_package_entries(package_root: Path):
    pending = [package_root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                yield path
                if not _is_reparse_point(path) and entry.is_dir(follow_symlinks=False):
                    pending.append(path)


def _lexical_path_overlaps(left: Path, right: Path) -> bool:
    normalized_left = os.path.normcase(os.fspath(left))
    normalized_right = os.path.normcase(os.fspath(right))
    return (
        normalized_left == normalized_right
        or normalized_left.startswith(normalized_right + os.sep)
        or normalized_right.startswith(normalized_left + os.sep)
    )


def _path_overlaps(left: Path, right: Path) -> bool:
    if _lexical_path_overlaps(left, right):
        return True

    def existing_ancestors(path: Path) -> list[Path]:
        ancestors: list[Path] = []
        current = path
        while True:
            if current.exists():
                ancestors.append(current)
            parent = current.parent
            if parent == current:
                return ancestors
            current = parent

    for left_ancestor in existing_ancestors(left):
        for right_ancestor in existing_ancestors(right):
            try:
                if not os.path.samefile(left_ancestor, right_ancestor):
                    continue
            except OSError:
                continue
            left_relative = left.relative_to(left_ancestor)
            right_relative = right.relative_to(right_ancestor)
            if _lexical_path_overlaps(Path(left_relative), Path(right_relative)):
                return True
    return False


def _preflight_output_destination(
    destination: Path,
    *,
    repository_root: Path | None = None,
    protected_roots: tuple[Path, ...] = (),
) -> Path:
    """Preflight a generated-package destination without following caller links.

    Repository-contained destinations receive full ancestor reparse-point
    containment. Destinations outside the repository are ephemeral staging
    roots that the caller created (for example ``tempfile.TemporaryDirectory``);
    they are validated as concrete directories with entry scans and
    resolved-overlap checks below, but their operating-system temporary
    ancestors are not rejected merely for passing through a symlink, junction,
    or other reparse point. Callers must only pass trusted, caller-created
    external roots; this function still rejects a destination that is itself a
    link and any link contained in an existing destination tree.
    """

    absolute = Path(os.path.abspath(destination))
    inside_repository = False
    if repository_root is not None:
        try:
            absolute.relative_to(repository_root.absolute())
        except ValueError:
            pass
        else:
            inside_repository = True
            _require_no_reparse_components(
                absolute,
                repository_root,
                label=f"Generated package output {_root_relative(absolute, repository_root)}",
            )
    if not inside_repository:
        # Callers only pass external staging roots they created themselves
        # (for example a fresh ``tempfile.TemporaryDirectory``) or freshly
        # created sibling stages whose parent was already preflighted. Reject
        # a destination that is itself a link, but do not reject a trusted
        # temporary root merely because an operating-system ancestor above it
        # is a symlink, junction, or other reparse point. Existing trees and
        # protected-input overlaps are still checked below.
        if _is_reparse_point(absolute):
            raise ValueError(f"Generated package output must not use symlinks or reparse points: {absolute}")
    if absolute.exists():
        if _is_reparse_point(absolute) or not absolute.is_dir():
            raise ValueError(f"Generated package output is not a regular directory: {absolute}")
        for entry in _iter_package_entries(absolute):
            if _is_reparse_point(entry):
                raise ValueError(
                    "Generated package output must not contain symlinks or reparse points: "
                    f"{entry.relative_to(absolute)}"
                )
    resolved = absolute.resolve(strict=False)
    if inside_repository:
        resolve_within(absolute, repository_root, label="Generated package output")
    for protected in protected_roots:
        protected_resolved = protected.resolve(strict=False)
        if _path_overlaps(resolved, protected_resolved):
            raise ValueError(f"Generated package output aliases or overlaps package input: {protected}")
    return absolute


def _create_sibling_stage(destination: Path) -> Path:
    while True:
        stage = destination.with_name(f".{destination.name}.stage-{uuid.uuid4().hex}")
        try:
            stage.mkdir()
        except FileExistsError:
            continue
        return stage


def _remove_stage(stage: Path) -> None:
    if not stage.exists() and not _is_reparse_point(stage):
        return
    if _is_reparse_point(stage):
        stage.unlink(missing_ok=True)
    else:
        shutil.rmtree(stage, ignore_errors=True)


def _path_identity(path: Path) -> tuple[int, int] | None:
    try:
        metadata = os.stat(path, follow_symlinks=False)
    except OSError:
        return None
    return metadata.st_dev, metadata.st_ino


def _replace_staged_outputs(
    staged_outputs: list[tuple[Path, Path]],
    *,
    replace: Callable[[Path, Path], None] | None = None,
    remove: Callable[[Path], None] | None = None,
) -> None:
    replacement = replace or os.replace
    removal = remove or shutil.rmtree
    backups: dict[Path, tuple[Path, tuple[int, int]]] = {}
    installed: dict[Path, tuple[int, int]] = {}
    try:
        for destination, stage in staged_outputs:
            if destination.exists():
                backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
                replacement(destination, backup)
                backup_identity = _path_identity(backup)
                if backup_identity is None:
                    replacement(backup, destination)
                    raise OSError(f"could not identify package backup {backup}")
                backups[destination] = (backup, backup_identity)
            replacement(stage, destination)
            destination_identity = _path_identity(destination)
            if destination_identity is None:
                raise OSError(f"could not identify replaced package {destination}")
            installed[destination] = destination_identity
    except BaseException as replacement_error:
        rollback_errors: list[str] = []
        for destination, destination_identity in reversed(list(installed.items())):
            stage = next(stage for target, stage in staged_outputs if target == destination)
            if _path_identity(destination) != destination_identity:
                rollback_errors.append(f"package destination changed during replacement {destination}")
                continue
            try:
                replacement(destination, stage)
            except OSError as exc:
                rollback_errors.append(f"could not move failed replacement {destination}: {exc}")
        for destination, (backup, backup_identity) in reversed(list(backups.items())):
            if _path_identity(backup) != backup_identity:
                rollback_errors.append(f"package backup changed during replacement {backup}")
                continue
            if destination.exists():
                rollback_errors.append(f"could not restore prior package because destination changed {destination}")
                continue
            try:
                replacement(backup, destination)
            except OSError as exc:
                rollback_errors.append(f"could not restore prior package {destination} from {backup}: {exc}")
        if rollback_errors:
            raise RuntimeError(
                "Package replacement failed and rollback was incomplete: " + "; ".join(rollback_errors)
            ) from replacement_error
        raise
    else:
        for backup, backup_identity in backups.values():
            if _path_identity(backup) != backup_identity:
                raise RuntimeError(f"Package backup changed before cleanup: {backup}")
            removal(backup)


def _safe_copy_file(source: str | Path, destination: str | Path) -> str:
    source_path = Path(source)
    if _is_reparse_point(source_path) or not source_path.is_file():
        raise ValueError(f"Package source entry is not a regular file: {source_path}")
    return shutil.copy2(source_path, destination)


def _preflight_source_tree(root: Path, *, label: str, ignored_directories: set[str] | None = None) -> None:
    ignored = ignored_directories or set()
    if _is_reparse_point(root) or not root.is_dir():
        raise ValueError(f"{label} is not a regular directory: {root}")

    def raise_walk_error(exc: OSError) -> None:
        raise ValueError(f"Could not inspect {label}: {exc}") from exc
    for current, directories, file_names in os.walk(root, topdown=True, followlinks=False, onerror=raise_walk_error):
        current_path = Path(current)
        for directory in list(directories):
            directory_path = current_path / directory
            if _is_reparse_point(directory_path):
                raise ValueError(f"{label} must not contain symlinks or reparse points: {directory_path}")
        directories[:] = [directory for directory in directories if directory not in ignored]
        for file_name in file_names:
            path = current_path / file_name
            if _is_reparse_point(path):
                raise ValueError(f"{label} must not contain symlinks or reparse points: {path}")


def package_material_errors(package_root: Path, label: str) -> list[str]:
    errors: list[str] = []
    if _is_reparse_point(package_root) or not package_root.is_dir():
        return [f"{label} is not a regular directory."]
    file_count = 0
    total_bytes = 0
    scan_files: list[Path] = []
    for entry in _iter_package_entries(package_root):
        relative = entry.relative_to(package_root).as_posix()
        if _is_reparse_point(entry):
            errors.append(f"{label} contains a symlink or reparse point: {relative}")
            continue
        try:
            resolve_within(entry, package_root, label=f"{label} entry {relative}")
        except ValueError as exc:
            errors.append(str(exc))
        folded_name = entry.name.casefold()
        if folded_name in DEBRIS_NAMES or folded_name.endswith(DEBRIS_SUFFIXES):
            errors.append(f"{label} contains forbidden debris: {relative}")
        if entry.is_dir():
            continue
        if not entry.is_file():
            errors.append(f"{label} contains a non-regular artifact: {relative}")
            continue
        file_count += 1
        if file_count > MAX_PACKAGE_FILES:
            errors.append(f"{label} exceeds the {MAX_PACKAGE_FILES}-file limit.")
            return errors
        try:
            size = entry.stat().st_size
        except OSError as exc:
            errors.append(f"{label} artifact is invalid: {relative} ({exc})")
            continue
        total_bytes += size
        if size > MAX_PACKAGE_FILE_BYTES:
            errors.append(f"{label} file exceeds the size limit ({MAX_PACKAGE_FILE_BYTES} bytes): {relative}")
        if entry.suffix.lower() not in TEXT_ARTIFACT_SUFFIXES:
            errors.append(f"{label} contains a non-text artifact: {relative}")
        else:
            scan_files.append(entry)
        if total_bytes > MAX_PACKAGE_BYTES:
            errors.append(f"{label} exceeds the total size limit ({MAX_PACKAGE_BYTES} bytes).")
            return errors
    if errors:
        return errors
    for path in scan_files:
        relative = path.relative_to(package_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{label} text artifact is invalid: {relative} ({exc})")
            continue
        if WINDOWS_PATH.search(text):
            errors.append(f"{label} contains a local machine path: {relative}")
        if SECRET_MATERIAL.search(text):
            errors.append(f"{label} contains secret material: {relative}")
    return errors


def _shared_references(text: str) -> set[str]:
    return {_relative_path(match.group("path")) for match in SHARED_REFERENCE.finditer(text)}


def _nested_shared_target(source: Path, relative: str, shared_root: Path) -> Path:
    candidate = source.parent / relative
    return resolve_within(candidate, shared_root, label=f"Shared reference {source.relative_to(shared_root).as_posix()}")


def _copy_shared_reference(
    source: Path,
    shared_root: Path,
    package_root: Path,
    copied: set[str],
    *,
    input_root: Path | None = None,
) -> None:
    shared_root = shared_root.resolve()
    relative_source = source.relative_to(shared_root)
    source_name = relative_source.as_posix()
    if source_name in copied:
        return
    copied.add(source_name)
    if source.suffix.lower() in VERBATIM_SHARED_SUFFIXES:
        target = package_root / "references" / relative_source
        target.parent.mkdir(parents=True, exist_ok=True)
        _safe_copy_file(source, target)
        return
    source_text = source.read_text(encoding="utf-8")
    nested_targets: list[tuple[str, Path]] = []
    for match in RELATIVE_REFERENCE.finditer(source_text):
        relative = _relative_path(match.group("path"))
        candidate = source.parent / relative
        if input_root is not None:
            _require_no_reparse_components(candidate, input_root, label=f"Shared reference {source_name}")
        nested = _nested_shared_target(source, relative, shared_root)
        if not nested.is_file():
            raise ValueError(f"Shared reference {source_name} is missing {relative}.")
        nested_targets.append((relative, nested))
    for _, nested in nested_targets:
        _copy_shared_reference(nested, shared_root, package_root, copied, input_root=input_root)
    source_directory = PurePosixPath(source_name).parent

    def rewrite(match: re.Match[str]) -> str:
        relative = _relative_path(match.group("path"))
        nested = _nested_shared_target(source, relative, shared_root)
        target_name = nested.relative_to(shared_root).as_posix()
        rewritten = PurePosixPath(posixpath.relpath(target_name, source_directory.as_posix())).as_posix()
        if not rewritten.startswith("../"):
            rewritten = f"./{rewritten}"
        return rewritten
    rewritten_text = RELATIVE_REFERENCE.sub(rewrite, source_text)
    target = package_root / "references" / relative_source
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rewritten_text, encoding="utf-8", newline="\n")


def _rewrite_skill_markdown(text: str) -> str:
    return SHARED_REFERENCE.sub(lambda match: f"references/{Path(match.group('path')).name}", text)


def _stage_work_mode_packages(root: Path, stage: Path) -> list[Path]:
    manifest = load_manifest(root)
    if manifest.get("version") != 1 or manifest.get("canonical_source") != CANONICAL_SOURCE:
        raise ValueError("Work Mode manifest has an invalid version or canonical_source.")
    entries = manifest.get("skills")
    if not isinstance(entries, list):
        raise ValueError("Work Mode manifest skills must be an array.")
    canonical_root = root / CANONICAL_SOURCE
    shared_root = root / SHARED_SOURCE
    _require_no_reparse_components(canonical_root, root, label="Canonical skill root")
    _require_no_reparse_components(shared_root, root, label="Shared reference root")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Work Mode manifest skill entry must be an object.")
        name = entry.get("name")
        work_mode = entry.get("work_mode")
        if not isinstance(name, str) or not SKILL_NAME.fullmatch(name) or len(name) > 64:
            raise ValueError("Work Mode manifest skill entry has an invalid name.")
        if name in seen:
            raise ValueError(f"Work Mode manifest contains duplicate skill {name}.")
        seen.add(name)
        if not isinstance(work_mode, dict):
            raise ValueError("Work Mode manifest skill entry is missing required fields.")
        package_path = work_mode.get("package_path")
        if package_path != f"plugins/coding-workflows/work-mode/dist/{name}":
            raise ValueError(f"Work Mode package path is invalid for {name}.")
        source = canonical_root / name
        package = stage / name
        _require_no_reparse_components(source, root, label=f"Canonical skill {name}")
        if not source.is_dir():
            raise ValueError(f"Canonical skill {name} does not exist.")
        _preflight_source_tree(source, label=f"Canonical skill {name} package source", ignored_directories=IGNORED_SOURCE_DIRECTORIES)
        skill_source = source / "SKILL.md"
        if not skill_source.is_file() or _is_reparse_point(skill_source):
            raise ValueError(f"Canonical skill {name} is missing SKILL.md.")
        canonical_text = skill_source.read_text(encoding="utf-8")
        shutil.copytree(
            source,
            package,
            ignore=shutil.ignore_patterns("agents", "__pycache__", "*.pyc"),
            copy_function=_safe_copy_file,
        )
        adaptation = work_mode.get("adaptation")
        if adaptation == "surface-adapted":
            adaptation_path = work_mode.get("adaptation_source")
            expected_adaptation = f"plugins/coding-workflows/work-mode/adaptations/{name}"
            if adaptation_path != expected_adaptation:
                raise ValueError(f"Work Mode adaptation source is invalid for {name}.")
            overlay = root / adaptation_path
            _require_no_reparse_components(overlay, root, label=f"Work Mode adaptation {name}")
            if not (overlay / "SKILL.md").is_file() or _is_reparse_point(overlay / "SKILL.md"):
                raise ValueError(f"Work Mode adaptation {name} is missing SKILL.md.")
            _preflight_source_tree(overlay, label=f"Work Mode adaptation {name}")
            shutil.copytree(overlay, package, dirs_exist_ok=True, copy_function=_safe_copy_file)
        elif adaptation != "shared-core":
            raise ValueError(f"Work Mode adaptation is invalid for {name}.")
        skill_path = package / "SKILL.md"
        source_text = skill_path.read_text(encoding="utf-8")
        skill_path.write_text(_rewrite_skill_markdown(source_text), encoding="utf-8", newline="\n")
        copied: set[str] = set()
        for reference_text in (canonical_text, source_text):
            for relative in _shared_references(reference_text):
                shared_source = source / relative
                _require_no_reparse_components(shared_source, root, label=f"Skill {name} shared reference")
                resolved = resolve_within(shared_source, shared_root, label=f"Skill {name} shared reference")
                if not resolved.is_file():
                    raise ValueError(f"Skill {name} shared reference is missing {relative}.")
                _copy_shared_reference(resolved, shared_root, package, copied, input_root=root)
        errors = package_material_errors(package, f"Work Mode package {name}")
        _validate_skill_metadata(skill_path, package, errors)
        _validate_package_references(package, errors, scan_sensitive_text=False)
        if errors:
            raise ValueError("Invalid staged Work Mode package: " + "; ".join(errors))
    return sorted(seen)


def build_packages(root: Path = ROOT, destination: Path | None = None) -> Path:
    manifest = load_manifest(root)
    entries = manifest.get("skills")
    if not isinstance(entries, list):
        raise ValueError("Work Mode manifest skills must be an array.")
    output = Path(os.path.abspath(destination or root / "plugins" / "coding-workflows" / "work-mode" / "dist"))
    canonical_root = root / CANONICAL_SOURCE
    shared_root = root / SHARED_SOURCE
    adaptation_root = root / "plugins" / "coding-workflows" / "work-mode" / "adaptations"
    adaptation_roots = tuple(
        adaptation_root / str(entry.get("name"))
        for entry in entries
        if isinstance(entry, dict)
    )
    protected_roots = (
        canonical_root,
        shared_root,
        root / "plugins" / "coding-workflows" / "work-mode" / "manifest.json",
        *adaptation_roots,
    )
    _preflight_output_destination(
        output,
        repository_root=root,
        protected_roots=protected_roots,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    _preflight_output_destination(
        output,
        repository_root=root,
        protected_roots=protected_roots,
    )
    stage = _create_sibling_stage(output)
    try:
        expected_names = _stage_work_mode_packages(root, stage)
        actual_entries = {entry.name for entry in stage.iterdir()}
        if actual_entries != set(expected_names) or any(not entry.is_dir() for entry in stage.iterdir()):
            raise ValueError("Staged Work Mode package set is invalid.")
        _preflight_output_destination(
            output,
            repository_root=root,
            protected_roots=protected_roots,
        )
        _preflight_output_destination(stage, protected_roots=protected_roots)
        _replace_staged_outputs([(output, stage)])
    except BaseException:
        _remove_stage(stage)
        raise
    return output


def _validate_skill_metadata(skill_path: Path, package_root: Path, errors: list[str]) -> None:
    try:
        metadata = parse_skill_frontmatter(skill_path)
    except (OSError, ValueError) as exc:
        errors.append(f"Work Mode package {package_root.name} has invalid SKILL.md: {exc}")
        return
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not isinstance(name, str) or not SKILL_NAME.fullmatch(name) or len(name) > 64:
        errors.append(f"Work Mode package {package_root.name} has an invalid Agent Skills name.")
    elif name != package_root.name:
        errors.append(f"Work Mode package {package_root.name} name does not match its directory.")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        errors.append(f"Work Mode package {package_root.name} has an invalid Agent Skills description.")


def _validate_package_references(
    package_root: Path, errors: list[str], *, scan_sensitive_text: bool = True
) -> None:
    for entry in _iter_package_entries(package_root):
        if _is_reparse_point(entry):
            errors.append(f"Work Mode package {package_root.name} must not use symlinks or reparse points: {entry.relative_to(package_root)}")
            continue
        try:
            resolve_within(entry, package_root, label=f"Work Mode package entry {entry.name}")
        except ValueError as exc:
            errors.append(str(exc))
    for path in _iter_package_entries(package_root):
        if not path.is_file() or path.suffix.lower() not in TEXT_ARTIFACT_SUFFIXES:
            continue
        try:
            require_repository_path(path, package_root, label=f"Work Mode package file {path.name}")
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if scan_sensitive_text:
            if WINDOWS_PATH.search(text):
                errors.append(f"Work Mode package {package_root.name} contains a local machine path: {path.relative_to(package_root)}")
            if SECRET_MATERIAL.search(text):
                errors.append(f"Work Mode package {package_root.name} contains secret material: {path.relative_to(package_root)}")
        for match in PACKAGE_REFERENCE.finditer(text):
            raw_path = _relative_path(match.group("path"))
            try:
                resolved = resolve_within(path.parent / raw_path, package_root, label=f"Work Mode package reference {raw_path}")
            except ValueError:
                errors.append(f"Work Mode package {package_root.name} reference escapes package root: {raw_path}")
                continue
            if not resolved.is_file():
                errors.append(f"Work Mode package {package_root.name} reference is missing: {raw_path}")


def validate_packages(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load_manifest(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"Invalid Work Mode manifest: {exc}"]
    if manifest.get("version") != 1 or manifest.get("canonical_source") != CANONICAL_SOURCE:
        return ["Invalid Work Mode manifest: version or canonical source is invalid."]
    entries = manifest.get("skills")
    if not isinstance(entries, list):
        return ["Invalid Work Mode manifest: skills must be an array."]
    seen: set[str] = set()
    dist = root / "plugins" / "coding-workflows" / "work-mode" / "dist"
    expected_packages: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("Invalid Work Mode manifest: skill entry must be an object.")
            continue
        name = entry.get("name")
        codex = entry.get("codex")
        work_mode = entry.get("work_mode")
        adaptation = work_mode.get("adaptation") if isinstance(work_mode, dict) else None
        if not isinstance(name, str) or not name:
            errors.append("Invalid Work Mode manifest: skill entry is missing a name.")
            continue
        if name in seen:
            errors.append(f"Invalid Work Mode manifest: duplicate skill {name}.")
        seen.add(name)
        expected_source = f"plugins/coding-workflows/skills/{name}"
        if codex != {"plugin": "coding-workflows", "source_path": expected_source, "delivery": "plugin-skill"}:
            errors.append(f"Invalid Work Mode manifest: Codex mapping for {name} is invalid.")
        expected_work_mode = {
            "personal_skill": name,
            "generated_from": expected_source,
            "package_path": f"plugins/coding-workflows/work-mode/dist/{name}",
            "adaptation": adaptation,
            "delivery": "separate-personal-skill-package",
            "package_state": "generated-and-validated",
        }
        if isinstance(work_mode, dict) and work_mode.get("adaptation") == "surface-adapted":
            expected_work_mode["adaptation_source"] = f"plugins/coding-workflows/work-mode/adaptations/{name}"
        if not isinstance(adaptation, str):
            errors.append(f"Invalid Work Mode manifest: adaptation for {name} is invalid.")
            continue
        if not isinstance(work_mode, dict) or work_mode != expected_work_mode:
            errors.append(f"Invalid Work Mode manifest: Work Mode mapping for {name} is invalid.")
            continue
        if adaptation not in {"shared-core", "surface-adapted"}:
            errors.append(f"Invalid Work Mode manifest: adaptation for {name} is invalid.")
        expected_packages.add(name)
    try:
        _preflight_output_destination(
            dist,
            repository_root=root,
            protected_roots=(
                root / CANONICAL_SOURCE,
                root / SHARED_SOURCE,
                root / "plugins" / "coding-workflows" / "work-mode" / "manifest.json",
            ),
        )
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        return errors
    if not dist.is_dir():
        errors.append("Work Mode package dist directory is missing.")
        return errors
    actual_entries = list(dist.iterdir())
    actual_packages = {path.name for path in actual_entries if path.is_dir()}
    unexpected = {path.name for path in actual_entries if not path.is_dir()}
    if unexpected:
        errors.append(f"Work Mode dist contains unexpected entries: {sorted(unexpected)}")
    if actual_packages != expected_packages:
        errors.append(f"Work Mode package set mismatch: packages={sorted(actual_packages)}, manifest={sorted(expected_packages)}")
    for package_name in sorted(expected_packages & actual_packages):
        package = dist / package_name
        try:
            require_repository_path(package, root, label=f"Work Mode package {package_name}")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        skill_path = package / "SKILL.md"
        if not skill_path.is_file():
            errors.append(f"Work Mode package {package_name} is missing SKILL.md.")
            continue
        material_errors = package_material_errors(package, f"Work Mode package {package_name}")
        errors.extend(material_errors)
        if not material_errors:
            _validate_skill_metadata(skill_path, package, errors)
            _validate_package_references(package, errors, scan_sensitive_text=True)
    return errors


def packages_are_current(root: Path = ROOT, *, details: dict[str, str] | None = None) -> bool:
    """Report whether generated output matches a fresh build.

    Returns True only when the output is current. Records a ``status`` entry
    in ``details`` when provided: ``current``, ``stale``, or ``build_failed``
    (with an ``error`` entry). A failed rebuild is not ordinary staleness, so
    callers surface it as a packaging failure instead.
    """

    def record(status: str, error: str | None = None) -> bool:
        if details is not None:
            details["status"] = status
            if error is not None:
                details["error"] = error
            elif "error" in details:
                del details["error"]
        return status == "current"

    with tempfile.TemporaryDirectory() as temporary:
        try:
            expected = build_packages(root, Path(temporary) / "dist")
        except (OSError, RuntimeError, ValueError) as exc:
            return record("build_failed", str(exc))
        actual = root / "plugins" / "coding-workflows" / "work-mode" / "dist"
        try:
            _preflight_output_destination(
                actual,
                repository_root=root,
                protected_roots=(
                root / CANONICAL_SOURCE,
                root / SHARED_SOURCE,
                root / "plugins" / "coding-workflows" / "work-mode" / "manifest.json",
            ),
            )
        except (OSError, ValueError) as exc:
            return record("build_failed", str(exc))
        if not actual.is_dir():
            return record("stale")
        return record("current" if _same_tree(expected, actual) else "stale")


def _same_tree(expected: Path, actual: Path) -> bool:
    expected_entries = sorted(path.relative_to(expected) for path in _iter_package_entries(expected))
    actual_entries = sorted(path.relative_to(actual) for path in _iter_package_entries(actual))
    if expected_entries != actual_entries:
        return False
    return all(
        (expected / expected_entry).is_dir()
        or _same_file(expected / expected_entry, actual / actual_entry)
        for expected_entry, actual_entry in zip(expected_entries, actual_entries, strict=True)
    )


def _same_file(expected: Path, actual: Path) -> bool:
    expected_bytes = expected.read_bytes()
    actual_bytes = actual.read_bytes()
    if expected.suffix.lower() not in TEXT_ARTIFACT_SUFFIXES:
        return expected_bytes == actual_bytes
    try:
        expected_text = expected_bytes.decode("utf-8")
        actual_text = actual_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return expected_bytes == actual_bytes
    return expected_text.replace("\r\n", "\n").replace("\r", "\n") == actual_text.replace("\r\n", "\n").replace("\r", "\n")
