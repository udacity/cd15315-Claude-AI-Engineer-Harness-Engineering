# Reflection Brief — Harness Engineering Capstone

**Name:**
**Date:**

Replace each `→` with your answer. **Every answer cites at least one artifact from your own runs** — a run ID, file path, token count, claim outcome, or test count. Uncited answers do not pass. 3–6 sentences each unless noted. Paste short artifact snippets where they help.

**Environment**

- Model(s):
- OS / Python:
- Approx. API spend:

---

## Part 1 — Per-system

### System 1 — Agentic loop

1. **Loop control.** Quote the `stop_reason` sequence from one trace. Name the file and function that decides continue-vs-stop, and how.
   → In `evidence/system-1/traces-20261119_111636/claim_05_auto_collision.jsonl`, the observed sequence is `tool_use -> tool_use -> tool_use -> end_turn`. In `claims_intake/loop.py`, `run()` continues on `tool_use`, returns on `end_turn`, and raises on any other stop reason. The trace shows three tool-use turns followed by normal termination.

2. **Anti-pattern.** Name one anti-pattern `test_antipatterns.py` checks for. What would break in your run if the loop used it?
   → `test_antipatterns.py` rejects natural-language string-membership control flow and integer-literal iteration caps as the loop’s primary stop condition. Such logic could stop before the model’s terminal response or ignore the actual `stop_reason`; claim 5’s four-turn trace shows why the loop must follow the response sequence rather than a fixed cap.

3. **Tool design.** Pick two tools with overlapping inputs. How do the descriptions prevent misrouting? What did a structured tool error let the agent do that a generic string would not?
   → 

4. **Your numbers.** Quote the turn count and cost for one claim. How does it differ from the README sample, and why?
   → 

### System 2 — Context strategy

5. **The reduction.** From `budget.json`: baseline tokens, assembled tokens, reduction %. Which section dominates the assembled context, and why keep it verbatim?
   → 

6. **Summarize vs preserve.** State the rule for what gets summarized vs kept byte-exact, citing your per-section token numbers.
   → 

7. **Facts block.** Compare `eval.jsonl` to `eval_control.jsonl`. Which question regressed, and what does that prove?
   → 

### System 3 — Claude Code config

8. **Path-scoped rules.** Quote the glob frontmatter from one rule file. Why is it better than a directory-level CLAUDE.md for cross-cutting conventions?
   → 

9. **Forked skill.** Quote the `context: fork` and `allowed-tools` lines. What does running forked + read-only buy you? What breaks without it?
   → 

10. **Scope.** From the validator output: project-level vs user-level scope. Give one example of each from this config.
    → 

### System 4 — Orchestration

11. **Push work down.** Defects the SQL query returned vs warm-tier total. Name the indexed query. Why does the model never see the full history?
    → 

12. **Crash recovery.** The resume-vs-fresh decision and its staleness threshold (`recovery.py`). Why is a fresh start with an injected summary sometimes more reliable than resuming?
    → `recovery.py` resumes only an incomplete run whose latest step is within `STALE_RESUME_THRESHOLD_MINUTES = 30`; an empty, completed, or stale manifest starts fresh. A fresh start avoids carrying forward stale partial state and can use recorded findings as a summary. The recovery truth-table and 30-minute threshold are covered by the System 4 tests.

13. **Small state.** Byte size of your `hot_state.json`. Why does the budget matter for a system run once per shift, indefinitely?
    → `evidence/system-4/hot_state-vocareum.json` is 965 bytes, below the 5,120-byte budget enforced by `state.py`. Keeping hot state bounded prevents each shift’s prompt state from growing indefinitely while the warm SQLite database retains history. `evidence/system-4/shift-run-vocareum.txt` records the run’s 17 new SQL-filtered defects.

---

## Part 2 — Synthesis

*Graded on connecting two or more systems. Cite a named file/artifact from each.*

14. **Three layers.** Point to a file/artifact for each layer and justify.
    → Model:
    → Harness:
    → Orchestration:

15. **Deterministic vs prompt.** Cite one behavior guaranteed in code (terminal tool, read-only allowlist, atomic write, byte budget) and one guided by prompt. When is each right?
    → 

16. **Context, two faces.** Compare context management in System 2 (intra-session) and System 4 (cross-session) with cited numbers from both. Same principle, different mechanism — how?
    → 

17. **Reliability you can't see in one run.** Name one behavior a test guarantees that a single successful run would not reveal. Why does it matter before shipping?
    → 

18. **Blast radius.** Pick one system. What's the blast radius if it misbehaves, and what's the kill switch? Ground it in that system's tools, enforcement points, and state.
    → 

---

## Part 3 — Honest assessment

19. **What broke.** One thing that failed first try in your environment, and how you fixed it. (If nothing, what you checked to be sure.)
    → 

20. **What you'd change.** One architectural decision you'd make differently, grounded in what you observed.
    → 
