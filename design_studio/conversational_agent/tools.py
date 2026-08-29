"""Strands agent tools — colours, fonts, themes, zones, and the CF-05 zone tour.

Each ``@tool`` function is exposed to Bedrock via ``agent.AGENT_TOOLS``. Tools read the
active merchant from ``shop_context`` (set by ``server.py`` / ``runtime.py``).

Sections:
  - Colour / font utilities (validation, palettes, WCAG)
  - ``save_theme``, ``apply_style_tokens`` — write ``StyleTokens`` + preview refresh
  - Theme packages (CF-02) from ``ThemePackage``
  - Legacy zone overrides (``customize_zone``) — prefer ``apply_style_tokens``
  - Zone tour tools (``start_zone_tour``, ``apply_zone_tour_choice``, …)

Note: Many merchant clicks are handled **without** calling these tools — see
``chat_fast_path.py`` and ``zone_tour_actions.py`` for server-side fast paths.
"""

import json

from strands import tool

from .models import Zone, BorderRadius, Spacing, ZONE_DISPLAY_NAMES, ZoneStyle
from .color_engine import (
    generate_palette_from_seed,
    get_contrast_color,
    check_contrast_ratio,
    is_accessible,
    adjust_for_contrast,
    is_valid_color,
    normalize_hex,
    get_lighter,
    get_darker,
    is_valid_google_font,
    HARMONY_DESCRIPTIONS,
)
from .constants import (
    GOOGLE_FONTS,
    GOOGLE_FONTS_BY_CATEGORY,
)
from .config_manager import ConfigManager
from .shop_context import get_shop_uuid
from .token_mapper import build_tokens_from_theme_save
from .zone_scopes import (
    VALID_ZONE_CODES,
    ZONE_COLOR_CODES,
    clear_zone_scopes,
    set_global_colors,
    set_zone_color_scope,
)
from .style_repository import StyleRepository
from .zone_tour import ZoneTourManager, TOUR_STEPS, Z5_POSITIVE_SCRIPT
from .direct_style import _merge_updates, zones_touched_from_keys
from .page_context import build_page_context_for_agent


def _get_config_manager() -> ConfigManager:
    return ConfigManager(shop_uuid=get_shop_uuid())


def _get_zone_tour_manager() -> ZoneTourManager:
    cm = _get_config_manager()
    return ZoneTourManager(get_shop_uuid(), cm._repo, config_path=cm.config_path)


def _get_style_repository() -> StyleRepository:
    return StyleRepository(shop_uuid=get_shop_uuid())


def _tour_suffix() -> str:
    """Append zone-tour start text after ``save_theme`` when tour is not already active."""
    mgr = _get_zone_tour_manager()
    if mgr.is_active():
        return ""
    progress = mgr.start()
    step = TOUR_STEPS[0]
    return (
        f"\n\n🎯 **Zone tour started** (CF-05) — Step 1 of {progress['total_steps']}: "
        f"**{step.name}**. {step.controls}\n"
        "Use get_zone_tour_status() then guide the merchant with options. "
        "They can say **skip** to skip a zone."
    )


# =============================================================================
# COLOR TOOLS - Use coloraide for generation, LLM names the colors
# =============================================================================


@tool
def generate_color_palette(
    seed_color: str,
    harmony_type: str = "analogous",
    count: int = 5,
) -> str:
    """Generate a harmonious color palette from a seed color using color theory.

    Use this when you have a seed color concept and need to generate a full palette.
    YOU should then give each color a creative, evocative name.

    Args:
        seed_color: A hex color code (e.g., "#C45B28" for terracotta).
        harmony_type: One of: analogous, complement, triad, split, square, mono.
        count: Number of colors (3-6).

    Returns:
        A list of hex colors with their harmony description. You should name these creatively.
    """
    if not is_valid_color(seed_color):
        return f"Invalid hex color: {seed_color}. Please use format #RRGGBB."

    harmony = harmony_type if harmony_type in HARMONY_DESCRIPTIONS else "analogous"
    colors = generate_palette_from_seed(seed_color, harmony, count)

    desc = HARMONY_DESCRIPTIONS.get(harmony, "")
    lines = [
        f"Generated {harmony} palette ({desc}):\n",
        f"Seed: {seed_color}",
        "",
        "Palette colors:",
    ]
    for i, c in enumerate(colors, 1):
        contrast = get_contrast_color(c)
        lines.append(f"  {i}. {c} (best text: {contrast})")

    lines.append("\nNow give each color a creative, evocative name!")
    return "\n".join(lines)


@tool
def validate_color_and_get_info(hex_color: str) -> str:
    """Validate a hex color and get useful information about it.

    Use this to check if a color the LLM generated is valid and get contrast info.

    Args:
        hex_color: The hex color to validate.

    Returns:
        Validation result and color information.
    """
    if not is_valid_color(hex_color):
        return f" Invalid hex color: {hex_color}"

    normalized = normalize_hex(hex_color)
    contrast_color = get_contrast_color(normalized)
    lighter = get_lighter(normalized, 0.15)
    darker = get_darker(normalized, 0.15)

    return f"""Valid color: {normalized}
Best text color: {contrast_color}
Lighter variant: {lighter}
Darker variant: {darker}"""


