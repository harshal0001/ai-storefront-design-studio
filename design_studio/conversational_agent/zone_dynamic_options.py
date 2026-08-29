"""Mood- and theme-aware zone tour options (CF-05 / CF-03).

Generates 3–4 colour or layout choices per tour sub-step from the merchant's saved
mood tags and current draft tokens — not fixed swatch lists. Options are cached on
``ZONE_TOUR.optionCache`` so ``find_color_option()`` can resolve clicks without Bedrock.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Literal

from coloraide import Color

from .color_engine import (
    adjust_for_contrast,
    check_contrast_ratio,
    friendly_color_name,
    generate_palette_from_seed,
    get_lighter,
    is_accessible,
    normalize_hex,
)
from .config_manager import ConfigManager
from .style_repository import StyleRepository
from .style_tokens import StyleTokens
from .zone_presets import ZONE_TOUR_PRESETS
from .zone_tour_types import ZoneSubStep

ColorRole = Literal["primary", "accent", "background", "surface"]

# Mood tag → default seed when theme is still generic
_MOOD_SEEDS: dict[str, str] = {
    "warm": "#C45B28",
    "cozy": "#8B4513",
    "rustic": "#A86B3F",
    "artisan": "#B87333",
    "elegant": "#5C4A72",
    "modern": "#1E5F8C",
    "minimal": "#4A5568",
    "sleek": "#2D3748",
    "bold": "#BE185D",
    "playful": "#E85D4C",
    "fresh": "#0D9488",
    "premium": "#1E293B",
    "classic": "#4A3728",
}

_MOOD_HARMONY: dict[str, str] = {
    "warm": "analogous",
    "cozy": "analogous",
    "rustic": "analogous",
    "artisan": "analogous",
    "elegant": "mono",
    "modern": "mono",
    "minimal": "mono",
    "sleek": "mono",
    "bold": "complement",
    "playful": "triad",
    "fresh": "split",
    "premium": "mono",
    "classic": "analogous",
}

_MOOD_ADJECTIVES: dict[str, tuple[str, ...]] = {
    "warm": ("Sunset", "Honey", "Copper", "Amber"),
    "cozy": ("Cocoa", "Toffee", "Chestnut", "Latte"),
    "rustic": ("Terracotta", "Clay", "Earth", "Harvest"),
    "modern": ("Slate", "Steel", "Ocean", "Graphite"),
    "minimal": ("Mist", "Pearl", "Cloud", "Stone"),
    "bold": ("Berry", "Coral", "Ruby", "Flame"),
    "playful": ("Coral", "Mango", "Splash", "Punch"),
    "fresh": ("Mint", "Seafoam", "Jade", "Spruce"),
    "elegant": ("Plum", "Mauve", "Velvet", "Dusk"),
    "premium": ("Ink", "Charcoal", "Midnight", "Onyx"),
}

# Layout preset → mood tags for ranking (CF-02-style matching)
_LAYOUT_MOOD_MATCH: dict[str, tuple[str, ...]] = {
    "classic_center": ("warm", "rustic", "cozy", "classic", "elegant"),
    "modern_left": ("modern", "minimal", "sleek"),
    "split_hero": ("modern", "elegant", "minimal"),
    "carousel_hero": ("bold", "playful", "modern"),
    "editorial_tagline": ("elegant", "premium", "classic"),
    "logo_forward": ("bold", "modern", "sleek"),
    "bold_dark": ("bold", "premium", "elegant"),
    "minimal_clean": ("minimal", "modern", "sleek"),
    "elegant_serif": ("elegant", "classic", "warm", "premium"),
    "modern_sans": ("modern", "minimal", "sleek"),
    "friendly_rounded": ("warm", "cozy", "playful", "artisan"),
    "compact_pro": ("modern", "minimal", "sleek"),
    "z3_scale_compact": ("minimal", "modern", "sleek"),
    "z3_scale_standard": ("warm", "classic", "elegant"),
    "z3_scale_generous": ("warm", "cozy", "playful", "artisan"),
    "soft_grid": ("warm", "cozy", "artisan"),
    "bold_grid": ("bold", "playful", "modern"),
    "grid_three": ("modern", "minimal", "sleek"),
    "list_view": ("minimal", "modern", "sleek"),
    "featured_mix": ("elegant", "premium", "stylish"),
    "sharp_minimal": ("minimal", "modern", "sleek"),
    "floating_cards": ("elegant", "premium", "stylish"),
    "airy_list": ("modern", "minimal", "sleek"),
    "minimal_sharp": ("modern", "minimal", "sleek"),
    "pill_cta": ("playful", "bold", "modern"),
    "soft_ghost": ("minimal", "elegant", "modern"),
    "pill_ghost": ("elegant", "minimal", "modern"),
    "large_filled": ("bold", "playful", "modern"),
    "outlined_rounded": ("elegant", "classic", "warm"),
    "compact_pill": ("modern", "minimal", "sleek"),
    "soft_outlined": ("elegant", "minimal", "warm"),
    "bold_ripple": ("bold", "premium", "playful"),
    "z6_dyn_sharp_soft": ("minimal", "modern", "sleek"),
    "z6_dyn_subtle_outlined": ("elegant", "warm", "classic"),
    "z6_dyn_pill_ripple": ("bold", "playful", "modern"),
    "z6_dyn_large_ghost": ("minimal", "elegant"),
    "z6_dyn_compact_outlined": ("modern", "minimal"),
    "z6_dyn_pill_soft": ("playful", "warm", "cozy"),
    "z6_size_compact": ("minimal", "modern", "sleek"),
    "z6_size_standard": ("warm", "classic", "elegant"),
    "z6_size_large": ("bold", "playful", "modern"),
}

# Token payloads for Z6 layout picks (static + dynamic variant ids).
Z6_BUTTON_TOKEN_MAP: dict[str, dict[str, str]] = {
    "friendly_rounded": {"shape": "rounded", "style": "filled", "pressAnimation": "scale"},
    "minimal_sharp": {"shape": "sharp", "style": "outlined", "pressAnimation": "darken"},
    "pill_cta": {"shape": "pill", "style": "filled", "pressAnimation": "scale"},
    "soft_ghost": {"shape": "rounded", "style": "ghost", "pressAnimation": "none"},
    "pill_ghost": {"shape": "pill", "style": "ghost", "pressAnimation": "scale"},
    "large_filled": {
        "shape": "rounded",
        "style": "filled",
        "size": "large",
        "pressAnimation": "scale",
    },
    "outlined_rounded": {"shape": "rounded", "style": "outlined", "pressAnimation": "darken"},
    "compact_pill": {
        "shape": "pill",
        "style": "filled",
        "size": "compact",
        "pressAnimation": "scale",
    },
    "soft_outlined": {"shape": "subtleRounded", "style": "outlined", "pressAnimation": "none"},
    "bold_ripple": {"shape": "rounded", "style": "filled", "pressAnimation": "ripple"},
    "z6_dyn_sharp_soft": {"shape": "sharp", "style": "soft", "pressAnimation": "darken"},
    "z6_dyn_subtle_outlined": {
        "shape": "subtleRounded",
        "style": "outlined",
        "pressAnimation": "darken",
    },
    "z6_dyn_pill_ripple": {"shape": "pill", "style": "filled", "pressAnimation": "ripple"},
    "z6_dyn_large_ghost": {
        "shape": "rounded",
        "style": "ghost",
        "size": "large",
        "pressAnimation": "none",
    },
    "z6_dyn_compact_outlined": {
        "shape": "pill",
        "style": "outlined",
        "size": "compact",
        "pressAnimation": "scale",
    },
    "z6_dyn_pill_soft": {"shape": "pill", "style": "soft", "pressAnimation": "scale"},
}

_Z6_SHAPES = ("sharp", "subtleRounded", "rounded", "pill")
_Z6_STYLES = ("filled", "outlined", "soft", "ghost")
_Z6_ANIMATIONS = ("none", "darken", "scale", "ripple")
_Z6_COMBO_CATALOG: list[dict[str, Any]] | None = None
_Z3_FONT_CATALOG: list[dict[str, Any]] | None = None

# Extra Google Font pairings (heading, body, scale, display name, mood tags).
_Z3_EXTRA_FONT_SPECS: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    ("Merriweather", "Open Sans", "standard", "Merriweather & Open Sans", ("warm", "classic")),
    ("Oswald", "Roboto", "standard", "Oswald & Roboto", ("bold", "modern")),
    (
        "Cormorant Garamond",
        "Mulish",
        "generous",
        "Cormorant & Mulish",
        ("elegant", "premium"),
    ),
    ("Poppins", "Nunito Sans", "standard", "Poppins & Nunito Sans", ("playful", "modern")),
    (
        "Libre Baskerville",
        "Source Sans 3",
        "standard",
        "Libre Baskerville & Source Sans",
        ("classic", "elegant"),
    ),
    ("Raleway", "Lato", "compact", "Raleway & Lato", ("minimal", "modern", "sleek")),
    ("PT Serif", "PT Sans", "standard", "PT Serif & PT Sans", ("classic", "minimal")),
    ("Ubuntu", "Roboto", "standard", "Ubuntu & Roboto", ("modern", "fresh")),
    ("Bitter", "Work Sans", "standard", "Bitter & Work Sans", ("warm", "artisan")),
    ("DM Serif Display", "DM Sans", "standard", "DM Serif & DM Sans", ("elegant", "modern")),
]

# Static Z3 presets + generated ids → typography token payloads for apply_zone_tour_choice.
Z6_SIZE_PRESETS: list[dict[str, str]] = [
    {
        "id": "z6_size_compact",
        "name": "Compact",
        "description": "**64rpx-class** tap targets — dense, still touch-friendly on product areas.",
    },
    {
        "id": "z6_size_standard",
        "name": "Standard",
        "description": "**80rpx-class** tap targets — balanced default for Follow & coupon CTAs.",
    },
    {
        "id": "z6_size_large",
        "name": "Large",
        "description": "**96rpx-class** tap targets — bold buttons that stand out on cards & catalogue.",
    },
]

Z6_SIZE_TOKEN_MAP: dict[str, str] = {
    "z6_size_compact": "compact",
    "z6_size_standard": "standard",
    "z6_size_large": "large",
}

Z3_SCALE_PRESETS: list[dict[str, str]] = [
    {
        "id": "z3_scale_compact",
        "name": "Compact",
        "description": "Smaller text scale (14/12px feel) across intro and store info.",
    },
    {
        "id": "z3_scale_standard",
        "name": "Standard",
        "description": "Balanced text scale (16/14px feel) — default readability.",
    },
    {
        "id": "z3_scale_generous",
        "name": "Generous",
        "description": "Larger text scale (22/16px feel) — headings stand out more.",
    },
]

Z3_FONT_TOKEN_MAP: dict[str, dict[str, str]] = {
    "elegant_serif": {"headingFont": "Playfair Display", "bodyFont": "Lato"},
    "modern_sans": {"headingFont": "Montserrat", "bodyFont": "Roboto"},
    "friendly_rounded": {"headingFont": "Nunito", "bodyFont": "Open Sans"},
    "compact_pro": {"headingFont": "Inter", "bodyFont": "Inter"},
}

_Z6_DYNAMIC_PRESETS: list[dict[str, str]] = [
    {
        "id": "z6_dyn_sharp_soft",
        "name": "Sharp soft fill",
        "description": "**Square soft-filled** buttons — crisp edges with a gentle fill.",
    },
    {
        "id": "z6_dyn_subtle_outlined",
        "name": "Subtle outlined",
        "description": "**Slightly rounded outlined** CTAs — refined, low visual noise.",
    },
    {
        "id": "z6_dyn_pill_ripple",
        "name": "Pill ripple",
        "description": "**Pill buttons** with ripple press — lively mobile CTAs.",
    },
    {
        "id": "z6_dyn_large_ghost",
        "name": "Large ghost",
        "description": "**Bigger ghost** buttons — airy, editorial tap targets.",
    },
    {
        "id": "z6_dyn_compact_outlined",
        "name": "Compact outlined pills",
        "description": "**Small outlined pills** — tight layouts, still tappable.",
    },
    {
        "id": "z6_dyn_pill_soft",
        "name": "Pill soft fill",
        "description": "**Soft-filled pills** — friendly coupons and Follow buttons.",
    },
]

_Z6_SHAPE_LABELS = {
    "sharp": "Square",
    "subtleRounded": "Soft-corner",
    "rounded": "Rounded",
    "pill": "Pill",
}
_Z6_STYLE_LABELS = {
    "filled": "filled",
    "outlined": "outlined",
    "soft": "soft-filled",
    "ghost": "ghost",
}
_Z6_ANIM_SKIP = {("ghost", "ripple")}


def _z6_token_signature(tokens: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        tokens.get("shape", "rounded"),
        tokens.get("style", "filled"),
        tokens.get("size", "standard"),
        tokens.get("pressAnimation", "scale"),
    )


def _z6_combo_mood_tags(shape: str, style: str, anim: str) -> tuple[str, ...]:
    tags: set[str] = set()
    if shape == "pill":
        tags.update(("playful", "bold", "modern"))
    if shape == "sharp":
        tags.update(("minimal", "modern", "sleek"))
    if shape in ("subtleRounded", "rounded"):
        tags.update(("warm", "elegant", "classic"))
    if style == "ghost":
        tags.update(("minimal", "elegant"))
    if style == "soft":
        tags.update(("cozy", "warm", "artisan"))
    if style == "outlined":
        tags.update(("elegant", "classic"))
    if style == "filled" and anim in ("scale", "ripple"):
        tags.update(("bold", "playful"))
    if anim == "ripple":
        tags.update(("premium", "bold"))
    if not tags:
        tags.add("modern")
    return tuple(tags)


def _z6_pick_size(shape: str, style: str, anim: str) -> str:
    if style == "ghost" and shape in ("rounded", "pill"):
        return "large"
    if shape == "pill" and style == "outlined":
        return "compact"
    if style == "filled" and shape in ("rounded", "pill") and anim == "scale":
        return "large"
    return "standard"


def _z6_combo_description(shape: str, style: str, anim: str) -> str:
    shape_l = _Z6_SHAPE_LABELS.get(shape, shape)
    style_l = _Z6_STYLE_LABELS.get(style, style)
    anim_bit = ""
    if anim == "ripple":
        anim_bit = " with ripple press"
    elif anim == "darken":
        anim_bit = " with darken press"
    elif anim == "scale":
        anim_bit = " with scale press"
    elif anim == "none":
        anim_bit = " with no press animation"
    return f"**{shape_l} {style_l}** buttons{anim_bit} — " "Follow, coupon & catalogue CTAs."


def _z6_combo_display_name(shape: str, style: str, size: str, anim: str) -> str:
    parts = [_Z6_SHAPE_LABELS.get(shape, shape), _Z6_STYLE_LABELS.get(style, style)]
    if size == "large":
        parts.insert(0, "Large")
    elif size == "compact":
        parts.insert(0, "Compact")
    if anim == "ripple":
        parts.append("(ripple)")
    return " ".join(parts)


def _ensure_z6_combo_catalog() -> list[dict[str, Any]]:
    """Lazily build shape × style × animation combos; register token map + mood tags."""
    global _Z6_COMBO_CATALOG
    if _Z6_COMBO_CATALOG is not None:
        return _Z6_COMBO_CATALOG

    seen = {_z6_token_signature(t) for t in Z6_BUTTON_TOKEN_MAP.values()}
    catalog: list[dict[str, Any]] = []

    for shape in _Z6_SHAPES:
        for style in _Z6_STYLES:
            for anim in _Z6_ANIMATIONS:
                if (style, anim) in _Z6_ANIM_SKIP:
                    continue
                size = _z6_pick_size(shape, style, anim)
                tokens = {
                    "shape": shape,
                    "style": style,
                    "size": size,
                    "pressAnimation": anim,
                }
                sig = _z6_token_signature(tokens)
                if sig in seen:
                    continue
                seen.add(sig)

                pid = f"z6_gen_{shape}_{style}_{anim}"
                name = _z6_combo_display_name(shape, style, size, anim)
                desc = _z6_combo_description(shape, style, anim)
                Z6_BUTTON_TOKEN_MAP[pid] = tokens
                _LAYOUT_MOOD_MATCH[pid] = _z6_combo_mood_tags(shape, style, anim)
                catalog.append({"id": pid, "name": name, "description": desc})

    _Z6_COMBO_CATALOG = catalog
    return catalog


def _font_spec_slug(heading: str, body: str, scale: str) -> str:
    parts = [
        re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")[:12],
        re.sub(r"[^a-z0-9]+", "_", body.lower()).strip("_")[:12],
        scale.lower(),
    ]
    return "_".join(p for p in parts if p)


def _ensure_z3_font_catalog() -> list[dict[str, Any]]:
    global _Z3_FONT_CATALOG
    if _Z3_FONT_CATALOG is not None:
        return _Z3_FONT_CATALOG

    catalog: list[dict[str, Any]] = []
    for heading, body, scale, name, moods in _Z3_EXTRA_FONT_SPECS:
        pid = f"z3_gen_{_font_spec_slug(heading, body, scale)}"
        tokens = {"headingFont": heading, "bodyFont": body}
        Z3_FONT_TOKEN_MAP[pid] = tokens
        _LAYOUT_MOOD_MATCH[pid] = moods
        catalog.append(
            {
                "id": pid,
                "name": name,
                "description": (
                    f"**{heading}** headings with **{body}** body text — "
                    "intro & store information."
                ),
                "font_tokens": tokens,
            }
        )
    _Z3_FONT_CATALOG = catalog
    return catalog


def typography_tokens_for_option(option_id: str) -> dict[str, str] | None:
    _ensure_z3_font_catalog()
    return Z3_FONT_TOKEN_MAP.get((option_id or "").strip())


def z6_button_size_for_option(option_id: str) -> str | None:
    oid = (option_id or "").strip()
    if oid in Z6_SIZE_TOKEN_MAP:
        return Z6_SIZE_TOKEN_MAP[oid]
    return None


def typography_scale_for_option(option_id: str) -> str | None:
    oid = (option_id or "").strip()
    if oid in ("z3_scale_compact", "z3_scale_standard", "z3_scale_generous"):
        return oid.removeprefix("z3_scale_")
    return None


def _format_contrast_ratio(foreground: str, background: str) -> str:
    ratio = check_contrast_ratio(foreground, background)
    return f"{ratio:.1f}:1"


def _z3_text_background(tokens: StyleTokens) -> str:
    z3 = tokens.zoneScopes.get("Z3")
    if z3 and z3.surface:
        return normalize_hex(z3.surface)
    surf = tokens.colors.surface or tokens.colors.background
    return normalize_hex(surf)


def _wcag_safe_text(hex_fg: str, bg: str) -> str:
    """Ensure foreground meets WCAG AA on the panel background (never offer failing combos)."""
    safe = normalize_hex(adjust_for_contrast(hex_fg, bg, 4.5))
    if is_accessible(safe, bg, "AA"):
        return safe
    return normalize_hex(adjust_for_contrast("#000000", bg, 4.5))


def _z3_text_archetype_hex(
    archetype: str,
    text_role: Literal["heading", "body"],
    *,
    primary: str,
    batch: int = 0,
    warmer: bool = False,
) -> tuple[str, str]:
    """Return (display_name, hex) for one Z3-03 archetype."""
    if archetype == "black":
        name = "Black" if text_role == "heading" else "Charcoal"
        raw = "#0A0A0A" if text_role == "heading" else "#1F2937"
    elif archetype == "dark_grey":
        name = "Dark grey" if text_role == "heading" else "Soft grey"
        raw = "#374151" if text_role == "heading" else "#4B5563"
    elif archetype == "brand_tinted":
        name = "Brand-tinted"
        c = Color(primary or "#1E293B").convert("oklch")
        c["lightness"] = max(0.1, min(0.38, c["lightness"] - 0.32 - batch * 0.03))
        if warmer:
            c["hue"] = (c["hue"] + 22) % 360
        if text_role == "body":
            c["lightness"] = min(0.45, c["lightness"] + 0.08)
        raw = c.convert("srgb").clip().to_string(hex=True)
    else:  # warm_dark
        name = "Warm dark"
        raw = "#3D2914" if text_role == "heading" else "#5C4033"

    if batch and archetype in ("black", "dark_grey", "warm_dark"):
        c = Color(raw).convert("oklch")
        c["lightness"] = max(0.05, c["lightness"] - batch * 0.04)
        if warmer and archetype == "warm_dark":
            c["hue"] = (c["hue"] + 15) % 360
        raw = c.convert("srgb").clip().to_string(hex=True)

    return name, normalize_hex(raw)


def generate_z3_text_colour_options(
    merchant_id: str,
    *,
    text_role: Literal["heading", "body"],
    user_request: str = "",
    batch: int = 0,
    exclude_ids: set[str] | None = None,
    limit: int = 4,
) -> list[dict[str, str]]:
    """Four WCAG AA text swatches per role (Z3-03)."""
    cm = ConfigManager(shop_uuid=merchant_id)
    cm.reload()
    bg = _z3_text_background(cm.tokens)
    primary = cm.tokens.colors.primary
    lower = user_request.lower()
    warmer = any(w in lower for w in ("warmer", "warm", "honey", "cozy", "rust"))
    if any(w in lower for w in ("darker", "deeper", "bold", "ink")):
        batch = max(batch, 1)

    archetypes = ("black", "dark_grey", "brand_tinted", "warm_dark")
    exclude = {i.lower() for i in (exclude_ids or set()) if i}
    options: list[dict[str, str]] = []
    role_key: Literal["text_heading", "text_body"] = (
        "text_heading" if text_role == "heading" else "text_body"
    )
    section = "Heading text" if text_role == "heading" else "Body text"

    for i, arch in enumerate(archetypes):
        name, raw_hex = _z3_text_archetype_hex(
            arch,
            text_role,
            primary=primary,
            batch=batch,
            warmer=warmer,
        )
        safe_hex = _wcag_safe_text(raw_hex, bg)
        oid = f"z3_txt_{text_role}_{arch}_{batch}"
        if oid.lower() in exclude:
            continue
        ratio = _format_contrast_ratio(safe_hex, bg)
        desc = (
            f"**{name}** on your panel background — contrast **{ratio}** (WCAG AA). "
            f"Applies to {text_role} text in intro & store information."
        )
        options.append(
            {
                "id": oid,
                "name": name,
                "hex": safe_hex,
                "description": desc,
                "role": role_key,
                "section": section,
                "contrast_ratio": ratio,
                "contrast_background": bg,
                "text_role": text_role,
                "applies_to": desc,
                "what_changes": desc,
                "generated": "true",
            }
        )
        if len(options) >= limit:
            break
    return options


def z6_button_tokens_for_option(option_id: str) -> dict[str, str] | None:
    _ensure_z6_combo_catalog()
    return Z6_BUTTON_TOKEN_MAP.get((option_id or "").strip())


def summarize_cached_tour_options(mgr: Any) -> str:
    """Comma-separated names of options currently shown as chat buttons."""
    opts = (
        list(mgr.get_cached_color_options())
        + list(mgr.get_cached_zone_options())
        + list(mgr.get_cached_theme_packages())
    )
    names = [o.get("name") or o.get("id", "") for o in opts if o.get("name") or o.get("id")]
    return ", ".join(names[:8])


_REQUEST_MOOD_HINTS: dict[str, tuple[str, ...]] = {
    "stylish": ("elegant", "premium", "bold"),
    "luxury": ("premium", "elegant"),
    "luxurious": ("premium", "elegant"),
    "modern": ("modern", "sleek", "minimal"),
    "minimal": ("minimal", "sleek"),
    "bold": ("bold", "playful"),
    "playful": ("playful", "bold"),
    "elegant": ("elegant", "premium"),
    "cozy": ("cozy", "warm"),
    "fresh": ("fresh", "modern"),
    "bigger": ("bold", "playful"),
    "larger": ("bold", "playful"),
    "smaller": ("minimal", "sleek"),
    "compact": ("minimal", "sleek"),
}

_SUB_STEP_CHANGE_EXPLANATIONS: dict[str, str] = {
    "z1_palette": (
        "Applies a full **brand palette** — primary, accent, page backdrop & intro panels "
        "across your storefront in one step."
    ),
    "z1_accent": (
        "Sets the **accent** for buttons, links & price tags — each swatch explains "
        "how it pairs with your brand colour."
    ),
    "z1_backdrop": (
        "Changes the **page backdrop** behind offers and product sections — "
        "Pure White, Warm White, Light Grey, or Soft Cream."
    ),
    "z1_motion": (
        "Chooses **page transitions** when customers move between sections — "
        "fade, slide-tint, or none."
    ),
    "z2_layout": (
        "Reshapes the **hero banner**: photo layout, logo position, tagline placement, "
        "and how bold your store name appears."
    ),
    "z2_hero_bg": (
        "Colours only the **strip behind your banner photo** — "
        "your product sections below stay unchanged for now."
    ),
    "z3_fonts": (
        "Chooses **heading & body fonts** for intro text and store information — "
        "readability and personality for your words."
    ),
    "z3_scale": (
        "Sets **font size scale** (compact, standard, generous) for intro and store information."
    ),
    "z3_text_colour": (
        "Picks **heading and body text colours** with WCAG AA contrast against your background."
    ),
    "z4_showcase": (
        "Background for **Our Products** carousel only — "
        "does not change All Products & Services until the next step."
    ),
    "z4_catalog": (
        "Background for **All Products & Services** only — "
        "Our Products keeps the colour you picked in the previous step."
    ),
    "z4_layout": (
        "Card **shape, grid layout & shadow** in both product sections — "
        "how product tiles look when customers browse."
    ),
    "z4_prices": (
        "**How prices look** on product cards in both sections — "
        "bold red, accent, understated grey, or badge pill (sample catalogue prices shown)."
    ),
    "z6_style": (
        "**Shape & style** of Follow, coupon, and catalogue buttons — "
        "filled, outlined, ghost, rounded or sharp."
    ),
    "z6_size": (
        "**Button height & padding** on Follow, coupons & catalogue CTAs — "
        "compact, standard, or large (touch-friendly minimum enforced)."
    ),
    "z6_cta_colour": (
        "**Button fill colour** for Follow, coupons & catalogue CTAs — "
        "the tap targets that drive action."
    ),
}


def _normalize_moods(mood_tags: list[str]) -> set[str]:
    return {t.strip().lower() for t in mood_tags if t and t.strip()}


def _dominant_mood(mood_tags: list[str]) -> str:
    moods = _normalize_moods(mood_tags)
    for key in _MOOD_SEEDS:
        if key in moods:
            return key
    return "warm"


def _seed_from_theme_and_mood(tokens: StyleTokens, mood_tags: list[str]) -> str:
    primary = (tokens.colors.primary or "").strip()
    if primary and primary.lower() not in ("#000000", "#ffffff", ""):
        return normalize_hex(primary)
    mood = _dominant_mood(mood_tags)
    return _MOOD_SEEDS.get(mood, "#C45B28")


def _harmony_for_moods(mood_tags: list[str]) -> str:
    moods = _normalize_moods(mood_tags)
    for mood, harmony in _MOOD_HARMONY.items():
        if mood in moods:
            return harmony
    return "analogous"


def _creative_name(hex_val: str, mood_tags: list[str], index: int) -> str:
    mood = _dominant_mood(mood_tags)
    pool = _MOOD_ADJECTIVES.get(mood, _MOOD_ADJECTIVES["warm"])
    base = pool[index % len(pool)]
    c = Color(hex_val).convert("oklch")
    if c["lightness"] > 0.85:
        return f"Soft {base}"
    if c["lightness"] < 0.35:
        return f"Deep {base}"
    return base


def _stable_option_id(sub_id: str, hex_val: str, index: int) -> str:
    digest = hashlib.sha256(f"{sub_id}:{hex_val}:{index}".encode()).hexdigest()[:8]
    return f"dyn_{sub_id}_{digest}"


def _role_hex_candidates(
    seed: str,
    harmony: str,
    role: ColorRole,
    count: int = 4,
    *,
    batch: int = 0,
) -> list[str]:
    palette = generate_palette_from_seed(seed, harmony=harmony, count=8 + batch * 2)  # type: ignore[arg-type]
    shift = (batch * max(1, count // 2)) % max(1, len(palette) - 1)
    palette = palette[shift:] + palette[:shift]
    out: list[str] = []

    if role in ("primary", "accent"):
        for h in palette[:count]:
            c = Color(h).convert("oklch")
            if 0.35 <= c["lightness"] <= 0.75:
                out.append(normalize_hex(h))
        while len(out) < count:
            for h in palette:
                if normalize_hex(h) not in out:
                    out.append(normalize_hex(h))
                if len(out) >= count:
                    break
            break

    elif role == "background":
        for h in palette:
            light = normalize_hex(get_lighter(h, 0.22))
            if light not in out:
                out.append(light)
            if len(out) >= count:
                break
        while len(out) < count:
            out.append(normalize_hex(get_lighter(seed, 0.25 + 0.05 * len(out))))

    else:  # surface
        for h in palette:
            light = normalize_hex(get_lighter(h, 0.32))
            if light not in out:
                out.append(light)
            if len(out) >= count:
                break
        while len(out) < count:
            out.append(normalize_hex(get_lighter(seed, 0.38 + 0.04 * len(out))))

    return out[:count]


def _what_changes_line(
    *,
    role: ColorRole,
    scope_zone: str,
    section: str,
    sub_id: str,
) -> str:
    if sub_id in _SUB_STEP_CHANGE_EXPLANATIONS:
        return _SUB_STEP_CHANGE_EXPLANATIONS[sub_id]
    if section:
        return f"Updates **{section}** in your live preview."
    if scope_zone == "Z4S":
        return "Updates the **Our Products** section background only."
    if scope_zone == "Z4C":
        return "Updates **All Products & Services** background only."
    if role == "primary":
        return "Updates main brand & Follow button colour."
    if role == "accent":
        return "Updates accent highlights and price tags."
    if role == "background":
        return "Updates section backdrop colour."
    return "Updates your live storefront preview."


def load_mood_tags(merchant_id: str) -> list[str]:
    repo = StyleRepository(shop_uuid=merchant_id)
    if not repo.enabled:
        return []
    profile = repo.get_style_profile(merchant_id) or {}
    return [t for t in profile.get("moodTags", []) if t]


def _format_mood_phrase(mood_tags: list[str]) -> str:
    labels: list[str] = []
    for tag in mood_tags[:4]:
        t = tag.strip()
        if not t:
            continue
        labels.append(t if "&" in t else t.title())
    return ", ".join(labels)


def build_theme_context(merchant_id: str) -> dict[str, Any]:
    """Summary of the applied theme + mood tags for tour UI copy."""
    cm = ConfigManager(shop_uuid=merchant_id)
    cm.reload()
    moods = load_mood_tags(merchant_id)
    c = cm.tokens.colors
    theme_name = (c.paletteName or cm.config.theme_name or "Your theme").strip()

    palette_line = f"Building on **{theme_name}**"
    palette_colors = [
        {
            "role": "brand",
            "label": "Brand",
            "name": friendly_color_name(c.primary),
            "hex": c.primary,
        },
        {
            "role": "page",
            "label": "Page",
            "name": friendly_color_name(c.background),
            "hex": c.background,
        },
    ]
    accent_name = friendly_color_name(c.accent)
    if c.accent and c.accent.lower() != c.primary.lower():
        palette_colors.insert(
            1,
            {
                "role": "accent",
                "label": "Accent",
                "name": accent_name,
                "hex": c.accent,
            },
        )

    mood_line = ""
    if moods:
        mood_line = f"Options below are tuned to your **{_format_mood_phrase(moods)}** vibe."

    return {
        "theme_name": theme_name,
        "palette_line": palette_line,
        "palette_colors": palette_colors,
        "palette_summary": palette_line,
        "mood_tags": moods,
        "mood_line": mood_line,
        "primary_hex": c.primary,
        "accent_hex": c.accent,
        "background_hex": c.background,
    }


def sub_step_explanation(sub_id: str) -> str:
    return _SUB_STEP_CHANGE_EXPLANATIONS.get(sub_id, "")


def exhausted_options_lead(sub_id: str) -> str:
    """Merchant-facing copy when every preset for this sub-step has been shown."""
    leads = {
        "z2_layout": (
            "You've seen all hero layout presets for this step — describe the look you want "
            "(e.g. carousel, logo left, dark scrim) and I'll apply it."
        ),
        "z2_hero_bg": (
            "You've seen the hero band colours for this step — name a colour or hex "
            "(e.g. navy, cream) and I'll apply it to the banner strip."
        ),
        "z3_fonts": (
            "You've seen all font pairings — describe the style you want "
            "(e.g. modern sans, elegant serif) and I'll apply it."
        ),
        "z3_scale": (
            "You've seen all text scales — say *bigger headings*, *more compact*, or "
            "*generous* and I'll apply it."
        ),
        "z3_text_colour": (
            "You've seen all text colour swatches — say *darker*, *warmer*, or a hex "
            "and I'll suggest accessible options."
        ),
        "z6_style": (
            "You've seen all button styles for this step — describe the look you want "
            "(e.g. pill ghost, large filled) and I'll apply it."
        ),
        "z6_size": (
            "You've seen all button sizes — say *bigger*, *smaller*, or *standard* "
            "and I'll apply a touch-friendly size."
        ),
        "z6_cta_colour": (
            "You've seen all CTA colour swatches — name a colour or hex for your buttons."
        ),
        "z1_palette": (
            "You've seen all palette cards — describe a vibe (e.g. *fresh & green*), "
            "upload a logo, or type your brand colours in chat."
        ),
        "z1_accent": (
            "You've seen all accent pairings — name a colour or say *warmer accent* "
            "and I'll suggest options that work with your brand."
        ),
        "z1_backdrop": (
            "You've seen all backdrop presets — say *warmer*, *cooler*, cream, or a hex."
        ),
        "z1_motion": (
            "You've seen all transition styles — say *fade*, *slide*, or *no animation*."
        ),
        "z4_prices": (
            "You've seen all price display styles — say *make prices stand out more*, "
            "*understated*, *badge pill*, or *bold red* and I'll apply it."
        ),
    }
    return leads.get(
        sub_id,
        "You've seen all built-in options for this step — describe what you want "
        "and I'll apply it to the preview.",
    )


def _moods_from_request(user_request: str, base_moods: list[str]) -> list[str]:
    moods = set(_normalize_moods(base_moods))
    lower = user_request.lower()
    for word, tags in _REQUEST_MOOD_HINTS.items():
        if word in lower:
            moods.update(tags)
    return list(moods)


def _layout_description(preset: dict[str, str], sub_id: str) -> str:
    base = (preset.get("description") or "").strip()
    if base:
        return base
    return _SUB_STEP_CHANGE_EXPLANATIONS.get(sub_id, "")


def _rank_presets(
    presets: list[dict[str, str]],
    mood_tags: list[str],
    limit: int = 4,
    *,
    exclude_ids: set[str] | None = None,
    batch: int = 0,
) -> list[dict[str, str]]:
    moods = _normalize_moods(mood_tags)
    exclude = {i.lower() for i in (exclude_ids or set()) if i}

    def score(p: dict[str, str]) -> int:
        pid = p.get("id", "")
        tags = _LAYOUT_MOOD_MATCH.get(pid, ())
        return len(moods & {t.lower() for t in tags})

    ranked = sorted(presets, key=lambda p: (-score(p), p.get("name", "")))
    pool = [p for p in ranked if p.get("id", "").lower() not in exclude]
    if not pool:
        return []
    start = (batch * limit) % len(pool)
    out: list[dict[str, str]] = []
    for i in range(min(limit, len(pool))):
        out.append(pool[(start + i) % len(pool)])
    return out


def generate_color_options_for_sub_step(
    merchant_id: str,
    zone_code: str,
    sub: ZoneSubStep,
    *,
    count: int = 4,
    user_request: str = "",
    batch: int = 0,
    exclude_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    """Build mood-matched colour swatches for one tour sub-step."""
    cm = ConfigManager(shop_uuid=merchant_id)
    cm.reload()
    mood_tags = _moods_from_request(user_request, load_mood_tags(merchant_id))

    seed = _seed_from_theme_and_mood(cm.tokens, mood_tags)
    harmony = _harmony_for_moods(mood_tags)

    template = _sub_step_color_template(zone_code, sub)
    role: ColorRole = template.get("role", "accent") if template else "accent"  # type: ignore[assignment]
    scope_zone = template.get("scope_zone", "") if template else ""
    section = template.get("section", "") if template else ""

    if not template and sub.option_ids:
        from .zone_color_presets import find_color_option

        hit = find_color_option(zone_code, option_id=sub.option_ids[0])
        if hit:
            role = hit.get("role", "accent")  # type: ignore[assignment]
            scope_zone = hit.get("scope_zone", "")
            section = hit.get("section", "")

    exclude = {i.lower() for i in (exclude_ids or set()) if i}
    hexes = _role_hex_candidates(seed, harmony, role, count=count * 2, batch=batch)
    options: list[dict[str, str]] = []
    for i, hex_val in enumerate(hexes):
        oid = _stable_option_id(sub.id, hex_val, i + batch * count)
        if oid.lower() in exclude:
            continue
        name = _creative_name(hex_val, mood_tags, i + batch * count)
        desc = _what_changes_line(
            role=role,
            scope_zone=scope_zone,
            section=section,
            sub_id=sub.id,
        )
        options.append(
            {
                "id": oid,
                "name": name,
                "hex": hex_val,
                "description": desc,
                "role": role,
                "scope_zone": scope_zone,
                "section": section,
                "applies_to": desc,
                "what_changes": desc,
                "generated": "true",
            }
        )
        if len(options) >= count:
            break
    return options


def _sub_step_color_template(zone_code: str, sub: ZoneSubStep) -> dict[str, str] | None:
    """Infer role/scope from first static template id on the sub-step."""
    from .zone_color_presets import find_color_option

    for oid in sub.option_ids:
        hit = find_color_option(zone_code, option_id=oid)
        if hit:
            return hit
    return None


def _layout_preset_pool(zone_code: str, sub: ZoneSubStep) -> list[dict[str, str]]:
    """Full catalog for ranking — Z6 adds mood-ranked shape × style × animation combos."""
    zone = zone_code.upper()
    presets = list(ZONE_TOUR_PRESETS.get(zone, []))
    by_id = {p["id"]: p for p in presets}
    if zone == "Z6" and sub.id == "z6_style":
        for dyn in _Z6_DYNAMIC_PRESETS:
            by_id.setdefault(dyn["id"], dyn)
        for combo in _ensure_z6_combo_catalog():
            by_id.setdefault(combo["id"], combo)
        return list(by_id.values())
    if zone == "Z3" and sub.id == "z3_fonts":
        for combo in _ensure_z3_font_catalog():
            by_id.setdefault(combo["id"], combo)
        return list(by_id.values())
    if zone == "Z3" and sub.id == "z3_scale":
        for preset in Z3_SCALE_PRESETS:
            by_id.setdefault(preset["id"], preset)
        return list(Z3_SCALE_PRESETS)
    if zone == "Z6" and sub.id == "z6_size":
        return list(Z6_SIZE_PRESETS)
    if zone == "Z4" and sub.id == "z4_prices":
        from .z4_tour_options import Z4_PRICE_STYLE_PRESETS

        return list(Z4_PRICE_STYLE_PRESETS)
    ordered = [by_id[i] for i in sub.option_ids if i in by_id]
    return ordered if ordered else presets


def generate_z6_button_style_options(
    merchant_id: str,
    *,
    user_request: str = "",
    batch: int = 0,
    exclude_ids: set[str] | None = None,
    limit: int = 4,
) -> list[dict[str, str]]:
    """Mood-ranked button presets from static catalog + generated shape/style/animation combos."""
    sub = ZoneSubStep(
        id="z6_style",
        prompt="",
        kind="layouts",
        option_ids=(),
        highlight="Z6",
    )
    return generate_layout_options_for_sub_step(
        merchant_id,
        "Z6",
        sub,
        user_request=user_request,
        batch=batch,
        exclude_ids=exclude_ids,
        limit=limit,
    )


def generate_layout_options_for_sub_step(
    merchant_id: str,
    zone_code: str,
    sub: ZoneSubStep,
    *,
    user_request: str = "",
    batch: int = 0,
    exclude_ids: set[str] | None = None,
    limit: int = 4,
) -> list[dict[str, str]]:
    """Rank layout/style presets by merchant mood tags."""
    mood_tags = _moods_from_request(user_request, load_mood_tags(merchant_id))
    ordered = _layout_preset_pool(zone_code, sub)

    ranked = _rank_presets(
        ordered,
        mood_tags,
        limit=limit,
        exclude_ids=exclude_ids,
        batch=batch,
    )
    out: list[dict[str, str]] = []
    for p in ranked:
        desc = _layout_description(p, sub.id)
        out.append(
            {
                **p,
                "description": desc,
                "applies_to": desc,
                "what_changes": desc,
                "generated": "true",
            }
        )
    return out


def generate_options_for_sub_step(
    merchant_id: str,
    zone_code: str,
    sub: ZoneSubStep,
    *,
    user_request: str = "",
    batch: int = 0,
    exclude_ids: set[str] | None = None,
    limit: int = 4,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (color_options, zone_options, theme_packages) for the current sub-step."""
    if sub.id == "z1_palette":
        from .z1_tour_options import generate_z1_palette_options

        return (
            [],
            [],
            generate_z1_palette_options(
                merchant_id,
                user_request=user_request,
                batch=batch,
                exclude_ids=exclude_ids,
                limit=min(limit, 5),
            ),
        )
    if sub.id == "z1_accent":
        from .z1_tour_options import generate_z1_accent_options

        return (
            generate_z1_accent_options(
                merchant_id,
                user_request=user_request,
                batch=batch,
                exclude_ids=exclude_ids,
                limit=limit,
            ),
            [],
            [],
        )
    if sub.id == "z1_backdrop":
        from .z1_tour_options import generate_z1_backdrop_options

        return (
            generate_z1_backdrop_options(
                merchant_id,
                user_request=user_request,
                batch=batch,
                exclude_ids=exclude_ids,
            ),
            [],
            [],
        )
    if sub.id == "z1_motion":
        from .z1_tour_options import generate_z1_motion_options

        return (
            [],
            generate_z1_motion_options(batch=batch, exclude_ids=exclude_ids),
            [],
        )
    if sub.id == "z4_prices":
        from .z4_tour_options import generate_z4_price_style_options

        return (
            [],
            generate_z4_price_style_options(
                merchant_id,
                user_request=user_request,
                batch=batch,
                exclude_ids=exclude_ids,
                limit=limit,
            ),
            [],
        )
    if sub.id == "z3_text_colour":
        from .zone_tour import ZoneTourManager

        phase = ZoneTourManager(merchant_id).get_z3_text_colour_phase()
        text_role: Literal["heading", "body"] = "body" if phase == "body" else "heading"
        return (
            generate_z3_text_colour_options(
                merchant_id,
                text_role=text_role,
                user_request=user_request,
                batch=batch,
                exclude_ids=exclude_ids,
                limit=limit,
            ),
            [],
            [],
        )
    if sub.kind == "layouts":
        return (
            [],
            generate_layout_options_for_sub_step(
                merchant_id,
                zone_code,
                sub,
                user_request=user_request,
                batch=batch,
                exclude_ids=exclude_ids,
                limit=limit,
            ),
            [],
        )
    if sub.kind == "palettes":
        from .z1_tour_options import generate_z1_palette_options

        return (
            [],
            [],
            generate_z1_palette_options(
                merchant_id,
                user_request=user_request,
                batch=batch,
                exclude_ids=exclude_ids,
                limit=min(limit, 5),
            ),
        )
    return (
        generate_color_options_for_sub_step(
            merchant_id,
            zone_code,
            sub,
            count=limit,
            user_request=user_request,
            batch=batch,
            exclude_ids=exclude_ids,
        ),
        [],
        [],
    )


