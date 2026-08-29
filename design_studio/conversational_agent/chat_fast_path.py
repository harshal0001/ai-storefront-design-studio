"""Deterministic chat handlers — apply style changes without calling Bedrock.

``run_fast_path()`` tries handlers in priority order and returns a full API dict when
one matches; otherwise ``None`` so ``server.py`` falls through to the Strands agent.

Handler priority (when no active tour):
  0. ``apply_zone_focused_color`` — section-scoped background/surface (runs even with UI focus)
  1. ``apply_focused_element_style`` — element-scoped rules (catalog card border radius, …)
  2. ``apply_direct_style_updates`` — global phrase → token mapping
  3. ``apply_page_color_updates`` — whole-page background / surface colours
  4. ``apply_product_card_fix`` — catalog/showcase card shape fixes
  5. ``try_handle_theme_choice`` — merchant picked a theme package card
  6. ``try_handle_zone_tour_message`` — start tour / tour navigation (when allowed)

When a zone tour is **active**, only the tour handler runs (step 6 first). Unrecognised
tour input returns ``None`` so the agent can help — but direct-style parsers are skipped
so a hex like ``#BE185D`` cannot bypass the current Z1 sub-step.

When ``style_via_agent=True`` (UI focus chip or cross-page request), steps 1–4 are
skipped so the Bedrock agent orchestrates via ``apply_style_tokens`` tools.
"""

from __future__ import annotations

from typing import Any

from .api_response import attach_section_focus, enrich_with_zone_tour
from .chat_session import append_exchange
from .direct_style import apply_direct_style_updates
from .element_focused_style import apply_focused_element_style
from .message_parsers import parse_choose_message, parse_vibe_message, parse_zone_option_id
from .page_colors import apply_page_color_updates
from .zone_focused_colors import apply_zone_focused_color
from .zone_focused_suggestions import (
    apply_focused_color_option,
    apply_focused_layout_option,
    build_focused_suggestions_response,
    classify_focused_request,
    focused_swatch_missed_message,
    get_cached_focus_layout_options,
    get_cached_focus_options,
    resolve_focused_option,
)
from .product_card_requests import apply_product_card_fix
from .section_focus import SectionFocus
from .shop_context import shop_context
from .style_repository import StyleRepository
from .theme_choice_actions import try_handle_theme_choice
from .zone_tour import ZoneTourManager
from .zone_tour_actions import try_handle_zone_tour_message


def record_vibe_selection(merchant_id: str, vibe: str) -> bool:
    """Persist a vibe-pill choice to STYLE_PROFILE (CF-01 / 3.1).

    Merges the new vibe with any existing mood tags (case-insensitive de-dupe) so
    repeated pill clicks accumulate. Returns ``True`` when the profile was written.
    """
    repo = StyleRepository(shop_uuid=merchant_id)
    existing = (repo.get_style_profile(merchant_id) or {}).get("moodTags") or []
    merged = list(existing)
    if not any(v.lower() == vibe.lower() for v in merged):
        merged.append(vibe)
    repo.update_mood_tags(merged, shop_uuid=merchant_id)
    return True


def direct_style_response(
    merchant_id: str,
    user_message: str,
    applied_summary: str,
    focus: SectionFocus | None = None,
) -> dict[str, Any]:
    """Return preview payload after server-side token parse (no Bedrock)."""
    area = f" in **{focus.display_label}**" if focus else ""
    message = f"Done — I've applied those changes to your preview{area} ({applied_summary})."
    append_exchange(merchant_id, user_message, message)
    resp = attach_section_focus(
        {"type": "applied", "message": message},
        merchant_id,
        focus,
    )
    return enrich_with_zone_tour(resp, merchant_id)


def _wrap_handler_response(
    merchant_id: str,
    user_message: str,
    resp: dict[str, Any],
    focus: SectionFocus | None,
) -> dict[str, Any]:
    append_exchange(merchant_id, user_message, resp.get("message", ""))
    return attach_section_focus(resp, merchant_id, focus)