@tool
def check_color_accessibility(foreground: str, background: str) -> str:
    """Check if a foreground/background color combination is accessible.

    Args:
        foreground: Text color hex.
        background: Background color hex.

    Returns:
        Accessibility analysis with recommendations.
    """
    if not is_valid_color(foreground) or not is_valid_color(background):
        return "Invalid color(s). Please use hex format #RRGGBB."

    ratio = check_contrast_ratio(foreground, background)
    aa_pass = is_accessible(foreground, background, "AA")
    aaa_pass = is_accessible(foreground, background, "AAA")

    status = "Excellent" if aaa_pass else ("Good" if aa_pass else "Poor")

    result = f"""Contrast Analysis: {foreground} on {background}
Ratio: {ratio:.2f}:1
WCAG AA (4.5:1): {"Pass" if aa_pass else "Fail"}
WCAG AAA (7:1): {"Pass" if aaa_pass else "Fail"}
Overall: {status}"""

    if not aa_pass:
        adjusted = adjust_for_contrast(foreground, background, 4.5)
        result += f"\n\nSuggested adjustment: {adjusted}"

    return result


@tool
def get_harmony_types() -> str:
    """Get available color harmony types with descriptions.

    Returns:
        List of harmony types the LLM can use for palette generation.
    """
    lines = ["Available color harmonies:\n"]
    for harmony, desc in HARMONY_DESCRIPTIONS.items():
        lines.append(f"  • **{harmony}** — {desc}")
    return "\n".join(lines)


# =============================================================================
# FONT TOOLS - Validate against Google Fonts
# =============================================================================


@tool
def get_available_fonts() -> str:
    """Get list of available Google Fonts.

    Returns:
        List of fonts the design can use (all free Google Fonts), grouped by
        category. Sourced from fonts.json so the whitelist stays in one place.
    """
    if not GOOGLE_FONTS_BY_CATEGORY:
        return "No fonts available — fonts.json missing or empty."

    lines = ["Available Google Fonts (all free):\n"]
    for category, fonts in GOOGLE_FONTS_BY_CATEGORY.items():
        if not fonts:
            continue
        label = category.replace("-", " ").capitalize()
        lines.append(f"**{label}:**")
        lines.append(f"  {', '.join(fonts)}")
        lines.append("")

    return "\n".join(lines)


@tool
def validate_font(font_name: str) -> str:
    """Check if a font is available in Google Fonts.

    Args:
        font_name: The font name to validate.

    Returns:
        Whether the font is valid and available.
    """
    if is_valid_google_font(font_name):
        return f"✅ '{font_name}' is available in Google Fonts."
    else:
        similar = [f for f in GOOGLE_FONTS if font_name.lower() in f.lower()]
        if similar:
            return f"❌ '{font_name}' not found. Did you mean: {', '.join(similar)}?"
        return f"❌ '{font_name}' not found. Use get_available_fonts() to see options."


# =============================================================================
# CONFIG TOOLS - Persist the design
# =============================================================================


@tool
def save_theme(
    theme_name: str,
    theme_description: str,
    mood_summary: str,
    primary_color: str,
    primary_color_name: str,
    secondary_color: str,
    secondary_color_name: str,
    accent_color: str,
    accent_color_name: str,
    background_color: str,
    background_color_name: str,
    surface_color: str,
    surface_color_name: str,
    heading_font: str,
    body_font: str,
    border_radius: str = "rounded",
    spacing: str = "normal",
) -> str:
    """Save a complete theme to the storefront configuration.

    Call this after you've designed a theme with the merchant.

    Args:
        theme_name: Creative name for the theme (e.g., "Aegean Sunset").
        theme_description: One-line description of the vibe.
        mood_summary: The merchant's mood/vibe keywords.
        primary_color: Primary brand color hex.
        primary_color_name: Creative name for primary color.
        secondary_color: Secondary color hex.
        secondary_color_name: Creative name for secondary color.
        accent_color: Accent color hex.
        accent_color_name: Creative name for accent color.
        background_color: Main background hex.
        background_color_name: Creative name for background.
        surface_color: Card/surface background hex.
        surface_color_name: Creative name for surface color.
        heading_font: Google Font for headings.
        body_font: Google Font for body text.
        border_radius: Shape style (sharp, soft, rounded, pill).
        spacing: Spacing preset (compact, normal, spacious).

    Returns:
        Confirmation of saved theme.
    """
    for color in [primary_color, secondary_color, accent_color, background_color, surface_color]:
        if not is_valid_color(color):
            return f"Invalid color: {color}. Please use hex format #RRGGBB."

    for font in [heading_font, body_font]:
        if not is_valid_google_font(font):
            return f"Invalid font: {font}. Use get_available_fonts() to see options."

    try:
        radius = BorderRadius(border_radius.lower())
    except ValueError:
        return f"Invalid border_radius: {border_radius}. Use: sharp, soft, rounded, pill."

    try:
        space = Spacing(spacing.lower())
    except ValueError:
        return f"Invalid spacing: {spacing}. Use: compact, normal, spacious."

    from .token_mapper import derive_text_colors

    text_primary, text_secondary = derive_text_colors(background_color)

    tokens = build_tokens_from_theme_save(
        theme_name=theme_name,
        primary_color=primary_color,
        secondary_color=secondary_color,
        accent_color=accent_color,
        background_color=background_color,
        surface_color=surface_color,
        text_primary=text_primary,
        text_secondary=text_secondary,
        heading_font=heading_font,
        body_font=body_font,
        border_radius=radius.value,
        spacing=space.value,
    )
    tokens.colors.paletteName = theme_name

    cm = _get_config_manager()
    cm.save_tokens(tokens, theme_name=theme_name, mood_summary=mood_summary)
    cm.reload()

    return f"""✨ Theme "{theme_name}" saved!

**{theme_description}**
Mood: {mood_summary}

Colors:
  • {primary_color_name}: {tokens.colors.primary}
  • {secondary_color_name}: {tokens.colors.secondary}
  • {accent_color_name}: {tokens.colors.accent}
  • {background_color_name}: {tokens.colors.background}
  • {surface_color_name}: {tokens.colors.surface}

Typography: {heading_font} / {body_font}
Shape: {radius.value}
Spacing: {space.value}
{_tour_suffix()}"""


