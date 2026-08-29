"""Apply confirmations match highlight scope; tour complete does not promise outlines."""

from conversational_agent.zone_highlight import preview_check_hint, tour_complete_message
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour_flow import current_sub_step
from conversational_agent.config_manager import ConfigManager


def test_preview_hint_page_scope():
    assert "full storefront" in preview_check_hint("z6_cta_colour").lower()
    assert "outlined" not in preview_check_hint("z6_cta_colour").lower()


def test_preview_hint_element_scope():
    hint = preview_check_hint("z2_hero_bg")
    assert "outlined" in hint.lower()


def test_tour_completing_hint_no_outline():
    hint = preview_check_hint("z6_cta_colour", tour_completing=True)
    assert "highlights are now off" in hint.lower() or "highlights are off" in hint.lower()
    assert "outlined" not in hint.lower()


def test_tour_complete_message():
    msg = tour_complete_message("Applied **Amber** — CTA colour updated")
    assert "Zone tour complete" in msg
    assert "highlighted area" not in msg.lower()
    assert "highlights" in msg.lower()


def test_last_z6_choice_completion_message(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "finish-msg"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(5):
        mgr.complete_current()
    mgr.advance_sub_step()
    mgr.advance_sub_step()
    assert current_sub_step("Z6", mgr.get_sub_step_index()).id == "z6_cta_colour"

    from conversational_agent.zone_tour_flow import options_for_sub_step

    sub = current_sub_step("Z6", mgr.get_sub_step_index())
    colors, _, _ = options_for_sub_step("Z6", sub, shop)
    assert colors
    pick = colors[0]
    resp = try_handle_zone_tour_message(shop, pick.get("name") or f"zone option {pick['id']}")
    assert resp is not None
    assert resp["zone_tour"]["active"] is False
    text = resp["message"].lower()
    assert "zone tour complete" in text
    assert "highlighted area" not in text
    assert "highlights" in text or "full preview" in text
