"""Domain models for storefront customization (legacy config path).

``StorefrontConfig`` + ``Zone`` / ``ZoneStyle`` dataclasses power the older
``customize_zone`` tool and ``token_mapper`` bridge. New persistence uses
``style_tokens.StyleTokens`` (DynamoDB). Structured LLM output models live in
``response_models.py``.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Zone(str, Enum):
    """Fixed storefront zones in display order."""

    HERO_BANNER = "hero_banner"
    STORE_LOGO = "store_logo"
    STORE_HEADER = "store_header"
    STORE_DESCRIPTION = "store_description"
    CONTACT_ICONS = "contact_icons"
    ADDRESS_BAR = "address_bar"
    BUSINESS_HOURS = "business_hours"
    FOLLOW_BUTTON = "follow_button"
    AD_BANNER = "ad_banner"
    OFFERS_CAROUSEL = "offers_carousel"
    PRODUCTS_GRID = "products_grid"
    MARKET_SECTION = "market_section"


ZONE_DISPLAY_NAMES = {
    Zone.HERO_BANNER: "Hero Banner",
    Zone.STORE_LOGO: "Store Logo",
    Zone.STORE_HEADER: "Store Name",
    Zone.STORE_DESCRIPTION: "Description & Tags",
    Zone.CONTACT_ICONS: "Contact Buttons",
    Zone.ADDRESS_BAR: "Address Bar",
    Zone.BUSINESS_HOURS: "Business Hours",
    Zone.FOLLOW_BUTTON: "Follow Button",
    Zone.AD_BANNER: "Announcement Card",
    Zone.OFFERS_CAROUSEL: "Offers Section",
    Zone.PRODUCTS_GRID: "Products Grid",
    Zone.MARKET_SECTION: "Market Background",
}


class BorderRadius(str, Enum):
    """Preset border radius options."""

    SHARP = "sharp"
    SOFT = "soft"
    ROUNDED = "rounded"
    PILL = "pill"


class Spacing(str, Enum):
    """Spacing presets (tight guardrails per CPO)."""

    COMPACT = "compact"
    NORMAL = "normal"
    SPACIOUS = "spacious"


@dataclass
class ZoneStyle:
    """Style overrides for a single zone."""

    primary_color: Optional[str] = None
    background_color: Optional[str] = None
    border_radius: Optional[BorderRadius] = None


@dataclass
class StorefrontConfig:
    """Complete storefront configuration — populated by save_theme tool."""

    theme_name: str = ""
    theme_description: str = ""
    mood_summary: str = ""

    # Colors (hex + creative name)
    primary_color: str = ""
    primary_color_name: str = ""
    secondary_color: str = ""
    secondary_color_name: str = ""
    accent_color: str = ""
    accent_color_name: str = ""
    background_color: str = ""
    background_color_name: str = ""
    surface_color: str = ""
    surface_color_name: str = ""

    # Auto-calculated from background
    text_primary: str = ""
    text_secondary: str = ""

    # Typography
    heading_font: str = ""
    body_font: str = ""

    # Style
    default_border_radius: BorderRadius = BorderRadius.ROUNDED
    default_spacing: Spacing = Spacing.NORMAL

    # Per-zone overrides
    zone_overrides: dict[Zone, ZoneStyle] = field(default_factory=dict)