@tool
def get_storefront_page_context() -> str:
    """Return the complete storefront blueprint + live theme — use before ambiguous edits.

    Includes:
    - page_layout_scroll_order: every visible block top-to-bottom (hero, intro, offers, products, footer)
    - theme_application_flow: how tokens become the HTML preview
    - token_to_preview_mapping: which token drives which CSS / look
    - playbook_examples: merchant phrase → exact tool steps (e.g. pink whole page, all italic)
    - look_and_feel_now: current colours, fonts, hero, cards, buttons
    - zones, zone_tour state, tool_selection_guide

    Call this when:
    - Merchant mentions whole page, entire storefront, or multiple areas at once
    - You are unsure which zone or tool to use
    - Before answering whether something is possible

    Returns:
        JSON blueprint and current token snapshot for the active shop.
    """
    ctx = build_page_context_for_agent(get_shop_uuid())
    return json.dumps(ctx, indent=2)


@tool
def apply_style_tokens(
    hero_overlay: str = "",
    hero_layout: str = "",
    logo_placement: str = "",
    tagline_placement: str = "",
    store_name_style: str = "",
    heading_font: str = "",
    body_font: str = "",
    font_scale: str = "",
    heading_style: str = "",
    body_style: str = "",
    product_card_shape: str = "",
    product_card_layout: str = "",
    product_card_shadow: str = "",
    price_style: str = "",
    card_tap_animation: str = "",
    button_shape: str = "",
    button_style: str = "",
    button_size: str = "",
    button_press_animation: str = "",
    border_radius: str = "",
    spacing: str = "",
    motion_transition: str = "",
    offer_filter_preset: str = "",
    background_color: str = "",
    surface_color: str = "",
    primary_color: str = "",
    accent_color: str = "",
    zone_code: str = "",
    clear_zone_color_overrides: bool = False,
) -> str:
    """Apply specific storefront style tokens and refresh the live preview immediately.

    Use this when the merchant asks for concrete visual changes (e.g. pill buttons,
    dark hero scrim, grid3 product cards) — including mid-conversation, without restarting
    discovery or theme packages.

    Args:
        hero_overlay: none, lightScrim, autoScrim, darkScrim
        hero_layout: fullWidth, splitImageText, carousel
        logo_placement: left, center, right
        tagline_placement: none, center, bottomLeft, bottomRight
        store_name_style: subtle, balanced, bold (hero store name only — not all page text)
        heading_font, body_font: Google Font family names (typography / Z3 + page text)
        font_scale: compact, standard, generous
        heading_style, body_style: normal, italic (page headings / body copy in intro, info, products)
        product_card_shape: rounded, sharp, circularImage
        product_card_layout: grid2, grid3, list, featuredPlusGrid
        product_card_shadow: flat, subtle, elevated, floating
        price_style: boldRed, accentColor, understatedGrey, badgePill
        card_tap_animation: none, scaleDown, ripple
        button_shape: sharp, subtleRounded, rounded, pill
        button_style: filled, outlined, soft, ghost
        button_size: compact, standard, large
        button_press_animation: none, darken, scale, ripple
        border_radius: sharp, soft, rounded, pill (global corners)
        spacing: compact, normal, spacious
        motion_transition: none, fadeTint, slideTint
        offer_filter_preset: warm, cool, vivid (offer card images only)
        background_color, surface_color: Page backdrop (Z1 global) OR section-only when zone_code is set
        zone_code: Z2, Z3, Z4S, Z4C, or Z6 — scopes background_color/surface_color to that section only
        primary_color, accent_color: Brand / CTA colours (Z1 global, or scoped with zone_code)
        clear_zone_color_overrides: True when changing page-wide background so zone tints do not block it

    Returns:
        Confirmation of what was updated.
    """
    explicit = {
        k: v
        for k, v in {
            "hero_overlay": hero_overlay,
            "hero_layout": hero_layout,
            "logo_placement": logo_placement,
            "tagline_placement": tagline_placement,
            "store_name_style": store_name_style,
            "heading_font": heading_font,
            "body_font": body_font,
            "font_scale": font_scale,
            "heading_style": heading_style,
            "body_style": body_style,
            "product_card_shape": product_card_shape,
            "product_card_layout": product_card_layout,
            "product_card_shadow": product_card_shadow,
            "price_style": price_style,
            "card_tap_animation": card_tap_animation,
            "button_shape": button_shape,
            "button_style": button_style,
            "button_size": button_size,
            "button_press_animation": button_press_animation,
            "border_radius": border_radius,
            "spacing": spacing,
            "motion_transition": motion_transition,
            "offer_filter_preset": offer_filter_preset,
        }.items()
        if v
    }
    color_updates: dict[str, str] = {}
    for key, val in [
        ("background_color", background_color),
        ("surface_color", surface_color),
        ("primary_color", primary_color),
        ("accent_color", accent_color),
    ]:
        if val:
            if not is_valid_color(val):
                return f"Invalid colour for {key}: {val}. Use #RRGGBB."
            color_updates[key.replace("_color", "")] = normalize_hex(val)

    if not explicit and not color_updates:
        return "No style parameters provided. Pass at least one field (e.g. button_shape=pill, background_color=#FFC0CB)."

    cm = _get_config_manager()
    tokens = cm.tokens.model_copy(deep=True)
    scope_zone = (zone_code or "").upper()
    if clear_zone_color_overrides and color_updates and scope_zone not in ZONE_COLOR_CODES:
        tokens = clear_zone_scopes(tokens)
    bg_in = color_updates.get("background")
    surf_in = color_updates.get("surface")
    if bg_in or surf_in or color_updates.get("primary") or color_updates.get("accent"):
        if scope_zone in ZONE_COLOR_CODES:
            tokens = set_zone_color_scope(
                tokens,
                scope_zone,
                primary=color_updates.get("primary", ""),
                accent=color_updates.get("accent", ""),
                background=bg_in or "",
                surface=surf_in or "",
            )
        elif bg_in or surf_in:
            main = bg_in or surf_in
            if not bg_in:
                bg_in = main
            if not surf_in:
                surf_in = main
            text_fix = get_contrast_color(surf_in)
            tokens = set_global_colors(
                tokens,
                background=bg_in,
                surface=surf_in,
                primary=color_updates.get("primary", ""),
                accent=color_updates.get("accent", ""),
                text_primary=text_fix,
                text_secondary=text_fix,
            )
        elif color_updates.get("primary") or color_updates.get("accent"):
            tokens = set_global_colors(
                tokens,
                primary=color_updates.get("primary", ""),
                accent=color_updates.get("accent", ""),
            )
    if explicit:
        try:
            tokens = _merge_updates(tokens, explicit)
        except (ValueError, Exception) as e:
            return str(e)
    all_changed_keys = set(explicit.keys())
    if color_updates:
        all_changed_keys.add("background_color")
    cm.save_tokens(
        tokens,
        theme_name=tokens.colors.paletteName or "Custom Theme",
        change_summary={
            "zonesTouched": zones_touched_from_keys(all_changed_keys),
            "humanSummary": "Style tokens updated from chat.",
        },
    )
    cm.reload()

    lines = [f"  • {k}: {v}" for k, v in explicit.items()]
    if scope_zone in ZONE_COLOR_CODES:
        lines.append(f"  • zone: {scope_zone} (section-scoped colours)")
    if bg_in:
        lines.append(f"  • background: {bg_in}")
    if surf_in:
        lines.append(f"  • surface: {surf_in}")
    for k in ("primary", "accent"):
        if color_updates.get(k):
            lines.append(f"  • {k}: {color_updates[k]}")
    out = "✨ Preview updated:\n" + "\n".join(lines)
    mgr = _get_zone_tour_manager()
    if mgr.is_active():
        from .zone_tour_advance import maybe_advance_after_style_tokens

        advance_note = maybe_advance_after_style_tokens(
            mgr,
            hero_overlay=hero_overlay,
            hero_layout=hero_layout,
            logo_placement=logo_placement,
            tagline_placement=tagline_placement,
            store_name_style=store_name_style,
            heading_font=heading_font,
            body_font=body_font,
            font_scale=font_scale,
            heading_style=heading_style,
            body_style=body_style,
            product_card_shape=product_card_shape,
            product_card_layout=product_card_layout,
            product_card_shadow=product_card_shadow,
            price_style=price_style,
            card_tap_animation=card_tap_animation,
            button_shape=button_shape,
            button_style=button_style,
            button_size=button_size,
            button_press_animation=button_press_animation,
            border_radius=border_radius,
            spacing=spacing,
            motion_transition=motion_transition,
            offer_filter_preset=offer_filter_preset,
            background_color=background_color,
            surface_color=surface_color,
            primary_color=primary_color,
            accent_color=accent_color,
            zone_code=zone_code,
        )
        if advance_note:
            out += f"\n\n{advance_note}"
    return out


