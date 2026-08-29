"""Hero layout sub-step — refresh and per-sub-step dismissed ids."""

from conversational_agent.zone_dynamic_options import (
    exhausted_options_lead,
    refresh_options_for_current_sub_step,
)
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_flow import current_sub_step, options_for_sub_step
from conversational_agent.config_manager import ConfigManager


def test_z2_refresh_after_first_batch_shows_layouts(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z2-refresh"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    mgr.complete_current()
    assert mgr.current_step().code == "Z2"
    sub = current_sub_step("Z2", 0)
    assert sub.id == "z2_layout"

    _, first, _ = options_for_sub_step("Z2", sub, shop)
    first_ids = {o["id"] for o in first}
    assert len(first_ids) >= 4

    _, second, _, lead = refresh_options_for_current_sub_step(shop, "give more options")
    second_ids = {o["id"] for o in second}
    assert second_ids
    assert "button" not in lead.lower()
    assert "hero" in exhausted_options_lead("z2_layout").lower()


def test_exhausted_lead_not_z6_on_hero(tmp_path, monkeypatch):
    assert "pill ghost" not in exhausted_options_lead("z2_layout")
    assert "pill ghost" in exhausted_options_lead("z6_style")
