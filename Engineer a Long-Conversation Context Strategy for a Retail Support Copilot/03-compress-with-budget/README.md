# Exercise 3: Build the Canonical Counter, Compress Resolved Segments, Emit budget.json

*Implement the canonical token-counting function that records its methodology, then use it to compress resolved conversation segments into structured ≤500-token summaries with a committed prompt template while preserving the active segment byte-exact, and emit a `budget.json` whose per-section numbers sum to the assembled total.*

---

## What you start with

`starter/` is byte-identical to Exercise 2's `solution/` — your pruner and your case-facts extractor are already in place. New for Exercise 3:

- `retail_context/tokens.py` — the canonical token counter. Currently a heuristic-only stub; you expand it to dispatch on `ANTHROPIC_API_KEY` presence.
- `retail_context/compressor.py` — the per-resolved-segment summarizer + the orchestrator. Two TODO bodies.
- `retail_context/prompts/compression_prompt.md` — currently a placeholder. You replace it with the structured 3-part summarization prompt.
- `retail_context/run.py:_build` — the budget-emission block is stubbed. You build the coherent `budget.json` dict and write it.

## What to build

1. **`tokens.py`** — fill in the two TODO blocks:
   - `count(text)`: when `ANTHROPIC_API_KEY` is set, call `get_client().messages.count_tokens(model=get_model(), messages=[...])` and return `int(resp.input_tokens)`. Otherwise fall back to the heuristic.
   - `methodology()`: return the descriptive string for whichever path is active. This string gets written verbatim into `budget.json` so a reviewer can interpret the numbers.

2. **`prompts/compression_prompt.md`** — write the structured prompt. The committed template is reviewed as part of the deliverable; a reviewer reads this file. The contract: outcome sentence → 3–6 bulleted facts (identifiers and amounts preserved verbatim) → resolution sentence, total ≤500 tokens, no preambles or closing remarks.

3. **`compressor.py`**:
   - `summarize_segment(segment, *, model=None)`: refuse anything whose status is not `"resolved"` (raise `ValueError`), then load the prompt and make one `complete_with_system` call. Return a `Summary` carrying the issue_id, the response text, and token counts.
   - `compress(transcript, *, model=None)`: per-segment dispatch — resolved → summarize; active → preserve byte-exact via `"\n\n".join(t.render() for t in seg.turns)`. Raise `RuntimeError` if no active segment is present.

4. **`run.py:_build`** — build the budget dict carrying `token_counter_methodology`, `baseline_tokens`, `assembled_tokens`, `reduction_pct`, `per_section_tokens`, and `compression_api`. Write `json.dumps(budget, indent=2)` to `run_dir / "budget.json"`.

## Verify

Unit-level (no API key required):

```bash
pytest tests/test_tokens.py tests/test_compressor.py tests/test_case_facts.py tests/test_pruner.py tests/test_transcript.py tests/test_antipatterns.py -v
```

All 25 of these must pass. Note that `tests/test_assemble.py` is NOT in the verify command — `assemble.py` is Exercise 4's work and is still stubbed. Running it now would fail with `NotImplementedError`, which is the expected state at this stage.

If you want to exercise the live compression and budget emission end-to-end (one extraction call + two summarization calls, ~$0.03 total on Haiku 4.5):

```bash
ANTHROPIC_API_KEY=sk-ant-... python -m retail_context.run --build
```

`--build` runs case-facts extraction and compression, then stops with `NotImplementedError` inside `assemble.build()`: **the assembly step is Exercise 4**. It doesn't reach `budget.json` either, because the budget's per-section numbers come from the assembled context (`assembled.section_tokens()`). The full `--build` run, `budget.json` included, works in Exercise 4's folder (`04-assemble-and-locate`), where you write the assembly.

If you'd rather verify the compression output without touching assembly at all, run this one-liner with `ANTHROPIC_API_KEY` set:

```bash
ANTHROPIC_API_KEY=sk-ant-... python3 -c "
from retail_context import compressor, transcript, tokens
t = transcript.load('data/transcript_48turns.json')
c = compressor.compress(t)
for issue, s in c.summaries.items():
    print(f'== {issue} ({s.input_tokens} in, {s.output_tokens} out, {tokens.count(s.text)} t) ==')
    print(s.text[:400])
    print()
print(f'active segment: {tokens.count(c.active_text)} tokens, issue={c.active_issue_id}')
print(f'methodology: {tokens.methodology()}')
"
```

Each resolved summary should follow the prompt's 3-part structure and clock in under 500 tokens.

## Where to look if you get stuck

- **Why is the active segment preserved byte-exact?** The whole point of tiered compression is that the *resolution-still-being-negotiated* thread cannot afford fidelity loss — a paraphrased turn might drop the line where the customer named their new card's last-4. The `summarize_segment` guard is the defense against accidentally summarizing the active thread "for consistency."
- **Why does the prompt matter?** The template is committed so reviewers can audit *intent*, not just output. A vague prompt produces grammatical-but-thin summaries that pass the token cap but fail the eval. Structure carries the load.
- **`per_section_tokens` must sum to `assembled_tokens`.** This is the coherence rule — if the per-section dict and the total disagree, the canonical counter has been bypassed somewhere. The `test_only_tokens_module_uses_count_tokens_or_heuristic` check catches the most common cause: a competing `len(x) / N` heuristic in another module.

## When you're done

Compare to `solution/retail_context/{tokens,compressor,run}.py` and `solution/retail_context/prompts/compression_prompt.md`. Exercise 4 is the capstone — it builds the assembly that wires your compressor and case-facts block into the position-aware engineered context.