@tool
def get_current_theme() -> str:
    """Get the current storefront theme configuration.

    Returns:
        Summary of current theme settings.
    """
    cm = _get_config_manager()
    config = cm.config

    lines = [
        f"**Current Theme: {config.theme_name}**",
        f"_{config.theme_description}_" if config.theme_description else "",
        f"Mood: {config.mood_summary}" if config.mood_summary else "",
        "",
        "**Colors:**",
        f"  • Primary: {config.primary_color_name} ({config.primary_color})",
        f"  • Secondary: {config.secondary_color_name} ({config.secondary_color})",
        f"  • Accent: {config.accent_color_name} ({config.accent_color})",
        f"  • Background: {config.background_color_name} ({config.background_color})",
        f"  • Surface: {config.surface_color_name} ({config.surface_color})",
        "",
        "**Typography:**",
        f"  • Headings: {config.heading_font}",
        f"  • Body: {config.body_font}",
        "",
        f"**Shape:** {config.default_border_radius.value}",
        f"**Spacing:** {config.default_spacing.value}",
    ]

    if config.zone_overrides:
        lines.append("")
        lines.append("**Customized Zones:**")
        for zone in config.zone_overrides:
            lines.append(f"  • {ZONE_DISPLAY_NAMES.get(zone, zone.value)}")

    return "\n".join(lines)


