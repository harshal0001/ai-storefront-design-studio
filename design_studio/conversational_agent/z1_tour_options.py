"""Z1 Brand Colours tour — palette cards, accent pairing, named backdrops, motion (Z1-01…Z1-07).

Z1-03 (text brand palette) and Z1-04 (photo upload) stay in chat/upload flows — not tour steps.
This module generates tour options and applies full palette packages for step ``z1_palette``.
"""

from __future__ import annotations

import re
from typing import Any

from .color_engine import (
    check_contrast_ratio,
    friendly_color_name,
    generate_palette_from_seed,
    get_lighter,
    normalize_hex,
)
from .config_manager import ConfigManager
from .harmony_feedback import HarmonyAssessment
from .style_repository import StyleRepository
from .style_tokens import StyleTokens
from .token_mapper import build_tokens_from_theme_save, clear_zone_scopes, derive_text_colors
from .theme_choice_actions import _map_colors
from .zone_dynamic_options import (
    _format_mood_phrase,
    _harmony_for_moods,
    _moods_from_request,
    _seed_from_theme_and_mood,
    load_mood_tags,
)

_Z1_ACCENT_ID_RE = re.compile(
    r"^z1_acc_(complement|analogous|split|triad)_(\d+)_(\d+)$",
    re.I,
)

# Z1-05 — fixed page backdrop names (spec: Pure White, Warm White, Light Grey, Soft Cream).
Z1_BACKDROP_PRESETS: list[dict[str, str]] = [
    {
        "id": "z1_bg_pure_white",
        "name": "Pure White",
        "hex": "#FFFFFF",
        "description": "Crisp white page backdrop — maximum brightness behind products & offers.",
        "role": "background",
        "section": "Page backdrop",
    },
    {
        "id": "z1_bg_warm_white",
        "name": "Warm White",
        "hex": "#F8F4EF",
        "description": "Soft warm white — easy on the eyes, pairs with earthy brands.",
        "role": "background",
        "section": "Page backdrop",
    },
    {
        "id": "z1_bg_light_grey",
        "name": "Light Grey",
        "hex": "#EEF2F6",
        "description": "Cool light grey — modern, neutral frame for your catalogue.",
        "role": "background",
        "section": "Page backdrop",
    },
    {
        "id": "z1_bg_soft_cream",
        "name": "Soft Cream",
        "hex": "#F5F0E6",
        "description": "Gentle cream — cozy, artisan-friendly page tone.",
        "role": "background",
        "section": "Page backdrop",
    },
]

# Z1-07 — navigation transition presets.
Z1_MOTION_PRESETS: list[dict[str, str]] = [
    {
        "id": "z1_motion_fade",
        "name": "Fade (0.3s)",
        "description": "Subtle **fade** when moving between sections — calm and polished.",
    },
    {
        "id": "z1_motion_slide",
        "name": "Slide-tint (0.4s)",
        "description": "Gentle **slide-tint** transition — a touch of movement without distraction.",
    },
    {
        "id": "z1_motion_none",
        "name": "None",
        "description": "No transition animation — instant section changes.",
    },
]

Z1_MOTION_TOKEN_MAP: dict[str, str] = {
    "z1_motion_fade": "fadeTint",
    "z1_motion_slide": "slideTint",
    "z1_motion_none": "none",
}

# Personality titles for Z1-01 palette cards (mood × batch index).
_PALETTE_NAME_POOL: dict[str, tuple[str, ...]] = {
    "warm": ("Sunset Warmth", "Honey Grove", "Copper Hearth", "Amber Lane", "Harvest Glow"),
    "cozy": ("Cocoa Comfort", "Latte Lounge", "Toffee Nook", "Chestnut Calm", "Ember Hearth"),
    "modern": ("Ocean Trust", "Slate Horizon", "Azure Edge", "Steel Current", "Nordic Bay"),
    "elegant": ("Velvet Dusk", "Plum Serenity", "Mauve Manor", "Twilight Grace", "Silk Evening"),
    "bold": ("Berry Pulse", "Coral Rush", "Ruby Spark", "Flame Accent", "Magenta Mood"),
    "fresh": ("Seafoam Fresh", "Mint Meadow", "Jade Stream", "Spruce Calm", "Coastal Air"),
    "premium": ("Midnight Ink", "Onyx Reserve", "Charcoal Luxe", "Obsidian Line", "Noir Studio"),
    "classic": ("Heritage Hearth", "Timber Classic", "Oak & Stone", "Vintage Earth", "Craft Manor"),
}

