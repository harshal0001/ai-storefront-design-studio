"""Server-only intent helpers for zone tour (not used to apply styles without the agent)."""

from __future__ import annotations

import re

# Used only to decide whether to run a post-agent refresh safety net — not fast-path routing.
_MORE_OPTIONS_INTENT_RE = re.compile(
    r"\b(?:\d+|one|a|another|extra)\s+more\b"
    r"|\b(?:more|other|different|another|new|extra)\s+"
    r"(?:options?|choices?|looks?|styles?|layouts?|variations?|ideas?)\b"
    r"|\b(?:show|give|suggest|offer)\s+(?:me\s+)?(?:\d+|one|a\s+)?(?:more|other|different|another)\b"
    r"|\bmore\s+(?:stylish|modern|bold|minimal|elegant|luxury|playful|fresh)\b",
    re.I,
)


def user_wants_more_options(text: str) -> bool:
    return bool(text and _MORE_OPTIONS_INTENT_RE.search(text.strip()))


def parse_requested_option_count(text: str) -> int | None:
    """How many new swatches the merchant asked for (agent/tool may override)."""
    if not text:
        return None
    match = re.search(
        r"\b(\d+|one|a)\s+more\s+(?:options?|choices?|looks?|layouts?|ideas?)\b",
        text.strip(),
        re.I,
    )
    if not match:
        return None
    word = match.group(1).lower()
    if word in ("one", "a"):
        return 1
    try:
        return max(1, min(int(word), 4))
    except ValueError:
        return None
