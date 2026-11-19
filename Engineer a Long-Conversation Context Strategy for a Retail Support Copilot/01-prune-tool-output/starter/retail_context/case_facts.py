"""Case-facts extraction into a persistent block at the top of context.

Extraction is LLM-driven: one Claude call against the full transcript that returns
strict JSON for the 12 required fields. This is commonly called a *scratchpad* — same
concept, different word: a dense structured block that survives compression and is
placed at the top boundary of context so the model can recover transactional facts
without scanning thousands of tokens of narrative.

Missing-field behavior raises `CaseFactExtractionError` listing the gaps — silent
null-fill is forbidden.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from retail_context.client import complete_with_system, get_model
from retail_context.transcript import Transcript

# TODO (Exercise 2): Replace with the 12-field contract for the case-facts block.
# Order matters — the to_markdown() rendering uses this order so the block is
# reviewer-readable and the model can re-find a value by name. Each name appears
# verbatim in the extraction system prompt as the JSON key the LLM must return.
#
# Required fields (12 total): customer_id; refund_order_id, refund_amount_usd,
# refund_status; subscription_id, subscription_plan, subscription_cancel_reason,
# subscription_status; active_payment_method_last4, new_payment_method_last4,
# payment_update_failure_code, payment_update_status.
REQUIRED_FIELDS: tuple[str, ...] = ()


# TODO (Exercise 2): Replace with a dataclass that carries the 12 fields above
# with explicit Python types (str for IDs / status tokens / last4 strings,
# float for refund_amount_usd). Then implement to_markdown(self) -> str so the
# block renders with a level-1 `# Case Facts` header and the four groups
# (Customer / Refund (resolved) / Subscription (resolved) / Payment update
# (active)) as bold inline labels. The rendering is part of the contract:
# fixed key order, bold group labels, reviewer-readable.
@dataclass
class CaseFacts:
    def to_markdown(self) -> str:
        raise NotImplementedError("Exercise 2: render the 12-field block as Markdown")


class CaseFactExtractionError(ValueError):
    def __init__(self, missing: list[str], raw: dict[str, Any]):
        super().__init__(f"case-facts extraction missing required fields: {missing}")
        self.missing = missing
        self.raw = raw


# TODO (Exercise 2): Replace with the system prompt that drives the extraction.
# The prompt must require Claude to return EXACTLY one JSON object with the
# 12 REQUIRED_FIELDS as keys, with the right types (refund_amount_usd is a
# number, last4 are zero-padded strings, status tokens preserved verbatim).
# Missing fields are null — DO NOT invent. Output is JSON only — no prose,
# no markdown, no code fences. The prompt is reviewed for its strict-schema
# intent; the reviewer reads it to decide whether following it would reliably
# produce a parseable JSON with every required field.
_SYSTEM_PROMPT = ""


def _parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.rstrip().endswith("```"):
            raw = raw.rsplit("```", 1)[0]
    return json.loads(raw)


def extract(
    transcript: Transcript,
    *,
    model: str | None = None,
    log_path: Path | None = None,
) -> CaseFacts:
    # TODO (Exercise 2): Run the extraction call and validate the result.
    #
    # 1. Build the user message: f"Transcript:\n\n{transcript.full_text}".
    #
    # 2. Call complete_with_system(_SYSTEM_PROMPT, user, model=model,
    #    max_tokens=2048). It returns (text, input_tokens, output_tokens).
    #
    # 3. Parse the response text with _parse_json (handles a stray ``` fence).
    #
    # 4. If a `log_path` was given, write a JSON log containing the model
    #    name, the input/output token counts, and the raw parsed dict. This
    #    is the `case_facts_call.json` artifact the reviewer audits.
    #
    # 5. Validate that every name in REQUIRED_FIELDS is present in the parsed
    #    dict and is not None and not the empty string. If anything is
    #    missing, raise CaseFactExtractionError(missing=..., raw=...) — DO
    #    NOT silently fill with null.
    #
    # 6. Construct and return a CaseFacts. Cast types explicitly:
    #    str(...) for ID/status fields, float(...) for refund_amount_usd.
    raise NotImplementedError("Exercise 2: implement case-facts extraction")


def to_dict(facts: CaseFacts) -> dict[str, Any]:
    return asdict(facts)
