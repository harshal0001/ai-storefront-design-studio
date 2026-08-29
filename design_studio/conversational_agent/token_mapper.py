"""Map between StyleTokens, StorefrontConfig, and storefront.html theme object.

- ``tokens_to_preview_theme()`` — camelCase ``storeInfo.theme`` for the iframe
- ``build_tokens_from_theme_save()`` — agent ``save_theme`` parameters → tokens + WCAG flags
- ``derive_text_colors()`` — contrast-safe text on a background hex
- Legacy ``StorefrontConfig`` ↔ tokens for ``customize_zone`` tool path
"""

from .color_engine import (
    check_contrast_ratio,
    get_contrast_color,
    get_darker,
    get_lighter,
    is_accessible,
    normalize_hex,
)
from .constants import BLACK, SECONDARY_TEXT_DARKEN, SECONDARY_TEXT_LIGHTEN, WHITE
from .models import BorderRadius, Spacing, StorefrontConfig, Zone, ZoneStyle
from .style_tokens import StyleTokens
from .zone_scopes import clear_zone_scopes, set_zone_color_scope, zone_scopes_for_preview


def default_tokens() -> StyleTokens:
    return StyleTokens()


def derive_text_colors(background_hex: str) -> tuple[str, str]:
    """WCAG-friendly primary/secondary text pair for a background colour."""
    text_primary = get_contrast_color(background_hex)
    if text_primary == WHITE:
        text_secondary = get_darker(WHITE, SECONDARY_TEXT_DARKEN)
    else:
        text_secondary = get_lighter(BLACK, SECONDARY_TEXT_LIGHTEN)
    return text_primary, text_secondary


def tokens_to_preview_theme(tokens: StyleTokens, *, name: str = "", description: str = "") -> dict:
    """CamelCase theme object for `storeInfo.theme` in storefront.html."""
    c = tokens.colors
    t = tokens.typography
    g = tokens.geometry
    return {
        "name": name or c.paletteName or "Default Theme",
        "description": description,
        "primaryColor": c.primary,
        "secondaryColor": c.secondary,
        "accentColor": c.accent,
        "backgroundColor": c.background,
        "surfaceColor": c.surface,
        "textPrimary": c.textPrimary,
        "textSecondary": c.textSecondary,
        "headingFont": t.headingFont,
        "bodyFont": t.bodyFont,
        "typeScale": t.scale,
        "headingStyle": t.headingStyle,
        "bodyStyle": t.bodyStyle,
        "dangerColor": c.danger,
        "warnColor": c.warn,
        "successColor": c.success,
        "borderRadius": g.borderRadiusPreset,
        "spacing": g.spacingPreset,
        "hero": tokens.hero.model_dump(),
        "productCards": tokens.productCards.model_dump(),
        "buttons": tokens.buttons.model_dump(),
        "motion": tokens.motion.model_dump(),
        "offerCards": tokens.offerCards.model_dump(),
        "zoneScopes": zone_scopes_for_preview(tokens),
    }


def tokens_to_storefront_config(
    tokens: StyleTokens,
    *,
    theme_name: str = "",
    theme_description: str = "",
    mood_summary: str = "",
) -> StorefrontConfig:
    c = tokens.colors
    g = tokens.geometry
    return StorefrontConfig(
        theme_name=theme_name or c.paletteName,
        theme_description=theme_description,
        mood_summary=mood_summary,
        primary_color=c.primary,
        primary_color_name=c.paletteName,
        secondary_color=c.secondary,
        secondary_color_name="",
        accent_color=c.accent,
        accent_color_name="",
        background_color=c.background,
        background_color_name="",
        surface_color=c.surface,
        surface_color_name="",
        text_primary=c.textPrimary,
        text_secondary=c.textSecondary,
        heading_font=tokens.typography.headingFont,
        body_font=tokens.typography.bodyFont,
        default_border_radius=BorderRadius(g.borderRadiusPreset),
        default_spacing=Spacing(g.spacingPreset),
        zone_overrides={},
    )


def recompute_quality_flags(tokens: StyleTokens) -> StyleTokens:
    """Recompute ``colors.harmonyChecked`` / ``colors.contrastAA`` from the palette.

    Called on every save (``ConfigManager.save_tokens`` / ``apply_zone``) so the
    WCAG flags track the current colours regardless of which edit path produced
    them — direct style, page colours, zone tour, scoped colour, etc. (2.9).
    Mirrors the checks in ``build_tokens_from_theme_save``.
    """
    c = tokens.colors
    contrast_ok = is_accessible(c.textPrimary, c.background, "AA") and is_accessible(
        c.textPrimary, c.surface, "AA"
    )
    harmony_ok = check_contrast_ratio(c.primary, c.background) >= 3.0
    if c.contrastAA == contrast_ok and c.harmonyChecked == harmony_ok:
        return tokens
    return tokens.model_copy(
        update={
            "colors": c.model_copy(update={"harmonyChecked": harmony_ok, "contrastAA": contrast_ok})
        }
    )


