"""Detect product-card fix requests and apply tokens without relying on the LLM.

Handles merchant complaints ("cards look bad", "not round", "border radius 0") especially
for the All Products catalog (Z4C). Delegates token writes to ``apply_direct_style_updates``.
"""

from __future__ import annotations

import re

from .config_manager import ConfigManager, DEFAULT_SHOP_UUID
from .direct_style import apply_direct_style_updates
from .product_card_phrases import (
    CARD_QUALITY_RE,
    LIST_LAYOUT_RE,
    PRODUCT_SECTION_RE,
    WANTS_RECTANGLE_RE,
)


def is_product_card_fix_request(
    message: str,
    *,
    focus_zone: str | None = None,
    focus_element_id: str | None = None,
) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if focus_element_id == "catalog_cards":
        return True
    if focus_zone == "Z4C" and re.search(
        r"\b(card|cards|rectangle|rectangular|shape|layout|hidden|bad|ugly|update)\b",
        text,
        re.I,
    ):
        return True
    if not PRODUCT_SECTION_RE.search(text):
        return False
    return bool(
        WANTS_RECTANGLE_RE.search(text)
        or CARD_QUALITY_RE.search(text)
        or LIST_LAYOUT_RE.search(text)
    )


def parse_product_card_fix_updates(
    message: str,
    *,
    current_shape: str = "",
    focus_zone: str | None = None,
    focus_element_id: str | None = None,
) -> dict[str, str]:
    """Map merchant complaints to concrete productCards token updates."""
    if not is_product_card_fix_request(
        message, focus_zone=focus_zone, focus_element_id=focus_element_id
    ):
        return {}

    updates: dict[str, str] = {}

    if WANTS_RECTANGLE_RE.search(message) or CARD_QUALITY_RE.search(message):
        if current_shape == "sharp" and re.search(r"\bsharp\b", message, re.I):
            updates["product_card_shape"] = "sharp"
        else:
            updates["product_card_shape"] = "rounded"
        updates["product_card_layout"] = "grid2"
        updates["product_card_shadow"] = "elevated"

    if LIST_LAYOUT_RE.search(message):
        updates["product_card_layout"] = "list"
        updates["product_card_shape"] = updates.get("product_card_shape", "rounded")

    return updates


def apply_product_card_fix(
    message: str,
    *,
    shop_uuid: str = DEFAULT_SHOP_UUID,
    focus_zone: str | None = None,
    focus_element_id: str | None = None,
) -> tuple[bool, str, dict[str, str]]:
    """Apply product card token fixes when the merchant describes catalog card problems."""
    cm = ConfigManager(shop_uuid=shop_uuid)
    cm.reload()
    current_shape = cm.tokens.productCards.shape
    updates = parse_product_card_fix_updates(
        message,
        current_shape=current_shape,
        focus_zone=focus_zone,
        focus_element_id=focus_element_id,
    )
    if not updates:
        return False, "", {}

    if (
        updates.get("product_card_shape") in ("rounded", "sharp")
        and current_shape == "circularImage"
    ):
        updates.setdefault("product_card_shape", "rounded")

    return apply_direct_style_updates(message, shop_uuid=shop_uuid, extra=updates)
