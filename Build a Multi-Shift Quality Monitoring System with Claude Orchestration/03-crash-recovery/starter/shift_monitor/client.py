"""Claude client boundary: Protocol + recorded fake + Anthropic production client."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Protocol

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


class ClaudeClient(Protocol):
    def complete(self, messages: list[Message]) -> Message: ...


@dataclass
class RecordedClaudeClient:
    """Replays pre-recorded assistant responses. Used in tests and offline runs."""

    responses: list[str]
    call_count: int = 0

    def complete(self, messages: list[Message]) -> Message:
        if self.call_count >= len(self.responses):
            raise RuntimeError("RecordedClaudeClient: responses exhausted")
        content = self.responses[self.call_count]
        self.call_count += 1
        return Message(role="assistant", content=content)


@dataclass
class AnthropicClaudeClient:
    """Production client using the Anthropic SDK. Requires ANTHROPIC_API_KEY in env.

    The `CLAUDE_MODEL` env var overrides the default model.
    """

    model: str = field(default_factory=lambda: os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL))
    max_tokens: int = 1024
    _client: object | None = field(default=None, init=False, repr=False)

    def complete(self, messages: list[Message]) -> Message:
        if self._client is None:
            from anthropic import Anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
            self._client = Anthropic(api_key=api_key)
        from anthropic import Anthropic

        assert isinstance(self._client, Anthropic)
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        text_parts = [block.text for block in resp.content if block.type == "text"]
        return Message(role="assistant", content="".join(text_parts))
