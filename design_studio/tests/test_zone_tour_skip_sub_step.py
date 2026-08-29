"""Skip a single zone tour sub-step (e.g. Z6 step 1 → step 2)."""

from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour_flow import current_sub_step, sub_steps_for_zone
from conversational_agent.message_parsers import wants_skip_sub_step
from conversational_agent.config_manager import ConfigManager


def _reach_z6_step1(shop: str) -> ZoneTourManager:
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(5):
        mgr.complete_current()
    assert mgr.current_step().code == "Z6"
    assert current_sub_step("Z6", 0).id == "z6_style"
    return mgr


def test_wants_skip_sub_step_phrases():
    assert wants_skip_sub_step("Skip this step")
    assert wants_skip_sub_step("next step")
    assert wants_skip_sub_step("skip to step 2")
    assert wants_skip_sub_step("zone option skip_sub_step")
    assert not wants_skip_sub_step("Skip this zone")


def test_skip_sub_step_advances_z6_to_cta_colour(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "skip-sub"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = _reach_z6_step1(shop)
    assert mgr.can_skip_sub_step()

    resp = try_handle_zone_tour_message(shop, "Skip this step")
    assert resp is not None
    assert resp["zone_tour"]["active"]
    assert mgr.get_sub_step_index() == 1
    assert current_sub_step("Z6", 1).id == "z6_size"
    assert resp["zone_tour"]["sub_step_index"] == 1
    total = len(sub_steps_for_zone("Z6"))
    assert resp["zone_tour"]["sub_step_total"] == total


def test_skip_to_step_jumps_forward(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "skip-jump"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = _reach_z6_step1(shop)

    resp = try_handle_zone_tour_message(shop, "skip to step 2")
    assert resp is not None
    assert mgr.get_sub_step_index() == 1
    assert current_sub_step("Z6", 1).id == "z6_size"


def test_cannot_skip_last_sub_step(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "skip-last"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = _reach_z6_step1(shop)
    mgr.advance_sub_step()
    mgr.advance_sub_step()
    assert current_sub_step("Z6", mgr.get_sub_step_index()).id == "z6_cta_colour"
    assert not mgr.can_skip_sub_step()
    assert try_handle_zone_tour_message(shop, "Skip this step") is None
