"""Optional semantic enrichment via the Claude API.

The rule-based extractor in :mod:`speccheck.extract` is the baseline and runs
everywhere. When an ``ANTHROPIC_API_KEY`` is present and the ``anthropic`` SDK
is installed, this module asks Claude to surface obligations the patterns miss
— qualitative requirements ("color to match architect's sample"), implied
submittal items, and standards referenced by description rather than number.

Enrichment is strictly additive and best-effort: any failure (no key, no SDK,
API error, malformed response) returns an empty list so verification still
runs fully offline.
"""

from __future__ import annotations

import json
import os

from .models import Requirement, RequirementKind

DEFAULT_MODEL = os.environ.get("SPECCHECK_MODEL", "claude-opus-4-8")

_PROMPT = """You are a construction submittal reviewer. From the specification \
text below, extract additional checkable requirements that a simple regex would \
miss. Focus on: required submittal deliverables, qualitative performance \
criteria, and standards referenced by name rather than number.

Return ONLY a JSON array. Each element: {{"kind": "submittal_item"|"standard"|\
"general", "keyword": "<short canonical token>", "text": "<verbatim clause>"}}.

SPECIFICATION:
{spec}
"""


def enrich(spec_text: str, model: str = DEFAULT_MODEL) -> list[Requirement]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return []
    try:
        import anthropic  # type: ignore
    except ImportError:
        return []

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": _PROMPT.format(spec=spec_text[:12000]),
            }],
        )
        payload = "".join(
            block.text for block in msg.content if block.type == "text"
        )
        return _parse(payload)
    except Exception:  # best-effort; never break the offline path
        return []


def _parse(payload: str) -> list[Requirement]:
    payload = payload.strip()
    start, end = payload.find("["), payload.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        items = json.loads(payload[start:end + 1])
    except json.JSONDecodeError:
        return []

    out: list[Requirement] = []
    valid = {k.value for k in RequirementKind}
    for it in items:
        if not isinstance(it, dict):
            continue
        kind = it.get("kind", "general")
        if kind not in valid:
            kind = "general"
        out.append(Requirement(
            kind=RequirementKind(kind),
            text=str(it.get("text", "")).strip(),
            keyword=str(it.get("keyword", "")).strip().lower(),
        ))
    return out
