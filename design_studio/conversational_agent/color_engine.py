"""Color engine combining coloraide's color science with validation helpers.

Provides palette generation (harmonies), hex normalization, WCAG contrast checks,
and Google Font name validation. Used by agent tools and ``token_mapper``.
"""

import re

from coloraide import Color
from typing import Literal

from .constants import (
    WHITE,
    BLACK,
    WCAG_AA_RATIO,
    WCAG_AAA_RATIO,
    GOOGLE_FONTS,
)


HarmonyType = Literal["analogous", "complement", "triad", "split", "square", "mono"]


HARMONY_DESCRIPTIONS = {
    "analogous": "colors that sit next to each other on the color wheel — harmonious and serene",
    "complement": "opposite colors that create vibrant contrast",
    "triad": "three colors equally spaced — balanced and dynamic",
    "split": "a color plus the two colors adjacent to its complement — subtle contrast",
    "square": "four colors equally spaced — rich and varied",
    "mono": "variations of a single hue — elegant and cohesive",
}


def generate_palette_from_seed(
    seed_hex: str,
    harmony: HarmonyType = "analogous",
    count: int = 5,
) -> list[str]:
    """Generate a color palette from a seed color using color theory."""
    seed = Color(seed_hex)

    if harmony == "mono":
        colors = _generate_monochromatic(seed, count)
    else:
        colors = list(seed.harmony(harmony))

    hex_colors = [c.convert("srgb").clip().to_string(hex=True) for c in colors]

    if len(hex_colors) < count:
        hex_colors = _expand_palette(hex_colors, count)

    return hex_colors[:count]


def _generate_monochromatic(seed: Color, count: int) -> list[Color]:
    """Generate monochromatic variations of a color."""
    colors = []
    oklch = seed.convert("oklch")

    steps = [0.3, 0.45, 0.6, 0.75, 0.9][:count]
    for lightness in steps:
        c = oklch.clone()
        c["lightness"] = lightness
        colors.append(c)

    return colors


def _expand_palette(colors: list[str], target: int) -> list[str]:
    """Expand a palette by adding lighter/darker variations."""
    result = list(colors)

    while len(result) < target:
        before = len(result)
        for hex_color in colors:
            if len(result) >= target:
                break
            c = Color(hex_color).convert("oklch")
            c["lightness"] = min(0.95, c["lightness"] + 0.15)
            new_hex = c.convert("srgb").clip().to_string(hex=True)
            if new_hex not in result:
                result.append(new_hex)
        if len(result) == before:
            # Lightness has saturated and every variant is a duplicate —
            # caller will truncate to `target` and accept fewer colors.
            break

    return result


def get_contrast_color(hex_color: str) -> str:
    """Get the best contrast color (black or white) for text on this background."""
    color = Color(hex_color)
    white = Color(WHITE)
    black = Color(BLACK)

    white_contrast = color.contrast(white, method="wcag21")
    black_contrast = color.contrast(black, method="wcag21")

    return WHITE if white_contrast > black_contrast else BLACK


def check_contrast_ratio(color1: str, color2: str) -> float:
    """Check WCAG 2.1 contrast ratio between two colors."""
    c1 = Color(color1)
    c2 = Color(color2)
    return c1.contrast(c2, method="wcag21")


def is_accessible(foreground: str, background: str, level: str = "AA") -> bool:
    """Check if color combination meets WCAG accessibility standards."""
    ratio = check_contrast_ratio(foreground, background)
    threshold = WCAG_AAA_RATIO if level == "AAA" else WCAG_AA_RATIO
    return ratio >= threshold


def adjust_for_contrast(
    color: str,
    background: str,
    min_ratio: float = WCAG_AA_RATIO,
) -> str:
    """Adjust a color to meet minimum contrast ratio against a background."""
    c = Color(color).convert("oklch")
    bg = Color(background)

    current_ratio = c.convert("srgb").contrast(bg, method="wcag21")

    if current_ratio >= min_ratio:
        return color

    bg_lightness = bg.convert("oklch")["lightness"]
    direction = -1 if bg_lightness > 0.5 else 1

    for _ in range(20):
        c["lightness"] = max(0, min(1, c["lightness"] + direction * 0.05))
        current_ratio = c.convert("srgb").clip().contrast(bg, method="wcag21")
        if current_ratio >= min_ratio:
            break

    return c.convert("srgb").clip().to_string(hex=True)


def blend_colors(color1: str, color2: str, ratio: float = 0.5) -> str:
    """Blend two colors together."""
    c1 = Color(color1)
    c2 = Color(color2)
    blended = c1.interpolate(c2, space="oklch")(ratio)
    return blended.convert("srgb").clip().to_string(hex=True)


def get_lighter(hex_color: str, amount: float = 0.1) -> str:
    """Get a lighter version of a color."""
    c = Color(hex_color).convert("oklch")
    c["lightness"] = min(0.98, c["lightness"] + amount)
    return c.convert("srgb").clip().to_string(hex=True)


def get_darker(hex_color: str, amount: float = 0.1) -> str:
    """Get a darker version of a color."""
    c = Color(hex_color).convert("oklch")
    c["lightness"] = max(0.02, c["lightness"] - amount)
    return c.convert("srgb").clip().to_string(hex=True)


def is_valid_color(color: str) -> bool:
    """Return True if coloraide can parse this (hex, CSS name, hsl, etc.)."""
    try:
        Color(color)
        return True
    except Exception:
        return False


def is_hex_format(value: str) -> bool:
    """Return True only for #RGB, #RRGGBB, or #RRGGBBAA strings."""
    return bool(re.fullmatch(r"#[0-9a-fA-F]{3,8}", value))


# Keep backward-compatible alias during transition
validate_hex = is_valid_color


def normalize_hex(hex_color: str) -> str:
    """Normalize a hex color to standard format (#RRGGBB)."""
    try:
        return Color(hex_color).convert("srgb").to_string(hex=True)
    except Exception:
        return hex_color


def is_valid_google_font(font_name: str) -> bool:
    """Check if a font name is in our Google Fonts list."""
    return font_name in GOOGLE_FONTS


def friendly_color_name(hex_color: str) -> str:
    """Human-readable colour label for chat copy (never show raw hex to merchants)."""
    try:
        h = normalize_hex(hex_color)
        hue, sat, light = Color(h).convert("hsl").coords()
        hue = float(hue) % 360
        sat = float(sat)
        light = float(light)
    except Exception:
        return "Custom colour"

    if sat < 0.08:
        if light > 0.92:
            return "Soft white"
        if light < 0.12:
            return "Deep black"
        if light > 0.7:
            return "Light grey"
        if light < 0.35:
            return "Charcoal"
        return "Stone grey"

    if light > 0.85:
        prefix = "Pale "
    elif light > 0.65:
        prefix = "Light "
    elif light < 0.25:
        prefix = "Deep "
    elif light < 0.4:
        prefix = "Dark "
    else:
        prefix = ""

    if hue < 15 or hue >= 345:
        base = "Crimson" if sat > 0.55 else "Rose"
    elif hue < 45:
        base = "Amber" if light < 0.55 else "Peach"
    elif hue < 70:
        base = "Gold"
    elif hue < 150:
        base = "Sage" if sat < 0.45 else "Green"
    elif hue < 190:
        base = "Teal"
    elif hue < 220:
        base = "Ocean blue"
    elif hue < 260:
        base = "Indigo"
    elif hue < 300:
        base = "Plum"
    else:
        base = "Berry"

    return f"{prefix}{base}".strip()