def build_tokens_from_theme_save(
    *,
    theme_name: str,
    primary_color: str,
    secondary_color: str,
    accent_color: str,
    background_color: str,
    surface_color: str,
    text_primary: str,
    text_secondary: str,
    heading_font: str,
    body_font: str,
    border_radius: str,
    spacing: str,
    based_on_package: StyleTokens | None = None,
) -> StyleTokens:
    """Build tokens from save_theme parameters; optional package as base."""
    base = based_on_package.model_copy(deep=True) if based_on_package else default_tokens()

    primary = normalize_hex(primary_color)
    background = normalize_hex(background_color)
    surface = normalize_hex(surface_color)
    contrast_ok = is_accessible(text_primary, background, "AA") and is_accessible(
        text_primary, surface, "AA"
    )
    harmony_ok = check_contrast_ratio(primary, background) >= 3.0

    base.colors = base.colors.model_copy(
        update={
            "primary": primary,
            "secondary": normalize_hex(secondary_color),
            "accent": normalize_hex(accent_color),
            "background": background,
            "surface": normalize_hex(surface_color),
            "textPrimary": normalize_hex(text_primary),
            "textSecondary": normalize_hex(text_secondary),
            "paletteName": theme_name,
            "harmonyChecked": harmony_ok,
            "contrastAA": contrast_ok,
        }
    )
    base.typography = base.typography.model_copy(
        update={
            "headingFont": heading_font,
            "bodyFont": body_font,
            "pairingName": base.typography.pairingName or f"{heading_font} / {body_font}",
        }
    )
    base.geometry = base.geometry.model_copy(
        update={
            "borderRadiusPreset": border_radius,  # type: ignore[arg-type]
            "spacingPreset": spacing,  # type: ignore[arg-type]
        }
    )
    return clear_zone_scopes(base)


def storefront_config_to_tokens(config: StorefrontConfig) -> StyleTokens:
    tokens = default_tokens()
    if config.primary_color:
        tokens.colors = tokens.colors.model_copy(
            update={
                "primary": config.primary_color,
                "secondary": config.secondary_color or tokens.colors.secondary,
                "accent": config.accent_color or tokens.colors.accent,
                "background": config.background_color or tokens.colors.background,
                "surface": config.surface_color or tokens.colors.surface,
                "textPrimary": config.text_primary or tokens.colors.textPrimary,
                "textSecondary": config.text_secondary or tokens.colors.textSecondary,
                "paletteName": config.theme_name or config.primary_color_name,
            }
        )
    if config.heading_font:
        tokens.typography = tokens.typography.model_copy(
            update={
                "headingFont": config.heading_font,
                "bodyFont": config.body_font or tokens.typography.bodyFont,
            }
        )
    tokens.geometry = tokens.geometry.model_copy(
        update={
            "borderRadiusPreset": config.default_border_radius.value,
            "spacingPreset": config.default_spacing.value,
        }
    )
    for zone, style in config.zone_overrides.items():
        tokens = apply_zone_override(tokens, zone, style)
    return tokens


_LEGACY_ZONE_SCOPE_CODES = {
    Zone.HERO_BANNER: "Z2",
    Zone.STORE_LOGO: "Z2",
    Zone.STORE_HEADER: "Z2",
    Zone.STORE_DESCRIPTION: "Z3",
    Zone.CONTACT_ICONS: "Z6",
    Zone.ADDRESS_BAR: "Z3",
    Zone.BUSINESS_HOURS: "Z3",
    Zone.FOLLOW_BUTTON: "Z6",
    Zone.AD_BANNER: "Z2",
    Zone.PRODUCTS_GRID: "Z4",
    Zone.MARKET_SECTION: "Z4",
}


def apply_zone_override(tokens: StyleTokens, zone: Zone, style: ZoneStyle) -> StyleTokens:
    updated = tokens.model_copy(deep=True)
    zone_code = _LEGACY_ZONE_SCOPE_CODES.get(zone)
    if zone_code and (style.primary_color or style.background_color):
        updated = set_zone_color_scope(
            updated,
            zone_code,
            primary=style.primary_color or "",
            accent=style.primary_color or "",
            background=style.background_color or "",
        )
    if style.border_radius:
        updated.geometry = updated.geometry.model_copy(
            update={"borderRadiusPreset": style.border_radius.value}  # type: ignore[arg-type]
        )
    return updated
