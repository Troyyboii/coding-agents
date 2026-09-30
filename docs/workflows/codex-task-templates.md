# Codex Task Templates

Paste-ready prompts for small, controlled repo work.

## Inspect Only

```text
Inspect the current repo. Do not edit anything.

Goal:
<what to evaluate>

Check:
- <files or folders>

Report:
1. What you found.
2. Risks or unclear areas.
3. Exactly 3 tiny reversible next steps.

Do not edit.
Do not move files.
Do not commit.
```

## Docs-Only Edit

```text
Make a small documentation-only improvement.

Objective:
<specific doc outcome>

Scope:
- <files to create or edit>

Rules:
- Do not change code.
- Do not move files.
- Keep edits concise and practical.
- Do not commit.

After editing:
1. Run git status.
2. Show git diff --stat.
3. Show the full relevant diff.
4. Stop and wait for approval before commit.
```

## Diff Review

```text
Review the current diff. Do not edit anything.

Focus on:
- unintended files
- content changes outside scope
- formatting or line-ending churn
- generated files
- missing docs or tests

Report findings first, ordered by severity.
If there are no issues, say so clearly.
Do not commit.
```

## Secret Scan

```text
Scan the repo for likely secrets. Do not edit anything.

Check for:
- API keys and tokens
- private keys
- credential files
- accidental .env files
- hardcoded passwords

Report likely findings with file path, line number if available, type of possible secret, whether it is tracked or untracked if available, and why it looks sensitive.
Do not print full secret values.
Do not delete or rewrite files.
Do not commit.
```

## No-Commit Reminder

```text
Do the requested work, but do not commit.

Before stopping:
1. Run git status.
2. Show git diff --stat.
3. Show the full relevant diff.
4. Wait for my explicit approval before any commit.
```
