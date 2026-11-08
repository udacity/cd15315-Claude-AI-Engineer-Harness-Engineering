# Capstone — Harness Engineering with Claude and Claude Code

This capstone is the integrative project for the **Harness Engineering** course. Instead of building one new system, you take the four systems you have studied across the course, **build them, run them, and verify them on your own machine**, then write an **evidence-grounded reflection brief** that defends the architectural decisions each system makes.


> **What "build and run" means here.** Each of the four systems is the **completed reference implementation** that ships in the final exercise's `solution/` folder of its project in the course repo (`cd15315`). You do **not** implement TODOs — the `starter/` folders are where the course's fill-in-the-blank exercises live; the capstone runs the finished `solution/`. Your job is to stand each system up in a working environment, run it against its fixtures, run its tests, capture the artifacts it produces, and analyze *why* it is built the way it is.

---

## The four systems

| # | System | Course project | Run with | Primary skills |
|---|--------|----------------|----------|----------------|
| 1 | **Insurance Claims Intake Agent** | Build a Claims Intake Agent with a stop_reason-Driven Loop | `python -m claims_intake.run --all` | Agentic loops, tool design, structured output |
| 2 | **Retail Support Context Strategy** | Engineer a Long-Conversation Context Strategy for a Retail Support Copilot | `python -m retail_context.run --all` | Context management |
| 3 | **E-Commerce Team Claude Code Config** | Configure Claude Code for a Multi-Surface Monorepo Team | `python -m ecommerce_team_config .` | Claude Code configuration & workflows |
| 4 | **Multi-Shift Quality Monitoring** | Build a Multi-Shift Quality Monitoring System with Claude Orchestration | `python -m shift_monitor run-shift …` | Layer 3 orchestration, state management |

The four systems live in the course repo (`cd15315 Claude AI Engineer Harness Engineering`), one project per top-level folder. The runnable system for each is the `solution/` of that project's **final** exercise:

```
cd15315 Claude AI Engineer Harness Engineering/
├── Build a Claims Intake Agent with a stop_reason-Driven Loop/
│   └── exercises/03-dynamic-decomposition/solution/          ← System 1
├── Engineer a Long-Conversation Context Strategy for a Retail Support Copilot/
│   └── 04-assemble-and-locate/solution/                      ← System 2
├── Configure Claude Code for a Multi-Surface Monorepo Team/
│   └── 04-plan-mode-and-explore-decision-doc/solution/       ← System 3
└── Build a Multi-Shift Quality Monitoring System with Claude Orchestration/
    └── 04-fork-scratchpad/solution/                          ← System 4
```

This capstone folder (`module-05-capstone-harness-engineering/`) lives separately and just holds the project materials:

```
module-05-capstone-harness-engineering/   ← you are here
├── README.md
└── reflection-brief-template.md
```

---

## Prerequisites

- **Python 3.10+**
- **A Claude API key** exported as `ANTHROPIC_API_KEY`. Systems 1, 2, and 4 call the real Claude API. System 3's validator does not require the API.
  > ⚠️ Running all four systems against the live API costs roughly **$1–$5 total** on the default Haiku/Sonnet models. System 4 can be run fully offline with `--recorded-response` if you want to avoid any spend on that one.
- **git** and a terminal (macOS, Linux, or WSL on Windows).

Each system pins its own dependencies in `pyproject.toml`. Use a separate virtual environment per system to avoid version conflicts (System 1 pins `anthropic==0.39.0`; System 2 pins `anthropic==0.69.0`).

---

## How to build, run, and verify each system

Run every command from inside that system's `solution/` directory. The pattern is the same for all four: create a venv, install, run the tests, then run the system end-to-end and save what it prints to disk.

The folder names contain spaces, so point a variable at your local clone of the course repo and quote it:

```bash
# Path to your clone of the cd15315 course repo:
SYSTEMS="../../Github Repos/cd15315 Claude AI Engineer Harness Engineering"
```

### System 1 — Insurance Claims Intake Agent

```bash
cd "$SYSTEMS/Build a Claims Intake Agent with a stop_reason-Driven Loop/exercises/03-dynamic-decomposition/solution"
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest tests/ -v                       # expect 29 passed
python -m claims_intake.run --all      # processes 8 claim fixtures
```

**What success looks like:** a new `runs/<timestamp>/` directory containing `summary.md` (a table of claim outcomes), `traces/` (one JSONL trace per claim showing `stop_reason` per turn), `queues/*.jsonl` (routed claims), and `escalations.jsonl`. The process exits `0` when every claim terminates (routed or escalated).

**Capture for evidence:** the `summary.md` table, one trace file, and the test output.

### System 2 — Retail Support Context Strategy

```bash
cd "$SYSTEMS/Engineer a Long-Conversation Context Strategy for a Retail Support Copilot/04-assemble-and-locate/solution"
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest tests/ -v                       # expect 30 passed
python -m retail_context.run --all     # assemble context + run 6 evals + control
```

**What success looks like:** a new `runs/<run_id>/` with `context.md` (the assembled context), `budget.json` (token accounting showing ≥50% reduction from the ~47k-token baseline), `eval.jsonl` (6 eval questions), and `eval_control.jsonl` (the case-facts-stripped control, where at least one question is expected to fail).

**Capture for evidence:** `budget.json`, the eval pass count, and the control comparison.

### System 3 — E-Commerce Team Claude Code Config

```bash
cd "$SYSTEMS/Configure Claude Code for a Multi-Surface Monorepo Team/04-plan-mode-and-explore-decision-doc/solution"
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest tests/ -v                       # expect 35 passed
python -m ecommerce_team_config .      # validate the config hierarchy
```

**What success looks like:** the validator prints `OK` and exits `0`, confirming the CLAUDE.md hierarchy, the three path-scoped rules, the `/review` command, and the `/deploy-check` skill all conform to spec.

**Capture for evidence:** the validator output, and the structure of `.claude/` (rules with glob frontmatter, the command, the `context: fork` skill).

### System 4 — Multi-Shift Quality Monitoring

```bash
cd "$SYSTEMS/Build a Multi-Shift Quality Monitoring System with Claude Orchestration/04-fork-scratchpad/solution"
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest tests/ -v                       # expect 33 passed

# seed the warm tier once
python -c "import json; from pathlib import Path; from shift_monitor.warm import WarmStore; \
w=WarmStore(Path('data/warm.sqlite')); w.initialize(); \
w.insert_many(json.load(open('fixtures/defects.json')))"

# run a shift offline against a recorded response (no API spend):
python -m shift_monitor run-shift --shift C --warm-db data/warm.sqlite \
  --recorded-response fixtures/recorded_responses/shift_C_2026-04-30.json
```

**What success looks like:** the shift summary prints to stdout, `data/hot_state.json` is updated (kept under ~5 KB), and a line is appended to `data/shift_scratchpad.jsonl`.

**Capture for evidence:** the shift output, the size of `hot_state.json`, and a fork's isolated scratchpad if you exercise the fork path.

---

## What you submit

1. **Evidence of building and running all four systems** — terminal logs / screenshots of each `pytest` run passing, and the key run artifact from each system (see "Capture for evidence" above). Organize one folder per system.
2. **The completed reflection brief** — `reflection-brief-template.md`, filled in. Every answer must cite specific artifacts from *your* runs (run IDs, token counts, outcomes, file paths).

