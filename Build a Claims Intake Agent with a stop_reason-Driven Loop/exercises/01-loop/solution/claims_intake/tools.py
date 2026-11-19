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

# TODO:Populate TOOL_SCHEMAS with the first four tool schemas. Each schema
# is a dict with "name", "description", and "input_schema". Tool descriptions are read by
# the model on every turn — write them as if you were teaching the model what each tool is
# for and *when* to call it. Categorical fields ("claim_type", "severity") must use
# Anthropic's tool-use `enum` shape against CLAIM_TYPES and SEVERITIES.
#
#   - lookup_policy(policy_id: str)
#     Returns the policy record. Used early in the conversation.
#   - record_claim_fact(field: str, value: str)
#     Records one normalized fact (incident_date, location, items_lost, ...).
#   - classify_claim(claim_type: enum CLAIM_TYPES, confidence: number in [0,1], rationale: str)
#     Commits the model to a claim type with a confidence score.
#   - assess_severity(severity: enum SEVERITIES, rationale: str)
#     Commits the model to a severity bucket.
#
# Later tools (request_clarification, route_to_adjuster, escalate_to_human) extend this list.
TOOL_SCHEMAS: list[dict[str, Any]] = []

# ----------------------------------------------------------------------------
# Errors — Graceful Tool Failure shape
# ----------------------------------------------------------------------------


def _err(category: str, retryable: bool, message: str) -> str:
    # TODO:Return a JSON string with these keys (the Graceful Tool Failure shape):
    #   is_error: True
    #   error_category: category   ("transient" or "permanent")
    #   is_retryable: retryable
    #   message: message
    # The shape is what tool_result content carries when the model needs to read an error
    # and adapt rather than crash the loop.
    return '{"is_error": true, "message": "TODO: _err not implemented"}'


def _ok(payload: dict[str, Any]) -> str:
    # TODO:Return json.dumps(payload). Tool results are always strings;
    # the model parses them on the next turn.
    return "{}"


# ----------------------------------------------------------------------------
# Tool implementations
# ----------------------------------------------------------------------------


def _t_lookup_policy(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO:Read inp["policy_id"]; if not a string, return a permanent error.
    # Look it up in session.policies; if missing, return a permanent error naming the id.
    # Otherwise return the policy dict via _ok(...).
    return _err("permanent", False, "TODO: _t_lookup_policy not implemented yet")


def _t_record_claim_fact(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO:Validate inp["field"] and inp["value"] are both strings; store
    # session.case_facts[field] = value; return _ok with {"recorded": True, "field": field,
    # "case_facts_count": len(session.case_facts)}.
    return _err("permanent", False, "TODO: _t_record_claim_fact not implemented yet")


def _t_classify_claim(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO:Validate claim_type (in CLAIM_TYPES), confidence (number in [0,1]),
    # rationale (string). Store session.classification = {claim_type, confidence, rationale}
    # and return _ok with the recorded values plus {"recorded": True}.
    return _err("permanent", False, "TODO: _t_classify_claim not implemented yet")


def _t_assess_severity(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO:Validate severity (in SEVERITIES) and rationale (string).
    # Store session.severity = {severity, rationale} and return _ok with the recorded
    # values plus {"recorded": True}.
    return _err("permanent", False, "TODO: _t_assess_severity not implemented yet")


def _t_request_clarification(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO:Implement the clarification dispatcher.
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
    # TODO:Implement the routing terminal tool.
    #   1. Guard against double-terminal: if session.terminal_called, return an error.
    #   2. Validate inp["queue"] is in CLAIM_TYPES and inp["claim_summary"] is a string.
    #   3. Require session.classification and session.severity to be set; otherwise error.
    #   4. Build the routing record (claim_id, policy_id, claim_type, severity, confidence,
    #      rationale, claim_summary, case_facts) and assign it to session.routing.
    #   5. Append the record to runs/<run>/queues/<queue>.jsonl via _append_jsonl.
    #   6. Return _ok({"routed": True, "queue": queue}).
    return _err("permanent", False, "TODO: _t_route_to_adjuster not implemented yet")


def _t_escalate_to_human(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO:Implement the escalation terminal tool.
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
