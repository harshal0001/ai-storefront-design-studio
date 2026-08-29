"""Typography font step — more options must return new pairing ids."""

from conversational_agent.zone_dynamic_options import refresh_options_for_current_sub_step
from conversational_agent.zone_tour import ZoneTourManager
from conversational_agent.zone_tour_flow import current_sub_step, options_for_sub_step
from conversational_agent.config_manager import ConfigManager


def _reach_z3_fonts(shop: str) -> ZoneTourManager:
    mgr = ZoneTourManager(shop)
    mgr.start()
    for _ in range(2):
        mgr.complete_current()
    assert mgr.current_step().code == "Z3"
    assert current_sub_step("Z3", 0).id == "z3_fonts"
    return mgr


def test_z3_more_options_returns_new_font_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    shop = "z3-more"
    cm = ConfigManager(shop_uuid=shop)
    cm.save_tokens(cm.tokens, theme_name="Test")
    _reach_z3_fonts(shop)
    sub = current_sub_step("Z3", 0)

    _, first, _ = options_for_sub_step("Z3", sub, shop)
    first_ids = {o["id"] for o in first}
    assert len(first_ids) == 4

    _, second, _, lead = refresh_options_for_current_sub_step(
        shop,
        "give more options stylish",
        must_differ_from=first_ids,
    )
    second_ids = {o["id"] for o in second}
    assert second_ids
    assert not second_ids.issubset(first_ids) or second_ids != first_ids
    assert "button" not in lead.lower()


def test_rank_presets_does_not_resurface_excluded(tmp_path, monkeypatch):
    from conversational_agent.zone_dynamic_options import _rank_presets
    from conversational_agent.zone_presets import ZONE_TOUR_PRESETS

    presets = ZONE_TOUR_PRESETS["Z3"]
    exclude = {p["id"] for p in presets}
    ranked = _rank_presets(presets, ["modern"], limit=4, exclude_ids=exclude, batch=1)
    assert ranked == [] or not {p["id"] for p in ranked}.issubset(exclude)
