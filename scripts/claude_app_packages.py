"""Build and validate Claude app (claude.ai) Custom Skill ZIP packages."""

from __future__ import annotations

import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from repository_inventory import (
    ROOT,
    parse_skill_frontmatter_text,
    require_repository_path,
    resolve_within,
    validate_excluded_skill_names,
)
from work_mode_packages import (
    MAX_PACKAGE_BYTES,
    MAX_PACKAGE_FILE_BYTES,
    MAX_PACKAGE_FILES,
    PACKAGE_REFERENCE,
    SECRET_MATERIAL,
    SKILL_NAME,
    TEXT_ARTIFACT_SUFFIXES,
    WINDOWS_PATH,
    _copy_shared_reference,
    _create_sibling_stage,
    _is_reparse_point,
    _preflight_output_destination,
    _preflight_source_tree,
    _relative_path,
    _remove_stage,
    _replace_staged_outputs,
    _require_no_reparse_components,
    _rewrite_skill_markdown,
    _safe_copy_file,
    _shared_references,
    IGNORED_SOURCE_DIRECTORIES,
    package_material_errors,
)


CLAUDE_APP_ROOT = ROOT / "plugins" / "coding-workflows" / "claude-app"
MANIFEST_PATH = CLAUDE_APP_ROOT / "manifest.json"
DIST_ROOT = CLAUDE_APP_ROOT / "dist"
CANONICAL_SOURCE = "plugins/coding-workflows/skills"
SHARED_SOURCE = "plugins/coding-workflows/references"
PACKAGE_SUFFIX = ".zip"
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
MAX_ZIP_ARCHIVE_BYTES = MAX_PACKAGE_BYTES
MAX_ZIP_MEMBERS = MAX_PACKAGE_FILES
MAX_ZIP_MEMBER_BYTES = MAX_PACKAGE_FILE_BYTES
MAX_ZIP_TOTAL_BYTES = MAX_PACKAGE_BYTES
MAX_ZIP_COMPRESSION_RATIO = 100
MAX_ZIP_NAME_BYTES = 512
MAX_ZIP_PATH_DEPTH = 32
SUPPORTED_ZIP_COMPRESSIONS = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})
RESERVED_NAME_WORDS = ("anthropic", "claude")
XML_TAG = re.compile(r"<[^>\n]*>")


def load_manifest(root: Path = ROOT) -> dict[str, Any]:
    path = root / "plugins" / "coding-workflows" / "claude-app" / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Claude app manifest must be a JSON object.")
    return data


def discover_canonical_skills(root: Path = ROOT) -> list[str]:
    canonical_root = root / CANONICAL_SOURCE
    _require_no_reparse_components(canonical_root, root, label="Canonical skill root")
    names = []
    for entry in sorted(canonical_root.iterdir()):
        if _require_is_regular_entry(entry, root, label="Canonical skill entry"):
            names.append(entry.name)
    return names


def _require_is_regular_entry(entry: Path, root: Path, *, label: str) -> bool:
    if entry.name in IGNORED_SOURCE_DIRECTORIES or entry.name.casefold().endswith((".pyc", ".pyo")):
        return False
    _require_no_reparse_components(entry, root, label=label)
    if not entry.is_dir() or not (entry / "SKILL.md").is_file():
        return False
    return True


def _active_skill_names(root: Path, manifest: dict[str, Any]) -> list[str]:
    canonical_names = discover_canonical_skills(root)
    excluded = validate_excluded_skill_names(set(canonical_names), manifest.get("excluded_skills", []))
    return [name for name in canonical_names if name not in excluded]


def active_skill_names(root: Path = ROOT, manifest: dict[str, Any] | None = None) -> list[str]:
    return _active_skill_names(root, manifest if manifest is not None else load_manifest(root))


