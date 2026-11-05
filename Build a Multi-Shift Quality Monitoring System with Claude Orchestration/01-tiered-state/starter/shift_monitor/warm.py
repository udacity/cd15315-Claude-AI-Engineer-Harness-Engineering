"""Warm tier: SQLite-backed defect store with indexed `defects_since` query."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

# TODO: Build the schema. Three pieces matter:
#   1. A `defects` table with columns
#      (id TEXT PRIMARY KEY, ts TEXT NOT NULL, shift TEXT NOT NULL,
#       component TEXT NOT NULL, severity TEXT NOT NULL, description TEXT NOT NULL).
#   2. A named index `idx_defects_shift_ts` on `(shift, ts)`.
#   3. A named index `idx_defects_ts` on `(ts)`. `defects_since` filters on `ts`
#      without naming a `shift`, so this is the index SQLite can use for it.
#      Without it the query plan is a full `SCAN defects` and the index test fails.
SCHEMA_SQL = """
"""


class WarmStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        # TODO: Make sure the parent directory exists, open a connection, and
        # run SCHEMA_SQL against it.
        raise NotImplementedError

    def insert_many(self, rows: Iterable[Mapping[str, Any]]) -> None:
        # TODO: Bulk-insert defect rows. Use INSERT OR REPLACE so the same fixture
        # can be loaded twice without errors. Each row is a mapping with keys
        # id, ts, shift, component, severity, description.
        raise NotImplementedError

    def count(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM defects")
            return int(cur.fetchone()[0])

    def fetch_by_id(self, defect_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM defects WHERE id = ?", (defect_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def column_names(self, table: str) -> list[str]:
        with self._connect() as conn:
            cur = conn.execute(f"PRAGMA table_info({table})")
            return [r["name"] for r in cur.fetchall()]

    def has_index_on(self, table: str, columns: tuple[str, ...]) -> bool:
        with self._connect() as conn:
            indexes = conn.execute(f"PRAGMA index_list({table})").fetchall()
            for idx in indexes:
                cols = conn.execute(f"PRAGMA index_info({idx['name']})").fetchall()
                if tuple(c["name"] for c in cols) == columns:
                    return True
            return False

    def defects_since(self, since_ts: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return defects with ts > since_ts, newest first, up to limit rows.

        SQL-side filtering only — no Python-side filtering of severity,
        component, or time.
        """
        # TODO: Run an indexed SELECT against the defects table with `WHERE ts > ?`
        # ORDER BY ts DESC LIMIT ?, parameterised. Do not pull the whole table
        # into Python and filter in a list comprehension.
        raise NotImplementedError

    def explain_defects_since(self, since_ts: str, limit: int = 50) -> list[tuple[Any, ...]]:
        # TODO: Return the rows that `EXPLAIN QUERY PLAN` produces for the
        # same SELECT as defects_since. Each row is (id, parent, notused, detail);
        # callers will check the index name shows up in the `detail` column.
        raise NotImplementedError

    def top_components_for_month(self, year: int, month: int, n: int = 3) -> list[tuple[str, int]]:
        # TODO: Return the top-N components for a given year+month, as
        # (component, count) pairs, ordered by count DESC then component ASC.
        # Use a LIKE filter on the `ts` column to scope by month.
        raise NotImplementedError

    def count_for_month(self, year: int, month: int) -> int:
        # TODO: Return the total defect count for the given year+month.
        raise NotImplementedError
