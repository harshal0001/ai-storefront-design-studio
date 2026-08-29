"""Apply theme package clicks without Bedrock.

Handles ``I choose "Theme Name"`` from React theme cards. Pending LLM-generated packages
are cached in-process (``_pending_theme_packages``); catalogue packages load from DynamoDB.

After apply, may auto-start the zone tour via ``_maybe_start_zone_tour()`` (todo: make optional).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .section_focus import SectionFocus

from .color_engine import is_valid_google_font, is_valid_color
from .config_manager import ConfigManager
from .models import BorderRadius, Spacing
from .style_repository import StyleRepository
from .api_response import build_applied_response, enrich_with_zone_tour
from .message_parsers import parse_choose_message
from .token_mapper import build_tokens_from_theme_save, clear_zone_scopes, derive_text_colors
from .zone_tour import TOUR_STEPS, ZoneTourManager

# In-memory cache of packages last shown in chat (merchant_id -> list of dicts)
_pending_theme_packages: dict[str, list[dict]] = {}

_RADIUS_VALUES = {r.value for r in BorderRadius}
_SPACING_VALUES = {s.value for s in Spacing}

_DEFAULT_HEADING_FONT = "Playfair Display"
_DEFAULT_BODY_FONT = "Lato"


def store_pending_theme_packages(merchant_id: str, packages: list[dict]) -> None:
    """Remember theme cards the UI last rendered so clicks can apply without the LLM."""
    if packages:
        _pending_theme_packages[merchant_id] = packages


def clear_pending_theme_packages(merchant_id: str) -> None:
    _pending_theme_packages.pop(merchant_id, None)


def _norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return slug.strip("_")


def _norm_preset(value: str, default: str, allowed: set[str]) -> str:
    v = (value or default).strip().lower()
    return v if v in allowed else default


def _resolve_font(name: str, fallback: str) -> str:
    if name and is_valid_google_font(name):
        return name
    if fallback and is_valid_google_font(fallback):
        return fallback
    return _DEFAULT_BODY_FONT if fallback == _DEFAULT_BODY_FONT else _DEFAULT_HEADING_FONT


def _map_colors(colors: list[dict]) -> dict[str, str]:
    """Map agent theme package colors to save_theme roles.

    Prompt order (5): primary, background, secondary, accent, surface.
    With fewer swatches we keep the same priority and derive surface from background.
    """
    if not colors:
        raise ValueError("Theme package has no colors")

    def hex_at(i: int, default_i: int = 0) -> str:
        idx = i if i < len(colors) else default_i
        return colors[idx]["hex"]

    def name_at(i: int, default_i: int = 0) -> str:
        idx = i if i < len(colors) else default_i
        return colors[idx].get("name") or "Color"

    n = len(colors)
    if n >= 5:
        return {
            "primary_color": hex_at(0),
            "primary_color_name": name_at(0),
            "background_color": hex_at(1),
            "background_color_name": name_at(1),
            "secondary_color": hex_at(2),
            "secondary_color_name": name_at(2),
            "accent_color": hex_at(3),
            "accent_color_name": name_at(3),
            "surface_color": hex_at(4),
            "surface_color_name": name_at(4),
        }
    if n == 4:
        # UI swatch order: brand, support, accent, page background
        return {
            "primary_color": hex_at(0),
            "primary_color_name": name_at(0),
            "secondary_color": hex_at(1),
            "secondary_color_name": name_at(1),
            "accent_color": hex_at(2),
            "accent_color_name": name_at(2),
            "background_color": hex_at(3),
            "background_color_name": name_at(3),
            "surface_color": hex_at(3),
            "surface_color_name": name_at(3),
        }
    if n == 3:
        return {
            "primary_color": hex_at(0),
            "primary_color_name": name_at(0),
            "background_color": hex_at(1),
            "background_color_name": name_at(1),
            "secondary_color": hex_at(0),
            "secondary_color_name": name_at(0),
            "accent_color": hex_at(2),
            "accent_color_name": name_at(2),
            "surface_color": hex_at(1),
            "surface_color_name": name_at(1, 1),
        }
    # 1–2 swatches: repeat for missing roles
    primary = hex_at(0)
    bg = hex_at(1, 0) if n > 1 else hex_at(0)
    return {
        "primary_color": primary,
        "primary_color_name": name_at(0),
        "background_color": bg,
        "background_color_name": name_at(1, 0) if n > 1 else name_at(0),
        "secondary_color": primary,
        "secondary_color_name": name_at(0),
        "accent_color": primary,
        "accent_color_name": name_at(0),
        "surface_color": bg,
        "surface_color_name": name_at(1, 0) if n > 1 else name_at(0),
    }


def _find_pending_package(merchant_id: str, choice_name: str) -> dict | None:
    pending = _pending_theme_packages.get(merchant_id) or []
    key = _norm_name(choice_name)
    for pkg in pending:
        if _norm_name(pkg.get("name", "")) == key:
            return pkg
    return None


def _find_catalog_package(choice_name: str, shop_uuid: str) -> dict | None:
    repo = StyleRepository(shop_uuid=shop_uuid)
    if not repo.enabled:
        return None
    key = _norm_name(choice_name)
    slug = _slugify(choice_name)
    for pkg in repo.list_theme_packages():
        if _norm_name(pkg.get("displayName", "")) == key:
            return pkg
        if pkg.get("packageId") == slug:
            return pkg
    direct = repo.get_theme_package(slug)
    return direct


def _apply_catalog_package(merchant_id: str, pkg: dict, mood_summary: str = "") -> str:
    package_id = pkg.get("packageId", "")
    repo = StyleRepository(shop_uuid=merchant_id)
    tokens = repo.get_theme_package_tokens(package_id)
    if not tokens:
        raise ValueError(f"Package '{package_id}' has no tokens")

    tokens = clear_zone_scopes(tokens)
    name = pkg.get("displayName", package_id)
    cm = ConfigManager(shop_uuid=merchant_id)
    cm.save_tokens(
        tokens,
        theme_name=name,
        mood_summary=mood_summary,
        based_on_package_id=package_id,
    )
    cm.reload()
    return name


def _apply_custom_package(merchant_id: str, pkg: dict) -> str:
    colors = pkg.get("colors") or []
    for c in colors:
        if not is_valid_color(c.get("hex", "")):
            raise ValueError(f"Invalid color in theme: {c.get('hex')}")

    mapped = _map_colors(colors)
    background = mapped["background_color"]
    text_primary, text_secondary = derive_text_colors(background)

    heading_font = _resolve_font(pkg.get("heading_font", ""), _DEFAULT_HEADING_FONT)
    body_font = _resolve_font(pkg.get("body_font", ""), _DEFAULT_BODY_FONT)
    border_radius = _norm_preset(pkg.get("border_radius", ""), "rounded", _RADIUS_VALUES)
    spacing = _norm_preset(pkg.get("spacing", ""), "normal", _SPACING_VALUES)

    color_fields = {k: v for k, v in mapped.items() if not k.endswith("_name")}
    tokens = build_tokens_from_theme_save(
        theme_name=pkg.get("name", "Custom theme"),
        text_primary=text_primary,
        text_secondary=text_secondary,
        heading_font=heading_font,
        body_font=body_font,
        border_radius=border_radius,
        spacing=spacing,
        **color_fields,
    )
    tokens.colors.paletteName = pkg.get("name", "")

    cm = ConfigManager(shop_uuid=merchant_id)
    cm.save_tokens(
        tokens,
        theme_name=pkg.get("name", "Custom theme"),
        mood_summary=pkg.get("description", ""),
    )
    cm.reload()
    return pkg.get("name", "Custom theme")


def _maybe_start_zone_tour(merchant_id: str) -> str:
    cm = ConfigManager(shop_uuid=merchant_id)
    mgr = ZoneTourManager(merchant_id, cm._repo, config_path=cm.config_path)
    if mgr.is_active():
        return ""
    # Discovery theme cards must not override tour swatch resolution.
    clear_pending_theme_packages(merchant_id)
    progress = mgr.start()
    step = TOUR_STEPS[0]
    return (
        f"\n\nNext up: **{step.name}** — we'll fine-tune each area one step at a time "
        f"({progress['editable_completed']}/{progress['editable_total']} done)."
    )


def apply_theme_choice(merchant_id: str, choice_name: str) -> str:
    """Apply a theme by display name; raises ValueError if not found."""
    pending = _find_pending_package(merchant_id, choice_name)
    if pending:
        return _apply_custom_package(merchant_id, pending)

    catalog = _find_catalog_package(choice_name, merchant_id)
    if catalog:
        return _apply_catalog_package(merchant_id, catalog)

    raise ValueError(
        f'No theme "{choice_name}" in this session. Pick one of the cards above, '
        "or ask for new theme options."
    )


def try_handle_theme_choice(
    merchant_id: str,
    message: str,
    *,
    focus: "SectionFocus | None" = None,
) -> dict[str, Any] | None:
    """Handle `I choose "Theme Name"` from discovery/agent theme cards (not zone tour)."""
    # During the zone tour, swatches use ``zone option <id>`` — never re-apply discovery themes.
    if ZoneTourManager(merchant_id).is_active():
        return None

    choice_name = parse_choose_message(message)
    if not choice_name:
        return None

    if focus is not None:
        from .zone_focused_suggestions import (
            apply_focused_color_option,
            apply_focused_layout_option,
            focused_swatch_missed_message,
            get_cached_focus_layout_options,
            get_cached_focus_options,
            resolve_focused_option,
        )

        swatch, pick_kind = resolve_focused_option(merchant_id, focus, name=choice_name)
        if swatch:
            if pick_kind == "layout":
                summary = apply_focused_layout_option(merchant_id, swatch, focus)
            else:
                summary = apply_focused_color_option(merchant_id, swatch, focus)
            if summary:
                area = focus.display_label or focus.zone
                msg = (
                    f"Done — applied **{swatch.get('name', choice_name)}** "
                    f"to **{area}** ({summary.rstrip('.')})."
                )
                return enrich_with_zone_tour(build_applied_response(merchant_id, msg), merchant_id)
        if get_cached_focus_options(merchant_id) or get_cached_focus_layout_options(merchant_id):
            return {
                "type": "message",
                "message": focused_swatch_missed_message(choice_name, focus),
            }

    try:
        theme_name = apply_theme_choice(merchant_id, choice_name)
    except ValueError as e:
        return {
            "type": "message",
            "message": str(e),
        }

    tour_note = _maybe_start_zone_tour(merchant_id)
    msg = (
        f'Applied **"{theme_name}"** to your preview — colors, fonts, and shapes are updated.'
        f"{tour_note}"
    )
    return enrich_with_zone_tour(build_applied_response(merchant_id, msg), merchant_id)
