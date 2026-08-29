"""Server-side zone tour actions — no Bedrock required for preset clicks.

Handles swatch clicks, free-text colour names, skip/exit phrases, and Z5 "got it".
Advances tour state via ``ZoneTourManager`` and returns API payloads through
``api_response.build_tour_response`` / ``build_tour_finished_response``.

When the tour ends, responses include ``zone_tour: { active: false }`` so the UI
clears tour progress chrome. Swatches are attached to each chat response for the
active sub-step. Unmatched free-text (including “more options”) is sent to the
Bedrock agent, which uses ``refresh_zone_tour_options``, ``apply_style_tokens``, etc.
"""

from __future__ import annotations

from typing import Any

from .api_response import build_tour_finished_response, build_tour_response
from .message_parsers import (
    CHOOSE_RE,
    EXIT_ZONE_TOUR_RE,
    GOT_IT_CONTINUE_RE,
    SKIP_ZONE_RE,
    START_ZONE_TOUR_RE,
    parse_skip_sub_step_target,
    parse_zone_option_id,
    wants_skip_sub_step,
)
from .zone_tour import Z5_POSITIVE_SCRIPT, ZoneTourManager
from .zone_tour_flow import (
    build_sub_step_message,
    color_choice_from_hex,
    current_sub_step,
    extract_hex_from_text,
    match_sub_step_choice,
    normalize_tour_input,
    sub_steps_for_zone,
)
from .zone_dynamic_options import sub_step_explanation
from .zone_highlight import preview_check_hint, tour_complete_message
from .zone_tour_color_apply import (
    apply_tour_color_choice,
    color_apply_summary,
    preview_tokens_for_z1_color,
)
from .zone_tour_swatch_errors import (
    should_force_refresh_options,
    swatch_failure_hint,
)


def _step_intro(step) -> str:
    if step.info_only:
        return Z5_POSITIVE_SCRIPT
    sub = current_sub_step(step.code, 0)
    if not sub:
        return f"**{step.name}** — {step.headline}"
    return build_sub_step_message(step.code, sub, intro=True)


def _next_step_message(mgr: ZoneTourManager, step) -> str:
    sub_idx = mgr.get_sub_step_index()
    sub = current_sub_step(step.code, sub_idx)
    if not sub:
        return _step_intro(step)
    if sub_idx == 0:
        return build_sub_step_message(step.code, sub, intro=True)
    return sub.prompt


def _with_preview_hint(summary: str, sub_step_id: str) -> str:
    return f"{summary.rstrip('.')}. {preview_check_hint(sub_step_id)}"


def _handle_skip_sub_step(
    mgr: ZoneTourManager,
    merchant_id: str,
    text: str,
) -> dict[str, Any] | None:
    """Advance to the next sub-step (or jump to step N) without applying a choice."""
    if not mgr.can_skip_sub_step():
        return None

    step = mgr.current_step()
    if not step:
        return None
    zone = step.code
    sub_idx_before = mgr.get_sub_step_index()
    sub_before = current_sub_step(zone, sub_idx_before)
    total = len(sub_steps_for_zone(zone))

    target = parse_skip_sub_step_target(text)
    if target is not None:
        mgr.skip_to_sub_step(target)
    else:
        mgr.skip_current_sub_step()

    sub_after = current_sub_step(zone, mgr.get_sub_step_index())
    prev_num = sub_idx_before + 1
    next_num = mgr.get_sub_step_index() + 1
    skipped_label = sub_before.id.replace("_", " ") if sub_before else f"step {prev_num}"
    lead = (
        f"Skipped **{skipped_label}** — now on **step {next_num} of {total}** "
        f"in **{step.name}**."
    )
    if sub_after:
        lead += f"\n\n{build_sub_step_message(zone, sub_after, merchant_id=merchant_id)}"
    return build_tour_response(merchant_id, lead)


def _advance_after_choice(
    mgr: ZoneTourManager,
    merchant_id: str,
    applied_summary: str,
    sub_step_id: str,
) -> dict[str, Any]:
    """Move to next sub-step or next zone after a successful choice."""
    if mgr.advance_sub_step():
        step = mgr.current_step()
        if step:
            msg = _with_preview_hint(applied_summary, sub_step_id)
            return build_tour_response(
                merchant_id,
                f"{msg}\n\n{_next_step_message(mgr, step)}",
            )
    mgr.complete_current()
    next_step = mgr.current_step()
    if not next_step:
        return build_tour_finished_response(
            merchant_id,
            tour_complete_message(applied_summary),
        )
    msg = _with_preview_hint(applied_summary, sub_step_id)
    return build_tour_response(
        merchant_id,
        f"{msg}\n\n{_next_step_message(mgr, next_step)}",
    )


