# Routing Evaluations

The routing evaluation set checks whether the installed `coding-workflows`
plugin activates the intended skill, avoids unrelated skills, and respects each
workflow's boundary.

The source set is
`plugins/coding-workflows/evals/trigger-routing.json`. Every skill has one
direct case, two indirect cases, three negative cases, and one edge case. Case
IDs are stable so results remain comparable between revisions.

## Free Dry Run

Preview every case without calling a model or writing a report:

```powershell
python scripts\routing_evals.py
```

Filter by skill or case:

```powershell
python scripts\routing_evals.py --skill repo-xray
python scripts\routing_evals.py --case repo-xray-edge-1
```

Dry-run mode is the default. It does not require the plugin to be installed.

## Optional Model-Backed Run

A live run requires the plugin to be installed and enabled in the active Codex
profile. Confirm discovery before installing:

```powershell
codex plugin list --marketplace coding-agents --available --json
codex plugin add coding-workflows@coding-agents
```

Start a new Codex session after installation, then run a small selected set:

```powershell
python scripts\routing_evals.py `
  --run `
  --acknowledge-cost `
  --skill repo-xray
```

`--run` is intentionally insufficient by itself. `--acknowledge-cost` confirms
that model-backed evaluation may consume quota or incur API cost. Use `--model`
only when comparing a deliberate model target; omission preserves the active
Codex default.

Each case runs in a fresh ephemeral, read-only Codex session. Reports are
written under `.artifacts/routing-evals/`, which Git ignores.

## Review Policy

The runner records the skill the model says it applied, whether that declaration
matches the golden expectation, its answer, and its stated boundary evidence.
Those fields remain `unreviewed` until a person inspects the response against
`expected_behavior`.

A successful process exit proves only that the selected cases executed and
produced valid structured output. It does not convert model self-report into an
automatic behavioral pass. Required CI therefore validates the corpus and the
runner deterministically but does not make paid model calls.
