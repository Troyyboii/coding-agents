"""Tests for the dependency-risk offline npm lockfile inventory."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import extension_fixtures as fx
from repo_support import ROOT, SKILLS, run_python, temp_dir


INVENTORY = SKILLS / "dependency-risk" / "scripts" / "dep_inventory.py"
REGISTRY = "https://registry.npmjs.org"


def lockfile(packages: dict[str, dict], root_deps: dict[str, dict[str, str]], version: int = 3) -> str:
    entries = {"": {"name": "app", "version": "1.0.0", **root_deps}, **packages}
    return json.dumps({"name": "app", "lockfileVersion": version, "requires": True, "packages": entries})


def pkg(name: str, version: str, **extra) -> dict:
    return {"version": version, "resolved": f"{REGISTRY}/{name}/-/{name.split('/')[-1]}-{version}.tgz",
            "integrity": "sha512-" + "A" * 20, **extra}


class DependencyInventoryTests(unittest.TestCase):
    def project(self, packages: dict[str, dict], root_deps: dict, manifest: dict | None = None, *, version: int = 3) -> Path:
        root = temp_dir(self)
        fx.write(root / "package.json", json.dumps(manifest if manifest is not None else {"name": "app", **root_deps}))
        fx.write(root / "package-lock.json", lockfile(packages, root_deps, version))
        return root

    def run_inventory(self, root: Path, *args: str) -> tuple[int, dict]:
        result = run_python(INVENTORY, str(root), *args)
        self.assertIn(result.returncode, {0, 1, 2}, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_direct_transitive_and_hoisting_are_distinguished(self) -> None:
        deps = {"dependencies": {"express": "^4.0.0"}, "devDependencies": {"jest": "^29.0.0"}}
        packages = {
            "node_modules/express": pkg("express", "4.19.2"),
            "node_modules/jest": pkg("jest", "29.7.0", dev=True),
            "node_modules/body-parser": pkg("body-parser", "1.20.2"),
            "node_modules/express/node_modules/debug": pkg("debug", "2.6.9"),
        }
        code, report = self.run_inventory(self.project(packages, deps))
        self.assertEqual(0, code, report["findings"])
        records = {item["location"]: item for item in report["packages"]}
        self.assertTrue(records["node_modules/express"]["direct"])
        self.assertTrue(records["node_modules/jest"]["dev"])
        self.assertFalse(records["node_modules/body-parser"]["direct"], "hoisted transitive package")
        self.assertEqual("debug", records["node_modules/express/node_modules/debug"]["name"])
        self.assertEqual((2, 2), (report["summary"]["direct"], report["summary"]["transitive"]))
        self.assertEqual("clear", report["coverage"]["install-script"]["state"])
        self.assertEqual("not checked", report["coverage"]["advisories"]["state"])
        self.assertIn("authorization", report["coverage"]["advisories"]["reason"])
        self.assertFalse(report["network"])

    def test_risk_signals_are_flagged(self) -> None:
        deps = {"dependencies": {"native": "^1.0.0", "fork": "github:someone/fork", "blob": "https://example.com/b.tgz"}}
        packages = {
            "node_modules/native": pkg("native", "1.0.0", hasInstallScript=True),
            "node_modules/fork": {"version": "0.1.0", "resolved": "git+ssh://git@github.com/someone/fork.git#abc123"},
            "node_modules/blob": {"version": "1.0.0", "resolved": "https://example.com/b.tgz"},
            "node_modules/nohash": {"version": "1.0.0", "resolved": f"{REGISTRY}/nohash/-/nohash-1.0.0.tgz"},
            "packages/local": {"version": "0.0.1"},
            "node_modules/local": {"resolved": "packages/local", "link": True},
        }
        code, report = self.run_inventory(self.project(packages, deps))
        self.assertEqual(1, code)
        rules = {(item["rule"], item["detail"].split(" ")[0]) for item in report["findings"]}
        for expected in (("install-script", "native@1.0.0"), ("git-source", "fork@0.1.0"),
                         ("tarball-source", "blob@1.0.0"), ("missing-integrity", "blob@1.0.0"),
                         ("missing-integrity", "nohash@1.0.0")):
            with self.subTest(expected=expected):
                self.assertIn(expected, rules)
        sources = {item["location"]: item["source"] for item in report["packages"]}
        self.assertEqual(("workspace", "link"), (sources["packages/local"], sources["node_modules/local"]))

    def test_lock_drift_both_directions(self) -> None:
        manifest = {"name": "app", "dependencies": {"a": "^2.0.0", "c": "^1.0.0"}}
        deps = {"dependencies": {"a": "^1.0.0", "b": "^1.0.0"}}
        code, report = self.run_inventory(self.project({"node_modules/a": pkg("a", "1.0.0")}, deps, manifest))
        self.assertEqual(1, code)
        issues = {(item["name"], item["issue"].split(":")[0]) for item in report["drift"]}
        self.assertEqual({("c", "declared in package.json but not in the lockfile"),
                          ("b", "in the lockfile root but not in package.json"), ("a", "range differs")}, issues)

    def test_nothing_measured_is_never_a_pass(self) -> None:
        empty = temp_dir(self)
        code, report = self.run_inventory(empty)
        self.assertEqual(2, code)
        self.assertEqual({"not checked"}, {item["state"] for item in report["coverage"].values()})
        no_lock = temp_dir(self)
        fx.write(no_lock / "package.json", '{"dependencies": {"a": "1"}}')
        code, report = self.run_inventory(no_lock)
        self.assertEqual(2, code)
        self.assertEqual("blocked", report["coverage"]["install-script"]["state"])
        old = self.project({}, {"dependencies": {}}, version=1)
        (old / "package-lock.json").write_text('{"lockfileVersion": 1, "dependencies": {}}', encoding="utf-8")
        code, report = self.run_inventory(old)
        self.assertEqual(2, code)
        self.assertIn("lockfileVersion 1", report["coverage"]["integrity"]["reason"])

    def test_unsupported_ecosystems_are_listed(self) -> None:
        root = self.project({}, {"dependencies": {}})
        fx.write(root / "requirements.txt", "requests==2.0\n")
        fx.write(root / "yarn.lock", "# yarn\n")
        fx.write(root / "packages" / "web" / "package.json", "{}")
        _, report = self.run_inventory(root)
        listed = {item["path"]: item["ecosystem"] for item in report["unsupported"]}
        self.assertEqual({"requirements.txt": "Python", "yarn.lock": "npm (yarn lockfile)",
                          "packages/web/package.json": "npm (nested package)"}, listed)

    def test_advisory_payload_and_ingest(self) -> None:
        deps = {"dependencies": {"a": "^1.0.0", "b": "^1.0.0"}}
        root = self.project({"node_modules/a": pkg("a", "1.0.0"), "node_modules/b": pkg("b", "2.0.0"),
                             "packages/w": {"version": "0.1.0"}}, deps)
        out = temp_dir(self)
        code, _ = self.run_inventory(root, "--emit-osv-query", str(out / "q.json"))
        payload = json.loads((out / "q.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {"queries": [{"package": {"name": "a", "ecosystem": "npm"}, "version": "1.0.0"},
                         {"package": {"name": "b", "ecosystem": "npm"}, "version": "2.0.0"}]}, payload)
        fx.write(out / "r.json", json.dumps({"results": [{"vulns": [{"id": "GHSA-xxxx-yyyy-zzzz"}]}, {}]}))
        code, report = self.run_inventory(root, "--osv-results", str(out / "r.json"))
        self.assertEqual(1, code)
        self.assertEqual({"a@1.0.0": ["GHSA-xxxx-yyyy-zzzz"]}, report["advisories"])
        self.assertEqual("flagged", report["coverage"]["advisories"]["state"])
        fx.write(out / "bad.json", json.dumps({"results": [{}]}))
        _, report = self.run_inventory(root, "--osv-results", str(out / "bad.json"))
        self.assertEqual("not checked", report["coverage"]["advisories"]["state"])

    def test_npmrc_credentials_are_reported_without_values(self) -> None:
        root = self.project({}, {"dependencies": {}})
        secret = "npm" + "_" + "Q" * 36
        fx.write(root / ".npmrc", f"//registry.npmjs.org/:_authToken={secret}\n//other/:_authToken=${{NPM_TOKEN}}\n")
        result = run_python(INVENTORY, str(root))
        self.assertNotIn(secret, result.stdout)
        report = json.loads(result.stdout)
        hits = [item for item in report["findings"] if item["rule"] == "npmrc-credential"]
        self.assertEqual([1], [item["line"] for item in hits])

    def test_this_repository_has_no_supported_manifest(self) -> None:
        code, report = self.run_inventory(ROOT)
        self.assertEqual(2, code)
        self.assertFalse(report["summary"]["measured"])


if __name__ == "__main__":
    unittest.main()
