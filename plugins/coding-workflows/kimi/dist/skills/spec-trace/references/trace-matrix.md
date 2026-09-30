# Trace Matrix Contract

One row per requirement, plus one row per material implemented behavior found in
the reverse pass. Present it as a table for people or as JSON matching the
schema below when another tool or workflow consumes it.

## Requirement rows

| Field | Rule |
| --- | --- |
| `id` | The specification's own identifier when it has one; otherwise `R-<section>-<n>`, stable across reruns. |
| `source` | Exact location: file and line, or URL with anchor, plus the specification version or date. |
| `quote` | At most two lines of the requirement text, quoted exactly. |
| `strength` | `must`, `should`, or `may` (normative keywords per RFC 2119, or the specification's own equivalent). |
| `absence_criterion` | Written before searching: what code, test, or configuration would exist if this were implemented, and where. |
| `search` | Terms, symbols, and paths actually searched. |
| `implementation` | File and line evidence, or empty. |
| `enforcement` | Test, runtime check, or schema that enforces it, or empty. |
| `verdict` | See below. |
| `evidence_kind` | `observed`, `executed`, `inferred`, or `unverified`, from the shared evidence contract. |
| `note` | Why the verdict follows, in one or two sentences. |

## Verdicts

| Verdict | Use when |
| --- | --- |
| `satisfied` | Implementation evidence matches the requirement; say whether enforcement evidence exists. |
| `partial` | Some required behavior exists and some is missing or narrower. |
| `contradicted` | The implementation does something the requirement forbids or requires otherwise. |
| `not found in the inspected scope` | The absence criterion was searched for, with the search recorded, and nothing matched. |
| `blocked` | A named prerequisite prevented assessment, such as missing access, a generated or external component, or dynamic dispatch that cannot be traced. |
| `not checked` | Outside the requested scope or not reached; say why. |

`not found in the inspected scope` is never a universal negative, and never a
verdict without a recorded search. Code presence without enforcement is still
`satisfied` or `partial`; record the missing enforcement in `note`.

## Reverse-pass rows

For each material implemented behavior in scope (public entry point, endpoint,
flag, error code, configuration key), record `behavior`, `location`, and one
classification: `documented` (cite the requirement), `extension` (compatible
addition), `divergent` (conflicts with the specification or its intent), or
`internal` (not part of the specified surface).

## JSON schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["specification", "scope", "requirements", "reverse", "coverage"],
  "properties": {
    "specification": {
      "type": "object",
      "required": ["source", "version"],
      "properties": {
        "source": {"type": "string"},
        "version": {"type": "string"},
        "precedence": {"type": "string"}
      }
    },
    "scope": {"type": "string"},
    "requirements": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "source", "quote", "strength", "absence_criterion", "search", "verdict", "evidence_kind"],
        "properties": {
          "id": {"type": "string"},
          "source": {"type": "string"},
          "quote": {"type": "string"},
          "strength": {"enum": ["must", "should", "may"]},
          "absence_criterion": {"type": "string"},
          "search": {"type": "array", "items": {"type": "string"}},
          "implementation": {"type": "array", "items": {"type": "string"}},
          "enforcement": {"type": "array", "items": {"type": "string"}},
          "verdict": {
            "enum": ["satisfied", "partial", "contradicted", "not found in the inspected scope", "blocked", "not checked"]
          },
          "evidence_kind": {"enum": ["observed", "executed", "inferred", "unverified"]},
          "note": {"type": "string"}
        }
      }
    },
    "reverse": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["behavior", "location", "classification"],
        "properties": {
          "behavior": {"type": "string"},
          "location": {"type": "string"},
          "classification": {"enum": ["documented", "extension", "divergent", "internal"]},
          "requirement": {"type": "string"}
        }
      }
    },
    "coverage": {
      "type": "object",
      "required": ["requirements_total", "assessed"],
      "properties": {
        "requirements_total": {"type": "integer"},
        "assessed": {"type": "integer"},
        "not_assessed_reason": {"type": "string"}
      }
    }
  }
}
```
