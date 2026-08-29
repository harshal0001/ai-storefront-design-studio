"""Shared design constants — contrast math, WCAG thresholds, Google Fonts whitelist.

Fonts are loaded once from ``fonts.json`` at import time. Used by ``color_engine``,
``token_mapper``, and agent colour tools.
"""

import json
from pathlib import Path

# Base colors for text contrast
WHITE = "#FFFFFF"
BLACK = "#000000"

# Text color adjustments (how much to lighten/darken for secondary text)
SECONDARY_TEXT_DARKEN = 0.35  # For light text on dark bg
SECONDARY_TEXT_LIGHTEN = 0.45  # For dark text on light bg

# Accessibility thresholds (WCAG 2.1)
WCAG_AA_RATIO = 4.5
WCAG_AAA_RATIO = 7.0

# Google Fonts - loaded from fonts.json
_FONTS_FILE = Path(__file__).parent.parent / "fonts.json"


def _load_font_data() -> dict[str, list[str]]:
    """Load fonts grouped by category from fonts.json (single read)."""
    try:
        with open(_FONTS_FILE) as f:
            data = json.load(f)
        return data.get("fonts", {})
    except FileNotFoundError:
        return {}


GOOGLE_FONTS_BY_CATEGORY = _load_font_data()
GOOGLE_FONTS = [f for fonts in GOOGLE_FONTS_BY_CATEGORY.values() for f in fonts]
