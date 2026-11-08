"""Tests for crash recovery via the incremental manifest."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from shift_monitor import recovery
from shift_monitor.invocation import resumed
from shift_monitor.manifest import Manifest, ManifestState, Step
from shift_monitor.recovery import STALE_RESUME_THRESHOLD_MINUTES
from shift_monitor.warm import WarmStore

UTC = timezone.utc


def _make_step(name: str, when: datetime, shape: str = "rich") -> Step:
    return Step(
        step_id=f"sid-{name}",
        name=name,
        ts=when,
        invocation_shape=shape,  # type: ignore[arg-type]
        payload={"detail": f"payload for {name}"},
    )


# ---------- atomic, line-complete manifest appends ----------


def test_append_step_writes_and_fsyncs(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest_S1.jsonl")
    now = datetime.now(UTC)
    manifest.append_step(_make_step("gather", now))
    manifest.append_step(_make_step("analyze", now + timedelta(seconds=2)))
    raw = (tmp_path / "manifest_S1.jsonl").read_text().splitlines()
    assert len(raw) == 2
    assert "gather" in raw[0]
    assert "analyze" in raw[1]


def test_mid_write_read_reveals_prior_complete_lines(tmp_path: Path) -> None:
    """A reader opening the file between append calls sees only complete lines."""
    manifest_path = tmp_path / "manifest_S2.jsonl"
    manifest = Manifest(manifest_path)
    now = datetime.now(UTC)
    manifest.append_step(_make_step("gather", now))
    # Concurrent reader at this point sees the gather line:
    intermediate = manifest_path.read_text().splitlines()
    assert len(intermediate) == 1
    assert "gather" in intermediate[0]
    manifest.append_step(_make_step("analyze", now + timedelta(seconds=1)))
    final = manifest_path.read_text().splitlines()
    assert len(final) == 2


# ---------- loading manifest state ----------


def test_load_returns_incomplete_state(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest_S3.jsonl")
    now = datetime.now(UTC)
    manifest.append_step(_make_step("gather", now))
    manifest.append_step(_make_step("analyze", now + timedelta(seconds=1)))
    state = Manifest.load(tmp_path / "manifest_S3.jsonl")
    assert isinstance(state, ManifestState)
    assert state.complete is False
    assert [s.name for s in state.steps] == ["gather", "analyze"]


def test_load_returns_complete_state(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest_S4.jsonl")
    now = datetime.now(UTC)
    manifest.append_step(_make_step("gather", now))
    manifest.append_step(_make_step("complete", now + timedelta(seconds=2)))
    state = Manifest.load(tmp_path / "manifest_S4.jsonl")
    assert state.complete is True


def test_load_on_missing_file_returns_empty(tmp_path: Path) -> None:
    state = Manifest.load(tmp_path / "does_not_exist.jsonl")
    assert state.complete is False
    assert state.steps == []


# ---------- resume-vs-fresh decision ----------


@pytest.mark.parametrize(
    "minutes_ago,complete,expected",
    [
        (1, False, "resume"),
        (29, False, "resume"),
        (30, False, "resume"),
        (31, False, "fresh"),
        (1, True, "fresh"),
        (60, True, "fresh"),
    ],
)
def test_recovery_decide_truth_table(
    minutes_ago: int, complete: bool, expected: str
) -> None:
    now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)
    last_ts = now - timedelta(minutes=minutes_ago)
    steps = [_make_step("gather", last_ts)]
    if complete:
        steps.append(_make_step("complete", last_ts + timedelta(seconds=1)))
    state = ManifestState(
        complete=complete,
        steps=steps,
    )
    assert recovery.decide(state, now) == expected


def test_recovery_decide_empty_manifest_is_fresh() -> None:
    now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)
    assert recovery.decide(ManifestState(complete=False, steps=[]), now) == "fresh"


def test_threshold_constant_is_30_minutes() -> None:
    assert STALE_RESUME_THRESHOLD_MINUTES == 30


# ---------- resumed prompt construction ----------


def test_resumed_prompt_has_both_sections(
    tmp_path: Path, defect_rows: list[dict[str, Any]]
) -> None:
    warm = WarmStore(tmp_path / "warm.sqlite")
    warm.initialize()
    warm.insert_many(defect_rows)
    # Pretend the last step happened just after a known timestamp;
    # new defects since then should appear in the resumed prompt.
    last_step_ts = "2026-04-19T00:00:00Z"
    new_defects = warm.defects_since(last_step_ts, limit=20)
    assert len(new_defects) > 0

    prior_steps = [
        {"name": "gather", "payload": {"count": 12}},
        {"name": "analyze", "payload": {"finding": "lot 2026-0430-B suspect"}},
    ]
    inv = resumed(
        session_id="sess-C-2026-04-30",
        summary="Prior shift identified lot quarantine candidate.",
        latest_message="Continue from where you left off.",
        prior_steps=prior_steps,
        new_defects=new_defects,
    )
    assert inv.shape == "resumed"
    assert "Prior partial findings" in inv.prompt
    assert "New defects since last partial step" in inv.prompt
    for d in new_defects:
        assert d["id"] in inv.prompt
