"""Hot-state schema and atomic disk I/O."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

MAX_RECENT_HASHES = 20
HOT_STATE_BYTE_BUDGET = 5_120


class HotState(BaseModel):
    """In-context shift state. Kept under ~5 KB so it fits in every prompt."""

    model_config = ConfigDict(frozen=True)

    # TODO: Declare the four required fields with the right types and constraints.
    # The state schema uses exactly these names:
    #   recent_defect_hashes: list[str], capped at MAX_RECENT_HASHES items.
    #     NOTE: In Pydantic v2 the list-length constraint is `max_length`.
    #     Older blog posts use `max_items` — that key was renamed and is silently
    #     ignored, so validation will appear to work but never enforce the cap.
    #   current_shift_summary: str
    #   active_alerts: list[str]
    #   threshold_statuses: dict[str, str]
    recent_defect_hashes: list[str] = Field(...)
    current_shift_summary: str = ""
    active_alerts: list[str] = Field(default_factory=list)
    threshold_statuses: dict[str, str] = Field(default_factory=dict)

    def to_json_bytes(self) -> bytes:
        # TODO: Serialize this model to UTF-8 JSON bytes. Pydantic v2 gives you
        # `self.model_dump_json()` for the JSON string; encode it as UTF-8.
        raise NotImplementedError

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> Self:
        # TODO: Parse JSON bytes back into a HotState instance.
        raise NotImplementedError

    @classmethod
    def from_path(cls, path: Path) -> Self:
        # TODO: Read the bytes at `path` and parse them into a HotState.
        raise NotImplementedError

    def write_atomic(self, path: Path) -> None:
        # TODO: Durably write `self.to_json_bytes()` to `path`.
        #
        # Requirements:
        #   1. Make sure the parent directory exists.
        #   2. Raise ValueError if the serialized payload is larger than
        #      HOT_STATE_BYTE_BUDGET — the budget is what forces SQL pre-filtering.
        #   3. Write to a tempfile in the *same* directory as `path`, flush + fsync,
        #      then swap it in with os.replace().
        #
        # Use os.replace, not os.rename. They behave the same on POSIX, but
        # os.rename fails on Windows when the destination already exists. The
        # whole point of an atomic write is that the destination *does* exist.
        raise NotImplementedError
