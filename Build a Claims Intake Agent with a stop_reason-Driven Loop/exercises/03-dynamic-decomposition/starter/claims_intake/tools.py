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
    {
        "name": "request_clarification",
        "description": (
            "Ask the claimant ONE clarifying question to disambiguate the claim "
            "type or fill a critical missing fact. Use only when the claim type is "
            "genuinely ambiguous between two or more types. Returns the claimant's "
            "reply, or the literal string NO_RESPONSE if the claimant cannot answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "A single specific question"},
                "ambiguity_between": {
                    "type": "array",
                    "items": {"type": "string", "enum": CLAIM_TYPES},
                    "minItems": 2,
                    "description": "Candidate claim types the question is meant to distinguish",
                },
            },
            "required": ["question", "ambiguity_between"],
        },
    },
    {
        "name": "route_to_adjuster",
        "description": (
            "TERMINAL TOOL. Route this claim to the matching adjuster queue. "
            "Call this exactly once when classification confidence is at least "
            "0.6 and severity has been assessed. After this, your next response "
            "should be a brief confirmation and stop with end_turn."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {"type": "string", "enum": CLAIM_TYPES},
                "claim_summary": {
                    "type": "string",
                    "description": "Two-to-three sentence summary the adjuster will read first",
                },
            },
            "required": ["queue", "claim_summary"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "TERMINAL TOOL. Escalate this claim to a human reviewer when "
            "classification confidence is below 0.6 even after clarification, or "
            "when the claim cannot be routed safely (multiple plausible types, "
            "missing critical facts the claimant cannot supply, policy disputes). "
            "Call this exactly once. After this, your next response should be a "
            "brief confirmation and stop with end_turn."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Short reason: unresolved_ambiguity | low_confidence | missing_facts | policy_dispute | other",
                },
                "structured_summary": {
                    "type": "object",
                    "properties": {
                        "policy_id": {"type": "string"},
                        "root_cause": {"type": "string"},
                        "candidate_claim_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": CLAIM_TYPES},
                        },
                        "case_facts": {"type": "object"},
                        "recommended_action": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    },
                    "required": [
                        "policy_id",
                        "root_cause",
                        "candidate_claim_types",
                        "case_facts",
                        "recommended_action",
                        "confidence",
                    ],
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
    question = inp.get("question")
    candidates = inp.get("ambiguity_between")
    if not isinstance(question, str):
        return _err("permanent", False, "question must be a string")
    if not isinstance(candidates, list) or len(candidates) < 2:
        return _err("permanent", False, "ambiguity_between must list at least two candidate types")
    session.clarifications_asked.append({"question": question, "candidates": list(candidates)})

    # Match the question against the fixture's scripted responses.
    # Pattern matching is intentionally loose: a substring match on the
    # claimant's keyword is enough. If nothing matches, return NO_RESPONSE.
    qlow = question.lower()
    for pattern, reply in session.clarification_responses.items():
        if pattern.lower() in qlow:
            return _ok({"claimant_reply": reply})
    return _ok({"claimant_reply": "NO_RESPONSE"})


def _t_route_to_adjuster(session: ClaimSession, inp: dict[str, Any]) -> str:
    if session.terminal_called:
        return _err("permanent", False, "terminal tool already called this claim")
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


def _t_escalate_to_human(session: ClaimSession, inp: dict[str, Any]) -> str:
    if session.terminal_called:
        return _err("permanent", False, "terminal tool already called this claim")
    reason = inp.get("reason")
    summary = inp.get("structured_summary")
    if not isinstance(reason, str):
        return _err("permanent", False, "reason must be a string")
    if not isinstance(summary, dict):
        return _err("permanent", False, "structured_summary must be an object")
    required = {
        "policy_id",
        "root_cause",
        "candidate_claim_types",
        "case_facts",
        "recommended_action",
        "confidence",
    }
    missing = required - summary.keys()
    if missing:
        return _err("permanent", False, f"structured_summary missing fields: {sorted(missing)}")

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
