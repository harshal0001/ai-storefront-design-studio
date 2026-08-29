"""Tour advances after agent apply or typed hex — not only UI swatch clicks."""

from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_flow import current_sub_step
from conversational_agent.zone_tour_advance import (
    advance_tour_after_sub_step_apply,
    apply_fulfills_current_sub_step,
    maybe_advance_after_style_tokens,
)
from conversational_agent.config_manager import ConfigManager


def _reach_z3_text_colour(shop: str) -> ZoneTourManager:
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(2):
        mgr.complete_current()
    assert mgr.current_step().code == "Z3"
    assert current_sub_step("Z3", 0).id == "z3_fonts"
    mgr.advance_sub_step()
    assert current_sub_step("Z3", mgr.get_sub_step_index()).id == "z3_scale"
    mgr.advance_sub_step()
    assert current_sub_step("Z3", mgr.get_sub_step_index()).id == "z3_text_colour"
    return mgr


def test_apply_style_tokens_advances_from_z3_scale(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "tool-advance"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(2):
        mgr.complete_current()
    mgr.advance_sub_step()
    assert current_sub_step("Z3", mgr.get_sub_step_index()).id == "z3_scale"
    idx_before = mgr.get_sub_step_index()

    note = maybe_advance_after_style_tokens(mgr, font_scale="generous", zone_code="Z3")
    assert note
    assert mgr.get_sub_step_index() != idx_before


def test_apply_fulfills_z3_scale(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "fulfill-z3"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(2):
        mgr.complete_current()
    mgr.advance_sub_step()
    assert apply_fulfills_current_sub_step(
        mgr,
        apply_zone="Z3",
        applied_fields={"font_scale"},
    )


def test_advance_after_sub_step_moves_to_next_zone(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "advance-zone"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    mgr = _reach_z3_text_colour(shop)
    mgr.apply_selection_to_tokens("Z3", text_primary="#111111")
    mgr.set_z3_text_colour_phase("body")
    mgr.apply_selection_to_tokens("Z3", text_secondary="#333333")
    note = advance_tour_after_sub_step_apply(mgr)
    assert note
    assert mgr.current_step().code == "Z4"
