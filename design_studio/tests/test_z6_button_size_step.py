"""Z6 tour — button size sub-step (Z6-04)."""

from conversational_agent.zone_dynamic_options import (
    Z6_SIZE_PRESETS,
    generate_layout_options_for_sub_step,
    z6_button_size_for_option,
)
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour_flow import ZONE_SUB_STEPS, current_sub_step
from conversational_agent.config_manager import ConfigManager


def test_z6_sub_steps_include_size():
    steps = ZONE_SUB_STEPS["Z6"]
    assert [s.id for s in steps] == ["z6_style", "z6_size", "z6_cta_colour"]


def test_z6_size_presets_three_options(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z6-size"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    sub = current_sub_step("Z6", 1)
    assert sub and sub.id == "z6_size"
    opts = generate_layout_options_for_sub_step(shop, "Z6", sub)
    assert len(opts) == 3
    assert {o["id"] for o in opts} == {p["id"] for p in Z6_SIZE_PRESETS}


def test_z6_size_apply_updates_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z6-apply-size"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(5):
        mgr.complete_current()
    mgr.advance_sub_step()
    assert current_sub_step("Z6", mgr.get_sub_step_index()).id == "z6_size"

    mgr.apply_selection_to_tokens("Z6", option_id="z6_size_large")
    cm.reload()
    assert cm.tokens.buttons.size == "large"
    assert z6_button_size_for_option("z6_size_large") == "large"


def test_skip_from_z6_style_goes_to_size(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z6-skip-size"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = _reach_z6_style(shop)
    resp = try_handle_zone_tour_message(shop, "Skip this step")
    assert resp is not None
    assert current_sub_step("Z6", mgr.get_sub_step_index()).id == "z6_size"


def _reach_z6_style(shop: str) -> ZoneTourManager:
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(5):
        mgr.complete_current()
    assert current_sub_step("Z6", 0).id == "z6_style"
    return mgr
