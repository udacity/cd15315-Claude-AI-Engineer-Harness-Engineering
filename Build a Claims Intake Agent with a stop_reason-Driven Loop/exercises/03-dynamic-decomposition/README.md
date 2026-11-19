# Exercise 3 — Wire Up Clarification and Escalation, Run the Fixtures End-to-End

> Picking up from Exercise 2: your tool kit lets the model look up policies, record facts, classify claims, and assess severity — but the loop has no way to terminate (no terminal tools) and no way to ask the claimant a follow-up (no `request_clarification`). This is the exercise that turns the agent on for real.

## What You're Learning Here

There is a useful contrast that comes up everywhere in agent design. A **prompt chain** is a fixed pipeline — `extract → classify → assess → route`. It works when the steps are known in advance. Most production "agents" that fail in interesting ways are prompt chains pretending to be agents.

**Dynamic decomposition** is the alternative. The right next action depends on *what was just learned at the previous step*. Take a claim that opens with *"my basement is flooded."* A fixed pipeline has to commit to either `property_damage` or `liability` from those words alone. The agentic loop can do something a prompt chain cannot: notice the ambiguity in its own facts, emit a `request_clarification` call ("what was the source of the water?"), receive the reply, *and then* commit. The clarifying step was not in any plan. It emerged from the model inspecting its own partial state.

That is the whole pattern. Same loop. Same tool kit. The *plan* emerges from inspection.

This exercise builds the pieces that make dynamic decomposition observable:

1. `request_clarification` — the tool the model calls to ask the claimant a follow-up. The dispatcher matches the question against the fixture's scripted replies and returns the matching reply, or `"NO_RESPONSE"`.
2. `route_to_adjuster` and `escalate_to_human` — the two terminal tools. Exactly one of them runs per claim. The model picks which.
3. The system prompt — the only place the *domain* (insurance, claim types, severity buckets, the "ask once when ambiguous" rule) appears.
4. The fixture runner wiring — passes the fixture's `clarification_responses` map into the session so `request_clarification` can return scripted replies.

## Now Apply It to the Claims Intake Project

### What You'll Build

The full agent. After this exercise, running

```bash
python -m claims_intake.run --all
```

processes 8 fixture claims end-to-end. Six route to one of the four queues. One escalates to a human reviewer (because the storm-damage fixture cannot be resolved with the facts on hand). One more is ambiguous-but-resolvable and routes only after the model issues a clarification.

### Requirements

- `request_clarification`, `route_to_adjuster`, `escalate_to_human` are added to `TOOL_SCHEMAS` with valid input schemas and `enum` on categorical fields.
- The matching dispatchers (`_t_request_clarification`, `_t_route_to_adjuster`, `_t_escalate_to_human`) are implemented per the contract in `tools.py`.
- Exactly one terminal tool is called per claim. Calling both, or neither, is a graceful error.
- The system prompt directs the model to (a) look up the policy early, (b) record facts as they arrive, (c) ask one clarifying question per missing piece of information when the claim type is ambiguous, (d) commit via `classify_claim` + `assess_severity` + a terminal tool.
- The fixture runner wires `fixture["clarification_responses"]` into the session so `request_clarification` can match.
- All 8 fixtures terminate cleanly. `claim_03` routes after a clarification. `claim_06` escalates. `claim_05` routes without clarification.

### How This Exercises the Dynamic Decomposition

When you open `runs/<ts>/traces/claim_03_water_damage.jsonl` and see a `request_clarification` turn between the fact-gathering and the `classify_claim` call, you are looking at dynamic decomposition. The clarification was not in any plan. The model emitted it because it inspected its own partial state and noticed the ambiguity. Same loop. Same tool kit. Different observed behavior — driven by the facts in flight.

### Resources

- Starter code: `starter/` (your finished Exercise 2 code, plus stubs for the three new tools, the system prompt, and the runner wiring)
- Reference docs: the Anthropic Messages API tool-use docs

### Instructions

- [ ] Add the three remaining schemas to `TOOL_SCHEMAS` in `starter/claims_intake/tools.py`.
- [ ] Implement `_t_request_clarification`, `_t_route_to_adjuster`, `_t_escalate_to_human` per the TODO comments in `tools.py`.
- [ ] Write `SYSTEM_PROMPT` in `starter/claims_intake/system_prompt.py` covering the claim types, severity buckets, the clarification rule, and the terminal choice.
- [ ] In `starter/claims_intake/run.py`, wire `clarification_responses=fixture.get("clarification_responses", {})` into the `ClaimSession(...)` call.

### Verify

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m claims_intake.run --all
pytest tests/ -v
```

`runs/<ts>/summary.md` should show 7 routed, 1 escalated. Estimated cost ≈ $0.05 on Haiku 4.5. The full pytest suite (30 tests) should be green.

### Troubleshooting

- **All claims terminate in `escalate_to_human`** — the system prompt's terminal-choice clause is probably backwards or missing. Re-read step 6 of the process: route when confidence is at least 0.6 *and* severity is set.
- **`claim_03` routes without any `request_clarification`** — either the prompt does not tell the model to ask one focused question when the claim type is ambiguous, or `ambiguity_between` is missing from the schema (the model uses that hint to decide *whether* to clarify).
- **`request_clarification` always returns `NO_RESPONSE`** — your substring matcher is comparing the question to the keys without lower-casing both sides. Look at the keys in `fixture["clarification_responses"]` — they are short keywords like `"source"`, `"locked"`, `"police"`. Match case-insensitively.
- **The model calls `route_to_adjuster` *and* `escalate_to_human`** — the dispatcher should short-circuit on `session.terminal_called` and return a graceful error.

### Stretch Challenges (Optional)

- Add a `--interactive` mode to `run.py` that takes claimant input from stdin instead of fixtures.
- Cap `request_clarification` at 3 per claim via a session-level counter so the model cannot loop on clarifications. (Note: this is *not* an anti-pattern because it is a session-state guard, not a control-flow signal — the loop still exits on `stop_reason`.)

---

After this exercise, you have the working reference project. The loop, the tool kit, and the dynamic decomposition behavior are all in place. This is the pattern that later work extends.
