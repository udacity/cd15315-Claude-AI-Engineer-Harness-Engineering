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

    recent_defect_hashes: list[str] = Field(max_length=MAX_RECENT_HASHES)
    current_shift_summary: str
    active_alerts: list[str]
    threshold_statuses: dict[str, str]

    def to_json_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> Self:
        return cls.model_validate_json(payload)

    @classmethod
    def from_path(cls, path: Path) -> Self:
        return cls.from_json_bytes(path.read_bytes())

    def write_atomic(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_json_bytes()
        if len(payload) > HOT_STATE_BYTE_BUDGET:
            raise ValueError(
                f"hot state {len(payload)} bytes exceeds {HOT_STATE_BYTE_BUDGET}-byte budget"
            )
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, delete=False, prefix=".hot_state.", suffix=".tmp"
        ) as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)
