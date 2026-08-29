"""Canonical zone colour options — injected by API (scoped vs global brand colours).

Curated swatches per zone/sub-step (Z2 hero, Z3 nav, Z4 showcase/catalogue, Z6 footer).
``find_color_option()`` resolves merchant picks from chat or UI chips to hex + role.
"""

from __future__ import annotations

from typing import Any, Literal

ColorRole = Literal["primary", "accent", "background", "surface"]


def _opt(
    id: str,
    name: str,
    hex: str,
    description: str,
    role: ColorRole = "accent",
    *,
    scope_zone: str = "",
    section: str = "",
) -> dict[str, str]:
    return {
        "id": id,
        "name": name,
        "hex": hex,
        "description": description,
        "role": role,
        "scope_zone": scope_zone,
        "section": section,
    }


# Z1 — brand colours (labels match what merchants see in the preview)
Z1_COLOR_OPTIONS: list[dict[str, str]] = [
    _opt(
        "warm_caramel",
        "Warm Caramel",
        "#C45B28",
        "Follow button & main brand accent.",
        "primary",
        section="Follow button & accents",
    ),
    _opt(
        "aegean_blue",
        "Aegean Blue",
        "#1E5F8C",
        "Follow button & main brand accent.",
        "primary",
        section="Follow button & accents",
    ),
    _opt(
        "bg_cream",
        "Soft cream backdrop",
        "#F8F4EF",
        "Page backdrop behind offers & product sections.",
        "background",
        section="Page backdrop",
    ),
    _opt(
        "bg_slate",
        "Cool slate backdrop",
        "#EEF2F6",
        "Page backdrop behind offers & product sections.",
        "background",
        section="Page backdrop",
    ),
    _opt(
        "surf_white",
        "Clean white panels",
        "#FFFFFF",
        "Store name, tagline & intro panel background.",
        "surface",
        section="Store name & intro",
    ),
    _opt(
        "surf_ivory",
        "Warm ivory panels",
        "#FFF8F0",
        "Store name, tagline & intro panel background.",
        "surface",
        section="Store name & intro",
    ),
    _opt(
        "accent_berry",
        "Berry accent",
        "#B6306A",
        "Secondary accent for highlights, links & price tags.",
        "accent",
        section="Accent highlights",
    ),
    _opt(
        "accent_teal",
        "Teal accent",
        "#0D9488",
        "Secondary accent for highlights, links & price tags.",
        "accent",
        section="Accent highlights",
    ),
]

Z2_COLOR_OPTIONS: list[dict[str, str]] = [
    _opt(
        "hero_bg_blush",
        "Blush hero band",
        "#FCE8EC",
        "Background strip behind the banner photo only.",
        "background",
        section="Hero banner background",
    ),
    _opt(
        "hero_bg_slate",
        "Cool grey hero",
        "#E8ECF0",
        "Background strip behind the banner photo only.",
        "background",
        section="Hero banner background",
    ),
    _opt(
        "hero_bg_mint",
        "Soft mint hero",
        "#E6F4EF",
        "Background strip behind the banner photo only.",
        "background",
        section="Hero banner background",
    ),
    _opt(
        "hero_bg_ink",
        "Deep ink hero",
        "#1E293B",
        "Dark background behind the banner photo only.",
        "background",
        section="Hero banner background",
    ),
]

Z3_COLOR_OPTIONS: list[dict[str, str]] = [
    _opt(
        "z3_surf_white", "White intro panels", "#FFFFFF", "Intro & info sections only.", "surface"
    ),
    _opt("z3_surf_sand", "Sand intro panels", "#F5F0E6", "Intro & info sections only.", "surface"),
    _opt("z3_surf_lavender", "Lavender intro", "#F3EEFA", "Intro & info sections only.", "surface"),
    _opt(
        "z3_bg_pale",
        "Pale page behind intro",
        "#F0F4F8",
        "Section backdrop in typography zone.",
        "background",
    ),
]

# Z4 — split: Our Products (showcase) vs All Products (catalogue)
Z4_SHOWCASE_SURFACES: list[dict[str, str]] = [
    _opt(
        "showcase_mint",
        "Mint — Our Products",
        "#E8F5F0",
        "Background for the Our Products carousel only.",
        "surface",
        scope_zone="Z4S",
        section="Our Products",
    ),
    _opt(
        "showcase_blush",
        "Blush — Our Products",
        "#FDEEEB",
        "Background for the Our Products carousel only.",
        "surface",
        scope_zone="Z4S",
        section="Our Products",
    ),
    _opt(
        "showcase_white",
        "White — Our Products",
        "#FFFFFF",
        "Background for the Our Products carousel only.",
        "surface",
        scope_zone="Z4S",
        section="Our Products",
    ),
]

