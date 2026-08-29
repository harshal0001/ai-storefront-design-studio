"""Z6 button-style refresh must not silently repeat the same four presets."""

from conversational_agent.zone_dynamic_options import (
    generate_layout_options_for_sub_step,
    refresh_options_for_current_sub_step,
)
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_flow import current_sub_step, options_for_sub_step
from conversational_agent.config_manager import ConfigManager


def _start_z6_style_step(shop: str) -> ZoneTourManager:
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(5):
        mgr.complete_current()
    assert mgr.current_step().code == "Z6"
    assert current_sub_step("Z6", mgr.get_sub_step_index()).id == "z6_style"
    return mgr


def test_z6_catalog_has_more_than_four_presets():
    sub = current_sub_step("Z6", 0)
    assert sub
    opts = generate_layout_options_for_sub_step("z6-catalog", "Z6", sub, limit=4)
    assert len(opts) == 4
    assert len({o["id"] for o in opts}) == 4


def test_z6_refresh_cycles_new_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z6-no-repeat"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = _start_z6_style_step(shop)
    sub = current_sub_step("Z6", mgr.get_sub_step_index())

    _, first, _ = options_for_sub_step("Z6", sub, shop)
    first_ids = {o["id"] for o in first}
    assert len(first_ids) >= 3

    _, second, _, lead = refresh_options_for_current_sub_step(shop, "give me more options")
    second_ids = {o["id"] for o in second}
    assert second_ids
    assert second_ids.isdisjoint(first_ids), f"repeated: {second_ids & first_ids}"
    assert "more" in lead.lower() or "options" in lead.lower()


def test_z6_one_more_appends_to_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z6-append"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = _start_z6_style_step(shop)
    sub = current_sub_step("Z6", mgr.get_sub_step_index())

    _, first, _ = options_for_sub_step("Z6", sub, shop)
    n_first = len(first)

    _, one, _, lead = refresh_options_for_current_sub_step(
        shop, "give 1 more option", option_limit=1, append=True
    )
    assert len(one) == 1
    cached = mgr.get_cached_zone_options()
    assert len(cached) == n_first + 1
    assert "added" in lead.lower() or "more" in lead.lower()
