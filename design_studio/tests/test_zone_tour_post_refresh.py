"""Post-agent refresh safety net when the agent narrates new options without calling the tool."""

from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_flow import current_sub_step, options_for_sub_step
from conversational_agent.zone_tour_post_refresh import ensure_tour_options_refreshed_if_requested
from conversational_agent.config_manager import ConfigManager


def test_post_agent_refresh_when_cache_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "post-refresh"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(5):
        mgr.complete_current()
    sub = current_sub_step("Z6", mgr.get_sub_step_index())
    _, first, _ = options_for_sub_step("Z6", sub, shop)
    before = mgr.get_cached_option_ids()

    resp = ensure_tour_options_refreshed_if_requested(
        shop,
        "give me more options",
        {"message": "Here are some fresh button styles for you."},
        option_ids_before=before,
    )
    after = mgr.get_cached_option_ids()
    assert after != before
    assert "more" in resp["message"].lower() or "options" in resp["message"].lower()


def test_post_agent_skips_when_cache_already_changed(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "post-skip"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(5):
        mgr.complete_current()
    sub = current_sub_step("Z6", mgr.get_sub_step_index())
    options_for_sub_step("Z6", sub, shop)
    before = mgr.get_cached_option_ids()
    from conversational_agent.zone_dynamic_options import refresh_options_for_current_sub_step

    refresh_options_for_current_sub_step(shop, "more")
    after_tool = mgr.get_cached_option_ids()
    assert after_tool != before

    resp = ensure_tour_options_refreshed_if_requested(
        shop,
        "give me more options",
        {"message": "Done."},
        option_ids_before=before,
    )
    assert mgr.get_cached_option_ids() == after_tool
    assert resp["message"] == "Done."
