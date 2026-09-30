"""Inventory npm lockfile dependencies offline and report measured risk signals with coverage.

Supports npm `package-lock.json` and `npm-shrinkwrap.json` lockfile versions 2
and 3. Separates declared from resolved dependencies and direct from transitive
ones, records each package's resolution source, integrity, and install-script
flag, detects lock drift, and lists other ecosystems it does not assess. It makes
no network requests: it can write an advisory query payload for the agent to send
with host tools, and ingest the saved results. Never prints credential values.
Exit codes: 0 no Important or Blocker finding; 1 findings; 2 usage error or
nothing measured.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "references", _HERE.parents[2] / "references"):
    if (_candidate / "cw_scan.py").is_file():
        sys.path.insert(0, str(_candidate))
        break
import cw_scan  # noqa: E402


TOOL = "dependency-risk/dep_inventory"
DECLARED_SECTIONS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
CHECKS = ("install-script", "resolution-source", "integrity", "lock-drift", "advisories")
OTHER_ECOSYSTEMS = {
    "yarn.lock": "npm (yarn lockfile)",
    "pnpm-lock.yaml": "npm (pnpm lockfile)",
    "bun.lockb": "npm (bun lockfile)",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "poetry.lock": "Python",
    "uv.lock": "Python",
    "pipfile.lock": "Python",
    "cargo.lock": "Rust",
    "go.sum": "Go",
    "gemfile.lock": "Ruby",
    "composer.lock": "PHP",
    "packages.lock.json": ".NET",
    "pom.xml": "Java",
    "build.gradle": "Java",
}
SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "vendor", "target", "dist", "build"})
REGISTRY_TARBALL = re.compile(r"^https?://[^/]+/.+/-/[^/]+\.tgz(?:[?#].*)?$")
NPMRC_CREDENTIAL = re.compile(r"^\s*(?P<key>[^=\s]*(?:_authToken|_auth|_password|:_authToken))\s*=\s*(?P<value>.*)$")


def package_name(location: str) -> str | None:
    if "node_modules/" not in location:
        return None
    return location.rsplit("node_modules/", 1)[1]


def source_kind(entry: dict[str, object]) -> tuple[str, str | None]:
    if entry.get("link"):
        return "link", None
    resolved = entry.get("resolved")
    if not isinstance(resolved, str) or not resolved:
        return ("bundled", None) if entry.get("inBundle") else ("unknown", None)
    if resolved.startswith(("git+", "git:", "github:", "gitlab:", "bitbucket:")) or ".git#" in resolved:
        return "git", None
    if resolved.startswith("file:"):
        return "file", None
    if REGISTRY_TARBALL.match(resolved):
        host = urlsplit(resolved).hostname or ""
        return "registry", host
    if resolved.startswith(("http://", "https://")):
        return "tarball", urlsplit(resolved).hostname
    return "unknown", None


def declared(manifest: dict[str, object]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for section in DECLARED_SECTIONS:
        values = manifest.get(section)
        if isinstance(values, dict):
            result[section] = {str(name): str(spec) for name, spec in values.items()}
    return result


def main(argv: list[str] | None = None) -> int:
    cw_scan.require_python()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", help="project directory containing package.json")
    parser.add_argument("--emit-osv-query", metavar="FILE",
                        help="write an advisory query payload (package names and versions only) to FILE")
    parser.add_argument("--osv-results", metavar="FILE",
                        help="ingest a saved response to the payload written by --emit-osv-query")
    parser.add_argument("--output", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    findings: list[dict[str, object]] = []
    coverage: dict[str, dict[str, str]] = {}
    unsupported: list[dict[str, str]] = []
    walked = cw_scan.walk(root, cw_scan.Limits(max_depth=6, max_files=20000), SKIP_DIRS)
    for entry in walked.entries:
        name = PurePosixPath(entry.relative).name.casefold()
        if entry.kind != "file":
            continue
        if name in OTHER_ECOSYSTEMS or re.match(r"requirements.*\.txt$", name):
            unsupported.append({"path": entry.relative, "ecosystem": OTHER_ECOSYSTEMS.get(name, "Python"),
                                "status": "not checked (ecosystem or format not implemented)"})
        elif name == "package.json" and entry.relative != "package.json":
            unsupported.append({"path": entry.relative, "ecosystem": "npm (nested package)",
                                "status": "not checked (run the helper in that directory)"})

    npmrc = root / ".npmrc"
    if npmrc.is_file():
        for number, line in cw_scan.iter_lines(npmrc.read_text(encoding="utf-8", errors="replace")):
            match = NPMRC_CREDENTIAL.match(line)
            if match and not match.group("value").strip().startswith("${"):
                findings.append(cw_scan.finding("npmrc-credential", "credentials", "Important", ".npmrc", number,
                                                "config", f"credential value set for {match.group('key')} (value withheld)"))

    manifest_path = root / "package.json"
    lock_path = next((root / name for name in ("npm-shrinkwrap.json", "package-lock.json") if (root / name).is_file()), None)
    packages: list[dict[str, object]] = []
    drift: list[dict[str, str]] = []
    lock_version = None
    measured = False
    manifest: dict[str, object] = {}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: package.json is not readable JSON: {exc}", file=sys.stderr)
            return 2

    if lock_path is None:
        reason = "no npm lockfile; resolved versions unknown" if manifest_path.is_file() else "no package.json or npm lockfile"
        for check in CHECKS:
            coverage[check] = cw_scan.coverage("blocked" if manifest_path.is_file() else "not checked", reason)
    else:
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: {lock_path.name} is not readable JSON: {exc}", file=sys.stderr)
            return 2
        lock_version = lock.get("lockfileVersion") if isinstance(lock, dict) else None
        entries = lock.get("packages") if isinstance(lock, dict) else None
        if not isinstance(lock_version, int) or lock_version < 2 or not isinstance(entries, dict):
            for check in CHECKS:
                coverage[check] = cw_scan.coverage(
                    "not checked", f"lockfileVersion {lock_version!r} lacks the packages map this helper reads")
        else:
            measured = True
            root_entry = entries.get("", {}) if isinstance(entries.get(""), dict) else {}
            locked_declared = declared(root_entry)
            manifest_declared = declared(manifest)
            direct_names = {name for section in locked_declared.values() for name in section}
            for section in DECLARED_SECTIONS:
                wanted = manifest_declared.get(section, {})
                locked = locked_declared.get(section, {})
                for name in sorted(set(wanted) - set(locked)):
                    drift.append({"name": name, "section": section, "issue": "declared in package.json but not in the lockfile"})
                for name in sorted(set(locked) - set(wanted)):
                    drift.append({"name": name, "section": section, "issue": "in the lockfile root but not in package.json"})
                for name in sorted(set(wanted) & set(locked)):
                    if wanted[name] != locked[name]:
                        drift.append({"name": name, "section": section,
                                      "issue": f"range differs: package.json {wanted[name]} vs lockfile {locked[name]}"})
            for location, entry in sorted(entries.items()):
                if location == "" or not isinstance(entry, dict):
                    continue
                name = package_name(location)
                kind, host = source_kind(entry)
                is_workspace = name is None
                record = {
                    "name": name or location,
                    "version": entry.get("version"),
                    "location": location,
                    "direct": bool(name) and location == f"node_modules/{name}" and name in direct_names,
                    "dev": bool(entry.get("dev")),
                    "optional": bool(entry.get("optional") or entry.get("devOptional")),
                    "source": "workspace" if is_workspace else kind,
                    "registry_host": host,
                    "integrity": bool(entry.get("integrity")),
                    "install_script": bool(entry.get("hasInstallScript")),
                    "license": entry.get("license") if isinstance(entry.get("license"), str) else None,
                }
                packages.append(record)
                label = f"{record['name']}@{record['version']}"
                if record["install_script"]:
                    findings.append(cw_scan.finding("install-script", "install-script", "Important", lock_path.name, None,
                                                    "lockfile", f"{label} runs a preinstall, install, or postinstall script"))
                if kind in {"git", "tarball"} and not is_workspace:
                    findings.append(cw_scan.finding(f"{kind}-source", "resolution-source", "Important", lock_path.name,
                                                    None, "lockfile", f"{label} resolves from a {kind} source, not a registry"))
                if kind == "registry" and host and host != "registry.npmjs.org":
                    findings.append(cw_scan.finding("custom-registry", "resolution-source", "Minor", lock_path.name,
                                                    None, "lockfile", f"{label} resolves from registry host {host}"))
                if kind in {"registry", "tarball"} and not record["integrity"]:
                    findings.append(cw_scan.finding("missing-integrity", "integrity", "Important", lock_path.name, None,
                                                    "lockfile", f"{label} has no integrity hash"))
            for item in drift:
                findings.append(cw_scan.finding("lock-drift", "lock-drift", "Important", lock_path.name, None, "lockfile",
                                                f"{item['name']} ({item['section']}): {item['issue']}"))

    queryable = [item for item in packages if item["source"] == "registry" and isinstance(item["version"], str)]
    queries = sorted({(str(item["name"]), str(item["version"])) for item in queryable})
    advisories: dict[str, list[str]] = {}
    if args.emit_osv_query:
        payload = {"queries": [{"package": {"name": name, "ecosystem": "npm"}, "version": version} for name, version in queries]}
        Path(args.emit_osv_query).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    if measured:
        families = {str(item["family"]) for item in findings}
        for check in ("install-script", "resolution-source", "integrity", "lock-drift"):
            coverage[check] = cw_scan.coverage("flagged" if check in families else "clear")
        if args.osv_results:
            try:
                results = json.loads(Path(args.osv_results).read_text(encoding="utf-8")).get("results")
            except (OSError, json.JSONDecodeError, AttributeError) as exc:
                print(f"error: advisory results are not readable: {exc}", file=sys.stderr)
                return 2
            if not isinstance(results, list) or len(results) != len(queries):
                coverage["advisories"] = cw_scan.coverage(
                    "not checked", "advisory results do not match the current query payload; regenerate and resend it")
            else:
                for (name, version), result in zip(queries, results):
                    vulns = result.get("vulns", []) if isinstance(result, dict) else []
                    ids = sorted(str(item.get("id")) for item in vulns if isinstance(item, dict) and item.get("id"))
                    if ids:
                        advisories[f"{name}@{version}"] = ids
                        findings.append(cw_scan.finding("known-advisory", "advisories", "Important", "advisory results",
                                                        None, "external", f"{name}@{version}: {', '.join(ids)}"))
                coverage["advisories"] = cw_scan.coverage("flagged" if advisories else "clear")
        else:
            coverage["advisories"] = cw_scan.coverage(
                "not checked",
                "no advisory lookup; sending the repository's package list outside requires the user's authorization",
            )

    counts = {check: {"flagged": sum(1 for f in findings if f["family"] == check)} for check in CHECKS}
    report = cw_scan.envelope(
        TOOL,
        {"root": root.resolve().name, "lockfile": lock_path.name if lock_path else None, "lockfile_version": lock_version},
        summary={
            "packages": len(packages),
            "direct": sum(1 for item in packages if item["direct"]),
            "transitive": sum(1 for item in packages if not item["direct"] and item["source"] != "workspace"),
            "install_scripts": sum(1 for item in packages if item["install_script"]),
            "queryable_for_advisories": len(queries),
            "findings": {severity: sum(1 for f in findings if f["severity"] == severity) for severity in cw_scan.SEVERITIES},
            "flagged_by_check": {check: counts[check]["flagged"] for check in CHECKS},
            "measured": measured,
        },
        coverage=coverage,
        findings=findings,
        drift=drift,
        advisories=advisories,
        unsupported=unsupported,
        packages=packages,
        executed=False,
        network=False,
    )
    cw_scan.emit(report, args.output)
    if not measured:
        return 2
    return 1 if any(item["severity"] in {"Blocker", "Important"} for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
