"""Tests for the plan mode vs direct execution decision doc + Explore subagent guidance."""

from pathlib import Path

import pytest

from ecommerce_team_config.plan_mode_doc import (
    cited_file_paths,
    has_combined_workflow_example,
    has_direct_execution_example,
    has_explore_example,
    has_knight_webb_curriculum_citation,
    has_plan_mode_example,
)


@pytest.fixture(scope="module")
def doc_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "plan-mode-vs-direct-execution.md"


def test_ac_05_01_doc_exists(doc_path: Path) -> None:
    assert doc_path.exists()


def test_ac_05_02_plan_mode_example_three_files_and_rework_phrasing(doc_path: Path) -> None:
    section = has_plan_mode_example(doc_path)
    assert section.found, "Plan-mode example section must exist"
    assert len(section.file_paths) >= 3, (
        f"Plan-mode example must touch ≥3 files, lists {section.file_paths}"
    )
    assert section.cites_rework, (
        "Plan-mode reasoning must explicitly cite 'prevent costly rework' or equivalent"
    )


def test_ac_05_03_direct_execution_example(doc_path: Path) -> None:
    section = has_direct_execution_example(doc_path)
    assert section.found, "Direct-execution example section must exist"
    assert section.is_single_function, (
        "Direct-execution example must target a single well-scoped function"
    )


def test_ac_05_04_explore_example_with_scratchpad(doc_path: Path) -> None:
    section = has_explore_example(doc_path)
    assert section.found, "Explore subagent example section must exist"
    assert section.cites_isolation, (
        "Explore example must reference isolating verbose discovery output"
    )
    assert section.cites_scratchpad, (
        "Explore example must reference the scratchpad pattern"
    )


def test_ac_05_05_knight_webb_curriculum_citation(doc_path: Path) -> None:
    assert has_knight_webb_curriculum_citation(doc_path), (
        "Doc must cite the Knight-Webb 'SWE Is Becoming Plan and Review' anchor talk"
    )


def test_ac_05_06_all_cited_file_paths_exist(doc_path: Path, repo_root: Path) -> None:
    missing = [p for p in cited_file_paths(doc_path) if not (repo_root / p).exists()]
    assert not missing, f"Doc cites file paths that don't exist in the scaffold: {missing}"


def test_ac_05_07_combined_workflow_example(doc_path: Path) -> None:
    assert has_combined_workflow_example(doc_path), (
        "Doc must contain a combined-workflow example (plan-mode investigation → direct execution)"
    )
