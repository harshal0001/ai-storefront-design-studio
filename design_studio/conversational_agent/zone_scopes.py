"""Per-zone style overrides — scoped to storefront sections (CF-05 / Z1–Z6).

``tokens.zoneScopes`` holds per-zone colour accents (Z2, Z3, Z4S, Z4C, Z6) without changing
global ``colors.*``. Z4 price accent uses scoped Z4S/Z4C entries. ``zone_scopes_for_preview()``
feeds the camelCase preview theme object in ``storefront.html``.
"""

from __future__ import annotations

from typing import Literal, get_args

from .style_tokens import StyleTokens, ZoneColorScope

ZoneCode = Literal["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]
VALID_ZONE_CODES: set[str] = set(get_args(ZoneCode))

# Z1 updates global colors only; Z5 is view-only (no colour overrides).
# Z4 splits into showcase (Our Products) vs catalogue (All Products & Services).
ZONE_COLOR_CODES: tuple[str, ...] = ("Z2", "Z3", "Z4", "Z4S", "Z4C", "Z6")


def clear_zone_scopes(tokens: StyleTokens) -> StyleTokens:
    """Full theme save/package applies uniformly — drop per-zone color overrides."""
    return tokens.model_copy(update={"zoneScopes": {}})


def set_global_colors(
    tokens: StyleTokens,
    *,
    primary: str = "",
    accent: str = "",
    background: str = "",
    surface: str = "",
    text_primary: str = "",
    text_secondary: str = "",
) -> StyleTokens:
    """Z1 / save_theme — page-wide brand colours."""
    updates = {}
    if primary:
        updates["primary"] = primary
    if accent:
        updates["accent"] = accent
    if background:
        updates["background"] = background
    if surface:
        updates["surface"] = surface
    if text_primary:
        updates["textPrimary"] = text_primary
    if text_secondary:
        updates["textSecondary"] = text_secondary
    if not updates:
        return tokens
    return tokens.model_copy(update={"colors": tokens.colors.model_copy(update=updates)})


def set_zone_color_scope(
    tokens: StyleTokens,
    zone_code: str,
    *,
    primary: str = "",
    accent: str = "",
    background: str = "",
    surface: str = "",
    card_face: str = "",
    text_primary: str = "",
    text_secondary: str = "",
) -> StyleTokens:
    """Zone tour / targeted edit — colours only inside that zone's DOM subtree."""
    code = zone_code.upper()
    if code == "Z1":
        return set_global_colors(
            tokens,
            primary=primary,
            accent=accent,
            background=background,
            surface=surface,
            text_primary=text_primary,
            text_secondary=text_secondary,
        )
    if code not in ZONE_COLOR_CODES:
        return tokens

    scopes = dict(tokens.zoneScopes)
    current = scopes.get(code, ZoneColorScope())
    updates = {}
    if primary:
        updates["primary"] = primary
    if accent:
        updates["accent"] = accent
    if background:
        updates["background"] = background
    if surface:
        updates["surface"] = surface
    if card_face:
        updates["cardFace"] = card_face
    if text_primary:
        updates["textPrimary"] = text_primary
    if text_secondary:
        updates["textSecondary"] = text_secondary
    if not updates:
        return tokens

    scopes[code] = current.model_copy(update=updates)
    if code in ("Z4S", "Z4C"):
        scopes.pop("Z4", None)
    return tokens.model_copy(update={"zoneScopes": scopes})


def _scope_to_preview(scope: ZoneColorScope, *, zone_code: str = "") -> dict[str, str]:
    dumped = scope.model_dump(exclude_none=True)
    if not dumped:
        return {}
    mapped = {
        "primaryColor": dumped.get("primary"),
        "accentColor": dumped.get("accent"),
        "backgroundColor": dumped.get("background"),
        "surfaceColor": dumped.get("surface"),
        "cardFace": dumped.get("cardFace"),
        "textPrimary": dumped.get("textPrimary"),
        "textSecondary": dumped.get("textSecondary"),
    }
    out = {k: v for k, v in mapped.items() if v}
    # Z6 CTA fill uses --color-cta → secondaryColor in storefront.html
    if zone_code == "Z6" and out.get("primaryColor") and "secondaryColor" not in out:
        out["secondaryColor"] = out["primaryColor"]
    return out


def normalize_product_zone_scopes(tokens: StyleTokens) -> StyleTokens:
    """Drop legacy unified Z4 scope once sub-zones exist; migrate Z4 → Z4S/Z4C when needed."""
    scopes = dict(tokens.zoneScopes)
    legacy = scopes.pop("Z4", None)
    if legacy:
        for sub in ("Z4S", "Z4C"):
            current = scopes.get(sub, ZoneColorScope())
            updates: dict[str, str] = {}
            if legacy.surface and not current.surface:
                updates["surface"] = legacy.surface
            if legacy.background and not current.background:
                updates["background"] = legacy.background
            if legacy.accent and not current.accent:
                updates["accent"] = legacy.accent
            if legacy.primary and not current.primary:
                updates["primary"] = legacy.primary
            if updates:
                scopes[sub] = current.model_copy(update=updates)
    if scopes != tokens.zoneScopes:
        return tokens.model_copy(update={"zoneScopes": scopes})
    return tokens


def zone_scopes_for_preview(tokens: StyleTokens) -> dict[str, dict]:
    """CamelCase zone scope colours for storefront.html."""
    tokens = normalize_product_zone_scopes(tokens)
    out: dict[str, dict] = {}
    for code, scope in tokens.zoneScopes.items():
        if code == "Z4":
            continue
        preview = _scope_to_preview(scope, zone_code=code)
        if preview:
            out[code] = preview

    return out
