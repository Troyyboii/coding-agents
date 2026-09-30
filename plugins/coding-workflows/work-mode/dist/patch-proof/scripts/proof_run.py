"""Validate and, only with --execute, run an approved proof plan in isolated temporary clones.

Two plan modes. `differential` runs the same cases against a pinned base revision
and a pinned patched revision (another commit, or the base plus a hashed diff)
to show the original failure reproduces before and not after, a root-cause
variant is also fixed, and legitimate behavior still works. `single_revision`
runs cases against one pinned revision, for example an outsider reproduction;
it is never a patch proof. Without --execute the plan is validated, revisions
are resolved, and the exact commands are printed; nothing runs. With --execute,
workspaces are cloned outside the repository with user and system Git
configuration ignored, each command runs from its argv without a shell under a
timeout in its own process group, output is capped and redacted, and workspaces
are removed afterwards. The source repository is only read. Exit codes: 0 plan
valid (dry run) or claim verified; 1 claim failed; 2 usage error, invalid plan,
or blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "references", _HERE.parents[2] / "references"):
    if (_candidate / "cw_scan.py").is_file():
        sys.path.insert(0, str(_candidate))
        break
import cw_scan  # noqa: E402


PLAN_SCHEMA = "coding-workflows/proof-plan"
EVIDENCE_SCHEMA = "coding-workflows/proof-evidence"
MODES = ("differential", "single_revision")
ROLES = {
    "differential": ("original_reproduction", "root_cause_variant", "legitimate_behavior"),
    "single_revision": ("reproduction",),
}
SHELL_WRAPPERS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh",
                  "pwsh.exe"}
SHELL_FLAGS = {"-c", "/c", "/k", "-command", "-encodedcommand", "-e", "-ec"}
DEFAULT_PASS_ENV = ("PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "TEMP",
                    "TMP", "TMPDIR", "LANG", "LC_ALL")
MAX_TIMEOUT = 3600
IS_WINDOWS = os.name == "nt"


class PlanError(ValueError):
    pass


# -- plan validation --------------------------------------------------------

def _argv(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise PlanError(f"{label} must be a non-empty list of non-empty strings (no shell command strings)")
    program = Path(value[0]).name.casefold()
    if program in SHELL_WRAPPERS and any(item.casefold() in SHELL_FLAGS for item in value[1:]):
        raise PlanError(f"{label} wraps a command in a shell; list the program and its arguments directly")
    return value


def _timeout(value: object, label: str, default: int) -> int:
    value = default if value is None else value
    if not isinstance(value, int) or not 0 < value <= MAX_TIMEOUT:
        raise PlanError(f"{label} must be an integer between 1 and {MAX_TIMEOUT} seconds")
    return value


def _expectation(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not value:
        raise PlanError(f"{label} must state the expected exit and/or output markers")
    unknown = set(value) - {"exit", "stdout_contains", "stdout_excludes"}
    if unknown:
        raise PlanError(f"{label} has unsupported fields: {sorted(unknown)}")
    exit_value = value.get("exit")
    if exit_value is not None and not (isinstance(exit_value, int) or exit_value in {"zero", "nonzero"}):
        raise PlanError(f"{label}.exit must be an integer, \"zero\", or \"nonzero\"")
    for key in ("stdout_contains", "stdout_excludes"):
        markers = value.get(key, [])
        if not isinstance(markers, list) or not all(isinstance(item, str) and item for item in markers):
            raise PlanError(f"{label}.{key} must be a list of non-empty strings")
    return value


def validate_plan(plan: object) -> dict[str, object]:
    if not isinstance(plan, dict):
        raise PlanError("plan must be a JSON object")
    if plan.get("schema") != PLAN_SCHEMA or plan.get("schema_version") != 1:
        raise PlanError(f"plan schema must be {PLAN_SCHEMA} version 1")
    mode = plan.get("mode")
    if mode not in MODES:
        raise PlanError(f"mode must be one of {', '.join(MODES)}")
    if plan.get("network") != "not-controlled":
        raise PlanError("plan must set \"network\": \"not-controlled\" to acknowledge that commands may use the network")
    base = plan.get("base")
    if not isinstance(base, dict) or not isinstance(base.get("rev"), str) or not base["rev"]:
        raise PlanError("base.rev is required")
    patched = plan.get("patched")
    if mode == "differential":
        if not isinstance(patched, dict) or not (
            isinstance(patched.get("rev"), str) or (isinstance(patched.get("diff"), str) and isinstance(patched.get("diff_sha256"), str))
        ):
            raise PlanError("differential mode needs patched.rev, or patched.diff with patched.diff_sha256")
    elif patched is not None:
        raise PlanError("single_revision mode takes no patched revision")
    sides = ("base", "patched") if mode == "differential" else ("revision",)
    for index, step in enumerate(plan.get("setup", []) or []):
        if not isinstance(step, dict):
            raise PlanError(f"setup[{index}] must be an object")
        _argv(step.get("argv"), f"setup[{index}].argv")
        _timeout(step.get("timeout_s"), f"setup[{index}].timeout_s", 600)
    cases = plan.get("cases")
    if not isinstance(cases, list) or not cases:
        raise PlanError("cases must be a non-empty list")
    seen: set[str] = set()
    roles: list[str] = []
    for index, case in enumerate(cases):
        label = f"cases[{index}]"
        if not isinstance(case, dict):
            raise PlanError(f"{label} must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise PlanError(f"{label}.id must be a unique non-empty string")
        seen.add(case_id)
        if case.get("role") not in ROLES[mode]:
            raise PlanError(f"{label}.role must be one of {', '.join(ROLES[mode])} in {mode} mode")
        roles.append(str(case["role"]))
        _argv(case.get("argv"), f"{label}.argv")
        _timeout(case.get("timeout_s"), f"{label}.timeout_s", 120)
        expect = case.get("expect")
        if not isinstance(expect, dict) or set(expect) != set(sides):
            raise PlanError(f"{label}.expect must define exactly: {', '.join(sides)}")
        for side in sides:
            _expectation(expect[side], f"{label}.expect.{side}")
    if mode == "differential":
        waiver = (plan.get("waiver") or {}).get("root_cause_variant")
        if "original_reproduction" not in roles:
            raise PlanError("differential mode needs at least one original_reproduction case")
        if "legitimate_behavior" not in roles:
            raise PlanError("differential mode needs at least one legitimate_behavior case")
        if "root_cause_variant" not in roles and not (isinstance(waiver, str) and waiver.strip()):
            raise PlanError("differential mode needs a root_cause_variant case or waiver.root_cause_variant with a reason")
    env = plan.get("env") or {}
    if not isinstance(env, dict) or not all(isinstance(item, str) for item in env.get("pass", [])) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in (env.get("set") or {}).items()
    ):
        raise PlanError("env.pass must list variable names and env.set must map names to strings")
    limits = plan.get("limits") or {}
    output_bytes = limits.get("output_bytes", 65536)
    if not isinstance(output_bytes, int) or not 1024 <= output_bytes <= 1_048_576:
        raise PlanError("limits.output_bytes must be between 1024 and 1048576")
    _timeout(limits.get("total_timeout_s", 1800), "limits.total_timeout_s", 1800)
    return plan


# -- git --------------------------------------------------------------------

def isolated_git_env(scratch: Path) -> dict[str, str]:
    config = scratch / "empty-gitconfig"
    config.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(config), "GIT_TERMINAL_PROMPT": "0",
                "GIT_LFS_SKIP_SMUDGE": "1", "GIT_OPTIONAL_LOCKS": "0"})
    return env


def git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300, check=False)


def resolve(repo: Path, rev: str) -> str:
    completed = git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    if completed.returncode != 0 or not completed.stdout.strip():
        raise PlanError(f"revision does not resolve to a commit: {rev}")
    return completed.stdout.strip()


def status_fingerprint(repo: Path) -> str:
    completed = git(repo, "status", "--porcelain=v2", "-z", "--untracked-files=all",
                    env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    return hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest()


# -- execution --------------------------------------------------------------

def command_env(plan: dict[str, object]) -> dict[str, str]:
    env_spec = plan.get("env") or {}
    names = set(DEFAULT_PASS_ENV) | set(env_spec.get("pass", []))
    env = {name: value for name, value in os.environ.items() if name in names}
    env.update(env_spec.get("set") or {})
    return env


def terminate_group(process: subprocess.Popen[bytes]) -> None:
    if IS_WINDOWS:
        try:
            os.kill(process.pid, signal.CTRL_BREAK_EVENT)
        except OSError:
            pass
        try:
            process.kill()
        except OSError:
            pass
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def scan_output(path: Path, markers: list[str]) -> dict[str, bool]:
    found = {marker: False for marker in markers}
    if not markers:
        return found
    overlap = max(len(marker.encode("utf-8")) for marker in markers)
    tail = b""
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            window = tail + chunk
            text = window.decode("utf-8", errors="replace")
            for marker in markers:
                if marker in text:
                    found[marker] = True
            tail = window[-overlap:]
    return found


def run_command(argv: list[str], cwd: Path, env: dict[str, str], timeout: int, output_limit: int, log: Path,
                markers: list[str]) -> dict[str, object]:
    started = time.monotonic()
    kwargs: dict[str, object] = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    timed_out = False
    try:
        with open(log, "wb") as sink:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=sink,
                                       stderr=subprocess.STDOUT, **kwargs)
            try:
                exit_code: int | None = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_group(process)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass
                exit_code = None
            else:
                terminate_group(process)  # remove any stragglers left in the group
    except OSError as exc:
        return {"argv": argv, "exit_code": None, "timed_out": False, "start_error": str(exc)[:200],
                "duration_s": round(time.monotonic() - started, 3), "output_bytes": 0, "output_sha256": None,
                "head": "", "tail": "", "markers": {marker: False for marker in markers}}
    data = log.read_bytes() if log.stat().st_size <= output_limit else None
    size = log.stat().st_size
    digest = cw_scan.sha256_file(log)
    if data is None:
        with open(log, "rb") as handle:
            head_bytes = handle.read(output_limit // 2)
            handle.seek(max(0, size - output_limit // 2))
            tail_bytes = handle.read(output_limit // 2)
    else:
        head_bytes, tail_bytes = data, b""
    return {
        "argv": [cw_scan.redact(item) for item in argv],
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_s": round(time.monotonic() - started, 3),
        "output_bytes": size,
        "output_sha256": digest,
        "output_truncated": data is None,
        "head": cw_scan.redact(head_bytes.decode("utf-8", errors="replace")),
        "tail": cw_scan.redact(tail_bytes.decode("utf-8", errors="replace")),
        "markers": scan_output(log, markers),
    }


def expectation_met(expect: dict[str, object], result: dict[str, object]) -> bool:
    exit_code = result.get("exit_code")
    if result.get("timed_out") or exit_code is None:
        return False
    wanted = expect.get("exit")
    if wanted == "zero" and exit_code != 0:
        return False
    if wanted == "nonzero" and exit_code == 0:
        return False
    if isinstance(wanted, int) and exit_code != wanted:
        return False
    markers = result.get("markers") or {}
    if not all(markers.get(marker) for marker in expect.get("stdout_contains", [])):
        return False
    return not any(markers.get(marker) for marker in expect.get("stdout_excludes", []))


def case_status(mode: str, role: str, outcomes: dict[str, dict[str, object]]) -> tuple[str, str | None]:
    if any(item["result"].get("timed_out") for item in outcomes.values()):
        return "blocked", "timeout"
    if any(item["result"].get("start_error") for item in outcomes.values()):
        return "blocked", "start-failed"
    if mode == "single_revision":
        return ("verified", None) if outcomes["revision"]["met"] else ("failed", "expectation-not-met")
    base, patched = outcomes["base"]["met"], outcomes["patched"]["met"]
    if base and patched:
        return "verified", None
    if role == "legitimate_behavior":
        return "failed", "baseline-broken" if not base else "regressed"
    return "failed", "not-reproduced-on-base" if not base else "still-fails"


def overall(mode: str, plan: dict[str, object], cases: list[dict[str, object]], blocked_reason: str | None) -> dict[str, object]:
    statuses = [case["status"] for case in cases]
    if blocked_reason:
        return {"status": "blocked", "reason": blocked_reason}
    if "failed" in statuses:
        status = "failed"
    elif "blocked" in statuses:
        status = "blocked"
    else:
        status = "verified"
    if mode == "single_revision":
        return {"status": status, "claim": "the listed commands behave as expected at this revision",
                "note": "single-revision reproduction; not a patch proof"}
    variant_ok = any(case["role"] == "root_cause_variant" and case["status"] == "verified" for case in cases)
    waiver = (plan.get("waiver") or {}).get("root_cause_variant")
    if status == "verified" and not variant_ok and not waiver:
        status = "not checked"
    result = {"status": status,
              "claim": "the original failure reproduces on base and not on the patched revision, a root-cause variant "
                       "is also fixed, and legitimate behavior still works"}
    if waiver and not variant_ok:
        result["variant_waiver"] = cw_scan.excerpt(str(waiver), 200)
    return result


def remove_tree(path: Path, attempts: int = 10, delay_s: float = 0.5) -> bool:
    """Remove the scratch tree without raising; report whether it is gone.

    On Windows a process that outlived a timeout can hold its working directory or an
    open file inside the tree, so removal is retried for a bounded time before failing.
    """
    def make_writable(function, target, _):
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        function(target)

    for attempt in range(attempts):
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(path, onexc=make_writable)
            else:
                shutil.rmtree(path, onerror=make_writable)
        except OSError:
            pass
        if not path.exists():
            return True
        if attempt + 1 < attempts:
            time.sleep(delay_s)
    return False


def prepare(repo: Path, plan: dict[str, object], resolved: dict[str, str], diff_path: Path | None, scratch: Path,
            git_env: dict[str, str]) -> dict[str, Path]:
    workspaces: dict[str, Path] = {}
    sides = ("base", "patched") if plan["mode"] == "differential" else ("revision",)
    for side in sides:
        target = scratch / side
        clone = git(scratch, "clone", "--no-checkout", "--no-hardlinks", "--quiet", str(repo.resolve()), str(target), env=git_env)
        if clone.returncode != 0:
            raise RuntimeError(f"could not clone the repository for {side}: {clone.stderr.strip()[:200]}")
        revision = resolved["patched"] if side == "patched" and "patched" in resolved else resolved["base"]
        checkout = git(target, "checkout", "--quiet", "--detach", revision, env=git_env)
        if checkout.returncode != 0:
            raise RuntimeError(f"could not check out {revision} for {side}: {checkout.stderr.strip()[:200]}")
        if side == "patched" and diff_path is not None:
            applied = git(target, "apply", "--whitespace=nowarn", str(diff_path), env=git_env)
            if applied.returncode != 0:
                raise RuntimeError(f"the diff did not apply to base: {applied.stderr.strip()[:200]}")
        workspaces[side] = target
    return workspaces


def main(argv: list[str] | None = None) -> int:
    cw_scan.require_python()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", help="proof plan JSON")
    parser.add_argument("--repo", default=".", help="source repository (read only)")
    parser.add_argument("--execute", action="store_true", help="run the plan; only after the user approved the printed plan")
    parser.add_argument("--evidence", help="write evidence JSON here instead of stdout")
    parser.add_argument("--keep-workspaces", action="store_true", help="keep the temporary clones for inspection")
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    try:
        plan = validate_plan(json.loads(Path(args.plan).read_text(encoding="utf-8")))
        if git(repo, "rev-parse", "--git-dir").returncode != 0:
            raise PlanError(f"not a Git repository: {repo}")
        resolved = {"base": resolve(repo, str(plan["base"]["rev"]))}
        diff_path = None
        patched = plan.get("patched") or {}
        if "rev" in patched:
            resolved["patched"] = resolve(repo, str(patched["rev"]))
        elif "diff" in patched:
            diff_path = Path(str(patched["diff"]))
            digest = cw_scan.sha256_file(diff_path)
            if digest is None or digest != str(patched["diff_sha256"]).casefold():
                raise PlanError("patched.diff does not match patched.diff_sha256")
    except (PlanError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    mode = str(plan["mode"])
    sides = ("base", "patched") if mode == "differential" else ("revision",)
    def shown(argv_items: list[str]) -> list[str]:
        return [cw_scan.redact(item) for item in argv_items]

    commands = [{"phase": "setup", "side": side, "argv": shown(step["argv"]), "timeout_s": step.get("timeout_s", 600)}
                for side in sides for step in plan.get("setup", []) or []]
    commands += [{"phase": case["id"], "role": case["role"], "side": side, "argv": shown(case["argv"]),
                  "timeout_s": case.get("timeout_s", 120)} for case in plan["cases"] for side in sides]
    header = {"schema": EVIDENCE_SCHEMA, "schema_version": 1, "mode": mode,
              "revisions": {**resolved, **({"diff_sha256": plan["patched"]["diff_sha256"]} if diff_path else {})},
              "network": "not-controlled", "commands": commands}
    if not args.execute:
        cw_scan.emit({**header, "executed": False,
                      "authorization_required": "Show these exact commands to the user and rerun with --execute only after approval."},
                     args.evidence)
        return 0

    before = status_fingerprint(repo)
    scratch = Path(tempfile.mkdtemp(prefix="patch-proof-"))
    git_env = isolated_git_env(scratch)
    env = command_env(plan)
    limit = int((plan.get("limits") or {}).get("output_bytes", 65536))
    budget = int((plan.get("limits") or {}).get("total_timeout_s", 1800))
    deadline = time.monotonic() + budget
    setup_results: list[dict[str, object]] = []
    case_results: list[dict[str, object]] = []
    blocked_reason = None
    cleanup = "not attempted"
    try:
        workspaces = prepare(repo, plan, resolved, diff_path, scratch, git_env)
        logs = scratch / "logs"
        logs.mkdir()
        counter = 0
        for side in sides:
            for step in plan.get("setup", []) or []:
                counter += 1
                result = run_command(step["argv"], workspaces[side], env, min(step.get("timeout_s", 600), max(1, int(deadline - time.monotonic()))),
                                     limit, logs / f"{counter}.log", [])
                setup_results.append({"side": side, **result})
                if result["exit_code"] != 0:
                    blocked_reason = f"setup failed on {side}"
                    break
            if blocked_reason:
                break
        if not blocked_reason:
            for case in plan["cases"]:
                outcomes: dict[str, dict[str, object]] = {}
                for side in sides:
                    if time.monotonic() >= deadline:
                        blocked_reason = "total timeout reached"
                        break
                    counter += 1
                    expect = case["expect"][side]
                    markers = [*expect.get("stdout_contains", []), *expect.get("stdout_excludes", [])]
                    timeout = min(case.get("timeout_s", 120), max(1, int(deadline - time.monotonic())))
                    result = run_command(case["argv"], workspaces[side], env, timeout, limit, logs / f"{counter}.log", markers)
                    outcomes[side] = {"result": result, "met": expectation_met(expect, result)}
                if blocked_reason:
                    break
                status, reason = case_status(mode, case["role"], outcomes)
                case_results.append({"id": case["id"], "role": case["role"], "status": status, "reason": reason,
                                     "evidence_kind": "executed",
                                     "sides": {side: {**item["result"], "expectation_met": item["met"]}
                                               for side, item in outcomes.items()}})
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        blocked_reason = f"workspace preparation failed: {str(exc)[:200]}"
    finally:
        if args.keep_workspaces:
            cleanup = f"kept at {scratch}"
        else:
            cleanup = "removed" if remove_tree(scratch) else f"removal failed: {scratch}"
    after = status_fingerprint(repo)
    evidence = {**header, "executed": True, "setup": setup_results, "cases": case_results,
                "result": overall(mode, plan, case_results, blocked_reason),
                "source_worktree_unchanged": before == after, "cleanup": cleanup,
                "limitations": ["network access by commands is not controlled",
                                "submodules and Git LFS objects are not fetched",
                                *(["on Windows, processes outside the console group may survive a timeout"] if IS_WINDOWS else [])]}
    cw_scan.emit(evidence, args.evidence)
    status = evidence["result"]["status"]
    return 0 if status == "verified" else 1 if status == "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
