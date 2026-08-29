"""Canonical zone tour presets — injected by the API (not LLM structured output).

``ZONE_TOUR_PRESETS`` lists layout/style choices per zone (hero layout, card style, …).
``zone_options_for_code()`` returns the batch for the current tour sub-step.
"""

from __future__ import annotations

from typing import Any

# Each preset: id (for apply_zone_tour_choice), name, description (UI + agent context)
ZONE_TOUR_PRESETS: dict[str, list[dict[str, str]]] = {
    "Z2": [
        {
            "id": "classic_center",
            "name": "Classic centered",
            "description": "Applies to: banner layout, logo & tagline — centered classic look.",
        },
        {
            "id": "modern_left",
            "name": "Modern left",
            "description": "Applies to: banner layout, logo left, tagline bottom-left.",
        },
        {
            "id": "bold_dark",
            "name": "Bold & dramatic",
            "description": "Applies to: dark banner scrim, centered logo, bold store name.",
        },
        {
            "id": "minimal_clean",
            "name": "Minimal clean",
            "description": "Applies to: banner with no scrim, logo right, subtle store name.",
        },
        {
            "id": "split_hero",
            "name": "Split image & text",
            "description": "Applies to: half-width banner photo with text beside it — editorial layout.",
        },
        {
            "id": "carousel_hero",
            "name": "Carousel hero",
            "description": "Applies to: rotating banner slides with dots — dynamic storefront entrance.",
        },
        {
            "id": "editorial_tagline",
            "name": "Editorial tagline",
            "description": "Applies to: bottom-right tagline, light scrim, refined store name plate.",
        },
        {
            "id": "logo_forward",
            "name": "Logo forward",
            "description": "Applies to: prominent left logo, minimal scrim, confident store name.",
        },
    ],
    "Z3": [
        {
            "id": "elegant_serif",
            "name": "Elegant serif",
            "description": "Applies to: headings & body text in intro and store info.",
        },
        {
            "id": "modern_sans",
            "name": "Modern sans",
            "description": "Applies to: headings & body text in intro and store info.",
        },
        {
            "id": "friendly_rounded",
            "name": "Friendly & open",
            "description": "Applies to: headings & body text in intro and store info.",
        },
        {
            "id": "compact_pro",
            "name": "Compact pro",
            "description": "Applies to: tight Inter headings & body in intro and store info.",
        },
    ],
    "Z4": [
        {
            "id": "soft_grid",
            "name": "Soft two-column grid",
            "description": "Rounded cards in a **two-column grid** with gentle shadows — calm and easy to browse.",
        },
        {
            "id": "bold_grid",
            "name": "Bold elevated grid",
            "description": "Two columns with **stronger lift and shadow** — products feel prominent and tactile.",
        },
        {
            "id": "grid_three",
            "name": "Three-column grid",
            "description": "Compact **three-across grid** — more products visible without scrolling.",
        },
        {
            "id": "list_view",
            "name": "List layout",
            "description": "**Horizontal rows** (image + details) — great for comparing items quickly.",
        },
        {
            "id": "featured_mix",
            "name": "Featured hero + grid",
            "description": "One **large featured tile** beside a grid — editorial, boutique-style merchandising.",
        },
        {
            "id": "sharp_minimal",
            "name": "Sharp minimal grid",
            "description": "**Square corners**, flat shadows, two columns — crisp gallery-like tiles.",
        },
        {
            "id": "floating_cards",
            "name": "Floating cards",
            "description": "Three columns with **floating shadows** — light, premium, magazine feel.",
        },
        {
            "id": "airy_list",
            "name": "Airy list rows",
            "description": "Spacious **list rows** with soft depth — readable and modern on mobile.",
        },
    ],
    "Z6": [
        {
            "id": "friendly_rounded",
            "name": "Friendly rounded",
            "description": "**Rounded filled** buttons with a gentle press scale — approachable and warm.",
        },
        {
            "id": "minimal_sharp",
            "name": "Minimal sharp",
            "description": "**Square outlined** Follow & coupon buttons — crisp and understated.",
        },
        {
            "id": "pill_cta",
            "name": "Pill CTAs",
            "description": "**Pill-shaped filled** buttons — modern and easy to tap on mobile.",
        },
        {
            "id": "soft_ghost",
            "name": "Soft ghost",
            "description": "**Soft ghost** buttons — light fill, minimal visual weight.",
        },
        {
            "id": "pill_ghost",
            "name": "Pill ghost",
            "description": "**Pill outline ghost** style — trendy, low-contrast CTAs.",
        },
        {
            "id": "large_filled",
            "name": "Large filled CTAs",
            "description": "**Bigger filled** buttons — bold tap targets for Follow & coupons.",
        },
        {
            "id": "outlined_rounded",
            "name": "Outlined rounded",
            "description": "**Rounded outlined** buttons with a darken press — clean boutique feel.",
        },
        {
            "id": "compact_pill",
            "name": "Compact pills",
            "description": "**Smaller pill** buttons — dense layout, still finger-friendly.",
        },
        {
            "id": "soft_outlined",
            "name": "Soft outlined",
            "description": "**Soft outlined** style on rounded shapes — subtle, editorial.",
        },
        {
            "id": "bold_ripple",
            "name": "Bold ripple",
            "description": "**Filled rounded** buttons with ripple feedback — energetic and premium.",
        },
    ],
}


def zone_options_for_code(zone_code: str | None) -> list[dict[str, Any]]:
    if not zone_code:
        return []
    return list(ZONE_TOUR_PRESETS.get(zone_code.upper(), []))
