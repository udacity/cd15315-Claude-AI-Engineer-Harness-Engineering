# Reflection Brief — Harness Engineering Capstone

**Name:** Capstone submission
**Date:** 2026-11-19

**Environment**

- Model(s): `claude-haiku-4-5-20251001` ran Claims Intake and the configured Claude backend ran Retail Context. System 4 used a recorded response fixture, not a live model call.
- OS / Python: Vocareum Linux; Python 3.10.14; pytest 9.2.0.
- Approx. API spend: System 1 reports an estimated **$0.1240** in `evidence/system-1/summary-20261119_111636.md`. No separate System 2 spend total was captured.

---

## Part 1 — Per-system

### System 1 — Agentic loop

1. **Loop control.** Quote the `stop_reason` sequence from one trace. Name the file and function that decides continue-vs-stop, and how.
   → In `evidence/system-1/traces-20261119_111636/claim_04_neighbor_injury.jsonl`, the observed sequence is `tool_use -> tool_use -> tool_use -> tool_use -> end_turn`. The decision is in `claims_intake/loop.py` in `run()`: `tool_use` appends tool results and continues; `end_turn` returns `FinalState`; every other value raises `UnexpectedStopReason`. The live run processed 8 claims and is summarized in `evidence/system-1/run-output-vocareum.txt`.

2. **Anti-pattern.** Name one anti-pattern `test_antipatterns.py` checks for. What would break in your run if the loop used it?
   → The static audit rejects an integer-literal iteration cap in `test_antipatterns.py`. A fixed cap could stop a claim before `end_turn` or continue after a terminal result instead of honoring the model's stop reason. The suite's 30 local tests previously passed, and the live trace confirms that actual termination came from `end_turn`, not a turn-count heuristic.

3. **Tool design.** Pick two tools with overlapping inputs. How do the descriptions prevent misrouting? What did a structured tool error let the agent do that a generic string would not?
   → `classify_claim` commits to a claim type, while `assess_severity` commits to a severity bucket; their descriptions separate when they are called and their schemas require different enum fields in `claims_intake/tools.py`. The live liability trace calls both once in turn 3 before routing. Structured errors use `is_error`, `error_category`, `is_retryable`, and `message`, allowing the caller to distinguish retryable failures from permanent or validation failures rather than inferring meaning from prose.

4. **Your numbers.** Quote the turn count and cost for one claim. How does it differ from the README sample, and why?
   → Claim `claim_04_neighbor_injury` used 5 turns, 17,823 input tokens, 950 output tokens, and an estimated `$0.0226`, shown in `evidence/system-1/summary-20261119_111636.md`. The complete run estimated `$0.1240` for 8 claims. Live counts differ from README examples because each claim performs a different sequence of tools and may follow a different terminal path; in this run, claims 1–3 escalated unexpectedly instead of routing.

### System 2 — Context strategy

5. **The reduction.** From `budget.json`: baseline tokens, assembled tokens, reduction %. Which section dominates the assembled context, and why keep it verbatim?
   → `evidence/system-2/budget.json` records 38,708 baseline tokens, 16,825 assembled tokens, and a 56.53% reduction. The active section dominates at 15,789 tokens. It is kept verbatim because Turn 48 of a live issue can contain decision-critical details; resolved refund and subscription histories can be compressed.

6. **Summarize vs preserve.** State the rule for what gets summarized vs kept byte-exact, citing your per-section token numbers.
   → The rule is to summarize resolved issues and preserve the live active issue. `budget.json` gives 204 tokens for `case_facts`, 388 for `resolved_refund`, 462 for `resolved_subscription`, and 15,789 for `active`. The 12-field facts block and stabilized resolved summaries carry durable facts, while active turn-by-turn context remains byte-exact.

7. **Facts block.** Compare `eval.jsonl` to `eval_control.jsonl`. Which question regressed, and what does that prove?
   → The full eval in `evidence/system-2/eval.jsonl` passed 6/6. In `evidence/system-2/eval_control.jsonl`, Q1 held at `$22.14` but Q6 failed and returned `unknown`, with the run log showing control 1/2 regressed. This proves the structured facts block carries load-bearing status information that is not reliably recoverable after it is stripped. Note that Q5's evaluator result says “received,” but this is not independently proven by the evidence excerpt as a receipt event.

### System 3 — Claude Code config

8. **Path-scoped rules.** Quote the glob frontmatter from one rule file. Why is it better than a directory-level CLAUDE.md for cross-cutting conventions?
   → In `.claude/rules/react.md`, the frontmatter is:
   ```yaml
   paths:
     - "src/components/**/*"
     - "src/pages/**/*"
   ```
   Path-scoped activation keeps React rules loaded only while matching files are involved, rather than adding directory conventions globally. The inventory is in `evidence/system-3/claude-config-tree-vocareum.txt`, and the suite passed 35 tests in `evidence/system-3/pytest-vocareum.txt`.

9. **Forked skill.** Quote the `context: fork` and `allowed-tools` lines. What does running forked + read-only buy you? What breaks without it?
   → The skill frontmatter in `.claude/skills/deploy-check/SKILL.md` contains `context: fork` and `allowed-tools:` with read-only entries including `Read`, `Grep`, `Glob`, and `Bash(git status:*)`. Forking keeps verbose discovery outside the main conversation, while read-only allowlisting prevents writes or deployment. Without the fork, raw inspection output pollutes the main session; without the allowlist, a future change could mutate or ship code during a supposedly read-only check.

