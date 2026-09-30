"""Validate, preview, and optionally run the plugin routing evaluation set."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_PATH = ROOT / "plugins" / "coding-workflows" / "evals" / "trigger-routing.json"
DEFAULT_OUTPUT_ROOT = ROOT / ".artifacts" / "routing-evals"
ALLOWED_KINDS = {"direct", "indirect", "negative", "edge"}
CASE_FIELDS = {"id", "kind", "prompt", "expected_skill", "expected_behavior"}
CASE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CANONICAL_MARKETPLACE_NAME = "coding-agents"
CANONICAL_PLUGIN_NAME = "coding-workflows"
CANONICAL_PLUGIN_ID = f"{CANONICAL_PLUGIN_NAME}@{CANONICAL_MARKETPLACE_NAME}"
CANONICAL_PLUGIN_SOURCE = "./plugins/coding-workflows"
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/-]{0,127}$")
PLUGIN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PLUGIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,191}$")
VERSION_ID = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
GIT_REVISION = re.compile(r"^[0-9a-f]{7,64}$")
REPORT_SECRET_MATERIAL = re.compile(
    r"(?i)(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|(?<![A-Za-z0-9_-])(?:sk-|gh[pousr]_|xox[baprs]-)[A-Za-z0-9_-]{16,}|(?<![A-Za-z0-9_-])AKIA[0-9A-Z]{16}(?![A-Za-z0-9_-]))"
)
REPORT_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
REPORT_PRIVATE_PATH = re.compile(
    r"(?i)(?:[A-Z]:\\Users\\[^\\\s]+|/home/[^/\s]+/[^/\s]+|/Users/[^/\s]+/[^/\s]+)"
)


def _stable_code(value: str) -> str:
    return f"routing_preflight:{value}"


def _safe_model(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or MODEL_ID.fullmatch(value) is None:
        return "invalid"
    if "\\" in value or value.startswith("/") or "//" in value or ".." in value:
        return "invalid"
    return value


def _same_path(value: Any, expected: Path, *, base: Path | None = None) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        observed_path = Path(value)
        if base is not None and not observed_path.is_absolute():
            observed_path = base / observed_path
        observed = observed_path.resolve()
        resolved_expected = expected.resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return observed == resolved_expected


def _canonical_plugin_identity(
    repository_root: Path | None = None,
) -> tuple[dict[str, str] | None, str | None]:
    try:
        root = (repository_root or ROOT).resolve()
    except (OSError, RuntimeError, ValueError):
        return None, "canonical_repository_unavailable"
    marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
    try:
        if not marketplace_path.resolve().is_relative_to(root):
            return None, "canonical_marketplace_unverified"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, RuntimeError, ValueError, json.JSONDecodeError):
        return None, "canonical_marketplace_unreadable"
    if not isinstance(marketplace, dict) or marketplace.get("name") != CANONICAL_MARKETPLACE_NAME:
        return None, "canonical_marketplace_invalid"
    entries = marketplace.get("plugins")
    if not isinstance(entries, list):
        return None, "canonical_marketplace_invalid"
    matches = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and entry["name"].casefold() == CANONICAL_PLUGIN_NAME.casefold()
    ]
    if len(matches) != 1:
        return None, "canonical_plugin_not_unambiguous"
    entry = matches[0]
    source = entry.get("source")
    if (
        not isinstance(source, dict)
        or source.get("source") != "local"
        or source.get("path") != CANONICAL_PLUGIN_SOURCE
    ):
        return None, "canonical_source_invalid"
    expected_source = root / "plugins" / CANONICAL_PLUGIN_NAME
    try:
        plugin_root = (root / "plugins").resolve()
        resolved_source = expected_source.resolve()
    except (OSError, RuntimeError, ValueError):
        return None, "canonical_source_unverified"
    if not plugin_root.is_relative_to(root) or not resolved_source.is_relative_to(plugin_root):
        return None, "canonical_source_unverified"
    manifest_path = expected_source / ".codex-plugin" / "plugin.json"
    try:
        if not manifest_path.resolve().is_relative_to(root):
            return None, "canonical_manifest_unverified"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, RuntimeError, ValueError, json.JSONDecodeError):
        return None, "canonical_manifest_unreadable"
    if not isinstance(manifest, dict) or manifest.get("name") != CANONICAL_PLUGIN_NAME:
        return None, "canonical_manifest_invalid"
    version = manifest.get("version")
    if not isinstance(version, str) or VERSION_ID.fullmatch(version) is None:
        return None, "canonical_version_invalid"
    return {
        "plugin_id": CANONICAL_PLUGIN_ID,
        "name": CANONICAL_PLUGIN_NAME,
        "marketplace_name": CANONICAL_MARKETPLACE_NAME,
        "version": version,
        "source": CANONICAL_PLUGIN_SOURCE,
    }, None


def _plugin_preflight(
    codex_command: str, repository_root: Path | None = None
) -> tuple[bool, str, dict[str, str] | None, dict[str, str] | None]:
    canonical, canonical_failure = _canonical_plugin_identity(repository_root)
    if canonical is None:
        return False, _stable_code(canonical_failure or "canonical_identity_unavailable"), None, None
    try:
        executable = shutil.which(codex_command)
    except (OSError, TypeError, ValueError, RuntimeError):
        return False, _stable_code("executable_inspection_failed"), canonical, None
    if executable is None:
        return False, _stable_code("executable_missing"), canonical, None
    try:
        completed = subprocess.run(
            [executable, "plugin", "list", "--json", "--available"],
            cwd=repository_root or ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(completed.stdout)
    except (
        OSError,
        TypeError,
        ValueError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ):
        return False, _stable_code("plugin_inspection_failed"), canonical, None
    if not isinstance(payload, dict):
        return False, _stable_code("plugin_output_invalid"), canonical, None
    installed = payload.get("installed")
    if not isinstance(installed, list) or not all(isinstance(plugin, dict) for plugin in installed):
        return False, _stable_code("plugin_output_invalid"), canonical, None
    available = payload.get("available")
    if not isinstance(available, list) or not all(isinstance(plugin, dict) for plugin in available):
        return False, _stable_code("plugin_output_invalid"), canonical, None
    related = [
        plugin
        for plugin in installed
        if plugin.get("name") == CANONICAL_PLUGIN_NAME
        or plugin.get("pluginId") == CANONICAL_PLUGIN_ID
        or (
            isinstance(plugin.get("name"), str)
            and plugin.get("name").casefold() == CANONICAL_PLUGIN_NAME.casefold()
        )
    ]
    available_related = [
        plugin
        for plugin in available
        if plugin.get("name") == CANONICAL_PLUGIN_NAME
        or plugin.get("pluginId") == CANONICAL_PLUGIN_ID
        or (
            isinstance(plugin.get("name"), str)
            and plugin.get("name").casefold() == CANONICAL_PLUGIN_NAME.casefold()
        )
    ]
    # The live `codex plugin list --json --available` schema is not verified
    # from an authoritative source in this repository: `available` may or may
    # not repeat an installed plugin. Until live evidence establishes the
    # schema, preflight deliberately fails closed here so an uncertain
    # identity can never authorize a model-backed run.
    if available_related:
        return False, _stable_code("plugin_identity_ambiguous"), canonical, None
    if not related:
        return False, _stable_code("plugin_not_installed"), canonical, None
    if len(related) != 1:
        return False, _stable_code("plugin_identity_ambiguous"), canonical, None
    plugin = related[0]
    plugin_id = plugin.get("pluginId")
    name = plugin.get("name")
    marketplace_name = plugin.get("marketplaceName")
    if not isinstance(plugin_id, str) or not isinstance(name, str) or not isinstance(marketplace_name, str):
        return False, _stable_code("plugin_identity_missing"), canonical, None
    if plugin_id != canonical["plugin_id"]:
        return False, _stable_code("plugin_id_mismatch"), canonical, None
    if name != canonical["name"]:
        return False, _stable_code("plugin_name_mismatch"), canonical, None
    if marketplace_name != canonical["marketplace_name"]:
        return False, _stable_code("marketplace_mismatch"), canonical, None
    if plugin.get("installed") is not True:
        return False, _stable_code("plugin_not_installed"), canonical, None
    if plugin.get("enabled") is not True:
        return False, _stable_code("plugin_disabled"), canonical, None
    version = plugin.get("version")
    if not isinstance(version, str) or not version:
        return False, _stable_code("plugin_version_missing"), canonical, None
    if version != canonical["version"]:
        return False, _stable_code("plugin_version_mismatch"), canonical, None
    source = plugin.get("source")
    if not isinstance(source, dict) or source.get("source") != "local":
        return False, _stable_code("plugin_source_invalid"), canonical, None
    expected_source = (repository_root or ROOT) / "plugins" / CANONICAL_PLUGIN_NAME
    source_matches_plugin = _same_path(
        source.get("path"), expected_source, base=repository_root or ROOT
    )
    marketplace_source = plugin.get("marketplaceSource")
    if marketplace_source is None:
        if not source_matches_plugin:
            return False, _stable_code("marketplace_source_missing"), canonical, None
        source_evidence = "canonical_plugin_path"
    else:
        if not isinstance(marketplace_source, dict) or marketplace_source.get("sourceType") != "local":
            return False, _stable_code("marketplace_source_invalid"), canonical, None
        if not _same_path(
            marketplace_source.get("source"),
            (repository_root or ROOT),
            base=repository_root or ROOT,
        ):
            return False, _stable_code("marketplace_source_mismatch"), canonical, None
        source_evidence = "local_marketplace"
    observed = {
        "plugin_id": plugin_id,
        "name": name,
        "marketplace_name": marketplace_name,
        "version": version,
        "source": canonical["source"],
        "source_evidence": source_evidence,
    }
    return True, f"Using {plugin_id} version {version}", canonical, observed


def load_eval_data(path: Path = DEFAULT_CASES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_cases(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for skill in data.get("skills", []):
        if not isinstance(skill, dict):
            continue
        for case in skill.get("cases", []):
            if isinstance(case, dict):
                yield {**case, "skill": skill.get("name")}


def validate_eval_data(data: Any, skill_names: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Routing evaluations must be a JSON object."]
    if data.get("version") != 2:
        errors.append("Routing evaluations must use version 2.")
    entries = data.get("skills")
    if not isinstance(entries, list):
        return errors + ["Routing evaluations must contain a skills array."]

    names: list[str] = []
    case_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("Routing evaluation skill entry must be an object.")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            errors.append("Routing evaluation skill entry is missing a name.")
            continue
        names.append(name)
        cases = entry.get("cases")
        if not isinstance(cases, list):
            errors.append(f"Routing evaluation {name} must contain a cases array.")
            continue

        kind_counts = {kind: 0 for kind in ALLOWED_KINDS}
        for case in cases:
            if not isinstance(case, dict):
                errors.append(f"Routing evaluation {name} contains a non-object case.")
                continue
            case_id = case.get("id")
            kind = case.get("kind")
            prompt = case.get("prompt")
            expected_skill = case.get("expected_skill")
            expected_behavior = case.get("expected_behavior")
            unknown_fields = sorted(set(case) - CASE_FIELDS)
            if unknown_fields:
                errors.append(
                    f"Routing evaluation {name} case {case_id!r} has unsupported fields: {unknown_fields}."
                )

            if not isinstance(case_id, str) or CASE_ID.fullmatch(case_id) is None:
                errors.append(f"Routing evaluation {name} has an invalid case id: {case_id!r}")
            elif case_id in case_ids:
                errors.append(f"Duplicate routing evaluation case id: {case_id}")
            else:
                case_ids.add(case_id)
            if kind not in ALLOWED_KINDS:
                errors.append(f"Routing evaluation {name} case {case_id!r} has invalid kind {kind!r}.")
                continue
            kind_counts[kind] += 1
            if not isinstance(prompt, str) or not prompt.strip():
                errors.append(f"Routing evaluation {name} case {case_id!r} is missing a prompt.")
            if not isinstance(expected_behavior, str) or not expected_behavior.strip():
                errors.append(f"Routing evaluation {name} case {case_id!r} is missing expected behavior.")
            if kind in {"direct", "indirect"} and expected_skill != name:
                errors.append(f"Routing evaluation {name} case {case_id!r} must expect {name}.")
            if kind == "negative" and expected_skill is not None:
                errors.append(f"Routing evaluation {name} negative case {case_id!r} must expect no skill.")
            if expected_skill is not None and not isinstance(expected_skill, str):
                errors.append(f"Routing evaluation {name} case {case_id!r} has invalid expected_skill.")

        if kind_counts["direct"] < 1 or kind_counts["indirect"] < 2:
            errors.append(f"Routing evaluation {name} needs one direct and two indirect cases.")
        if kind_counts["negative"] < 3:
            errors.append(f"Routing evaluation {name} needs at least three negative cases.")
        if kind_counts["edge"] < 1:
            errors.append(f"Routing evaluation {name} needs at least one edge case.")

    if len(names) != len(set(names)):
        errors.append("Routing evaluations contain duplicate skill names.")
    allowed_skill_names = set(names) if skill_names is None else skill_names
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry.get("name"):
            continue
        name = entry["name"]
        cases = entry.get("cases")
        if not isinstance(cases, list):
            continue
        for case in cases:
            if not isinstance(case, dict):
                continue
            expected_skill = case.get("expected_skill")
            if isinstance(expected_skill, str) and expected_skill not in allowed_skill_names:
                errors.append(
                    f"Routing evaluation {name} case {case.get('id')!r} has unknown expected_skill {expected_skill!r}."
                )
    if skill_names is not None and set(names) != skill_names:
        errors.append(f"Routing/skill mismatch: routing={sorted(names)}, skills={sorted(skill_names)}")
    return errors


def select_cases(
    data: dict[str, Any],
    *,
    skills: set[str] | None = None,
    case_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    cases = list(iter_cases(data))
    if skills:
        cases = [case for case in cases if case["skill"] in skills]
    if case_ids:
        cases = [case for case in cases if case["id"] in case_ids]
    return cases


def plugin_is_ready(
    codex_command: str,
    *,
    repository_root: Path | None = None,
    details: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    ready, message, canonical, observed = _plugin_preflight(codex_command, repository_root)
    if details is not None:
        details.update({"canonical": canonical, "observed": observed})
    return ready, message


def _output_schema(case_id: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "case_id": {"const": case_id},
            "applied_skill": {"type": ["string", "null"]},
            "boundary_observed": {"type": "boolean"},
            "evidence": {"type": "string"},
            "response": {"type": "string"},
        },
        "required": ["case_id", "applied_skill", "boundary_observed", "evidence", "response"],
    }


def _evaluation_prompt(case: dict[str, Any]) -> str:
    return (
        "Complete the user request below using the installed skills only when they genuinely apply. "
        "Return the required JSON object. Set applied_skill to the exact skill name you used, or null. "
        "Set boundary_observed to true only when the response respects the selected workflow's scope. "
        "Put the actual user-facing answer in response and concise observable justification in evidence.\n\n"
        f"USER REQUEST:\n{case['prompt']}"
    )


def _failed_case_result(
    case: dict[str, Any],
    failure_code: str,
    *,
    elapsed_seconds: float | None = None,
    exit_code: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "case": case,
        "infrastructure_status": "failed",
        "failure_code": failure_code,
        "review_status": "unreviewed",
    }
    if elapsed_seconds is not None:
        result["elapsed_seconds"] = elapsed_seconds
    if exit_code is not None:
        result["exit_code"] = exit_code
    return result


def run_case(
    case: dict[str, Any],
    *,
    codex_command: str,
    model: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    try:
        executable = shutil.which(codex_command) or codex_command
    except (OSError, TypeError, ValueError, RuntimeError):
        return _failed_case_result(case, "case_process_error")
    with tempfile.TemporaryDirectory(prefix="coding-workflows-eval-") as temp_dir:
        temp_root = Path(temp_dir)
        schema_path = temp_root / "schema.json"
        response_path = temp_root / "response.json"
        try:
            schema_path.write_text(
                json.dumps(_output_schema(case["id"]), indent=2), encoding="utf-8"
            )
        except (OSError, TypeError, ValueError):
            return _failed_case_result(case, "case_schema_write_failed")
        command = [
            executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(response_path),
            "--cd",
            str(ROOT),
        ]
        if model:
            command.extend(["--model", model])
        command.append(_evaluation_prompt(case))
        started = datetime.now(UTC)
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _failed_case_result(case, "case_timeout")
        except (
            OSError,
            TypeError,
            ValueError,
            RuntimeError,
            StopIteration,
            subprocess.SubprocessError,
        ):
            return _failed_case_result(case, "case_process_error")
        elapsed = (datetime.now(UTC) - started).total_seconds()
        return_code = completed.returncode if isinstance(completed.returncode, int) else -1
        try:
            response_exists = response_path.is_file()
        except OSError:
            response_exists = False
        if return_code != 0:
            return _failed_case_result(
                case,
                "case_nonzero_exit",
                elapsed_seconds=elapsed,
                exit_code=return_code,
            )
        if not response_exists:
            return _failed_case_result(case, "case_output_missing", elapsed_seconds=elapsed)
        try:
            observed = json.loads(response_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TypeError, json.JSONDecodeError):
            return _failed_case_result(case, "case_response_unreadable", elapsed_seconds=elapsed)
        required_fields = {
            "case_id": str,
            "boundary_observed": bool,
            "evidence": str,
            "response": str,
        }
        expected_fields = set(required_fields) | {"applied_skill"}
        if not isinstance(observed, dict):
            return _failed_case_result(case, "case_response_not_object", elapsed_seconds=elapsed)
        if set(observed) != expected_fields:
            return _failed_case_result(case, "case_response_fields_mismatch", elapsed_seconds=elapsed)
        if observed.get("case_id") != case["id"]:
            return _failed_case_result(case, "case_id_mismatch", elapsed_seconds=elapsed)
        if any(not isinstance(observed.get(field), expected_type) for field, expected_type in required_fields.items()):
            return _failed_case_result(case, "case_field_type", elapsed_seconds=elapsed)
        applied_skill = observed.get("applied_skill")
        if applied_skill is not None and not isinstance(applied_skill, str):
            return _failed_case_result(case, "case_applied_skill_type", elapsed_seconds=elapsed)
        return {
            "case": case,
            "infrastructure_status": "completed",
            "elapsed_seconds": elapsed,
            "observed": observed,
            "declared_skill_match": applied_skill == case.get("expected_skill"),
            "review_status": "unreviewed",
        }


def _case_set_provenance(cases: list[dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "algorithm": "sha256",
        "hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "count": len(cases),
    }


def _git_value(arguments: list[str], repository_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, TypeError, ValueError, RuntimeError, subprocess.SubprocessError, StopIteration):
        return None
    if completed.returncode != 0 or not isinstance(completed.stdout, str):
        return None
    return completed.stdout.strip()


def _repository_provenance(repository_root: Path) -> dict[str, Any]:
    revision = _git_value(["rev-parse", "HEAD"], repository_root)
    if revision is None or GIT_REVISION.fullmatch(revision) is None:
        revision = None
    status = _git_value(["status", "--porcelain", "--untracked-files=normal"], repository_root)
    return {"revision": revision, "dirty": None if status is None else bool(status)}


def _model_provenance(requested_model: str | None) -> dict[str, Any]:
    requested = _safe_model(requested_model)
    if requested_model is None:
        requested = "active-default"
    elif requested == "invalid":
        requested = "invalid"
    return {
        "requested": requested,
        "resolved": None,
        "resolution": "not_exposed",
    }


def _public_plugin_identity(identity: dict[str, str] | None) -> dict[str, str] | None:
    if identity is None:
        return None
    plugin_id = identity.get("plugin_id")
    name = identity.get("name")
    marketplace_name = identity.get("marketplace_name")
    version = identity.get("version")
    source = identity.get("source")
    source_evidence = identity.get("source_evidence")
    if (
        not isinstance(plugin_id, str)
        or PLUGIN_ID.fullmatch(plugin_id) is None
        or not isinstance(name, str)
        or PLUGIN_NAME.fullmatch(name) is None
        or not isinstance(marketplace_name, str)
        or PLUGIN_NAME.fullmatch(marketplace_name) is None
        or not isinstance(version, str)
        or VERSION_ID.fullmatch(version) is None
        or source != CANONICAL_PLUGIN_SOURCE
        or (
            source_evidence is not None
            and source_evidence not in {"canonical_plugin_path", "local_marketplace"}
        )
    ):
        return None
    result = {
        "plugin_id": plugin_id,
        "name": name,
        "marketplace_name": marketplace_name,
        "version": version,
        "source": source,
    }
    if isinstance(source_evidence, str):
        result["source_evidence"] = source_evidence
    return result


def build_provenance(
    cases: list[dict[str, Any]],
    *,
    requested_model: str | None,
    canonical_plugin: dict[str, str] | None,
    observed_plugin: dict[str, str] | None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    root = (repository_root or ROOT).resolve()
    return {
        "case_set": _case_set_provenance(cases),
        "repository": _repository_provenance(root),
        "plugin": {
            "canonical": _public_plugin_identity(canonical_plugin),
            "observed": _public_plugin_identity(observed_plugin),
        },
        "model": _model_provenance(requested_model),
    }


def _report_contains_sensitive_data(report: dict[str, Any]) -> bool:
    def visit(value: Any) -> bool:
        if isinstance(value, dict):
            return any(visit(item) for item in value.values())
        if isinstance(value, list):
            return any(visit(item) for item in value)
        if not isinstance(value, str):
            return False
        return any(
            pattern.search(value)
            for pattern in (REPORT_SECRET_MATERIAL, REPORT_EMAIL, REPORT_PRIVATE_PATH)
        )

    return visit(report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Call Codex for the selected cases. Default is dry-run.")
    parser.add_argument(
        "--acknowledge-cost",
        action="store_true",
        help="Required with --run because model-backed evaluations can consume quota or incur API cost.",
    )
    parser.add_argument("--skill", action="append", default=[], help="Evaluate one skill; repeat to select several.")
    parser.add_argument("--case", action="append", default=[], help="Evaluate one case id; repeat to select several.")
    parser.add_argument("--model", help="Optional Codex model override. The active default is used when omitted.")
    parser.add_argument("--codex-command", default="codex", help="Codex executable name or path.")
    parser.add_argument("--timeout-seconds", type=int, default=300, help="Per-case timeout; default 300.")
    parser.add_argument("--output", type=Path, help="Report path. Defaults under .artifacts/routing-evals/.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = load_eval_data()
    except (OSError, UnicodeError, TypeError, json.JSONDecodeError):
        print("ERROR: routing evaluation data could not be read (routing_data_unavailable)", file=sys.stderr)
        return 2
    errors = validate_eval_data(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    cases = select_cases(data, skills=set(args.skill), case_ids=set(args.case))
    if not cases:
        print("No routing evaluation cases matched the selection.", file=sys.stderr)
        return 2

    if not args.run:
        for case in cases:
            print(f"{case['id']} [{case['kind']}] expected={case.get('expected_skill') or 'none'}")
            print(f"  {case['prompt']}")
        print(f"Dry run: {len(cases)} case(s); no model calls or files written.")
        return 0
    if not args.acknowledge_cost:
        print("--run requires --acknowledge-cost.", file=sys.stderr)
        return 2
    preflight_details: dict[str, Any] = {}
    ready, message = plugin_is_ready(args.codex_command, details=preflight_details)
    canonical_plugin = preflight_details.get("canonical")
    observed_plugin = preflight_details.get("observed")
    if ready and (canonical_plugin is None or observed_plugin is None):
        print("Preflight failed: routing_preflight:identity_incomplete", file=sys.stderr)
        return 2
    if not ready:
        print(f"Preflight failed: {message}", file=sys.stderr)
        return 2
    print(message)
    provenance = build_provenance(
        cases,
        requested_model=args.model,
        canonical_plugin=canonical_plugin,
        observed_plugin=observed_plugin,
    )

    results = [
        run_case(
            case,
            codex_command=args.codex_command,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
        )
        for case in cases
    ]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = args.output or DEFAULT_OUTPUT_ROOT / f"routing-eval-{timestamp}.json"
    report = {
        "schema_version": 2,
        "created_at": datetime.now(UTC).isoformat(),
        "model": _safe_model(args.model) or "active-default",
        "review_policy": "Model declarations are unreviewed evidence, not automatic behavioral passes.",
        "provenance": provenance,
        "results": results,
    }
    if _report_contains_sensitive_data(report):
        print("ERROR: routing report contained sensitive data and was not written", file=sys.stderr)
        return 2
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (OSError, TypeError, ValueError):
        print("ERROR: routing report could not be written (routing_report_write_failed)", file=sys.stderr)
        return 2
    failures = sum(result["infrastructure_status"] != "completed" for result in results)
    print(f"Wrote {len(results)} unreviewed result(s) to {output_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
