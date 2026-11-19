---
name: deploy-check
description: Run read-only pre-deployment validation in a forked sub-agent and report a single pass/fail summary back to the main session
context: fork
argument-hint: "[target-branch] (defaults to main)"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git rev-parse:*)
  - Bash(git ls-files:*)
  - Bash(gh pr view:*)
  - Bash(gh pr checks:*)
---

# /deploy-check

Runs the team's pre-deployment validation checklist against the current working tree and the branch you're about to ship. Read-only by design — this skill never modifies files, never pushes, never deploys. It returns a single structured summary so the calling session can decide whether to proceed.

## Why this is a skill (not a CLAUDE.md addition)

`/deploy-check` is **on-demand and task-specific**: you only need it right before a deploy, and it produces verbose intermediate output (file enumeration, diff parsing, check execution traces) that has no value once the summary is known. That makes it a good fit for a skill — invoked when needed, running in a forked context.

The opposite shape — always-loaded, universal guidance like "tests are co-located with source" or "throw `ApiError` for validation failures" — belongs in `CLAUDE.md` or `.claude/standards/`. Those need to be present in every session, not gated behind an invocation. Rule of thumb: **on-demand, forked, task-specific → skill; always-loaded, universal → CLAUDE.md**.

## Why `context: fork`

The goal of the fork is to keep the verbose discovery output **out of the main session**. A deploy check walks the working tree, inspects diffs, and runs several enumeration passes — none of that intermediate output has any value to the calling session once we know whether to ship. By running in a forked sub-agent, only the structured summary returns to the main conversation; the megabytes of file lists and `git status` output stay in the fork.

`context: fork` is a Claude Code product feature operating at the skill-invocation layer. Conceptually it is analogous to the **Branching Reality** pattern — establish a foundational analysis, then branch into isolated explorations whose outputs do not contaminate the parent. Session-level forking (`fork_session`) applies that pattern to a whole session; `context: fork` is the skill-spec equivalent.

## Checks

Run all three. Each check produces a pass-or-fail verdict; if any fails, the overall summary is **fail**.

### 1. Uncommitted changes

- **Detect:** run `git status --porcelain`. Empty output means the working tree is clean.
- **Pass:** working tree has no staged, unstaged, or untracked files.
- **Fail:** any file shows up in `git status --porcelain`. List the first 10 paths in the summary so the author knows what to commit or stash.

### 2. Migrations up-to-date with code

- **Detect:** glob `src/db/migrations/*.sql` for the highest sequence number, then `grep -R "from \"src/db/.*\"" src/api/` for repository imports added in the diff since the target branch. If any new repository module is imported but no migration file's sequence ≥ the previous highest, that's a fail. Also check `git diff <target>..HEAD --name-only` for any `src/db/types.ts` change without a corresponding `src/db/migrations/` change.
- **Pass:** every new repository function or type change is backed by a migration file in this branch.
- **Fail:** code references a column or table that doesn't exist in any committed migration. Report the orphaned reference and the missing migration name.

### 3. CI checks green on the open PR

- **Detect:** if a PR exists for this branch (`gh pr view --json number,state,statusCheckRollup`), inspect the latest `statusCheckRollup`. Otherwise note "no PR open" and skip.
- **Pass:** all required checks have status `SUCCESS`.
- **Fail:** any required check is `FAILURE`, `CANCELLED`, or still `PENDING` when the PR is marked ready-for-review. Report the failing check names and link to the run.

## Output format

Return exactly this shape to the main session:

```
verdict: pass | fail
checks:
  - name: uncommitted-changes
    status: pass | fail
    detail: <one line or empty>
  - name: migrations
    status: pass | fail
    detail: <one line or empty>
  - name: ci
    status: pass | fail | skipped
    detail: <one line or empty>
```

Do not include the raw `git status`, raw diff hunks, or full check logs in the returned summary — those stay in the fork. If the author wants to investigate a failed check, they can re-invoke the skill targeting that single check or run the underlying command themselves.

## Personalization

This skill is project-scoped (`.claude/skills/deploy-check/`) so the whole team gets the same checks. If you want a stricter personal variant — say, you want to additionally fail when the diff exceeds 500 lines without a PR description longer than 200 chars — create a parallel skill in `~/.claude/skills/deploy-check-strict/` with a different name. Your variant will not affect teammates and will not be committed to the repo.

## What this skill deliberately does not do

- It never pushes, deploys, or runs migrations. The `allowed-tools` allowlist is read-only by construction; even if a future maintainer adds `Write` here, the team's `/review` command should catch the change.
- It does not run the test suite. Tests have their own pre-merge gate in CI; duplicating that here would slow every deploy check without adding signal.
- It does not check for secrets in code. That's the job of the `gitleaks` pre-commit hook, which fails the commit, not the deploy.
