"""Chat-style zone tour: one question at a time with a small option batch.

Defines sub-steps per zone (``TourSubStep``), colour/layout option batches, preview
highlight CSS selectors, and free-text matching (``match_sub_step_choice``).

``tour_enrichment_payload()`` is what ``api_response.enrich_with_zone_tour()`` uses to
attach ``color_options`` / ``zone_options`` to each assistant chat message (all zones Z1–Z6).
"""

from __future__ import annotations

import re
from typing import Any

from .color_engine import normalize_hex, is_valid_color
from .message_parsers import CHOOSE_RE, parse_zone_option_id
from .zone_catalog import zone_label
from .zone_color_presets import (
    Z2_COLOR_OPTIONS,
    Z4_CATALOG_SURFACES,
    Z4_SHOWCASE_SURFACES,
    Z6_COLOR_OPTIONS,
    find_color_option,
)
from .zone_option_cache import option_cache_matches_sub_step
from .zone_option_resolver import resolve_tour_option
from .zone_presets import zone_options_for_code
from .zone_tour_types import StepKind, ZoneSubStep

# Re-export for backward compatibility.
__all__ = [
    "StepKind",
    "ZoneSubStep",
    "ZONE_SUB_STEPS",
    "build_sub_step_message",
    "color_choice_from_hex",
    "current_sub_step",
    "extract_hex_from_text",
    "match_sub_step_choice",
    "normalize_tour_input",
    "options_for_sub_step",
    "resolve_tour_option",
    "sub_steps_for_zone",
    "tour_enrichment_payload",
]


def _ids(options: list[dict[str, str]]) -> tuple[str, ...]:
    return tuple(o["id"] for o in options)


ZONE_SUB_STEPS: dict[str, tuple[ZoneSubStep, ...]] = {
    "Z1": (
        ZoneSubStep(
            "z1_palette",
            "Choose a **brand palette** that matches your mood — each card sets brand, "
            "accent & neutrals across the storefront. Or describe a vibe (e.g. *fresh & green*), "
            "upload a logo, or type your brand colours anytime in chat.",
            "palettes",
            (),
            highlight="Z1",
        ),
        ZoneSubStep(
            "z1_accent",
            "Pick an **accent** that complements your brand — used on buttons, links & prices. "
            "Each option explains why the pairing works.",
            "colors",
            (),
            highlight="Z1_ACCENT",
        ),
        ZoneSubStep(
            "z1_backdrop",
            "What **page backdrop** sits behind offers and product sections? "
            "Pick one of the four classics or say *warmer* / *cooler*.",
            "colors",
            (),
            highlight="Z1_BACKDROP",
        ),
        ZoneSubStep(
            "z1_motion",
            "**Page transitions** when customers move between sections — pick a style or *none*.",
            "layouts",
            ("z1_motion_fade", "z1_motion_slide", "z1_motion_none"),
            highlight="Z1",
        ),
    ),
    "Z2": (
        ZoneSubStep(
            "z2_layout",
            "How should your **hero & header** look? Pick a layout card or describe the vibe.",
            "layouts",
            tuple(p["id"] for p in zone_options_for_code("Z2")),
            highlight="Z2",
        ),
        ZoneSubStep(
            "z2_hero_bg",
            "Background **behind the banner photo** only — pick a hero band colour or name one.",
            "colors",
            _ids(Z2_COLOR_OPTIONS),
            highlight="Z2",
        ),
    ),
    "Z3": (
        ZoneSubStep(
            "z3_fonts",
            "Which **fonts** for intro and store information? Pick a pairing or tell me the style.",
            "layouts",
            tuple(p["id"] for p in zone_options_for_code("Z3")),
            highlight="Z3",
        ),
        ZoneSubStep(
            "z3_scale",
            "**Font size scaling** for intro and store information — pick a scale or say "
            "*bigger headings* / *more compact*.",
            "layouts",
            ("z3_scale_compact", "z3_scale_standard", "z3_scale_generous"),
            highlight="Z3",
        ),
        ZoneSubStep(
            "z3_text_colour",
            "Choose **heading text colour** that reads well on your background. "
            "Each swatch shows contrast — say *darker* or *warmer* for more options.",
            "colors",
            (),
            highlight="Z3",
        ),
    ),
    "Z4": (
        ZoneSubStep(
            "z4_showcase",
            "Background for **Our Products** — pick below or type a colour name.",
            "colors",
            _ids(Z4_SHOWCASE_SURFACES),
            highlight="Z4S",
        ),
        ZoneSubStep(
            "z4_catalog",
            "Background for **All Products & Services** — pick below or describe it.",
            "colors",
            _ids(Z4_CATALOG_SURFACES),
            highlight="Z4C",
        ),
        ZoneSubStep(
            "z4_layout",
            "How should **product cards** look in both sections? Pick a layout or describe it.",
            "layouts",
            tuple(p["id"] for p in zone_options_for_code("Z4")),
            highlight="Z4",
        ),
        ZoneSubStep(
            "z4_prices",
            "**Price display style** on product cards (both sections)? "
            "Each option shows sample prices from your catalogue — pick one or say "
            "*make prices stand out more*.",
            "layouts",
            (
                "z4_price_bold_red",
                "z4_price_accent",
                "z4_price_understated",
                "z4_price_badge_pill",
            ),
            highlight="Z4",
        ),
    ),
    "Z6": (
        ZoneSubStep(
            "z6_style",
            "**Button shape & style** for Follow, coupons & catalogue CTAs? Pick a card or describe it.",
            "layouts",
            tuple(p["id"] for p in zone_options_for_code("Z6")),
            highlight="Z6",
        ),
        ZoneSubStep(
            "z6_size",
            "**Button size** on Follow, coupon & catalogue CTAs? Pick a scale or say "
            "*bigger* / *smaller* (touch-friendly minimums apply).",
            "layouts",
            ("z6_size_compact", "z6_size_standard", "z6_size_large"),
            highlight="Z6",
        ),
        ZoneSubStep(
            "z6_cta_colour",
            "**CTA colour** for those buttons? Pick below or type a colour (e.g. berry, navy).",
            "colors",
            _ids(Z6_COLOR_OPTIONS),
            highlight="Z6",
        ),
    ),
}

