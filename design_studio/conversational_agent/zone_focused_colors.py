"""Apply background/surface colours only inside the merchant's focused preview zone.

When a section chip is selected (e.g. Hero → Store name & tagline), ``background_color``
on ``apply_style_tokens`` would repaint the whole storefront. This module writes
``tokens.zoneScopes[Z2]`` (etc.) so only that section updates in ``storefront.html``.
"""

from __future__ import annotations

import re

from .config_manager import ConfigManager, DEFAULT_SHOP_UUID
from .page_colors import is_page_color_request, resolve_color_from_text
from .section_focus import SectionFocus
from .zone_scopes import ZONE_COLOR_CODES, set_zone_color_scope

# element_id → (zone scope key, scope field: background | surface)
_ELEMENT_ZONE_COLOR: dict[str, tuple[str, str]] = {
    "hero_store_name": ("Z2", "surface"),
    "hero_logo": ("Z2", "surface"),
    "hero_banner": ("Z2", "background"),
    "intro_copy": ("Z3", "surface"),
    "store_details": ("Z3", "surface"),
    "showcase_cards": ("Z4S", "surface"),
    "catalog_cards": ("Z4C", "surface"),
    "catalog_filters": ("Z4C", "surface"),
    "catalogue_button": ("Z4C", "surface"),
    "follow_button": ("Z6", "surface"),
    "directions_button": ("Z6", "surface"),
}

_COLOR_INTENT_RE = re.compile(
    r"\b(?:background|backdrop|bg|colou?r|fill|panel|section|cards?|tiles?)\b",
    re.I,
)

# Product zones whose cards can be recoloured independently of the section panel.
_PRODUCT_ZONES = ("Z4S", "Z4C")
_CARD_ELEMENTS = ("catalog_cards", "showcase_cards")
_PANEL_RE = re.compile(r"\b(?:panel|section|behind|around|backdrop)\b", re.I)
_CARD_RE = re.compile(r"\b(?:cards?|tiles?)\b", re.I)


def _zone_scope_key(focus: SectionFocus) -> str | None:
    code = (focus.zone or "").upper()
    if code in ZONE_COLOR_CODES:
        return code
    return None


def resolve_zone_color_target(
    focus: SectionFocus,
    message: str,
) -> tuple[str, str] | None:
    """Map focus + message to (zoneScopes key, role) where role is cardFace|surface|background."""
    if focus.element_id == "page_backdrop":
        return None

    element_mapped = bool(focus.element_id and focus.element_id in _ELEMENT_ZONE_COLOR)
    if element_mapped:
        zone, default_role = _ELEMENT_ZONE_COLOR[focus.element_id]
    else:
        zone = _zone_scope_key(focus)
        default_role = "background"
        if not zone:
            return None

    # Product zones: decide card faces vs section panel from the wording (RAP-38 B5).
    if zone in _PRODUCT_ZONES:
        if _PANEL_RE.search(message):
            return zone, "background"  # section panel behind the cards
        if _CARD_RE.search(message) or focus.element_id in _CARD_ELEMENTS:
            return zone, "cardFace"  # the card tiles themselves
        return zone, "background"

    # Non-product zones: an explicit element mapping wins (legacy behaviour).
    if element_mapped:
        return zone, default_role

    if re.search(r"\b(?:panel|surface|fill|card)\b", message, re.I):
        return zone, "surface"
    if focus.section_id == "hero" and re.search(
        r"\b(?:store\s+name|tagline|name\s+plate|hero\s+text)\b", message, re.I
    ):
        return "Z2", "surface"
    return zone, "background"


def is_zone_focused_color_request(message: str, focus: SectionFocus | None) -> bool:
    """Merchant wants a colour change scoped to the highlighted section only."""
    if not focus:
        return False
    if focus.element_id == "page_backdrop":
        return False
    if not _zone_scope_key(focus):
        return False
    if is_page_color_request(message):
        return False
    if not resolve_color_from_text(message):
        return False
    if not resolve_zone_color_target(focus, message):
        return False
    # A focused card element + a colour is intent enough (e.g. "make it pink"),
    # so it stays on the fast-path instead of leaking to the agent's panel default.
    if focus.element_id in _CARD_ELEMENTS:
        return True
    return bool(_COLOR_INTENT_RE.search(message))


def apply_zone_focused_color(
    message: str,
    *,
    shop_uuid: str = DEFAULT_SHOP_UUID,
    focus: SectionFocus | None,
) -> tuple[bool, str, dict[str, str]]:
    """Set zoneScopes colour for the focused section; leaves global colors.* unchanged."""
    if not focus or not is_zone_focused_color_request(message, focus):
        return False, "", {}

    target = resolve_zone_color_target(focus, message)
    if not target:
        return False, "", {}

    zone_key, role = target
    color_hex = resolve_color_from_text(message)
    if not color_hex:
        return False, "", {}

    cm = ConfigManager(shop_uuid=shop_uuid)
    tokens = cm.tokens.model_copy(deep=True)
    kwarg = {"cardFace": "card_face", "surface": "surface", "background": "background"}[role]
    tokens = set_zone_color_scope(tokens, zone_key, **{kwarg: color_hex})

    cm.save_tokens(
        tokens,
        theme_name=tokens.colors.paletteName or "Custom Theme",
        change_summary={
            "zonesTouched": [zone_key],
            "humanSummary": f"{focus.display_label} {role} → {color_hex}.",
        },
    )
    cm.reload()

    role_label = {
        "cardFace": "card colour",
        "surface": "panel fill",
        "background": "section background",
    }[role]
    summary = f"{role_label} → **{color_hex}**"
    return True, summary, {f"zone_{zone_key}_{role}": color_hex}
