"""Apply zone tour selections to ``StyleTokens`` (one handler per zone code)."""

from __future__ import annotations

from typing import Any

from .style_tokens import StyleTokens
from .zone_scopes import set_global_colors, set_zone_color_scope

# Hero layout presets keyed by tour option id (Z2).
_HERO_PRESETS: dict[str, dict[str, str]] = {
    "classic_center": {
        "layout": "fullWidth",
        "overlay": "lightScrim",
        "logoPlacement": "center",
        "taglinePlacement": "center",
    },
    "modern_left": {
        "layout": "fullWidth",
        "overlay": "autoScrim",
        "logoPlacement": "left",
        "taglinePlacement": "bottomLeft",
    },
    "bold_dark": {
        "layout": "fullWidth",
        "overlay": "darkScrim",
        "logoPlacement": "center",
        "taglinePlacement": "center",
        "storeNameStyle": "bold",
    },
    "minimal_clean": {
        "layout": "fullWidth",
        "overlay": "none",
        "logoPlacement": "right",
        "taglinePlacement": "bottomRight",
        "storeNameStyle": "subtle",
    },
    "split_hero": {
        "layout": "splitImageText",
        "overlay": "lightScrim",
        "logoPlacement": "left",
        "taglinePlacement": "bottomLeft",
        "storeNameStyle": "balanced",
    },
    "carousel_hero": {
        "layout": "carousel",
        "overlay": "autoScrim",
        "logoPlacement": "center",
        "taglinePlacement": "center",
        "storeNameStyle": "bold",
    },
    "editorial_tagline": {
        "layout": "fullWidth",
        "overlay": "lightScrim",
        "logoPlacement": "right",
        "taglinePlacement": "bottomRight",
        "storeNameStyle": "subtle",
    },
    "logo_forward": {
        "layout": "fullWidth",
        "overlay": "autoScrim",
        "logoPlacement": "left",
        "taglinePlacement": "bottomLeft",
        "storeNameStyle": "bold",
    },
}

# Product card layout presets (Z4).
_PRODUCT_CARD_PRESETS: dict[str, dict[str, str]] = {
    "soft_grid": {"shape": "rounded", "layout": "grid2", "shadow": "subtle"},
    "bold_grid": {"shape": "rounded", "layout": "grid2", "shadow": "elevated"},
    "grid_three": {"shape": "rounded", "layout": "grid3", "shadow": "subtle"},
    "list_view": {"shape": "rounded", "layout": "list", "shadow": "flat"},
    "featured_mix": {"shape": "rounded", "layout": "featuredPlusGrid", "shadow": "subtle"},
    "sharp_minimal": {"shape": "sharp", "layout": "grid2", "shadow": "flat"},
    "floating_cards": {"shape": "rounded", "layout": "grid3", "shadow": "floating"},
    "airy_list": {"shape": "rounded", "layout": "list", "shadow": "subtle"},
}

# Legacy typography option ids (Z3 fonts).
_LEGACY_FONT_PRESETS: dict[str, dict[str, str]] = {
    "elegant_serif": {"headingFont": "Playfair Display", "bodyFont": "Lato"},
    "modern_sans": {"headingFont": "Montserrat", "bodyFont": "Roboto"},
    "friendly_rounded": {"headingFont": "Nunito", "bodyFont": "Open Sans"},
    "compact_pro": {"headingFont": "Inter", "bodyFont": "Inter"},
}


def apply_zone_selection(
    tokens: StyleTokens,
    zone_code: str,
    shop_uuid: str,
    **kwargs: Any,
) -> StyleTokens:
    """Dispatch to the zone-specific token updater."""
    code = zone_code.upper()
    if code == "Z1":
        return _apply_z1(tokens, shop_uuid=shop_uuid, **kwargs)
    if code == "Z2":
        return _apply_z2(tokens, shop_uuid=shop_uuid, **kwargs)
    if code == "Z3":
        return _apply_z3(tokens, shop_uuid=shop_uuid, **kwargs)
    if code == "Z4":
        return _apply_z4(tokens, shop_uuid=shop_uuid, **kwargs)
    if code in ("Z4S", "Z4C"):
        return _apply_z4_subzone(tokens, code, shop_uuid=shop_uuid, **kwargs)
    if code == "Z6":
        return _apply_z6(tokens, shop_uuid=shop_uuid, **kwargs)
    return tokens