@tool
def list_zones() -> str:
    """List all customizable storefront zones in display order.

    Returns:
        List of zones the merchant can customize.
    """
    cm = _get_config_manager()
    overrides = cm.config.zone_overrides

    lines = ["**Storefront Zones** (in display order):\n"]
    for zone in Zone:
        name = ZONE_DISPLAY_NAMES.get(zone, zone.value)
        status = " ✨" if zone in overrides else ""
        lines.append(f"  {name}{status}")

    lines.append("\n_Zones marked with ✨ have custom styling._")
    return "\n".join(lines)


@tool
def customize_zone(
    zone_name: str,
    primary_color: str = "",
    background_color: str = "",
    border_radius: str = "",
) -> str:
    """Apply custom styling to a specific zone.

    Args:
        zone_name: Zone to customize (use list_zones() to see options).
        primary_color: Custom primary color for this zone (hex).
        background_color: Custom background color for this zone (hex).
        border_radius: Custom shape (sharp, soft, rounded, pill).

    Returns:
        Confirmation of zone customization.
    """
    zone_key = zone_name.lower().replace(" ", "_")
    try:
        zone = Zone(zone_key)
    except ValueError:
        zones = ", ".join(ZONE_DISPLAY_NAMES.values())
        return f"Unknown zone '{zone_name}'. Available zones: {zones}"

    cm = _get_config_manager()
    config = cm.config

    if zone not in config.zone_overrides:
        config.zone_overrides[zone] = ZoneStyle()

    style = config.zone_overrides[zone]
    changes = []

    if primary_color:
        if not is_valid_color(primary_color):
            return f"Invalid color: {primary_color}"
        style.primary_color = normalize_hex(primary_color)
        changes.append(f"primary color → {primary_color}")

    if background_color:
        if not is_valid_color(background_color):
            return f"Invalid color: {background_color}"
        style.background_color = normalize_hex(background_color)
        changes.append(f"background → {background_color}")

    if border_radius:
        try:
            style.border_radius = BorderRadius(border_radius.lower())
            changes.append(f"shape → {border_radius}")
        except ValueError:
            return f"Invalid shape: {border_radius}. Use: sharp, soft, rounded, pill."

    cm.apply_zone(zone, style)
    cm.reload()

    display_name = ZONE_DISPLAY_NAMES.get(zone, zone_name)
    return f"✨ Customized **{display_name}**: {', '.join(changes)}"


@tool
def reset_zone(zone_name: str, confirmed: bool = False) -> str:
    """Reset a zone to use the global theme settings.

    Args:
        zone_name: Zone to reset.
        confirmed: Must be True to execute. If False, returns a confirmation prompt.

    Returns:
        Confirmation prompt or result.
    """
    zone_key = zone_name.lower().replace(" ", "_")
    try:
        zone = Zone(zone_key)
    except ValueError:
        return f"Unknown zone '{zone_name}'."

    display_name = ZONE_DISPLAY_NAMES.get(zone, zone_name)

    if not confirmed:
        return (
            f"⚠️ This will reset **{display_name}** to global theme defaults, "
            f"removing all zone-specific customizations. "
            f"Please confirm with the user before calling again with confirmed=True."
        )

    cm = _get_config_manager()
    if zone in cm.config.zone_overrides:
        del cm.config.zone_overrides[zone]
        from .token_mapper import storefront_config_to_tokens

        cm.save_tokens(
            storefront_config_to_tokens(cm.config),
            theme_name=cm.config.theme_name,
        )
        cm.reload()

    return f"**{display_name}** now uses global theme settings."


def rank_packages_by_mood(packages: list[dict], mood_tags: list[str]) -> list[dict]:
    """Order catalogue packages by overlap of their ``moodMatch`` with saved mood tags (CF-02 / 3.3).

    Best matches first; ties and non-matching packages keep their original order (stable).
    """
    wanted = {t.strip().lower() for t in mood_tags if t and t.strip()}
    if not wanted:
        return list(packages)

    def overlap(pkg: dict) -> int:
        pkg_moods = {m.strip().lower() for m in pkg.get("moodMatch", []) if m}
        return len(wanted & pkg_moods)

    return [pkg for _, pkg in sorted(enumerate(packages), key=lambda p: (-overlap(p[1]), p[0]))]


