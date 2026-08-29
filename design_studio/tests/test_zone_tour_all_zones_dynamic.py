"""Every editable zone sub-step exposes dynamic chat options."""

import pytest

from conversational_agent.config_manager import ConfigManager
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_flow import (
    ZONE_SUB_STEPS,
    current_sub_step,
    options_for_sub_step,
)


@pytest.mark.parametrize("zone_code", ["Z1", "Z2", "Z3", "Z4", "Z6"])
def test_each_zone_substep_generates_chat_options(tmp_path, monkeypatch, zone_code):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = f"zone-opts-{zone_code}"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test Theme")
    cm.reload()

    for idx, sub in enumerate(ZONE_SUB_STEPS[zone_code]):
        colors, layouts, packages = options_for_sub_step(zone_code, sub, shop)
        opts = packages or layouts or colors
        assert len(opts) >= 1, f"{zone_code} {sub.id} produced no options"
        assert all(o.get("what_changes") or o.get("description") for o in opts)


def test_z2_hero_bg_uses_dynamic_colours(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z2-hero-bg"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    mgr.complete_current()
    sub = current_sub_step("Z2", 1)
    assert sub and sub.id == "z2_hero_bg"
    colors, _, _ = options_for_sub_step("Z2", sub, shop)
    assert len(colors) >= 3
    assert colors[0]["id"].startswith("dyn_")
