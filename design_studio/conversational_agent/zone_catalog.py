"""Human-readable zone names and place hints for chat + UI (Z1–Z6).

``TOUR_ZONE_LABELS`` maps Z1…Z6 to merchant-facing copy. ``zone_label()`` /
``zone_place_hint()`` are used in tour prompts and ``zone_tour_flow`` sub-step text.
"""

from __future__ import annotations

from typing import Any

# Merchant-facing names (not Z1…Z6 codes)
TOUR_ZONE_LABELS: dict[str, str] = {
    "Z1": "Brand Colours",
    "Z2": "Hero & Header",
    "Z3": "Typography",
    "Z4": "Product Cards",
    "Z5": "Offer Cards",
    "Z6": "Buttons & CTAs",
}

ZONE_CHAT_INTRO: dict[str, str] = {
    "Z1": "Pick a palette card or swatch — upload a logo or describe your brand colours in chat anytime.",
    "Z2": "These options change the banner photo area, logo placement, and store name on the hero.",
    "Z3": "These options change fonts and text size on intro and store information sections.",
    "Z4": "Choose backgrounds per product section, card layout, then how prices display on cards.",
    "Z5": "Offer cards are managed by the platform — read the note below, then continue.",
    "Z6": "These options change the Follow button, coupon buttons, and other call-to-action buttons.",
}


def zone_label(code: str | None) -> str:
    if not code:
        return ""
    return TOUR_ZONE_LABELS.get(code.upper(), code)


def zone_chat_intro(code: str | None) -> str:
    if not code:
        return ""
    return ZONE_CHAT_INTRO.get(
        code.upper(), "Pick an option below to update this part of your storefront."
    )


def enrich_color_options(
    zone_code: str | None, options: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach zone_name for chat UI."""
    name = zone_label(zone_code)
    out = []
    for opt in options:
        row = dict(opt)
        row["zone_name"] = name
        row["applies_to"] = opt.get("description") or opt.get("section") or ""
        out.append(row)
    return out


def enrich_zone_options(
    zone_code: str | None, options: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    name = zone_label(zone_code)
    out = []
    for opt in options:
        row = dict(opt)
        row["zone_name"] = name
        row["applies_to"] = opt.get("description") or ""
        out.append(row)
    return out
