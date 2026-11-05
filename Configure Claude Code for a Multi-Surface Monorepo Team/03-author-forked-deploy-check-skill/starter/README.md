# Starter — Exercise 3

This starter carries everything from Exercise 2's solution plus a starter `.claude/skills/deploy-check/SKILL.md`.

## Files you will edit

- `.claude/skills/deploy-check/SKILL.md` — five TODO blocks:
  1. Frontmatter (`name`, `description`, `context: fork`, `argument-hint` quoted, read-only `allowed-tools`).
  2. "Why this is a skill (not a CLAUDE.md addition)" — the skill-vs-CLAUDE.md rubric.
  3. "Why `context: fork`" — the main-session-isolation rationale plus the Branching-Reality reference.
  4. The three Checks (each with Detect / Pass / Fail).
  5. The Personalization note.

## Run / verify

```bash
source .venv/bin/activate
pytest -q tests/test_us01_claude_md_hierarchy.py tests/test_us02_path_scoped_rules.py tests/test_us03_review_command.py tests/test_us04_deploy_check_skill.py
ecommerce-team-config .
```

Replace each TODO until pytest reports `28 passed` and the CLI prints `OK`.

## Troubleshooting

- **IDE LSP warning on `context: fork` or `allowed-tools`** — the current Claude Code skill-frontmatter LSP (2026-05) hasn't caught up to the current skill-frontmatter schema. The warning is informational, not an error. Proceed.
- **Frontmatter fails to load with a "nested mapping" error** — quote any value containing a colon: `argument-hint: "[target] (defaults to main)"`, not `argument-hint: <target: optional>`.
