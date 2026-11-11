"""Anthropic client + model configuration.

Two inference paths are supported:

1. **SDK path (preferred / exemplar)** — used when `ANTHROPIC_API_KEY` is set.
   Direct Anthropic Python SDK calls. This is what you use in the Docker
   container with the project's $25 API credit.

2. **Claude Code CLI path (fallback)** — used when no API key is set but the
   `claude` CLI is available and authenticated. Shells out to
   `claude -p --output-format json --model <model>`. This is purely a
   convenience for local development against an existing Claude Code session
   subscription — it does not represent the canonical workflow.

`CLAUDE_MODEL` env var overrides the default model in either path.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from functools import lru_cache
from typing import Literal

import anthropic

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
InferenceBackend = Literal["sdk", "cli"]


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def get_model() -> str:
    """`CLAUDE_MODEL` if set, else the lab's `ANTHROPIC_MODEL`, else DEFAULT_MODEL."""
    return os.environ.get("CLAUDE_MODEL") or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


def set_model(model: str) -> None:
    os.environ["CLAUDE_MODEL"] = model


def _backend() -> InferenceBackend:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "sdk"
    if shutil.which("claude"):
        return "cli"
    raise RuntimeError(
        "No inference backend available. Set ANTHROPIC_API_KEY or install the `claude` CLI."
    )


def complete(prompt: str, *, model: str | None = None, max_tokens: int = 2048) -> str:
    """Issue a single user-turn completion and return the assistant's text."""
    target_model = model or get_model()
    backend = _backend()
    if backend == "sdk":
        resp = get_client().messages.create(
            model=target_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    # CLI fallback
    result = subprocess.run(
        ["claude", "-p", "--model", target_model, "--output-format", "json", prompt],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    return (payload.get("result") or "").strip()


def complete_with_system(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = 2048,
) -> tuple[str, int, int]:
    """Issue a system + user-turn call. Returns (text, input_tokens, output_tokens)."""
    target_model = model or get_model()
    backend = _backend()
    if backend == "sdk":
        resp = get_client().messages.create(
            model=target_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text, int(resp.usage.input_tokens), int(resp.usage.output_tokens)

    # CLI fallback — concatenates system + user as one prompt; usage approximated.
    result = subprocess.run(
        [
            "claude",
            "-p",
            "--model",
            target_model,
            "--output-format",
            "json",
            "--append-system-prompt",
            system,
            user,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    text = (payload.get("result") or "").strip()
    usage = payload.get("usage") or {}
    return text, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