def _dedupe_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for o in options:
        oid = (o.get("id") or "").lower()
        if not oid or oid in seen:
            continue
        seen.add(oid)
        out.append(o)
    return out


def _option_ids(options: list[dict[str, Any]]) -> set[str]:
    return {(o.get("id") or "").lower() for o in options if o.get("id")}


def refresh_options_for_current_sub_step(
    merchant_id: str,
    user_request: str = "",
    *,
    option_limit: int | None = None,
    append: bool = False,
    must_differ_from: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str]:
    """New option batch for the active tour sub-step (excludes prior shown ids)."""
    from .zone_tour import ZoneTourManager
    from .zone_tour_flow import current_sub_step

    mgr = ZoneTourManager(merchant_id)
    step = mgr.current_step()
    if not step:
        return [], [], [], ""
    sub = current_sub_step(step.code, mgr.get_sub_step_index())
    if not sub:
        return [], [], [], ""

    exclude = mgr.get_dismissed_option_ids()
    batch = mgr.bump_option_batch()
    limit = 4 if option_limit is None else max(1, min(option_limit, 4))

    prior_ids = must_differ_from or set()

    def _generate(ex_ids: set[str], batch_no: int) -> tuple[list, list, list]:
        return generate_options_for_sub_step(
            merchant_id,
            step.code,
            sub,
            user_request=user_request,
            batch=batch_no,
            exclude_ids=ex_ids,
            limit=limit,
        )

    colors, layouts, packages = _generate(exclude, batch)
    opts = packages or layouts or colors
    new_ids = _option_ids(opts)
    if opts and prior_ids and new_ids.issubset(prior_ids):
        mgr.clear_dismissed_for_sub_step(sub.id)
        colors, layouts, packages = _generate(set(), batch + 1)
        opts = packages or layouts or colors
    elif opts and exclude and new_ids.issubset(exclude):
        mgr.clear_dismissed_for_sub_step(sub.id)
        colors, layouts, packages = _generate(set(), batch + 1)
        opts = packages or layouts or colors

    vibe = _format_mood_phrase(_moods_from_request(user_request, load_mood_tags(merchant_id)))

    if not opts:
        mgr.clear_dismissed_for_sub_step(sub.id)
        colors, layouts, packages = generate_options_for_sub_step(
            merchant_id,
            step.code,
            sub,
            user_request=user_request,
            batch=batch + 1,
            exclude_ids=set(),
            limit=limit,
        )
        opts = packages or layouts or colors
        if opts:
            lead = "Here are more options to try"
        else:
            lead = exhausted_options_lead(sub.id)
            mgr.cache_sub_step_options(
                sub.id, colors, layouts, theme_packages=packages, append=append
            )
            return colors, layouts, packages, lead

    mgr.cache_sub_step_options(sub.id, colors, layouts, theme_packages=packages, append=append)
    names = [o.get("name", "") for o in opts if o.get("name")]

    if append and limit == 1 and names:
        lead = f"Added one more option: **{names[0]}**"
    elif limit == 1 and names:
        lead = f"Here's one more option: **{names[0]}**"
    elif limit < 4 and names:
        lead = f"Here are **{len(names)}** more options" + (
            f" with a **{vibe}** feel" if vibe else ""
        )
    elif vibe and user_request.strip():
        lead = f"Here are more options with a **{vibe}** feel"
    elif names:
        lead = "Here are more options to try"
    else:
        lead = "Here are fresh options"
    return colors, layouts, packages, lead


# Swatch resolution lives in zone_option_resolver (re-exported for existing imports).