Z4_CATALOG_SURFACES: list[dict[str, str]] = [
    _opt(
        "catalog_grey",
        "Grey — All Products",
        "#F1F3F5",
        "Background for All Products & Services only.",
        "surface",
        scope_zone="Z4C",
        section="All Products & Services",
    ),
    _opt(
        "catalog_ivory",
        "Ivory — All Products",
        "#FFF8F0",
        "Background for All Products & Services only.",
        "surface",
        scope_zone="Z4C",
        section="All Products & Services",
    ),
    _opt(
        "catalog_lavender",
        "Lavender — All Products",
        "#F3EEFA",
        "Background for All Products & Services only.",
        "surface",
        scope_zone="Z4C",
        section="All Products & Services",
    ),
]

Z4_ACCENT_OPTIONS: list[dict[str, str]] = [
    _opt(
        "accent_coral",
        "Coral prices",
        "#E85D4C",
        "Price accent on both product sections.",
        "accent",
        scope_zone="Z4",
        section="Prices (both sections)",
    ),
    _opt(
        "accent_teal",
        "Teal prices",
        "#0D9488",
        "Price accent on both product sections.",
        "accent",
        scope_zone="Z4",
        section="Prices (both sections)",
    ),
    _opt(
        "accent_violet",
        "Violet prices",
        "#7C3AED",
        "Price accent on both product sections.",
        "accent",
        scope_zone="Z4",
        section="Prices (both sections)",
    ),
]

Z4_COLOR_OPTIONS: list[dict[str, str]] = (
    Z4_SHOWCASE_SURFACES + Z4_CATALOG_SURFACES + Z4_ACCENT_OPTIONS
)

Z6_COLOR_OPTIONS: list[dict[str, str]] = [
    _opt(
        "cta_berry",
        "Berry CTA",
        "#BE185D",
        "Follow button, coupon buttons & catalogue CTA.",
        "primary",
        section="Buttons & CTAs",
    ),
    _opt(
        "cta_navy",
        "Navy CTA",
        "#1E3A5F",
        "Follow button, coupon buttons & catalogue CTA.",
        "primary",
        section="Buttons & CTAs",
    ),
    _opt(
        "cta_emerald",
        "Emerald CTA",
        "#059669",
        "Follow button, coupon buttons & catalogue CTA.",
        "primary",
        section="Buttons & CTAs",
    ),
]

ZONE_COLOR_OPTIONS: dict[str, list[dict[str, str]]] = {
    "Z1": Z1_COLOR_OPTIONS,
    "Z2": Z2_COLOR_OPTIONS,
    "Z3": Z3_COLOR_OPTIONS,
    "Z4": Z4_COLOR_OPTIONS,
    "Z6": Z6_COLOR_OPTIONS,
}

_COLOR_BY_ID: dict[str, dict[str, str]] = {}
for _zone, _opts in ZONE_COLOR_OPTIONS.items():
    for _o in _opts:
        entry = {**_o, "tour_zone": _zone}
        _COLOR_BY_ID[_o["id"]] = entry


def zone_color_options_for_code(zone_code: str | None) -> list[dict[str, Any]]:
    if not zone_code:
        return []
    return list(ZONE_COLOR_OPTIONS.get(zone_code.upper(), []))


def find_color_option(
    zone_code: str,
    *,
    option_id: str = "",
    name: str = "",
    merchant_id: str | None = None,
) -> dict[str, str] | None:
    from .shop_context import get_shop_uuid
    from .zone_option_resolver import find_dynamic_color_option

    shop = merchant_id or get_shop_uuid()
    if shop:
        hit = find_dynamic_color_option(
            shop,
            zone_code,
            option_id=option_id,
            name=name,
        )
        if hit:
            return hit
    if option_id:
        hit = _COLOR_BY_ID.get(option_id.lower())
        if hit and hit.get("tour_zone") == zone_code.upper():
            return hit
    if name:
        key = name.strip().lower()
        for o in ZONE_COLOR_OPTIONS.get(zone_code.upper(), []):
            if o["name"].lower() == key:
                return o
    return None


def is_zone_color_option_id(zone_code: str, option_id: str) -> bool:
    """True for static catalogue ids and tour-generated colour option ids."""
    oid = option_id.lower()
    if oid.startswith(("dyn_", "z1_", "z2_", "z3_", "z4_", "z6_")):
        return True
    hit = _COLOR_BY_ID.get(oid)
    return bool(hit and hit.get("tour_zone") == zone_code.upper())
