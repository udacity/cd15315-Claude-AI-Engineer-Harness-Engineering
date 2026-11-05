"""Structural checks on docs/plan-mode-vs-direct-execution.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PATH_TOKEN_RE = re.compile(r"`(src/[^`]+|docs/[^`]+|\.claude/[^`]+|tests?/[^`]+)`")
_REWORK_RE = re.compile(r"(prevent|avoid|prevents|avoids)\s+(costly\s+)?rework", re.IGNORECASE)
_ISOLATION_RE = re.compile(
    r"isolat\w*\s+verbose|verbose\s+discovery|out\s+of\s+the\s+main", re.IGNORECASE
)
_SCRATCHPAD_RE = re.compile(r"scratchpad", re.IGNORECASE)
_KNIGHT_WEBB_RE = re.compile(r"knight[- ]webb", re.IGNORECASE)
_PLAN_REVIEW_TALK_RE = re.compile(r"SWE\s+Is\s+Becoming\s+Plan\s+and\s+Review", re.IGNORECASE)
_CURRICULUM_RE = re.compile(r"curriculum|module\s+8|anchor[- ]talk", re.IGNORECASE)
_COMBINED_RE = re.compile(
    r"combin\w+\s+workflow|plan[- ]mode\s+(then|→|->|followed\s+by)\s+direct",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PlanModeSection:
    found: bool
    file_paths: list[str]
    cites_rework: bool


@dataclass(frozen=True)
class DirectExecutionSection:
    found: bool
    is_single_function: bool


@dataclass(frozen=True)
class ExploreSection:
    found: bool
    cites_isolation: bool
    cites_scratchpad: bool


def _section(doc_path: Path, heading_pattern: str) -> str | None:
    text = doc_path.read_text(encoding="utf-8")
    # Allow optional numbering prefix like `## 1.` or `### 2)` before the heading text.
    # Wrap the heading_pattern in a non-capturing group so a top-level `|` inside it does
    # not split the surrounding regex.
    pattern = re.compile(
        rf"(##+\s+(?:\d+[\.\)]\s+)?(?:{heading_pattern}).*?)(?=\n##\s|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1) if match else None


def _paths_in(section_text: str) -> list[str]:
    return _PATH_TOKEN_RE.findall(section_text)


def has_plan_mode_example(doc_path: Path) -> PlanModeSection:
    section = _section(doc_path, r"plan[- ]?mode")
    if section is None:
        return PlanModeSection(found=False, file_paths=[], cites_rework=False)
    return PlanModeSection(
        found=True,
        file_paths=_paths_in(section),
        cites_rework=bool(_REWORK_RE.search(section)),
    )


def has_direct_execution_example(doc_path: Path) -> DirectExecutionSection:
    section = _section(doc_path, r"direct[- ]?execution")
    if section is None:
        return DirectExecutionSection(found=False, is_single_function=False)
    # The exercise requires a "well-scoped single-function" change. The prose mention is the
    # real signal; we don't care whether the example incidentally name-drops a schema
    # file alongside the function's home file.
    mentions_single = bool(re.search(r"\bone\s+(function|handler|check|line)\b", section, re.I))
    return DirectExecutionSection(found=True, is_single_function=mentions_single)


def has_explore_example(doc_path: Path) -> ExploreSection:
    section = _section(doc_path, r"explore")
    if section is None:
        return ExploreSection(found=False, cites_isolation=False, cites_scratchpad=False)
    return ExploreSection(
        found=True,
        cites_isolation=bool(_ISOLATION_RE.search(section)),
        cites_scratchpad=bool(_SCRATCHPAD_RE.search(section)),
    )


def has_knight_webb_curriculum_citation(doc_path: Path) -> bool:
    text = doc_path.read_text(encoding="utf-8")
    return (
        bool(_KNIGHT_WEBB_RE.search(text))
        and bool(_PLAN_REVIEW_TALK_RE.search(text))
        and bool(_CURRICULUM_RE.search(text))
    )


def has_combined_workflow_example(doc_path: Path) -> bool:
    text = doc_path.read_text(encoding="utf-8")
    section = _section(doc_path, r"combined[- ]?workflow|plan[- ]?then[- ]?execute")
    return bool(_COMBINED_RE.search(text)) and section is not None


def cited_file_paths(doc_path: Path) -> list[str]:
    text = doc_path.read_text(encoding="utf-8")
    return sorted(set(_PATH_TOKEN_RE.findall(text)))