def _write_deterministic_zip(source_dir: Path, zip_path: Path, root_name: str) -> None:
    material_errors = package_material_errors(source_dir, f"Claude app package {root_name}")
    if material_errors:
        raise ValueError("Invalid Claude app package material: " + "; ".join(material_errors))
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(
        (path for path in source_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(source_dir).as_posix(),
    )
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            arcname = f"{root_name}/{path.relative_to(source_dir).as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=ZIP_EPOCH)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            data = path.read_bytes()
            if path.suffix.lower() in TEXT_ARTIFACT_SUFFIXES:
                data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            archive.writestr(info, data)


def _stage_claude_packages(root: Path, stage: Path, names: list[str]) -> None:
    canonical_root = root / CANONICAL_SOURCE
    shared_root = root / SHARED_SOURCE
    _require_no_reparse_components(canonical_root, root, label="Canonical skill root")
    _require_no_reparse_components(shared_root, root, label="Shared reference root")
    for name in names:
        source = canonical_root / name
        _require_no_reparse_components(source, root, label=f"Canonical skill {name}")
        if not source.is_dir():
            raise ValueError(f"Canonical skill {name} does not exist.")
        _preflight_source_tree(source, label=f"Canonical skill {name} package source", ignored_directories=IGNORED_SOURCE_DIRECTORIES)
        skill_source = source / "SKILL.md"
        if not skill_source.is_file():
            raise ValueError(f"Canonical skill {name} is missing SKILL.md.")
        canonical_text = skill_source.read_text(encoding="utf-8")
        package = stage / f".{name}"
        shutil.copytree(
            source,
            package,
            ignore=shutil.ignore_patterns("agents", "__pycache__", "*.pyc"),
            copy_function=_safe_copy_file,
        )
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
                    raise ValueError(f"Skill {name} shared reference is missing: {relative}.")
                _copy_shared_reference(resolved, shared_root, package, copied, input_root=root)
        _write_deterministic_zip(package, stage / f"{name}{PACKAGE_SUFFIX}", name)
        _remove_stage(package)


def build_packages(root: Path = ROOT, destination: Path | None = None) -> Path:
    manifest = load_manifest(root)
    if manifest.get("version") != 1 or manifest.get("canonical_source") != CANONICAL_SOURCE:
        raise ValueError("Claude app manifest has an invalid version or canonical_source.")
    if manifest.get("package_root") != "plugins/coding-workflows/claude-app/dist":
        raise ValueError("Claude app manifest has an invalid package_root.")
    if manifest.get("package_suffix") != PACKAGE_SUFFIX:
        raise ValueError("Claude app manifest has an invalid package_suffix.")
    names = _active_skill_names(root, manifest)
    output = destination or root / "plugins" / "coding-workflows" / "claude-app" / "dist"
    output = output.absolute()
    protected_roots = (
        root / CANONICAL_SOURCE,
        root / SHARED_SOURCE,
        root / "plugins" / "coding-workflows" / "claude-app" / "manifest.json",
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
        _stage_claude_packages(root, stage, names)
        expected_files = {f"{name}{PACKAGE_SUFFIX}" for name in names}
        if {entry.name for entry in stage.iterdir()} != expected_files:
            raise ValueError("Staged Claude app package set is invalid.")
        errors: list[str] = []
        for name in names:
            _validate_zip_package(stage / f"{name}{PACKAGE_SUFFIX}", name, errors)
        if errors:
            raise ValueError("Invalid staged Claude app packages: " + "; ".join(errors))
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


def _resolve_zip_reference(entry_name: str, raw_path: str, expected_name: str) -> str | None:
    entry_dir = PurePosixPath(entry_name).parent
    normalized: list[str] = []
    for part in (*entry_dir.parts, *raw_path.split("/")):
        if part in ("", "."):
            continue
        if part == "..":
            if len(normalized) <= 1:
                return None
            normalized.pop()
            continue
        normalized.append(part)
    if not normalized or normalized[0] != expected_name:
        return None
    return "/".join(normalized)


def _read_zip_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    chunks: list[bytes] = []
    remaining = MAX_ZIP_MEMBER_BYTES + 1
    with archive.open(info, "r") as stream:
        while remaining:
            chunk = stream.read(min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    data = b"".join(chunks)
    if len(data) > MAX_ZIP_MEMBER_BYTES:
        raise ValueError(f"expanded member exceeds the {MAX_ZIP_MEMBER_BYTES}-byte read limit: {info.filename}")
    if len(data) != info.file_size:
        raise ValueError(f"expanded member size does not match ZIP metadata: {info.filename}")
    return data


def _zip_metadata_errors(infos: list[zipfile.ZipInfo]) -> list[str]:
    # Fail fast on the member-count bound before any per-member work so
    # oversized archives never pay for collision or metadata scans.
    if len(infos) > MAX_ZIP_MEMBERS:
        return [f"Claude app package exceeds the {MAX_ZIP_MEMBERS}-member limit."]
    names = [info.filename for info in infos]
    # Bound each name before prefix work: collision detection costs
    # O(depth * length) per name, so unbounded names would be quadratic.
    if any(
        len(name.encode("utf-8", errors="surrogatepass")) > MAX_ZIP_NAME_BYTES
        or name.count("/") > MAX_ZIP_PATH_DEPTH
        for name in names
    ):
        return [
            f"Claude app package contains a ZIP entry name longer than {MAX_ZIP_NAME_BYTES} bytes "
            f"or deeper than {MAX_ZIP_PATH_DEPTH} path components."
        ]
    errors: list[str] = []
    if len(names) != len(set(names)):
        errors.append("Claude app package contains duplicate ZIP entries.")
    folded_names = [name.casefold() for name in names]
    if len(folded_names) != len(set(folded_names)):
        errors.append("Claude app package contains case-folded duplicate ZIP entries.")
    # A name collides when another entry is one of its parent paths, or when
    # it is itself a parent path of another entry. One pass over each name's
    # parent prefixes marks both sides without storing every prefix.
    name_set = set(names)
    colliding: set[str] = set()
    for name in names:
        index = name.find("/")
        while index != -1:
            parent = name[:index]
            if parent in name_set:
                colliding.add(name)
                colliding.add(parent)
            index = name.find("/", index + 1)
    for name in names:
        if name in colliding:
            errors.append(f"Claude app package contains a file/directory path collision: {name!r}")
    total_size = 0
    total_compressed = 0
    for info in infos:
        name = info.filename
        parts = PurePosixPath(name).parts
        canonical_name = PurePosixPath(name).as_posix()
        if (
            not name
            or name.startswith("/")
            or "\\" in name
            or ".." in parts
            or not parts
            or canonical_name != name
            or "//" in name
        ):
            errors.append(f"Claude app package contains an unsafe path: {name!r}")
            continue
        if info.flag_bits & 0x1:
            errors.append(f"Claude app package contains an encrypted member: {name}")
        if info.compress_type not in SUPPORTED_ZIP_COMPRESSIONS:
            errors.append(f"Claude app package contains unsupported compression: {name}")
        unix_mode = info.external_attr >> 16
        file_type = stat.S_IFMT(unix_mode)
        if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
            errors.append(f"Claude app package contains a non-regular ZIP member: {name}")
        if info.file_size > MAX_ZIP_MEMBER_BYTES:
            errors.append(f"Claude app package member exceeds the {MAX_ZIP_MEMBER_BYTES}-byte size limit: {name}")
        total_size += info.file_size
        total_compressed += info.compress_size
        if info.file_size and info.compress_size == 0:
            errors.append(f"Claude app package member has an invalid compression ratio: {name}")
        elif info.file_size > info.compress_size * MAX_ZIP_COMPRESSION_RATIO:
            errors.append(f"Claude app package member exceeds the {MAX_ZIP_COMPRESSION_RATIO}:1 compression ratio: {name}")
        folded_name = PurePosixPath(name).name.casefold()
        if folded_name in {"__pycache__", ".ds_store", "thumbs.db", ".git", ".venv", ".artifacts", ".pytest_cache", ".cache", "node_modules", "agents"}:
            errors.append(f"Claude app package contains excluded content: {name}")
        if len(parts) > 1 and parts[1].casefold() == "agents":
            errors.append(f"Claude app package contains excluded content: {name}")
        if not info.is_dir() and PurePosixPath(name).suffix.casefold() not in TEXT_ARTIFACT_SUFFIXES:
            errors.append(f"Claude app package contains a non-text artifact: {name}")
    if total_size > MAX_ZIP_TOTAL_BYTES:
        errors.append(f"Claude app package exceeds the {MAX_ZIP_TOTAL_BYTES}-byte expanded size limit.")
    if total_size and total_compressed and total_size > total_compressed * MAX_ZIP_COMPRESSION_RATIO:
        errors.append(f"Claude app package exceeds the {MAX_ZIP_COMPRESSION_RATIO}:1 aggregate compression ratio.")
    return errors


def _validate_zip_package(zip_path: Path, expected_name: str, errors: list[str]) -> None:
    try:
        archive_size = zip_path.stat().st_size
    except OSError as exc:
        errors.append(f"Claude app package {zip_path.name} is invalid: {exc}")
        return
    if archive_size > MAX_ZIP_ARCHIVE_BYTES:
        errors.append(f"Claude app package {zip_path.name} exceeds the {MAX_ZIP_ARCHIVE_BYTES}-byte archive limit.")
        return
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            metadata_errors = _zip_metadata_errors(infos)
            if metadata_errors:
                errors.extend(f"Claude app package {zip_path.name}: {error}" for error in metadata_errors)
                return
            names = {info.filename for info in infos}
            top_level = {name.split("/", 1)[0] for name in names}
            if top_level != {expected_name}:
                errors.append(
                    f"Claude app package {zip_path.name} must contain exactly one top-level directory "
                    f"named {expected_name!r}; found {sorted(top_level)}."
                )
                return
            skill_entry = f"{expected_name}/SKILL.md"
            skill_info = next((info for info in infos if info.filename == skill_entry and not info.is_dir()), None)
            if skill_info is None:
                errors.append(f"Claude app package {zip_path.name} is missing {skill_entry}.")
                return
            text_entries = [info for info in infos if not info.is_dir() and PurePosixPath(info.filename).suffix.casefold() in TEXT_ARTIFACT_SUFFIXES]
            text_data: dict[str, bytes] = {}
            for info in text_entries:
                text_data[info.filename] = _read_zip_member(archive, info)
    except (zipfile.BadZipFile, OSError, KeyError, RuntimeError, ValueError, NotImplementedError) as exc:
        errors.append(f"Claude app package {zip_path.name} is invalid: {exc}")
        return
    try:
        skill_text = text_data[skill_entry].decode("utf-8")
    except (KeyError, UnicodeDecodeError) as exc:
        errors.append(f"Claude app package {zip_path.name} has invalid SKILL.md: {exc}")
        return
    try:
        metadata = parse_skill_frontmatter_text(skill_text, label=skill_entry)
    except ValueError as exc:
        errors.append(f"Claude app package {zip_path.name} has invalid SKILL.md: {exc}")
        return
    skill_name = metadata.get("name", "")
    if skill_name != expected_name:
        errors.append(
            f"Claude app package {zip_path.name} SKILL.md name {skill_name!r} does not match "
            f"folder {expected_name!r}."
        )
    if not isinstance(skill_name, str) or not SKILL_NAME.fullmatch(skill_name) or len(skill_name) > 64:
        errors.append(f"Claude app package {zip_path.name} has an invalid Custom Skill name.")
    elif any(word in skill_name.casefold() for word in RESERVED_NAME_WORDS):
        errors.append(f"Claude app package {zip_path.name} name contains a reserved word: {skill_name!r}.")
    if XML_TAG.search(skill_name if isinstance(skill_name, str) else ""):
        errors.append(f"Claude app package {zip_path.name} name must not contain XML tags.")
    description = metadata.get("description", "")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        errors.append(f"Claude app package {zip_path.name} has an invalid Custom Skill description.")
    elif XML_TAG.search(description):
        errors.append(f"Claude app package {zip_path.name} description must not contain XML tags.")
    for name, data in text_data.items():
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"Claude app package {zip_path.name} has invalid text content: {name} ({exc})")
            continue
        if WINDOWS_PATH.search(text):
            errors.append(f"Claude app package {zip_path.name} contains a local machine path: {name}")
        if SECRET_MATERIAL.search(text):
            errors.append(f"Claude app package {zip_path.name} contains secret material: {name}")
        for match in PACKAGE_REFERENCE.finditer(text):
            raw_path = _relative_path(match.group("path"))
            resolved = _resolve_zip_reference(name, raw_path, expected_name)
            if resolved is None:
                errors.append(f"Claude app package {zip_path.name} reference escapes package root: {raw_path}")
            elif resolved not in {info.filename for info in infos}:
                errors.append(f"Claude app package {zip_path.name} reference is missing: {raw_path}")


def validate_packages(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load_manifest(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"Invalid Claude app manifest: {exc}"]
    if manifest.get("version") != 1 or manifest.get("canonical_source") != CANONICAL_SOURCE:
        return ["Invalid Claude app manifest: version or canonical source is invalid."]
    if manifest.get("package_root") != "plugins/coding-workflows/claude-app/dist":
        return ["Invalid Claude app manifest: package_root is invalid."]
    if manifest.get("package_suffix") != PACKAGE_SUFFIX:
        return ["Invalid Claude app manifest: package_suffix is invalid."]
    try:
        expected_names = set(_active_skill_names(root, manifest))
        dist = root / "plugins" / "coding-workflows" / "claude-app" / "dist"
        _preflight_output_destination(
            dist,
            repository_root=root,
            protected_roots=(root / CANONICAL_SOURCE, root / SHARED_SOURCE),
        )
    except (OSError, ValueError) as exc:
        return [str(exc)]
    if not dist.is_dir():
        return ["Claude app package dist directory is missing."]
    expected_files = {f"{name}{PACKAGE_SUFFIX}" for name in expected_names}
    entries = list(dist.iterdir())
    actual_files = {path.name for path in entries if path.is_file() and not _is_reparse_point(path)}
    unexpected = {path.name for path in entries if path.name not in expected_files}
    if unexpected:
        errors.append(f"Claude app dist contains unexpected entries: {sorted(unexpected)}")
    if actual_files != expected_files:
        errors.append(
            f"Claude app package set mismatch: packages={sorted(actual_files)}, expected={sorted(expected_files)}"
        )
    for name in sorted(expected_names):
        zip_path = dist / f"{name}{PACKAGE_SUFFIX}"
        if not zip_path.is_file():
            errors.append(f"Claude app package is missing: {zip_path.name}")
            continue
        if _is_reparse_point(zip_path):
            errors.append(f"Claude app package must not use symlinks or reparse points: {zip_path.name}")
            continue
        try:
            require_repository_path(zip_path, root, label=f"Claude app package {name}")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        _validate_zip_package(zip_path, name, errors)
    return errors


def packages_are_current(root: Path = ROOT, *, details: dict[str, str] | None = None) -> bool:
    """Report whether generated ZIP output matches a fresh build.

    Records ``current``, ``stale``, or ``build_failed`` in ``details`` when
    provided; a failed rebuild is a packaging failure, not ordinary staleness.
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
        actual = root / "plugins" / "coding-workflows" / "claude-app" / "dist"
        try:
            _preflight_output_destination(
                actual,
                repository_root=root,
                protected_roots=(root / CANONICAL_SOURCE, root / SHARED_SOURCE),
            )
        except (OSError, ValueError) as exc:
            return record("build_failed", str(exc))
        if not actual.is_dir():
            return record("stale")
        expected_files = sorted(path.name for path in expected.glob(f"*{PACKAGE_SUFFIX}"))
        actual_files = sorted(path.name for path in actual.glob(f"*{PACKAGE_SUFFIX}"))
        if expected_files != actual_files:
            return record("stale")
        same = all((expected / name).read_bytes() == (actual / name).read_bytes() for name in expected_files)
        return record("current" if same else "stale")
