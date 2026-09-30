"""Index GitHub Actions workflows and local actions for CI trust review, without running anything.

A line- and indentation-based locator, not a YAML implementation: it records
triggers, permissions, jobs, steps, `uses:` references with pin status, every
`${{ }}` expression with its location and taint class, checkouts, artifacts,
runners, and local or remote call edges, then lists candidate source-to-sink
locations for a reviewer to confirm. Regions using YAML features it does not
index (anchors, aliases, merge keys, flow mappings, multiple documents, tabs)
are reported as unparsed instead of guessed. Emits JSON. Exit codes: 0 no
candidates and nothing unparsed; 1 candidates found; 2 usage error or
incomplete indexing.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "references", _HERE.parents[2] / "references"):
    if (_candidate / "cw_scan.py").is_file():
        sys.path.insert(0, str(_candidate))
        break
import cw_scan  # noqa: E402


TOOL = "ci-trust-review/workflow_index"
SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "vendor", "dist", "build", "target"})
OUTSIDER_TRIGGERS = frozenset(
    {"pull_request", "pull_request_target", "issue_comment", "issues", "discussion", "discussion_comment",
     "pull_request_review", "pull_request_review_comment", "workflow_run", "fork", "watch"}
)
PRIVILEGED_OUTSIDER_TRIGGERS = OUTSIDER_TRIGGERS - {"pull_request"}
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}")
ATTACKER_CONTEXT = re.compile(
    r"github\.event\.(?:issue\.(?:title|body)|pull_request\.(?:title|body|head\.(?:ref|label)|head\.repo\.(?:name|full_name|description))"
    r"|comment\.body|review\.body|review_comment\.body|discussion\.(?:title|body)|pages\b.*page_name"
    r"|commits\b.*(?:message|author)|head_commit\.(?:message|author)"
    r"|workflow_run\.(?:head_branch|display_title|head_commit\.(?:message|author))"
    r"|(?:issue|pull_request)\.labels)|github\.head_ref"
)
CALLER_CONTEXT = re.compile(r"\b(?:inputs|github\.event\.inputs)\.")
DERIVED_CONTEXT = re.compile(r"\b(?:steps|needs|jobs)\.[A-Za-z0-9_-]+\.outputs\.|\benv\.")
UNTRUSTED_REF = re.compile(
    r"pull_request\.head\.(?:sha|ref)|github\.head_ref|workflow_run\.head_(?:sha|branch)|refs/pull/"
)
AGENT_ACTION = re.compile(r"(?i)(?:claude|anthropic|openai|codex|gemini|copilot|\bllm\b|gpt|aider|ai-agent|coderabbit)")
KEY_LINE = re.compile(r"""^(?P<key>"[^"]+"|'[^']+'|[^\s:#"'][^:#]*?)\s*:(?:\s+(?P<value>.*))?$""")
BLOCK_SCALAR = re.compile(r"^[|>][+-]?\d*$")
SHA_PIN = re.compile(r"@[0-9a-fA-F]{40}$")
UNSUPPORTED = (
    (re.compile(r"^\s*(?:-\s+)?[^#'\"]*?:\s+[&*][A-Za-z_][\w-]*\s*(?:#.*)?$"), "anchor or alias"),
    (re.compile(r"^\s*-\s+\*[A-Za-z_][\w-]*\s*$"), "alias"),
    (re.compile(r"^\s*<<\s*:"), "merge key"),
    (re.compile(r"^\s*(?:-\s+)?[^#'\"]*?:\s+\{"), "flow mapping"),
    (re.compile(r"^\s*-\s+\{"), "flow mapping"),
)


@dataclass
class Step:
    line: int
    index: int
    uses: str | None = None
    with_values: dict[str, str] = field(default_factory=dict)
    run_lines: list[int] = field(default_factory=list)


@dataclass
class Job:
    name: str
    line: int
    runs_on: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    condition: str | None = None
    uses: str | None = None
    secrets_inherit: bool = False
    steps: list[Step] = field(default_factory=list)


def strip_value(value: str | None) -> str:
    if value is None:
        return ""
    value = value.strip()
    if value[:1] in {"'", '"'} and value[-1:] == value[:1] and len(value) > 1:
        return value[1:-1]
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def taint(expression: str) -> str:
    if ATTACKER_CONTEXT.search(expression):
        return "attacker"
    if CALLER_CONTEXT.search(expression):
        return "caller"
    if DERIVED_CONTEXT.search(expression):
        return "derived"
    return "trusted-or-unknown"