@tool
def list_theme_packages() -> str:
    """List pre-built theme packages from the catalogue (CF-02).

    Use when presenting starter themes. Packages include full tokens (colors, fonts, cards, buttons).
    When the merchant has saved mood tags, packages are ordered by how well they match (CF-02 / 3.3).

    Returns:
        Available theme packages with packageId, name, description, and mood tags.
    """
    repo = StyleRepository(shop_uuid=get_shop_uuid())
    if not repo.enabled:
        return "Theme package catalogue unavailable (USE_DYNAMODB=false)."

    packages = repo.list_theme_packages()
    if not packages:
        return (
            "No theme packages in the catalogue yet. "
            "Run: uv run python scripts/seed_theme_packages.py"
        )

    mood_tags = [t for t in (repo.get_style_profile() or {}).get("moodTags", []) if t]
    if mood_tags:
        packages = rank_packages_by_mood(packages, mood_tags)

    header = "**Pre-built theme packages:**"
    if mood_tags:
        header += f"\n_Ordered to match the merchant's saved vibe: {', '.join(mood_tags)}._"
    lines = [header + "\n"]
    for pkg in packages:
        moods = ", ".join(pkg.get("moodMatch", []))
        lines.append(
            f"• **{pkg.get('displayName')}** (`{pkg.get('packageId')}`) — {pkg.get('description', '')}"
        )
        if moods:
            lines.append(f"  Mood match: {moods}")
    lines.append(
        "\nUse apply_theme_package(package_id) only for these catalogue ids. "
        "Custom themes from chat use save_theme; UI card clicks are applied by the server."
    )
    return "\n".join(lines)


@tool
def apply_theme_package(package_id: str, mood_summary: str = "") -> str:
    """Apply a pre-built theme package by id (e.g. tuscan_workshop).

    Args:
        package_id: Stable slug from list_theme_packages().
        mood_summary: Optional merchant mood keywords.

    Returns:
        Confirmation after saving to draft.
    """
    repo = StyleRepository()
    if not repo.enabled:
        return "DynamoDB disabled — cannot load theme packages."

    pkg = repo.get_theme_package(package_id)
    if not pkg:
        return f"Unknown package '{package_id}'. Use list_theme_packages() to see options."

    tokens = repo.get_theme_package_tokens(package_id)
    if not tokens:
        return f"Package '{package_id}' has no tokens."

    tokens = clear_zone_scopes(tokens)
    name = pkg.get("displayName", package_id)
    cm = _get_config_manager()
    cm.save_tokens(
        tokens,
        theme_name=name,
        mood_summary=mood_summary,
        based_on_package_id=package_id,
    )
    cm.reload()

    return f"""✨ Applied theme package **{name}**!

{pkg.get('description', '')}

Saved as draft — preview updated.{_tour_suffix()}"""


@tool
def save_mood_tags(
    mood_tags: str,
    merchant_category: str = "",
) -> str:
    """Save merchant mood/style tags to their style profile (CF-01).

    Args:
        mood_tags: Comma-separated tags e.g. "warm, rustic, artisan".
        merchant_category: Optional category e.g. "cafe_bar".

    Returns:
        Confirmation.
    """
    tags = [t.strip() for t in mood_tags.split(",") if t.strip()]
    if not tags:
        return "Please provide at least one mood tag."

    repo = _get_style_repository()
    if not repo.enabled:
        return "DynamoDB not configured — cannot save profile."

    repo.update_mood_tags(tags, merchant_category=merchant_category)
    return f"Saved mood tags: {', '.join(tags)}. I'll use these for theme suggestions!"


@tool
def start_zone_tour() -> str:
    """Start the zone-by-zone customization tour (CF-05).

    Call after a theme is saved if the tour did not auto-start.

    Returns:
        Current step and instructions for the agent.
    """
    mgr = _get_zone_tour_manager()
    if mgr.is_active():
        return get_zone_tour_status()
    progress = mgr.start()
    step = mgr.current_step()
    return (
        f"Zone tour started. Current: **{step.name}** ({step.code}).\n"
        f"{step.headline}\n{step.controls}\n"
        f"Progress: {progress['editable_completed']}/{progress['editable_total']} editable zones done."
    )


