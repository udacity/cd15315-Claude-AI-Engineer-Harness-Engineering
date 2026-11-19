# Exercise 2 — Define the Tool Kit and Add the Anti-Pattern Audit

> Picking up from Exercise 1: your loop in `claims_intake/loop.py` drives a model that calls tools and returns when `stop_reason == "end_turn"`. But the tool kit is empty. Right now the model has nothing to call. This exercise gives the model its action space.

## What You're Learning Here

The tool schemas you write **are the agent's API**. The set of tools you expose is the set of actions the model can take. When the model has to choose between "ask a clarifying question" and "commit to a classification," it is choosing between two tool schemas you registered.

This has a sharp consequence: decision logic does not belong in Python. The moment your harness contains `if "water" in transcript: claim_type = "property_damage"`, you have moved the decision out of the model. That looks helpful but it is the anti-pattern that defines this module. If the model is making the decision, the harness has nothing to branch on — the model's tool choice carries it.

The four named anti-patterns in this module are how decision logic sneaks back into Python:

1. **Natural-language termination** — using `"done" in text` to decide whether to stop.
2. **Integer-literal iteration caps** — `for _ in range(10)` or `while turn < N` as the primary stop mechanism. A *Budget* (token / wall-clock, sourced from config) is the safety net; a literal cap is not.
3. **Text-content completion checks** — exiting because the response looks finished, instead of because `stop_reason == "end_turn"`.
4. **`if claim_type == "..."` branching** — Python deciding what to do based on what the model said.

An **AST audit** is how you keep them out. Static analysis on `loop.py` and the package catches these even when no test exercises the offending code path.

## Now Apply It to the Claims Intake Tool Kit

### What You'll Build

Four tool schemas the model will use to gather facts and commit to a classification:

| Tool | Purpose |
|---|---|
| `lookup_policy(policy_id)` | Returns the policy record from `data/policies.json`. |
| `record_claim_fact(field, value)` | Appends a normalized fact to the case file. |
| `classify_claim(claim_type, confidence, rationale)` | Commits the model to one of the four claim types. |
| `assess_severity(severity, rationale)` | Commits the model to `low` / `medium` / `high`. |

Plus the **Graceful Tool Failure** helpers `_err` and `_ok`, the matching dispatcher functions, and four AST tests that audit `loop.py` for the anti-patterns above.

(Exercise 3 will add `request_clarification`, `route_to_adjuster`, and `escalate_to_human`. The dispatcher stubs for those three are already in place.)

### Requirements

- All four schemas are registered in `TOOL_SCHEMAS` with `name`, `description`, and `input_schema`.
- `input_schema.required` lists every parameter the dispatcher reads.
- Categorical fields use `enum`: `claim_type` against `CLAIM_TYPES`, `severity` against `SEVERITIES`.
- Tool errors return a JSON string with shape `{"is_error": true, "error_category": "permanent"|"transient", "is_retryable": bool, "message": "..."}`. Errors are *never* raised as Python exceptions to the loop.
- Each dispatcher validates inputs and returns `_err(...)` on bad input rather than crashing.
- The four AST tests pass against `loop.py`.

### How This Exercises the Tool Kit and Anti-Pattern

The tools are the surface area through which the model can act. Writing the schemas forces you to name those actions precisely. The AST audit then closes the loop: even if someone refactors `loop.py` later and is tempted to add `if "..." in response_text:`, the audit will catch it.

### Resources

- Starter code: `starter/`
- Tool dispatcher tests: `tests/test_tools.py` (already in place; runs against what you write)

### Instructions

- [x] In `starter/claims_intake/tools.py`, populate `TOOL_SCHEMAS` with the four schemas above.
- [x] Implement `_err` and `_ok` so they return the right JSON shape.
- [x] Implement `_t_lookup_policy`, `_t_record_claim_fact`, `_t_classify_claim`, `_t_assess_severity`. Each validates its input and returns a graceful error on bad input.
- [x] In `starter/tests/test_antipatterns.py`, write the four AST tests (the file has detailed TODO comments naming the heuristic for each).

### Verify

```bash
pytest tests/test_antipatterns.py -v
pytest tests/test_tools.py::test_lookup_policy_returns_record \
       tests/test_tools.py::test_lookup_policy_unknown_id_returns_graceful_error \
       tests/test_tools.py::test_unknown_tool_returns_graceful_error \
       tests/test_tools.py::test_handler_exception_is_caught_as_transient_error -v
```

The four AST tests should pass. The four dispatcher tests above should pass. The other tests in `tests/test_tools.py` reference `request_clarification`, `route_to_adjuster`, and `escalate_to_human` — they will still fail until Exercise 3.

### Troubleshooting

- **`test_seven_tools_registered_with_schemas` fails** — that test counts 7 tools; you only have 4 after Exercise 2. Expected; it goes green at the end of Exercise 3.
- **`test_no_string_membership_against_text_in_loop` flags your own audit** — you may have used a string literal in an `in` test inside the audit itself. The audit reads `loop.py`, not its own file; double-check `PKG / "loop.py"` is the path you parse.
- **A dispatcher crashes the test rather than returning an error** — your handler raised instead of returning `_err(...)`. The dispatcher wraps handlers in `try/except`, but your own handler should prefer to return a graceful error rather than raise in the first place.

### Stretch Challenges (Optional)

- Add a fifth AST test that fails if `loop.py` imports `claim_type` from anywhere — a structural way to enforce that the loop has no domain knowledge.
- Add a description-quality lint: assert that every tool's `description` is at least 80 characters and mentions when to call it.

---

After this exercise, your tool kit can collect facts and commit to a classification — but it has no way to ask a clarifying question or terminate. Exercise 3 wires those in and turns the project on end-to-end.
