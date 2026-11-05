---
# TODO: Write the YAML frontmatter for this command. It must include:
#
#   description:   one line, ≥10 characters, naming what the command does
#   argument-hint: short description of how to pass a target (PR ref, diff range, or file path)
#   allowed-tools: a list of READ-ORIENTED tools only — no Edit, Write, NotebookEdit, or
#                  unrestricted Bash.
#
# Granular Bash sub-command allowlisting is the canonical pattern. For example:
#   - Bash(git diff:*)
#   - Bash(git log:*)
#   - Bash(gh pr view:*)
# This lets you allow READ operations on git without unlocking the full shell. The
# command should be able to run `git diff`, `git log`, `gh pr view`, `gh pr checks`,
# etc. — but NOT `git push`, `git commit`, or arbitrary `Bash(...)`.
---

# /review — team PR review

You are reviewing the diff identified by `$ARGUMENTS` against this repository's conventions. Apply the path-scoped rules in `.claude/rules/` (they auto-load based on the files touched) and the shared standards in `.claude/standards/`.

## Phase 1 — Interview pattern

<!--
TODO: Write the interview-pattern subsection. The reviewer agent should ask clarifying
      questions BEFORE reporting findings whenever the author's intent is ambiguous.

      Why this matters (and why it's not obvious on first read): without an interview
      step, the reviewer commits to a confidently-wrong verdict on ambiguous changes —
      e.g. a refactor that touched no test files. The author then has to argue against
      a "no test coverage" finding when the behavior was already covered upstream. The
      interview pattern asks first.

      Name at least three concrete trigger conditions where the reviewer should
      interview rather than report. Suggested triggers:
        - dependency changes (package.json or pyproject.toml diffs)
        - public API response shape changes or DB column changes
        - refactors with no corresponding test changes
        - changes that touch multiple surfaces (API + components + DB) at once
-->

## Phase 2 — Review criteria

<!--
TODO: Write the explicit must-report vs. skip taxonomy. The point of explicit criteria
      (vs vague "be thorough" instructions) is that two teammates running this command
      on the same PR should reach the same verdict.

      Must report: at minimum, name categories for bugs (logic errors, missing await,
      race conditions, off-by-one), security (raw SQL with user input, missing auth,
      secrets in code, dangerouslySetInnerHTML), convention violations the path-scoped
      rules catch, breaking changes, and migration safety.

      Skip: at minimum, name categories the reviewer should NOT block on — minor
      formatting (Prettier handles it), naming bikeshed when the name is fine, personal
      stylistic preferences not encoded in rules/standards, and TODOs that already have
      tracked tickets.

      The skip list is what keeps false positives from destroying author trust.
-->

## Phase 3 — Bundling: interacting vs. independent findings

<!--
TODO: Write the bundling guidance. The contrast is hard to internalize without a
      concrete pair of examples (which you'll write in the Examples section below).

      Interacting findings: those that overlap or affect the same fix. Bundle into
      ONE detailed message with all context. Example: a missing `await` and a missing
      transaction wrapper on the same function — the author needs to see them together
      because the fix changes both lines.

      Independent findings: separate functions, separate files, no shared fix. Report
      SEQUENTIALLY as discrete items so each piece of feedback is actionable.

      Give a one-line heuristic for telling them apart (e.g. "if fixing A changes the
      code B references, they are interacting").
-->

## Phase 4 — Output format

For each finding, produce:

```
[severity] path/to/file.ts:line
finding: <one-sentence description>
fix: <one-sentence recommendation>
```

Severity is `bug` | `security` | `convention` | `breaking`. End with a one-line verdict: `approve`, `comment`, or `request-changes`.

## Examples

<!--
TODO: Write at least TWO concrete input/output examples using the format above.

Examples are the difference between a command that produces
consistent output across team members and one that produces wildly varying output.

Example 1 — INDEPENDENT findings. Show a diff with two unrelated convention
violations on the same file (e.g. a handler returning a `{ status: 404 }` shape
instead of throwing ApiError, AND a raw SQL call that bypasses the repository
layer). Report each as a separate `[convention]` finding. End with a verdict.

Example 2 — INTERACTING findings. Show a diff where multiple problems share a
single fix (e.g. a refundOrder handler that has missing awaits AND no transaction
wrapper AND wrong ordering between paymentService and DB writes). Bundle them
into ONE `[bug]` finding that lists the three issues together because the fix
changes the same three lines. End with a verdict.
-->

## Notes

- This command is project-scoped (`.claude/commands/review.md`) so everyone on the team gets the same review. If you want to layer personal preferences (e.g. a stricter accessibility check on your own PRs), put a `~/.claude/commands/review-strict.md` in your home directory — it will not affect teammates.
- If a finding requires running code or modifying files to verify, ask the author to run a specific check rather than attempting it from the review session. This command's `allowed-tools` are read-only by design.
