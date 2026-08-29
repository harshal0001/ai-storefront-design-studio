"""Tests for server-side zone tour handlers."""

from conversational_agent.zone_color_presets import find_color_option, zone_color_options_for_code
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.config_manager import ConfigManager
from conversational_agent.zone_tour_flow import (
    extract_hex_from_text,
    match_sub_step_choice,
    current_sub_step,
)


def test_extract_hex_strips_trailing_period():
    assert extract_hex_from_text("#BE185D.") == "#be185d"


def test_free_text_hex_applies_and_advances_during_tour(tmp_path, monkeypatch):
    """Typed hex on a colour sub-step applies without Bedrock and advances the tour."""
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "hex-z1-test"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    cm.reload()

    cm.tokens.colors.paletteName = "Configured"
    cm.tokens.colors.primary = "#BE185D"
    cm.save_tokens(cm.tokens, theme_name="Test")
    cm.reload()

    mgr = ZoneTourManager(shop)
    mgr.start()
    sub = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub and sub.id == "z1_accent"
    assert match_sub_step_choice("Z1", sub, "#BE185D.") is None
    resp = try_handle_zone_tour_message(shop, "#BE185D.")
    assert resp is not None
    assert mgr.get_sub_step_index() == 2
    assert try_handle_zone_tour_message(shop, "warm coral") is None
    assert try_handle_zone_tour_message(shop, "make the backdrop cream") is None


def test_z1_accent_substep_sets_accent_without_changing_primary(tmp_path, monkeypatch):
    """Z1-02: accent sub-step sets a global accent independent of primary."""
    from conversational_agent.zone_tour_flow import options_for_sub_step

    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-accent-test"
    cm = ConfigManager(shop_uuid=shop)
    cm.tokens.colors.primary = "#336699"
    cm.tokens.colors.accent = "#336699"
    cm.save_tokens(cm.tokens, theme_name="Test")
    cm.reload()
    monkeypatch.setattr(
        "conversational_agent.zone_dynamic_options.load_mood_tags",
        lambda _mid: ["warm"],
    )

    mgr = ZoneTourManager(shop)
    mgr.start()
    sub0 = current_sub_step("Z1", 0)
    assert sub0.id == "z1_palette"
    _, _, packages = options_for_sub_step("Z1", sub0, shop)
    try_handle_zone_tour_message(shop, f"zone option {packages[0]['id']}")

    sub1 = current_sub_step("Z1", 1)
    assert sub1.id == "z1_accent"
    primary_before = ConfigManager(shop_uuid=shop).tokens.colors.primary
    accent_opts, _, _ = options_for_sub_step("Z1", sub1, shop)
    try_handle_zone_tour_message(shop, f"zone option {accent_opts[0]['id']}")

    cm2 = ConfigManager(shop_uuid=shop)
    cm2.reload()
    assert cm2.tokens.colors.primary == primary_before
    assert cm2.tokens.colors.accent
    assert cm2.tokens.colors.accent != cm2.tokens.colors.primary


def test_z4_color_options_exist():
    opts = zone_color_options_for_code("Z4")
    assert len(opts) >= 4
    assert find_color_option("Z4", name="Coral prices")["hex"] == "#E85D4C"


def test_z4_price_style_apply(tmp_path, monkeypatch):
    """Z4 step 4 applies price display style (not accent colour swatches)."""
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "test-z4-price-style"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")

    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(3):
        mgr.complete_current()
    assert mgr.current_step().code == "Z4"
    for _ in range(3):
        mgr.advance_sub_step()
    assert mgr.get_sub_step_index() == 3

    from conversational_agent.zone_tour_flow import options_for_sub_step

    sub = current_sub_step("Z4", 3)
    assert sub.id == "z4_prices"
    _, price_opts, _ = options_for_sub_step("Z4", sub, shop)
    assert len(price_opts) == 4
    ids = {o["id"] for o in price_opts}
    assert "z4_price_bold_red" in ids
    assert all(o.get("sample_prices") for o in price_opts)

    bold = next(o for o in price_opts if o["id"] == "z4_price_bold_red")
    resp = try_handle_zone_tour_message(shop, f"zone option {bold['id']}")
    assert resp is not None
    assert "not saved" not in (resp.get("message") or "").lower()

    cm2 = ConfigManager(shop_uuid=shop)
    cm2.reload()
    assert cm2.tokens.productCards.priceStyle == "boldRed"


def test_exit_zone_customization_clears_active(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "exit-tour-test"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    ZoneTourManager(shop).start()

    resp = try_handle_zone_tour_message(shop, "Exit zone customization")
    assert resp is not None
    assert resp["zone_tour"]["active"] is False
    assert resp["zone_tour"]["status"] == "cancelled"
    assert ZoneTourManager(shop).is_active() is False


def test_skip_through_tour_finishes_with_inactive_panel(tmp_path, monkeypatch):
    """Finishing the last zone returns active: false so the UI panel dismisses."""
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "complete-tour-test"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()

    resp = None
    for _ in range(20):
        if not mgr.is_active():
            break
        step = mgr.current_step()
        if step and step.info_only:
            resp = try_handle_zone_tour_message(shop, "Got it, continue the tour")
        else:
            resp = try_handle_zone_tour_message(shop, "Skip this zone")

    assert not mgr.is_active()
    assert resp is not None
    assert resp["zone_tour"]["active"] is False
