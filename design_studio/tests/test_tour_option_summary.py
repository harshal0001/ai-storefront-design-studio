"""Cached option summary for agent/tool copy (P1)."""

from conversational_agent.zone_dynamic_options import summarize_cached_tour_options
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.config_manager import ConfigManager


def test_summarize_cached_options_after_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "sum-opts"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    mgr.cache_sub_step_options(
        "z6_style",
        zone_options=[
            {"id": "a", "name": "Friendly rounded"},
            {"id": "b", "name": "Pill CTAs"},
        ],
    )
    summary = summarize_cached_tour_options(mgr)
    assert "Friendly rounded" in summary
    assert "Pill CTAs" in summary
