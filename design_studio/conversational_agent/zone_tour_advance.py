"""Advance zone tour sub-steps after a choice is applied (UI click or agent tool)."""

from __future__ import annotations

from typing import Any

from .zone_tour import ZoneTourManager
from .zone_tour_flow import current_sub_step, sub_steps_for_zone

# Sub-step id → fields on apply_style_tokens / apply_zone_tour_choice that complete the step.
_SUB_STEP_APPLY_FIELDS: dict[str, frozenset[str]] = {
    "z1_palette": frozenset({"primary_color", "accent_color", "background_color", "surface_color"}),
    "z1_accent": frozenset({"accent_color"}),
    "z1_backdrop": frozenset({"background_color", "surface_color"}),
    "z1_motion": frozenset({"motion_transition", "option_id"}),
    "z2_layout": frozenset(
        {
            "hero_layout",
            "hero_overlay",
            "logo_placement",
            "tagline_placement",
            "store_name_style",
            "option_id",
        }
    ),
    "z2_hero_bg": frozenset({"background_color", "surface_color", "primary_color", "accent_color"}),
    "z3_fonts": frozenset(
        {"heading_font", "body_font", "heading_style", "body_style", "option_id"}
    ),
    "z3_scale": frozenset({"font_scale", "option_id"}),
    "z3_text_colour": frozenset({"text_primary", "text_secondary", "text_color", "option_id"}),
    "z4_showcase": frozenset(
        {"background_color", "surface_color", "primary_color", "accent_color"}
    ),
    "z4_catalog": frozenset({"background_color", "surface_color", "primary_color", "accent_color"}),
    "z4_layout": frozenset(
        {
            "product_card_shape",
            "product_card_layout",
            "product_card_shadow",
            "card_tap_animation",
            "card_shape",
            "card_layout",
            "card_shadow",
            "option_id",
        }
    ),
    "z4_prices": frozenset({"price_style", "option_id"}),
    "z6_style": frozenset(
        {
            "button_shape",
            "button_style",
            "button_press_animation",
            "border_radius",
            "option_id",
        }
    ),
    "z6_size": frozenset({"button_size", "option_id"}),
    "z6_cta_colour": frozenset(
        {"primary_color", "accent_color", "background_color", "surface_color"}
    ),
}

# Z4 tour zone may receive scoped applies on Z4S / Z4C.
_ZONE_SCOPE_ALIASES: dict[str, frozenset[str]] = {
    "Z4": frozenset({"Z4", "Z4S", "Z4C"}),
}


def _zone_matches_tour_step(tour_zone: str, apply_zone: str) -> bool:
    if not apply_zone:
        return True
    apply_zone = apply_zone.upper()
    tour_zone = tour_zone.upper()
    if apply_zone == tour_zone:
        return True
    allowed = _ZONE_SCOPE_ALIASES.get(tour_zone)
    return bool(allowed and apply_zone in allowed)


def apply_fulfills_current_sub_step(
    mgr: ZoneTourManager,
    *,
    apply_zone: str = "",
    applied_fields: set[str],
) -> bool:
    """True when the apply touches fields relevant to the active tour sub-step."""
    if not mgr.is_active():
        return False
    step = mgr.current_step()
    if not step or step.info_only:
        return False
    sub = current_sub_step(step.code, mgr.get_sub_step_index())
    if not sub:
        return False
    if not _zone_matches_tour_step(step.code, apply_zone):
        return False
    expected = _SUB_STEP_APPLY_FIELDS.get(sub.id)
    if not expected:
        return bool(applied_fields)
    return bool(applied_fields & expected)


