"""Section + element focus for chat — zones, sub-elements, preview click, text detection.

Merchants pick a **section** (Hero, Our Products, …) or **element** (catalog card, logo)
via UI chips or preview click. ``merge_focus()`` combines explicit UI focus with
regex detection from the message. ``highlight_selectors_for_focus()`` drives preview outlines.

API field: ``section_focus`` on chat responses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Zone-level sections (parent chips)
SECTION_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "hero",
        "zone": "Z2",
        "chip_label": "Hero",
        "label": "Hero & Header",
        "selectors": [".sf-zone--z2"],
        "aliases": (r"\bhero\b", r"\bheader\b", r"\bbanner\b"),
    },
    {
        "id": "intro",
        "zone": "Z3",
        "chip_label": "Intro & text",
        "label": "Store intro & typography",
        "selectors": [".sf-store-intro", ".sf-store-details.sf-zone--z3"],
        "aliases": (r"\bintro\b", r"\btypography\b", r"\bfonts?\b"),
    },
    {
        "id": "offers",
        "zone": "Z5",
        "chip_label": "Offers",
        "label": "Offers",
        "selectors": [".sf-zone--z5"],
        "aliases": (r"\boffers?\b", r"\bcoupons?\b"),
    },
    {
        "id": "showcase",
        "zone": "Z4S",
        "chip_label": "Our Products",
        "label": "Our Products",
        "selectors": [".sf-zone--z4-showcase"],
        "aliases": (r"\bour\s+products\b", r"\bshowcase\b"),
    },
    {
        "id": "catalog",
        "zone": "Z4C",
        "chip_label": "All Products",
        "label": "All Products & Services",
        "selectors": [".sf-zone--z4-catalog"],
        "aliases": (
            r"\ball\s+products?\s*(?:&\s*services)?\b",
            r"\bproducts?\s*&\s*services\b",
        ),
    },
    {
        "id": "buttons",
        "zone": "Z6",
        "chip_label": "Buttons",
        "label": "Buttons & CTAs",
        "selectors": [
            ".sf-follow__btn",
            ".sf-coupon__btn",
            ".sf-products-catalogue",
            ".sf-directions__btn",
        ],
        "aliases": (r"\bbuttons?\b", r"\bcta\b"),
    },
    {
        "id": "brand",
        "zone": "Z1",
        "chip_label": "Brand colours",
        "label": "Brand Colours",
        "selectors": [".sf-follow", "#sf-offers-section", "#sf-products-section"],
        "aliases": (r"\bbrand\s+colou?rs?\b", r"\bpage\s+background\b"),
    },
)

# Individual elements inside zones (sub-chips + precise preview click)
ELEMENT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    # Z2 Hero
    {
        "id": "hero_banner",
        "section_id": "hero",
        "zone": "Z2",
        "chip_label": "Banner photo",
        "label": "Hero banner photo",
        "selectors": [".sf-banner__media", ".sf-banner__img"],
        "aliases": (r"\bbanner\s+photo\b", r"\bhero\s+image\b", r"\bbanner\b"),
        "agent_hint": "hero_overlay, hero_layout — scrim and banner layout only.",
    },
    {
        "id": "hero_logo",
        "section_id": "hero",
        "zone": "Z2",
        "chip_label": "Logo",
        "label": "Logo on hero",
        "selectors": [".sf-banner__logo-wrap", "#sf-logo"],
        "aliases": (r"\blogo\b", r"\blogo\s+placement\b"),
        "agent_hint": "logo_placement: left, center, or right.",
    },
    {
        "id": "hero_store_name",
        "section_id": "hero",
        "zone": "Z2",
        "chip_label": "Store name",
        "label": "Store name & tagline",
        "selectors": ["#sf-name", ".sf-hero-tagline", ".sf-info.sf-info--hero"],
        "aliases": (r"\bstore\s+name\b", r"\btagline\b", r"\bhero\s+text\b"),
        "agent_hint": (
            "Store name plate background: apply_zone_tour_choice(zone_code=Z2, surface_color=#hex) "
            "or apply_style_tokens(zone_code=Z2, surface_color=#hex). "
            "Do NOT use background_color without zone_code — that repaints the whole page."
        ),
    },
    # Z3 Typography / intro
    {
        "id": "intro_copy",
        "section_id": "intro",
        "zone": "Z3",
        "chip_label": "Intro text",
        "label": "Store introduction",
        "selectors": [".sf-store-intro", "#sf-description"],
        "aliases": (r"\bintro\b", r"\bdescription\b", r"\babout\s+text\b"),
        "agent_hint": "heading_font, body_font, heading_style, body_style for intro copy.",
    },
    {
        "id": "store_details",
        "section_id": "intro",
        "zone": "Z3",
        "chip_label": "Store info",
        "label": "Store information & hours",
        "selectors": [".sf-store-details", ".sf-hours-section"],
        "aliases": (r"\bstore\s+information\b", r"\bhours\b", r"\baddress\b", r"\bphone\b"),
        "agent_hint": "Typography tokens for store details block.",
    },
    # Z5
    {
        "id": "offer_carousel",
        "section_id": "offers",
        "zone": "Z5",
        "chip_label": "Coupon cards",
        "label": "Offer / coupon carousel",
        "selectors": ["#sf-offers-section", ".sf-coupon-list", ".sf-coupon"],
        "aliases": (r"\boffers?\b", r"\bcoupons?\b", r"\bdeal\b"),
        "agent_hint": "Offers layout is fixed; only offer_filter_preset for images.",
    },
    # Z4S
    {
        "id": "showcase_cards",
        "section_id": "showcase",
        "zone": "Z4S",
        "chip_label": "Carousel cards",
        "label": "Our Products carousel cards",
        "selectors": [".sf-showcase-card", ".sf-showcase"],
        "aliases": (r"\bshowcase\b", r"\bcarousel\b", r"\bour\s+products\b"),
        "agent_hint": "productCards.* shapes layout for showcase carousel.",
    },
    # Z4C — catalogue (most specific merchant requests)
    {
        "id": "catalog_cards",
        "section_id": "catalog",
        "zone": "Z4C",
        "chip_label": "Product cards",
        "label": "Product cards grid",
        "selectors": ["#sf-products-section .sf-product", "#sf-products-section .sf-products"],
        "aliases": (
            r"\bproduct\s+cards?\b",
            r"\bproduct\s+grid\b",
            r"\brectangle\b",
            r"\brectangular\b",
            r"\bcards?\s+look\b",
        ),
        "agent_hint": (
            "product_card_shape=rounded or sharp (NOT circularImage), "
            "product_card_layout, product_card_shadow — merchant means this grid."
        ),
    },
    {
        "id": "catalog_filters",
        "section_id": "catalog",
        "zone": "Z4C",
        "chip_label": "Category tabs",
        "label": "Product category filters",
        "selectors": [".sf-product-filters", ".sf-product-filter"],
        "aliases": (r"\bfilters?\b", r"\bcategories\b", r"\btabs\b"),
        "agent_hint": "Filter chip styling inherits section colours.",
    },
    {
        "id": "catalogue_button",
        "section_id": "catalog",
        "zone": "Z4C",
        "chip_label": "Catalogue button",
        "label": "View full catalogue button",
        "selectors": [".sf-products-catalogue", "#sf-products-catalogue"],
        "aliases": (r"\bview\s+full\s+catalogue\b", r"\bcatalogue\s+button\b"),
        "agent_hint": "buttons.shape, buttons.style for catalogue CTA.",
    },
    # Z6
    {
        "id": "follow_button",
        "section_id": "buttons",
        "zone": "Z6",
        "chip_label": "Follow button",
        "label": "Follow button",
        "selectors": [".sf-follow__btn", ".sf-follow.sf-zone--z6"],
        "aliases": (r"\bfollow\s+button\b", r"\bfollow\b"),
        "agent_hint": "button_shape, button_style, button_size.",
    },
    {
        "id": "directions_button",
        "section_id": "buttons",
        "zone": "Z6",
        "chip_label": "Directions",
        "label": "Get Directions button",
        "selectors": [".sf-directions__btn", ".sf-directions"],
        "aliases": (r"\bdirections\b", r"\bget\s+directions\b", r"\bfooter\s+button\b"),
        "agent_hint": "buttons.* for footer CTA.",
    },
    # Z1 brand (colour targets)
    {
        "id": "brand_follow_colour",
        "section_id": "brand",
        "zone": "Z1",
        "chip_label": "Follow colour",
        "label": "Follow button brand colour",
        "selectors": [".sf-follow__btn"],
        "aliases": (r"\bfollow\s+colou?r\b", r"\bprimary\s+colou?r\b", r"\baccent\b"),
        "agent_hint": "colors.primary, colors.accent.",
    },
    {
        "id": "page_backdrop",
        "section_id": "brand",
        "zone": "Z1",
        "chip_label": "Page backdrop",
        "label": "Page background",
        "selectors": [
            "#sf-offers-section",
            "#sf-showcase-section",
            "#sf-products-section",
            ".sf-store-intro",
        ],
        "aliases": (r"\bpage\s+background\b", r"\bbackdrop\b", r"\bbehind\s+everything\b"),
        "agent_hint": "background_color + surface_color + clear_zone_color_overrides.",
    },
)

_SECTION_BY_ID = {s["id"]: s for s in SECTION_DEFINITIONS}
_ZONE_BY_CODE = {s["zone"]: s for s in SECTION_DEFINITIONS}
_ELEMENT_BY_ID = {e["id"]: e for e in ELEMENT_DEFINITIONS}
# Nested element chips grouped by parent section for GET /api/sections
_ELEMENTS_BY_SECTION = {}
for _e in ELEMENT_DEFINITIONS:
    _ELEMENTS_BY_SECTION.setdefault(_e["section_id"], []).append(_e)


@dataclass(frozen=True)
class SectionFocus:
    """Resolved focus for one chat turn — drives preview highlight + agent scoping."""

    zone: str  # Z1–Z6 or Z4S / Z4C product sub-zones
    label: str  # Parent section label shown in UI
    section_id: str  # Stable id from SECTION_DEFINITIONS (e.g. "catalog")
    source: str  # "chip" | "explicit" | "text" — how focus was determined
    selectors: tuple[str, ...]  # CSS selectors for preview outline
    element_id: str | None = None  # Sub-element when merchant clicked a precise target
    element_label: str | None = None

    @property
    def display_label(self) -> str:
        if self.element_label:
            return f"{self.element_label} · {self.label}"
        return self.label

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "zone": self.zone,
            "sectionId": self.section_id,
            "elementId": self.element_id,
            "label": self.label,
            "elementLabel": self.element_label,
            "displayLabel": self.display_label,
            "source": self.source,
            "highlight_selectors": list(self.selectors),
        }


def list_sections_for_ui() -> list[dict[str, Any]]:
    """Zone chips with nested element chips for the chat panel."""
    out: list[dict[str, Any]] = []
    for sec in SECTION_DEFINITIONS:
        row = {
            "id": sec["id"],
            "zone": sec["zone"],
            "chipLabel": sec["chip_label"],
            "label": sec["label"],
            "elements": [
                {
                    "id": el["id"],
                    "sectionId": el["section_id"],
                    "zone": el["zone"],
                    "chipLabel": el["chip_label"],
                    "label": el["label"],
                }
                for el in _ELEMENTS_BY_SECTION.get(sec["id"], [])
            ],
        }
        out.append(row)
    return out


def section_for_zone(zone: str | None) -> dict[str, Any] | None:
    if not zone:
        return None
    return _ZONE_BY_CODE.get(zone.upper())


def element_for_id(element_id: str | None) -> dict[str, Any] | None:
    if not element_id:
        return None
    return _ELEMENT_BY_ID.get(element_id)


def highlight_selectors_for_focus(
    zone: str | None = None,
    element_id: str | None = None,
) -> list[str]:
    """CSS selectors for the preview overlay — element beats zone beats tour default."""
    el = element_for_id(element_id)
    if el:
        return list(el["selectors"])
    if zone:
        sec = section_for_zone(zone)
        if sec:
            return list(sec["selectors"])
        from .zone_highlight import highlight_spec_for_zone_tour

        spec = highlight_spec_for_zone_tour(zone, None)
        return list(spec.selectors)
    return []


def _focus_from_element(el: dict[str, Any], source: str) -> SectionFocus:
    sec = _SECTION_BY_ID.get(el["section_id"], {})
    return SectionFocus(
        zone=el["zone"],
        label=sec.get("label", el["section_id"]),
        section_id=el["section_id"],
        source=source,
        selectors=tuple(el["selectors"]),
        element_id=el["id"],
        element_label=el["label"],
    )


def _focus_from_section(sec: dict[str, Any], source: str) -> SectionFocus:
    return SectionFocus(
        zone=sec["zone"],
        label=sec["label"],
        section_id=sec["id"],
        source=source,
        selectors=tuple(sec["selectors"]),
    )


def resolve_focus_from_text(message: str) -> SectionFocus | None:
    """Detect element first (more specific), then zone."""
    text = message or ""
    if not text.strip():
        return None

    best_el: tuple[int, SectionFocus] | None = None
    for el in ELEMENT_DEFINITIONS:
        score = sum(1 for p in el["aliases"] if re.search(p, text, re.I))
        if score > 0 and (best_el is None or score > best_el[0]):
            best_el = (score, _focus_from_element(el, "text"))

    if best_el:
        return best_el[1]

    best_sec: tuple[int, SectionFocus] | None = None
    for sec in SECTION_DEFINITIONS:
        score = sum(1 for p in sec["aliases"] if re.search(p, text, re.I))
        if score > 0 and (best_sec is None or score > best_sec[0]):
            best_sec = (score, _focus_from_section(sec, "text"))
    return best_sec[1] if best_sec else None


def resolve_focus(
    *,
    focus_zone: str | None = None,
    focus_section_id: str | None = None,
    focus_element_id: str | None = None,
    message: str = "",
) -> SectionFocus | None:
    if focus_element_id:
        el = element_for_id(focus_element_id)
        if el:
            return _focus_from_element(el, "chip")
    if focus_section_id:
        sec = _SECTION_BY_ID.get(focus_section_id)
        if sec:
            return _focus_from_section(sec, "chip")
    if focus_zone:
        sec = section_for_zone(focus_zone)
        if sec:
            return _focus_from_section(sec, "explicit")
    return resolve_focus_from_text(message)


def format_focus_agent_prefix(focus: SectionFocus | None) -> str:
    if not focus:
        return ""
    hint = ""
    if focus.element_id:
        el = element_for_id(focus.element_id)
        if el:
            hint = el.get("agent_hint", "")
    if not hint:
        hints = {
            "Z4C": "All Products & Services section — product card tokens.",
            "Z4S": "Our Products carousel.",
            "Z5": "Offers are mostly fixed.",
            "Z1": "Brand/page colours.",
        }
        hint = hints.get(focus.zone, f"Zone {focus.zone}.")
    return (
        f"[Focus: **{focus.display_label}** (zone {focus.zone}"
        f"{', element ' + focus.element_id if focus.element_id else ''}). "
        f"The preview highlights this exact area. {hint} "
        f"Do not claim changes without calling the right tool.]\n\n"
    )


def merge_focus(
    *,
    focus_zone: str | None = None,
    focus_section_id: str | None = None,
    focus_element_id: str | None = None,
    message: str = "",
) -> SectionFocus | None:
    """Combine explicit UI focus with regex detection from the message.

    Priority: element chip > section chip > focusZone param > text aliases.
    Explicit chips ignore message text so a stale phrase cannot override UI selection.
    """
    explicit = resolve_focus(
        focus_zone=focus_zone,
        focus_section_id=focus_section_id,
        focus_element_id=focus_element_id,
        message="",
    )
    if explicit:
        if focus_element_id:
            el = element_for_id(focus_element_id)
            if el:
                return _focus_from_element(el, "chip")
        if focus_section_id:
            return _focus_from_section(_SECTION_BY_ID[focus_section_id], "chip")
        if focus_zone:
            sec = section_for_zone(focus_zone)
            if sec:
                return _focus_from_section(sec, "explicit")
    return resolve_focus_from_text(message)


# Back-compat alias
def highlight_selectors_for_zone(zone: str | None) -> list[str]:
    return highlight_selectors_for_focus(zone=zone)
