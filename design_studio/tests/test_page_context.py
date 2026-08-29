"""Tests for page context routing and cross-page style parsing."""

from conversational_agent.direct_style import parse_direct_style_updates
from conversational_agent.page_context import (
    format_focused_style_message,
    has_explicit_ui_focus,
    is_cross_page_style_request,
    build_page_context_for_agent,
)
from conversational_agent.config import load_system_prompt
from conversational_agent.page_colors import apply_page_color_updates, is_page_color_request
from conversational_agent.section_focus import merge_focus


def test_build_page_context_includes_merchant_profile(monkeypatch):
    """Page context carries the saved brand profile so the agent stays mood-aware (CF-01 / 3.2)."""
    monkeypatch.setenv("USE_DYNAMODB", "false")
    ctx = build_page_context_for_agent("ctx-profile-shop")
    assert ctx["merchant_profile"] == {
        "moodTags": [],
        "audienceTags": [],
        "merchantCategory": "",
    }


def test_has_explicit_ui_focus():
    assert has_explicit_ui_focus(
        focus_zone=None,
        focus_section_id="catalog",
        focus_element_id="catalog_cards",
    )
    assert not has_explicit_ui_focus(
        focus_zone=None,
        focus_section_id=None,
        focus_element_id=None,
    )


def test_focused_style_message_requires_agent_tools():
    focus = merge_focus(
        focus_zone="Z4C",
        focus_section_id="catalog",
        focus_element_id="catalog_cards",
        message="",
    )
    msg = format_focused_style_message("demo", "border radius 0", focus)
    assert "get_storefront_page_context" in msg
    assert "apply_style_tokens" in msg
    assert "catalog_cards" in msg


def test_cross_page_detects_whole_page_italic():
    assert is_cross_page_style_request("make the complete text in the page italic")
    assert is_cross_page_style_request("italic everywhere on the storefront")


def test_cross_page_false_for_single_swatch():
    assert not is_cross_page_style_request("warm caramel")
    assert not is_cross_page_style_request("#BE185D")


def test_parse_italic_page_wide():
    updates = parse_direct_style_updates("make the complete text in the page italic")
    assert updates.get("heading_style") == "italic"
    assert updates.get("body_style") == "italic"


def test_page_color_request_pink_storefront():
    assert is_page_color_request("ok make the background pink for the complete storefront")


def test_apply_page_color_pink(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    from conversational_agent.config_manager import ConfigManager
    from pathlib import Path

    shop = "pink-bg-test"
    cfg = Path(tmp_path) / f"storefront_config_{shop}.json"
    cm = ConfigManager(shop_uuid=shop, config_path=cfg)
    cm.save_tokens(cm.tokens, theme_name="T")

    applied, summary, updates = apply_page_color_updates(
        "make the background pink for the complete storefront",
        shop_uuid=shop,
        config_path=cfg,
    )
    assert applied
    assert "pink" in summary.lower() or updates.get("background")

    cm2 = ConfigManager(shop_uuid=shop, config_path=cfg)
    cm2.reload()
    assert cm2.tokens.colors.background == cm2.tokens.colors.surface
    assert cm2.tokens.zoneScopes == {}


def test_blueprint_in_page_context(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    from conversational_agent.storefront_blueprint import build_storefront_blueprint

    bp = build_storefront_blueprint()
    assert len(bp["page_layout_scroll_order"]) >= 8
    assert len(bp["playbook_examples"]) >= 4

    ctx = build_page_context_for_agent("ctx-shop")
    assert "blueprint" in ctx
    assert "look_and_feel_now" in ctx
    assert "theme_application_flow" in ctx


def test_system_prompt_includes_blueprint():
    prompt = load_system_prompt()
    assert "Storefront blueprint" in prompt
    assert "apply_style_tokens" in prompt
    assert "page_layout_scroll_order" in prompt or "Hero banner" in prompt


def test_page_context_includes_zones(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    ctx = build_page_context_for_agent("ctx-test-shop")
    assert "zones" in ctx
    codes = {z["code"] for z in ctx["zones"]}
    assert "Z3" in codes
    assert "italic" in str(ctx["zones"]).lower() or "headingStyle" in str(ctx["current_theme"])