def _apply_sub_step_choice(
    mgr: ZoneTourManager,
    zone: str,
    sub,
    choice: dict[str, str],
    merchant_id: str,
) -> dict[str, Any]:
    if sub.kind == "palettes":
        from .harmony_feedback import format_harmony_appendix
        from .z1_tour_options import apply_z1_palette_package

        name, assessment = apply_z1_palette_package(merchant_id, choice)
        if assessment.blocked:
            return build_tour_response(
                merchant_id,
                format_harmony_appendix(assessment),
            )
        detail = (
            choice.get("what_changes")
            or choice.get("applies_to")
            or choice.get("description")
            or sub_step_explanation(sub.id)
        )
        summary = f"Applied **{name}** — *{detail}*."
        appendix = format_harmony_appendix(assessment)
        if appendix:
            summary = f"{summary} {appendix}"
        return _advance_after_choice(mgr, merchant_id, summary, sub.id)

    if sub.kind == "colors":
        if zone == "Z1":
            from .config_manager import ConfigManager
            from .harmony_feedback import (
                assess_brand_colours_for_sub_step,
                format_harmony_appendix,
            )

            preview = preview_tokens_for_z1_color(merchant_id, sub.id, choice)
            pre_check = assess_brand_colours_for_sub_step(sub.id, preview)
            if pre_check.blocked:
                return build_tour_response(merchant_id, format_harmony_appendix(pre_check))

        try:
            apply_tour_color_choice(mgr, zone, choice)
        except ValueError as exc:
            return build_tour_response(merchant_id, str(exc))
        summary = color_apply_summary(zone, choice, merchant_id, sub.id)
        if zone == "Z1":
            from .config_manager import ConfigManager
            from .harmony_feedback import (
                assess_brand_colours_for_sub_step,
                format_harmony_appendix,
            )

            cm = ConfigManager(shop_uuid=merchant_id)
            cm.reload()
            appendix = format_harmony_appendix(assess_brand_colours_for_sub_step(sub.id, cm.tokens))
            if appendix:
                summary = f"{summary} {appendix}"
        if sub.id == "z3_text_colour" and choice.get("role") == "text_body":
            mgr.clear_z3_text_colour_phase()
        if sub.id == "z3_text_colour" and choice.get("role") == "text_heading":
            mgr.set_z3_text_colour_phase("body")
            mgr.clear_dismissed_for_sub_step(sub.id)
            mgr.clear_option_cache()
            from .zone_tour_flow import build_sub_step_message, options_for_sub_step

            options_for_sub_step(zone, sub, merchant_id, force_refresh=True)
            body_prompt = build_sub_step_message(zone, sub, merchant_id=merchant_id)
            msg = _with_preview_hint(summary, sub.id)
            return build_tour_response(merchant_id, f"{msg}\n\n{body_prompt}")
        return _advance_after_choice(mgr, merchant_id, summary, sub.id)

    option_id = choice.get("id", "")
    apply_kwargs: dict[str, str] = {"option_id": option_id}
    if sub.id == "z1_motion":
        from .z1_tour_options import z1_motion_for_option

        motion_val = z1_motion_for_option(option_id) or ""
        if motion_val:
            apply_kwargs["motion_transition"] = motion_val
    try:
        mgr.apply_selection_to_tokens(zone, **apply_kwargs)  # type: ignore[arg-type]
    except ValueError as exc:
        return build_tour_response(merchant_id, str(exc))
    detail = (
        choice.get("what_changes")
        or choice.get("applies_to")
        or choice.get("description")
        or sub_step_explanation(sub.id)
    )
    name = choice.get("name", option_id)
    if sub.id == "z1_motion":
        from .z1_tour_options import z1_motion_for_option

        token = z1_motion_for_option(option_id) or "fadeTint"
        hint = (
            "Scroll the preview up and down — the page backdrop should "
            "**ease between sections**. Try **Slide-tint** or **None** if Fade looks unchanged."
            if token == "fadeTint"
            else "Scroll the preview to see how section backdrops respond."
        )
        summary = f"Page transitions → **{name}**. {detail} {hint}"
        return _advance_after_choice(mgr, merchant_id, summary, sub.id)
    if sub.id == "z4_prices":
        samples = choice.get("sample_prices") or ""
        extra = f" Sample: {samples}." if samples else ""
        summary = f"Price display → **{name}**. {detail}{extra}"
    else:
        summary = f"Applied **{name}** — *{detail}*."
    return _advance_after_choice(mgr, merchant_id, summary, sub.id)


