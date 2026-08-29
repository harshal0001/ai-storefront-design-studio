"""End-to-end Z1 tour clicks: every sub-step applies tokens and advances."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour_flow import current_sub_step, options_for_sub_step


def _click(shop: str, option_id: str) -> dict:
    resp = try_handle_zone_tour_message(shop, f"zone option {option_id}")
    assert resp is not None, f"No response for {option_id}"
    assert resp.get("type") == "zone_tour"
    assert "html" in resp
    return resp


def test_z1_all_sub_steps_apply_and_advance(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-full-tour"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()

    # Step 1 — palette cards
    sub = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub.id == "z1_palette"
    _, _, packages = options_for_sub_step("Z1", sub, shop)
    assert packages
    _click(shop, packages[0]["id"])
    assert mgr.get_sub_step_index() == 1

    # Step 2 — accent
    sub = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub.id == "z1_accent"
    accents, _, _ = options_for_sub_step("Z1", sub, shop)
    assert accents[0]["id"].startswith("z1_acc_")
    accent_hex = accents[0]["hex"]
    _click(shop, accents[0]["id"])
    assert mgr.get_sub_step_index() == 2
    cm.reload()
    assert cm.tokens.colors.accent.lower() == accent_hex.lower()

    # Step 3 — backdrop
    sub = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub.id == "z1_backdrop"
    backdrops, _, _ = options_for_sub_step("Z1", sub, shop)
    bg_hex = backdrops[0]["hex"]
    _click(shop, backdrops[0]["id"])
    assert mgr.get_sub_step_index() == 3
    cm.reload()
    assert cm.tokens.colors.background.lower() == bg_hex.lower()

    # Step 4 — motion
    sub = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub.id == "z1_motion"
    _, motions, _ = options_for_sub_step("Z1", sub, shop)
    motion_id = motions[0]["id"]
    _click(shop, motion_id)
    assert mgr.get_sub_step_index() == 0
    assert mgr.current_step().code == "Z2"
    cm.reload()
    assert cm.tokens.motion.transition in ("fadeTint", "slideTint", "none")


def test_zone_option_click_never_returns_none_for_cached_id(tmp_path, monkeypatch):
    """Swatch clicks must get a server tour response, not Bedrock (None from fast path)."""
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-no-agent-fallback"
    ConfigManager(shop_uuid=shop).save_tokens(
        ConfigManager(shop_uuid=shop).tokens, theme_name="Test"
    )
    mgr = ZoneTourManager(shop)
    mgr.start()
    _, _, packages = options_for_sub_step("Z1", current_sub_step("Z1", 0), shop)
    mgr.clear_option_cache()
    resp = try_handle_zone_tour_message(shop, f"zone option {packages[0]['id']}")
    assert resp is not None
    assert "Great choice" not in (resp.get("message") or "")