10. **Scope.** From the validator output: project-level vs user-level scope. Give one example of each from this config.
    → The project-level example is repository `CLAUDE.md`, which imports `.claude/standards/*.md` and is shared through version control. The user-level example is `~/.claude/CLAUDE.md`, documented in the project `CLAUDE.md` as personal and outside repository version control. `evidence/system-3/validator-output-vocareum.txt` contains `OK`, and the complete file inventory is in `evidence/system-3/claude-config-tree-vocareum.txt`.

### System 4 — Orchestration

11. **Push work down.** Defects the SQL query returned vs warm-tier total. Name the indexed query. Why does the model never see the full history?
    → The warm fixture has 40 defect rows; using `defects_since("2026-04-01T00:00:00Z", limit=50)`, the SQL slice returned 17 rows. The indexed query is `SELECT * FROM defects WHERE ts > ? ORDER BY ts DESC LIMIT ?`, backed by `idx_defects_ts`. The run used the seeded `warm-april-fixture.sqlite` and is recorded in `evidence/system-4/shift-run-vocareum.txt`. The model sees only this filtered slice because `gather_new_defects()` and `run_shift()` pass the SQL result into the prompt; full history stays in SQLite.

12. **Crash recovery.** The resume-vs-fresh decision and its staleness threshold (`recovery.py`). Why is a fresh start with an injected summary sometimes more reliable than resuming?
    → `recovery.py` defines `STALE_RESUME_THRESHOLD_MINUTES = 30`. It resumes a recent incomplete manifest, but starts fresh when the manifest is stale or complete, with recorded findings injectible as a summary. A fresh start avoids extending stale partial state and restarts from a known baseline. This threshold and resume/fresh truth table are covered by the 33 passing tests in `evidence/system-4/pytest-vocareum.txt`.

13. **Small state.** Byte size of your `hot_state.json`. Why does the budget matter for a system run once per shift, indefinitely?
    → `evidence/system-4/hot_state-vocareum.json` is under the code's 5,120-byte hot-state budget. A hard budget prevents hashes, alerts, and summaries from accumulating indefinitely across repeated shifts; history remains in SQLite and cold storage instead. `evidence/system-4/pytest-vocareum.txt` confirms 33 tests passed, including tiered-state, budget, and atomic-write coverage.

---

## Part 2 — Synthesis

14. **Three layers.** Point to a file/artifact for each layer and justify.
    → Model: `claims_intake/system_prompt.py` guides claim classification and terminal choice; live behavior appears in `evidence/system-1/traces-20261119_111636/claim_04_neighbor_injury.jsonl`. Harness: `claims_intake/loop.py` owns `stop_reason` dispatch and tool-result return; test coverage is in the Claims Intake suite. Orchestration: `shift_monitor/pipeline.py` owns filtering, prompt construction, single-invocation execution, and atomic state update; the Vocareum run is in `evidence/system-4/shift-run-vocareum.txt`.

15. **Deterministic vs prompt.** Cite one behavior guaranteed in code (terminal tool, read-only allowlist, atomic write, byte budget) and one guided by prompt. When is each right?
    → Code guarantees the hot-state limit and atomic replacement in `shift_monitor/state.py`, and the 33 System 4 tests validate that behavior. Prompting governs whether the claim agent calls `route_to_adjuster` or `escalate_to_human`, with live routing visible in the traces. Code is right for invariants and safety limits; prompts are right for contextual judgment.

16. **Context, two faces.** Compare context management in System 2 (intra-session) and System 4 (cross-session) with cited numbers from both. Same principle, different mechanism — how?
    → System 2 reduced an intra-session baseline of 38,708 tokens to 16,825 (56.53%) in `evidence/system-2/budget.json`. System 4 retained 40 rows in warm SQLite but selected only 17 for one shift, while keeping hot state under 5,120 bytes. Both keep only decision-relevant working context and archive/stage the rest; System 2 summarizes a conversation, while System 4 separates hot state from warm SQL history across shifts.

17. **Reliability you can't see in one run.** Name one behavior a test guarantees that a single successful run would not reveal. Why does it matter before shipping?
    → The Claims Intake anti-pattern suite guarantees that no string-membership or integer-literal loop control is present. A successful claim run could hide such drift if all fixtures happened to finish normally. This matters because the control contract would become brittle across different model output and edge cases. The suite evidence is the project test contract plus the trace-backed live run.

18. **Blast radius.** Pick one system. What's the blast radius if it misbehaves, and what's the kill switch? Ground it in that system's tools, enforcement points, and state.
    → System 1 could route a claim incorrectly or put it in the wrong human-review path. Terminal tools `route_to_adjuster` and `escalate_to_human` and the deterministic backstop limit outcomes, but no external kill switch is implemented. Disabling the runner/API credential or removing terminal-tool availability would stop processing; three live claims in the run unexpectedly escalated, visible in `evidence/system-1/escalations-20261119_111636.jsonl`.

---

## Part 3 — Honest assessment

19. **What broke.** One thing that failed first try in your environment, and how you fixed it. (If nothing, what you checked to be sure.)
    → In Vocareum, the initial `venv` failed to provide `ensurepip`; `python3.10` had global pip but the project environment could not bootstrap. Creating each project environment with `python3 -m virtualenv` restored pip and allowed dependencies to install. The real runs then produced the captured budget, eval, traces, validator, and shift artifacts.

20. **What you'd change.** One architectural decision you'd make differently, grounded in what you observed.
    → I would improve the Claims Intake backstop by recording why a model ended with no terminal tool and retrying or escalating by a structural reason, while preserving the existing deterministic escalation. Three fixtures reached an `end_turn` without terminal action and landed in human review. A visible terminal-tool compliance metric and preflight test for every fixture would catch this before submission or production.
