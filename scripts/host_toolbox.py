"""Inspect host capabilities safely and optionally evaluate repository readiness."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CODEX_HOME = Path.home() / ".codex"
DEFAULT_PROFILE = ROOT / "config" / "host-readiness.json"
LUNA_CONTRACTS = {
    "luna_worker": {"file": "luna-worker.toml", "reasoning": "high"},
    "luna_max_worker": {"file": "luna-max-worker.toml", "reasoning": "max"},
}
MCP_ROW = re.compile(
    r"^\s*(?P<name>\S+)\s+(?P<target>\S+)\s+.*?\s+(?P<status>enabled|disabled)\s+(?P<auth>.+?)\s*$",
    re.IGNORECASE,
)
PROFILE_FIELDS = {"schema_version", "name", "requirements"}
REQUIREMENT_FIELDS = {
    "plugin": {
        "kind",
        "name",
        "severity",
        "enabled",
        "match_repository_version",
        "plugin_id",
        "marketplace_name",
    },
    "worker": {"kind", "name", "severity"},
    "mcp": {"kind", "name", "severity", "enabled", "authenticated"},
}
SEVERITIES = {"required", "recommended", "optional"}
AUTHENTICATED_LABELS = {"bearer", "bearer token", "oauth"}
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_PLUGIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,191}$")
SAFE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
MAX_LUNA_CONFIG_BYTES = 64 * 1024
LUNA_ROOT_LABEL = "codex-home"


def _safe_label(value: Any) -> str | None:
    if isinstance(value, str) and SAFE_LABEL.fullmatch(value) is not None:
        return value
    return None


def _safe_plugin_id(value: Any) -> str | None:
    if isinstance(value, str) and SAFE_PLUGIN_ID.fullmatch(value) is not None:
        return value
    return None


def _safe_version(value: Any) -> str | None:
    if isinstance(value, str) and SAFE_VERSION.fullmatch(value) is not None:
        return value
    return None


def _safe_worker_file(filename: str) -> str:
    return f"agents/{filename}"


def _diagnostic(area: str, code: str) -> dict[str, str]:
    return {"area": area, "code": code}


def _command_result(command: Sequence[str], *, cwd: Path | None = None) -> tuple[str, str | None]:
    """Run a bounded host command and return stdout plus a sanitized failure code."""

    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return "", "executable_missing"
    except subprocess.TimeoutExpired:
        return "", "timeout"
    except subprocess.CalledProcessError:
        return "", "nonzero_exit"
    except OSError:
        return "", "os_error"
    except (TypeError, ValueError, RuntimeError, subprocess.SubprocessError):
        return "", "os_error"
    return completed.stdout, None


def _plugin_summary(payload: Any) -> dict[str, Any]:
    installed = payload.get("installed", []) if isinstance(payload, dict) else []
    plugins: list[dict[str, Any]] = []
    if isinstance(installed, list):
        for item in installed:
            if not isinstance(item, dict):
                continue
            name = _safe_label(item.get("name"))
            if name is None:
                continue
            plugins.append(
                {
                    "name": name,
                    "plugin_id": _safe_plugin_id(item.get("pluginId")),
                    "marketplace_name": _safe_label(item.get("marketplaceName")),
                    "version": _safe_version(item.get("version")),
                    "installed": item.get("installed") is True,
                    "enabled": item.get("enabled") is True,
                }
            )
    return {"status": "configured", "evidence": "configured", "plugins": plugins, "diagnostics": []}


def _categorize_auth(auth: str) -> str:
    """Reduce CLI authentication text to a non-sensitive readiness category."""

    normalized = " ".join(auth.casefold().split())
    if normalized in {"", "-", "none", "not logged in", "unauthenticated", "login required"}:
        return "not_authenticated"
    if normalized == "unsupported":
        return "unsupported"
    if normalized in AUTHENTICATED_LABELS:
        return "authenticated"
    return "unknown"


def parse_mcp_output(output: str) -> dict[str, Any]:
    """Parse safe MCP listing fields and describe how confidently the output was understood."""

    servers: list[dict[str, str]] = []
    diagnostics: list[dict[str, str]] = []
    section: str | None = None
    saw_header = False
    saw_unrecognized_row = False

    if not output.strip():
        return {
            "status": "listed_unparsed",
            "evidence": "not_checked",
            "servers": [],
            "diagnostics": [_diagnostic("codex.mcp", "empty_output")],
        }

    for line in output.splitlines():
        if "Command" in line and "Status" in line and "Name" in line:
            section = "local"
            saw_header = True
            continue
        if "Url" in line and "Status" in line and "Name" in line:
            section = "remote"
            saw_header = True
            continue
        if not line.strip() or set(line.strip()) <= {"-", " "}:
            continue
        match = MCP_ROW.match(line)
        if match and section:
            name = _safe_label(match.group("name"))
            if name is None:
                saw_unrecognized_row = True
                continue
            servers.append(
                {
                    "name": name,
                    "transport": section,
                    "status": match.group("status").lower(),
                    "auth_state": _categorize_auth(match.group("auth")),
                }
            )
        else:
            saw_unrecognized_row = True

    if not saw_header:
        diagnostics.append(_diagnostic("codex.mcp", "missing_headers"))
    if saw_unrecognized_row:
        diagnostics.append(_diagnostic("codex.mcp", "unrecognized_row"))
    names = [server["name"].casefold() for server in servers]
    if len(names) != len(set(names)):
        diagnostics.append(_diagnostic("codex.mcp", "duplicate_name"))
    if saw_header and not servers and not saw_unrecognized_row:
        diagnostics.append(_diagnostic("codex.mcp", "empty_list"))

    parse_failed = not saw_header or saw_unrecognized_row or len(names) != len(set(names))
    return {
        "status": "listed_unparsed" if parse_failed else "configured",
        "evidence": "not_checked" if parse_failed else "configured",
        "servers": servers,
        "diagnostics": diagnostics,
    }


def parse_mcp_list(output: str) -> list[dict[str, str]]:
    """Return safe MCP rows for callers that only need the legacy list interface."""

    return parse_mcp_output(output)["servers"]


def inspect_codex(codex_command: str = "codex") -> dict[str, Any]:
    """Inspect configured plugins and MCP servers without exposing environment values."""

    executable = shutil.which(codex_command) or codex_command
    plugin_output, plugin_failure = _command_result([executable, "plugin", "list", "--json"])
    if plugin_failure:
        plugin_data: dict[str, Any] = {
            "status": "not checked",
            "evidence": "not_checked",
            "failure_code": plugin_failure,
            "plugins": [],
            "diagnostics": [_diagnostic("codex.plugins", plugin_failure)],
        }
    else:
        try:
            payload = json.loads(plugin_output)
            if not isinstance(payload, dict) or not isinstance(payload.get("installed"), list):
                raise ValueError
            plugin_data = _plugin_summary(payload)
        except (json.JSONDecodeError, ValueError):
            plugin_data = {
                "status": "invalid",
                "evidence": "not_checked",
                "failure_code": "malformed_output",
                "plugins": [],
                "diagnostics": [_diagnostic("codex.plugins", "malformed_output")],
            }

    mcp_output, mcp_failure = _command_result([executable, "mcp", "list"])
    if mcp_failure:
        mcp_data: dict[str, Any] = {
            "status": "not checked",
            "evidence": "not_checked",
            "failure_code": mcp_failure,
            "servers": [],
            "diagnostics": [_diagnostic("codex.mcp", mcp_failure)],
        }
    else:
        mcp_data = parse_mcp_output(mcp_output)
    return {"plugins": plugin_data, "mcp": mcp_data}


def inspect_luna(codex_home: Path = DEFAULT_CODEX_HOME) -> dict[str, Any]:
    """Check the two expected host-level Luna worker contracts."""

    result: dict[str, Any] = {"root": LUNA_ROOT_LABEL, "workers": {}}
    try:
        home = Path(codex_home)
    except (TypeError, ValueError):
        home = None
    for name, contract in LUNA_CONTRACTS.items():
        safe: dict[str, Any] = {
            "file": _safe_worker_file(contract["file"]),
            "expected_name": name,
            "expected_model": "gpt-5.6-luna",
            "expected_reasoning": contract["reasoning"],
        }
        path = home / "agents" / contract["file"] if home is not None else None
        try:
            present = path.is_file() if path is not None else False
        except OSError:
            present = False
        if not present or path is None:
            safe["status"] = "missing"
            safe["evidence"] = "not_checked"
            result["workers"][name] = safe
            continue
        try:
            if path.stat().st_size > MAX_LUNA_CONFIG_BYTES:
                raise ValueError
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, tomllib.TOMLDecodeError):
            safe["status"] = "invalid"
            safe["evidence"] = "not_checked"
            result["workers"][name] = safe
            continue
        contract_ok = (
            data.get("name") == name
            and data.get("model") == "gpt-5.6-luna"
            and data.get("model_reasoning_effort") == contract["reasoning"]
            and data.get("sandbox_mode") == "workspace-write"
            and isinstance(data.get("developer_instructions"), str)
            and bool(data["developer_instructions"].strip())
        )
        safe["status"] = "verified" if contract_ok else "invalid"
        safe["evidence"] = "contract_verified" if contract_ok else "not_checked"
        if contract_ok:
            safe["model"] = "gpt-5.6-luna"
            safe["model_reasoning_effort"] = contract["reasoning"]
            safe["sandbox_mode"] = "workspace-write"
        result["workers"][name] = safe
    return result


def build_report(*, codex_command: str = "codex", codex_home: Path = DEFAULT_CODEX_HOME) -> dict[str, Any]:
    """Build the schema-v3 redacted host-capability report."""

    codex = inspect_codex(codex_command)
    diagnostics = [
        item
        for area in (codex["plugins"], codex["mcp"])
        for item in area.get("diagnostics", [])
    ]
    return {
        "schema_version": 3,
        "codex": codex,
        "luna": inspect_luna(codex_home),
        "readiness": {"status": "not_evaluated", "required_failure": False},
        "requirements": [],
        "diagnostics": diagnostics,
    }


def _validate_requirement(requirement: Any, index: int) -> dict[str, Any]:
    if not isinstance(requirement, dict):
        raise ValueError(f"requirement {index} must be an object")
    kind = requirement.get("kind")
    if kind not in REQUIREMENT_FIELDS:
        raise ValueError(f"requirement {index} has unsupported kind")
    unsupported = set(requirement) - REQUIREMENT_FIELDS[kind]
    if unsupported:
        raise ValueError(f"requirement {index} has unsupported fields: {sorted(unsupported)}")
    if not isinstance(requirement.get("name"), str) or not requirement["name"].strip():
        raise ValueError(f"requirement {index} must have a non-empty name")
    if requirement.get("severity") not in SEVERITIES:
        raise ValueError(f"requirement {index} has unsupported severity")
    for field in ("enabled", "match_repository_version"):
        if field in requirement and not isinstance(requirement[field], bool):
            raise ValueError(f"requirement {index} field {field} must be boolean")
    for field in ("plugin_id", "marketplace_name"):
        if field in requirement and (
            not isinstance(requirement[field], str) or not requirement[field].strip()
        ):
            raise ValueError(f"requirement {index} field {field} must be a non-empty string")
    return requirement


def load_profile(path: Path) -> dict[str, Any]:
    """Load and validate a readiness profile without accepting executable content."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("profile must be an object")
    unsupported = set(payload) - PROFILE_FIELDS
    if unsupported:
        raise ValueError(f"profile has unsupported fields: {sorted(unsupported)}")
    if payload.get("schema_version") != 1:
        raise ValueError("profile schema_version must be 1")
    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        raise ValueError("profile name must be a non-empty string")
    raw_requirements = payload.get("requirements")
    if not isinstance(raw_requirements, list) or not raw_requirements:
        raise ValueError("profile requirements must be a non-empty array")
    requirements = [_validate_requirement(item, index) for index, item in enumerate(raw_requirements)]
    identities = [(item["kind"], item["name"].casefold()) for item in requirements]
    if len(identities) != len(set(identities)):
        raise ValueError("profile contains a duplicate requirement")
    return {"schema_version": 1, "name": payload["name"], "requirements": requirements}