_PAIRING_TEMPLATES: dict[str, str] = {
    "complement": "Complementary to **{brand}** — strong contrast on links, prices & highlights.",
    "analogous": "Analogous to **{brand}** — harmonious highlights on buttons and price tags.",
    "triad": "Triad accent for **{brand}** — lively but balanced on CTAs and links.",
    "split": "Split-complement accent for **{brand}** — subtle pop on highlights.",
}


def z1_palette_already_configured(tokens: StyleTokens) -> bool:
    """True when discovery/theme apply already set a named palette (skip step 1)."""
    name = (tokens.colors.paletteName or "").strip().lower()
    if not name or name in ("custom theme", "default theme", "your theme"):
        return False
    primary = (tokens.colors.primary or "").strip().lower()
    return primary not in ("", "#b63f81", "#000000")


def _palette_display_name(mood_tags: list[str], index: int, batch: int) -> str:
    mood = "warm"
    for key in _PALETTE_NAME_POOL:
        if key in {t.lower() for t in mood_tags}:
            mood = key
            break
    pool = _PALETTE_NAME_POOL.get(mood, _PALETTE_NAME_POOL["warm"])
    return pool[(index + batch * 2) % len(pool)]


def _build_palette_colors(
    seed: str,
    harmony: str,
    *,
    batch: int,
) -> list[dict[str, str]]:
    """Four swatches per card: brand, accent, page, panels (Z1-01 primary + accent + neutral)."""
    hexes = generate_palette_from_seed(seed, harmony, count=5)  # type: ignore[arg-type]
    shift = (batch * 2) % max(1, len(hexes) - 1)
    hexes = hexes[shift:] + hexes[:shift]
    primary = normalize_hex(hexes[0])
    accent = normalize_hex(hexes[2] if len(hexes) > 2 else hexes[1])
    background = normalize_hex(get_lighter(hexes[1] if len(hexes) > 1 else hexes[0], 0.28))
    surface = normalize_hex(get_lighter(background, 0.12))
    return [
        {"name": "Brand", "hex": primary},
        {"name": "Accent", "hex": accent},
        {"name": "Page", "hex": background},
        {"name": "Panels", "hex": surface},
    ]


