"""Parse and apply page-wide / storefront-wide colour requests without the LLM.

Detects phrases like "make the whole page pink" and sets global background/surface via
``set_global_colors()``, clearing ``zoneScopes`` so per-zone tints do not block the change.
"""

from __future__ import annotations

import re
from pathlib import Path

from coloraide import Color

from .color_engine import get_contrast_color, normalize_hex, is_valid_color
from .config_manager import ConfigManager, DEFAULT_SHOP_UUID
from .zone_scopes import clear_zone_scopes, set_global_colors
from .zone_tour_flow import extract_hex_from_text

# Common merchant colour words (coloraide resolves these)
_COLOR_WORDS = (
    "pink",
    "magenta",
    "rose",
    "hotpink",
    "fuchsia",
    "red",
    "crimson",
    "blue",
    "navy",
    "skyblue",
    "teal",
    "green",
    "emerald",
    "yellow",
    "gold",
    "orange",
    "coral",
    "purple",
    "violet",
    "lavender",
    "cream",
    "ivory",
    "white",
    "black",
    "grey",
    "gray",
    "slate",
    "charcoal",
    "brown",
    "beige",
    "peach",
    "mint",
    "cyan",
)

_FULL_PAGE_RE = re.compile(
    r"\b(?:complete|entire|whole|all|full)\s+(?:the\s+)?(?:storefront|store\s+front|page|site)\b"
    r"|\b(?:storefront|store\s+front|page)\s+(?:wide|background)\b"
    r"|\bpage[- ]?wide\b",
    re.I,
)

_BACKGROUND_RE = re.compile(
    r"\b(?:background|backdrop|page\s+colour|page\s+color|behind\s+everything)\b",
    re.I,
)

_COLOR_WORDS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in sorted(_COLOR_WORDS, key=len, reverse=True)) + r")\b",
    re.I,
)


def is_page_color_request(message: str) -> bool:
    """Merchant wants to change page / storefront colours (often whole-page)."""
    text = message or ""
    if not text.strip():
        return False
    has_color = bool(extract_hex_from_text(text)) or bool(_COLOR_WORDS_RE.search(text))
    if not has_color:
        return False
    if _BACKGROUND_RE.search(text) and (
        _FULL_PAGE_RE.search(text) or re.search(r"\b(?:everywhere|all\s+over)\b", text, re.I)
    ):
        return True
    if _FULL_PAGE_RE.search(text) and _BACKGROUND_RE.search(text):
        return True
    # "make the complete storefront pink"
    if _FULL_PAGE_RE.search(text) and re.search(r"\b(?:make|turn|set|change)\b", text, re.I):
        return True
    return False


_COMPOUND_COLOR_PHRASES = (
    "dark red",
    "dark blue",
    "dark green",
    "dark grey",
    "dark gray",
    "light blue",
    "light green",
    "light grey",
    "light gray",
    "sky blue",
    "hot pink",
)


def resolve_color_from_text(text: str) -> str | None:
    """Resolve a hex colour from hex codes or colour names in the message."""
    hex_val = extract_hex_from_text(text)
    if hex_val and is_valid_color(hex_val):
        return normalize_hex(hex_val)

    for phrase in _COMPOUND_COLOR_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", text, re.I):
            try:
                c = Color(phrase)
                return normalize_hex(c.convert("srgb").clip().to_string(hex=True))
            except Exception:
                continue

    match = _COLOR_WORDS_RE.search(text)
    if match:
        try:
            c = Color(match.group())
            return normalize_hex(c.convert("srgb").clip().to_string(hex=True))
        except Exception:
            pass
    return None


def apply_page_color_updates(
    message: str,
    *,
    shop_uuid: str = DEFAULT_SHOP_UUID,
    config_path: Path | str | None = None,
) -> tuple[bool, str, dict[str, str]]:
    """Apply a whole-storefront background/surface colour. Clears per-zone overrides."""
    if not is_page_color_request(message):
        return False, "", {}

    color_hex = resolve_color_from_text(message)
    if not color_hex:
        return False, "", {}

    cm = ConfigManager(shop_uuid=shop_uuid, config_path=config_path)
    tokens = clear_zone_scopes(cm.tokens.model_copy(deep=True))
    text_primary = get_contrast_color(color_hex)
    tokens = set_global_colors(
        tokens,
        background=color_hex,
        surface=color_hex,
        text_primary=text_primary,
        text_secondary=text_primary,
    )

    cm.save_tokens(
        tokens,
        theme_name=tokens.colors.paletteName or "Custom Theme",
        change_summary={
            "zonesTouched": ["Z1"],
            "humanSummary": f"Storefront background set to {color_hex}.",
        },
    )
    cm.reload()

    summary = (
        f"Storefront background & panels → **{color_hex}** "
        f"(readable text adjusted). Check the full preview."
    )
    return (
        True,
        summary,
        {
            "background": color_hex,
            "surface": color_hex,
            "text_primary": text_primary,
        },
    )
