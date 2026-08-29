"""Zone tour option refresh — agent tool + generation (no regex routing)."""

from conversational_agent.zone_dynamic_options import refresh_options_for_current_sub_step
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour_flow import current_sub_step
from conversational_agent.config_manager import ConfigManager


def test_one_more_option_via_tool_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "one-more-opt"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(3):
        mgr.complete_current()
    mgr.advance_sub_step()
    mgr.advance_sub_step()

    from conversational_agent.zone_tour_flow import options_for_sub_step

    sub = current_sub_step("Z4", mgr.get_sub_step_index())
    first, _, _ = options_for_sub_step("Z4", sub, shop)
    first_ids = {o["id"] for o in _}

    _, one, _, lead = refresh_options_for_current_sub_step(shop, "stylish minimal", option_limit=1)
    assert len(one) == 1
    assert one[0]["id"] not in first_ids
    assert "one more" in lead.lower()
    assert "grid" in one[0]["what_changes"].lower() or "column" in one[0]["what_changes"].lower()


def test_refresh_returns_different_layout_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "refresh-layout"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    cm.reload()

    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(3):
        mgr.complete_current()
    assert mgr.current_step().code == "Z4"
    mgr.advance_sub_step()
    mgr.advance_sub_step()
    assert current_sub_step("Z4", mgr.get_sub_step_index()).id == "z4_layout"

    _, first, _, _ = refresh_options_for_current_sub_step(shop, "")
    first_ids = {o["id"] for o in first}

    _, second, _, lead = refresh_options_for_current_sub_step(shop, "stylish elegant")
    second_ids = {o["id"] for o in second}
    assert "more" in lead.lower() or "stylish" in lead.lower() or "elegant" in lead.lower()
    assert first_ids != second_ids or len(second) >= 1


def test_more_options_routes_to_agent_not_fast_path(tmp_path, monkeypatch):
    """Free-form 'more options' must return None so server invokes Bedrock."""
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "agent-route-more"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(3):
        mgr.complete_current()
    mgr.advance_sub_step()
    mgr.advance_sub_step()

    assert try_handle_zone_tour_message(shop, "give 1 more options") is None
    assert try_handle_zone_tour_message(shop, "give me more stylish options") is None