def generate_z1_palette_options(
    merchant_id: str,
    *,
    user_request: str = "",
    batch: int = 0,
    exclude_ids: set[str] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Z1-01: 4–5 mood-ranked **palette cards** (theme-package shape for the UI)."""
    cm = ConfigManager(shop_uuid=merchant_id)
    cm.reload()
    mood_tags = _moods_from_request(user_request, load_mood_tags(merchant_id))
    exclude = {i.lower() for i in (exclude_ids or set()) if i}

    # Five distinct seeds from mood + batch so refresh yields new personalities.
    base_seed = _seed_from_theme_and_mood(cm.tokens, mood_tags)
    harmonies: list[str] = []
    for mood in mood_tags[:3]:
        harmonies.append(_harmony_for_moods([mood]))
    if not harmonies:
        harmonies = ["analogous", "complement", "triad", "split", "mono"]
    else:
        harmonies = list(dict.fromkeys(harmonies))
        while len(harmonies) < 5:
            harmonies.append(_harmony_for_moods(mood_tags))

    packages: list[dict[str, Any]] = []
    typo = cm.tokens.typography
    for i in range(limit):
        harmony = harmonies[(i + batch) % len(harmonies)]
        seed_palette = generate_palette_from_seed(base_seed, harmony, count=4)  # type: ignore[arg-type]
        seed = seed_palette[(i + batch) % len(seed_palette)]
        name = _palette_display_name(mood_tags, i, batch)
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        oid = f"z1_palette_{slug}_{batch}_{i}"
        if oid.lower() in exclude:
            continue
        colors = _build_palette_colors(seed, harmony, batch=batch + i)
        desc = (
            f"**{name}** — brand, accent & neutrals applied across your storefront. "
            f"Mood: {_format_mood_phrase(mood_tags) or 'your style'}."
        )
        packages.append(
            {
                "id": oid,
                "name": name,
                "description": desc,
                "colors": colors,
                "heading_font": typo.headingFont,
                "body_font": typo.bodyFont,
                "border_radius": cm.tokens.geometry.borderRadiusPreset,
                "spacing": cm.tokens.geometry.spacingPreset,
                "harmony": harmony,
                "generated": "true",
                "what_changes": desc,
                "applies_to": desc,
            }
        )
        if len(packages) >= limit:
            break

    # Tour palette cards live in optionCache.themePackages only — not _pending_theme_packages
    # (discovery themes) or clicks re-apply the wrong package during the walkthrough.
    return packages


def generate_z1_accent_options(
    merchant_id: str,
    *,
    user_request: str = "",
    batch: int = 0,
    exclude_ids: set[str] | None = None,
    limit: int = 4,
) -> list[dict[str, str]]:
    """Z1-02: accent swatches derived from the current primary with pairing rationale."""
    cm = ConfigManager(shop_uuid=merchant_id)
    cm.reload()
    primary = cm.tokens.colors.primary
    brand_name = friendly_color_name(primary)
    exclude = {i.lower() for i in (exclude_ids or set()) if i}

    harmony_modes: list[tuple[str, str]] = [
        ("complement", "complement"),
        ("analogous", "analogous"),
        ("split", "split"),
        ("triad", "triad"),
    ]
    options: list[dict[str, str]] = []
    for i, (harmony, key) in enumerate(harmony_modes):
        palette = generate_palette_from_seed(primary, harmony, count=6)  # type: ignore[arg-type]
        pick = palette[(i + 1 + batch) % len(palette)]
        accent_hex = normalize_hex(pick)
        oid = f"z1_acc_{key}_{batch}_{i}"
        if oid.lower() in exclude:
            continue
        pairing = _PAIRING_TEMPLATES[key].format(brand=brand_name)
        ratio = check_contrast_ratio(accent_hex, cm.tokens.colors.background)
        desc = (
            f"{pairing} Contrast vs page: **{ratio:.1f}:1**. "
            "Shows on buttons, links & price tags."
        )
        options.append(
            {
                "id": oid,
                "name": friendly_color_name(accent_hex),
                "hex": accent_hex,
                "description": desc,
                "role": "accent",
                "section": "Accent highlights",
                "pairing_note": pairing,
                "what_changes": desc,
                "applies_to": desc,
                "generated": "true",
            }
        )
        if len(options) >= limit:
            break
    return options


def find_z1_accent_option(merchant_id: str, option_id: str) -> dict[str, str] | None:
    """Resolve ``z1_acc_complement_0_0`` even when optionCache is empty or stale."""
    oid = (option_id or "").strip()
    match = _Z1_ACCENT_ID_RE.match(oid)
    if not match:
        return None
    batch = int(match.group(2))
    opts = generate_z1_accent_options(merchant_id, batch=batch, limit=8)
    key = oid.lower()
    for row in opts:
        if (row.get("id") or "").lower() == key:
            return row
    return None


def fields_for_backdrop_apply(hex_val: str) -> dict[str, str]:
    """Page backdrop apply also refreshes panels + readable text (preview must visibly update)."""
    background = normalize_hex(hex_val)
    surface = normalize_hex(get_lighter(background, 0.08))
    if background.upper() == "#FFFFFF":
        surface = "#FFFFFF"
    text_primary, text_secondary = derive_text_colors(background)
    return {
        "background_color": background,
        "surface_color": surface,
        "text_primary": text_primary,
        "text_secondary": text_secondary,
    }


def generate_z1_backdrop_options(
    merchant_id: str,
    *,
    user_request: str = "",
    batch: int = 0,
    exclude_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    """Z1-05: four named page backgrounds; warmer/cooler refresh rotates order only."""
    lower = user_request.lower()
    presets = list(Z1_BACKDROP_PRESETS)
    if any(w in lower for w in ("warmer", "cream", "honey", "cozy")):
        presets = [presets[3], presets[1], presets[0], presets[2]]
    elif any(w in lower for w in ("cooler", "grey", "gray", "slate")):
        presets = [presets[2], presets[0], presets[1], presets[3]]
    start = (batch * 2) % len(presets)
    rotated = presets[start:] + presets[:start]
    exclude = {i.lower() for i in (exclude_ids or set()) if i}
    out: list[dict[str, str]] = []
    for p in rotated:
        if p["id"].lower() in exclude:
            continue
        row = dict(p)
        row["what_changes"] = row["description"]
        row["applies_to"] = row["description"]
        row["generated"] = "true"
        out.append(row)
    return out[:4]


def generate_z1_motion_options(
    *,
    batch: int = 0,
    exclude_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    """Z1-07: fade / slide-tint / none."""
    exclude = {i.lower() for i in (exclude_ids or set()) if i}
    start = batch % len(Z1_MOTION_PRESETS)
    ordered = Z1_MOTION_PRESETS[start:] + Z1_MOTION_PRESETS[:start]
    out: list[dict[str, str]] = []
    for p in ordered:
        if p["id"].lower() in exclude:
            continue
        row = dict(p)
        row["what_changes"] = row["description"]
        row["applies_to"] = row["description"]
        row["generated"] = "true"
        out.append(row)
    return out


def tokens_from_z1_palette_package(package: dict[str, Any]) -> StyleTokens:
    """Build in-memory tokens for one palette card (no save)."""
    colors = package.get("colors") or []
    mapped = _map_colors(colors)
    background = mapped["background_color"]
    text_primary, text_secondary = derive_text_colors(background)
    tokens = build_tokens_from_theme_save(
        theme_name=package.get("name", "Brand palette"),
        text_primary=text_primary,
        text_secondary=text_secondary,
        heading_font=package.get("heading_font") or "Montserrat",
        body_font=package.get("body_font") or "Roboto",
        border_radius=package.get("border_radius") or "rounded",
        spacing=package.get("spacing") or "normal",
        **{k: v for k, v in mapped.items() if not k.endswith("_name")},
    )
    tokens = clear_zone_scopes(tokens)
    tokens.colors.paletteName = package.get("name", "")
    return tokens


def apply_z1_palette_package(
    merchant_id: str,
    package: dict[str, Any],
) -> tuple[str, HarmonyAssessment]:
    """Apply one Z1-01 palette card after Z1-06 harmony check. Returns (theme name, assessment)."""
    from .harmony_feedback import assess_brand_colours

    tokens = tokens_from_z1_palette_package(package)
    assessment = assess_brand_colours(tokens)
    name = package.get("name", "Brand palette")
    if assessment.blocked:
        return name, assessment

    cm = ConfigManager(shop_uuid=merchant_id)
    cm.save_tokens(
        tokens,
        theme_name=name,
        mood_summary=package.get("description", ""),
    )
    repo = StyleRepository(shop_uuid=merchant_id)
    if repo.enabled:
        moods = load_mood_tags(merchant_id)
        if moods:
            repo.update_mood_tags(moods, shop_uuid=merchant_id)
    return name, assessment


def find_z1_palette_package(
    merchant_id: str,
    *,
    option_id: str = "",
    name: str = "",
) -> dict[str, Any] | None:
    """Resolve a Z1 tour palette card from ``optionCache.themePackages`` only."""
    from .zone_tour import ZoneTourManager

    mgr = ZoneTourManager(merchant_id)
    cached = mgr.get_cached_theme_packages()
    if option_id:
        key = option_id.lower()
        for pkg in cached:
            if pkg.get("id", "").lower() == key:
                return dict(pkg)
    if name:
        key = name.strip().lower()
        for pkg in cached:
            if pkg.get("name", "").lower() == key:
                return dict(pkg)
    return None


def z1_motion_for_option(option_id: str) -> str | None:
    return Z1_MOTION_TOKEN_MAP.get((option_id or "").strip())


def find_z1_motion_option(
    merchant_id: str,
    *,
    option_id: str = "",
    name: str = "",
) -> dict[str, str] | None:
    """Resolve motion preset from cache or static catalogue (batch-stable ids)."""
    from .zone_tour import ZoneTourManager

    oid = (option_id or "").strip().lower()
    key = (name or "").strip().lower()
    for preset in Z1_MOTION_PRESETS:
        row = dict(preset)
        row["what_changes"] = row["description"]
        row["applies_to"] = row["description"]
        if oid and preset["id"].lower() == oid:
            return row
        if key and preset["name"].lower() == key:
            return row
    mgr = ZoneTourManager(merchant_id)
    for o in mgr.get_cached_zone_options():
        row = dict(o)
        rid = (row.get("id") or "").lower()
        if oid and rid == oid:
            return row
        if key and (row.get("name") or "").lower() == key:
            return row
    return None
