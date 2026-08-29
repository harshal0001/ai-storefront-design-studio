"""Round-trip tests for ConfigManager persistence — no AWS, no LLM.

ConfigManager defaults to CWD-relative `storefront_config.json`. These tests
always pass an explicit `tmp_path` so they never touch the developer's CWD.
JSON fallback is disabled globally in ``tests/conftest.py`` (USE_DYNAMODB=false).
"""

from unittest.mock import MagicMock

from conversational_agent.config_manager import ConfigManager
from conversational_agent.models import (
    BorderRadius,
    Spacing,
    StorefrontConfig,
    Zone,
    ZoneStyle,
)
from conversational_agent.style_tokens import StyleTokens
from conversational_agent.token_mapper import recompute_quality_flags


def test_empty_config_when_file_does_not_exist(tmp_path):
    cm = ConfigManager(config_path=tmp_path / "missing.json")
    config = cm.config
    assert isinstance(config, StorefrontConfig)
    assert config.theme_name == ""
    assert config.default_border_radius == BorderRadius.ROUNDED
    assert config.default_spacing == Spacing.NORMAL


def test_save_then_reload_roundtrips_theme(tmp_path):
    path = tmp_path / "config.json"
    cm = ConfigManager(config_path=path)
    cm.config.theme_name = "Tuscan Workshop"
    cm.config.theme_description = "Warm and rustic"
    cm.config.primary_color = "#C45B28"
    cm.config.primary_color_name = "Terracotta Sun"
    cm.config.heading_font = "Playfair Display"
    cm.config.body_font = "Lato"
    cm.config.default_border_radius = BorderRadius.SOFT
    cm.config.default_spacing = Spacing.SPACIOUS
    cm.save()

    assert path.exists()

    reloaded = ConfigManager(config_path=path)
    cfg = reloaded.config
    assert cfg.theme_name == "Tuscan Workshop"
    assert cfg.theme_description == "Warm and rustic"
    assert cfg.primary_color == "#C45B28"
    assert cfg.primary_color_name == "Terracotta Sun"
    assert cfg.heading_font == "Playfair Display"
    assert cfg.body_font == "Lato"
    assert cfg.default_border_radius == BorderRadius.SOFT
    assert cfg.default_spacing == Spacing.SPACIOUS


def test_zone_overrides_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cm = ConfigManager(config_path=path)
    cm.config.zone_overrides[Zone.HERO_BANNER] = ZoneStyle(
        primary_color="#112233",
        background_color="#AABBCC",
        border_radius=BorderRadius.PILL,
    )
    cm.save()

    reloaded = ConfigManager(config_path=path).config
    assert Zone.HERO_BANNER in reloaded.zone_overrides
    override = reloaded.zone_overrides[Zone.HERO_BANNER]
    assert override.primary_color == "#112233"
    assert override.background_color == "#AABBCC"
    assert override.border_radius == BorderRadius.PILL


def test_apply_zone_uses_zone_scope_without_changing_global_colors(tmp_path):
    path = tmp_path / "config.json"
    shop = "scoped-zone-shop"
    cm = ConfigManager(shop_uuid=shop, config_path=path)
    cm.tokens.colors.accent = "#111111"
    cm.tokens.colors.background = "#FFFFFF"
    cm.save_tokens(cm.tokens, theme_name="Scoped Test")
    cm.reload()

    cm.apply_zone(
        Zone.PRODUCTS_GRID,
        ZoneStyle(primary_color="#0D9488", background_color="#F0FDFA"),
    )

    reloaded = ConfigManager(shop_uuid=shop, config_path=path)
    reloaded.reload()
    assert reloaded.tokens.colors.accent == "#111111"
    assert reloaded.tokens.colors.background == "#FFFFFF"
    assert reloaded.tokens.zoneScopes["Z4S"].accent == "#0D9488"
    assert reloaded.tokens.zoneScopes["Z4C"].accent == "#0D9488"
    assert reloaded.tokens.zoneScopes["Z4S"].background == "#F0FDFA"
    assert reloaded.tokens.zoneScopes["Z4C"].background == "#F0FDFA"


def test_save_tokens_default_summary_omits_unknown_zones(tmp_path):
    cm = ConfigManager(shop_uuid="summary-shop", config_path=tmp_path / "config.json")
    repo = MagicMock()
    repo.enabled = True
    repo.save_tokens_with_history.return_value = 1
    cm._repo = repo

    cm.save_tokens(StyleTokens(), theme_name="Scoped Test")

    assert repo.save_tokens_with_history.call_args.kwargs["change_summary"] == {
        "humanSummary": 'Applied theme "Scoped Test".'
    }


def test_save_default_summary_omits_unknown_zones(tmp_path):
    cm = ConfigManager(shop_uuid="summary-shop", config_path=tmp_path / "config.json")
    repo = MagicMock()
    repo.enabled = True
    repo.save_tokens_with_history.return_value = 1
    cm._repo = repo
    cm._config = StorefrontConfig(theme_name="Config Theme")

    cm.save()

    assert repo.save_tokens_with_history.call_args.kwargs["change_summary"] == {
        "humanSummary": 'Applied theme "Config Theme".'
    }


def _tokens_with_colors(**overrides):
    tokens = StyleTokens()
    tokens.colors = tokens.colors.model_copy(update=overrides)
    return tokens


def test_recompute_quality_flags_passing_palette():
    tokens = _tokens_with_colors(
        primary="#000000",
        background="#FFFFFF",
        surface="#FFFFFF",
        textPrimary="#000000",
        harmonyChecked=False,
        contrastAA=False,
    )
    out = recompute_quality_flags(tokens)
    assert out.colors.harmonyChecked is True
    assert out.colors.contrastAA is True


def test_recompute_quality_flags_clears_stale_flags_on_failing_palette():
    # White on white passes nothing; stale True flags must be cleared.
    tokens = _tokens_with_colors(
        primary="#FFFFFF",
        background="#FFFFFF",
        surface="#FFFFFF",
        textPrimary="#FFFFFF",
        harmonyChecked=True,
        contrastAA=True,
    )
    out = recompute_quality_flags(tokens)
    assert out.colors.harmonyChecked is False
    assert out.colors.contrastAA is False


def test_save_tokens_recomputes_quality_flags_on_any_edit_path(tmp_path):
    # 2.9: flags must be set on save regardless of the path that built the tokens.
    # Hand save_tokens an inaccessible palette carrying stale True flags.
    cm = ConfigManager(shop_uuid="flags-shop", config_path=tmp_path / "config.json")
    cm.save_tokens(
        _tokens_with_colors(
            primary="#FFFFFF",
            background="#FFFFFF",
            surface="#FFFFFF",
            textPrimary="#FFFFFF",
            harmonyChecked=True,
            contrastAA=True,
        ),
        theme_name="Flags",
    )
    assert cm.tokens.colors.harmonyChecked is False
    assert cm.tokens.colors.contrastAA is False
