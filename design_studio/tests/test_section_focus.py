"""Section + element focus — chips, text detection, highlights."""

from conversational_agent.section_focus import (
    element_for_id,
    highlight_selectors_for_focus,
    list_sections_for_ui,
    merge_focus,
    resolve_focus_from_text,
)


def test_list_sections_includes_elements():
    sections = list_sections_for_ui()
    catalog = next(s for s in sections if s["id"] == "catalog")
    assert len(catalog["elements"]) >= 2
    ids = {e["id"] for e in catalog["elements"]}
    assert "catalog_cards" in ids


def test_text_detects_catalog_product_cards_element():
    focus = resolve_focus_from_text(
        "product cards under ALL PRODUCTS look bad, make them rectangular"
    )
    assert focus is not None
    assert focus.element_id == "catalog_cards"
    assert focus.zone == "Z4C"
    assert "Product cards" in focus.element_label


def test_explicit_element_wins_over_zone():
    focus = merge_focus(
        focus_zone="Z2",
        focus_element_id="catalog_cards",
        message="hero banner",
    )
    assert focus is not None
    assert focus.element_id == "catalog_cards"


def test_element_highlight_narrower_than_zone():
    zone_sels = highlight_selectors_for_focus(zone="Z4C")
    card_sels = highlight_selectors_for_focus(zone="Z4C", element_id="catalog_cards")
    assert ".sf-zone--z4-catalog" in zone_sels[0] or any("z4-catalog" in s for s in zone_sels)
    assert any("sf-product" in s for s in card_sels)


def test_buttons_zone_highlights_button_elements_not_wrapper():
    selectors = highlight_selectors_for_focus(zone="Z6")
    assert ".sf-follow__btn" in selectors
    assert ".sf-zone--z6" not in selectors


def test_catalog_cards_element_exists():
    el = element_for_id("catalog_cards")
    assert el is not None
    assert el["section_id"] == "catalog"