class WorkflowFile:
    def __init__(self, relative: str, text: str, kind: str):
        self.relative = relative
        self.kind = kind
        self.lines = text.splitlines()
        self.triggers: list[str] = []
        self.permissions: list[str] = []
        self.jobs: dict[str, Job] = {}
        self.composite_steps: list[Step] = []
        self.expressions: list[dict[str, object]] = []
        self.unparsed: list[dict[str, object]] = []
        self.parse()

    def mark_unparsed(self, line: int, reason: str) -> None:
        self.unparsed.append({"line": line, "reason": reason})

    def parse(self) -> None:
        stack: list[tuple[int, str]] = []
        block: tuple[int, str, list[str], Step | None] | None = None
        step_counts: dict[str, int] = {}
        current_step: Step | None = None
        for number, raw in enumerate(self.lines, start=1):
            if "\t" in raw[: len(raw) - len(raw.lstrip())]:
                self.mark_unparsed(number, "tab indentation")
                continue
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip(" "))
            if block is not None:
                block_indent, block_key, block_path, block_step = block
                if not stripped or indent > block_indent:
                    self.record_expressions(number, raw, block_path, block_key, block_step, in_block=True)
                    continue
                block = None
            if not stripped or stripped.startswith("#"):
                continue
            if stripped in {"---", "..."}:
                if number > 1:
                    self.mark_unparsed(number, "multiple YAML documents")
                continue
            unsupported = next((reason for pattern, reason in UNSUPPORTED if pattern.match(raw)), None)
            if unsupported:
                self.mark_unparsed(number, unsupported)
            is_item = stripped == "-" or stripped.startswith("- ")
            while stack and stack[-1][0] >= indent:
                stack.pop()
            content = stripped
            key_indent = indent
            if is_item:
                path = [name for _, name in stack if name != "-"]
                stack.append((indent, "-"))
                content = stripped[1:].strip()
                key_indent = indent + 2
                current_step = self.start_step(path, number, step_counts) or (
                    current_step if len(path) > 0 and path[-1] != "steps" else None
                )
            path = [name for _, name in stack if name != "-"]
            match = KEY_LINE.match(content) if content else None
            if match is None:
                if content:
                    self.record_list_value(path, strip_value(content), number)
                    self.record_expressions(number, raw, path, path[-1] if path else "", current_step, in_block=False)
                continue
            key = match.group("key").strip().strip("\"'")
            value = match.group("value")
            stack.append((key_indent, key))
            full = [*path, key]
            step = current_step if "steps" in path else None
            if value is not None and BLOCK_SCALAR.match(value.strip()):
                block = (key_indent, key, full, step)
                continue
            clean = strip_value(value)
            self.record_key(full, clean, number, step)
            self.record_expressions(number, raw, full, key, step, in_block=False)

    def start_step(self, path: list[str], number: int, counts: dict[str, int]) -> Step | None:
        if path and path[-1] == "steps":
            owner = "/".join(path[:-1])
            index = counts.get(owner, 0)
            counts[owner] = index + 1
            step = Step(number, index)
            if len(path) >= 3 and path[0] == "jobs":
                job = self.jobs.setdefault(path[1], Job(path[1], number))
                job.steps.append(step)
            elif path[:2] == ["runs", "steps"]:
                self.composite_steps.append(step)
            return step
        return None

    def record_list_value(self, path: list[str], value: str, number: int) -> None:
        if path == ["on"]:
            self.triggers.append(value)
        elif len(path) == 3 and path[0] == "jobs" and path[2] == "runs-on":
            self.jobs.setdefault(path[1], Job(path[1], number)).runs_on.append(value)

    def record_key(self, full: list[str], value: str, number: int, step: Step | None) -> None:
        if full == ["on"] and value:
            self.triggers.extend(item.strip() for item in value.strip("[]").split(",") if item.strip())
        elif len(full) == 2 and full[0] == "on":
            self.triggers.append(full[1])
        elif full[0] == "permissions" and len(full) <= 2 and (value or len(full) == 2):
            self.permissions.append(f"{full[1]}: {value}" if len(full) == 2 else value)
        elif len(full) >= 2 and full[0] == "jobs":
            job = self.jobs.setdefault(full[1], Job(full[1], number))
            if len(full) == 3:
                if full[2] == "runs-on" and value:
                    job.runs_on.extend(item.strip() for item in value.strip("[]").split(",") if item.strip())
                elif full[2] == "if":
                    job.condition = value
                elif full[2] == "uses":
                    job.uses = value
                elif full[2] == "secrets" and value == "inherit":
                    job.secrets_inherit = True
                elif full[2] == "permissions" and value:
                    job.permissions.append(value)
            elif len(full) == 4 and full[2] == "permissions":
                job.permissions.append(f"{full[3]}: {value}")
        if step is not None:
            key = full[-1]
            if key == "uses" and full[-2] == "steps":
                step.uses = value
            elif len(full) >= 2 and full[-2] == "with":
                step.with_values[key] = value
            elif key == "run" and value:
                step.run_lines.append(number)

    def record_expressions(self, number: int, raw: str, path: list[str], key: str, step: Step | None,
                           *, in_block: bool) -> None:
        if in_block and key == "run" and step is not None:
            step.run_lines.append(number)
        for match in EXPRESSION.finditer(raw):
            expression = match.group(1).strip()
            if key == "run":
                location = "run"
            elif key == "script" and len(path) >= 2 and path[-2] == "with":
                location = "script"
            elif "env" in path:
                location = "env"
            elif key == "if":
                location = "condition"
            else:
                location = "other"
            self.expressions.append(
                {"line": number, "expression": cw_scan.excerpt(expression, 160), "location": location,
                 "taint": taint(expression), "path": ".".join(path)}
            )
            if location in {"run", "script"} and step is not None and number not in step.run_lines:
                step.run_lines.append(number)


