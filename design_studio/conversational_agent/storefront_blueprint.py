"""Canonical storefront layout, tokens, and agent playbooks — tied to storefront.html.

``PAGE_LAYOUT`` documents DOM selectors and zone codes top-to-bottom. Injected into the
system prompt so the LLM knows what merchants see. Keep in sync when ``storefront.html``
structure changes.
"""

from __future__ import annotations

from typing import Any

# Top-to-bottom scroll order (mobile preview) — what merchants see
PAGE_LAYOUT: list[dict[str, Any]] = [
    {
        "order": 1,
        "merchant_label": "Hero banner photo",
        "dom": ".sf-hero.sf-zone--z2 .sf-banner__media",
        "zone": "Z2",
        "look_and_feel": "Full-width photo; scrim overlay (light/auto/dark/none) via hero.overlay",
    },
    {
        "order": 2,
        "merchant_label": "Store logo on hero",
        "dom": ".sf-banner__logo-wrap",
        "zone": "Z2",
        "look_and_feel": "Logo position left/center/right — hero.logoPlacement",
    },
    {
        "order": 3,
        "merchant_label": "Store name & tagline band",
        "dom": "#sf-name, .sf-hero-tagline, .sf-info.sf-info--hero",
        "zone": "Z2 + Z3",
        "look_and_feel": "Store name weight subtle/balanced/bold (Z2); panels use surface colour (Z1)",
    },
    {
        "order": 4,
        "merchant_label": "Follow button",
        "dom": ".sf-follow.sf-zone--z6 .sf-follow__btn",
        "zone": "Z6 + Z1",
        "look_and_feel": "Shape/style from buttons.*; colour from primary/accent or zoneScopes.Z6",
    },
    {
        "order": 5,
        "merchant_label": "Store intro",
        "dom": ".sf-store-intro.sf-zone--z3",
        "zone": "Z3",
        "look_and_feel": "Fonts typography.*; panel background = colors.surface (Z1) or zoneScopes.Z3",
    },
    {
        "order": 6,
        "merchant_label": "Offer / coupon carousel",
        "dom": "#sf-offers-section.sf-zone--z5",
        "zone": "Z5",
        "look_and_feel": "Layout fixed by the platform; optional image filter warm/cool/vivid only",
    },
    {
        "order": 7,
        "merchant_label": "Our Products carousel",
        "dom": "#sf-showcase-section.sf-zone--z4-showcase",
        "zone": "Z4S",
        "look_and_feel": "Section background zoneScopes.Z4S; cards use productCards.*",
    },
    {
        "order": 8,
        "merchant_label": "All Products & Services grid",
        "dom": "#sf-products-section.sf-zone--z4-catalog",
        "zone": "Z4C",
        "look_and_feel": "Section background zoneScopes.Z4C; same card tokens as showcase",
    },
    {
        "order": 9,
        "merchant_label": "Store details & hours",
        "dom": ".sf-store-details, .sf-hours-section.sf-zone--z3",
        "zone": "Z3",
        "look_and_feel": "Body/heading fonts and scale; text colours from colors.textPrimary",
    },
    {
        "order": 10,
        "merchant_label": "Get Directions footer CTA",
        "dom": ".sf-directions, .sf-directions__btn",
        "zone": "Z6",
        "look_and_feel": "Footer bar uses surface; button uses buttons.* + secondary/CTA colours",
    },
]

THEME_APPLICATION_FLOW: list[str] = [
    "1. Merchant picks a theme package OR you call save_theme / apply_theme_package → writes tokens.colors, typography, geometry to STYLE#DRAFT.",
    "2. ConfigManager maps tokens → camelCase theme object (token_mapper.tokens_to_preview_theme).",
    "3. server injects theme JSON into storefront.html before render(); preview iframe runs applyTheme(theme).",
    "4. applyTheme sets CSS variables on .sf-frame: --sf-color-page (background), --color-white (surface), fonts, radius, spacing.",
    "5. Per-zone overrides: theme.zoneScopes.Z4S etc. paint only that section (offer/showcase/catalog/hero panels).",
    "6. Mid-session tweaks: apply_style_tokens / apply_zone_tour_choice update tokens → save → preview refreshes.",
    "7. Whole-page background colour: set BOTH background_color AND surface_color + clear_zone_color_overrides=true.",
]

