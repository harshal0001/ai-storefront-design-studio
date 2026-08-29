"""Z6 combinatorial button-style generator (P1)."""

from conversational_agent.zone_dynamic_options import (
    _ensure_z6_combo_catalog,
    generate_z6_button_style_options,
    z6_button_tokens_for_option,
)
from conversational_agent.zone_tour_flow import current_sub_step


def test_z6_combo_catalog_size():
    catalog = _ensure_z6_combo_catalog()
    assert len(catalog) >= 20
    assert any(p["id"].startswith("z6_gen_") for p in catalog)


def test_z6_generated_option_resolves_tokens():
    catalog = _ensure_z6_combo_catalog()
    sample = next(p for p in catalog if p["id"].startswith("z6_gen_"))
    tokens = z6_button_tokens_for_option(sample["id"])
    assert tokens
    assert tokens["shape"] in ("sharp", "subtleRounded", "rounded", "pill")
    assert tokens["style"] in ("filled", "outlined", "soft", "ghost")


def test_generate_z6_button_style_options_mood_ranked(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_DYNAMODB", "false")
    monkeypatch.setattr(
        "conversational_agent.zone_dynamic_options.load_mood_tags",
        lambda _mid: ["modern", "minimal"],
    )
    sub = current_sub_step("Z6", 0)
    assert sub
    opts = generate_z6_button_style_options("z6-gen-shop", limit=4)
    assert len(opts) == 4
    assert all(o.get("what_changes") for o in opts)
