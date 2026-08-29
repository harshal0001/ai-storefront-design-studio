"""Per sub-step preview highlight scope (CF-05).

Brand colours, typography (fonts), and button shape/style are **storefront-wide** — we do
not outline a single iframe region; the chat banner explains that instead.

Section-scoped steps (hero band, product areas, intro panel fill) get precise selectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

HighlightScope = Literal["page", "zone", "element", "none"]

PAGE_WIDE_HINT = (
    "This choice applies **throughout your storefront** — watch the full preview, "
    "not just one section."
)
SECTION_HINT_TEMPLATE = "**{label}** is outlined in the preview →"


@dataclass(frozen=True)
class HighlightSpec:
    scope: HighlightScope
    selectors: tuple[str, ...]
    label: str
    scroll_selector: str | None = None
    merchant_hint: str = ""

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "highlight_scope": self.scope,
            "highlight_label": self.label,
            "highlight_selectors": list(self.selectors),
            "highlight_scroll_selector": self.scroll_selector,
            "highlight_hint": self.merchant_hint,
        }


# Sub-step id → highlight behaviour (aligned with docs/03-zone-customisations.md).
SUB_STEP_HIGHLIGHTS: dict[str, HighlightSpec] = {
    # Z1 — brand colours (storefront-wide; Z1-01 palette, Z1-02 accent, Z1-05 backdrop, Z1-07 motion)
    "z1_palette": HighlightSpec(
        "page",
        (),
        "Brand palette",
        merchant_hint=PAGE_WIDE_HINT,
    ),
    "z1_accent": HighlightSpec(
        "page",
        (),
        "Accent colour (buttons, links & prices)",
        merchant_hint=PAGE_WIDE_HINT,
    ),
    "z1_backdrop": HighlightSpec(
        "page",
        (),
        "Page backdrop",
        merchant_hint=PAGE_WIDE_HINT,
    ),
    "z1_motion": HighlightSpec(
        "page",
        (),
        "Page transitions",
        merchant_hint=PAGE_WIDE_HINT,
    ),
    # Z2 — hero (zone + banner strip)
    "z2_layout": HighlightSpec(
        "zone",
        (".sf-zone--z2",),
        "Hero & header layout",
        scroll_selector=".sf-zone--z2",
        merchant_hint=SECTION_HINT_TEMPLATE.format(label="Hero & header"),
    ),
    "z2_hero_bg": HighlightSpec(
        "element",
        (".sf-banner__media",),
        "Banner photo band",
        scroll_selector=".sf-banner__media",
        merchant_hint=SECTION_HINT_TEMPLATE.format(label="Banner background band"),
    ),
    # Z3 — typography (fonts global; panel fill section-scoped)
    "z3_fonts": HighlightSpec(
        "page",
        (),
        "Fonts (headings & body)",
        merchant_hint=PAGE_WIDE_HINT,
    ),
    "z3_scale": HighlightSpec(
        "page",
        (),
        "Font size scale",
        merchant_hint=PAGE_WIDE_HINT,
    ),
    "z3_text_colour": HighlightSpec(
        "page",
        (),
        "Text colours (headings & body)",
        merchant_hint=PAGE_WIDE_HINT,
    ),
    # Z4 — product sections
    "z4_showcase": HighlightSpec(
        "zone",
        ("#sf-showcase-section",),
        "Our Products section",
        scroll_selector="#sf-showcase-section",
        merchant_hint=SECTION_HINT_TEMPLATE.format(label="Our Products"),
    ),
    "z4_catalog": HighlightSpec(
        "zone",
        ("#sf-products-section",),
        "All Products & Services section",
        scroll_selector="#sf-products-section",
        merchant_hint=SECTION_HINT_TEMPLATE.format(label="All Products & Services"),
    ),
    "z4_layout": HighlightSpec(
        "element",
        (
            "#sf-showcase-section .sf-showcase-card",
            "#sf-products-section .sf-product",
        ),
        "Product cards (both sections)",
        scroll_selector="#sf-showcase-section .sf-showcase-card",
        merchant_hint=SECTION_HINT_TEMPLATE.format(label="Product cards"),
    ),
    "z4_prices": HighlightSpec(
        "element",
        (
            "#sf-showcase-section .sf-product__price",
            "#sf-products-section .sf-product__price",
        ),
        "Product prices (both sections)",
        scroll_selector="#sf-products-section .sf-product__price",
        merchant_hint=SECTION_HINT_TEMPLATE.format(label="Product prices"),
    ),
    # Z5
    "z5_info": HighlightSpec(
        "zone",
        ("#sf-offers-section",),
        "Offer cards",
        scroll_selector="#sf-offers-section",
        merchant_hint=SECTION_HINT_TEMPLATE.format(label="Offers"),
    ),
    # Z6 — buttons & CTAs (global)
    "z6_style": HighlightSpec(
        "page",
        (),
        "Button shape & style",
        merchant_hint=PAGE_WIDE_HINT,
    ),
    "z6_size": HighlightSpec(
        "element",
        (
            ".sf-follow__btn",
            ".sf-coupon__btn",
            ".sf-products-catalogue",
        ),
        "Button sizes (Follow, coupons & catalogue)",
        scroll_selector="#sf-products-section",
        merchant_hint=SECTION_HINT_TEMPLATE.format(label="CTA buttons on product areas"),
    ),
    "z6_cta_colour": HighlightSpec(
        "page",
        (),
        "Button & CTA colours",
        merchant_hint=PAGE_WIDE_HINT,
    ),
}

# Legacy zone keys → fallback when only zone code is known (non-tour focus).
ZONE_HIGHLIGHT_FALLBACK: dict[str, list[str]] = {
    "Z1_ACCENT": [],
    "Z1_BACKDROP": [],
    "Z1_INTRO": (
        ".sf-info--hero",
        ".sf-store-intro",
        "#sf-name",
        ".sf-hero-tagline",
    ),
    "Z2": list(SUB_STEP_HIGHLIGHTS["z2_layout"].selectors),
    "Z3": [],
    "Z4": list(SUB_STEP_HIGHLIGHTS["z4_layout"].selectors),
    "Z4S": list(SUB_STEP_HIGHLIGHTS["z4_showcase"].selectors),
    "Z4C": list(SUB_STEP_HIGHLIGHTS["z4_catalog"].selectors),
    "Z5": list(SUB_STEP_HIGHLIGHTS["z5_info"].selectors),
    "Z6": [],
}


def highlight_spec_for_sub_step(sub_step_id: str | None) -> HighlightSpec | None:
    if not sub_step_id:
        return None
    return SUB_STEP_HIGHLIGHTS.get(sub_step_id)


def preview_check_hint(
    sub_step_id: str | None,
    *,
    tour_completing: bool = False,
) -> str:
    """Short suffix for apply confirmations — matches whether the iframe shows an outline."""
    if tour_completing:
        return (
            "Guided highlights are now off — browse the **full preview** above, "
            "or tell me what to tweak next."
        )
    spec = highlight_spec_for_sub_step(sub_step_id)
    if spec and spec.scope == "page":
        return "Check your **full storefront** preview."
    if spec and spec.scope in ("zone", "element"):
        return "See the **outlined section** in your preview."
    return "Check your storefront preview."


def tour_complete_message(applied_summary: str) -> str:
    """Apply line + tour-done copy without promising a section highlight."""
    summary = applied_summary.strip().rstrip(".")
    return (
        f"{summary}. **Zone tour complete!** Your storefront is ready to fine-tune or publish. "
        f"{preview_check_hint(None, tour_completing=True)}"
    )


def highlight_spec_for_zone_tour(
    zone_code: str | None,
    sub_step_id: str | None,
) -> HighlightSpec:
    """Resolve highlight for active tour step."""
    spec = highlight_spec_for_sub_step(sub_step_id)
    if spec:
        return spec
    zone = (zone_code or "").upper()
    if zone == "Z5":
        return SUB_STEP_HIGHLIGHTS["z5_info"]
    selectors = tuple(ZONE_HIGHLIGHT_FALLBACK.get(zone, ()))
    if selectors:
        return HighlightSpec(
            "zone",
            selectors,
            zone,
            scroll_selector=selectors[0],
            merchant_hint=SECTION_HINT_TEMPLATE.format(label=zone),
        )
    return HighlightSpec("page", (), zone or "Storefront", merchant_hint=PAGE_WIDE_HINT)