def _repository_plugin_version(repository_root: Path, name: str) -> str | None:
    manifest = repository_root / "plugins" / name / ".codex-plugin" / "plugin.json"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = payload.get("version") if isinstance(payload, dict) else None
    return version if isinstance(version, str) and version else None


def _result(requirement: dict[str, Any], status: str, evidence: str, message: str) -> dict[str, Any]:
    return {
        "kind": requirement["kind"],
        "name": _safe_label(requirement["name"]) or "unknown",
        "severity": requirement["severity"],
        "status": status,
        "evidence": evidence,
        "message": message,
    }


def _evaluate_plugin(
    requirement: dict[str, Any], report: dict[str, Any], repository_root: Path
) -> dict[str, Any]:
    plugin_report = report.get("codex", {}).get("plugins", {})
    if plugin_report.get("status") != "configured":
        return _result(requirement, "unknown", "not_checked", "Plugin configuration could not be checked.")
    matches = [
        item
        for item in plugin_report.get("plugins", [])
        if isinstance(item, dict) and str(item.get("name", "")).casefold() == requirement["name"].casefold()
    ]
    if len(matches) > 1:
        return _result(requirement, "invalid", "configured", "Required plugin identity is ambiguous.")
    plugin = matches[0] if matches else None
    if plugin is None or plugin.get("installed") is not True:
        return _result(requirement, "missing", "configured", "Required plugin is not installed.")
    expected_plugin_id = requirement.get("plugin_id")
    if expected_plugin_id is not None and plugin.get("plugin_id") != expected_plugin_id:
        return _result(requirement, "invalid", "configured", "Installed plugin ID does not match the profile.")
    expected_marketplace = requirement.get("marketplace_name")
    if expected_marketplace is not None and plugin.get("marketplace_name") != expected_marketplace:
        return _result(requirement, "invalid", "configured", "Installed plugin marketplace does not match the profile.")
    if requirement.get("enabled", False) and plugin.get("enabled") is not True:
        return _result(requirement, "invalid", "configured", "Plugin is installed but disabled.")
    if requirement.get("match_repository_version", False):
        expected = _repository_plugin_version(repository_root, requirement["name"])
        if expected is None:
            return _result(requirement, "unknown", "not_checked", "Repository plugin version could not be read.")
        if plugin.get("version") != expected:
            return _result(requirement, "invalid", "configured", "Installed plugin version does not match the repository.")
    return _result(requirement, "satisfied", "configured", "Plugin configuration satisfies the profile.")


