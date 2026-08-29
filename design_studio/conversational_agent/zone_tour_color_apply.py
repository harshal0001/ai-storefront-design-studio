"""Colour choice helpers for the zone tour fast path (no Bedrock)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .zone_scopes import set_global_colors
from .z1_tour_options import fields_for_backdrop_apply

if TYPE_CHECKING:
    from .style_tokens import StyleTokens
    from .zone_tour import ZoneTourManager


def token_fields_for_color_role(role: str, hex_val: str) -> dict[str, str]:
    """Map a swatch role to ``apply_selection_to_tokens`` keyword arguments."""
    if role == "background":
        return {"background_color": hex_val}
    if role == "surface":
        return {"surface_color": hex_val}
    if role == "primary":
        return {"primary_color": hex_val, "accent_color": hex_val}
    if role == "text_heading":
        return {"text_primary": hex_val}
    if role == "text_body":
        return {"text_secondary": hex_val}
    return {"accent_color": hex_val}


def apply_tour_color_choice(
    mgr: "ZoneTourManager",
    zone: str,
    option: dict[str, str],
) -> None:
    """Persist one colour swatch to tokens for the correct scope."""
    hex_val = option["hex"]
    role = option.get("role", "accent")
    scope_zone = (option.get("scope_zone") or "").upper() or zone
    option_id = str(option.get("id", ""))

    if zone == "Z1" and role == "surface" and option_id.startswith("z3_"):
        scope_zone = "Z3"
    if zone == "Z1" and role == "background" and option_id.startswith("z1_bg_"):
        fields = fields_for_backdrop_apply(hex_val)
    else:
        fields = token_fields_for_color_role(role, hex_val)

    extra: dict[str, str] = {}
    if scope_zone == "Z4" and role == "accent":
        extra["option_id"] = "accent_scoped"
    if zone == "Z6":
        extra["option_id"] = "cta_scoped"

    mgr.apply_selection_to_tokens(scope_zone, **fields, **extra)  # type: ignore[arg-type]


def preview_tokens_for_z1_color(
    merchant_id: str,
    sub_step_id: str,
    choice: dict[str, str],
) -> "StyleTokens":
    """Build tokens for harmony pre-check before applying a Z1 colour."""
    from .config_manager import ConfigManager

    preview = ConfigManager(shop_uuid=merchant_id).tokens.model_copy(deep=True)
    role = choice.get("role", "accent")
    hex_val = choice["hex"]
    if sub_step_id == "z1_backdrop" and str(choice.get("id", "")).startswith("z1_bg_"):
        fields = fields_for_backdrop_apply(hex_val)
    else:
        fields = token_fields_for_color_role(role, hex_val)
    return set_global_colors(
        preview,
        primary=fields.get("primary_color", ""),
        accent=fields.get("accent_color", ""),
        background=fields.get("background_color", ""),
        surface=fields.get("surface_color", ""),
        text_primary=fields.get("text_primary", ""),
        text_secondary=fields.get("text_secondary", ""),
    )


def color_apply_summary(
    zone: str,
    option: dict[str, str],
    merchant_id: str,
    sub_step_id: str,
) -> str:
    """Human-readable confirmation after a colour swatch is applied."""
    from .color_engine import friendly_color_name

    if option.get("id") == "custom_hex":
        place = option.get("section") or option.get("description") or "this step"
        label = friendly_color_name(option.get("hex", ""))
        return f"Applied **{label}** — *{place}*."

    role = option.get("role", "accent")
    scope_key = option.get("scope_zone") or zone
    detail = (
        option.get("what_changes")
        or option.get("applies_to")
        or option.get("description")
        or option.get("section")
        or "this choice"
    )

    if zone == "Z1" and not option.get("scope_zone"):
        pairing = option.get("pairing_note")
        if pairing and role == "accent":
            return f"Accent → **{option['name']}**. {pairing}"
        if role == "background":
            return f"Page backdrop → **{option['name']}**. {detail}"
        return f"Updated **{option['name']}** — *{detail}*."

    if role == "text_heading":
        ratio = option.get("contrast_ratio", "")
        extra = f" (contrast {ratio})" if ratio else ""
        return f"Heading text colour → **{option['name']}**{extra}."
    if role == "text_body":
        ratio = option.get("contrast_ratio", "")
        extra = f" (contrast {ratio})" if ratio else ""
        return f"Body text colour → **{option['name']}**{extra}."
    if scope_key == "Z4S":
        return f"**Our Products** background → **{option['name']}**."
    if scope_key == "Z4C":
        return f"**All Products & Services** background → **{option['name']}**."
    if scope_key == "Z4" and role == "accent":
        return f"Price accent → **{option['name']}** on both product sections."
    if role == "background":
        return f"Hero band background → **{option['name']}**."
    if role == "surface":
        return f"Section fill → **{option['name']}**."
    return f"Applied **{option['name']}** — *{detail}*."