def _apply_z1(tokens: StyleTokens, *, shop_uuid: str = "", **kwargs: Any) -> StyleTokens:
    from .z1_tour_options import fields_for_backdrop_apply, z1_motion_for_option

    primary_color = kwargs.get("primary_color", "")
    accent_color = kwargs.get("accent_color", "")
    background_color = kwargs.get("background_color", "")
    surface_color = kwargs.get("surface_color", "")
    text_primary = kwargs.get("text_primary", "")
    text_secondary = kwargs.get("text_secondary", "")
    option_id = kwargs.get("option_id", "")
    motion_transition = kwargs.get("motion_transition", "")

    bg_only = bool(background_color) and not (primary_color or surface_color or accent_color)
    if bg_only and not surface_color:
        backdrop = fields_for_backdrop_apply(background_color)
        background_color = backdrop["background_color"]
        surface_color = backdrop["surface_color"]
        text_primary = backdrop["text_primary"]
        text_secondary = backdrop["text_secondary"]

    tokens = set_global_colors(
        tokens,
        primary=primary_color,
        accent=accent_color or (primary_color if primary_color else ""),
        background=background_color,
        surface=surface_color,
        text_primary=text_primary,
        text_secondary=text_secondary,
    )
    motion_val = motion_transition or z1_motion_for_option(option_id or "")
    if motion_val:
        tokens.motion = tokens.motion.model_copy(update={"transition": motion_val})  # type: ignore[arg-type]
    return tokens


def _apply_z2(tokens: StyleTokens, *, shop_uuid: str = "", **kwargs: Any) -> StyleTokens:
    primary_color = kwargs.get("primary_color", "")
    accent_color = kwargs.get("accent_color", "")
    background_color = kwargs.get("background_color", "")
    surface_color = kwargs.get("surface_color", "")
    hero_layout = kwargs.get("hero_layout", "")
    hero_overlay = kwargs.get("hero_overlay", "")
    logo_placement = kwargs.get("logo_placement", "")
    option_id = kwargs.get("option_id", "")

    if primary_color or accent_color or background_color or surface_color:
        tokens = set_zone_color_scope(
            tokens,
            "Z2",
            primary=primary_color,
            accent=accent_color,
            background=background_color,
            surface=surface_color,
        )

    hero = dict(tokens.hero.model_dump())
    if hero_layout:
        hero["layout"] = hero_layout
    if hero_overlay:
        hero["overlay"] = hero_overlay
    if logo_placement:
        hero["logoPlacement"] = logo_placement
    preset = _HERO_PRESETS.get(option_id or "")
    if preset:
        hero.update(preset)
    tokens.hero = tokens.hero.model_validate(hero)
    return tokens


def _apply_z3(tokens: StyleTokens, *, shop_uuid: str = "", **kwargs: Any) -> StyleTokens:
    from .color_engine import normalize_hex as normalize_hex
    from .zone_option_resolver import find_dynamic_color_option
    from .zone_dynamic_options import (
        typography_scale_for_option,
        typography_tokens_for_option,
    )

    option_id = kwargs.get("option_id", "")
    primary_color = kwargs.get("primary_color", "")
    accent_color = kwargs.get("accent_color", "")
    background_color = kwargs.get("background_color", "")
    surface_color = kwargs.get("surface_color", "")
    text_primary = kwargs.get("text_primary", "")
    text_secondary = kwargs.get("text_secondary", "")
    heading_font = kwargs.get("heading_font", "")
    body_font = kwargs.get("body_font", "")
    font_scale = kwargs.get("font_scale", "")

    text_hit = find_dynamic_color_option(shop_uuid, "Z3", option_id=option_id or "")
    if text_hit:
        role = text_hit.get("role", "")
        hex_val = text_hit.get("hex", "")
        if role == "text_heading" and hex_val:
            text_primary = text_primary or hex_val
        elif role == "text_body" and hex_val:
            text_secondary = text_secondary or hex_val

    if primary_color or accent_color or background_color or surface_color:
        tokens = set_zone_color_scope(
            tokens,
            "Z3",
            primary=primary_color,
            accent=accent_color,
            background=background_color,
            surface=surface_color,
        )

    colors = dict(tokens.colors.model_dump())
    if text_primary:
        colors["textPrimary"] = normalize_hex(text_primary)
    if text_secondary:
        colors["textSecondary"] = normalize_hex(text_secondary)
    if text_primary or text_secondary:
        tokens.colors = tokens.colors.model_validate(colors)

    typo = dict(tokens.typography.model_dump())
    font_preset = typography_tokens_for_option(option_id or "")
    if font_preset:
        typo.update({k: v for k, v in font_preset.items() if k != "scale"})
    elif option_id in _LEGACY_FONT_PRESETS:
        typo.update(_LEGACY_FONT_PRESETS[option_id])

    scale_preset = typography_scale_for_option(option_id or "")
    if scale_preset:
        typo["scale"] = scale_preset
    elif option_id in ("z3_scale_compact", "z3_scale_standard", "z3_scale_generous"):
        typo["scale"] = option_id.removeprefix("z3_scale_")
    if heading_font:
        typo["headingFont"] = heading_font
    if body_font:
        typo["bodyFont"] = body_font
    if font_scale:
        typo["scale"] = font_scale
    tokens.typography = tokens.typography.model_validate(typo)
    return tokens


