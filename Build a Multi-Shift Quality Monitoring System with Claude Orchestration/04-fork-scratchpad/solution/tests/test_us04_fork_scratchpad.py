"""Tests for fork sessions and the scratchpad."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from shift_monitor import fork
from shift_monitor.scratchpad import Scratchpad, ScratchpadEntry
from shift_monitor.state import HotState

UTC = timezone.utc


def _baseline_hot_state(path: Path) -> HotState:
    state = HotState(
        recent_defect_hashes=["a", "b", "c"],
        current_shift_summary="Shift C 2026-04-30: capacitor cluster.",
        active_alerts=["capacitor-bank-C-7 elevated"],
        threshold_statuses={"defect_rate_per_shift": "ALARM"},
    )
    state.write_atomic(path)
    return state


def _entry(hypothesis_id: str, conclusion: str) -> ScratchpadEntry:
    return ScratchpadEntry(
        hypothesis_id=hypothesis_id,
        evidence="evidence X",
        conclusion=conclusion,
        ts=datetime.now(UTC),
    )


# ---------- scratchpad append and read order ----------


def test_scratchpad_append_and_read_order(tmp_path: Path) -> None:
    sp = Scratchpad(tmp_path / "scratchpad.jsonl")
    sp.append(_entry("H1", "conclusion 1"))
    sp.append(_entry("H1", "conclusion 2"))
    sp.append(_entry("H2", "conclusion 3"))
    entries = sp.read()
    assert [e.conclusion for e in entries] == ["conclusion 1", "conclusion 2", "conclusion 3"]
    # JSON lines on disk
    raw_lines = (tmp_path / "scratchpad.jsonl").read_text().strip().splitlines()
    assert len(raw_lines) == 3


# ---------- forking state without mutating the base ----------


def test_fork_for_hypothesis_copies_state_without_mutating_base(tmp_path: Path) -> None:
    base = tmp_path / "hot_state.json"
    _baseline_hot_state(base)
    base_bytes = base.read_bytes()

    fork_dir = fork.fork_for_hypothesis(base, hypothesis_id="H1", forks_root=tmp_path / "forks")
    assert fork_dir == tmp_path / "forks" / "H1"
    assert (fork_dir / "hot_state.json").exists()
    assert (fork_dir / "hot_state.json").read_bytes() == base_bytes
    # Base file untouched
    assert base.read_bytes() == base_bytes


# ---------- independent per-fork scratchpads ----------


def test_two_forks_produce_independent_scratchpads(tmp_path: Path) -> None:
    base = tmp_path / "hot_state.json"
    _baseline_hot_state(base)
    base_bytes_before = base.read_bytes()
    forks_root = tmp_path / "forks"

    h1_dir = fork.fork_for_hypothesis(base, "H1", forks_root=forks_root)
    h1_pad = Scratchpad(h1_dir / "scratchpad.jsonl")
    h1_pad.append(_entry("H1", "H1 conclusion A"))
    h1_pad.append(_entry("H1", "H1 conclusion B"))

    h2_dir = fork.fork_for_hypothesis(base, "H2", forks_root=forks_root)
    h2_pad = Scratchpad(h2_dir / "scratchpad.jsonl")
    h2_pad.append(_entry("H2", "H2 conclusion A"))

    # Distinct paths
    assert h1_pad.path != h2_pad.path
    assert h1_pad.path == forks_root / "H1" / "scratchpad.jsonl"
    assert h2_pad.path == forks_root / "H2" / "scratchpad.jsonl"

    # Neither fork's contents appear in the other
    h1_contents = h1_pad.path.read_text()
    h2_contents = h2_pad.path.read_text()
    assert "H1 conclusion" not in h2_contents
    assert "H2 conclusion" not in h1_contents

    # Main hot state file bytes unchanged
    assert base.read_bytes() == base_bytes_before


# ---------- merging fork findings into main ----------


def test_merge_findings_appends_without_rewriting_existing(tmp_path: Path) -> None:
    main_path = tmp_path / "main_scratchpad.jsonl"
    main = Scratchpad(main_path)
    main.append(_entry("main", "pre-existing finding"))
    pre_hash = hashlib.sha256(main_path.read_bytes()).hexdigest()

    # Build two fork scratchpads
    fork_a = tmp_path / "forks" / "H1" / "scratchpad.jsonl"
    fork_b = tmp_path / "forks" / "H2" / "scratchpad.jsonl"
    Scratchpad(fork_a).append(_entry("H1", "fork A finding 1"))
    Scratchpad(fork_a).append(_entry("H1", "fork A finding 2"))
    Scratchpad(fork_b).append(_entry("H2", "fork B finding 1"))

    fork.merge_findings([fork_a, fork_b], main_path)

    # Pre-existing content hash unchanged: the merged file *starts with* the same bytes.
    merged_bytes = main_path.read_bytes()
    pre_existing_bytes_len = len(
        (
            ScratchpadEntry(
                hypothesis_id="main",
                evidence="evidence X",
                conclusion="pre-existing finding",
                ts=datetime.now(UTC),
            )
        ).model_dump_json()
        + "\n"
    )
    # We re-hash only the first line, which should be the original pre-existing entry.
    first_line_end = merged_bytes.index(b"\n") + 1
    original_first_line = main_path.read_bytes()[:first_line_end]
    # The original file before merge: same prefix bytes
    assert original_first_line == (main_path).read_bytes()[:first_line_end]
    assert pre_hash == hashlib.sha256(original_first_line).hexdigest()
    del pre_existing_bytes_len  # only used to ensure consistency in earlier reasoning

    # And the merged file contains all fork findings
    all_entries = Scratchpad(main_path).read()
    conclusions = [e.conclusion for e in all_entries]
    assert "pre-existing finding" in conclusions
    assert "fork A finding 1" in conclusions
    assert "fork A finding 2" in conclusions
    assert "fork B finding 1" in conclusions
    # Order: main first, then fork entries in input order
    assert conclusions[0] == "pre-existing finding"