@tool
def get_zone_tour_status() -> str:
    """Get zone tour progress (current area, chat sub-step, completed/skipped).

    The UI shows one question per sub-step with server-injected buttons; preview highlights the active section.

    Returns:
        Summary for guiding the merchant in plain language.
    """
    mgr = _get_zone_tour_manager()
    progress = mgr.progress_dict()
    if not progress.get("active"):
        return "No active zone tour. Start one with start_zone_tour() after saving a theme."

    step = mgr.current_step()
    if not step:
        return "Zone tour is complete! 🎉 Summarize the design journey."

    sub_total = progress.get("sub_step_total") or 0
    sub_idx = (progress.get("sub_step_index") or 0) + 1
    sub_line = (
        f"Chat sub-step {sub_idx}/{sub_total}: {progress.get('current_prompt', '')}"
        if sub_total
        else ""
    )
    lines = [
        f"**Tour active** — Area {progress['step_index'] + 1}/{progress['total_steps']}: "
        f"**{step.name}**",
        f"Headline: {step.headline}",
        sub_line,
        f"Editable areas done: {progress['editable_completed']}/{progress['editable_total']}",
        f"Can skip area: {progress['can_skip']}",
        f"Can skip sub-step: {progress.get('can_skip_sub_step', False)}",
    ]
    if step.info_only:
        lines.append(f"Z5 script (use in message): {Z5_POSITIVE_SCRIPT}")
    else:
        from .zone_dynamic_options import summarize_cached_tour_options

        shown = summarize_cached_tour_options(mgr)
        if shown:
            lines.append(f"Chat buttons visible now (only mention these): {shown}")
    return "\n".join(lines)


@tool
def refresh_zone_tour_options(
    user_request: str = "",
    option_count: int = 0,
) -> str:
    """Generate a fresh batch of swatches for the current tour sub-step.

    Call when the merchant asks for more, different, or stylish options instead of
    repeating the same presets. Updates the chat buttons; does not advance the tour.

    Args:
        user_request: Merchant words — used to tune mood ranking (e.g. "stylish", "minimal").
        option_count: How many new swatches to show (1–4). Use 0 for a full batch of four.

    Returns:
        Names of the new options — use response_type zone_tour and a short intro message.
    """
    from .zone_dynamic_options import refresh_options_for_current_sub_step

    mgr = _get_zone_tour_manager()
    if not mgr.is_active():
        return "No active zone tour."

    step = mgr.current_step()
    if not step:
        return "Tour has no current step."

    if step.info_only:
        return "Z5 is view-only — use acknowledge_offers_zone()."

    limit = option_count if 1 <= option_count <= 4 else None
    append = option_count == 1
    before_ids = mgr.get_cached_option_ids()
    colors, layouts, packages, lead = refresh_options_for_current_sub_step(
        mgr.shop_uuid,
        user_request,
        option_limit=limit,
        append=append,
        must_differ_from=before_ids,
    )
    opts = packages or layouts or colors
    if not opts:
        return (
            f"{lead} Describe the look you want and use apply_style_tokens or "
            "apply_zone_tour_choice — do not claim new swatches were added."
        )

    from .zone_dynamic_options import summarize_cached_tour_options

    visible = summarize_cached_tour_options(mgr)
    return (
        f"{lead}. Chat buttons now visible: {visible or 'none'}. "
        "In your merchant-facing message, ONLY reference option names from that list. "
        "Reply with response_type **zone_tour**, a one-line intro, and do NOT say you "
        "already applied a style unless you also called apply_style_tokens or "
        "apply_zone_tour_choice in this turn."
    )


@tool
def apply_zone_tour_choice(
    zone_code: str,
    option_id: str = "",
    primary_color: str = "",
    accent_color: str = "",
    background_color: str = "",
    heading_font: str = "",
    body_font: str = "",
    font_scale: str = "",
    text_primary: str = "",
    text_secondary: str = "",
    hero_layout: str = "",
    hero_overlay: str = "",
    logo_placement: str = "",
    card_shape: str = "",
    card_layout: str = "",
    card_shadow: str = "",
    price_style: str = "",
    button_shape: str = "",
    button_style: str = "",
    button_size: str = "",
) -> str:
    """Apply the merchant's choice for the current zone tour step.

    Args:
        zone_code: Z1, Z2, Z3, Z4, or Z6 (not Z5 — offers are platform-managed).
        option_id: Preset id e.g. classic_center, soft_grid, friendly_rounded, keep_current.
        primary_color, accent_color, background_color: For Z1.
        heading_font, body_font, font_scale: For Z3.
        hero_layout, hero_overlay, logo_placement: For Z2.
        card_shape, card_layout, card_shadow: For Z4 layout step.
        price_style: boldRed, accentColor, understatedGrey, badgePill (Z4 price display step).
        button_shape, button_style, button_size: For Z6 (compact, standard, large).

    Returns:
        Confirmation; call complete_zone_tour_step() after presenting options.
    """
    code = zone_code.upper()
    if code not in VALID_ZONE_CODES:
        return f"Invalid zone_code '{zone_code}'. Must be one of: {', '.join(sorted(VALID_ZONE_CODES))}."
    if code == "Z5":
        return "Z5 is view-only. Use acknowledge_offers_zone() instead."

    mgr = _get_zone_tour_manager()
    if mgr.is_active() and option_id:
        from .zone_tour_actions import try_handle_zone_tour_message

        tour_resp = try_handle_zone_tour_message(get_shop_uuid(), f"zone option {option_id}")
        if tour_resp:
            return tour_resp.get("message", "Applied to your preview.")

    mgr.apply_selection_to_tokens(
        code,  # type: ignore[arg-type]
        option_id=option_id,
        primary_color=primary_color,
        accent_color=accent_color,
        background_color=background_color,
        heading_font=heading_font,
        body_font=body_font,
        font_scale=font_scale,
        text_primary=text_primary,
        text_secondary=text_secondary,
        hero_layout=hero_layout,
        hero_overlay=hero_overlay,
        logo_placement=logo_placement,
        card_shape=card_shape,
        card_layout=card_layout,
        card_shadow=card_shadow,
        price_style=price_style,
        button_shape=button_shape,
        button_style=button_style,
        button_size=button_size,
    )
    msg = f"Applied selection for {code}" + (f" ({option_id})" if option_id else "") + "."
    if mgr.is_active():
        from .zone_tour_advance import maybe_advance_after_zone_choice

        advance_note = maybe_advance_after_zone_choice(
            mgr,
            code,
            option_id=option_id,
            primary_color=primary_color,
            accent_color=accent_color,
            background_color=background_color,
            heading_font=heading_font,
            body_font=body_font,
            font_scale=font_scale,
            text_primary=text_primary,
            text_secondary=text_secondary,
            hero_layout=hero_layout,
            hero_overlay=hero_overlay,
            logo_placement=logo_placement,
            card_shape=card_shape,
            card_layout=card_layout,
            card_shadow=card_shadow,
            price_style=price_style,
            button_shape=button_shape,
            button_style=button_style,
            button_size=button_size,
        )
        if advance_note:
            msg += f"\n\n{advance_note}"
    return msg