# Legacy zone-key map — prefer ``zone_highlight.SUB_STEP_HIGHLIGHTS`` per sub-step id.


def sub_steps_for_zone(zone_code: str | None) -> tuple[ZoneSubStep, ...]:
    if not zone_code:
        return ()
    return ZONE_SUB_STEPS.get(zone_code.upper(), ())


def current_sub_step(zone_code: str | None, sub_index: int) -> ZoneSubStep | None:
    steps = sub_steps_for_zone(zone_code)
    if sub_index < 0 or sub_index >= len(steps):
        return None
    return steps[sub_index]


def normalize_tour_input(text: str) -> str:
    """Strip whitespace and trailing punctuation from chat input."""
    return text.strip().strip(".,;:!?\"' ")


def extract_hex_from_text(text: str) -> str | None:
    """Parse a hex colour from free text (e.g. '#BE185D.' or 'be185d')."""
    cleaned = normalize_tour_input(text)
    if not cleaned:
        return None
    # Prefer 6/8-digit hex before 3-digit shorthand (#BE185D must not parse as #BE1)
    for match in re.finditer(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{8}|[0-9a-fA-F]{3})", cleaned, re.I):
        candidate = f"#{match.group(1)}"
        if is_valid_color(candidate):
            return normalize_hex(candidate)
    bare = re.search(r"\b([0-9a-fA-F]{6})\b", cleaned, re.I)
    if bare:
        candidate = f"#{bare.group(1)}"
        if is_valid_color(candidate):
            return normalize_hex(candidate)
    return None


def _sub_step_color_template(zone_code: str, sub: ZoneSubStep) -> dict[str, str] | None:
    for oid in sub.option_ids:
        hit = find_color_option(zone_code, option_id=oid)
        if hit:
            return hit
    return None


def color_choice_from_hex(
    zone_code: str,
    sub: ZoneSubStep,
    hex_val: str,
) -> dict[str, str] | None:
    """Build an apply-able colour choice for a custom hex on the current sub-step."""
    if sub.kind != "colors":
        return None
    normalized = normalize_hex(hex_val) if is_valid_color(hex_val) else None
    if not normalized:
        return None
    template = _sub_step_color_template(zone_code, sub) or {}
    return {
        "id": "custom_hex",
        "name": normalized,
        "hex": normalized,
        "description": template.get("description", ""),
        "role": template.get("role", "accent"),
        "scope_zone": template.get("scope_zone", ""),
        "section": template.get("section", ""),
    }