TOKEN_TO_PREVIEW: dict[str, str] = {
    "colors.primary": "Follow button, accents, price highlights (--sf-color-primary)",
    "colors.accent": "Secondary accents, links",
    "colors.background": "Page backdrop between sections (--sf-color-page)",
    "colors.surface": "White panels: intro, hero info band, directions bar (--color-white)",
    "colors.textPrimary": "Main text (--sf-color-text)",
    "colors.textSecondary": "Muted text",
    "typography.headingFont": "Headings, store name (--sf-font-display)",
    "typography.bodyFont": "Body copy (--sf-font-sans)",
    "typography.scale": "Text size compact/standard/generous",
    "typography.headingStyle": "italic on headings + store name",
    "typography.bodyStyle": "italic on body text site-wide",
    "hero.overlay": "Banner scrim: none|lightScrim|autoScrim|darkScrim",
    "hero.logoPlacement": "left|center|right",
    "hero.storeNameStyle": "subtle|balanced|bold — #sf-name only",
    "productCards.layout": "grid2|grid3|list on .sf-products",
    "productCards.shape": "rounded|sharp|circularImage",
    "productCards.priceStyle": "boldRed|accentColor|understatedGrey|badgePill",
    "buttons.shape": "sharp|rounded|pill on Follow + coupon + catalogue CTAs",
    "buttons.style": "filled|outlined|soft|ghost",
    "geometry.borderRadiusPreset": "Global corner radius",
    "geometry.spacingPreset": "Section/card spacing",
}

# Worked examples: merchant prompt → tools → what changes in preview
AGENT_PLAYBOOK_EXAMPLES: list[dict[str, Any]] = [
    {
        "merchant_says": "make the background pink for the complete storefront",
        "steps": [
            "get_storefront_page_context() — confirm Z1 colours",
            "apply_style_tokens(background_color=<pink hex>, surface_color=<same hex>, clear_zone_color_overrides=true)",
        ],
        "preview_result": "Hero band, intro, offers gap, product sections, footer panels all pink; text contrast auto-adjusted",
        "response_type": "applied",
    },
    {
        "merchant_says": "make all the text italic",
        "steps": [
            "apply_style_tokens(heading_style=italic, body_style=italic)",
        ],
        "preview_result": "Intro, store info, hours, product titles use italic",
        "response_type": "applied",
    },
    {
        "merchant_says": "pill buttons and dark hero scrim",
        "steps": [
            "apply_style_tokens(button_shape=pill, hero_overlay=darkScrim)",
        ],
        "preview_result": "Follow/coupon buttons pill-shaped; banner darker overlay",
        "response_type": "applied",
    },
    {
        "merchant_says": "three column products and teal price colour",
        "steps": [
            "apply_style_tokens(product_card_layout=grid3)",
            "apply_zone_tour_choice on Z4 price sub-step OR apply_style_tokens if scoped accent available",
        ],
        "preview_result": "Product grids 3 columns; price accent in both product sections",
        "response_type": "applied",
    },
    {
        "merchant_says": "I like Tuscan Workshop",
        "steps": [
            "apply_theme_package or save_theme with package colours/fonts",
            "Tour may auto-start — use get_zone_tour_status, let server show swatches",
        ],
        "preview_result": "Full new palette + fonts; then zone tour refines each area",
        "response_type": "applied",
    },
    {
        "merchant_says": "bold store name only, keep body normal",
        "steps": [
            "apply_style_tokens(store_name_style=bold)",
            "Do NOT set body_style unless they asked for all text",
        ],
        "preview_result": "Only #sf-name in hero gets heavier weight",
        "response_type": "applied",
    },
]

TOOL_SELECTION_GUIDE: dict[str, str] = {
    "get_storefront_page_context": "FIRST for ambiguous, whole-page, or multi-zone requests — returns layout, tokens, tour, examples",
    "apply_style_tokens": "Immediate single or multi token change (hero, buttons, cards, fonts, page background)",
    "apply_zone_tour_choice": "During active tour — one swatch/preset for current sub-step",
    "save_theme / apply_theme_package": "Initial full theme from discovery (resets zoneScopes)",
    "generate_color_palette": "Discovery only — building theme packages",
    "get_zone_tour_status": "During tour — where we are in Brand Colours → … → CTAs",
    "complete_zone_tour_step": "After finishing ALL sub-steps in one zone",
    "acknowledge_offers_zone": "Z5 info-only — no layout changes",
}


def build_storefront_blueprint() -> dict[str, Any]:
    """Static blueprint the agent can rely on every session."""
    return {
        "layout_fixed": True,
        "page_layout_scroll_order": PAGE_LAYOUT,
        "theme_application_flow": THEME_APPLICATION_FLOW,
        "token_to_preview_mapping": TOKEN_TO_PREVIEW,
        "tool_selection_guide": TOOL_SELECTION_GUIDE,
        "playbook_examples": AGENT_PLAYBOOK_EXAMPLES,
        "colour_scoping_rules": [
            "Z1 / save_theme: tokens.colors = global brand (primary, accent, background, surface, text).",
            "zoneScopes.Z2–Z6: colours ONLY inside that zone's DOM (see page_layout).",
            "Full-page background: background + surface BOTH same hex, clear_zone_color_overrides=true.",
            "Hero store name bold ≠ all text bold — use hero.storeNameStyle only.",
        ],
    }
