"""Tests for the ci-trust-review workflow locator."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import extension_fixtures as fx
from repo_support import ROOT, SKILLS, run_python, temp_dir


INDEXER = SKILLS / "ci-trust-review" / "scripts" / "workflow_index.py"

PWN_REQUEST = """name: build
on:
  pull_request_target:
    types: [opened]
permissions:
  contents: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: npm ci && npm test
"""

TITLE_INJECTION = """on:
  issues:
    types: [opened]
jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - name: echo title
        run: |
          echo "New issue: ${{ github.event.issue.title }}"
      - name: safe
        env:
          TITLE: ${{ github.event.issue.title }}
        run: echo "$TITLE"
      - uses: ./.github/actions/greet
        with:
          who: ${{ github.event.issue.user.login }}
      - uses: example/agent-claude-action@v1
      - uses: some-org/shared/.github/workflows/lint.yml@main
"""

COMPOSITE = """name: greet
runs:
  using: composite
  steps:
    - run: echo "hello ${{ inputs.who }}"
      shell: bash
"""

ARTIFACT = """on:
  workflow_run:
    workflows: [build]
    types: [completed]
jobs:
  report:
    runs-on: [self-hosted, linux]
    steps:
      - uses: actions/download-artifact@v4
      - run: ./report.sh
"""

ANCHORS = """on: push
jobs:
  a:
    runs-on: ubuntu-latest
    steps: &shared
      - run: echo hi
  b:
    runs-on: ubuntu-latest
    steps: *shared
"""


def index(testcase: unittest.TestCase, root: Path) -> tuple[int, dict]:
    result = run_python(INDEXER, str(root))
    testcase.assertIn(result.returncode, {0, 1, 2}, result.stderr)
    return result.returncode, json.loads(result.stdout)


def candidate_rules(report: dict) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {}
    for item in report["candidates"]:
        found.setdefault(item["rule"], []).append(item)
    return found


class WorkflowIndexTests(unittest.TestCase):
    def repo(self, workflows: dict[str, str], actions: dict[str, str] | None = None) -> Path:
        root = temp_dir(self)
        for name, text in workflows.items():
            fx.write(root / ".github" / "workflows" / name, text)
        for path, text in (actions or {}).items():
            fx.write(root / path, text)
        return root

    def test_untrusted_checkout_in_privileged_context_is_a_candidate(self) -> None:
        code, report = index(self, self.repo({"build.yml": PWN_REQUEST}))
        self.assertEqual(1, code)
        hit = candidate_rules(report)["untrusted-checkout-in-privileged-context"][0]
        self.assertEqual(["pull_request_target"], hit["reachable_triggers"])
        self.assertIn("1 later step", hit["detail"])
        self.assertEqual(["contents: write"], report["files"][0]["permissions"])
        notes = {item["note"] for item in report["hardening"]}
        self.assertTrue(any("not pinned" in note for note in notes))
        self.assertTrue(any("persist-credentials" in note for note in notes))

    def test_interpolation_sinks_are_distinguished_from_env_indirection(self) -> None:
        root = self.repo({"triage.yml": TITLE_INJECTION}, {".github/actions/greet/action.yml": COMPOSITE})
        code, report = index(self, root)
        self.assertEqual(1, code)
        found = candidate_rules(report)
        sinks = found["attacker-text-in-code"]
        self.assertEqual([("triage.yml", 10)], [(Path(item["file"]).name, item["line"]) for item in sinks])
        self.assertEqual(["issues"], sinks[0]["reachable_triggers"])
        workflow = next(item for item in report["files"] if item["path"].endswith("triage.yml"))
        env_uses = [e for e in workflow["expressions"] if e["location"] == "env"]
        self.assertEqual("attacker", env_uses[0]["taint"])
        self.assertEqual(13, env_uses[0]["line"])
        self.assertIn("caller-input-in-code", found)
        self.assertEqual(".github/actions/greet/action.yml", found["caller-input-in-code"][0]["file"])
        self.assertIn("agent-step-on-outsider-trigger", found)
        edges = {edge["uses"]: edge for edge in report["edges"]}
        self.assertEqual("resolved", edges["./.github/actions/greet"]["state"])
        self.assertEqual(".github/actions/greet/action.yml", edges["./.github/actions/greet"]["target"])
        self.assertEqual("unresolved", edges["some-org/shared/.github/workflows/lint.yml@main"]["state"])

    def test_artifacts_and_self_hosted_runners_on_outsider_triggers(self) -> None:
        _, report = index(self, self.repo({"report.yml": ARTIFACT}))
        found = candidate_rules(report)
        self.assertIn("artifact-from-triggering-run", found)
        self.assertIn("self-hosted-runner-on-outsider-trigger", found)

    def test_unsupported_yaml_fails_closed(self) -> None:
        code, report = index(self, self.repo({"anchors.yml": ANCHORS}))
        self.assertEqual(2, code)
        reasons = {item["reason"] for item in report["unparsed"]}
        self.assertEqual({"anchor or alias"}, reasons)
        self.assertEqual("not checked", report["files"][0]["coverage"]["state"])

    def test_this_repository_workflows_have_no_candidates(self) -> None:
        code, report = index(self, ROOT)
        self.assertEqual(0, code, report["candidates"])
        self.assertEqual([], report["hardening"])
        self.assertEqual(2, report["summary"]["workflows"])
        for item in report["files"]:
            self.assertEqual(["contents: read"], item["permissions"])
            self.assertNotIn("pull_request_target", item["triggers"])


if __name__ == "__main__":
    unittest.main()
