"""CLI entry point — runs the full pipeline end-to-end.

Usage:
    python -m retail_context.run --all
    python -m retail_context.run --eval
    python -m retail_context.run --build         # build context.md only (no eval)
    python -m retail_context.run --eval --model claude-sonnet-4-5-20250929

Outputs (under runs/<run_id>/):
    context.md                — the assembled context
    budget.json               — token accounting
    case_facts_call.json      — LLM call log for case-facts extraction
    eval.jsonl                — eval-question results
    eval_control.jsonl        — control eval with case-facts stripped
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from retail_context import case_facts, compressor, evaluate, tokens, transcript
from retail_context.assemble import build as build_context
from retail_context.client import set_model

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RUNS_DIR = PROJECT_ROOT / "runs"


def _run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _load_eval_questions() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "eval_questions.json").read_text())["questions"]


def _build(run_dir: Path) -> tuple[Any, Any, Any]:
    print("[1/3] loading transcript + computing baseline token count")
    t = transcript.load(DATA_DIR / "transcript_48turns.json")
    baseline = t.token_count
    print(f"      baseline transcript tokens: {baseline}")

    print("[2/3] extracting case facts (LLM call)")
    facts = case_facts.extract(t, log_path=run_dir / "case_facts_call.json")

    print("[3/3] compressing resolved segments (LLM calls)")
    compressed = compressor.compress(t)
    for issue_id, summary in compressed.summaries.items():
        print(
            f"      resolved/{issue_id}: in={summary.input_tokens} out={summary.output_tokens}"
        )

    assembled = build_context(facts, compressed)

    (run_dir / "context.md").write_text(assembled.markdown)

    section_tokens = assembled.section_tokens()
    total = assembled.total_tokens()
    # TODO (Exercise 3): Build the coherent budget dict and write it to
    # `run_dir / "budget.json"`. The dict must carry these keys so the README
    # token table is reviewer-reproducible and the AST audit passes:
    #
    #   token_counter_methodology : tokens.methodology()
    #     — single line, sourced from the canonical counter so reviewers can
    #       interpret per-section numbers without re-deriving the algorithm.
    #
    #   baseline_tokens           : baseline   (from t.token_count above)
    #   assembled_tokens          : total      (= sum of per_section_tokens — invariant)
    #   reduction_pct             : round((1 - total / baseline) * 100, 2) if baseline else 0
    #
    #   per_section_tokens        : section_tokens
    #     — { "case_facts", "resolved_refund", "resolved_subscription", "active" }
    #       from assembled.section_tokens().
    #
    #   compression_api           : per-issue { input_tokens, output_tokens } from
    #                                compressed.summaries[issue_id]
    #
    # Write json.dumps(budget, indent=2) to `run_dir / "budget.json"`.
    budget: dict[str, Any] = {}
    raise NotImplementedError("Exercise 3: build the coherent budget dict and write budget.json")

    print()
    print(f"      assembled tokens: {total}  ({budget['reduction_pct']}% reduction)")
    for k, v in section_tokens.items():
        print(f"        {k:32s}  {v:>7}")

    return t, facts, assembled


def _eval(run_dir: Path, assembled_md: str) -> None:
    questions = _load_eval_questions()

    print()
    print(f"[eval] running {len(questions)} questions against compressed context")
    results = evaluate.run_questions(questions, assembled_md)
    evaluate.write_jsonl(results, run_dir / "eval.jsonl")
    for r in results:
        marker = "PASS" if r.passed else "FAIL"
        print(f"      {marker}  {r.question_id}  {r.question}")
        print(f"            answer: {r.model_answer[:120]}")
    n_passed = sum(1 for r in results if r.passed)
    print(f"      => {n_passed}/{len(results)} passed")

    print()
    print("[eval-control] running case-facts-stripped variant against Q1, Q6")
    stripped = evaluate.strip_case_facts(assembled_md)
    control_qs = [q for q in questions if q.get("required_in_control_fail")]
    control_results = evaluate.run_questions(control_qs, stripped)
    evaluate.write_jsonl(control_results, run_dir / "eval_control.jsonl")
    for r in control_results:
        marker = "PASS" if r.passed else "FAIL"
        expected = "expected FAIL" if not r.passed else "UNEXPECTED PASS"
        print(f"      {marker}  {r.question_id}  ({expected})")
        print(f"            answer: {r.model_answer[:120]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retail_context.run")
    parser.add_argument("--all", action="store_true", help="build + eval + control")
    parser.add_argument("--build", action="store_true", help="build assembled context only")
    parser.add_argument("--eval", action="store_true", help="build then eval")
    parser.add_argument("--model", default=None, help="override CLAUDE_MODEL for this run")
    parser.add_argument("--run-id", default=None, help="override run id (default: timestamp)")
    args = parser.parse_args(argv)

    if args.model:
        set_model(args.model)

    if not (args.all or args.build or args.eval):
        parser.print_help()
        return 1

    run_id = args.run_id or _run_id()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"run_id: {run_id}  (writing to {run_dir.relative_to(PROJECT_ROOT)})")
    print()

    _t, _facts, assembled = _build(run_dir)

    if args.eval or args.all:
        _eval(run_dir, assembled.markdown)

    print()
    print(f"done. artifacts in: {run_dir.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
