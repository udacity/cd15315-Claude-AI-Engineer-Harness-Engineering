"""Tests for the /deploy-check skill with context: fork and read-only allowed-tools."""

from pathlib import Path

import pytest

from ecommerce_team_config.skill import (
    body_has_branching_reality_note,
    body_has_check_entries,
    body_has_main_session_isolation_rationale,
    body_has_personal_customization_note,
    body_has_skill_vs_claude_md_rubric,
    load_skill,
)
from ecommerce_team_config.tool_allowlist import write_capable_tools


@pytest.fixture(scope="module")
def deploy_check_path(repo_root: Path) -> Path:
    return repo_root / ".claude" / "skills" / "deploy-check" / "SKILL.md"


def test_ac_04_01_exists_with_valid_frontmatter(deploy_check_path: Path) -> None:
    assert deploy_check_path.exists()
    skill = load_skill(deploy_check_path)
    assert isinstance(skill.frontmatter, dict) and skill.frontmatter


def test_ac_04_02_name_description_context_fork(deploy_check_path: Path) -> None:
    skill = load_skill(deploy_check_path)
    assert skill.frontmatter.get("name") == "deploy-check"
    desc = skill.frontmatter.get("description")
    assert isinstance(desc, str) and len(desc) >= 10
    assert skill.frontmatter.get("context") == "fork"


def test_ac_04_03_allowed_tools_read_only(deploy_check_path: Path) -> None:
    skill = load_skill(deploy_check_path)
    tools = skill.frontmatter.get("allowed-tools")
    assert tools, "allowed-tools frontmatter must be present"
    tool_list = tools if isinstance(tools, list) else [t.strip() for t in str(tools).split(",")]
    offenders = write_capable_tools(tool_list)
    assert not offenders, f"deploy-check must not allow write-capable tools, got {offenders}"


def test_ac_04_04_three_pre_deployment_checks(deploy_check_path: Path) -> None:
    skill = load_skill(deploy_check_path)
    checks = body_has_check_entries(skill.body)
    assert len(checks) >= 3, (
        f"Body must declare ≥3 pre-deployment checks with detection/pass/fail, got {len(checks)}"
    )
    for check in checks:
        assert check.has_detection, f"check {check.title!r} missing detection method"
        assert check.has_pass_criterion, f"check {check.title!r} missing pass criterion"
        assert check.has_fail_criterion, f"check {check.title!r} missing fail criterion"


def test_ac_04_05_rationale_cites_main_session_and_branching_reality(
    deploy_check_path: Path,
) -> None:
    skill = load_skill(deploy_check_path)
    assert body_has_main_session_isolation_rationale(skill.body), (
        "Rationale must explicitly state the goal is keeping verbose output out of the main session"
    )
    assert body_has_branching_reality_note(skill.body), (
        "Rationale must note context: fork is a Claude Code product feature analogous to "
        "the Branching Reality pattern"
    )


def test_ac_04_06_personal_customization_note(deploy_check_path: Path) -> None:
    skill = load_skill(deploy_check_path)
    assert body_has_personal_customization_note(skill.body), (
        "Body must note personal-customization via ~/.claude/skills/"
    )


def test_ac_04_07_skill_vs_claude_md_rubric(deploy_check_path: Path) -> None:
    skill = load_skill(deploy_check_path)
    assert body_has_skill_vs_claude_md_rubric(skill.body), (
        "Body must include a skill-vs-CLAUDE.md decision rubric explaining the on-demand/forked "
        "vs always-loaded tradeoff"
    )
