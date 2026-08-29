"""Tour swatch clicks must not re-apply discovery theme packages."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.theme_choice_actions import (
    store_pending_theme_packages,
    try_handle_theme_choice,
)
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_actions import try_handle_zone_tour_message
from conversational_agent.zone_tour_flow import current_sub_step, options_for_sub_step

DISCOVERY = {
    "id": "discovery_tropical",
    "name": "Tropical Oasis",
    "description": "Discovery theme",
    "colors": [
        {"name": "Brand", "hex": "#E85D4C"},
        {"name": "Accent", "hex": "#2D6A4F"},
        {"name": "Page", "hex": "#F8F4EF"},
        {"name": "Panels", "hex": "#FFFFFF"},
    ],
    "heading_font": "Montserrat",
    "body_font": "Roboto",
    "border_radius": "rounded",
}


def test_i_choose_during_tour_does_not_reapply_discovery_theme(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "tour-theme-isolation"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    store_pending_theme_packages(shop, [DISCOVERY])
    mgr = ZoneTourManager(shop)
    mgr.start()
    mgr.ensure_current_sub_step_ready()
    sub = current_sub_step("Z1", mgr.get_sub_step_index())

    theme_resp = try_handle_theme_choice(shop, 'I choose "Tropical Oasis"')
    assert theme_resp is None

    if sub.id == "z1_accent":
        accents, _, _ = options_for_sub_step("Z1", sub, shop)
        resp = try_handle_zone_tour_message(shop, f"zone option {accents[0]['id']}")
        assert resp is not None
        assert "Tropical Oasis" not in (resp.get("message") or "")
        assert "colors, fonts, and shapes" not in (resp.get("message") or "")
        assert mgr.get_sub_step_index() == 2
