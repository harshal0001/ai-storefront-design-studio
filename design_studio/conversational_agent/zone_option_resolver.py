"""Resolve tour swatch clicks to option dicts (cache, presets, or regenerated ids).

Used by ``zone_tour_flow.match_sub_step_choice`` and ``zone_tour_actions`` so clicks
never fall through to Bedrock when a swatch id is known.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from .zone_tour_types import ZoneSubStep

# Stable dynamic ids: dyn_{sub_step_id}_{8-char hex digest}
_DYN_OPTION_ID_RE = re.compile(r"^dyn_(.+)_([a-f0-9]{8})$", re.IGNORECASE)

# Z3 text swatches: z3_txt_{heading|body}_{archetype}_{batch}
_Z3_TEXT_ID_RE = re.compile(
    r"^z3_txt_(heading|body)_(black|dark_grey|brand_tinted|warm_dark)_(\d+)$",
    re.IGNORECASE,
)

_MAX_REGEN_BATCHES = 6
_REGEN_BATCH_COUNT = 8


def parse_dyn_option_id(option_id: str) -> tuple[str, str] | None:
    """``dyn_z6_cta_colour_b20c9a15`` → (``z6_cta_colour``, ``b20c9a15``)."""
    raw = (option_id or "").strip().lower()
    if not raw.startswith("dyn_"):
        return None
    rest = raw[4:]
    digest = rest.rsplit("_", 1)[-1]
    if len(digest) != 8 or not re.fullmatch(r"[a-f0-9]{8}", digest):
        return None
    sub_step_id = rest[: -(len(digest) + 1)]
    return (sub_step_id, digest) if sub_step_id else None


def find_generated_color_option(
    merchant_id: str,
    zone_code: str,
    sub: ZoneSubStep,
    option_id: str,
) -> dict[str, str] | None:
    """Resolve ``dyn_{sub_id}_{hash}`` by regenerating mood swatches."""
    from .zone_dynamic_options import generate_color_options_for_sub_step

    parsed = parse_dyn_option_id(option_id)
    if not parsed or parsed[0] != sub.id:
        return None
    key = option_id.lower()
    for batch in range(_MAX_REGEN_BATCHES):
        options = generate_color_options_for_sub_step(
            merchant_id,
            zone_code,
            sub,
            batch=batch,
            count=_REGEN_BATCH_COUNT,
        )
        for row in options:
            if (row.get("id") or "").lower() == key:
                return row
    return None


def find_z3_text_colour_option(
    merchant_id: str,
    option_id: str = "",
    *,
    name: str = "",
) -> dict[str, str] | None:
    """Resolve ``z3_txt_heading_dark_grey_0`` without relying on optionCache."""
    from .zone_dynamic_options import generate_z3_text_colour_options

    oid = (option_id or "").strip()
    match = _Z3_TEXT_ID_RE.match(oid)
    if not match:
        if not name:
            return None
        from .zone_tour import ZoneTourManager

        phase = ZoneTourManager(merchant_id).get_z3_text_colour_phase()
        text_role: Literal["heading", "body"] = "body" if phase == "body" else "heading"
        options = generate_z3_text_colour_options(
            merchant_id, text_role=text_role, limit=_REGEN_BATCH_COUNT
        )
        key = name.strip().lower()
        for row in options:
            if (row.get("name") or "").lower() == key:
                return row
        return None

    text_role: Literal["heading", "body"] = (
        "body" if match.group(1).lower() == "body" else "heading"
    )
    batch = int(match.group(3))
    options = generate_z3_text_colour_options(
        merchant_id, text_role=text_role, batch=batch, limit=_REGEN_BATCH_COUNT
    )
    key = oid.lower()
    for row in options:
        if (row.get("id") or "").lower() == key:
            return row
    return None


def find_dynamic_color_option(
    merchant_id: str,
    zone_code: str,
    *,
    option_id: str = "",
    name: str = "",
) -> dict[str, str] | None:
    """Match option id or display name against cached colour swatches."""
    from .zone_tour import ZoneTourManager

    oid = (option_id or "").strip()
    if oid.lower().startswith("z3_txt_"):
        hit = find_z3_text_colour_option(merchant_id, oid, name=name)
        if hit:
            return hit

    cached = ZoneTourManager(merchant_id).get_cached_color_options()
    if oid:
        key = oid.lower()
        for option in cached:
            if option.get("id", "").lower() == key:
                return dict(option)
    if name:
        key = name.strip().lower()
        for option in cached:
            option_name = option.get("name", "").lower()
            if option_name == key or key in option_name:
                return dict(option)
    return None


def _lookup_palette_option(
    merchant_id: str,
    *,
    option_id: str,
    name: str,
) -> dict[str, Any] | None:
    from .z1_tour_options import find_z1_palette_package

    if option_id:
        hit = find_z1_palette_package(merchant_id, option_id=option_id)
        if hit:
            return hit
    if name:
        hit = find_z1_palette_package(merchant_id, name=name)
        if hit and hit.get("name", "").lower() == name.strip().lower():
            return hit
    return None


def _lookup_color_option(
    merchant_id: str,
    zone_code: str,
    sub: ZoneSubStep,
    *,
    option_id: str,
    name: str,
) -> dict[str, Any] | None:
    from .zone_color_presets import find_color_option, is_zone_color_option_id
    from .z1_tour_options import find_z1_accent_option
    from .zone_tour import ZoneTourManager

    label_key = name.strip().lower()

    if option_id:
        if option_id.startswith("z3_txt_"):
            hit = find_z3_text_colour_option(merchant_id, option_id)
            if hit:
                return hit
        if option_id.startswith("dyn_"):
            hit = find_generated_color_option(merchant_id, zone_code, sub, option_id)
            if hit:
                return hit
        hit = find_dynamic_color_option(merchant_id, zone_code, option_id=option_id)
        if hit:
            return hit
        if option_id.startswith("z1_acc_"):
            hit = find_z1_accent_option(merchant_id, option_id)
            if hit:
                return hit
        if is_zone_color_option_id(zone_code, option_id):
            hit = find_color_option(zone_code, option_id=option_id)
            if hit:
                return hit

    if name:
        hit = find_dynamic_color_option(merchant_id, zone_code, name=name)
        if hit and hit.get("name", "").lower() == label_key:
            return hit
        for option in ZoneTourManager(merchant_id).get_cached_color_options():
            if option.get("name", "").lower() == label_key:
                return dict(option)
    return None


def _lookup_layout_option(
    merchant_id: str,
    *,
    option_id: str,
    name: str,
) -> dict[str, Any] | None:
    from .zone_tour import ZoneTourManager

    label_key = name.strip().lower()
    for option in ZoneTourManager(merchant_id).get_cached_zone_options():
        if option_id and (option.get("id") or "").lower() == option_id:
            return dict(option)
        if name and option.get("name", "").lower() == label_key:
            return dict(option)
    return None


def lookup_tour_option(
    merchant_id: str,
    zone_code: str,
    sub: ZoneSubStep,
    *,
    option_id: str = "",
    name: str = "",
) -> dict[str, Any] | None:
    """Single-pass resolve for the active sub-step (no cache refresh)."""
    oid = (option_id or "").lower()
    label = (name or "").strip()

    if sub.kind == "palettes":
        return _lookup_palette_option(merchant_id, option_id=oid, name=label)

    if sub.id == "z1_accent" and oid:
        from .z1_tour_options import find_z1_accent_option

        return find_z1_accent_option(merchant_id, oid)

    if sub.kind == "colors":
        return _lookup_color_option(merchant_id, zone_code, sub, option_id=oid, name=label)

    if sub.id == "z4_prices":
        from .z4_tour_options import resolve_z4_price_style_choice

        return resolve_z4_price_style_choice(merchant_id, option_id=oid, name=label)

    if sub.id == "z1_motion":
        from .z1_tour_options import find_z1_motion_option

        return find_z1_motion_option(merchant_id, option_id=oid, name=label)

    if sub.kind == "layouts":
        return _lookup_layout_option(merchant_id, option_id=oid, name=label)

    return None


def resolve_tour_option(
    merchant_id: str,
    zone_code: str,
    sub: ZoneSubStep,
    *,
    option_id: str = "",
    name: str = "",
) -> dict[str, Any] | None:
    """Resolve a swatch click; refresh cache once and retry if the first lookup misses."""
    from .zone_tour_flow import options_for_sub_step

    hit = lookup_tour_option(merchant_id, zone_code, sub, option_id=option_id, name=name)
    if hit:
        return hit
    if (option_id or "").strip() or (name or "").strip():
        options_for_sub_step(zone_code, sub, merchant_id, force_refresh=True)
        return lookup_tour_option(merchant_id, zone_code, sub, option_id=option_id, name=name)
    return None
