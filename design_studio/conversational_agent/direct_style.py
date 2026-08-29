"""Parse direct merchant style requests and apply token updates without the discovery flow.

Maps natural language (e.g. "pill buttons", "grid3", "italic headings") to ``StyleTokens``
fields via ``_PHRASE_RULES``, then saves through ``ConfigManager.save_tokens()``.

Called from ``chat_fast_path`` before the zone tour and Bedrock agent. Does not set
``harmonyChecked`` / ``contrastAA`` — only ``build_tokens_from_theme_save`` does today.

Skipped when ``style_via_agent=True`` — those requests need multi-token orchestration.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from .color_engine import normalize_hex
from .config_manager import ConfigManager, DEFAULT_SHOP_UUID
from .product_card_phrases import PRODUCT_CARD_BORDER_RADIUS_ZERO, PRODUCT_CARD_RECTANGLE
from .style_tokens import (
    StyleTokens,
    VALID_BORDER_RADIUS,
    VALID_BUTTON_ANIMATION,
    VALID_BUTTON_SHAPE,
    VALID_BUTTON_SIZE,
    VALID_BUTTON_STYLE,
    VALID_SPACING,
)

_KEY_TO_ZONE: dict[str, str] = {
    "hero_overlay": "Z2",
    "hero_layout": "Z2",
    "logo_placement": "Z2",
    "tagline_placement": "Z2",
    "store_name_style": "Z2",
    "heading_font": "Z3",
    "body_font": "Z3",
    "font_scale": "Z3",
    "heading_style": "Z3",
    "body_style": "Z3",
    "product_card_shape": "Z4",
    "product_card_layout": "Z4",
    "product_card_shadow": "Z4",
    "price_style": "Z4",
    "card_tap_animation": "Z4",
    "featured_enabled": "Z4",
    "featured_style": "Z4",
    "offer_filter_preset": "Z5",
    "button_shape": "Z6",
    "button_style": "Z6",
    "button_size": "Z6",
    "button_press_animation": "Z6",
    "text_color": "Z3",
    "border_radius": "Z4",
    "spacing": "Z4",
    "motion_transition": "Z6",
}


def zones_touched_from_keys(keys: Iterable[str]) -> list[str]:
    """Derive sorted list of zones actually affected by a set of update keys."""
    return sorted({_KEY_TO_ZONE.get(k, "Z1") for k in keys})


# Natural-language → token field updates (snake_case keys consumed by _merge_updates)
_PHRASE_RULES: list[tuple[re.Pattern[str], dict[str, str]]] = [
    # Buttons (Z6)
    (re.compile(r"\bpill\s+buttons?\b|\bbuttons?\s+.{0,20}pill\b", re.I), {"button_shape": "pill"}),
    (re.compile(r"\brounded\s+buttons?\b", re.I), {"button_shape": "rounded"}),
    (re.compile(r"\bsharp\s+buttons?\b", re.I), {"button_shape": "sharp"}),
    (re.compile(r"\boutlined\s+buttons?\b", re.I), {"button_style": "outlined"}),
    (re.compile(r"\bfilled\s+buttons?\b", re.I), {"button_style": "filled"}),
    (re.compile(r"\bghost\s+buttons?\b", re.I), {"button_style": "ghost"}),
    (re.compile(r"\bsoft\s+buttons?\b", re.I), {"button_style": "soft"}),
    # Hero (Z2)
    (re.compile(r"\bdark\s+(hero\s+)?scrim\b|\bdarkscrim\b", re.I), {"hero_overlay": "darkScrim"}),
    (
        re.compile(r"\blight\s+(hero\s+)?scrim\b|\blightscrim\b", re.I),
        {"hero_overlay": "lightScrim"},
    ),
    (
        re.compile(r"\bno\s+(hero\s+)?scrim\b|\bhero\s+overlay\s+none\b", re.I),
        {"hero_overlay": "none"},
    ),
    (re.compile(r"\bauto\s+scrim\b", re.I), {"hero_overlay": "autoScrim"}),
    (re.compile(r"\blogo\s+(on\s+)?left\b", re.I), {"logo_placement": "left"}),
    (re.compile(r"\blogo\s+center(?:ed)?\b", re.I), {"logo_placement": "center"}),
    (re.compile(r"\blogo\s+right\b", re.I), {"logo_placement": "right"}),
    # Product cards (Z4)
    (
        re.compile(r"\bgrid\s*3\b|\bgrid3\b|\bthree[\s-]column\s+(products?|cards?|grid)\b", re.I),
        {"product_card_layout": "grid3"},
    ),
    (
        re.compile(r"\bgrid\s*2\b|\bgrid2\b|\btwo[\s-]column\b", re.I),
        {"product_card_layout": "grid2"},
    ),
    (
        re.compile(r"\blist\s+(layout|products?|cards?)\b|\bproduct\s+list\b", re.I),
        {"product_card_layout": "list"},
    ),
    (
        re.compile(r"\bcircular\s+(product\s+)?images?\b", re.I),
        {"product_card_shape": "circularImage"},
    ),
    (re.compile(r"\bsharp\s+(product\s+)?cards?\b", re.I), {"product_card_shape": "sharp"}),
    (re.compile(r"\brounded\s+(product\s+)?cards?\b", re.I), {"product_card_shape": "rounded"}),
    (PRODUCT_CARD_BORDER_RADIUS_ZERO, {"product_card_shape": "sharp"}),
    (PRODUCT_CARD_RECTANGLE, {"product_card_shape": "rounded", "product_card_layout": "grid2"}),
    (
        re.compile(r"\bfloating\s+shadow\b|\bfloating\s+cards?\b", re.I),
        {"product_card_shadow": "floating"},
    ),
    (re.compile(r"\bflat\s+cards?\b", re.I), {"product_card_shadow": "flat"}),
    # Featured product (Z4-04) — highlight the first product card
    (
        re.compile(
            r"\bfeature(?:d)?\s+(?:\w+\s+){0,3}?product\b"
            r"|\bhighlight\s+(?:\w+\s+){0,3}?product\b",
            re.I,
        ),
        {"featured_enabled": "true"},
    ),
    (
        re.compile(
            r"\b(?:no|remove|turn\s+off|disable|hide)\s+featured\s+products?\b|\bunfeature\b",
            re.I,
        ),
        {"featured_enabled": "false"},
    ),
    # Geometry (Z1 global)
    (
        re.compile(r"\bpill\s+corners?\b|\bpill\s+shape\b|\bpill\s+border\b", re.I),
        {"border_radius": "pill"},
    ),
    (re.compile(r"\bsharp\s+corners?\b", re.I), {"border_radius": "sharp"}),
    (re.compile(r"\bspacious\s+spacing\b", re.I), {"spacing": "spacious"}),
    (re.compile(r"\bcompact\s+spacing\b", re.I), {"spacing": "compact"}),
    # Typography (Z3 / page-wide)
    (
        re.compile(r"\bstore\s+name\s+bold\b|\bbold\s+store\s+name\b", re.I),
        {"store_name_style": "bold"},
    ),
    (
        re.compile(
            r"(?:\b(?:all|entire|whole|complete|every|full)\s+(?:page|text|storefront)\b.*\b(?:italic|italics)\b"
            r"|\b(?:italic|italics)\b.*\b(?:all|entire|whole|page|storefront|everywhere)\b"
            r"|\bmake\b.*\b(?:text|words?|copy)\b.*\b(?:italic|italics)\b)",
            re.I,
        ),
        {"heading_style": "italic", "body_style": "italic"},
    ),
    (
        re.compile(r"\bheading(?:s)?\s+italic\b|\bitalic\s+heading(?:s)?\b", re.I),
        {"heading_style": "italic"},
    ),
    (re.compile(r"\bbody\s+italic\b|\bitalic\s+body\b", re.I), {"body_style": "italic"}),
    # Button size (Z6-04)
    (
        re.compile(
            r"\b(?:big|bigger|large|larger)\s+buttons?\b|\bbuttons?\s+(?:big|bigger|large|larger)\b",
            re.I,
        ),
        {"button_size": "large"},
    ),
    (
        re.compile(
            r"\b(?:small|smaller|compact|tiny)\s+buttons?\b|\bbuttons?\s+(?:small|smaller|tiny)\b",
            re.I,
        ),
        {"button_size": "compact"},
    ),
    (
        re.compile(r"\b(?:standard|normal|medium|default)[\s-]?(?:sized?\s+)?buttons?\b", re.I),
        {"button_size": "standard"},
    ),
    # Button press feedback (Z6-05) — ripple needs JS, not offered here
    (
        re.compile(r"\bbuttons?\s+darken\b|\bdarken\b.{0,15}\bon\s+(?:press|tap|click)\b", re.I),
        {"button_press_animation": "darken"},
    ),
    (
        re.compile(
            r"\bbuttons?\s+(?:scale|shrink)\b|\b(?:scale|shrink)\b.{0,15}\bon\s+(?:press|tap|click)\b",
            re.I,
        ),
        {"button_press_animation": "scale"},
    ),
    (
        re.compile(r"\bno\s+button\s+(?:press|tap)\s+(?:animation|feedback|effect)\b", re.I),
        {"button_press_animation": "none"},
    ),
    # Text scale (Z3-02)
    (
        re.compile(
            r"\b(?:bigger|larger|increase)\s+(?:the\s+)?(?:text|font|type)(?:\s+size)?\b"
            r"|\b(?:text|font|type)\s+(?:bigger|larger)\b",
            re.I,
        ),
        {"font_scale": "generous"},
    ),
    (
        re.compile(
            r"\b(?:smaller|tinier|reduce|decrease|compact)\s+(?:the\s+)?(?:text|font|type)(?:\s+size)?\b"
            r"|\b(?:text|font|type)\s+(?:smaller|tinier)\b",
            re.I,
        ),
        {"font_scale": "compact"},
    ),
    (
        re.compile(r"\b(?:standard|normal|default)\s+(?:text|font|type)\s+size\b", re.I),
        {"font_scale": "standard"},
    ),
    # Price display style (Z4-03)
    (
        re.compile(
            r"\b(?:prices?|price\s+tags?)\s+stand\s+out\b"
            r"|\bstand\s+out\s+more\b"
            r"|\bmake\s+prices?\s+(?:pop|bold|bolder)\b"
            r"|\bbold(?:er)?\s+prices?\b",
            re.I,
        ),
        {"price_style": "boldRed"},
    ),
    (
        re.compile(
            r"\bunderstated\s+prices?\b|\bsubtle\s+prices?\b|\bgrey\s+prices?\b",
            re.I,
        ),
        {"price_style": "understatedGrey"},
    ),
    (
        re.compile(r"\bbadge\s+pill\s+prices?\b|\bpill\s+prices?\b", re.I),
        {"price_style": "badgePill"},
    ),
    (
        re.compile(r"\baccent\s+(?:colou?r\s+)?prices?\b", re.I),
        {"price_style": "accentColor"},
    ),
    (
        re.compile(r"\bbold\s+red\s+prices?\b", re.I),
        {"price_style": "boldRed"},
    ),
    # Text colour (Z3-03) — independent override; explicit hex handled in parse_direct_style_updates
    (
        re.compile(r"\b(?:dark|darker|black)\s+text\b|\btext\s+(?:dark|darker|black)\b", re.I),
        {"text_color": "#1a1a1a"},
    ),
    (
        re.compile(r"\b(?:light|lighter|white)\s+text\b|\btext\s+(?:light|lighter|white)\b", re.I),
        {"text_color": "#ffffff"},
    ),
]

_HUMAN_LABELS = {
    "button_shape": "button shape",
    "button_style": "button style",
    "button_size": "button size",
    "button_press_animation": "button press animation",
    "hero_overlay": "hero scrim",
    "hero_layout": "hero layout",
    "logo_placement": "logo placement",
    "tagline_placement": "tagline placement",
    "store_name_style": "store name style",
    "product_card_shape": "product card shape",
    "product_card_layout": "product card layout",
    "product_card_shadow": "product card shadow",
    "price_style": "price style",
    "card_tap_animation": "card tap animation",
    "featured_enabled": "featured product",
    "featured_style": "featured style",
    "border_radius": "corner style",
    "spacing": "spacing",
    "motion_transition": "page transitions",
    "offer_filter_preset": "offer image filter",
    "heading_font": "heading font",
    "body_font": "body font",
    "font_scale": "text scale",
    "heading_style": "heading style",
    "body_style": "body style",
    "text_color": "text colour",
}


def parse_direct_style_updates(message: str) -> dict[str, str]:
    """Extract token updates from a free-text style request."""
    if not message or not message.strip():
        return {}

    updates: dict[str, str] = {}
    for pattern, fields in _PHRASE_RULES:
        if pattern.search(message):
            updates.update(fields)

    # Explicit enum tokens (hero_overlay=darkScrim)
    for key in _HUMAN_LABELS:
        m = re.search(rf"\b{key}\s*[=:]\s*([\w]+)", message, re.I)
        if m:
            updates[key] = m.group(1)

    # Explicit text colour hex (e.g. "text colour #2b2b2b") wins over dark/light shortcuts
    m = re.search(r"\btext\s+colou?r\s+(#[0-9a-fA-F]{3,8})\b", message, re.I)
    if m:
        updates["text_color"] = m.group(1)

    return updates


_BUTTON_VALID: dict[str, set[str]] = {
    "button_shape": VALID_BUTTON_SHAPE,
    "button_style": VALID_BUTTON_STYLE,
    "button_size": VALID_BUTTON_SIZE,
    "button_press_animation": VALID_BUTTON_ANIMATION,
}


def _merge_updates(tokens: StyleTokens, updates: dict[str, str]) -> StyleTokens:
    t = tokens.model_copy(deep=True)

    if updates.get("hero_overlay") or updates.get("hero_layout") or updates.get("logo_placement"):
        hero = t.hero.model_dump()
        for k, attr in [
            ("hero_overlay", "overlay"),
            ("hero_layout", "layout"),
            ("logo_placement", "logoPlacement"),
            ("tagline_placement", "taglinePlacement"),
            ("store_name_style", "storeNameStyle"),
        ]:
            if updates.get(k):
                hero[attr] = updates[k]
        t.hero = t.hero.model_validate(hero)

    if any(
        updates.get(k)
        for k in (
            "product_card_shape",
            "product_card_layout",
            "product_card_shadow",
            "price_style",
            "card_tap_animation",
        )
    ):
        cards = t.productCards.model_dump()
        mapping = {
            "product_card_shape": "shape",
            "product_card_layout": "layout",
            "product_card_shadow": "shadow",
            "price_style": "priceStyle",
            "card_tap_animation": "tapAnimation",
        }
        for src, dst in mapping.items():
            if updates.get(src):
                cards[dst] = updates[src]
        t.productCards = t.productCards.model_validate(cards)

    if updates.get("featured_enabled") is not None or updates.get("featured_style"):
        cards = t.productCards.model_dump()
        featured = dict(cards.get("featured") or {})
        if updates.get("featured_enabled") is not None:
            featured["enabled"] = updates["featured_enabled"].lower() in ("true", "yes", "on", "1")
        if updates.get("featured_style"):
            featured["style"] = updates["featured_style"]
        cards["featured"] = featured
        t.productCards = t.productCards.model_validate(cards)

    if any(
        updates.get(k)
        for k in ("button_shape", "button_style", "button_size", "button_press_animation")
    ):
        buttons = t.buttons.model_dump()
        mapping = {
            "button_shape": "shape",
            "button_style": "style",
            "button_size": "size",
            "button_press_animation": "pressAnimation",
        }
        for src, dst in mapping.items():
            if updates.get(src):
                valid = _BUTTON_VALID.get(src)
                if valid and updates[src] not in valid:
                    raise ValueError(
                        f"Invalid {src}='{updates[src]}'. "
                        f"Must be one of: {', '.join(sorted(valid))}"
                    )
                buttons[dst] = updates[src]
        t.buttons = t.buttons.model_validate(buttons)

    if updates.get("border_radius") or updates.get("spacing"):
        geo = t.geometry.model_dump()
        if updates.get("border_radius") and updates["border_radius"] in VALID_BORDER_RADIUS:
            geo["borderRadiusPreset"] = updates["border_radius"]
        if updates.get("spacing") and updates["spacing"] in VALID_SPACING:
            geo["spacingPreset"] = updates["spacing"]
        t.geometry = t.geometry.model_validate(geo)

    if updates.get("text_color"):
        t.colors = t.colors.model_copy(update={"textPrimary": normalize_hex(updates["text_color"])})

    if updates.get("motion_transition"):
        t.motion = t.motion.model_copy(update={"transition": updates["motion_transition"]})  # type: ignore[arg-type]

    if updates.get("offer_filter_preset"):
        t.offerCards = t.offerCards.model_copy(
            update={
                "imageBeautification": t.offerCards.imageBeautification.model_copy(
                    update={"filterPreset": updates["offer_filter_preset"]}  # type: ignore[arg-type]
                )
            }
        )

    typo_keys = ("heading_font", "body_font", "font_scale", "heading_style", "body_style")
    if any(updates.get(k) for k in typo_keys):
        typo = t.typography.model_dump()
        mapping = {
            "heading_font": "headingFont",
            "body_font": "bodyFont",
            "font_scale": "scale",
            "heading_style": "headingStyle",
            "body_style": "bodyStyle",
        }
        for src, dst in mapping.items():
            if updates.get(src):
                typo[dst] = updates[src]
        t.typography = t.typography.model_validate(typo)

    return t


def apply_direct_style_updates(
    message: str,
    *,
    shop_uuid: str = DEFAULT_SHOP_UUID,
    extra: dict[str, str] | None = None,
) -> tuple[bool, str, dict[str, str]]:
    """Apply parsed (and optional explicit) token updates. Returns (applied, summary, updates)."""
    updates = parse_direct_style_updates(message)
    if extra:
        updates = {**updates, **extra}

    if not updates:
        return False, "", {}

    cm = ConfigManager(shop_uuid=shop_uuid)
    tokens = _merge_updates(cm.tokens, updates)
    cm.save_tokens(
        tokens,
        theme_name=tokens.colors.paletteName or "Custom Theme",
        change_summary={
            "zonesTouched": zones_touched_from_keys(updates.keys()),
            "humanSummary": "Direct style update from chat.",
        },
    )
    cm.reload()

    parts = [f"{_HUMAN_LABELS.get(k, k)} → {v}" for k, v in updates.items()]
    return True, "; ".join(parts), updates


def format_agent_hint(applied_summary: str) -> str:
    return (
        f"\n\n[System: Preview already updated — {applied_summary}. "
        "Confirm what changed in friendly plain language. "
        "Do NOT restart discovery, vibe questions, or theme packages. "
        "Set response_type to applied.]"
    )
