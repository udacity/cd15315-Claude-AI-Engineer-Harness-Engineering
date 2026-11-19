# Exercise 1 — Build the Agentic Loop

> Picking up from the bootstrap scaffold: the project skeleton is in place — Claude API client factory, `Budget`, `Tracer`, `ClaimSession` dataclass, package layout, tests. Your job in this exercise is the single function that drives every later turn the agent ever takes: the agentic loop.

## What You're Learning Here

An agent harness is **a loop the model controls**. On each iteration the harness does exactly one thing — sends the messages to the model — and then reads the model's `stop_reason` to decide what to do next:

- `stop_reason == "end_turn"` → the model is done. Return.
- `stop_reason == "tool_use"` → the model wants to use one or more tools. Execute them, package the results into a *single* user turn of `tool_result` blocks, and ask the model again.
- anything else (`max_tokens`, `stop_sequence`, `pause_turn`, `refusal`) → something happened we did not plan for. Raise loudly. Do not guess.

The harness owns the loop. The model owns the decision to keep going, ask for tools, or stop. The signal that crosses the boundary between them is `stop_reason`.

## Now Apply It to the Claims Intake Loop

The file `claims_intake/loop.py` already contains:

- The `FinalState` dataclass that you will return on `end_turn`.
- The `UnexpectedStopReason` exception you will raise when `stop_reason` is anything else.
- The `run(...)` signature and the entire setup: working messages, turn counter, the `while True:` header, `budget.check()`, the `client.messages.create(...)` call, and the token bookkeeping.

You will write the **body** of each iteration: build the trace record, call `tracer.write(...)`, and the three-case triage on `response.stop_reason`.

### Requirements

- The loop terminates **only** on `stop_reason == "end_turn"`.
- The loop continues **only** on `stop_reason == "tool_use"`.
- Any other `stop_reason` raises `UnexpectedStopReason` naming the turn and the offending value.
- All `tool_use` blocks in a single assistant turn are executed and returned in **one** following user turn whose `content` is a list of `tool_result` blocks (each with the matching `tool_use_id`). Not one user turn per tool.
- The trace records one JSON object per turn with these keys: `turn`, `stop_reason`, `tool_calls`, `latency_ms`, `input_tokens`, `output_tokens`.

### How This Exercises the Loop

The loop you write here is the artifact every later stage extends — context engineering, evals, bounded autonomy, multi-agent orchestration. Getting the `stop_reason`-driven control flow right now is what makes those later stages tractable.

### Resources

- Starter code: `starter/`
- Solution reference (do not peek until you have the loop running): `solution/`
- The `tests/test_loop.py` file already exists — your job is to make it pass.

### Instructions

- [x] Open `starter/claims_intake/loop.py` and read the function signature and the existing scaffold above the TODO.
- [x] Build the per-turn trace record (`turn`, `stop_reason`, `tool_calls`, `latency_ms`, `input_tokens`, `output_tokens`) and call `tracer.write(...)`.
- [x] Handle the `end_turn` case: append the assistant turn to `working_messages`, return a `FinalState`.
- [x] Handle the `tool_use` case: append the assistant turn, then for every `tool_use` block call `tool_executor(name, input)`, collect the results into matching `tool_result` blocks, append a *single* user turn containing all of them, and `continue` the loop.
- [x] Raise `UnexpectedStopReason` for anything else.

### Verify

From inside `starter/`:

```bash
pip install -e ".[dev]"
pytest tests/test_loop.py -v
```

All 5 tests should pass. They use a scripted `FakeMessages` client, so this runs offline and costs nothing.

> Run `pytest tests/test_loop.py`, not a bare `pytest`. This project is cumulative — `tests/test_tools.py` and `tests/test_fixtures.py` are already present but belong to Exercises 2 and 3, so a bare `pytest` will show them as expected reds until you get there.

### Troubleshooting

- **`API rejects with shape error`** — you are probably returning the `tool_result` blocks in an assistant turn instead of a user turn. Check the `role` field.
- **`test_loop_handles_multiple_tool_use_blocks_in_one_turn` fails** — the test asserts that *all* `tool_result` blocks land in ONE user turn. If you appended one user turn per tool, you'll get 4 messages where the test expects 3.
- **`test_loop_raises_on_unexpected_stop_reason` fails** — make sure your fallback path raises rather than silently continuing.

### Stretch Challenges (Optional)

- Add a structured `pause_turn` handler that re-issues the request once before raising — useful for long-running tool calls in later modules.
- Extend the trace record with `model` and `system_prompt_hash` fields so traces from different prompts can be compared.

---

After this exercise, your `claims_intake/loop.py` is the foundation the next two exercises build on. `starter/02-tools-and-audit/` picks up your finished `loop.py` byte-for-byte.
