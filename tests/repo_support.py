"""Shared loaders and fixture helpers for repository test modules."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SKILLS = ROOT / "plugins" / "coding-workflows" / "skills"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# Never write bytecode next to the sources under test. Running skill helpers
# that live inside generated package trees would otherwise drop
# __pycache__/*.pyc into those outputs and contaminate package-currentness
# validation (forbidden debris / stale output).
sys.dont_write_bytecode = True


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module("coding_agents_validate_repository_support", SCRIPTS / "validate-repository.py")


def load_helper(skill: str, helper: str):
    """Import a skill helper from the canonical whole-plugin layout."""

    return load_module(f"skill_helper_{skill.replace('-', '_')}_{Path(helper).stem}", SKILLS / skill / "scripts" / helper)


def make_repo_fixture(testcase: unittest.TestCase, *, with_dist: bool = True) -> Path:
    """Copy the repository into a temporary directory that is removed after the test.

    Tests whose subject is unrelated to generated-package outputs may pass
    ``with_dist=False`` to skip the ``*/dist`` trees (314 files). Structural
    package checks then report missing outputs, but non-package assertions
    using ``any(expected in error)`` still prove their mutation is detected
    while the fixture copies and validates ~3x faster.
    """

    temporary = tempfile.TemporaryDirectory()
    testcase.addCleanup(temporary.cleanup)
    fixture = Path(temporary.name) / "repo"
    ignored = [".git", ".artifacts", "__pycache__", "*.pyc", ".codex-home"]
    if not with_dist:
        ignored.append("dist")
    shutil.copytree(ROOT, fixture, ignore=shutil.ignore_patterns(*ignored))
    return fixture


def temp_dir(testcase: unittest.TestCase) -> Path:
    temporary = tempfile.TemporaryDirectory()
    testcase.addCleanup(temporary.cleanup)
    return Path(temporary.name)


def symlink_or_skip(testcase: unittest.TestCase, link: Path, target: Path, *, target_is_directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        testcase.skipTest(f"symlink creation is unavailable or denied: {exc}")


def isolated_git_env(home: Path) -> dict[str, str]:
    """Environment for test Git repositories that ignores user and system configuration."""

    config = home / "gitconfig"
    if not config.exists():
        config.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(config),
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def git(repo: Path, *args: str, env: dict[str, str]) -> str:
    completed = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def make_git_repo(testcase: unittest.TestCase, files: dict[str, str] | None = None) -> tuple[Path, dict[str, str]]:
    """Create a temporary Git repository with one commit and isolated configuration."""

    base = temp_dir(testcase)
    env = isolated_git_env(base)
    repo = base / "repo"
    repo.mkdir()
    git(repo, "init", "-q", env=env)
    # Set the unborn branch directly; older Git versions ignore init.defaultBranch.
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main", env=env)
    for relative, content in (files or {"README.md": "fixture\n"}).items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", "-A", env=env)
    git(repo, "commit", "-q", "-m", "initial", env=env)
    return repo, env


def run_python(script: Path, *args: str, cwd: Path | None = None, env: dict[str, str] | None = None,
               timeout: int = 120) -> subprocess.CompletedProcess[str]:
    run_env = dict(env) if env is not None else dict(os.environ)
    # Keep helper execution from writing __pycache__/.pyc into generated
    # package trees (see sys.dont_write_bytecode above).
    run_env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(script), *args],
        cwd=cwd,
        env=run_env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def fast_validate(fixture: Path, tracked_files: list[str] | None = None):
    """Run the repository validator without generated-package rebuilds.

    TEST-ONLY fast path for tests whose subject is unrelated to package
    currency. Structural package checks still run; only the rebuild
    comparisons are skipped. Package integration tests must use
    VALIDATOR.validate() with the default enabled checks.
    """

    return VALIDATOR.validate(
        fixture,
        tracked_files=[] if tracked_files is None else tracked_files,
        check_generated_packages=False,
    )


def fast_inventory(fixture: Path):
    """Collect inventory without generated-package rebuilds (TEST-ONLY)."""

    from repository_inventory import collect_inventory

    return collect_inventory(fixture, check_generated_packages=False)
