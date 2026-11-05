# Starter — Exercise 4

This starter carries everything from Exercise 3's solution plus a starter `docs/plan-mode-vs-direct-execution.md`.

## Files you will edit

- `docs/plan-mode-vs-direct-execution.md` — five TODO blocks:
  1. Knight-Webb citation block: name the speaker, the talk title, and the words "anchor talk".
  2. Section 1 — plan-mode example touching ≥3 files in `src/components/`, citing "prevent costly rework."
  3. Section 2 — direct-execution example targeting one function in `src/api/orders/handler.ts`.
  4. Section 3 — Explore sub-agent example with the scratchpad-pattern reference.
  5. Section 4 — combined-workflow example renaming `findById` → `getById` in `src/db/orders.ts`.

## Run / verify

```bash
source .venv/bin/activate
pytest -q
ecommerce-team-config .
```

Replace each TODO until pytest reports `35 passed` and the CLI prints `OK`.
