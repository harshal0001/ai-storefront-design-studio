"""Section-focus options — dynamic swatches, layouts, or agent for ambiguous style asks.

Colour and layout batches are generated from the merchant's **mood tags + theme seed**
(see ``generate_color_options_for_sub_step`` / ``generate_layout_options_for_sub_step``).
Interpretive requests like *more style* fall through to the Bedrock agent.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from .config_manager import ConfigManager
from .page_colors import is_page_color_request, resolve_color_from_text
from .section_focus import SectionFocus
from .zone_catalog import enrich_color_options, enrich_zone_options, zone_label
from .zone_color_presets import find_color_option
from .zone_focused_colors import resolve_zone_color_target
from .zone_scopes import set_zone_color_scope
from .zone_tour_intent import user_wants_more_options
from .zone_tour_types import ZoneSubStep

FocusRequestKind = Literal["color", "layout", "agent"]

# In-memory option cache per merchant (dev server).
_focus_option_cache: dict[str, dict[str, Any]] = {}

_SUGGESTION_INTENT_RE = re.compile(
    r"\b(?:suggest(?:ion)?s?|ideas?|recommend(?:ation)?s?|inspiration)\b",
    re.I,
)
_COLOUR_TOPIC_RE = re.compile(
    r"\b(?:background|backdrop|panel|surface|colou?r|fill)\b",
    re.I,
)
_LAYOUT_INTENT_RE = re.compile(
    r"\b(?:layout|grid|shape|shadow|list\s+view|columns?|arrangement|"
    r"card\s+style|product\s+card|tiles?)\b",
    re.I,
)
_STYLE_AMBIGUOUS_RE = re.compile(
    r"\b(?:style|styling|look|appearance|aesthetic|vibe|feel)\b",
    re.I,
)
_BACKGROUND_SUGGEST_RE = re.compile(
    r"\b(?:background|backdrop|panel|surface)\b.*\b(?:suggest|idea|option|choice|more)\b"
    r"|\b(?:suggest|give|show|more|another|extra).*\b(?:background|backdrop|panel|surface)\b",
    re.I,
)
_COLOR_OPTIONS_INTENT_RE = re.compile(
    r"\b(?:colou?r\s+options?|options?\s+for\s+(?:the\s+)?colou?r)\b"
    r"|\b(?:give|show)\s+(?:me\s+)?(?:some\s+)?(?:colou?r\s+)?options?\b"
    r"|\bwhat\s+colou?rs?\b",
    re.I,
)

_FOCUS_ROLE_COPY: dict[str, str] = {
    "cardFace": "Updates the **product card tile colour** in this section only.",
    "surface": "Updates the **panel fill** behind text or controls in this section.",
    "background": "Updates the **section backdrop** colour in this section only.",
    "primary": "Updates **brand accent** in this highlighted area.",
    "accent": "Updates **accent highlights** in this highlighted area.",
}


def _focus_supports_layout(focus: SectionFocus) -> bool:
    if focus.zone in ("Z2", "Z4", "Z4C", "Z4S", "Z6"):
        return True
    return focus.element_id in (
        "catalog_cards",
        "showcase_cards",
        "hero_banner",
        "hero_store_name",
        "follow_button",
    )


def user_wants_focused_layout_options(message: str, focus: SectionFocus | None) -> bool:
    text = (message or "").strip()
    if not text or not focus or not _focus_supports_layout(focus):
        return False
    return bool(_LAYOUT_INTENT_RE.search(text))


def user_wants_focused_color_suggestions(
    message: str,
    focus: SectionFocus | None,
) -> bool:
    """Explicit colour / background asks — not generic *more options* or *style*."""
    text = (message or "").strip()
    if not text or not focus:
        return False
    if focus.element_id == "page_backdrop":
        return False
    if is_page_color_request(text):
        return False
    if resolve_color_from_text(text):
        return False
    if not resolve_zone_color_target(focus, text or "background"):
        return False
    if user_wants_focused_layout_options(text, focus):
        return False
    if _STYLE_AMBIGUOUS_RE.search(text) and not _COLOUR_TOPIC_RE.search(text):
        return False
    if _COLOR_OPTIONS_INTENT_RE.search(text):
        return True
    if _BACKGROUND_SUGGEST_RE.search(text):
        return True
    if _SUGGESTION_INTENT_RE.search(text) and _COLOUR_TOPIC_RE.search(text):
        return True
    if user_wants_more_options(text) and _COLOUR_TOPIC_RE.search(text):
        return True
    return False


def classify_focused_request(
    message: str,
    focus: SectionFocus | None,
) -> FocusRequestKind | None:
    """Route focus UI messages: colour swatches, layout swatches, or agent."""
    if not focus or not (message or "").strip():
        return None
    if resolve_color_from_text(message) or is_page_color_request(message):
        return None
    if user_wants_focused_layout_options(message, focus):
        return "layout"
    if user_wants_focused_color_suggestions(message, focus):
        return "color"
    if user_wants_more_options(message) and _STYLE_AMBIGUOUS_RE.search(message):
        return "agent"
    if user_wants_more_options(message):
        return "agent"
    return None


def _role_label(role: str) -> str:
    return {
        "cardFace": "card colour",
        "surface": "panel fill",
        "background": "section background",
        "primary": "accent colour",
        "accent": "accent colour",
    }.get(role, "colour")


def _next_batch(merchant_id: str, kind: str) -> int:
    cache = _focus_option_cache.get(merchant_id) or {}
    if cache.get("kind") == kind:
        return int(cache.get("batch", 0)) + 1
    return 0


def _synthetic_color_sub_step(zone_code: str, role: str) -> ZoneSubStep:
    from .zone_color_presets import ZONE_COLOR_OPTIONS

    zone = zone_code.upper()
    presets = [p for p in ZONE_COLOR_OPTIONS.get(zone, []) if p.get("role") == role]
    if not presets and zone in ("Z4C", "Z4S"):
        presets = [p for p in ZONE_COLOR_OPTIONS.get("Z4", []) if p.get("role") == role]
    ids = tuple(p["id"] for p in presets[:1]) if presets else (f"focus_tpl_{zone}_{role}",)
    return ZoneSubStep(
        id=f"focus_{zone.lower()}_{role}",
        prompt="",
        kind="colors",
        option_ids=ids,
    )


def _layout_sub_step_for_focus(focus: SectionFocus) -> ZoneSubStep | None:
    from .zone_presets import zone_options_for_code

    zone = focus.zone.upper()
    if zone in ("Z4", "Z4C", "Z4S") or focus.element_id in ("catalog_cards", "showcase_cards"):
        presets = zone_options_for_code("Z4")
        return ZoneSubStep(
            "focus_z4_layout",
            "Product card layout",
            "layouts",
            tuple(p["id"] for p in presets),
            highlight="Z4",
        )
    if zone == "Z6" or focus.section_id == "buttons":
        from .zone_tour_flow import ZONE_SUB_STEPS

        z6 = ZONE_SUB_STEPS["Z6"]
        style = next((s for s in z6 if s.id == "z6_style"), None)
        if style:
            return ZoneSubStep(
                "focus_z6_style",
                style.prompt,
                "layouts",
                style.option_ids,
                highlight="Z6",
            )
    if zone == "Z2" or focus.section_id == "hero":
        presets = zone_options_for_code("Z2")
        return ZoneSubStep(
            "focus_z2_layout",
            "Hero layout",
            "layouts",
            tuple(p["id"] for p in presets),
            highlight="Z2",
        )
    return None


def generate_focused_color_suggestions(
    merchant_id: str,
    focus: SectionFocus,
    message: str,
    *,
    batch: int = 0,
) -> list[dict[str, str]]:
    """Four mood-matched colour swatches (dynamic hex from theme + mood)."""
    from .zone_dynamic_options import generate_color_options_for_sub_step

    target = resolve_zone_color_target(focus, message or "background")
    if not target:
        return []
    zone_code, role = target
    sub = _synthetic_color_sub_step(zone_code, role)
    options = generate_color_options_for_sub_step(
        merchant_id,
        zone_code,
        sub,
        user_request=message,
        batch=batch,
        count=4,
    )
    copy = _FOCUS_ROLE_COPY.get(role, _FOCUS_ROLE_COPY["background"])
    for row in options:
        row["role"] = role
        row["scope_zone"] = zone_code
        row["section"] = _role_label(role).title()
        row["description"] = copy
        row["what_changes"] = copy
        row["applies_to"] = copy
    return options


def generate_focused_layout_suggestions(
    merchant_id: str,
    focus: SectionFocus,
    message: str,
    *,
    batch: int = 0,
) -> list[dict[str, str]]:
    """Four mood-ranked layout presets for the focused zone."""
    from .zone_dynamic_options import generate_layout_options_for_sub_step

    sub = _layout_sub_step_for_focus(focus)
    if not sub:
        return []
    zone_code = "Z4" if focus.zone in ("Z4C", "Z4S") else focus.zone
    return generate_layout_options_for_sub_step(
        merchant_id,
        zone_code,
        sub,
        user_request=message,
        batch=batch,
        limit=4,
    )


def _cache_focus_options(
    merchant_id: str,
    *,
    kind: str,
    zone: str,
    role: str = "",
    color_options: list[dict] | None = None,
    zone_options: list[dict] | None = None,
    batch: int = 0,
) -> None:
    _focus_option_cache[merchant_id] = {
        "kind": kind,
        "zone": zone,
        "role": role,
        "batch": batch,
        "colorOptions": list(color_options or []),
        "zoneOptions": list(zone_options or []),
    }


def get_cached_focus_options(merchant_id: str) -> list[dict[str, str]]:
    return list((_focus_option_cache.get(merchant_id) or {}).get("colorOptions") or [])


def get_cached_focus_layout_options(merchant_id: str) -> list[dict[str, str]]:
    return list((_focus_option_cache.get(merchant_id) or {}).get("zoneOptions") or [])


def _match_option_name(options: list[dict[str, str]], label: str) -> dict[str, str] | None:
    key = label.strip().lower()
    if not key:
        return None
    for row in options:
        if (row.get("name") or "").strip().lower() == key:
            return dict(row)
    return None


def _regenerate_focused_color_by_name(
    merchant_id: str,
    focus: SectionFocus,
    label: str,
) -> dict[str, str] | None:
    target = resolve_zone_color_target(focus, "background")
    if not target:
        return None
    zone_code, role = target
    for batch in range(8):
        options = generate_focused_color_suggestions(merchant_id, focus, "background", batch=batch)
        hit = _match_option_name(options, label)
        if hit:
            _cache_focus_options(
                merchant_id,
                kind="color",
                zone=zone_code,
                role=role,
                color_options=options,
                batch=batch,
            )
            return hit
    return None


def resolve_focused_color_option(
    merchant_id: str,
    focus: SectionFocus,
    *,
    option_id: str = "",
    name: str = "",
) -> dict[str, str] | None:
    from .message_parsers import parse_choose_message
    from .zone_option_resolver import find_generated_color_option

    oid = (option_id or "").strip().lower()
    label = (name or "").strip()
    chosen = parse_choose_message(label) or parse_choose_message(name)
    if chosen:
        label = chosen

    cached = get_cached_focus_options(merchant_id)
    if oid:
        for row in cached:
            if (row.get("id") or "").lower() == oid:
                return dict(row)
        hit = find_color_option(focus.zone, option_id=oid, merchant_id=merchant_id)
        if hit:
            return hit
        target = resolve_zone_color_target(focus, "background")
        if target:
            zone_code, role = target
            sub = _synthetic_color_sub_step(zone_code, role)
            generated = find_generated_color_option(merchant_id, zone_code, sub, option_id)
            if generated:
                return generated
    if label:
        hit = _match_option_name(cached, label)
        if hit:
            return hit
        return _regenerate_focused_color_by_name(merchant_id, focus, label)
    return None


def resolve_focused_layout_option(
    merchant_id: str,
    focus: SectionFocus,
    *,
    option_id: str = "",
    name: str = "",
) -> dict[str, str] | None:
    from .message_parsers import parse_choose_message

    oid = (option_id or "").strip().lower()
    label = (name or "").strip()
    chosen = parse_choose_message(label) or parse_choose_message(name)
    if chosen:
        label = chosen

    cached = get_cached_focus_layout_options(merchant_id)
    if oid:
        for row in cached:
            if (row.get("id") or "").lower() == oid:
                return dict(row)
    if label:
        hit = _match_option_name(cached, label)
        if hit:
            return hit
    sub = _layout_sub_step_for_focus(focus)
    if not sub or not oid:
        return None
    for batch in range(6):
        for row in generate_focused_layout_suggestions(merchant_id, focus, "layout", batch=batch):
            if (row.get("id") or "").lower() == oid:
                return row
    return None


def resolve_focused_option(
    merchant_id: str,
    focus: SectionFocus,
    *,
    option_id: str = "",
    name: str = "",
) -> tuple[dict[str, str] | None, str]:
    """Return (option, kind) where kind is ``color`` or ``layout``."""
    cache = _focus_option_cache.get(merchant_id) or {}
    kind = cache.get("kind", "color")
    if kind == "layout" or (option_id and not option_id.startswith("dyn_focus_")):
        layout_hit = resolve_focused_layout_option(
            merchant_id, focus, option_id=option_id, name=name
        )
        if layout_hit:
            return layout_hit, "layout"
    color_hit = resolve_focused_color_option(merchant_id, focus, option_id=option_id, name=name)
    if color_hit:
        return color_hit, "color"
    layout_hit = resolve_focused_layout_option(merchant_id, focus, option_id=option_id, name=name)
    if layout_hit:
        return layout_hit, "layout"
    return None, ""


# Back-compat alias
resolve_focused_swatch_option = resolve_focused_color_option


def focused_swatch_missed_message(choice_name: str, focus: SectionFocus) -> str:
    area = focus.display_label or zone_label(focus.zone)
    return (
        f'Could not apply **"{choice_name}"** for **{area}**. '
        "Click a **swatch button** under the latest message, or rephrase "
        "(e.g. *give me color options* or *more layout options*)."
    )


def apply_focused_color_option(
    merchant_id: str,
    option: dict[str, str],
    focus: SectionFocus,
) -> str:
    zone = (option.get("scope_zone") or focus.zone or "").upper()
    role = option.get("role", "background")
    hex_val = option.get("hex", "")
    if not hex_val:
        return ""

    cm = ConfigManager(shop_uuid=merchant_id)
    tokens = cm.tokens.model_copy(deep=True)
    scope_kw: dict[str, str] = {}
    if role == "cardFace":
        scope_kw["card_face"] = hex_val
    elif role == "surface":
        scope_kw["surface"] = hex_val
    elif role in ("primary", "accent"):
        scope_kw["primary"] = hex_val
        scope_kw["accent"] = hex_val
    else:
        scope_kw["background"] = hex_val
    tokens = set_zone_color_scope(tokens, zone, **scope_kw)

    cm.save_tokens(
        tokens,
        theme_name=tokens.colors.paletteName or "Custom Theme",
        change_summary={
            "zonesTouched": [zone],
            "humanSummary": f"{focus.display_label} {role} → {option.get('name', hex_val)}.",
        },
    )
    cm.reload()
    return f"{_role_label(role)} → **{option.get('name', 'your pick')}**."


def apply_focused_layout_option(
    merchant_id: str,
    option: dict[str, str],
    focus: SectionFocus,
) -> str:
    from .zone_tour import ZoneTourManager

    oid = option.get("id", "")
    apply_zone = "Z4" if focus.zone in ("Z4C", "Z4S") else focus.zone
    ZoneTourManager(merchant_id).apply_selection_to_tokens(apply_zone, option_id=oid)
    detail = option.get("what_changes") or option.get("description") or "layout updated"
    return f"**{option.get('name', oid)}** — {detail}"


apply_focused_swatch_option = apply_focused_color_option


def build_focused_color_response(
    merchant_id: str,
    user_message: str,
    focus: SectionFocus,
) -> dict[str, Any]:
    target = resolve_zone_color_target(focus, user_message or "background")
    if not target:
        return {}
    zone_code, role = target
    batch = _next_batch(merchant_id, "color")
    options = generate_focused_color_suggestions(merchant_id, focus, user_message, batch=batch)
    if not options:
        return {}

    _cache_focus_options(
        merchant_id,
        kind="color",
        zone=zone_code,
        role=role,
        color_options=options,
        batch=batch,
    )
    from .zone_dynamic_options import build_theme_context

    mood_line = build_theme_context(merchant_id).get("mood_line", "")
    names = ", ".join(o.get("name", "") for o in options[:4] if o.get("name"))
    area = focus.display_label or zone_label(zone_code)
    message = (
        f"Here are **{len(options)}** {_role_label(role)} options for **{area}** — "
        f"pick a swatch ({names}). Changes apply only to the highlighted section."
    )
    if mood_line:
        message = f"{message}\n\n{mood_line}"
    return {
        "type": "color_options",
        "message": message,
        "color_options": enrich_color_options(zone_code, options),
        "response_type": "color_options",
    }


def build_focused_layout_response(
    merchant_id: str,
    user_message: str,
    focus: SectionFocus,
) -> dict[str, Any]:
    batch = _next_batch(merchant_id, "layout")
    options = generate_focused_layout_suggestions(merchant_id, focus, user_message, batch=batch)
    if not options:
        return {}

    zone_code = "Z4" if focus.zone in ("Z4C", "Z4S") else focus.zone
    _cache_focus_options(
        merchant_id,
        kind="layout",
        zone=zone_code,
        zone_options=options,
        batch=batch,
    )
    from .zone_dynamic_options import build_theme_context

    mood_line = build_theme_context(merchant_id).get("mood_line", "")
    names = ", ".join(o.get("name", "") for o in options[:4] if o.get("name"))
    area = focus.display_label or zone_label(zone_code)
    message = (
        f"Here are **{len(options)}** layout & card style options for **{area}** — "
        f"pick one ({names}). Product card settings apply across both product sections."
    )
    if mood_line:
        message = f"{message}\n\n{mood_line}"
    return {
        "type": "zone_options",
        "message": message,
        "zone_options": enrich_zone_options(zone_code, options),
        "response_type": "color_options",
    }


def build_focused_suggestions_response(
    merchant_id: str,
    user_message: str,
    focus: SectionFocus,
) -> dict[str, Any]:
    """Dispatch by classified request kind."""
    kind = classify_focused_request(user_message, focus)
    if kind == "layout":
        return build_focused_layout_response(merchant_id, user_message, focus)
    if kind == "color":
        return build_focused_color_response(merchant_id, user_message, focus)
    return {}
