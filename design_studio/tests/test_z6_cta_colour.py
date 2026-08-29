"""Z6 CTA colour — preview uses secondaryColor; dyn_* ids must resolve."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.token_mapper import tokens_to_preview_theme
from conversational_agent.zone_dynamic_options import generate_color_options_for_sub_step
from conversational_agent.zone_option_resolver import find_generated_color_option
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour_flow import ZONE_SUB_STEPS, current_sub_step


def _reach_z6_cta(shop: str) -> ZoneTourManager:
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(5):
        mgr.complete_current()
    mgr.advance_sub_step()
    mgr.advance_sub_step()
    assert current_sub_step("Z6", mgr.get_sub_step_index()).id == "z6_cta_colour"
    return mgr


def test_z6_cta_dyn_resolve_without_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z6-cta-resolve"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    sub = ZONE_SUB_STEPS["Z6"][2]
    opts = generate_color_options_for_sub_step(shop, "Z6", sub)
    pick = opts[0]
    assert pick["id"].startswith("dyn_z6_cta_colour_")
    hit = find_generated_color_option(shop, "Z6", sub, pick["id"])
    assert hit and hit["hex"] == pick["hex"]


def test_z6_cta_click_updates_secondary_and_preview(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z6-cta-click"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    _reach_z6_cta(shop)
    sub = current_sub_step("Z6", ZoneTourManager(shop).get_sub_step_index())
    pick = generate_color_options_for_sub_step(shop, "Z6", sub)[2]
    before = cm.tokens.colors.secondary
    resp = try_handle_zone_tour_message(shop, f"zone option {pick['id']}")
    assert resp is not None
    assert "couldn't apply" not in (resp.get("message") or "").lower()
    cm.reload()
    assert cm.tokens.colors.secondary.lower() == pick["hex"].lower()
    assert cm.tokens.colors.secondary.lower() != before.lower()
    theme = tokens_to_preview_theme(cm.tokens)
    assert theme["secondaryColor"].lower() == pick["hex"].lower()
    assert theme["zoneScopes"]["Z6"]["secondaryColor"].lower() == pick["hex"].lower()


def test_z6_cta_stale_cache_still_applies(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z6-cta-stale"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = _reach_z6_cta(shop)
    sub = current_sub_step("Z6", mgr.get_sub_step_index())
    pick = generate_color_options_for_sub_step(shop, "Z6", sub)[0]
    mgr.cache_sub_step_options("z4_showcase", [{"id": "wrong", "hex": "#000000"}])
    resp = try_handle_zone_tour_message(shop, f"zone option {pick['id']}")
    assert resp is not None
    cm.reload()
    assert cm.tokens.colors.secondary.lower() == pick["hex"].lower()
