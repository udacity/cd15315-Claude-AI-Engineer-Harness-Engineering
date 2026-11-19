"""Tool schemas and dispatcher.

Seven tools, registered with Anthropic tool-use shape. The dispatcher returns
serialized JSON strings to be wrapped as `tool_result` content. Errors follow
the Playbook "Graceful Tool Failure" shape:

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
ESCALATION_REQUIRED_KEYS = (
    "policy_id",
    "root_cause",
    "candidate_claim_types",
    "case_facts",
    "recommended_action",
    "confidence",
)

# ----------------------------------------------------------------------------
# Schemas — passed verbatim to the Anthropic Messages API as the `tools` arg.
# ----------------------------------------------------------------------------

# TODO: Populate TOOL_SCHEMAS with the first four tool schemas. Each schema
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
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "lookup_policy",
        "description": (
            "Look up the insurance policy record (holder, coverage, deductible, status) for a "
            "policy id. Call this early in the conversation, before classifying, so coverage "
            "and policy status can inform your decision. Returns a not-found error for unknown ids."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_id": {"type": "string", "description": "The policy identifier, e.g. 'POL-1001'."},
            },
            "required": ["policy_id"],
        },
    },
    {
        "name": "record_claim_fact",
        "description": (
            "Record one normalized fact about the claim in the case file (for example "
            "incident_date, location, items_lost, estimated_amount). Call once per fact as you "
            "extract them from the claimant's narrative; re-recording a field overwrites it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "description": "Snake_case fact name, e.g. 'incident_date'."},
                "value": {"type": "string", "description": "The normalized fact value."},
            },
            "required": ["field", "value"],
        },
    },
    {
        "name": "classify_claim",
        "description": (
            "Commit to a claim type with a confidence score and rationale. Call this once you "
            "have enough facts to decide; use a low confidence if the claim is ambiguous. "
            "Must be called before routing the claim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_type": {"type": "string", "enum": CLAIM_TYPES, "description": "The claim category."},
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Your confidence in the classification, from 0 to 1.",
                },
                "rationale": {"type": "string", "description": "Brief justification citing recorded facts."},
            },
            "required": ["claim_type", "confidence", "rationale"],
        },
    },
    {
        "name": "assess_severity",
        "description": (
            "Commit to a severity bucket (low, medium, high) with a rationale. Call this after "
            "the damage or loss is understood and before routing the claim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": SEVERITIES, "description": "The severity bucket."},
                "rationale": {"type": "string", "description": "Brief justification for the severity."},
            },
            "required": ["severity", "rationale"],
        },
    },
    {
        "name": "request_clarification",
        "description": (
            "Ask the claimant one focused follow-up question when the claim type is ambiguous "
            "between two or more candidates. Call this before classify_claim, not after. Returns "
            "the claimant's reply, or NO_RESPONSE if they cannot answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The single question to ask the claimant."},
                "ambiguity_between": {
                    "type": "array",
                    "items": {"type": "string", "enum": CLAIM_TYPES},
                    "minItems": 2,
                    "description": "The claim types the answer would help choose between.",
                },
            },
            "required": ["question", "ambiguity_between"],
        },
    },
    {
        "name": "route_to_adjuster",
        "description": (
            "Terminal tool: send the claim to an adjuster queue. Call when you are confident "
            "(roughly 0.6 or higher) and both classify_claim and assess_severity have been "
            "called. Exactly one of route_to_adjuster or escalate_to_human must be called per claim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {"type": "string", "enum": CLAIM_TYPES, "description": "Destination queue."},
                "claim_summary": {"type": "string", "description": "Short summary for the adjuster."},
            },
            "required": ["queue", "claim_summary"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Terminal tool: hand the claim to a human reviewer when it cannot be resolved with "
            "the facts on hand (low confidence, unresolved ambiguity, missing information). "
            "Exactly one of route_to_adjuster or escalate_to_human must be called per claim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Short reason code, e.g. 'unresolved_ambiguity'."},
                "structured_summary": {
                    "type": "object",
                    "properties": {
                        "policy_id": {"type": "string"},
                        "root_cause": {"type": "string", "description": "Why the claim cannot be resolved."},
                        "candidate_claim_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": CLAIM_TYPES},
                        },
                        "case_facts": {"type": "object", "description": "Facts gathered so far."},
                        "recommended_action": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": list(ESCALATION_REQUIRED_KEYS),
                },
            },
            "required": ["reason", "structured_summary"],
        },
    },
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
    policy_id = inp.get("policy_id")
    if not isinstance(policy_id, str):
        return _err("permanent", False, "policy_id must be a string")
    policy = session.policies.get(policy_id)
    if policy is None:
        return _err("permanent", False, f"policy {policy_id} not found")
    return _ok(policy)


def _t_record_claim_fact(session: ClaimSession, inp: dict[str, Any]) -> str:
    field = inp.get("field")
    value = inp.get("value")
    if not isinstance(field, str) or not field:
        return _err("permanent", False, "field must be a non-empty string")
    if not isinstance(value, str):
        return _err("permanent", False, "value must be a string")
    session.case_facts[field] = value
    return _ok({"recorded": True, "field": field, "case_facts_count": len(session.case_facts)})


def _t_classify_claim(session: ClaimSession, inp: dict[str, Any]) -> str:
    claim_type = inp.get("claim_type")
    confidence = inp.get("confidence")
    rationale = inp.get("rationale")
    if claim_type not in CLAIM_TYPES:
        return _err("permanent", False, f"claim_type must be one of {CLAIM_TYPES}")
    # bool is a subclass of int; reject it explicitly.
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return _err("permanent", False, "confidence must be a number between 0 and 1")
    if not 0 <= confidence <= 1:
        return _err("permanent", False, "confidence must be between 0 and 1")
    if not isinstance(rationale, str):
        return _err("permanent", False, "rationale must be a string")
    session.classification = {"claim_type": claim_type, "confidence": confidence, "rationale": rationale}
    return _ok({**session.classification, "recorded": True})


def _t_assess_severity(session: ClaimSession, inp: dict[str, Any]) -> str:
    severity = inp.get("severity")
    rationale = inp.get("rationale")
    if severity not in SEVERITIES:
        return _err("permanent", False, f"severity must be one of {SEVERITIES}")
    if not isinstance(rationale, str):
        return _err("permanent", False, "rationale must be a string")
    session.severity = {"severity": severity, "rationale": rationale}
    return _ok({**session.severity, "recorded": True})


def _t_request_clarification(session: ClaimSession, inp: dict[str, Any]) -> str:
    question = inp.get("question")
    ambiguity = inp.get("ambiguity_between")
    if not isinstance(question, str) or not question.strip():
        return _err("permanent", False, "question must be a non-empty string")
    if not isinstance(ambiguity, list) or len(ambiguity) < 2:
        return _err("permanent", False, "ambiguity_between must be a list of at least 2 entries")
    session.clarifications_asked.append({"question": question, "ambiguity_between": ambiguity})
    lowered = question.lower()
    for key, reply in session.clarification_responses.items():
        if key.lower() in lowered:
            return _ok({"claimant_reply": reply})
    return _ok({"claimant_reply": "NO_RESPONSE"})


def _t_route_to_adjuster(session: ClaimSession, inp: dict[str, Any]) -> str:
    if session.terminal_called:
        return _err("permanent", False, "a terminal tool was already called for this claim")
    queue = inp.get("queue")
    summary = inp.get("claim_summary")
    if queue not in CLAIM_TYPES:
        return _err("permanent", False, f"queue must be one of {CLAIM_TYPES}")
    if not isinstance(summary, str):
        return _err("permanent", False, "claim_summary must be a string")
    if session.classification is None:
        return _err("permanent", False, "classify_claim must be called before route_to_adjuster")
    if session.severity is None:
        return _err("permanent", False, "assess_severity must be called before route_to_adjuster")
    record = {
        "claim_id": session.claim_id,
        "policy_id": session.policy_id,
        "claim_type": session.classification["claim_type"],
        "severity": session.severity["severity"],
        "confidence": session.classification["confidence"],
        "rationale": session.classification["rationale"],
        "claim_summary": summary,
        "case_facts": dict(session.case_facts),
    }
    session.routing = record
    _append_jsonl(session.run_dir / "queues" / f"{queue}.jsonl", record)
    return _ok({"routed": True, "queue": queue})


def _t_escalate_to_human(session: ClaimSession, inp: dict[str, Any]) -> str:
    if session.terminal_called:
        return _err("permanent", False, "a terminal tool was already called for this claim")
    reason = inp.get("reason")
    summary = inp.get("structured_summary")
    if not isinstance(reason, str):
        return _err("permanent", False, "reason must be a string")
    if not isinstance(summary, dict):
        return _err("permanent", False, "structured_summary must be an object")
    missing = [k for k in ESCALATION_REQUIRED_KEYS if k not in summary]
    if missing:
        return _err("permanent", False, f"structured_summary missing required fields: {missing}")
    record = {
        "claim_id": session.claim_id,
        "policy_id": session.policy_id,
        "reason": reason,
        **summary,
        "case_facts_at_escalation": dict(session.case_facts),
    }
    session.escalation = record
    _append_jsonl(session.run_dir / "escalations.jsonl", record)
    return _ok({"escalated": True})


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
