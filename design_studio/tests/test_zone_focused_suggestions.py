"""Focused zone UI — suggestion swatches without hex in chat message."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.section_focus import merge_focus
from conversational_agent.chat_fast_path import run_fast_path
from conversational_agent.zone_focused_suggestions import (
    build_focused_suggestions_response,
    classify_focused_request,
    user_wants_focused_color_suggestions,
    user_wants_focused_layout_options,
)


def test_detects_give_me_color_options():
    focus = merge_focus(
        focus_element_id="hero_store_name",
        focus_section_id="hero",
        message="",
    )
    assert focus and focus.zone == "Z2"
    assert user_wants_focused_color_suggestions("give me color options", focus)


def test_hero_store_name_suggestions_and_i_choose(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "hero-color-opts"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Botanical")
    focus = merge_focus(focus_element_id="hero_store_name", message="")

    resp1 = run_fast_path(shop, "give me color options", focus, style_via_agent=True)
    assert resp1 and resp1.get("color_options")
    pick = resp1["color_options"][0]

    resp2 = run_fast_path(
        shop,
        f'I choose "{pick["name"]}"',
        focus,
        style_via_agent=True,
    )
    assert resp2 is not None
    assert "No theme" not in (resp2.get("message") or "")
    assert "Done" in resp2.get("message", "") or "→" in resp2.get("message", "")


def test_detects_background_suggestion_request():
    focus = merge_focus(focus_zone="Z3", focus_section_id="intro", message="")
    assert user_wants_focused_color_suggestions("give me more background suggestion", focus)
    assert not user_wants_focused_color_suggestions("change the background to #BE185D", focus)


def test_focused_suggestions_return_swatch_payload_no_hex_in_message(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "focus-suggest"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Botanical")
    focus = merge_focus(focus_zone="Z3", focus_section_id="intro", message="")
    payload = build_focused_suggestions_response(shop, "give me more background suggestion", focus)
    assert payload.get("color_options")
    assert len(payload["color_options"]) >= 1
    msg = payload.get("message", "")
    assert "#" not in msg or "pick a swatch" in msg.lower()
    for opt in payload["color_options"]:
        assert opt.get("hex")
        assert opt.get("name")


def test_fast_path_suggestions_then_apply(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "focus-suggest-apply"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    focus = merge_focus(focus_zone="Z3", focus_section_id="intro", message="")

    resp1 = run_fast_path(
        shop,
        "give me more background suggestion",
        focus,
        style_via_agent=True,
    )
    assert resp1 is not None
    assert resp1.get("color_options")
    assert "#" not in (resp1.get("message") or "")

    pick = resp1["color_options"][0]
    resp2 = run_fast_path(
        shop,
        f"zone option {pick['id']}",
        focus,
        style_via_agent=True,
    )
    assert resp2 is not None
    assert "Done" in resp2.get("message", "") or "→" in resp2.get("message", "")


def test_catalog_layout_vs_style_routing():
    focus = merge_focus(
        focus_element_id="catalog_cards",
        focus_section_id="catalog",
        message="",
    )
    assert focus and focus.zone == "Z4C"
    assert classify_focused_request("give its more layout options", focus) == "layout"
    assert user_wants_focused_layout_options("give its more layout options", focus)
    assert not user_wants_focused_color_suggestions("give more style option", focus)
    assert classify_focused_request("give more style option", focus) == "agent"


def test_catalog_layout_suggestions_use_zone_options(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "catalog-layout-opts"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Botanical")
    focus = merge_focus(focus_element_id="catalog_cards", message="")

    resp = run_fast_path(
        shop,
        "give its more layout options",
        focus,
        style_via_agent=True,
    )
    assert resp is not None
    assert resp.get("zone_options")
    assert not resp.get("color_options")
    msg = (resp.get("message") or "").lower()
    assert "layout" in msg or "card style" in msg
    for opt in resp["zone_options"]:
        assert opt.get("name")
        desc = (opt.get("description") or opt.get("what_changes") or "").lower()
        assert "accent highlights" not in desc


def test_catalog_color_options_card_face_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "catalog-color-opts"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Botanical")
    focus = merge_focus(focus_element_id="catalog_cards", message="")

    resp = run_fast_path(shop, "give me color options", focus, style_via_agent=True)
    assert resp and resp.get("color_options")
    for opt in resp["color_options"]:
        desc = (opt.get("description") or opt.get("what_changes") or "").lower()
        assert "product card" in desc or "card tile" in desc
        assert "accent highlights" not in desc


def test_more_style_does_not_return_colour_swatches(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "catalog-style-agent"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Botanical")
    focus = merge_focus(focus_element_id="catalog_cards", message="")

    resp = run_fast_path(
        shop,
        "give more style option",
        focus,
        style_via_agent=True,
    )
    assert resp is None
