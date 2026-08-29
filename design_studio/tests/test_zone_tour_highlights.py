"""Zone tour preview highlight scope — page-wide vs section-scoped."""

from conversational_agent.zone_highlight import (
    PAGE_WIDE_HINT,
    highlight_spec_for_sub_step,
)
from conversational_agent.zone_tour_flow import tour_enrichment_payload
from conversational_agent.config_manager import ConfigManager
from conversational_agent.zone_tour import ZoneTourManager


def test_brand_and_typography_and_buttons_are_page_scope_no_selectors():
    for sub_id in (
        "z1_palette",
        "z1_accent",
        "z1_backdrop",
        "z1_motion",
        "z3_fonts",
        "z6_style",
        "z6_cta_colour",
    ):
        spec = highlight_spec_for_sub_step(sub_id)
        assert spec is not None
        assert spec.scope == "page"
        assert spec.selectors == ()
        assert "throughout" in spec.merchant_hint.lower()


def test_product_showcase_has_section_selectors():
    spec = highlight_spec_for_sub_step("z4_showcase")
    assert spec.scope == "zone"
    assert "#sf-showcase-section" in spec.selectors
    assert spec.merchant_hint != PAGE_WIDE_HINT


def test_hero_bg_targets_banner_not_whole_zone():
    spec = highlight_spec_for_sub_step("z2_hero_bg")
    assert spec.scope == "element"
    assert spec.selectors == (".sf-banner__media",)
    assert ".sf-zone--z2" not in spec.selectors


def test_z4_layout_targets_cards_not_zone_wrapper():
    spec = highlight_spec_for_sub_step("z4_layout")
    assert ".sf-product" in "".join(spec.selectors)
    assert ".sf-zone--z4" not in spec.selectors


def test_tour_enrichment_payload_includes_highlight_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "hl-payload"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()

    flow = tour_enrichment_payload("Z1", 0, merchant_id=shop)
    assert flow["highlight_scope"] == "page"
    assert flow["highlight_selectors"] == []
    assert "throughout" in flow["highlight_hint"].lower()

    mgr.complete_current()
    mgr.complete_current()
    mgr.complete_current()
    flow_z3 = tour_enrichment_payload("Z3", 0, merchant_id=shop)
    assert flow_z3["highlight_scope"] == "page"

    flow_z4 = tour_enrichment_payload("Z4", 0, merchant_id=shop)
    assert flow_z4["highlight_scope"] == "zone"
    assert flow_z4["highlight_selectors"]
