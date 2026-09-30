"""Check the complete Git diff range selected for a validation event."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


GIT_REVISION = re.compile(r"^[0-9a-f]{40,64}$")
ZERO_REVISION = "0" * 40

#: `git diff --check` exit codes: 0 is clean, 2 reports whitespace findings.
#: Metadata/usage failures use a distinct code so tests and CI cannot confuse
#: an unusable event with a whitespace verdict.
METADATA_EXIT_CODE = 3
WHITESPACE_EXIT_CODE = 2


class DiffCheckError(RuntimeError):
    pass


def _run_git(repository: Path, arguments: list[str], *, input_bytes: bytes | None = None) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            input=input_bytes,
            capture_output=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DiffCheckError("git_diff_check_failed") from exc
    return completed.stdout.decode("ascii", errors="strict").strip()


def _empty_tree(repository: Path) -> str:
    return _run_git(repository, ["hash-object", "-t", "tree", "--stdin"], input_bytes=b"")


def _object_exists(repository: Path, revision: str) -> bool:
    try:
        _run_git(repository, ["cat-file", "-e", revision])
    except DiffCheckError:
        return False
    return True


def select_diff_base(
    repository: Path,
    *,
    event_name: str,
    event_before: str,
    pull_request_base: str,
    head_revision: str,
) -> str:
    if GIT_REVISION.fullmatch(head_revision) is None:
        raise DiffCheckError("invalid_head_revision")
    if event_name == "pull_request":
        if GIT_REVISION.fullmatch(pull_request_base) is None:
            raise DiffCheckError("missing_pull_request_base")
        base = pull_request_base
        base_must_be_commit = True
    elif event_name == "push":
        if not event_before or event_before == ZERO_REVISION:
            # Initial pushes (all-zero or absent `before`) compare the full tree.
            base = _empty_tree(repository)
            base_must_be_commit = False
        elif GIT_REVISION.fullmatch(event_before):
            base = event_before
            base_must_be_commit = True
        else:
            raise DiffCheckError("invalid_push_base")
    elif event_name == "workflow_dispatch":
        base = _empty_tree(repository)
        base_must_be_commit = False
    else:
        raise DiffCheckError("unsupported_event")
    if not _object_exists(repository, f"{head_revision}^{{commit}}"):
        raise DiffCheckError("missing_diff_revision")
    if base_must_be_commit:
        # A force-push (or a pruned history) can leave the recorded base
        # unreachable; report that explicitly instead of diffing garbage.
        if not _object_exists(repository, f"{base}^{{commit}}"):
            raise DiffCheckError("unreachable_diff_base")
    elif not _object_exists(repository, base):
        raise DiffCheckError("missing_empty_tree")
    return base


def main() -> int:
    repository = Path.cwd()
    try:
        head_revision = os.environ["HEAD_SHA"]
        base = select_diff_base(
            repository,
            event_name=os.environ.get("EVENT_NAME", ""),
            event_before=os.environ.get("EVENT_BEFORE", ""),
            pull_request_base=os.environ.get("PULL_REQUEST_BASE", ""),
            head_revision=head_revision,
        )
        completed = subprocess.run(
            ["git", "diff", "--check", base, head_revision],
            cwd=repository,
            check=False,
        )
    except (DiffCheckError, KeyError, UnicodeError):
        print("ERROR: invalid or incomplete diff-check event metadata", file=sys.stderr)
        return METADATA_EXIT_CODE
    if completed.returncode == 0:
        return 0
    if completed.returncode == WHITESPACE_EXIT_CODE:
        return WHITESPACE_EXIT_CODE
    print(
        f"ERROR: git diff failed for base {base} and head {head_revision}",
        file=sys.stderr,
    )
    return METADATA_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
