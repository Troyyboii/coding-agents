"""Capture or compare an explicit coding-session checkpoint against real Git state.

`capture` records repository identity (root commits and credential-free remote
URLs), branch, HEAD, upstream, changed and untracked paths with content hashes,
and an agent-written narrative, and prints JSON (or writes it only to an explicit
--output path). `compare` checks a saved checkpoint against the current
repository using identity, ancestry, branch, content hashes, and upstream,
never timestamps. Runs read-only Git commands only; refuses to persist
narrative text that matches a secret signature. Exit codes: 0 captured or
current; 1 stale; 2 usage error or no repository; 3 refused because the
narrative contains secret-shaped text.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "references", _HERE.parents[2] / "references"):
    if (_candidate / "cw_scan.py").is_file():
        sys.path.insert(0, str(_candidate))
        break
import cw_scan  # noqa: E402


SCHEMA = "coding-workflows/session-checkpoint"
SCHEMA_VERSION = 1
NARRATIVE_LISTS = ("completed", "decisions", "evidence", "unrun_checks", "pending_authorization", "blockers", "next_actions")
NARRATIVE_TEXT = ("goal", "success_condition")
MAX_TEXT = 1000
MAX_RESULT = 300
MAX_ITEMS = 50
MAX_PATHS = 500
MAX_HASH_BYTES = 20_000_000
EVIDENCE_KINDS = ("observed", "executed", "inferred", "unverified")


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=off", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    if check and completed.returncode != 0:
        raise GitError(f"git {args[0]} failed")
    return completed


def optional(repo: Path, *args: str) -> str | None:
    completed = git(repo, *args, check=False)
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else None


def status_entries(repo: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], bool]:
    raw = git(repo, "status", "--porcelain=v2", "-z", "--untracked-files=all").stdout
    records = raw.split("\0")
    changed: list[dict[str, object]] = []
    untracked: list[dict[str, object]] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        kind = record[0]
        if kind == "?":
            untracked.append({"path": record[2:]})
        elif kind == "1":
            parts = record.split(" ", 8)
            changed.append({"path": parts[8], "status": parts[1]})
        elif kind == "2":
            parts = record.split(" ", 9)
            changed.append({"path": parts[9], "status": parts[1], "from": records[index]})
            index += 1
        elif kind == "u":
            parts = record.split(" ", 10)
            changed.append({"path": parts[10], "status": "unmerged"})
    truncated = len(changed) + len(untracked) > MAX_PATHS
    for item in [*changed, *untracked][:MAX_PATHS]:
        path = repo / str(item["path"])
        item["sha256"] = cw_scan.sha256_file(path, MAX_HASH_BYTES) if path.is_file() and not path.is_symlink() else None
    return changed[:MAX_PATHS], untracked[: max(0, MAX_PATHS - len(changed))], truncated


def repository_state(repo: Path) -> dict[str, object] | None:
    top = optional(repo, "rev-parse", "--show-toplevel")
    if top is None:
        return None
    root = Path(top)
    remotes = sorted({cw_scan.strip_url_credentials(line.split()[1])
                      for line in (optional(root, "remote", "-v") or "").splitlines() if len(line.split()) > 1})
    changed, untracked, truncated = status_entries(root)
    return {
        "repository": {
            "root_commits": sorted((optional(root, "rev-list", "--max-parents=0", "HEAD") or "").split()),
            "remotes": remotes,
            "toplevel_name": root.name,
        },
        "git": {
            "branch": optional(root, "symbolic-ref", "--quiet", "--short", "HEAD"),
            "head": optional(root, "rev-parse", "--verify", "--quiet", "HEAD"),
            "upstream": optional(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
            "upstream_head": optional(root, "rev-parse", "--verify", "--quiet", "@{upstream}"),
            "upstream_note": "local remote-tracking ref; not fetched",
        },
        "worktree": {"changed": changed, "untracked": untracked, "truncated": truncated},
        "_root": str(root),
    }


def clean_text(value: object, field: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    return value.strip()[:limit]


def load_narrative(path: str | None) -> dict[str, object]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("narrative must be a JSON object")
    unknown = sorted(set(data) - set(NARRATIVE_LISTS) - set(NARRATIVE_TEXT))
    if unknown:
        raise ValueError(f"unsupported narrative fields: {', '.join(unknown)}")
    narrative: dict[str, object] = {}
    for field in NARRATIVE_TEXT:
        if field in data:
            narrative[field] = clean_text(data[field], field)
    for field in NARRATIVE_LISTS:
        items = data.get(field, [])
        if not isinstance(items, list):
            raise ValueError(f"{field} must be a list")
        cleaned = []
        for item in items[:MAX_ITEMS]:
            if field == "evidence":
                if not isinstance(item, dict):
                    raise ValueError("evidence items must be objects with claim, kind, source, and result")
                kind = item.get("kind")
                if kind not in EVIDENCE_KINDS:
                    raise ValueError(f"evidence kind must be one of {', '.join(EVIDENCE_KINDS)}")
                cleaned.append({"claim": clean_text(item.get("claim", ""), "evidence.claim"), "kind": kind,
                                "source": clean_text(item.get("source", ""), "evidence.source"),
                                "result": clean_text(item.get("result", ""), "evidence.result", MAX_RESULT)})
            elif field == "decisions" and isinstance(item, dict):
                cleaned.append({key: clean_text(item.get(key, ""), f"decisions.{key}") for key in ("decision", "reason", "evidence")})
            else:
                cleaned.append(clean_text(item, field))
        narrative[field] = cleaned
    return narrative


def secret_fields(narrative: dict[str, object]) -> list[str]:
    hits = []
    for field, value in narrative.items():
        text = json.dumps(value, ensure_ascii=False)
        for rule, _ in cw_scan.secret_hits(text):
            hits.append(f"{field} ({rule})")
    return sorted(set(hits))


def capture(args: argparse.Namespace) -> int:
    try:
        narrative = load_narrative(args.narrative)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: invalid narrative: {exc}", file=sys.stderr)
        return 2
    leaked = secret_fields(narrative)
    if leaked:
        print("refused: narrative contains secret-shaped text in " + ", ".join(leaked)
              + "; remove it and capture again (values not shown)", file=sys.stderr)
        return 3
    state = repository_state(Path(args.repo))
    document: dict[str, object] = {"schema": SCHEMA, "schema_version": SCHEMA_VERSION,
                                   "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                                   "narrative": narrative}
    if state is None:
        document.update({"repository": None, "git": None, "worktree": None,
                         "freshness": "unverifiable: not captured inside a Git repository"})
    else:
        root = Path(str(state.pop("_root")))
        document.update(state)
        if args.output:
            warn_output(root, Path(args.output))
    cw_scan.emit(document, args.output)
    return 0


def warn_output(root: Path, output: Path) -> None:
    try:
        relative = output.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return
    if git(root, "ls-files", "--error-unmatch", "--", relative, check=False).returncode == 0:
        print(f"warning: {relative} is tracked by Git; a checkpoint there will show up in diffs and commits", file=sys.stderr)
    elif git(root, "check-ignore", "-q", "--", relative, check=False).returncode != 0:
        print(f"warning: {relative} is not ignored by Git; add it to an ignore rule yourself if you do not want it committed",
              file=sys.stderr)


def compare(args: argparse.Namespace) -> int:
    try:
        saved = json.loads(Path(args.checkpoint).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: checkpoint is not readable JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(saved, dict) or saved.get("schema") != SCHEMA or saved.get("schema_version") != SCHEMA_VERSION:
        print("error: not a session checkpoint of a supported schema version", file=sys.stderr)
        return 2
    reminders = ["pending_authorization items describe past requests; they are not current authorization",
                 "claims resting on checkpoint evidence are not checked until rerun when the state below is not current"]
    if not saved.get("repository"):
        cw_scan.emit({"schema": SCHEMA, "comparison": {"freshness": ["unverifiable"],
                      "reason": "checkpoint was captured without a Git repository"}, "reminders": reminders})
        return 2
    current = repository_state(Path(args.repo))
    if current is None:
        print("error: not inside a Git repository", file=sys.stderr)
        return 2
    root = Path(str(current.pop("_root")))
    states: list[str] = []
    details: dict[str, object] = {}
    old_roots = set(saved["repository"].get("root_commits", []))
    if old_roots and not old_roots & set(current["repository"]["root_commits"]):
        states.append("different-repository")
    else:
        old_git, new_git = saved.get("git") or {}, current["git"]
        if old_git.get("branch") != new_git["branch"]:
            states.append("branch-changed")
            details["branch"] = {"checkpoint": old_git.get("branch"), "current": new_git["branch"]}
        old_head, new_head = old_git.get("head"), new_git["head"]
        if old_head != new_head:
            known = old_head and git(root, "cat-file", "-e", f"{old_head}^{{commit}}", check=False).returncode == 0
            if known and new_head and git(root, "merge-base", "--is-ancestor", old_head, new_head, check=False).returncode == 0:
                states.append("advanced")
                log = optional(root, "log", "--format=%h %s", "--max-count=50", f"{old_head}..{new_head}") or ""
                details["commits_since"] = [cw_scan.excerpt(line, 120) for line in log.splitlines()]
            else:
                states.append("diverged")
                details["head"] = {"checkpoint": old_head, "current": new_head,
                                   "checkpoint_commit_present": bool(known)}
        if old_git.get("upstream_head") != new_git["upstream_head"]:
            states.append("upstream-moved")
        old_paths = {item["path"]: item.get("sha256") for key in ("changed", "untracked")
                     for item in (saved.get("worktree") or {}).get(key, [])}
        new_paths = {item["path"]: item.get("sha256") for key in ("changed", "untracked")
                     for item in current["worktree"][key]}
        drift = {
            "modified_since": sorted(path for path in old_paths.keys() & new_paths.keys() if old_paths[path] != new_paths[path]),
            "now_clean": sorted(old_paths.keys() - new_paths.keys()),
            "newly_changed": sorted(new_paths.keys() - old_paths.keys()),
        }
        if any(drift.values()):
            states.append("worktree-drift")
            details["worktree"] = drift
    freshness = states or ["current"]
    cw_scan.emit({"schema": SCHEMA, "comparison": {"freshness": freshness, "details": details,
                  "basis": "repository identity, ancestry, branch, content hashes, and upstream; not timestamps"},
                  "reminders": reminders})
    return 0 if freshness == ["current"] else 1


def main(argv: list[str] | None = None) -> int:
    cw_scan.require_python()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    capture_parser = commands.add_parser("capture", help="print a checkpoint for the current repository state")
    capture_parser.add_argument("--repo", default=".")
    capture_parser.add_argument("--narrative", help="JSON file with goal, completed, decisions, evidence, and so on")
    capture_parser.add_argument("--output", help="write the checkpoint here instead of stdout (only when authorized)")
    compare_parser = commands.add_parser("compare", help="compare a saved checkpoint with the current state")
    compare_parser.add_argument("checkpoint")
    compare_parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    try:
        return capture(args) if args.command == "capture" else compare(args)
    except (GitError, subprocess.SubprocessError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