def _evaluate_worker(requirement: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    worker = report.get("luna", {}).get("workers", {}).get(requirement["name"])
    if worker is None or worker.get("status") == "missing":
        return _result(requirement, "missing", "not_checked", "Worker contract file is missing.")
    if worker.get("status") != "verified":
        return _result(requirement, "invalid", "not_checked", "Worker contract is invalid.")
    return _result(requirement, "satisfied", "contract_verified", "Worker contract satisfies the profile.")


def _evaluate_mcp(requirement: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    mcp_report = report.get("codex", {}).get("mcp", {})
    if mcp_report.get("status") != "configured":
        return _result(requirement, "unknown", "not_checked", "MCP configuration could not be parsed confidently.")
    server = next(
        (
            item
            for item in mcp_report.get("servers", [])
            if isinstance(item, dict) and str(item.get("name", "")).casefold() == requirement["name"].casefold()
        ),
        None,
    )
    if server is None:
        return _result(requirement, "missing", "configured", "MCP server is not configured.")
    if requirement.get("enabled", False) and server.get("status") != "enabled":
        return _result(requirement, "invalid", "configured", "MCP server is configured but disabled.")
    if requirement.get("authenticated", False) and server.get("auth_state") != "authenticated":
        return _result(requirement, "invalid", "configured", "MCP server does not report an authenticated state.")
    evidence = "auth_reported" if requirement.get("authenticated", False) else "configured"
    return _result(requirement, "satisfied", evidence, "MCP configuration satisfies the profile.")


def evaluate_readiness(
    report: dict[str, Any], profile: dict[str, Any], *, repository_root: Path = ROOT
) -> dict[str, Any]:
    """Evaluate configuration readiness without claiming or attempting tool callability."""

    results: list[dict[str, Any]] = []
    for requirement in profile["requirements"]:
        if requirement["kind"] == "plugin":
            results.append(_evaluate_plugin(requirement, report, repository_root))
        elif requirement["kind"] == "worker":
            results.append(_evaluate_worker(requirement, report))
        else:
            results.append(_evaluate_mcp(requirement, report))

    required_failure = any(
        item["severity"] == "required" and item["status"] != "satisfied" for item in results
    )
    recommended_gap = any(
        item["severity"] == "recommended" and item["status"] != "satisfied" for item in results
    )
    status = "not_ready" if required_failure else "degraded" if recommended_gap else "ready"
    evaluated = dict(report)
    evaluated["readiness"] = {
        "status": status,
        "profile": _safe_label(profile["name"]) or "unknown",
        "required_failure": required_failure,
        "counts": {
            outcome: sum(item["status"] == outcome for item in results)
            for outcome in ("satisfied", "missing", "invalid", "unknown")
        },
    }
    evaluated["requirements"] = results
    return evaluated


def _human_report(report: dict[str, Any]) -> str:
    lines = ["Host toolbox report"]
    codex = report["codex"]
    plugins = codex["plugins"]
    lines.append(f"Plugins: {plugins['status']} ({len(plugins.get('plugins', []))} listed)")
    for plugin in plugins.get("plugins", []):
        state = "enabled" if plugin["enabled"] else "disabled"
        lines.append(f"  {plugin['name']}: {state}")
    mcp = codex["mcp"]
    lines.append(f"MCP: {mcp['status']} ({len(mcp.get('servers', []))} parsed)")
    for server in mcp.get("servers", []):
        lines.append(f"  {server['name']}: {server['status']} ({server['auth_state']})")
    for name, worker in report["luna"]["workers"].items():
        lines.append(f"{name}: {worker['status']}")
    if report["readiness"]["status"] != "not_evaluated":
        lines.append(f"Readiness: {report['readiness']['status']}")
        for requirement in report["requirements"]:
            lines.append(
                f"  [{requirement['severity']}] {requirement['kind']} "
                f"{requirement['name']}: {requirement['status']}"
            )
        lines.append("Configuration evidence only; external tool callability was not tested.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-command", default="codex", help="Codex executable name or path.")
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=DEFAULT_CODEX_HOME,
        help="Codex home containing agents/. Defaults to the current user's .codex directory.",
    )
    parser.add_argument("--json", action="store_true", help="Print the redacted report as JSON.")
    parser.add_argument("--check", action="store_true", help="Evaluate the selected readiness profile.")
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
        help="Readiness profile JSON. Used only with --check.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profile: dict[str, Any] | None = None
    if args.check:
        try:
            profile = load_profile(args.profile)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"ERROR: invalid readiness profile ({type(exc).__name__})", file=sys.stderr)
            return 2
    report = build_report(codex_command=args.codex_command, codex_home=args.codex_home)
    if profile is not None:
        report = evaluate_readiness(report, profile)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(_human_report(report))
    return 1 if args.check and report["readiness"]["required_failure"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