@tool
def complete_zone_tour_step() -> str:
    """Mark the current zone tour step complete and advance to the next zone.

    Returns:
        Next step info or tour-complete message.
    """
    mgr = _get_zone_tour_manager()
    if not mgr.is_active():
        return "No active tour."

    progress = mgr.complete_current()
    if not progress.get("active"):
        return "Zone tour complete! 🎉 All zones visited. Offer to publish or fine-tune."

    step = mgr.current_step()
    if not step:
        return "Zone tour complete! 🎉"

    extra = ""
    if step.info_only:
        extra = f"\n\nDeliver Z5 message:\n{Z5_POSITIVE_SCRIPT}"

    return (
        f"Advanced to **{step.name}** ({step.code}).\n" f"{step.headline}\n{step.controls}{extra}"
    )


@tool
def skip_zone_tour_sub_step() -> str:
    """Skip the current chat sub-step and move to the next question in this area.

    Use when the merchant says *skip this step*, *next step*, or wants to jump ahead
    within the same zone (e.g. skip button style and go straight to CTA colour).

    Returns:
        Next sub-step prompt for the same zone.
    """
    mgr = _get_zone_tour_manager()
    if not mgr.is_active():
        return "No active tour."

    step = mgr.current_step()
    if not step or step.info_only:
        return "No sub-step to skip on this screen."

    if not mgr.can_skip_sub_step():
        return (
            "You're on the last step in this area — use **skip_zone_tour_step()** to skip "
            "the whole area, or pick an option."
        )

    from .zone_tour_flow import current_sub_step, sub_steps_for_zone

    sub_idx_before = mgr.get_sub_step_index()
    total = len(sub_steps_for_zone(step.code))
    mgr.skip_current_sub_step()
    sub = current_sub_step(step.code, mgr.get_sub_step_index())
    prev = sub_idx_before + 1
    nxt = mgr.get_sub_step_index() + 1
    prompt = sub.prompt if sub else ""
    return (
        f"Skipped sub-step {prev}/{total} in **{step.name}**. "
        f"Now on sub-step **{nxt}/{total}**.\n{prompt}"
    )


@tool
def skip_zone_tour_step() -> str:
    """Skip the entire current zone (merchant chose not to customize this area).

    Returns:
        Next step info.
    """
    mgr = _get_zone_tour_manager()
    if not mgr.is_active():
        return "No active tour."

    step = mgr.current_step()
    if step and step.info_only:
        return "Cannot skip Z5 — use acknowledge_offers_zone() to continue."

    progress = mgr.skip_current()
    if not progress.get("active"):
        return "Skipped — tour complete! 🎉"

    next_step = mgr.current_step()
    if not next_step:
        return "Skipped — tour complete! 🎉"

    return (
        f"Skipped **{step.name if step else 'zone'}**. "
        f"Now on **{next_step.name}** ({next_step.code}): {next_step.controls}"
    )


@tool
def acknowledge_offers_zone() -> str:
    """Acknowledge Z5 (offer cards) with positive framing and advance (Z5-02).

    Returns:
        Confirmation and next zone (Z6).
    """
    mgr = _get_zone_tour_manager()
    if not mgr.is_active():
        return "No active tour."

    step = mgr.current_step()
    if not step or step.code != "Z5":
        return f"Current zone is {step.code if step else 'none'} — use complete_zone_tour_step()."

    mgr.complete_current()
    next_step = mgr.current_step()
    if not next_step:
        return f"{Z5_POSITIVE_SCRIPT}\n\nTour complete! 🎉"

    return (
        f"{Z5_POSITIVE_SCRIPT}\n\n"
        f"Advanced to **{next_step.name}** ({next_step.code}): {next_step.controls}"
    )


@tool
def reset_all() -> str:
    """Reset the storefront to default settings.

    Returns:
        Confirmation of reset.
    """
    cm = _get_config_manager()
    cm.reset()
    cm.reload()
    return "Storefront reset to defaults. Ready to start fresh!"
