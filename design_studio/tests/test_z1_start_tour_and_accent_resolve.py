"""Start-tour phrases and accent swatch resolution without warm cache."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.z1_tour_options import find_z1_accent_option
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour_flow import current_sub_step


def test_start_zone_wise_customization_starts_tour(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-start-phrase"
    ConfigManager(shop_uuid=shop).save_tokens(
        ConfigManager(shop_uuid=shop).tokens, theme_name="Test"
    )
    mgr = ZoneTourManager(shop)
    assert not mgr.is_active()

    resp = try_handle_zone_tour_message(shop, "start zone wise customization")
    assert resp is not None
    assert resp.get("type") == "zone_tour"
    assert mgr.is_active()
    assert "html" in resp
    assert resp.get("zone_tour", {}).get("active") is True


def test_z1_acc_click_without_cache_still_applies(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-acc-no-cache"
    cm = ConfigManager(shop_uuid=shop)
    cm.tokens.colors.primary = "#2563EB"
    cm.save_tokens(cm.tokens, theme_name="Test")

    mgr = ZoneTourManager(shop)
    mgr.start()
    mgr.ensure_current_sub_step_ready()
    while current_sub_step("Z1", mgr.get_sub_step_index()).id != "z1_accent":
        mgr.advance_sub_step()
    mgr.clear_option_cache()

    hit = find_z1_accent_option(shop, "z1_acc_complement_0_0")
    assert hit is not None
    assert hit["hex"]

    resp = try_handle_zone_tour_message(shop, "zone option z1_acc_complement_0_0")
    assert resp is not None
    assert "couldn't apply" not in (resp.get("message") or "").lower()

    cm2 = ConfigManager(shop_uuid=shop)
    cm2.reload()
    assert cm2.tokens.colors.accent.lower() == hit["hex"].lower()


def test_z1_motion_fade_without_cache(tmp_path, monkeypatch):
    from conversational_agent.z1_tour_options import find_z1_motion_option
    from conversational_agent.zone_tour_flow import sub_steps_for_zone

    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-motion-no-cache"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")

    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(3):
        mgr.advance_sub_step()
    sub = sub_steps_for_zone("Z1")[3]
    assert sub.id == "z1_motion"
    mgr.clear_option_cache()

    assert find_z1_motion_option(shop, option_id="z1_motion_fade")
    resp = try_handle_zone_tour_message(shop, "zone option z1_motion_fade")
    assert resp is not None
    assert "couldn't apply" not in (resp.get("message") or "").lower()

    cm2 = ConfigManager(shop_uuid=shop)
    cm2.reload()
    assert cm2.tokens.motion.transition == "fadeTint"
