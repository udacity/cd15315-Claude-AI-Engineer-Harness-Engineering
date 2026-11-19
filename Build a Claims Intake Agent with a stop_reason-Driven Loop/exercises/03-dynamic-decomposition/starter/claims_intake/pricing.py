"""Token-to-USD cost estimator.

Rates are public list prices in USD per 1M tokens at the time of writing.
They are estimates for in-run reporting; the authoritative cost figure is
your Anthropic billing dashboard.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRate:
    input_per_mtok: float
    output_per_mtok: float


_RATES: dict[str, ModelRate] = {
    "claude-haiku-4-5": ModelRate(input_per_mtok=1.0, output_per_mtok=5.0),
    # Haiku 5.5's rate for prompts up to 100K tokens ($0.50 / $2.50 above that).
    "claude-haiku-5-5": ModelRate(input_per_mtok=0.10, output_per_mtok=0.50),
    "claude-sonnet-4-5": ModelRate(input_per_mtok=3.0, output_per_mtok=15.0),
    "claude-sonnet-4-6": ModelRate(input_per_mtok=3.0, output_per_mtok=15.0),
    "claude-sonnet-5": ModelRate(input_per_mtok=2.0, output_per_mtok=10.0),
    "claude-sonnet-5-5": ModelRate(input_per_mtok=2.0, output_per_mtok=10.0),
    "claude-opus-4-5": ModelRate(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-opus-4-6": ModelRate(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-opus-4-7": ModelRate(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-opus-4-8": ModelRate(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-opus-5": ModelRate(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-opus-5-5": ModelRate(input_per_mtok=4.0, output_per_mtok=20.0),
}


def _base_model_id(model: str) -> str:
    """The rate-table name for a model id.

    Drops a provider prefix (`eu.anthropic.`, `anthropic.`), a Bedrock version
    suffix (`-v1:0`) and a snapshot date (`-20251001`).
    """
    base = re.sub(r"^(?:[a-z]+\.)?anthropic\.", "", model.strip().lower())
    base = re.sub(r"-v\d+(?::\d+)?$", "", base)
    return re.sub(r"-\d{8}$", "", base)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for one run given token counts.

    Falls back to a conservative Sonnet rate if the model is unknown — better
    to over-estimate than under-estimate when budgeting.
    """
    rate = _RATES.get(_base_model_id(model)) or _RATES["claude-sonnet-4-6"]
    return (
        (input_tokens / 1_000_000.0) * rate.input_per_mtok
        + (output_tokens / 1_000_000.0) * rate.output_per_mtok
    )
