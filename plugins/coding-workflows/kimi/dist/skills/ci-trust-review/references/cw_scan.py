"""Shared offline scanning primitives for coding-workflows skill helpers.

Bounded non-following filesystem walks, text and binary classification, secret
signature detection with redaction, credential stripping for URLs, and the JSON
evidence envelope every helper emits. Standard library only; no network and no
subprocess use.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit, urlunsplit


SCHEMA = "coding-workflows/helper-evidence"
SCHEMA_VERSION = 1
SEVERITIES = ("Blocker", "Important", "Minor")
COVERAGE_STATES = ("flagged", "clear", "not checked", "blocked")

# Secret signatures. Literal examples of these formats must never appear in the
# repository, so the private-key marker is assembled from parts.
_PEM = "-----BEGIN " + "[A-Z0-9 ]*" + "PRIVATE KEY" + "-----"
SECRET_SIGNATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key-block", re.compile(_PEM)),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,255}\b")),
    ("github-fine-grained-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,255}\b")),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("api-secret-key", re.compile(r"(?<![A-Za-z0-9_-])sk-(?:ant-|proj-|live-)?[A-Za-z0-9_-]{20,}")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe-live-key", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{16,}")),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    (
        "credential-assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|access[_-]?token|auth[_-]?token|password|passwd)\b"
            r"[\"']?\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']"
        ),
    ),
)

# Generic pattern rules are less certain than format-specific signatures; obvious
# documentation placeholders are skipped for them.
HEURISTIC_SECRET_RULES = frozenset({"credential-assignment"})
PLACEHOLDER_VALUE = re.compile(
    r"(?i)^(?:your|my|example|sample|dummy|placeholder|changeme|test|fake|redacted|xxx)|your[-_]|example|placeholder"
    r"|^<[^>]*>$|^[$][{][^}]*[}]$|^[*.x]+$"
)

# Characters that change how text renders without being visible.
INVISIBLE_CODEPOINTS = frozenset(
    [*range(0x202A, 0x202F), *range(0x2066, 0x206A), 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF]
)

_BINARY_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x7fELF", "elf-executable"),
    (b"MZ", "windows-executable"),
    (b"\xcf\xfa\xed\xfe", "mach-o-executable"),
    (b"\xce\xfa\xed\xfe", "mach-o-executable"),
    (b"\xca\xfe\xba\xbe", "mach-o-universal-or-java-class"),
    (b"\x00asm", "webassembly"),
    (b"PK\x03\x04", "zip-archive"),
    (b"\x1f\x8b", "gzip-archive"),
    (b"\x89PNG", "png-image"),
    (b"GIF8", "gif-image"),
    (b"\xff\xd8\xff", "jpeg-image"),
    (b"%PDF", "pdf-document"),
)
EXECUTABLE_BINARY_KINDS = frozenset(
    {"elf-executable", "windows-executable", "mach-o-executable", "mach-o-universal-or-java-class", "webassembly"}
)


@dataclass
class Limits:
    max_depth: int = 24
    max_files: int = 5000
    max_file_bytes: int = 1_048_576
    max_total_bytes: int = 52_428_800


@dataclass
class WalkEntry:
    relative: str
    path: Path
    kind: str  # "file", "dir", "symlink", "reparse-point", or "other"
    depth: int
    size: int = 0
    mode: int = 0
    link_target: str | None = None


@dataclass
class WalkResult:
    entries: list[WalkEntry] = field(default_factory=list)
    limits_reached: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _is_reparse(metadata: os.stat_result) -> bool:
    attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(metadata, "st_file_attributes", 0) & attribute)


def walk(root: Path, limits: Limits, skip_dirs: frozenset[str] = frozenset()) -> WalkResult:
    """Enumerate a tree without following links, stopping at the given limits.

    Directories whose case-folded name is in ``skip_dirs`` are recorded but not entered.
    """

    result = WalkResult()
    files = 0
    pending: list[tuple[Path, str, int]] = [(root, "", 0)]
    while pending:
        directory, prefix, depth = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                children = sorted(iterator, key=lambda item: item.name)
        except OSError as exc:
            result.errors.append(f"{prefix or '.'}: {exc.strerror or exc}")
            continue
        for child in children:
            relative = f"{prefix}{child.name}"
            path = Path(child.path)
            try:
                metadata = os.lstat(path)
            except OSError as exc:
                result.errors.append(f"{relative}: {exc.strerror or exc}")
                continue
            if stat.S_ISLNK(metadata.st_mode):
                try:
                    target = os.readlink(path)
                except OSError:
                    target = None
                result.entries.append(WalkEntry(relative, path, "symlink", depth + 1, link_target=target))
                continue
            if _is_reparse(metadata):
                result.entries.append(WalkEntry(relative, path, "reparse-point", depth + 1))
                continue
            if stat.S_ISDIR(metadata.st_mode):
                result.entries.append(WalkEntry(relative, path, "dir", depth + 1))
                if child.name.casefold() in skip_dirs:
                    continue
                if depth + 1 >= limits.max_depth:
                    result.limits_reached.append(f"max-depth {limits.max_depth} reached at {relative}")
                    continue
                pending.append((path, f"{relative}/", depth + 1))
                continue
            if not stat.S_ISREG(metadata.st_mode):
                result.entries.append(WalkEntry(relative, path, "other", depth + 1, mode=metadata.st_mode))
                continue
            files += 1
            if files > limits.max_files:
                result.limits_reached.append(f"max-files {limits.max_files} reached")
                return result
            result.entries.append(
                WalkEntry(relative, path, "file", depth + 1, size=metadata.st_size, mode=metadata.st_mode)
            )
    return result


def link_escapes(entry_relative: str, target: str) -> tuple[bool, bool]:
    """Return (is_absolute, escapes_root) for a link target, resolved lexically."""

    normalized = target.replace(chr(92), "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        return True, True
    parts = entry_relative.split("/")[:-1]
    for part in normalized.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return False, True
            parts.pop()
        else:
            parts.append(part)
    return False, False


def binary_kind(head: bytes) -> str | None:
    """Classify leading bytes; return None for probable UTF-8 text."""

    for magic, kind in _BINARY_MAGIC:
        if head.startswith(magic):
            return kind
    if b"\x00" in head[:8192]:
        return "binary-data"
    try:
        head[:8192].decode("utf-8")
    except UnicodeDecodeError as exc:
        # A multi-byte sequence cut by the sample boundary is still text.
        if exc.start < len(head[:8192]) - 4:
            return "binary-data"
    return None


def read_bounded(path: Path, max_bytes: int) -> tuple[bytes, bool]:
    """Read at most max_bytes; return (data, truncated)."""

    with open(path, "rb") as handle:
        data = handle.read(max_bytes + 1)
    return data[:max_bytes], len(data) > max_bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, max_bytes: int | None = None) -> str | None:
    digest = hashlib.sha256()
    total = 0
    try:
        with open(path, "rb") as handle:
            while chunk := handle.read(65536):
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    return None
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def secret_hits(text: str) -> list[tuple[str, int]]:
    """Return (rule, line number) for each secret signature match; never the value."""

    hits: list[tuple[str, int]] = []
    for rule, pattern in SECRET_SIGNATURES:
        for match in pattern.finditer(text):
            if rule in HEURISTIC_SECRET_RULES:
                quoted = re.search(r"[\"']([^\"']+)[\"']\s*$", match.group(0))
                if quoted and PLACEHOLDER_VALUE.search(quoted.group(1)):
                    continue
            hits.append((rule, text.count("\n", 0, match.start()) + 1))
    return hits


def redact(text: str) -> str:
    for rule, pattern in SECRET_SIGNATURES:
        text = pattern.sub(f"[REDACTED:{rule}]", text)
    return text


def excerpt(line: str, limit: int = 120) -> str:
    """A redacted, single-line, bounded excerpt safe to include in evidence."""

    cleaned = "".join(
        "?" if ord(character) in INVISIBLE_CODEPOINTS else character for character in line.strip()
    )
    cleaned = redact(cleaned)
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."


def invisible_characters(text: str) -> list[int]:
    """Line numbers containing bidirectional or zero-width characters."""

    lines: list[int] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line[1:] if number == 1 and line.startswith(chr(0xFEFF)) else line
        if any(ord(character) in INVISIBLE_CODEPOINTS for character in stripped):
            lines.append(number)
    return lines


def strip_url_credentials(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return "[unparseable-url]"
    if parts.username is None and parts.password is None:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def finding(rule: str, family: str, severity: str, path: str, line: int | None, context: str,
            detail: str) -> dict[str, object]:
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity {severity}")
    return {
        "rule": rule,
        "family": family,
        "severity": severity,
        "path": path,
        "line": line,
        "context": context,
        "detail": excerpt(detail, 160),
    }


def coverage(state: str, reason: str | None = None) -> dict[str, str]:
    if state not in COVERAGE_STATES:
        raise ValueError(f"unknown coverage state {state}")
    if state in ("not checked", "blocked") and not reason:
        raise ValueError(f"coverage state {state} requires a reason")
    record = {"state": state}
    if reason:
        record["reason"] = reason
    return record


def envelope(tool: str, inputs: dict[str, object], **sections: object) -> dict[str, object]:
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "tool": tool, "inputs": inputs, **sections}


def emit(document: dict[str, object], output: str | None = None) -> None:
    """Print JSON to stdout, or write it only to an explicitly requested path."""

    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8", newline="\n")
        return
    sys.stdout.write(text)


def iter_lines(text: str) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(text.splitlines(), start=1):
        yield number, line


def require_python() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("This helper requires Python 3.11 or newer.")
