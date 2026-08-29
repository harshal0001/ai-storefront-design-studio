#!/usr/bin/env python3
"""Seed ThemePackage with starter themes (CF-02)."""

from __future__ import annotations

import os
import sys

# Allow running from design_studio/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conversational_agent.style_repository import StyleRepository
from conversational_agent.style_tokens import StyleTokens


def _pkg(
    package_id: str,
    display_name: str,
    description: str,
    mood_match: list[str],
    tokens: StyleTokens,
) -> dict:
    return {
        "packageId": package_id,
        "displayName": display_name,
        "description": description,
        "moodMatch": mood_match,
        "previewImageUrl": f"https://static.example.com/packages/{package_id}.png",
        "active": True,
        "updatedAt": "2026-05-20T08:00:00Z",
        "tokens": tokens.to_ddb_map(),
    }


PACKAGES = [
    _pkg(
        "tuscan_workshop",
        "Tuscan Workshop",
        "Warm ivory background, earthy palette, rounded cards, friendly fonts.",
        ["warm", "rustic", "artisan", "cozy"],
        StyleTokens.model_validate(
            {
                "colors": {
                    "primary": "#A86B3F",
                    "accent": "#7A4A1E",
                    "secondary": "#2C2419",
                    "background": "#FBF6EE",
                    "surface": "#FFFFFF",
                    "textPrimary": "#2C2419",
                    "textSecondary": "#6E5A41",
                    "danger": "#D72F4D",
                    "warn": "#C34F03",
                    "success": "#0A600A",
                    "paletteName": "Tuscan Earth",
                    "harmonyChecked": True,
                    "contrastAA": True,
                },
                "typography": {
                    "headingFont": "Playfair Display",
                    "bodyFont": "Lora",
                    "scale": "standard",
                    "pairingName": "Classic Duo",
                },
                "geometry": {"borderRadiusPreset": "rounded", "spacingPreset": "normal"},
                "hero": {
                    "layout": "fullWidth",
                    "overlay": "lightScrim",
                    "logoPlacement": "center",
                    "taglinePlacement": "center",
                    "storeNameStyle": "balanced",
                },
                "productCards": {
                    "shape": "rounded",
                    "layout": "grid2",
                    "shadow": "subtle",
                    "priceStyle": "understatedGrey",
                    "tapAnimation": "scaleDown",
                },
                "offerCards": {
                    "merchantCanCustomise": False,
                    "imageBeautification": {"filterPreset": "warm"},
                },
                "buttons": {
                    "shape": "subtleRounded",
                    "style": "filled",
                    "size": "standard",
                    "pressAnimation": "darken",
                },
                "motion": {"transition": "fadeTint"},
            }
        ),
    ),
    _pkg(
        "modern_minimalist",
        "Modern Minimalist",
        "Clean lines, cool neutrals, sharp cards, confident sans-serif type.",
        ["modern", "minimal", "sleek", "professional"],
        StyleTokens.model_validate(
            {
                "colors": {
                    "primary": "#1A1A2E",
                    "accent": "#4A90D9",
                    "secondary": "#16213E",
                    "background": "#F5F7FA",
                    "surface": "#FFFFFF",
                    "textPrimary": "#1A1A2E",
                    "textSecondary": "#5F6E7D",
                    "paletteName": "Nordic Calm",
                    "harmonyChecked": True,
                    "contrastAA": True,
                },
                "typography": {
                    "headingFont": "Montserrat",
                    "bodyFont": "Roboto",
                    "scale": "standard",
                    "pairingName": "Modern Pair",
                },
                "geometry": {"borderRadiusPreset": "soft", "spacingPreset": "normal"},
                "hero": {
                    "layout": "fullWidth",
                    "overlay": "autoScrim",
                    "logoPlacement": "left",
                    "taglinePlacement": "bottomLeft",
                    "storeNameStyle": "bold",
                },
                "productCards": {
                    "shape": "sharp",
                    "layout": "grid2",
                    "shadow": "flat",
                    "priceStyle": "accentColor",
                    "tapAnimation": "none",
                },
                "buttons": {
                    "shape": "rounded",
                    "style": "filled",
                    "size": "standard",
                    "pressAnimation": "scale",
                },
                "motion": {"transition": "none"},
            }
        ),
    ),
    _pkg(
        "bold_and_bright",
        "Bold & Bright",
        "Vibrant primaries, playful shapes, high energy for eye-catching promos.",
        ["bold", "playful", "energetic", "fun"],
        StyleTokens.model_validate(
            {
                "colors": {
                    "primary": "#E63946",
                    "accent": "#F4A261",
                    "secondary": "#2A9D8F",
                    "background": "#FFF8F0",
                    "surface": "#FFFFFF",
                    "textPrimary": "#1D3557",
                    "textSecondary": "#457B9D",
                    "paletteName": "Fiesta Pop",
                    "harmonyChecked": True,
                    "contrastAA": True,
                },
                "typography": {
                    "headingFont": "Poppins",
                    "bodyFont": "Open Sans",
                    "scale": "generous",
                    "pairingName": "Playful Pop",
                },
                "geometry": {"borderRadiusPreset": "pill", "spacingPreset": "spacious"},
                "hero": {
                    "layout": "fullWidth",
                    "overlay": "darkScrim",
                    "logoPlacement": "right",
                    "taglinePlacement": "center",
                    "storeNameStyle": "bold",
                },
                "productCards": {
                    "shape": "rounded",
                    "layout": "grid2",
                    "shadow": "elevated",
                    "priceStyle": "boldRed",
                    "tapAnimation": "ripple",
                },
                "buttons": {
                    "shape": "pill",
                    "style": "filled",
                    "size": "large",
                    "pressAnimation": "ripple",
                },
                "motion": {"transition": "slideTint"},
            }
        ),
    ),
]


def main() -> None:
    repo = StyleRepository()
    if not repo.enabled:
        print("ERROR: Set USE_DYNAMODB=true before seeding theme packages.", file=sys.stderr)
        sys.exit(1)

    for pkg in PACKAGES:
        repo.package_table.put_item(Item=pkg)
        print(f"Seeded {pkg['packageId']}: {pkg['displayName']}")

    repo.clear_theme_package_cache()
    print(f"\nDone. {len(PACKAGES)} packages in {repo.package_table_name}.")


if __name__ == "__main__":
    main()
