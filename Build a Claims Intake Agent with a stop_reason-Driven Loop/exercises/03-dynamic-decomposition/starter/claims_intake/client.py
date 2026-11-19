"""Anthropic client factory and model config."""

import os

from anthropic import Anthropic


def make_client() -> Anthropic:
    """Construct an Anthropic client from env. Fails fast if API key is missing."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it before running, e.g.:\n"
            "    export ANTHROPIC_API_KEY=sk-ant-..."
        )
    return Anthropic(api_key=api_key)


DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def default_model() -> str:
    """The model a run uses when no --model is given.

    `CLAUDE_MODEL` wins if it is set; otherwise `ANTHROPIC_MODEL`, which Udacity's
    labs set to a model their key accepts; otherwise DEFAULT_MODEL.
    """
    return os.environ.get("CLAUDE_MODEL") or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
