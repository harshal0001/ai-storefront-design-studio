"""Tests for mood/theme-driven zone tour option generation."""

from conversational_agent.zone_dynamic_options import (
    build_theme_context,
    generate_color_options_for_sub_step,
    generate_layout_options_for_sub_step,
)
from conversational_agent.zone_tour_flow import current_sub_step
from conversational_agent.config_manager import ConfigManager


def test_generate_z4_showcase_options_use_mood_tags(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "dyn-z4-showcase"
    cm = ConfigManager(shop_uuid=shop)
    cm.tokens.colors.primary = "#C45B28"
    cm.tokens.colors.paletteName = "Warm Workshop"
    cm.save_tokens(cm.tokens, theme_name="Warm Workshop")
    cm.reload()
    monkeypatch.setattr(
        "conversational_agent.zone_dynamic_options.load_mood_tags",
        lambda _mid: ["warm", "cozy"],
    )

    sub = current_sub_step("Z4", 0)
    assert sub and sub.id == "z4_showcase"
    opts = generate_color_options_for_sub_step(shop, "Z4", sub)
    # Warm primary seed → lighter showcase surfaces
    assert all(o["hex"].lower() != "#ffffff" or "white" in o["name"].lower() for o in opts)
    assert len(opts) >= 3
    assert all(o.get("what_changes") for o in opts)
    assert all("Our Products" in o["what_changes"] for o in opts)
    assert opts[0]["id"].startswith("dyn_")


def test_layout_options_ranked_by_mood(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "dyn-layout"
    monkeypatch.setattr(
        "conversational_agent.zone_dynamic_options.load_mood_tags",
        lambda _mid: ["modern", "minimal"],
    )

    sub = current_sub_step("Z2", 0)
    assert sub
    opts = generate_layout_options_for_sub_step(shop, "Z2", sub)
    assert len(opts) >= 2
    ids = [o["id"] for o in opts]
    assert "modern_left" in ids or "minimal_clean" in ids


def test_theme_context_includes_mood_line(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "dyn-ctx"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test Theme")
    monkeypatch.setattr(
        "conversational_agent.zone_dynamic_options.load_mood_tags",
        lambda _mid: ["warm", "artisan"],
    )

    ctx = build_theme_context(shop)
    assert "Test Theme" in ctx["theme_name"] or "Test" in ctx["palette_line"]
    assert "warm" in ctx["mood_line"].lower()
    assert "#" not in ctx["palette_line"]
    assert all("#" not in (c.get("name") or "") for c in ctx["palette_colors"])
