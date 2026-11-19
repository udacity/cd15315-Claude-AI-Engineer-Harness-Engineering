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
    recent_defect_hashes: list[str] = Field(..., max_length=MAX_RECENT_HASHES)
    current_shift_summary: str = ""
    active_alerts: list[str] = Field(default_factory=list)
    threshold_statuses: dict[str, str] = Field(default_factory=dict)

    def to_json_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> Self:
        return cls.model_validate_json(payload)

    @classmethod
    def from_path(cls, path: Path) -> Self:
        return cls.from_json_bytes(Path(path).read_bytes())

    def write_atomic(self, path: Path) -> None:
        path = Path(path)
        payload = self.to_json_bytes()
        if len(payload) > HOT_STATE_BYTE_BUDGET:
            raise ValueError(
                f"hot state {len(payload)} bytes exceeds budget {HOT_STATE_BYTE_BUDGET}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