def resolve_local(root: Path, reference: str) -> tuple[str, str | None]:
    target = reference[2:] if reference.startswith("./") else reference
    candidate = root / target
    if candidate.is_file():
        return "resolved", PurePosixPath(target).as_posix()
    for name in ("action.yml", "action.yaml"):
        if (candidate / name).is_file():
            return "resolved", (PurePosixPath(target) / name).as_posix()
    return "missing", None


def analyse(root: Path, files: list[WorkflowFile]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    candidates: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    hardening: list[dict[str, object]] = []

    def add(rule: str, source: WorkflowFile, line: int, detail: str, reachable: list[str], **extra: object) -> None:
        candidates.append({"rule": rule, "file": source.relative, "line": line, "detail": cw_scan.excerpt(detail, 200),
                           "reachable_triggers": reachable, "evidence_kind": "observed", **extra})

    for source in files:
        triggers = sorted(set(source.triggers))
        outsider = sorted(set(triggers) & OUTSIDER_TRIGGERS)
        privileged = sorted(set(triggers) & PRIVILEGED_OUTSIDER_TRIGGERS)
        for expression in source.expressions:
            if expression["location"] not in {"run", "script"}:
                continue
            line = int(expression["line"])
            if expression["taint"] == "attacker":
                add("attacker-text-in-code", source, line, str(expression["expression"]),
                    outsider if source.kind == "workflow" else ["(caller of this action)"])
            elif expression["taint"] == "caller":
                add("caller-input-in-code", source, line, str(expression["expression"]),
                    triggers if source.kind == "workflow" else ["(caller of this action)"])
            elif expression["taint"] == "derived":
                add("derived-value-in-code", source, line, str(expression["expression"]), outsider)
        for number, raw in enumerate(source.lines, start=1):
            if re.search(r"GITHUB_(?:ENV|OUTPUT|PATH)", raw) and any(
                taint(match.group(1)) in {"attacker", "caller", "derived"} for match in EXPRESSION.finditer(raw)
            ):
                add("untrusted-write-to-environment-file", source, number, raw.strip(), outsider)
        jobs = list(source.jobs.values())
        for job in jobs:
            if any("self-hosted" in label for label in job.runs_on) and outsider:
                add("self-hosted-runner-on-outsider-trigger", source, job.line, f"job {job.name} runs on {job.runs_on}", outsider)
            if job.uses:
                edge_kind = "local" if job.uses.startswith("./") else "remote"
                state, target = resolve_local(root, job.uses) if edge_kind == "local" else ("unresolved", None)
                edges.append({"from": source.relative, "line": job.line, "uses": job.uses, "kind": "reusable-workflow",
                              "state": state, "target": target, "secrets_inherit": job.secrets_inherit})
            if not job.permissions and not source.permissions and source.kind == "workflow":
                hardening.append({"file": source.relative, "job": job.name,
                                  "note": "no explicit permissions; token default is a repository setting"})
        for job_name, steps in [(job.name, job.steps) for job in jobs] + [("(composite)", source.composite_steps)]:
            for index, step in enumerate(steps):
                if not step.uses:
                    continue
                uses = step.uses
                if uses.startswith("./"):
                    state, target = resolve_local(root, uses)
                    edges.append({"from": source.relative, "line": step.line, "uses": uses, "kind": "local-action",
                                  "state": state, "target": target})
                elif uses.startswith("docker://"):
                    edges.append({"from": source.relative, "line": step.line, "uses": uses, "kind": "container",
                                  "state": "unresolved", "target": None})
                else:
                    edges.append({"from": source.relative, "line": step.line, "uses": uses, "kind": "remote-action",
                                  "state": "unresolved", "target": None, "pinned": bool(SHA_PIN.search(uses))})
                    if not SHA_PIN.search(uses):
                        hardening.append({"file": source.relative, "line": step.line,
                                          "note": f"action not pinned to a commit SHA: {uses}"})
                lowered = uses.casefold()
                if lowered.startswith("actions/checkout@"):
                    ref = step.with_values.get("ref", "")
                    later_runs = sum(1 for later in steps[index + 1:] if later.run_lines or later.uses)
                    if UNTRUSTED_REF.search(ref) and privileged:
                        add("untrusted-checkout-in-privileged-context", source, step.line,
                            f"checks out {ref} in job {job_name}; {later_runs} later step(s)", privileged)
                    if step.with_values.get("persist-credentials", "").casefold() != "false":
                        hardening.append({"file": source.relative, "line": step.line,
                                          "note": "checkout keeps credentials in the workspace (persist-credentials not false)"})
                if "download-artifact" in lowered and "workflow_run" in triggers:
                    add("artifact-from-triggering-run", source, step.line, uses, ["workflow_run"])
                if AGENT_ACTION.search(uses) and outsider:
                    add("agent-step-on-outsider-trigger", source, step.line, uses, outsider)
    return candidates, edges, hardening


def main(argv: list[str] | None = None) -> int:
    cw_scan.require_python()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument("--max-files", type=int, default=20000)
    parser.add_argument("--output", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    limits = cw_scan.Limits(max_files=args.max_files)
    walked = cw_scan.walk(root, limits, SKIP_DIRS)
    files: list[WorkflowFile] = []
    for entry in walked.entries:
        if entry.kind != "file":
            continue
        path = PurePosixPath(entry.relative)
        is_workflow = path.parent.as_posix() == ".github/workflows" and path.suffix in {".yml", ".yaml"}
        is_action = path.name in {"action.yml", "action.yaml"}
        if not (is_workflow or is_action):
            continue
        data, truncated = cw_scan.read_bounded(entry.path, limits.max_file_bytes)
        item = WorkflowFile(entry.relative, data.decode("utf-8", errors="replace"), "workflow" if is_workflow else "action")
        if truncated:
            item.mark_unparsed(0, "file larger than the read limit")
        files.append(item)
    candidates, edges, hardening = analyse(root, files)
    unparsed = [{"file": item.relative, **region} for item in files for region in item.unparsed]
    report = cw_scan.envelope(
        TOOL,
        {"root": root.resolve().name},
        files=[
            {"path": item.relative, "kind": item.kind, "triggers": sorted(set(item.triggers)),
             "permissions": item.permissions,
             "jobs": [{"name": job.name, "line": job.line, "runs_on": job.runs_on, "permissions": job.permissions,
                       "if": job.condition, "uses": job.uses, "steps": len(job.steps)} for job in item.jobs.values()],
             "expressions": item.expressions,
             "coverage": cw_scan.coverage("not checked", "unparsed regions; read them manually")
             if item.unparsed else cw_scan.coverage("flagged" if any(c["file"] == item.relative for c in candidates) else "clear")}
            for item in files
        ],
        candidates=candidates,
        edges=edges,
        hardening=hardening,
        unparsed=unparsed,
        summary={"workflows": sum(1 for item in files if item.kind == "workflow"),
                 "actions": sum(1 for item in files if item.kind == "action"), "candidates": len(candidates),
                 "unresolved_edges": sum(1 for edge in edges if edge["state"] != "resolved"),
                 "unparsed_regions": len(unparsed), "limits_reached": walked.limits_reached},
        executed=False,
    )
    cw_scan.emit(report, args.output)
    if candidates:
        return 1
    return 2 if unparsed or walked.limits_reached else 0


if __name__ == "__main__":
    raise SystemExit(main())
