"""Structural tests for the instruction-only spec-trace contract."""

from __future__ import annotations

import json
import re
import unittest

from repo_support import SKILLS


VERDICTS = ["satisfied", "partial", "contradicted", "not found in the inspected scope", "blocked", "not checked"]


class TraceMatrixContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = (SKILLS / "spec-trace" / "references" / "trace-matrix.md").read_text(encoding="utf-8")
        self.skill = (SKILLS / "spec-trace" / "SKILL.md").read_text(encoding="utf-8")

    def schema(self) -> dict:
        block = re.search(r"```json\n(.*?)\n```", self.reference, re.DOTALL)
        self.assertIsNotNone(block)
        return json.loads(block.group(1))

    def test_spec_trace_matrix_schema_is_valid_json_with_shared_verdicts(self) -> None:
        schema = self.schema()
        requirement = schema["properties"]["requirements"]["items"]
        self.assertEqual(VERDICTS, requirement["properties"]["verdict"]["enum"])
        self.assertEqual(
            ["observed", "executed", "inferred", "unverified"], requirement["properties"]["evidence_kind"]["enum"]
        )
        self.assertIn("absence_criterion", requirement["required"])
        self.assertIn("search", requirement["required"])

    def test_skill_and_reference_use_the_same_verdicts_and_no_retired_terms(self) -> None:
        for verdict in VERDICTS:
            self.assertIn(f"`{verdict}`", self.skill.replace("`not found in the\n   inspected scope`", "`not found in the inspected scope`"))
        for retired in ("unassessable", "cannot-assess", "cannot assess", "inconclusive"):
            self.assertNotIn(retired, self.skill + self.reference)


if __name__ == "__main__":
    unittest.main()
