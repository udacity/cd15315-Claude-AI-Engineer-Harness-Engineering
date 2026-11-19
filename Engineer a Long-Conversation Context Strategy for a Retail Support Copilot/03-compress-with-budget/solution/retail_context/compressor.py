"""Tiered compression: summarize resolved segments; preserve active verbatim.

Resolved segments are condensed by a single Claude call per segment using the
prompt template at `retail_context/prompts/compression_prompt.md`. The active
segment is **never** summarized — it is preserved byte-exact.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from retail_context.client import complete_with_system
from retail_context.transcript import Segment, Transcript


@dataclass
class Summary:
    issue_id: str
    text: str
    input_tokens: int
    output_tokens: int


@dataclass
class Compressed:
    summaries: dict[str, Summary]
    active_text: str
    active_issue_id: str


def _load_prompt() -> str:
    return resources.files("retail_context.prompts").joinpath(
        "compression_prompt.md"
    ).read_text()


def summarize_segment(segment: Segment, *, model: str | None = None) -> Summary:
    if segment.status != "resolved":
        raise ValueError(
            f"Refusing to summarize segment {segment.issue_id!r} with status {segment.status!r}."
            " Only resolved segments are compressed; the active segment is preserved verbatim."
        )
    system = _load_prompt()
    user = (
        f"Source segment — issue_id `{segment.issue_id}`, turns "
        f"{segment.turn_range[0]}–{segment.turn_range[1]}:\n\n{segment.text}"
    )
    text, in_tok, out_tok = complete_with_system(
        system, user, model=model, max_tokens=2048
    )
    return Summary(
        issue_id=segment.issue_id,
        text=text,
        input_tokens=in_tok,
        output_tokens=out_tok,
    )


def compress(transcript: Transcript, *, model: str | None = None) -> Compressed:
    summaries: dict[str, Summary] = {}
    active_text = ""
    active_id = ""
    for seg in transcript.segments:
        if seg.status == "resolved":
            summaries[seg.issue_id] = summarize_segment(seg, model=model)
        else:
            # Byte-exact preservation — exactly the raw rendered turns.
            active_text = "\n\n".join(t.render() for t in seg.turns)
            active_id = seg.issue_id
    if not active_id:
        raise RuntimeError("Transcript has no active segment.")
    return Compressed(summaries=summaries, active_text=active_text, active_issue_id=active_id)
