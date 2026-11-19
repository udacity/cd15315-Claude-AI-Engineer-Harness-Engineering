"""Tool schemas and dispatcher.

Seven tools, registered with Anthropic tool-use shape. The dispatcher returns
serialized JSON strings to be wrapped as `tool_result` content. Errors follow
the "Graceful Tool Failure" shape:

    {"is_error": true,
     "error_category": "transient"|"permanent",
     "is_retryable": bool,
     "message": "..."}

Errors are never raised to the loop.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claims_intake.session import ClaimSession

CLAIM_TYPES = ["property_damage", "theft", "liability", "auto"]
SEVERITIES = ["low", "medium", "high"]

# ----------------------------------------------------------------------------
# Schemas — passed verbatim to the Anthropic Messages API as the `tools` arg.
# ----------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "lookup_policy",
        "description": (
            "Look up a policyholder's coverage record. Use this early in the "
            "conversation to confirm the policy exists, what is covered, and the "
            "deductible. Returns coverage, deductible, status, and policy_holder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_id": {"type": "string", "description": "Policy identifier, e.g. POL-1001"}
            },
            "required": ["policy_id"],
        },
    },
    {
        "name": "record_claim_fact",
        "description": (
            "Record one normalized fact extracted from the claimant's statements "
            "(e.g., incident_date, location, description, items_lost, injury_party). "
            "Call once per fact. Facts accumulate into the case file used by routing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": "Snake_case field name, e.g. incident_date or location",
                },
                "value": {"type": "string", "description": "The fact as a short string"},
            },
            "required": ["field", "value"],
        },
    },
    {
        "name": "classify_claim",
        "description": (
            "Commit to a claim type with a confidence score and rationale. Call "
            "this exactly once per claim, after enough facts and clarifications "
            "have been gathered. If confidence is below 0.6, prefer escalate_to_human."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_type": {"type": "string", "enum": CLAIM_TYPES},
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "0.0 = no idea; 1.0 = certain",
                },
                "rationale": {
                    "type": "string",
                    "description": "One sentence explaining why this type fits the facts",
                },
            },
            "required": ["claim_type", "confidence", "rationale"],
        },
    },
    {
        "name": "assess_severity",
        "description": (
            "Commit to a severity bucket with a rationale. Call this exactly once "
            "per claim, after classification. Severity reflects damage magnitude, "
            "injury severity, and policy coverage limits."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": SEVERITIES},
                "rationale": {"type": "string"},
            },
            "required": ["severity", "rationale"],
        },
    },
    # TODO: Add three more tool schemas to this list.
    #
    #   - request_clarification(question: str, ambiguity_between: list of >=2 CLAIM_TYPES)
    #     Ask the claimant ONE clarifying question. Returns the scripted claimant reply,
    #     or the literal string "NO_RESPONSE" if nothing matches.
    #
    #   - route_to_adjuster(queue: enum CLAIM_TYPES, claim_summary: str)
    #     TERMINAL TOOL. The agent picks this when classification confidence is >= 0.6
    #     and severity has been assessed.
    #
    #   - escalate_to_human(reason: str, structured_summary: dict)
    #     TERMINAL TOOL. The agent picks this when the claim cannot be routed safely.
    #     structured_summary requires: policy_id, root_cause, candidate_claim_types,
    #     case_facts, recommended_action, confidence.
]

# ----------------------------------------------------------------------------
# Errors — Graceful Tool Failure shape
# ----------------------------------------------------------------------------


def _err(category: str, retryable: bool, message: str) -> str:
    return json.dumps(
        {
            "is_error": True,
            "error_category": category,
            "is_retryable": retryable,
            "message": message,
        }
    )


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


# ----------------------------------------------------------------------------
# Tool implementations
# ----------------------------------------------------------------------------


def _t_lookup_policy(session: ClaimSession, inp: dict[str, Any]) -> str:
    pid = inp.get("policy_id")
    if not isinstance(pid, str):
        return _err("permanent", False, "policy_id must be a string")
    policy = session.policies.get(pid)
    if policy is None:
        return _err("permanent", False, f"policy_id {pid!r} not found")
    return _ok(policy)


def _t_record_claim_fact(session: ClaimSession, inp: dict[str, Any]) -> str:
    field = inp.get("field")
    value = inp.get("value")
    if not isinstance(field, str) or not isinstance(value, str):
        return _err("permanent", False, "field and value must both be strings")
    session.case_facts[field] = value
    return _ok({"recorded": True, "field": field, "case_facts_count": len(session.case_facts)})


def _t_classify_claim(session: ClaimSession, inp: dict[str, Any]) -> str:
    claim_type = inp.get("claim_type")
    confidence = inp.get("confidence")
    rationale = inp.get("rationale")
    if claim_type not in CLAIM_TYPES:
        return _err("permanent", False, f"claim_type must be one of {CLAIM_TYPES}")
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        return _err("permanent", False, "confidence must be a number in [0,1]")
    if not isinstance(rationale, str):
        return _err("permanent", False, "rationale must be a string")
    session.classification = {
        "claim_type": claim_type,
        "confidence": float(confidence),
        "rationale": rationale,
    }
    return _ok({"recorded": True, **session.classification})


def _t_assess_severity(session: ClaimSession, inp: dict[str, Any]) -> str:
    severity = inp.get("severity")
    rationale = inp.get("rationale")
    if severity not in SEVERITIES:
        return _err("permanent", False, f"severity must be one of {SEVERITIES}")
    if not isinstance(rationale, str):
        return _err("permanent", False, "rationale must be a string")
    session.severity = {"severity": severity, "rationale": rationale}
    return _ok({"recorded": True, **session.severity})


def _t_request_clarification(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Implement the clarification dispatcher.
    #   1. Validate inp["question"] is a string and inp["ambiguity_between"] is a list of
    #      at least 2 entries; otherwise return _err("permanent", False, ...).
    #   2. Record the asked clarification in session.clarifications_asked (so the runner
    #      can count it).
    #   3. Substring-match the question (case-insensitive) against the keys in
    #      session.clarification_responses; if any key appears in the question, return
    #      _ok({"claimant_reply": <the matching reply>}).
    #   4. Otherwise return _ok({"claimant_reply": "NO_RESPONSE"}).
    return _err("permanent", False, "TODO: _t_request_clarification not implemented yet")


def _t_route_to_adjuster(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Implement the routing terminal tool.
    #   1. Guard against double-terminal: if session.terminal_called, return an error.
    #   2. Validate inp["queue"] is in CLAIM_TYPES and inp["claim_summary"] is a string.
    #   3. Require session.classification and session.severity to be set; otherwise error.
    #   4. Build the routing record (claim_id, policy_id, claim_type, severity, confidence,
    #      rationale, claim_summary, case_facts) and assign it to session.routing.
    #   5. Append the record to runs/<run>/queues/<queue>.jsonl via _append_jsonl.
    #   6. Return _ok({"routed": True, "queue": queue}).
    return _err("permanent", False, "TODO: _t_route_to_adjuster not implemented yet")


def _t_escalate_to_human(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Implement the escalation terminal tool.
    #   1. Guard against double-terminal: if session.terminal_called, return an error.
    #   2. Validate inp["reason"] is a string and inp["structured_summary"] is a dict
    #      containing all required keys: policy_id, root_cause, candidate_claim_types,
    #      case_facts, recommended_action, confidence. Return an error listing any missing
    #      fields by name.
    #   3. Build the escalation record (claim_id, policy_id, reason, **structured_summary,
    #      case_facts_at_escalation) and assign it to session.escalation.
    #   4. Append it to runs/<run>/escalations.jsonl via _append_jsonl.
    #   5. Return _ok({"escalated": True}).
    return _err("permanent", False, "TODO: _t_escalate_to_human not implemented yet")


# ----------------------------------------------------------------------------
# Dispatcher
# ----------------------------------------------------------------------------


_DISPATCH = {
    "lookup_policy": _t_lookup_policy,
    "record_claim_fact": _t_record_claim_fact,
    "classify_claim": _t_classify_claim,
    "assess_severity": _t_assess_severity,
    "request_clarification": _t_request_clarification,
    "route_to_adjuster": _t_route_to_adjuster,
    "escalate_to_human": _t_escalate_to_human,
}


def make_executor(session: ClaimSession) -> Executor:
    """Return a ToolExecutor callable bound to this session."""

    def execute(name: str, tool_input: dict[str, Any]) -> str:
        handler = _DISPATCH.get(name)
        if handler is None:
            return _err("permanent", False, f"unknown tool: {name}")
        try:
            return handler(session, tool_input)
        except Exception as exc:
            # Defensive: anything raised inside a handler becomes a graceful error,
            # never crashes the loop.
            return _err("transient", True, f"{type(exc).__name__}: {exc}")

    return execute


# Type alias for clarity; the loop only sees a Callable.
Executor = Any


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