def _apply_z4_subzone(
    tokens: StyleTokens,
    zone_code: str,
    *,
    shop_uuid: str = "",
    **kwargs: Any,
) -> StyleTokens:
    primary_color = kwargs.get("primary_color", "")
    accent_color = kwargs.get("accent_color", "")
    background_color = kwargs.get("background_color", "")
    surface_color = kwargs.get("surface_color", "")

    if primary_color or accent_color or background_color or surface_color:
        tokens = set_zone_color_scope(
            tokens,
            zone_code,
            primary=primary_color,
            accent=accent_color or primary_color,
            background=background_color,
            surface=surface_color,
        )
    return tokens


def _apply_z4(tokens: StyleTokens, *, shop_uuid: str = "", **kwargs: Any) -> StyleTokens:
    from .z4_tour_options import price_style_for_option_id

    accent_color = kwargs.get("accent_color", "")
    primary_color = kwargs.get("primary_color", "")
    card_shape = kwargs.get("card_shape", "")
    card_layout = kwargs.get("card_layout", "")
    card_shadow = kwargs.get("card_shadow", "")
    price_style = kwargs.get("price_style", "")
    option_id = kwargs.get("option_id", "")

    if (
        accent_color
        or option_id in ("accent_scoped",)
        or (option_id and option_id.startswith("accent_"))
    ):
        for sub_zone in ("Z4S", "Z4C"):
            tokens = set_zone_color_scope(
                tokens,
                sub_zone,
                accent=accent_color or primary_color,
            )

    cards = dict(tokens.productCards.model_dump())
    style_from_option = price_style_for_option_id(option_id or "")
    if style_from_option:
        cards["priceStyle"] = style_from_option
    elif price_style:
        cards["priceStyle"] = price_style
    if card_shape:
        cards["shape"] = card_shape
    if card_layout:
        cards["layout"] = card_layout
    if card_shadow:
        cards["shadow"] = card_shadow
    preset = _PRODUCT_CARD_PRESETS.get(option_id or "")
    if preset:
        cards.update(preset)
    tokens.productCards = tokens.productCards.model_validate(cards)
    return tokens


def _apply_z6(tokens: StyleTokens, *, shop_uuid: str = "", **kwargs: Any) -> StyleTokens:
    from .color_engine import normalize_hex as normalize_hex
    from .zone_dynamic_options import (
        z6_button_size_for_option,
        z6_button_tokens_for_option,
    )

    primary_color = kwargs.get("primary_color", "")
    accent_color = kwargs.get("accent_color", "")
    button_shape = kwargs.get("button_shape", "")
    button_style = kwargs.get("button_style", "")
    button_size = kwargs.get("button_size", "")
    option_id = kwargs.get("option_id", "")

    tokens = set_zone_color_scope(
        tokens,
        "Z6",
        primary=primary_color,
        accent=accent_color,
    )
    cta_hex = primary_color or accent_color
    if cta_hex:
        colors = dict(tokens.colors.model_dump())
        colors["secondary"] = normalize_hex(cta_hex)
        tokens.colors = tokens.colors.model_validate(colors)

    buttons = dict(tokens.buttons.model_dump())
    if button_shape:
        buttons["shape"] = button_shape
    if button_style:
        buttons["style"] = button_style
    if button_size:
        buttons["size"] = button_size
    preset = z6_button_tokens_for_option(option_id or "")
    if preset:
        buttons.update(preset)
    size_val = z6_button_size_for_option(option_id or "")
    if size_val:
        buttons["size"] = size_val
    elif option_id in ("z6_size_compact", "z6_size_standard", "z6_size_large"):
        buttons["size"] = option_id.removeprefix("z6_size_")
    tokens.buttons = tokens.buttons.model_validate(buttons)
    return tokens