def options_for_sub_step(
    zone_code: str,
    sub: ZoneSubStep,
    merchant_id: str,
    *,
    force_refresh: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (color_options, zone_options, theme_packages) for this sub-step."""
    from .zone_dynamic_options import generate_options_for_sub_step
    from .zone_tour import ZoneTourManager

    mgr = ZoneTourManager(merchant_id)
    if not force_refresh:
        cache = (mgr.get_state() or {}).get("optionCache") or {}
        if option_cache_matches_sub_step(cache, sub, merchant_id=merchant_id):
            colors = list(cache.get("colorOptions") or [])
            layouts = list(cache.get("zoneOptions") or [])
            packages = list(cache.get("themePackages") or [])
            return colors, layouts, packages
        if cache.get("subStepId") == sub.id:
            mgr.clear_option_cache()

    batch = mgr.get_option_batch()
    colors, layouts, packages = generate_options_for_sub_step(
        merchant_id, zone_code, sub, batch=batch
    )
    mgr.cache_sub_step_options(sub.id, colors, layouts, theme_packages=packages)
    return colors, layouts, packages


def match_sub_step_choice(
    zone_code: str,
    sub: ZoneSubStep,
    text: str,
    *,
    merchant_id: str | None = None,
) -> dict[str, str] | None:
    """Match only explicit swatch labels shown in chat (exact name).

    Fuzzy text, colour names, hex, and descriptions are handled by the Bedrock agent
    via ``apply_style_tokens`` / ``apply_zone_tour_choice`` / ``refresh_zone_tour_options``.
    """
    from .shop_context import get_shop_uuid

    raw = normalize_tour_input(text)
    if not raw:
        return None
    shop = merchant_id or get_shop_uuid()
    if not shop:
        return None

    choose = CHOOSE_RE.match(raw)
    if choose:
        raw = normalize_tour_input(choose.group(1))

    option_id = parse_zone_option_id(raw) or parse_zone_option_id(text) or ""
    hit = resolve_tour_option(
        shop,
        zone_code,
        sub,
        option_id=option_id,
        name=raw,
    )
    return hit


def _sub_step_prompt(sub: ZoneSubStep, merchant_id: str | None) -> str:
    if sub.id == "z4_prices" and merchant_id:
        from .z4_tour_options import price_style_recommendation_note

        return f"{sub.prompt}\n\n{price_style_recommendation_note(merchant_id)}"
    if sub.id == "z3_text_colour" and merchant_id:
        from .zone_tour import ZoneTourManager

        if ZoneTourManager(merchant_id).get_z3_text_colour_phase() == "body":
            return (
                "Now choose **body text colour** for intro and store information. "
                "Contrast is checked against your panel background — pick a swatch or "
                "say *darker* / *warmer*."
            )
    return sub.prompt


def build_sub_step_message(
    zone_code: str,
    sub: ZoneSubStep,
    *,
    intro: bool = False,
    merchant_id: str | None = None,
) -> str:
    """Short chat copy — theme/mood/step context lives on the tour banner (``zone_tour`` payload)."""
    prompt = _sub_step_prompt(sub, merchant_id)
    if intro:
        from .zone_catalog import zone_chat_intro

        name = zone_label(zone_code)
        hint = zone_chat_intro(zone_code)
        head = f"**{name}**" + (f" — {hint}" if hint else "")
        return f"{head}\n\n{prompt}"
    return prompt


def tour_enrichment_payload(
    zone_code: str | None,
    sub_index: int,
    *,
    merchant_id: str,
    intro: bool = False,
) -> dict[str, Any]:
    sub = current_sub_step(zone_code, sub_index)
    if not sub:
        return {}
    colors, layouts, theme_packages = options_for_sub_step(zone_code or "", sub, merchant_id)
    from .zone_dynamic_options import build_theme_context, sub_step_explanation
    from .zone_highlight import highlight_spec_for_zone_tour

    hl = highlight_spec_for_zone_tour(zone_code, sub.id)

    prompt = _sub_step_prompt(sub, merchant_id)
    payload: dict[str, Any] = {
        "current_prompt": prompt,
        "sub_step_index": sub_index,
        "sub_step_total": len(sub_steps_for_zone(zone_code)),
        "sub_step_id": sub.id,
        **hl.to_api_dict(),
        "color_options": colors,
        "zone_options": layouts,
        "theme_packages": theme_packages,
        "theme_context": build_theme_context(merchant_id),
        "step_explanation": sub_step_explanation(sub.id),
    }
    if sub.id == "z1_palette":
        from .z1_tour_options import z1_palette_already_configured
        from .config_manager import ConfigManager

        payload["palette_already_configured"] = z1_palette_already_configured(
            ConfigManager(shop_uuid=merchant_id).tokens
        )
    return payload
