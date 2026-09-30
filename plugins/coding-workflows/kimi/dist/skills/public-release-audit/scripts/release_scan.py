"""Collect publication-readiness evidence for a Git repository without changing it.

Scans tracked files for secret signatures, sensitive filenames, large or
generated artifacts, and files tracked despite ignore rules; checks licence,
security policy, README, contribution, and release documents; and, with
--history, scans added lines across all history for secret signatures, lists
sensitive files ever added or deleted, and counts author email addresses without
listing them. Reports locations only: never a secret value, partial value, or
fingerprint. Runs read-only Git commands only. Emits JSON gates with statuses
verified, failed, not checked, blocked, or not applicable. Exit codes: 0 no
failed gate; 1 at least one failed gate; 2 usage error or scan limits reached.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "references", _HERE.parents[2] / "references"):
    if (_candidate / "cw_scan.py").is_file():
        sys.path.insert(0, str(_candidate))
        break
import cw_scan  # noqa: E402


TOOL = "public-release-audit/release_scan"
SENSITIVE_NAME = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:\.(?!example$|sample$|template$)[^/]+)?|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?|[^/]+\.(?:pem|key|p12|pfx|jks|keystore|kdbx|tfstate(?:\.backup)?)"
    r"|credentials[^/]*\.json|service-account[^/]*\.json|client_secret[^/]*\.json|\.netrc|\.pypirc|\.htpasswd)$"
)
DEBRIS = re.compile(r"(?i)(?:^|/)(?:node_modules|__pycache__|\.pytest_cache|\.ds_store|thumbs\.db)(?:/|$)|\.pyc$|\.class$")
GENERATED_HINT = re.compile(r"(?i)\.min\.(?:js|css)$|\.map$")
LICENCE_NAMES = re.compile(r"(?i)^(?:licen[cs]e|copying)(?:\.[a-z]+)?$")
LICENCE_IDS = (
    ("MIT", re.compile(r"\bMIT License\b|Permission is hereby granted, free of charge")),
    ("Apache-2.0", re.compile(r"Apache License,?\s+Version 2\.0")),
    ("GPL-3.0", re.compile(r"GNU GENERAL PUBLIC LICENSE\s+Version 3")),
    ("GPL-2.0", re.compile(r"GNU GENERAL PUBLIC LICENSE\s+Version 2")),
    ("LGPL", re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE")),
    ("MPL-2.0", re.compile(r"Mozilla Public License,?\s+(?:version|v\.?)\s*2\.0", re.IGNORECASE)),
    ("BSD", re.compile(r"Redistribution and use in source and binary forms")),
    ("ISC", re.compile(r"\bISC License\b")),
    ("Unlicense", re.compile(r"This is free and unencumbered software released into the public domain")),
)


class GitError(RuntimeError):
    pass


def git_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    return env


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=repo, env=git_env(), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=300, check=False)
    if completed.returncode != 0:
        raise GitError(f"git {args[0]} failed: {completed.stderr.strip()[:200]}")
    return completed.stdout


def gate(name: str, status: str, evidence: object, action: str | None = None) -> dict[str, object]:
    assert status in {"verified", "failed", "not checked", "blocked", "not applicable"}
    record: dict[str, object] = {"gate": name, "status": status, "evidence": evidence}
    if action:
        record["owner_action"] = action
    return record


def secret_status(locations: list[dict[str, object]], incomplete: bool) -> str:
    """Format-specific signatures fail the gate; generic pattern hits need a human look."""

    if any(item["rule"] not in cw_scan.HEURISTIC_SECRET_RULES for item in locations):
        return "failed"
    if locations or incomplete:
        return "not checked"
    return "verified"


def find_file(repo: Path, tracked: set[str], names: tuple[str, ...]) -> str | None:
    for directory in ("", ".github/", "docs/"):
        for name in names:
            for candidate in tracked:
                if candidate.casefold() == f"{directory}{name}".casefold():
                    return candidate
    return None


def licence_of(text: str) -> str | None:
    return next((identifier for identifier, pattern in LICENCE_IDS if pattern.search(text)), None)


def declared_licences(repo: Path, tracked: set[str]) -> dict[str, str]:
    declared: dict[str, str] = {}
    if "package.json" in tracked:
        try:
            data = json.loads((repo / "package.json").read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("license"), str):
                declared["package.json"] = data["license"]
        except (OSError, json.JSONDecodeError):
            pass
    for name, table in (("pyproject.toml", "project"), ("Cargo.toml", "package")):
        if name in tracked:
            try:
                data = tomllib.loads((repo / name).read_text(encoding="utf-8")).get(table, {})
            except (OSError, tomllib.TOMLDecodeError):
                continue
            value = data.get("license")
            if isinstance(value, dict):
                value = value.get("text") or value.get("file")
            if isinstance(value, str):
                declared[name] = value
    return declared


def scan_history(repo: Path, max_commits: int, max_bytes: int) -> dict[str, object]:
    hits: list[dict[str, object]] = []
    limits: list[str] = []
    process = subprocess.Popen(
        ["git", "-c", "core.quotepath=off", "log", "--all", "-p", "--no-color", "--no-ext-diff", "--format=commit %H",
         f"--max-count={max_commits}"],
        cwd=repo, env=git_env(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    commit = path = None
    consumed = 0
    commits = 0
    seen: set[tuple[str, str, str]] = set()
    assert process.stdout is not None
    try:
        for raw in process.stdout:
            consumed += len(raw)
            if consumed > max_bytes:
                limits.append(f"history scan stopped after {max_bytes} bytes")
                break
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if line.startswith("commit "):
                commit = line[7:19]
                commits += 1
            elif line.startswith("+++ "):
                path = line[6:].rstrip("\t") if line.startswith("+++ b/") else None
            elif line.startswith("+") and commit and path:
                for rule, _ in cw_scan.secret_hits(line[1:]):
                    key = (commit, path, rule)
                    if key not in seen:
                        seen.add(key)
                        hits.append({"commit": commit, "path": path, "rule": rule})
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
        process.wait()
    if commits >= max_commits:
        limits.append(f"history scan limited to {max_commits} commits")
    added = git(repo, "log", "--all", "--diff-filter=A", "--name-only", "--format=")
    deleted = git(repo, "log", "--all", "--diff-filter=D", "--name-only", "--format=")
    emails = {line.strip().casefold() for line in git(repo, "log", "--all", "--format=%ae%n%ce").splitlines() if line.strip()}
    return {
        "secret_locations": hits,
        "sensitive_files_ever_added": sorted({name for name in added.splitlines() if name and SENSITIVE_NAME.search(name)}),
        "sensitive_files_deleted": sorted({name for name in deleted.splitlines() if name and SENSITIVE_NAME.search(name)}),
        "author_emails": {"distinct": len(emails), "not_noreply": sum(1 for email in emails if "noreply" not in email)},
        "commits_scanned": commits,
        "limits": limits,
    }


def main(argv: list[str] | None = None) -> int:
    cw_scan.require_python()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--history", action="store_true", help="also scan all history (slower)")
    parser.add_argument("--max-commits", type=int, default=5000)
    parser.add_argument("--max-history-bytes", type=int, default=200_000_000)
    parser.add_argument("--large-file-bytes", type=int, default=5_000_000)
    parser.add_argument("--max-file-bytes", type=int, default=1_048_576)
    parser.add_argument("--output", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    try:
        top = Path(git(repo, "rev-parse", "--show-toplevel").strip())
        tracked_list = [item for item in git(top, "ls-files", "-z").split("\0") if item]
        ignored_tracked = [item for item in git(top, "ls-files", "-z", "-ci", "--exclude-standard").split("\0") if item]
    except (GitError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    tracked = set(tracked_list)
    secret_locations: list[dict[str, object]] = []
    large: list[dict[str, object]] = []
    binaries: list[str] = []
    unread: list[str] = []
    for relative in sorted(tracked):
        path = top / relative
        if path.is_symlink() or not path.is_file():
            continue
        size = path.stat().st_size
        if size > args.large_file_bytes:
            large.append({"path": relative, "bytes": size})
        try:
            data, truncated = cw_scan.read_bounded(path, args.max_file_bytes)
        except OSError:
            unread.append(relative)
            continue
        if cw_scan.binary_kind(data) is not None:
            binaries.append(relative)
            continue
        if truncated:
            unread.append(relative)
        for rule, line in cw_scan.secret_hits(data.decode("utf-8", errors="replace")):
            secret_locations.append({"path": relative, "line": line, "rule": rule})
    sensitive = sorted(name for name in tracked if SENSITIVE_NAME.search(name))
    debris = sorted(name for name in tracked if DEBRIS.search(name))
    generated = sorted(name for name in tracked if GENERATED_HINT.search(name))
    gates: list[dict[str, object]] = []
    gates.append(gate("secrets in tracked files", secret_status(secret_locations, bool(unread)),
                      {"locations": secret_locations, "unread_files": unread[:50]},
                      "remove the secret, rotate it, and treat it as exposed" if secret_locations else None))
    history: dict[str, object] | None = None
    if args.history:
        try:
            history = scan_history(top, args.max_commits, args.max_history_bytes)
        except (GitError, OSError, subprocess.SubprocessError) as exc:
            gates.append(gate("secrets in history", "blocked", f"history scan failed: {exc}"))
        else:
            status = secret_status(history["secret_locations"], bool(history["limits"]))
            gates.append(gate("secrets in history", status,
                              {"locations": history["secret_locations"], "limits": history["limits"],
                               "commits_scanned": history["commits_scanned"]},
                              "rotate every exposed secret; rewriting history is a separate, owner-authorized decision"
                              if history["secret_locations"] else None))
    else:
        gates.append(gate("secrets in history", "not checked", "history scan not requested (--history)"))
    ever = history["sensitive_files_ever_added"] if history else []
    gates.append(gate("sensitive files", "failed" if sensitive or ever else "verified" if history else "not checked",
                      {"tracked": sensitive, "ever_added": ever,
                       "deleted": history["sensitive_files_deleted"] if history else "history not scanned"}))
    gates.append(gate("files tracked despite ignore rules", "failed" if ignored_tracked else "verified",
                      {"paths": sorted(ignored_tracked)[:100]}))
    licence_file = next((name for name in sorted(tracked) if "/" not in name and LICENCE_NAMES.match(name)), None)
    if licence_file is None:
        gates.append(gate("licence", "failed", "no LICENSE or COPYING file at the repository root",
                          "choose and add a licence; without one, others have no permission to reuse the code"))
    else:
        detected = licence_of((top / licence_file).read_text(encoding="utf-8", errors="replace"))
        declared = declared_licences(top, tracked)
        mismatched = {name: value for name, value in declared.items() if detected and detected.casefold() not in value.casefold()}
        status = "failed" if mismatched else "verified" if detected else "not checked"
        gates.append(gate("licence", status, {"file": licence_file, "detected": detected, "declared": declared,
                                               "mismatched": mismatched}))
    vendored = sorted({name.split("/")[0] + "/" for name in tracked if re.match(r"(?i)(?:vendor|third[_-]?party|external)/", name)})
    gates.append(gate("third-party and vendored material", "not checked",
                      {"vendored_directories": vendored}, "review attribution and redistribution terms for bundled material"))
    gates.append(gate("dependency provenance", "not checked", "hand to dependency-risk and cite its coverage"))
    gates.append(gate("generated, large, and debris artifacts", "failed" if debris or large else "verified",
                      {"debris": debris[:100], "large": large, "generated_hints": generated[:100], "binaries": binaries[:100]}))
    if history:
        emails = history["author_emails"]
        gates.append(gate("personal data in history", "verified" if emails["not_noreply"] == 0 else "not checked",
                          {"author_emails": emails, "note": "addresses are counted, not listed"},
                          "decide whether the listed author identities may be public" if emails["not_noreply"] else None))
    else:
        gates.append(gate("personal data in history", "not checked", "history scan not requested (--history)"))
    readme = next((name for name in sorted(tracked) if "/" not in name and name.casefold().startswith("readme")), None)
    gates.append(gate("readme", "verified" if readme else "failed", {"file": readme}))
    gates.append(gate("outsider reproduction", "not checked",
                      "follow the README from a clean clone; hand execution to patch-proof in single_revision mode"))
    workflows = sorted(name for name in tracked if name.startswith(".github/workflows/"))
    gates.append(gate("CI exposure when public", "not checked" if workflows else "not applicable",
                      {"workflows": workflows, "note": "hand to ci-trust-review" if workflows else "no workflows"}))
    security = find_file(top, tracked, ("SECURITY.md",))
    gates.append(gate("security policy", "verified" if security else "failed", {"file": security},
                      None if security else "add a SECURITY.md with a private reporting route"))
    contributing = find_file(top, tracked, ("CONTRIBUTING.md",))
    gates.append(gate("contribution and support surfaces", "verified" if contributing else "not checked",
                      {"contributing": contributing, "code_of_conduct": find_file(top, tracked, ("CODE_OF_CONDUCT.md",)),
                       "support": find_file(top, tracked, ("SUPPORT.md",))},
                      None if contributing else "decide whether contribution guidance is needed"))
    release_docs = [name for name in sorted(tracked) if re.search(r"(?i)(?:^|/)(?:changelog|releasing|release)(?:\.[a-z]+)?$", name)]
    gates.append(gate("release and versioning procedure", "verified" if release_docs else "not checked",
                      {"documents": release_docs}))
    gates.append(gate("platform settings", "blocked",
                      "visibility, secret scanning, branch protection, and private vulnerability reporting are not in "
                      "repository files; inspect them with host tools"))
    limits = history["limits"] if history else []
    report = cw_scan.envelope(
        TOOL,
        {"repository": top.name, "history": args.history},
        gates=gates,
        summary={status: sum(1 for item in gates if item["status"] == status)
                 for status in ("verified", "failed", "not checked", "blocked", "not applicable")},
        tracked_files=len(tracked),
        executed=False,
        changed_nothing=True,
    )
    cw_scan.emit(report, args.output)
    if any(item["status"] == "failed" for item in gates):
        return 1
    return 2 if limits else 0


if __name__ == "__main__":
    raise SystemExit(main())
