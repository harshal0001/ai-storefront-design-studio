"""Z3 tour — font scale step and text colour step (Z3-02 / Z3-03)."""

from conversational_agent.color_engine import is_accessible
from conversational_agent.zone_dynamic_options import (
    generate_z3_text_colour_options,
    generate_layout_options_for_sub_step,
)
from conversational_agent.zone_option_resolver import find_z3_text_colour_option
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour_flow import options_for_sub_step
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_flow import ZONE_SUB_STEPS, current_sub_step
from conversational_agent.config_manager import ConfigManager


def test_z3_sub_steps_order():
    steps = ZONE_SUB_STEPS["Z3"]
    assert [s.id for s in steps] == ["z3_fonts", "z3_scale", "z3_text_colour"]


def test_z3_scale_generous_click_updates_tokens_and_preview_theme(tmp_path, monkeypatch):
    from conversational_agent.token_mapper import tokens_to_preview_theme
    from conversational_agent.zone_tour import ZoneTourManager
    from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
    from conversational_agent.zone_tour_flow import current_sub_step, options_for_sub_step

    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z3-scale-click"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    while mgr.current_step() and mgr.current_step().code != "Z3":
        mgr.complete_current()
    while current_sub_step("Z3", mgr.get_sub_step_index()).id != "z3_scale":
        mgr.advance_sub_step()
    sub = current_sub_step("Z3", mgr.get_sub_step_index())
    _, layouts, _ = options_for_sub_step("Z3", sub, shop)
    resp = try_handle_zone_tour_message(shop, "zone option z3_scale_generous")
    assert resp is not None
    cm2 = ConfigManager(shop_uuid=shop)
    cm2.reload()
    assert cm2.tokens.typography.scale == "generous"
    assert tokens_to_preview_theme(cm2.tokens)["typeScale"] == "generous"


def test_z3_scale_options_are_three_scales(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z3-scale"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    sub = current_sub_step("Z3", 1)
    assert sub and sub.id == "z3_scale"
    opts = generate_layout_options_for_sub_step(shop, "Z3", sub)
    assert len(opts) == 3
    assert {o["id"] for o in opts} == {
        "z3_scale_compact",
        "z3_scale_standard",
        "z3_scale_generous",
    }


def test_z3_text_colour_options_pass_wcag_aa(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z3-text"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    bg = cm.tokens.colors.surface
    for role in ("heading", "body"):
        opts = generate_z3_text_colour_options(shop, text_role=role)
        assert len(opts) == 4
        names = {o["name"] for o in opts}
        assert "Black" in names or "Charcoal" in names
        assert "Dark grey" in names or "Soft grey" in names
        assert "Brand-tinted" in names
        assert "Warm dark" in names
        for o in opts:
            assert o.get("contrast_ratio")
            assert is_accessible(o["hex"], bg, "AA")


def test_z3_text_heading_then_body_phase(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z3-phase"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    mgr.advance_sub_step()
    mgr.advance_sub_step()
    assert current_sub_step("Z3", mgr.get_sub_step_index()).id == "z3_text_colour"
    assert mgr.get_z3_text_colour_phase() == "heading"
    opts_h = generate_z3_text_colour_options(shop, text_role="heading")
    pick = opts_h[0]
    mgr.apply_selection_to_tokens("Z3", text_primary=pick["hex"])
    mgr.set_z3_text_colour_phase("body")
    assert mgr.get_z3_text_colour_phase() == "body"
    opts_b = generate_z3_text_colour_options(shop, text_role="body")
    assert opts_b[0]["role"] == "text_body"


def test_z3_text_colour_resolve_without_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z3-resolve"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    hit = find_z3_text_colour_option(shop, "z3_txt_heading_dark_grey_0")
    assert hit and hit["role"] == "text_heading"
    assert hit["name"] == "Dark grey"


def test_z3_body_click_with_stale_heading_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z3-body-click"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    while mgr.current_step() and mgr.current_step().code != "Z3":
        mgr.complete_current()
    while current_sub_step("Z3", mgr.get_sub_step_index()).id != "z3_text_colour":
        mgr.advance_sub_step()
    sub = current_sub_step("Z3", mgr.get_sub_step_index())
    heading_opts = generate_z3_text_colour_options(shop, text_role="heading")
    mgr.cache_sub_step_options(sub.id, heading_opts)
    mgr.set_z3_text_colour_phase("body")
    body_pick = generate_z3_text_colour_options(shop, text_role="body")[1]
    assert body_pick["id"].startswith("z3_txt_body_")
    resp = try_handle_zone_tour_message(shop, f"zone option {body_pick['id']}")
    assert resp is not None
    assert "Body text colour" in resp["message"]
    cm.reload()
    assert cm.tokens.colors.textSecondary == body_pick["hex"]
    assert mgr.current_step().code == "Z4"


def test_z3_text_heading_then_body_one_click_each(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z3-two-click"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    while mgr.current_step() and mgr.current_step().code != "Z3":
        mgr.complete_current()
    while current_sub_step("Z3", mgr.get_sub_step_index()).id != "z3_text_colour":
        mgr.advance_sub_step()
    sub = current_sub_step("Z3", mgr.get_sub_step_index())
    options_for_sub_step("Z3", sub, shop)
    heading = generate_z3_text_colour_options(shop, text_role="heading")[0]
    resp_h = try_handle_zone_tour_message(shop, f"zone option {heading['id']}")
    assert resp_h and "Heading text colour" in resp_h["message"]
    assert mgr.get_z3_text_colour_phase() == "body"
    body = generate_z3_text_colour_options(shop, text_role="body")[0]
    resp_b = try_handle_zone_tour_message(shop, f"zone option {body['id']}")
    assert resp_b and "Body text colour" in resp_b["message"]
    cm.reload()
    assert cm.tokens.colors.textPrimary == heading["hex"]
    assert cm.tokens.colors.textSecondary == body["hex"]
