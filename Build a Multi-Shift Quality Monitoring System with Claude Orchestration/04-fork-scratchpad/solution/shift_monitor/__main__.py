"""CLI entry point: `python -m shift_monitor run-shift --shift <ID>`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import pipeline
from .client import AnthropicClaudeClient, ClaudeClient, RecordedClaudeClient
from .state import HotState
from .warm import WarmStore

UTC = timezone.utc


def _default_since() -> str:
    return (datetime.now(UTC) - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_client(recorded_path: Path | None) -> ClaudeClient:
    if recorded_path is not None:
        payload = json.loads(recorded_path.read_text())
        return RecordedClaudeClient(responses=[payload["content"]])
    return AnthropicClaudeClient()


def _ensure_hot_state(path: Path) -> None:
    if path.exists():
        return
    HotState(
        recent_defect_hashes=[],
        current_shift_summary="(no prior shift)",
        active_alerts=[],
        threshold_statuses={},
    ).write_atomic(path)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="shift-monitor")
    sub = parser.add_subparsers(dest="cmd", required=True)
    rs = sub.add_parser("run-shift", help="Run one shift analysis")
    rs.add_argument("--shift", required=True, choices=["A", "B", "C"])
    rs.add_argument("--warm-db", default="data/warm.sqlite")
    rs.add_argument("--hot-state", default="data/hot_state.json")
    rs.add_argument("--scratchpad", default="data/shift_scratchpad.jsonl")
    rs.add_argument("--since", default=None, help="ISO-8601 timestamp; default = 8h ago")
    rs.add_argument(
        "--recorded-response",
        default=None,
        help="Path to a recorded Claude response JSON (offline mode)",
    )
    args = parser.parse_args(argv)

    if args.cmd == "run-shift":
        warm_path = Path(args.warm_db)
        warm = WarmStore(warm_path)
        warm.initialize()
        hot_state_path = Path(args.hot_state)
        _ensure_hot_state(hot_state_path)
        client = _build_client(Path(args.recorded_response) if args.recorded_response else None)
        result = pipeline.run_shift(
            shift_id=args.shift,
            client=client,
            warm=warm,
            hot_state_path=hot_state_path,
            scratchpad_path=Path(args.scratchpad),
            since_ts=args.since or _default_since(),
        )
        print(f"shift {result.shift_id}: {result.new_defect_count} new defects")
        print(result.summary)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
