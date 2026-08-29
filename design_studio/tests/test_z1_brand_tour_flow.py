"""Z1 Brand Colours tour — palette cards, accents, backdrops, motion (Z1-01…Z1-07)."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.harmony_feedback import assess_brand_colours
from conversational_agent.style_tokens import StyleTokens
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_flow import (
    current_sub_step,
    options_for_sub_step,
    sub_steps_for_zone,
)
from conversational_agent.z1_tour_options import (
    Z1_BACKDROP_PRESETS,
    Z1_MOTION_PRESETS,
    generate_z1_accent_options,
    generate_z1_backdrop_options,
    generate_z1_motion_options,
    generate_z1_palette_options,
    z1_motion_for_option,
    z1_palette_already_configured,
)


def test_z1_sub_step_sequence():
    ids = [s.id for s in sub_steps_for_zone("Z1")]
    assert ids == ["z1_palette", "z1_accent", "z1_backdrop", "z1_motion"]


def test_z1_palette_generates_theme_packages(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-palette-opts"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    packages = generate_z1_palette_options(shop, limit=5)
    assert len(packages) >= 4
    assert all(p.get("colors") for p in packages)
    assert packages[0]["id"].startswith("z1_palette_")


def test_z1_backdrop_named_presets(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-backdrop"
    opts = generate_z1_backdrop_options(shop)
    names = {o["name"] for o in opts}
    assert names == {p["name"] for p in Z1_BACKDROP_PRESETS}


def test_z1_accent_includes_pairing_note(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-accent-note"
    cm = ConfigManager(shop_uuid=shop)
    cm.tokens.colors.primary = "#2563EB"
    cm.save_tokens(cm.tokens, theme_name="Test")
    opts = generate_z1_accent_options(shop)
    assert opts
    assert opts[0].get("pairing_note")


def test_z1_motion_presets_and_token_map():
    opts = generate_z1_motion_options()
    assert len(opts) == len(Z1_MOTION_PRESETS)
    assert z1_motion_for_option("z1_motion_fade") == "fadeTint"
    assert z1_motion_for_option("z1_motion_none") == "none"


def test_skip_z1_palette_when_already_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-skip-palette"
    cm = ConfigManager(shop_uuid=shop)
    cm.tokens.colors.paletteName = "Nordic Calm"
    cm.tokens.colors.primary = "#1E3A5F"
    cm.save_tokens(cm.tokens, theme_name="Nordic Calm")
    cm.reload()
    assert z1_palette_already_configured(cm.tokens)

    mgr = ZoneTourManager(shop)
    mgr.start()
    sub = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub.id == "z1_accent"


def test_z1_accent_apply_advances_when_primary_bg_already_fail(tmp_path, monkeypatch):
    """Accent step must not block on palette/theme contrast issues from step 1."""
    from conversational_agent.harmony_feedback import assess_brand_colours_for_sub_step
    from conversational_agent.zone_tour_actions import try_handle_zone_tour_message

    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-accent-harmony"
    cm = ConfigManager(shop_uuid=shop)
    cm.tokens.colors.primary = "#8B7B9A"
    cm.tokens.colors.accent = "#8B7B9A"
    cm.tokens.colors.background = "#9A95A8"
    cm.tokens.colors.surface = "#FFFFFF"
    cm.tokens.colors.paletteName = "Dynamic Triad"
    cm.save_tokens(cm.tokens, theme_name="Dynamic Triad")

    full = assess_brand_colours_for_sub_step("z1_palette", cm.tokens)
    assert full.blocked is True

    accent_only = assess_brand_colours_for_sub_step("z1_accent", cm.tokens)
    assert accent_only.blocked is False

    mgr = ZoneTourManager(shop)
    mgr.start()
    mgr.ensure_current_sub_step_ready()
    sub = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub.id == "z1_accent"
    accents, _, _ = options_for_sub_step("Z1", sub, shop)
    resp = try_handle_zone_tour_message(shop, f"zone option {accents[0]['id']}")
    assert resp is not None
    assert mgr.get_sub_step_index() == 2
    assert "not saved" not in (resp.get("message") or "").lower()


def test_z1_backdrop_apply_saves_and_updates_preview(tmp_path, monkeypatch):
    """Light brand on white must still save backdrop and advance (step 3)."""
    from conversational_agent.harmony_feedback import assess_brand_colours_for_sub_step
    from conversational_agent.zone_tour_actions import try_handle_zone_tour_message

    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-backdrop-apply"
    cm = ConfigManager(shop_uuid=shop)
    cm.tokens.colors.primary = "#E8D5A3"
    cm.tokens.colors.accent = "#C4B5E8"
    cm.tokens.colors.background = "#2A6B6B"
    cm.tokens.colors.surface = "#FFFFFF"
    cm.tokens.colors.paletteName = "Summer Breeze"
    cm.save_tokens(cm.tokens, theme_name="Summer Breeze")

    preview_white = cm.tokens.model_copy(deep=True)
    preview_white.colors.background = "#FFFFFF"
    assert assess_brand_colours(preview_white).blocked is True
    assert assess_brand_colours_for_sub_step("z1_backdrop", preview_white).blocked is False

    mgr = ZoneTourManager(shop)
    mgr.start()
    mgr.advance_sub_step()
    sub = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub.id == "z1_backdrop"
    backdrops, _, _ = options_for_sub_step("Z1", sub, shop)
    white = next(o for o in backdrops if o["id"] == "z1_bg_pure_white")
    resp = try_handle_zone_tour_message(shop, f"zone option {white['id']}")
    assert resp is not None
    assert "not saved" not in (resp.get("message") or "").lower()
    assert mgr.get_sub_step_index() == 3

    cm2 = ConfigManager(shop_uuid=shop)
    cm2.reload()
    assert cm2.tokens.colors.background.upper() == "#FFFFFF"


def test_harmony_blocks_near_identical_primary_and_background():
    tokens = StyleTokens()
    tokens.colors.primary = "#F5F5F5"
    tokens.colors.background = "#F8F8F8"
    tokens.colors.textPrimary = "#111111"
    tokens.colors.surface = "#FFFFFF"
    tokens.colors.accent = "#333333"
    result = assess_brand_colours(tokens)
    assert result.blocked is True


def test_z1_accent_option_id_click_applies_and_advances(tmp_path, monkeypatch):
    """Clicks like ``zone option z1_acc_complement_0_0`` must not fall through to Bedrock."""
    from conversational_agent.zone_tour_actions import try_handle_zone_tour_message

    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-accent-click"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    sub0 = current_sub_step("Z1", 0)
    _, _, packages = options_for_sub_step("Z1", sub0, shop)
    try_handle_zone_tour_message(shop, f"zone option {packages[0]['id']}")

    sub1 = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub1.id == "z1_accent"
    accent_opts, _, _ = options_for_sub_step("Z1", sub1, shop)
    oid = accent_opts[0]["id"]
    assert oid.startswith("z1_acc_")

    resp = try_handle_zone_tour_message(shop, f"zone option {oid}")
    assert resp is not None
    assert resp.get("type") == "zone_tour"
    assert mgr.get_sub_step_index() == 2
    assert "preview_html" in resp or "preview" in str(resp.keys()).lower()

    cm2 = ConfigManager(shop_uuid=shop)
    cm2.reload()
    assert cm2.tokens.colors.accent.lower() == accent_opts[0]["hex"].lower()


def test_z1_motion_apply_via_tour(tmp_path, monkeypatch):
    from conversational_agent.zone_tour_actions import try_handle_zone_tour_message

    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z1-motion-apply"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(3):
        mgr.advance_sub_step()
    sub = current_sub_step("Z1", mgr.get_sub_step_index())
    assert sub.id == "z1_motion"
    _, layouts, _ = options_for_sub_step("Z1", sub, shop)
    resp = try_handle_zone_tour_message(shop, f"zone option {layouts[0]['id']}")
    assert resp is not None
    cm2 = ConfigManager(shop_uuid=shop)
    cm2.reload()
    assert cm2.tokens.motion.transition == z1_motion_for_option(layouts[0]["id"])