def run_fast_path(
    merchant_id: str,
    message: str,
    focus: SectionFocus | None,
    *,
    allow_zone_tour: bool = True,
    style_via_agent: bool = False,
) -> dict[str, Any] | None:
    """Try handlers in priority order; return API payload or None for agent."""
    text = message.strip()
    if not text:
        return None

    with shop_context(merchant_id):
        # --- Active tour: exclusive handler (blocks direct-style bypass) ---
        if allow_zone_tour and ZoneTourManager(merchant_id).is_active():
            tour_resp = try_handle_zone_tour_message(merchant_id, text)
            if tour_resp:
                append_exchange(merchant_id, text, tour_resp.get("message", ""))
                return tour_resp
            # Swatch clicks must never fall through to theme choice or a silent no-op.
            if parse_zone_option_id(text):
                from .api_response import build_tour_response

                return build_tour_response(
                    merchant_id,
                    "That swatch could not be applied — say **Start zone tour** (or "
                    "**zone-wise customization**) if you have not begun the walkthrough, "
                    "then click the swatch under the latest step message.",
                )
            # Other tour free-text → agent with zone-tour context (server.py)
            return None

        # --- Vibe pill: persist mood tag (CF-01), then let the agent offer mood-matched themes ---
        vibe = parse_vibe_message(text)
        if vibe:
            record_vibe_selection(merchant_id, vibe)
            return None

        # --- Focused zone: colour/layout swatches or agent for ambiguous *style* ---
        if focus and not ZoneTourManager(merchant_id).is_active():
            request_kind = classify_focused_request(text, focus)
            if request_kind in ("color", "layout"):
                sugg = build_focused_suggestions_response(merchant_id, text, focus)
                if sugg.get("color_options") or sugg.get("zone_options"):
                    append_exchange(merchant_id, text, sugg.get("message", ""))
                    return attach_section_focus(sugg, merchant_id, focus)
            # request_kind == "agent" → fall through to Bedrock with UI focus

            option_id = parse_zone_option_id(text) or ""
            choose_name = parse_choose_message(text) or ""
            picked, pick_kind = resolve_focused_option(
                merchant_id,
                focus,
                option_id=option_id,
                name=choose_name or text,
            )
            if picked:
                if pick_kind == "layout":
                    summary = apply_focused_layout_option(merchant_id, picked, focus)
                else:
                    summary = apply_focused_color_option(merchant_id, picked, focus)
                if summary:
                    return direct_style_response(merchant_id, text, summary, focus)
            if choose_name and (
                get_cached_focus_options(merchant_id)
                or get_cached_focus_layout_options(merchant_id)
                or option_id
            ):
                return _wrap_handler_response(
                    merchant_id,
                    text,
                    {
                        "type": "message",
                        "message": focused_swatch_missed_message(choose_name, focus),
                    },
                    focus,
                )

        # --- Zone-scoped colours: apply a named colour to the highlight ---
        if focus:
            applied, summary, _ = apply_zone_focused_color(text, shop_uuid=merchant_id, focus=focus)
            if applied:
                return direct_style_response(merchant_id, text, summary, focus)

        # --- Other deterministic parsers (skipped when UI focus sends work to agent) ---
        if not style_via_agent:
            applied, summary, _ = apply_focused_element_style(
                text, shop_uuid=merchant_id, focus=focus
            )
            if applied:
                return direct_style_response(merchant_id, text, summary, focus)

            applied, summary, _ = apply_direct_style_updates(text, shop_uuid=merchant_id)
            if applied:
                return direct_style_response(merchant_id, text, summary, focus)

            applied, summary, _ = apply_page_color_updates(text, shop_uuid=merchant_id)
            if applied:
                return direct_style_response(merchant_id, text, summary, focus)

            applied, summary, _ = apply_product_card_fix(
                text,
                shop_uuid=merchant_id,
                focus_zone=focus.zone if focus else None,
                focus_element_id=focus.element_id if focus else None,
            )
            if applied:
                label = focus.label if focus else "All Products & Services"
                return direct_style_response(
                    merchant_id,
                    text,
                    f"Product cards ({label}): {summary}",
                    focus,
                )

        # Discovery theme cards only — not zone-focus swatches
        if not (
            focus
            and (
                get_cached_focus_options(merchant_id)
                or get_cached_focus_layout_options(merchant_id)
                or parse_choose_message(text)
            )
        ):
            theme_resp = try_handle_theme_choice(merchant_id, text)
            if theme_resp:
                return _wrap_handler_response(merchant_id, text, theme_resp, focus)

        # Start tour / tour commands when no tour is active yet
        if allow_zone_tour:
            tour_resp = try_handle_zone_tour_message(merchant_id, text)
            if tour_resp:
                append_exchange(merchant_id, text, tour_resp.get("message", ""))
                return tour_resp

    return None
