"""Validate ``optionCache`` entries against the active tour sub-step.

Stale cache rows (e.g. heading swatches during body text phase, accent colours on
the price-style step) are rejected so ``options_for_sub_step`` regenerates options.
"""

from __future__ import annotations

from typing import Any

from .zone_tour_types import ZoneSubStep


def z3_text_role_from_cache(colors: list[dict[str, Any]]) -> str | None:
    """Return ``heading`` or ``body`` when every cached id is a Z3 text swatch."""
    roles: set[str] = set()
    for option in colors:
        option_id = str(option.get("id", "")).lower()
        if "_heading_" in option_id:
            roles.add("heading")
        elif "_body_" in option_id:
            roles.add("body")
    return roles.pop() if len(roles) == 1 else None


def option_cache_matches_sub_step(
    cache: dict[str, Any],
    sub: ZoneSubStep,
    *,
    merchant_id: str | None = None,
) -> bool:
    """True when cached swatches match the current sub-step (and Z3 phase)."""
    if cache.get("subStepId") != sub.id:
        return False

    color_options = list(cache.get("colorOptions") or [])
    layout_options = list(cache.get("zoneOptions") or [])
    theme_packages = list(cache.get("themePackages") or [])

    validators: dict[str, Any] = {
        "z3_text_colour": _cache_valid_z3_text_colour,
        "z4_prices": _cache_valid_z4_prices,
        "z1_accent": _cache_valid_z1_accent,
        "z1_motion": _cache_valid_z1_motion,
        "z6_cta_colour": _cache_valid_z6_cta_colour,
    }
    custom = validators.get(sub.id)
    if custom is not None:
        return custom(
            color_options,
            layout_options,
            theme_packages,
            merchant_id=merchant_id,
        )

    if sub.kind == "palettes":
        return bool(theme_packages)
    if sub.kind == "layouts":
        return bool(layout_options)
    if sub.kind == "colors":
        return bool(color_options)
    return bool(color_options or layout_options or theme_packages)


def _cache_valid_z3_text_colour(
    colors: list[dict[str, Any]],
    _layouts: list[dict[str, Any]],
    _packages: list[dict[str, Any]],
    *,
    merchant_id: str | None,
) -> bool:
    if not colors or not all(
        str(option.get("id", "")).lower().startswith("z3_txt_") for option in colors
    ):
        return False
    cached_role = z3_text_role_from_cache(colors)
    if not cached_role or not merchant_id:
        return False
    from .zone_tour import ZoneTourManager

    phase = ZoneTourManager(merchant_id).get_z3_text_colour_phase()
    expected_role = "body" if phase == "body" else "heading"
    return cached_role == expected_role


def _cache_valid_z4_prices(
    colors: list[dict[str, Any]],
    layouts: list[dict[str, Any]],
    _packages: list[dict[str, Any]],
    **_: Any,
) -> bool:
    return (
        bool(layouts)
        and not colors
        and all(str(option.get("id", "")).startswith("z4_price_") for option in layouts)
    )


def _cache_valid_z1_accent(
    colors: list[dict[str, Any]],
    _layouts: list[dict[str, Any]],
    _packages: list[dict[str, Any]],
    **_: Any,
) -> bool:
    return bool(colors) and all(
        str(option.get("id", "")).startswith("z1_acc_") for option in colors
    )


def _cache_valid_z1_motion(
    _colors: list[dict[str, Any]],
    layouts: list[dict[str, Any]],
    _packages: list[dict[str, Any]],
    **_: Any,
) -> bool:
    return bool(layouts) and all(
        str(option.get("id", "")).startswith("z1_motion_") for option in layouts
    )


def _cache_valid_z6_cta_colour(
    colors: list[dict[str, Any]],
    _layouts: list[dict[str, Any]],
    _packages: list[dict[str, Any]],
    **_: Any,
) -> bool:
    return bool(colors) and all(
        str(option.get("id", "")).lower().startswith("dyn_z6_cta_colour_")
        or str(option.get("id", "")).startswith("cta_")
        for option in colors
    )