def _resolve_choice(
    mgr: ZoneTourManager,
    zone: str,
    text: str,
) -> dict[str, str] | None:
    from .zone_tour_flow import resolve_tour_option

    sub = current_sub_step(zone, mgr.get_sub_step_index())
    if not sub:
        return None

    text = normalize_tour_input(text)
    choose = CHOOSE_RE.match(text)
    if choose:
        text = normalize_tour_input(choose.group(1))

    option_id = parse_zone_option_id(text) or ""
    hit = resolve_tour_option(
        mgr.shop_uuid,
        zone,
        sub,
        option_id=option_id,
        name=text,
    )
    if hit:
        return hit
    return match_sub_step_choice(zone, sub, text, merchant_id=mgr.shop_uuid)


def try_handle_zone_tour_message(merchant_id: str, message: str) -> dict[str, Any] | None:
    """Handle zone tour UI clicks and tour navigation (skip/exit/got it).

    All interpretive chat (colours, layouts, more options, tweaks) goes to Bedrock.
    """
    text = message.strip()
    if not text:
        return None

    mgr = ZoneTourManager(merchant_id)

    # Exit phrases work even when tour is not active (returns cancelled/finished payload)
    if EXIT_ZONE_TOUR_RE.search(text):
        was_active = mgr.is_active()
        mgr.cancel()
        if was_active:
            msg = (
                "You've left the zone-by-zone customization. "
                "Tell me what to change next, or say **Start zone tour** to walk through the areas again."
            )
        else:
            msg = (
                "Zone customization isn't running right now. "
                "Tell me what you'd like to change, or say **Start zone tour** to begin the walkthrough."
            )
        return build_tour_finished_response(merchant_id, msg, status="cancelled")

    if not mgr.is_active():
        if START_ZONE_TOUR_RE.search(text):
            mgr.start()
            step = mgr.current_step()
            if step:
                return build_tour_response(merchant_id, _next_step_message(mgr, step))
        return None

    step = mgr.current_step()
    if not step:
        return None

    zone = step.code

    # Z5 is info-only — merchant must acknowledge before advancing
    if GOT_IT_CONTINUE_RE.search(text):
        if not step.info_only:
            return None
        mgr.complete_current()
        next_step = mgr.current_step()
        if not next_step:
            return build_tour_finished_response(
                merchant_id,
                f"{Z5_POSITIVE_SCRIPT}\n\n**Zone tour complete!** Your storefront is ready to "
                f"fine-tune or publish. {preview_check_hint(None, tour_completing=True)}",
            )
        return build_tour_response(
            merchant_id,
            f"{Z5_POSITIVE_SCRIPT}\n\n{_next_step_message(mgr, next_step)}",
        )

    if wants_skip_sub_step(text):
        resp = _handle_skip_sub_step(mgr, merchant_id, text)
        if resp:
            return resp

    if SKIP_ZONE_RE.search(text) and mgr.progress_dict().get("can_skip"):
        mgr.skip_current()
        next_step = mgr.current_step()
        if not next_step:
            return build_tour_finished_response(
                merchant_id,
                "**Skipped — zone tour complete!** "
                f"{preview_check_hint(None, tour_completing=True)}",
            )
        return build_tour_response(merchant_id, _next_step_message(mgr, next_step))

    if step.info_only:
        return None  # Non-"got it" messages on Z5 fall through to agent

    sub = current_sub_step(zone, mgr.get_sub_step_index())
    if not sub:
        return None

    # Warm optionCache before resolving ``zone option <id>`` (ids are batch-specific).
    if parse_zone_option_id(normalize_tour_input(text)):
        from .zone_tour_flow import options_for_sub_step

        oid = parse_zone_option_id(normalize_tour_input(text)) or ""
        options_for_sub_step(
            zone,
            sub,
            merchant_id,
            force_refresh=should_force_refresh_options(sub, oid),
        )

    choice = _resolve_choice(mgr, zone, text)
    if choice:
        return _apply_sub_step_choice(mgr, zone, sub, choice, merchant_id)

    hex_val = extract_hex_from_text(text)
    if hex_val and sub.kind == "colors":
        hex_choice = color_choice_from_hex(zone, sub, hex_val)
        if hex_choice:
            from .color_engine import friendly_color_name

            hex_choice["name"] = friendly_color_name(hex_val)
            return _apply_sub_step_choice(mgr, zone, sub, hex_choice, merchant_id)

    # Explicit swatch clicks must not fall through to Bedrock (agent often claims apply
    # without calling tools, so preview and tour step stay unchanged).
    if parse_zone_option_id(normalize_tour_input(text)):
        oid = parse_zone_option_id(normalize_tour_input(text)) or ""
        return build_tour_response(merchant_id, swatch_failure_hint(oid, sub))

    # Free-form (more options, stylish, tweaks, …) → Bedrock agent decides via tools.
    return None
