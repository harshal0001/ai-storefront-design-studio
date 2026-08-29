"""Focused element style parsing (product card border radius, etc.)."""

from conversational_agent.element_focused_style import (
    parse_focused_element_updates,
)
from conversational_agent.section_focus import merge_focus


def _catalog_focus():
    return merge_focus(
        focus_zone="Z4C",
        focus_section_id="catalog",
        focus_element_id="catalog_cards",
        message="",
    )


def test_border_radius_zero_on_catalog_cards_focus():
    focus = _catalog_focus()
    updates = parse_focused_element_updates("make the product border radius 0", focus)
    assert updates == {"product_card_shape": "sharp"}


def test_border_radius_zero_without_product_word_when_focused():
    focus = _catalog_focus()
    updates = parse_focused_element_updates("border radius 0", focus)
    assert updates == {"product_card_shape": "sharp"}


def test_no_updates_without_focus():
    assert parse_focused_element_updates("border radius 0", None) == {}


def test_direct_style_product_border_radius_without_focus():
    from conversational_agent.direct_style import parse_direct_style_updates

    assert parse_direct_style_updates("make the product border radius 0") == {
        "product_card_shape": "sharp"
    }
