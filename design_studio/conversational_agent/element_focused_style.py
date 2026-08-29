"""Apply style updates when chat focus is on a specific preview element.

When the UI sends ``focusElementId`` (e.g. ``catalog_cards``), only rules in
``_ELEMENT_RULES`` for that element are considered — tighter than global ``direct_style``.

Skipped entirely when ``server`` sets ``style_via_agent=True`` (focused edits go to Bedrock).
"""

from __future__ import annotations

import re

from .direct_style import apply_direct_style_updates
from .product_card_phrases import ELEMENT_BORDER_RADIUS_ZERO, PRODUCT_CARD_BORDER_RADIUS_ZERO
from .section_focus import SectionFocus

# Element id → phrase rules (applied only when that element is focused in the UI)
_ELEMENT_RULES: dict[str, list[tuple[re.Pattern[str], dict[str, str]]]] = {
    "catalog_cards": [
        # product_card_shape=sharp also sets data-card-shape on the catalog zone in storefront.html
        (PRODUCT_CARD_BORDER_RADIUS_ZERO, {"product_card_shape": "sharp"}),
        (ELEMENT_BORDER_RADIUS_ZERO, {"product_card_shape": "sharp"}),
        (re.compile(r"\brounded\s+(product\s+)?cards?\b", re.I), {"product_card_shape": "rounded"}),
        (
            re.compile(r"\bcircular\s+(product\s+)?images?\b", re.I),
            {"product_card_shape": "circularImage"},
        ),
    ],
    "showcase_cards": [
        (ELEMENT_BORDER_RADIUS_ZERO, {"product_card_shape": "sharp"}),
    ],
}


def parse_focused_element_updates(message: str, focus: SectionFocus | None) -> dict[str, str]:
    if not focus or not focus.element_id:
        return {}
    rules = _ELEMENT_RULES.get(focus.element_id, [])
    updates: dict[str, str] = {}
    for pattern, fields in rules:
        if pattern.search(message):
            updates.update(fields)
    return updates


def apply_focused_element_style(
    message: str,
    *,
    shop_uuid: str,
    focus: SectionFocus | None,
) -> tuple[bool, str, dict[str, str]]:
    updates = parse_focused_element_updates(message, focus)
    if not updates:
        return False, "", {}
    return apply_direct_style_updates(message, shop_uuid=shop_uuid, extra=updates)
