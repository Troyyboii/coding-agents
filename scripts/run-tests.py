"""Run the repository unit tests in parallel worker processes."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
# Windows caps a command line at 32,767 characters; keep each worker well below it.
MAX_COMMAND_CHARS = 24_000
RAN = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
SKIPPED = re.compile(r"skipped=(\d+)")


def discover_test_ids() -> list[str]:
    """Return every test id the standard `unittest discover -s tests` run would execute."""

    sys.path.insert(0, str(TESTS))
    suite = unittest.TestLoader().discover(str(TESTS), top_level_dir=str(TESTS))
    ids: list[str] = []
    pending: list[unittest.TestSuite | unittest.TestCase] = [suite]
    while pending:
        item = pending.pop()
        if isinstance(item, unittest.TestSuite):
            pending.extend(item)
        else:
            ids.append(item.id())
    broken = sorted(test_id for test_id in ids if test_id.startswith("unittest.loader."))
    if broken:
        raise SystemExit(
            "Test modules failed to import: "
            + ", ".join(test_id.rsplit(".", 1)[-1] for test_id in broken)
            + "\nRun `python -m unittest discover -s tests` to see the import errors."
        )
    return sorted(ids)


def split_ids(ids: list[str], jobs: int) -> list[list[str]]:
    """Deal sorted ids round-robin so slow neighbours in one class land on different workers."""

    chunks: list[list[str]] = [[] for _ in range(max(1, min(jobs, len(ids))))]
    for index, test_id in enumerate(ids):
        chunks[index % len(chunks)].append(test_id)
    bounded: list[list[str]] = []
    for chunk in chunks:
        current: list[str] = []
        length = 0
        for test_id in chunk:
            if current and length + len(test_id) + 1 > MAX_COMMAND_CHARS:
                bounded.append(current)
                current, length = [], 0
            current.append(test_id)
            length += len(test_id) + 1
        if current:
            bounded.append(current)
    return bounded


def run_chunk(test_ids: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(TESTS), env.get("PYTHONPATH")]))
    # Match tests/repo_support.py: never write bytecode into package trees under test.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", "-m", "unittest", *test_ids],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", "-j", type=int, default=os.cpu_count() or 2, help="worker processes (default: CPU count)")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")

    started = time.perf_counter()
    ids = discover_test_ids()
    chunks = split_ids(ids, args.jobs)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run_chunk, chunks))

    ran = skipped = 0
    failed_workers = 0
    for chunk, result in zip(chunks, results, strict=True):
        output = result.stderr + result.stdout
        match = RAN.search(output)
        ran += int(match.group(1)) if match else 0
        skipped += sum(int(value) for value in SKIPPED.findall(output.splitlines()[-1] if output.strip() else ""))
        if result.returncode != 0 or match is None:
            failed_workers += 1
            print(f"--- worker with {len(chunk)} tests failed (exit {result.returncode}) ---", file=sys.stderr)
            print(output.rstrip(), file=sys.stderr)

    elapsed = time.perf_counter() - started
    summary = f"Ran {ran} of {len(ids)} tests in {elapsed:.1f}s across {len(chunks)} workers"
    if skipped:
        summary += f" ({skipped} skipped)"
    if failed_workers or ran != len(ids):
        print(f"{summary}: FAILED", file=sys.stderr)
        return 1
    print(f"{summary}: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
