"""Static checks on the fixture set and the policy file."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "data" / "policies.json"
FIXTURE_DIR = ROOT / "fixtures" / "claims"

EXPECTED_CLAIM_TYPES = {"property_damage", "theft", "liability", "auto"}
EXPECTED_SEVERITIES = {"low", "medium", "high"}


def test_policies_file_loads_and_covers_all_claim_types() -> None:
    policies = json.loads(POLICIES.read_text())
    assert len(policies) >= 6
    covered: set[str] = set()
    for pol in policies.values():
        assert pol["status"] == "active"
        covered.update(pol["coverage"])
    assert EXPECTED_CLAIM_TYPES.issubset(covered), (
        f"policies do not collectively cover all four claim types: missing {EXPECTED_CLAIM_TYPES - covered}"
    )


def _load_fixtures() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(FIXTURE_DIR.glob("*.json"))]


def test_eight_fixtures_exist() -> None:
    assert len(_load_fixtures()) == 8


def test_every_fixture_references_a_known_policy() -> None:
    policies = json.loads(POLICIES.read_text())
    for fx in _load_fixtures():
        assert fx["policy_id"] in policies, f"{fx['claim_id']} references unknown policy {fx['policy_id']}"


def test_fixture_outcome_distribution_meets_targets() -> None:
    fixtures = _load_fixtures()
    routed = [f for f in fixtures if f["expected_outcome"] == "routed"]
    escalated = [f for f in fixtures if f["expected_outcome"] == "escalated"]
    assert len(routed) >= 6, "at least 6 fixtures must terminate in routing"
    assert len(escalated) >= 1, "at least 1 fixture must terminate in escalation"


def test_routed_fixtures_cover_all_four_types_and_all_severities() -> None:
    routed = [f for f in _load_fixtures() if f["expected_outcome"] == "routed"]
    types = {f["expected_type"] for f in routed}
    sevs = {f["expected_severity"] for f in routed}
    assert EXPECTED_CLAIM_TYPES.issubset(types), f"missing routed types: {EXPECTED_CLAIM_TYPES - types}"
    assert EXPECTED_SEVERITIES.issubset(sevs), f"missing severities: {EXPECTED_SEVERITIES - sevs}"


def test_fixture_schemas_are_consistent() -> None:
    for fx in _load_fixtures():
        assert isinstance(fx["claim_id"], str)
        assert isinstance(fx["policy_id"], str)
        assert isinstance(fx["initial_message"], str) and len(fx["initial_message"]) > 50
        assert isinstance(fx["clarification_responses"], dict)
        assert fx["expected_outcome"] in {"routed", "escalated"}
        if fx["expected_outcome"] == "routed":
            assert fx["expected_type"] in EXPECTED_CLAIM_TYPES
            assert fx["expected_severity"] in EXPECTED_SEVERITIES
        else:
            assert fx["expected_type"] is None


def test_ambiguous_fixtures_have_clarification_scripts() -> None:
    for fx in _load_fixtures():
        if fx.get("ambiguous") and fx["expected_outcome"] == "routed":
            assert fx["clarification_responses"], (
                f"{fx['claim_id']} is ambiguous but ships with no clarification_responses — "
                "the agent will get NO_RESPONSE and may fail to classify"
            )


def test_claim_06_is_the_escalation_fixture() -> None:
    """claim_06 is referenced by name; lock it in."""
    fx = json.loads((FIXTURE_DIR / "claim_06_low_confidence_escalation.json").read_text())
    assert fx["expected_outcome"] == "escalated"
    assert fx["clarification_responses"], "claim_06 must provide clarification responses"