def _collect_applied_fields_from_style_tokens(**kwargs: Any) -> set[str]:
    """Map non-empty apply_style_tokens args to logical field names."""
    field_map = {
        "hero_overlay": "hero_overlay",
        "hero_layout": "hero_layout",
        "logo_placement": "logo_placement",
        "tagline_placement": "tagline_placement",
        "store_name_style": "store_name_style",
        "heading_font": "heading_font",
        "body_font": "body_font",
        "font_scale": "font_scale",
        "heading_style": "heading_style",
        "body_style": "body_style",
        "product_card_shape": "product_card_shape",
        "product_card_layout": "product_card_layout",
        "product_card_shadow": "product_card_shadow",
        "price_style": "price_style",
        "card_tap_animation": "card_tap_animation",
        "button_shape": "button_shape",
        "button_style": "button_style",
        "button_size": "button_size",
        "button_press_animation": "button_press_animation",
        "border_radius": "border_radius",
        "spacing": "spacing",
        "motion_transition": "motion_transition",
        "offer_filter_preset": "offer_filter_preset",
        "background_color": "background_color",
        "surface_color": "surface_color",
        "primary_color": "primary_color",
        "accent_color": "accent_color",
        "text_color": "text_color",
        "text_primary": "text_primary",
        "text_secondary": "text_secondary",
        "zone_code": "zone_code",
    }
    out: set[str] = set()
    for key, val in kwargs.items():
        if val in ("", False, None):
            continue
        logical = field_map.get(key, key)
        out.add(logical)
    return out


def advance_tour_after_sub_step_apply(mgr: ZoneTourManager) -> str | None:
    """Move to the next sub-step or zone; return a short status line for tool output."""
    if not mgr.is_active():
        return None
    step = mgr.current_step()
    if not step:
        return None

    from .zone_tour_actions import _next_step_message

    if mgr.advance_sub_step():
        nxt = mgr.current_step()
        if nxt:
            return f"Tour advanced to sub-step {mgr.get_sub_step_index() + 1} of {len(sub_steps_for_zone(nxt.code))} in **{nxt.name}**."
    mgr.complete_current()
    nxt = mgr.current_step()
    if not nxt:
        return "Zone tour complete — all areas visited."
    return f"Finished **{step.name}**. Next area: **{nxt.name}** — {_next_step_message(mgr, nxt)[:120]}…"


def maybe_advance_after_style_tokens(mgr: ZoneTourManager, **tool_kwargs: Any) -> str:
    fields = _collect_applied_fields_from_style_tokens(**tool_kwargs)
    zone = (tool_kwargs.get("zone_code") or "").strip()
    if apply_fulfills_current_sub_step(mgr, apply_zone=zone, applied_fields=fields):
        return advance_tour_after_sub_step_apply(mgr) or ""
    return ""


def maybe_advance_after_zone_choice(
    mgr: ZoneTourManager, zone_code: str, **tool_kwargs: Any
) -> str:
    fields = {k for k, v in tool_kwargs.items() if v not in ("", None)}
    if tool_kwargs.get("option_id"):
        fields.add("option_id")
    step = mgr.current_step()
    if step and step.code.upper() == "Z3":
        sub = current_sub_step(step.code, mgr.get_sub_step_index())
        if sub and sub.id == "z3_text_colour":
            has_heading = bool(tool_kwargs.get("text_primary"))
            has_body = bool(tool_kwargs.get("text_secondary"))
            if has_heading and not has_body:
                mgr.set_z3_text_colour_phase("body")
                mgr.clear_dismissed_for_sub_step(sub.id)
                mgr.clear_option_cache()
                return (
                    "Heading text colour applied. Pick a **body text colour** next — "
                    "new swatches are in chat (WCAG contrast shown)."
                )
            if has_body:
                mgr.clear_z3_text_colour_phase()
            if (
                apply_fulfills_current_sub_step(mgr, apply_zone=zone_code, applied_fields=fields)
                and has_body
            ):
                return advance_tour_after_sub_step_apply(mgr) or ""
            return ""
    if apply_fulfills_current_sub_step(mgr, apply_zone=zone_code, applied_fields=fields):
        return advance_tour_after_sub_step_apply(mgr) or ""
    return ""
