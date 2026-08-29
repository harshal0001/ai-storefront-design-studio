"""Zone-scoped colour requests when a preview section is focused."""

from conversational_agent.page_colors import resolve_color_from_text
from conversational_agent.section_focus import merge_focus
from conversational_agent.zone_focused_colors import (
    apply_zone_focused_color,
    is_zone_focused_color_request,
    resolve_zone_color_target,
)


def test_dark_red_compound_color():
    assert resolve_color_from_text("change the background color to dark red")


def test_hero_store_name_focus_targets_z2_surface():
    focus = merge_focus(
        focus_zone="Z2",
        focus_section_id="hero",
        focus_element_id="hero_store_name",
        message="",
    )
    target = resolve_zone_color_target(focus, "change the background color to dark red")
    assert target == ("Z2", "surface")


def test_detects_zone_color_request_with_ui_focus():
    focus = merge_focus(
        focus_zone="Z2",
        focus_section_id="hero",
        focus_element_id="hero_store_name",
        message="",
    )
    msg = "change the background color to dark red"
    assert is_zone_focused_color_request(msg, focus)
    assert not is_zone_focused_color_request(
        "make the background pink for the complete storefront", focus
    )


def test_apply_zone_focused_color_does_not_touch_global_background(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    from pathlib import Path

    from conversational_agent.config_manager import ConfigManager

    shop = "zone-bg-test"
    cfg = Path(tmp_path) / f"storefront_config_{shop}.json"
    cm = ConfigManager(shop_uuid=shop, config_path=cfg)
    original_bg = cm.tokens.colors.background
    cm.save_tokens(cm.tokens, theme_name="T")

    focus = merge_focus(
        focus_zone="Z2",
        focus_section_id="hero",
        focus_element_id="hero_store_name",
        message="",
    )
    applied, summary, updates = apply_zone_focused_color(
        "change the background color to dark red",
        shop_uuid=shop,
        focus=focus,
    )
    assert applied
    assert "surface" in summary or updates

    cm2 = ConfigManager(shop_uuid=shop, config_path=cfg)
    cm2.reload()
    assert cm2.tokens.colors.background == original_bg
    assert cm2.tokens.zoneScopes.get("Z2") is not None
    assert cm2.tokens.zoneScopes["Z2"].surface


def _product_cards_focus():
    return merge_focus(
        focus_zone="Z4C",
        focus_section_id="catalog",
        focus_element_id="catalog_cards",
        message="",
    )


def test_product_cards_focus_targets_card_faces():
    focus = _product_cards_focus()
    # "card(s)" wording, or the cards element with no qualifier, → card faces
    assert resolve_zone_color_target(focus, "make the product cards pink") == ("Z4C", "cardFace")
    assert resolve_zone_color_target(focus, "turn the cards green") == ("Z4C", "cardFace")


def test_product_panel_phrase_targets_section_panel():
    focus = _product_cards_focus()
    assert resolve_zone_color_target(focus, "make the section panel pink") == ("Z4C", "background")
    assert resolve_zone_color_target(focus, "change the background behind the cards to pink") == (
        "Z4C",
        "background",
    )


def test_apply_card_face_leaves_panel_and_globals(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    from pathlib import Path

    from conversational_agent.config_manager import ConfigManager

    shop = "card-face-test"
    cfg = Path(tmp_path) / f"storefront_config_{shop}.json"
    cm = ConfigManager(shop_uuid=shop, config_path=cfg)
    original_bg = cm.tokens.colors.background
    original_surface = cm.tokens.colors.surface
    cm.save_tokens(cm.tokens, theme_name="T")

    applied, summary, updates = apply_zone_focused_color(
        "make the product cards pink",
        shop_uuid=shop,
        focus=_product_cards_focus(),
    )
    assert applied
    assert "card" in summary.lower()

    cm2 = ConfigManager(shop_uuid=shop, config_path=cfg)
    cm2.reload()
    # card face is scoped; global colours and the section panel (background) are untouched
    assert cm2.tokens.colors.background == original_bg
    assert cm2.tokens.colors.surface == original_surface
    assert cm2.tokens.zoneScopes["Z4C"].cardFace
    assert cm2.tokens.zoneScopes["Z4C"].background is None
