"""Shared regex parsers for merchant chat messages.

Used by ``zone_tour_actions`` (swatches, skip, exit) and ``theme_choice_actions``
(theme card clicks). Keeps ``I choose "…"`` and exit phrases consistent across handlers.
"""

from __future__ import annotations

import re

CHOOSE_RE = re.compile(r'^I choose ["\'](.+?)["\']\s*$', re.I)
VIBE_RE = re.compile(r"^i'?m going for an? (.+?) vibe$", re.I)
ZONE_OPTION_RE = re.compile(r"^zone\s+option\s+([\w-]+)\s*$", re.I)
GOT_IT_CONTINUE_RE = re.compile(r"got it.*continue", re.I)
SKIP_ZONE_RE = re.compile(r"skip (this )?(zone|area)\b", re.I)
SKIP_SUB_STEP_RE = re.compile(
    r"skip (this )?step\b"
    r"|^next step\b"
    r"|(?:skip|jump) to step\s*(\d+)\b"
    r"|zone option skip_sub_step\b",
    re.I,
)
START_ZONE_TOUR_RE = re.compile(
    r"(?:^|\b)(?:start\s+)?zone\s+(?:wise|by[-\s]*zone)\s+customi[sz]"
    r"|(?:^|\b)start\s+(?:the\s+)?zone\s+tour\b"
    r"|(?:^|\b)zone[-\s]*by[-\s]*zone\s+customi[sz]",
    re.I,
)

EXIT_ZONE_TOUR_RE = re.compile(
    r"(?:^|\b)(?:exit|end|stop|leave|quit|cancel|finish)\s+"
    r"(?:the\s+)?(?:zone\s+)?(?:customi[sz]ation|customi[sz]e|tour|walkthrough)"
    r"|(?:^|\b)exit\s+(?:zone\s+)?tour\b"
    r"|(?:^|\b)done\s+with\s+(?:the\s+)?(?:zone\s+)?tour\b",
    re.I,
)
HEX_IN_MESSAGE_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# Z1-03 — merchant types their own brand colours in chat. Require a brand/palette
# cue so plain single-colour asks still flow to the normal colour handlers. Lives
# here (no Pillow dependency) so the Lambda backend can gate its fast path without
# importing ``palette`` (which pulls in PIL and is not bundled in the Lambda).
BRAND_PALETTE_TRIGGER_RE = re.compile(
    r"\bbrand\s+(?:colou?rs?|palette)\b"
    r"|\bmy\s+(?:colou?rs?|palette)\s+(?:are|is)\b"
    r"|\buse\s+(?:these|my|our)\s+(?:brand\s+)?colou?rs?\b"
    r"|\bour\s+(?:brand\s+)?(?:colou?rs?|palette)\b",
    re.I,
)


def is_brand_palette_request(text: str) -> bool:
    """True when the merchant is describing their own brand palette (Z1-03).

    Matches on the brand/palette cue regardless of format, so requests using colour
    names or descriptions ("my brand red") route to the brand-palette flow even when
    no explicit hex is present.
    """
    return bool(text and BRAND_PALETTE_TRIGGER_RE.search(text))


def parse_choose_message(text: str) -> str | None:
    """Return the chosen label from `I choose "…"` messages."""
    match = CHOOSE_RE.match(text.strip())
    return match.group(1).strip() if match else None


def parse_vibe_message(text: str) -> str | None:
    """Return the vibe name from a vibe-pill click, e.g. `I'm going for a Modern & minimal vibe`."""
    match = VIBE_RE.match(text.strip())
    return match.group(1).strip() if match else None


def parse_zone_option_id(text: str) -> str | None:
    match = ZONE_OPTION_RE.match(text.strip())
    if not match:
        return None
    return match.group(1).lower().replace("-", "_")


def parse_skip_sub_step_target(text: str) -> int | None:
    """Return a 1-based sub-step number for 'skip/jump to step N', else ``None``."""
    m = re.search(r"(?:skip|jump) to step\s*(\d+)\b", text.strip(), re.I)
    if m:
        return int(m.group(1))
    return None


def wants_skip_sub_step(text: str) -> bool:
    """True for UI/button/chat phrases that mean 'skip this sub-step'."""
    cleaned = text.strip()
    if parse_zone_option_id(cleaned) == "skip_sub_step":
        return True
    return bool(SKIP_SUB_STEP_RE.search(cleaned))
