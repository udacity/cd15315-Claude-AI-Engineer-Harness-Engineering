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

# ----------------------------------------------------------------------------
# Schemas — passed verbatim to the Anthropic Messages API as the `tools` arg.
# ----------------------------------------------------------------------------

def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "lookup_policy",
        "description": (
            "Look up the insurance policy record (holder, coverage, deductible, status) by "
            "policy_id. Call this early, once the policy id is known, to check coverage."
        ),
        "input_schema": _obj(
            {"policy_id": {"type": "string", "description": "Policy identifier, e.g. POL-1001."}},
            ["policy_id"],
        ),
    },
    {
        "name": "record_claim_fact",
        "description": (
            "Record one normalized fact about the claim (e.g. incident_date, location, "
            "items_lost, injuries, estimated_cost). Call once per distinct fact as it arrives. "
            "Do not invent facts."
        ),
        "input_schema": _obj(
            {
                "field": {"type": "string", "description": "Fact name, snake_case."},
                "value": {"type": "string", "description": "Fact value as stated by the claimant."},
            },
            ["field", "value"],
        ),
    },
    {
        "name": "classify_claim",
        "description": (
            "Commit to a claim type with a confidence score and rationale. Call exactly once, "
            "after gathering facts and any needed clarification. Low confidence means the claim "
            "should be escalated rather than routed."
        ),
        "input_schema": _obj(
            {
                "claim_type": {"type": "string", "enum": CLAIM_TYPES},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string"},
            },
            ["claim_type", "confidence", "rationale"],
        ),
    },
    {
        "name": "assess_severity",
        "description": (
            "Commit to a severity bucket (low/medium/high) with a rationale based on dollar "
            "amount and injury cues. Call exactly once."
        ),
        "input_schema": _obj(
            {
                "severity": {"type": "string", "enum": SEVERITIES},
                "rationale": {"type": "string"},
            },
            ["severity", "rationale"],
        ),
    },
    {
        "name": "request_clarification",
        "description": (
            "Ask the claimant one clarifying question when the claim type is genuinely ambiguous. "
            "Name the candidate claim types in ambiguity_between. Ask once per missing piece of "
            "information. A reply of NO_RESPONSE means the claimant cannot answer: do not re-ask."
        ),
        "input_schema": _obj(
            {
                "question": {"type": "string"},
                "ambiguity_between": {
                    "type": "array",
                    "items": {"type": "string", "enum": CLAIM_TYPES},
                    "minItems": 2,
                },
            },
            ["question", "ambiguity_between"],
        ),
    },
    {
        "name": "route_to_adjuster",
        "description": (
            "Terminal tool. Route the claim to the adjuster queue for its claim type. Requires "
            "classify_claim and assess_severity to have been called. Use when confidence is at "
            "least 0.6. Call at most one terminal tool per claim."
        ),
        "input_schema": _obj(
            {
                "queue": {"type": "string", "enum": CLAIM_TYPES},
                "claim_summary": {"type": "string"},
            },
            ["queue", "claim_summary"],
        ),
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Terminal tool. Escalate the claim to a human when it cannot be routed safely "
            "(low confidence, unresolved ambiguity, missing information). Provide a complete "
            "structured_summary. Call at most one terminal tool per claim."
        ),
        "input_schema": _obj(
            {
                "reason": {"type": "string"},
                "structured_summary": _obj(
                    {
                        "policy_id": {"type": "string"},
                        "root_cause": {"type": "string"},
                        "candidate_claim_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": CLAIM_TYPES},
                        },
                        "case_facts": {"type": "object"},
                        "recommended_action": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    [
                        "policy_id",
                        "root_cause",
                        "candidate_claim_types",
                        "case_facts",
                        "recommended_action",
                        "confidence",
                    ],
                ),
            },
            ["reason", "structured_summary"],
        ),
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
    field_name = inp.get("field")
    value = inp.get("value")
    if not isinstance(field_name, str) or not isinstance(value, str):
        return _err("permanent", False, "field and value must both be strings")
    session.case_facts[field_name] = value
    return _ok(
        {"recorded": True, "field": field_name, "case_facts_count": len(session.case_facts)}
    )


def _t_classify_claim(session: ClaimSession, inp: dict[str, Any]) -> str:
    claim_type = inp.get("claim_type")
    confidence = inp.get("confidence")
    rationale = inp.get("rationale")
    if claim_type not in CLAIM_TYPES:
        return _err("permanent", False, f"claim_type must be one of {CLAIM_TYPES}")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        return _err("permanent", False, "confidence must be a number between 0 and 1")
    if not isinstance(rationale, str):
        return _err("permanent", False, "rationale must be a string")
    session.classification = {
        "claim_type": claim_type,
        "confidence": confidence,
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
    question = inp.get("question")
    ambiguity = inp.get("ambiguity_between")
    if not isinstance(question, str):
        return _err("permanent", False, "question must be a string")
    if not isinstance(ambiguity, list) or len(ambiguity) < 2:
        return _err("permanent", False, "ambiguity_between must list at least 2 candidates")
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
        return _err("permanent", False, "classify_claim must be called before routing")
    if session.severity is None:
        return _err("permanent", False, "assess_severity must be called before routing")
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


_ESCALATION_REQUIRED = [
    "policy_id",
    "root_cause",
    "candidate_claim_types",
    "case_facts",
    "recommended_action",
    "confidence",
]


def _t_escalate_to_human(session: ClaimSession, inp: dict[str, Any]) -> str:
    if session.terminal_called:
        return _err("permanent", False, "a terminal tool was already called for this claim")
    reason = inp.get("reason")
    summary = inp.get("structured_summary")
    if not isinstance(reason, str):
        return _err("permanent", False, "reason must be a string")
    if not isinstance(summary, dict):
        return _err("permanent", False, "structured_summary must be an object")
    missing = [k for k in _ESCALATION_REQUIRED if k not in summary]
    if missing:
        return _err("permanent", False, f"structured_summary missing fields: {', '.join(missing)}")
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
