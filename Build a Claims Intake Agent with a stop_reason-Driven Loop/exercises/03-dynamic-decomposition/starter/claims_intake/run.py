"""Fixture runner.

`python -m claims_intake.run --all`
`python -m claims_intake.run --fixture claim_03_water_damage`
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from claims_intake.budget import Budget, BudgetExceeded
from claims_intake.client import DEFAULT_MODEL, make_client
from claims_intake.loop import FinalState, UnexpectedStopReason
from claims_intake.loop import run as run_loop
from claims_intake.pricing import estimate_cost_usd
from claims_intake.session import ClaimSession
from claims_intake.system_prompt import SYSTEM_PROMPT
from claims_intake.tools import TOOL_SCHEMAS, make_executor
from claims_intake.tracer import Tracer

ROOT = Path(__file__).resolve().parents[1]
POLICIES_PATH = ROOT / "data" / "policies.json"
FIXTURE_DIR = ROOT / "fixtures" / "claims"
RUNS_ROOT = ROOT / "runs"


@dataclass
class FixtureResult:
    fixture: dict[str, Any]
    session: ClaimSession
    state: FinalState | None
    error: str | None
    elapsed_s: float
    clarifications_asked: int


def _run_one(
    *,
    client: Any,
    model: str,
    fixture: dict[str, Any],
    policies: dict[str, dict[str, Any]],
    run_dir: Path,
    max_input_tokens: int,
    max_wall_clock_s: float,
) -> FixtureResult:
    session = ClaimSession(
        claim_id=fixture["claim_id"],
        policy_id=fixture["policy_id"],
        run_dir=run_dir,
        policies=policies,
        clarification_responses=fixture.get("clarification_responses", {}),
    )
    executor = make_executor(session)
    budget = Budget(
        max_input_tokens=max_input_tokens,
        max_wall_clock_s=max_wall_clock_s,
    )
    trace_path = run_dir / "traces" / f"{fixture['claim_id']}.jsonl"
    t0 = time.monotonic()
    state: FinalState | None = None
    error: str | None = None
    with Tracer(trace_path) as tracer:
        try:
            state = run_loop(
                client=client,
                model=model,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=[{"role": "user", "content": fixture["initial_message"]}],
                tool_executor=executor,
                budget=budget,
                tracer=tracer,
            )
        except (BudgetExceeded, UnexpectedStopReason) as exc:
            error = f"{type(exc).__name__}: {exc}"
    if state is not None and not session.terminal_called:
        _escalate_without_terminal(executor, session)
    return FixtureResult(
        fixture=fixture,
        session=session,
        state=state,
        error=error,
        elapsed_s=time.monotonic() - t0,
        clarifications_asked=len(session.clarifications_asked),
    )


def _escalate_without_terminal(executor: Any, session: ClaimSession) -> None:
    """Deterministic backstop: the model ended its turn without routing or escalating.

    The loop correctly stops on end_turn; whether a terminal tool was called is a
    separate question, answered here in code rather than left to the model. The
    claim is escalated through the same tool the model would have used, so it is
    written to escalations.jsonl like any other escalation.
    """
    executor(
        "escalate_to_human",
        {
            "reason": "model ended its turn without a terminal action (deterministic backstop)",
            "structured_summary": {
                "policy_id": session.policy_id,
                "root_cause": "no terminal tool called before end_turn",
                "candidate_claim_types": (
                    [session.classification["claim_type"]] if session.classification else []
                ),
                "case_facts": dict(session.case_facts),
                "recommended_action": "human review of the full transcript",
                "confidence": 0.0,
            },
        },
    )


def _summary_row(model: str, r: FixtureResult) -> dict[str, Any]:
    s = r.session
    state = r.state
    input_t = state.total_input_tokens if state else 0
    output_t = state.total_output_tokens if state else 0
    turns = state.turn_count if state else 0
    outcome = s.outcome if s.terminal_called else ("error" if r.error else "incomplete")
    claim_type: Any
    severity: Any
    if outcome == "routed" and s.routing is not None:
        claim_type = s.routing["claim_type"]
        severity = s.routing["severity"]
    elif outcome == "escalated" and s.escalation is not None:
        claim_type = ",".join(s.escalation.get("candidate_claim_types", []))
        severity = "-"
    else:
        claim_type = "-"
        severity = "-"
    return {
        "claim_id": s.claim_id,
        "outcome": outcome,
        "claim_type": claim_type,
        "severity": severity,
        "turns": turns,
        "clarifications_asked": r.clarifications_asked,
        "input_tokens": input_t,
        "output_tokens": output_t,
        "est_cost_usd": round(estimate_cost_usd(model, input_t, output_t), 4),
        "elapsed_s": round(r.elapsed_s, 1),
        "error": r.error or "",
    }


def _write_summary(
    run_dir: Path, model: str, rows: list[dict[str, Any]], total_cost: float
) -> Path:
    md_path = run_dir / "summary.md"
    headers = [
        "claim_id",
        "outcome",
        "claim_type",
        "severity",
        "turns",
        "clarifications_asked",
        "input_tokens",
        "output_tokens",
        "est_cost_usd",
        "elapsed_s",
    ]
    lines = [
        f"# Run summary — {run_dir.name}",
        "",
        f"- Model: `{model}`",
        f"- Fixtures processed: {len(rows)}",
        f"- Estimated total cost: **${total_cost:.4f}** USD",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(str(r[h]) for h in headers) + " |")
        if r["error"]:
            lines.append(f"  - error: `{r['error']}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def _load_fixtures(arg_fixture: str | None) -> list[Path]:
    if arg_fixture is not None:
        path = FIXTURE_DIR / f"{arg_fixture}.json"
        if not path.exists():
            raise FileNotFoundError(f"fixture not found: {path}")
        return [path]
    return sorted(FIXTURE_DIR.glob("claim_*.json"))


def _make_run_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_ROOT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_intake.run")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--all", action="store_true", help="Process every fixture in fixtures/claims/")
    grp.add_argument(
        "--fixture",
        type=str,
        metavar="NAME",
        help="Process one fixture, e.g. --fixture claim_03_water_damage",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-input-tokens", type=int, default=500_000)
    parser.add_argument("--max-wall-clock-s", type=float, default=180.0)
    args = parser.parse_args(argv)

    client = make_client()
    policies = json.loads(POLICIES_PATH.read_text())
    fixtures_to_run = _load_fixtures(args.fixture)
    run_dir = _make_run_dir()
    print(f"run_dir: {run_dir}", file=sys.stderr)

    rows: list[dict[str, Any]] = []
    total_input = 0
    total_output = 0
    any_failure = False

    for fx_path in fixtures_to_run:
        fixture = json.loads(fx_path.read_text())
        print(
            f"[{fixture['claim_id']}] policy={fixture['policy_id']} expected={fixture['expected_outcome']}",
            file=sys.stderr,
        )
        result = _run_one(
            client=client,
            model=args.model,
            fixture=fixture,
            policies=policies,
            run_dir=run_dir,
            max_input_tokens=args.max_input_tokens,
            max_wall_clock_s=args.max_wall_clock_s,
        )
        row = _summary_row(args.model, result)
        rows.append(row)
        if result.state is not None:
            total_input += result.state.total_input_tokens
            total_output += result.state.total_output_tokens
        if not result.session.terminal_called:
            any_failure = True
        print(
            f"  → outcome={row['outcome']} turns={row['turns']} clarifications={row['clarifications_asked']} "
            f"tokens={row['input_tokens']}/{row['output_tokens']} est=${row['est_cost_usd']:.4f}",
            file=sys.stderr,
        )

    total_cost = estimate_cost_usd(args.model, total_input, total_output)
    summary_path = _write_summary(run_dir, args.model, rows, total_cost)
    print(f"summary: {summary_path}", file=sys.stderr)
    print(f"total estimated cost: ${total_cost:.4f}", file=sys.stderr)
    return 1 if any_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
