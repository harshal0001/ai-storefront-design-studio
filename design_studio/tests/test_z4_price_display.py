"""Z4-03 price display style tour — four presets, catalogue samples, mood ranking."""

from conversational_agent.config_manager import ConfigManager
from conversational_agent.direct_style import parse_direct_style_updates
from conversational_agent.z4_tour_options import (
    Z4_PRICE_STYLE_PRESETS,
    catalog_sample_price_line,
    generate_z4_price_style_options,
    price_style_for_option_id,
    recommend_price_style_id,
)
from conversational_agent.zone_tour_flow import ZONE_SUB_STEPS


def test_z4_sub_step_price_display_is_four_styles():
    steps = ZONE_SUB_STEPS["Z4"]
    price = steps[3]
    assert price.id == "z4_prices"
    assert price.kind == "layouts"
    assert len(price.option_ids) == 4


def test_price_style_option_ids_map_to_tokens():
    assert price_style_for_option_id("z4_price_bold_red") == "boldRed"
    assert price_style_for_option_id("z4_price_badge_pill") == "badgePill"
    assert len(Z4_PRICE_STYLE_PRESETS) == 4


def test_catalog_sample_prices_in_options(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z4-price-opts"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    opts = generate_z4_price_style_options(shop)
    assert len(opts) == 4
    line = catalog_sample_price_line()
    assert "Cappuccino" in line
    assert "€" in line
    assert all(line in (o.get("sample_prices") or "") for o in opts)


def test_stand_out_more_prefers_bold_red(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z4-stand-out"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    rid = recommend_price_style_id(shop, user_request="make prices stand out more")
    assert rid == "z4_price_bold_red"


def test_premium_mood_prefers_understated(monkeypatch):
    monkeypatch.setattr(
        "conversational_agent.z4_tour_options.load_mood_tags",
        lambda _m: ["premium", "elegant"],
    )
    rid = recommend_price_style_id("any-shop")
    assert rid == "z4_price_understated"


def test_direct_style_stand_out_phrase():
    assert parse_direct_style_updates("make prices stand out more")["price_style"] == "boldRed"


def test_stale_z4_prices_colour_cache_is_regenerated(tmp_path, monkeypatch):
    """Old tours cached accent hex swatches; step 4 must show price style presets."""
    from conversational_agent.zone_tour import ZoneTourManager
    from conversational_agent.zone_tour_flow import (
        options_for_sub_step,
        sub_steps_for_zone,
    )

    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z4-stale-cache"
    sub = sub_steps_for_zone("Z4")[3]
    assert sub.id == "z4_prices"

    mgr = ZoneTourManager(shop)
    mgr.start()
    state = mgr.get_state() or {}
    state["subStepIndex"] = 3
    state["optionCache"] = {
        "subStepId": "z4_prices",
        "colorOptions": [
            {
                "id": "dyn_z4_prices_3dfd097e",
                "name": "Soft Honey",
                "hex": "#E8C4A0",
                "role": "accent",
                "section": "Prices (both sections)",
            }
        ],
        "zoneOptions": [],
    }
    mgr._save(state)

    colors, layouts, _ = options_for_sub_step("Z4", sub, shop)
    assert colors == []
    assert len(layouts) == 4
    assert layouts[0]["id"].startswith("z4_price_")


def test_legacy_dyn_z4_prices_click_resolves(tmp_path, monkeypatch):
    from conversational_agent.zone_tour_flow import resolve_tour_option
    from conversational_agent.zone_tour_flow import sub_steps_for_zone

    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z4-legacy-dyn"
    sub = sub_steps_for_zone("Z4")[3]
    hit = resolve_tour_option(
        shop,
        "Z4",
        sub,
        option_id="dyn_z4_prices_3dfd097e",
    )
    assert hit is not None
    assert hit.get("price_style") == "accentColor"
