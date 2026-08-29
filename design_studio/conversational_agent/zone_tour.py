"""CF-05 zone tour — state machine and token application for Z1–Z6.

``ZoneTourManager`` tracks ``currentIndex``, ``subStepIndex``, completed/skipped zones.
Persistence:
  - DynamoDB ``SK=ZONE_TOUR`` when DDB enabled
  - Else ``storefront_zone_tour_{shop}.json``

Only ``status == "active"`` is treated as in-progress (``get_state()``). Completed or
cancelled tours remain in storage until ``cancel()`` or ``ConfigManager.reset()``.

``apply_selection_to_tokens()`` maps tour choices to ``StyleTokens`` and saves via
``ConfigManager.save_tokens()``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .config_manager import ConfigManager, default_config_path
from .style_repository import StyleRepository
from .style_tokens import StyleTokens
from .zone_tour_flow import (
    current_sub_step,
    sub_steps_for_zone,
    tour_enrichment_payload,
)


ZoneCode = Literal["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]


@dataclass(frozen=True)
class TourStep:
    """One editable area in the merchant-facing tour (maps to Z1–Z6 spec)."""

    code: ZoneCode
    name: str
    headline: str
    controls: str
    skip_allowed: bool = True
    info_only: bool = False


TOUR_STEPS: tuple[TourStep, ...] = (
    TourStep(
        "Z1",
        "Brand Colours",
        "Let's start with your brand colours",
        "Primary, accent, background, and surface colours — they set the mood for everything else.",
    ),
    TourStep(
        "Z2",
        "Hero & Header",
        "Shape your hero & header",
        "Hero layout, overlay, logo placement, and how your store name appears.",
    ),
    TourStep(
        "Z3",
        "Typography",
        "Pick your fonts",
        "Heading and body font pairing, plus overall text scale.",
    ),
    TourStep(
        "Z4",
        "Product Cards",
        "Style your product cards",
        "Separate backgrounds for Our Products vs All Products, plus card layout and price accent.",
    ),
    TourStep(
        "Z5",
        "Offer Cards",
        "About your offer cards",
        "Offer cards are platform-managed — we A/B test them to maximise your sales.",
        skip_allowed=False,
        info_only=True,
    ),
    TourStep(
        "Z6",
        "Buttons & CTAs",
        "Finish with buttons & CTAs",
        "Button shape & style, size (compact/standard/large), then CTA colour.",
    ),
)

Z5_POSITIVE_SCRIPT = (
    "Quick note on your **Offers** section: we keep those cards consistent across stores "
    "because we've seen it boost conversions — we run A/B tests so you don't have to guess. "
    "They'll always look polished in your preview. If you ever have questions, our team is happy to help!"
)


class ZoneTourManager:
    """Persist zone tour state — DynamoDB (`SK=ZONE_TOUR`) or JSON (matches ConfigManager)."""

    def __init__(
        self,
        shop_uuid: str,
        repo: StyleRepository | None = None,
        *,
        config_path: Path | str | None = None,
    ):
        self.shop_uuid = shop_uuid
        self._config_path = Path(config_path or default_config_path())
        self._cm = ConfigManager(shop_uuid=shop_uuid, config_path=self._config_path)
        self.repo = repo or self._cm._repo

    @property
    def uses_dynamodb(self) -> bool:
        return self._cm.uses_dynamodb

    def _zone_tour_path(self) -> Path:
        return self._config_path.with_name(f"storefront_zone_tour_{self.shop_uuid}.json")

    def _load(self) -> dict | None:
        if self.uses_dynamodb:
            return self.repo.get_zone_tour(self.shop_uuid)
        path = self._zone_tour_path()
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def _save(self, state: dict) -> None:
        if self.uses_dynamodb:
            self.repo.put_zone_tour(self.shop_uuid, state)
            return
        # Test-only JSON path — guarded so DDB mode never writes tour files locally
        self._cm.guard_json_write()
        path = self._zone_tour_path()
        with open(path, "w") as f:
            json.dump(state, f, indent=2)

    def start(self) -> dict:
        from .theme_choice_actions import clear_pending_theme_packages

        clear_pending_theme_packages(self.shop_uuid)
        state = {
            "status": "active",  # only "active" counts as in-progress (see get_state)
            "currentIndex": 0,  # index into TOUR_STEPS
            "subStepIndex": 0,  # index into zone-specific sub-steps (colours, layouts, …)
            "completed": [],
            "skipped": [],
        }
        self._save(state)
        self.ensure_current_sub_step_ready()
        return self.progress_dict()

    def cache_sub_step_options(
        self,
        sub_step_id: str,
        color_options: list[dict] | None = None,
        zone_options: list[dict] | None = None,
        *,
        theme_packages: list[dict] | None = None,
        append: bool = False,
    ) -> None:
        """Persist generated swatches so clicks resolve without a static catalogue."""
        from .zone_dynamic_options import _dedupe_options

        state = self.get_state()
        if not state:
            return
        cache = state.get("optionCache") or {}
        prev_colors: list[dict] = []
        prev_zone: list[dict] = []
        prev_packages: list[dict] = []
        if append and cache.get("subStepId") == sub_step_id:
            prev_colors = list(cache.get("colorOptions") or [])
            prev_zone = list(cache.get("zoneOptions") or [])
            prev_packages = list(cache.get("themePackages") or [])

        merged_colors = _dedupe_options(prev_colors + list(color_options or []))
        merged_zone = _dedupe_options(prev_zone + list(zone_options or []))
        merged_packages = _dedupe_options(prev_packages + list(theme_packages or []))

        by_sub: dict[str, list[str]] = dict(state.get("dismissedBySubStep") or {})
        shown = set(by_sub.get(sub_step_id, []))
        for o in merged_colors + merged_zone + merged_packages:
            oid = o.get("id")
            if oid:
                shown.add(oid)
        by_sub[sub_step_id] = list(shown)
        state["dismissedBySubStep"] = by_sub
        from .zone_tour_flow import current_sub_step

        step = self.current_step()
        sub_kind = ""
        if step:
            sub = current_sub_step(step.code, self.get_sub_step_index())
            if sub and sub.id == sub_step_id:
                sub_kind = sub.kind
        state["optionCache"] = {
            "subStepId": sub_step_id,
            "subStepKind": sub_kind,
            "colorOptions": merged_colors,
            "zoneOptions": merged_zone,
            "themePackages": merged_packages,
        }
        self._save(state)

    def get_cached_theme_packages(self) -> list[dict]:
        state = self.get_state() or {}
        cache = state.get("optionCache") or {}
        return list(cache.get("themePackages") or [])

    def ensure_current_sub_step_ready(self) -> None:
        """Skip ``z1_palette`` when discovery already configured brand colours (Z1-01)."""
        from .config_manager import ConfigManager
        from .z1_tour_options import z1_palette_already_configured

        while True:
            step = self.current_step()
            if not step or step.code != "Z1":
                return
            sub = current_sub_step(step.code, self.get_sub_step_index())
            if not sub or sub.id != "z1_palette":
                return
            cm = ConfigManager(shop_uuid=self.shop_uuid)
            cm.reload()
            if not z1_palette_already_configured(cm.tokens):
                return
            if not self.advance_sub_step():
                return

    def clear_dismissed_for_sub_step(self, sub_step_id: str) -> None:
        state = self.get_state()
        if not state:
            return
        by_sub: dict[str, list[str]] = dict(state.get("dismissedBySubStep") or {})
        by_sub.pop(sub_step_id, None)
        state["dismissedBySubStep"] = by_sub
        self._save(state)

    def get_cached_option_ids(self) -> set[str]:
        ids: set[str] = set()
        for o in (
            self.get_cached_color_options()
            + self.get_cached_zone_options()
            + self.get_cached_theme_packages()
        ):
            oid = o.get("id")
            if oid:
                ids.add(oid)
        return ids

    def get_cached_color_options(self) -> list[dict]:
        state = self.get_state() or {}
        cache = state.get("optionCache") or {}
        return list(cache.get("colorOptions") or [])

    def get_cached_zone_options(self) -> list[dict]:
        state = self.get_state() or {}
        cache = state.get("optionCache") or {}
        return list(cache.get("zoneOptions") or [])

    def get_sub_step_index(self) -> int:
        state = self.get_state()
        if not state:
            return 0
        idx = int(state.get("subStepIndex", 0))
        step = self.current_step()
        if step:
            total = len(sub_steps_for_zone(step.code))
            if total and idx >= total:
                state["subStepIndex"] = 0
                self._save(state)
                return 0
        return idx

    def get_z3_text_colour_phase(self) -> str:
        """Within ``z3_text_colour``: ``heading`` then ``body`` before advancing the zone."""
        state = self.get_state() or {}
        return state.get("z3TextColourPhase") or "heading"

    def set_z3_text_colour_phase(self, phase: str) -> None:
        state = self.get_state()
        if not state:
            return
        state["z3TextColourPhase"] = phase
        self._save(state)

    def clear_z3_text_colour_phase(self) -> None:
        state = self.get_state()
        if not state:
            return
        state.pop("z3TextColourPhase", None)
        self._save(state)

    def _reset_sub_step(self, state: dict) -> None:
        state["subStepIndex"] = 0
        state["optionBatch"] = 0
        state.pop("dismissedBySubStep", None)
        state.pop("dismissedOptionIds", None)
        state.pop("optionCache", None)
        state.pop("z3TextColourPhase", None)

    def _clear_option_cache(self, state: dict) -> None:
        state.pop("optionCache", None)

    def clear_option_cache(self) -> None:
        state = self.get_state()
        if not state:
            return
        self._clear_option_cache(state)
        self._save(state)

    def get_option_batch(self) -> int:
        state = self.get_state() or {}
        return int(state.get("optionBatch", 0))

    def bump_option_batch(self) -> int:
        state = self.get_state()
        if not state:
            return 0
        batch = int(state.get("optionBatch", 0)) + 1
        state["optionBatch"] = batch
        self._save(state)
        return batch

    def get_dismissed_option_ids(self) -> set[str]:
        """Option ids already shown for the **current** sub-step (not the whole tour)."""
        state = self.get_state() or {}
        cache = state.get("optionCache") or {}
        sub_id = cache.get("subStepId") or ""
        if sub_id:
            by_sub = state.get("dismissedBySubStep") or {}
            return set(by_sub.get(sub_id, []))
        legacy = set(state.get("dismissedOptionIds") or [])
        for o in (
            (cache.get("colorOptions") or [])
            + (cache.get("zoneOptions") or [])
            + (cache.get("themePackages") or [])
        ):
            if o.get("id"):
                legacy.add(o["id"])
        return legacy

    def advance_sub_step(self) -> bool:
        """Advance within the current zone. Returns True if zone has more sub-steps."""
        state = self.get_state()
        if not state:
            return False
        step = self.current_step()
        if not step:
            return False
        idx = int(state.get("subStepIndex", 0)) + 1
        total = len(sub_steps_for_zone(step.code))
        if idx < total:
            state["subStepIndex"] = idx
            self._clear_option_cache(state)
            state.pop("z3TextColourPhase", None)
            self._save(state)
            self.ensure_current_sub_step_ready()
            return True
        return False

    def can_skip_sub_step(self) -> bool:
        """True when the merchant can skip the current chat sub-step (not the last in the zone)."""
        state = self.get_state()
        step = self.current_step()
        if not state or not step or step.info_only:
            return False
        sub_idx = int(state.get("subStepIndex", 0))
        total = len(sub_steps_for_zone(step.code))
        return total > 1 and sub_idx < total - 1

    def skip_to_sub_step(self, one_based: int) -> bool:
        """Jump forward to a later sub-step (1-based). Returns True if index changed."""
        state = self.get_state()
        if not state:
            return False
        step = self.current_step()
        if not step or step.info_only:
            return False
        total = len(sub_steps_for_zone(step.code))
        if total <= 1:
            return False
        target = max(0, min(one_based - 1, total - 1))
        current = int(state.get("subStepIndex", 0))
        if target <= current:
            return self.advance_sub_step()
        state["subStepIndex"] = target
        self._clear_option_cache(state)
        state.pop("z3TextColourPhase", None)
        self._save(state)
        self.ensure_current_sub_step_ready()
        return True

    def skip_current_sub_step(self) -> bool:
        """Skip the active sub-step without applying tokens. Returns True if advanced."""
        if not self.can_skip_sub_step():
            return False
        return self.advance_sub_step()

    def get_state(self) -> dict | None:
        raw = self._load()
        if not raw or raw.get("status") != "active":
            return None
        return raw

    def is_active(self) -> bool:
        return self.get_state() is not None

    def current_step(self) -> TourStep | None:
        state = self.get_state()
        if not state:
            return None
        idx = int(state.get("currentIndex", 0))
        if idx >= len(TOUR_STEPS):
            return None
        return TOUR_STEPS[idx]

    def progress_dict(self) -> dict[str, Any]:
        state = self.get_state()
        if not state:
            return {"active": False}

        idx = int(state.get("currentIndex", 0))
        current = TOUR_STEPS[idx] if idx < len(TOUR_STEPS) else None
        completed = list(state.get("completed") or [])
        skipped = list(state.get("skipped") or [])

        editable_total = sum(1 for s in TOUR_STEPS if not s.info_only)
        editable_done = sum(
            1 for c in completed if c in {s.code for s in TOUR_STEPS if not s.info_only}
        )

        sub_idx = int(state.get("subStepIndex", 0))
        zone_code = current.code if current else None
        sub = current_sub_step(zone_code, sub_idx) if zone_code else None
        flow = (
            tour_enrichment_payload(zone_code, sub_idx, merchant_id=self.shop_uuid)
            if zone_code and sub and not (current and current.info_only)
            else {}
        )

        from .zone_dynamic_options import build_theme_context, sub_step_explanation

        theme_ctx = build_theme_context(self.shop_uuid)
        step_expl = sub_step_explanation(sub.id) if sub else ""

        base: dict[str, Any] = {
            "active": True,
            "status": state.get("status", "active"),
            "current_zone": zone_code,
            "current_zone_name": current.name if current else None,
            "current_headline": current.headline if current else None,
            "current_controls": current.controls if current else None,
            "current_prompt": flow.get("current_prompt") or (sub.prompt if sub else None),
            "sub_step_index": sub_idx,
            "sub_step_total": flow.get("sub_step_total", 0),
            "sub_step_id": flow.get("sub_step_id"),
            "highlight_selectors": flow.get("highlight_selectors") or [],
            "step_index": idx,
            "total_steps": len(TOUR_STEPS),
            "editable_total": editable_total,
            "editable_completed": editable_done,
            "completed_zones": completed,
            "skipped_zones": skipped,
            "can_skip": bool(current and current.skip_allowed and not current.info_only),
            "can_skip_sub_step": self.can_skip_sub_step(),
            "info_only": bool(current and current.info_only),
            "z5_message": Z5_POSITIVE_SCRIPT if current and current.code == "Z5" else None,
            "theme_context": theme_ctx,
            "step_explanation": step_expl,
            "steps": [
                {
                    "code": s.code,
                    "name": s.name,
                    "info_only": s.info_only,
                    "done": s.code in completed,
                    "skipped": s.code in skipped,
                    "current": i == idx,
                }
                for i, s in enumerate(TOUR_STEPS)
            ],
        }
        base.update(
            {
                k: v
                for k, v in flow.items()
                if k not in ("prompt_message", "color_options", "zone_options")
            }
        )
        return base

    def complete_current(self) -> dict:
        state = self.get_state()
        if not state:
            return self.progress_dict()

        idx = int(state["currentIndex"])
        step = TOUR_STEPS[idx]
        completed = list(state.get("completed") or [])
        if step.code not in completed:
            completed.append(step.code)

        state["completed"] = completed
        state["currentIndex"] = idx + 1
        self._reset_sub_step(state)
        if state["currentIndex"] >= len(TOUR_STEPS):
            state["status"] = "completed"
        self._save(state)
        self.ensure_current_sub_step_ready()
        return self.progress_dict()

    def skip_current(self) -> dict:
        state = self.get_state()
        if not state:
            return self.progress_dict()

        idx = int(state["currentIndex"])
        step = TOUR_STEPS[idx]
        if not step.skip_allowed or step.info_only:
            return self.progress_dict()

        skipped = list(state.get("skipped") or [])
        if step.code not in skipped:
            skipped.append(step.code)

        state["skipped"] = skipped
        state["currentIndex"] = idx + 1
        self._reset_sub_step(state)
        if state["currentIndex"] >= len(TOUR_STEPS):
            state["status"] = "completed"
        self._save(state)
        self.ensure_current_sub_step_ready()
        return self.progress_dict()

    def cancel(self) -> None:
        if self.uses_dynamodb:
            self._save(
                {
                    "status": "cancelled",
                    "currentIndex": 0,
                    "subStepIndex": 0,
                    "completed": [],
                    "skipped": [],
                }
            )
            return
        path = self._zone_tour_path()
        if path.exists():
            path.unlink()

    def apply_selection_to_tokens(
        self,
        zone_code: ZoneCode,
        *,
        option_id: str = "",
        primary_color: str = "",
        accent_color: str = "",
        background_color: str = "",
        surface_color: str = "",
        heading_font: str = "",
        body_font: str = "",
        font_scale: str = "",
        text_primary: str = "",
        text_secondary: str = "",
        hero_layout: str = "",
        hero_overlay: str = "",
        logo_placement: str = "",
        card_shape: str = "",
        card_layout: str = "",
        card_shadow: str = "",
        price_style: str = "",
        button_shape: str = "",
        button_style: str = "",
        button_size: str = "",
        motion_transition: str = "",
    ) -> StyleTokens:
        from .config_manager import ConfigManager

        cm = ConfigManager(shop_uuid=self.shop_uuid)
        tokens = cm.tokens.model_copy(deep=True)

        from .zone_tour_token_apply import apply_zone_selection

        tokens = apply_zone_selection(
            tokens,
            zone_code,
            self.shop_uuid,
            option_id=option_id,
            primary_color=primary_color,
            accent_color=accent_color,
            background_color=background_color,
            surface_color=surface_color,
            heading_font=heading_font,
            body_font=body_font,
            font_scale=font_scale,
            text_primary=text_primary,
            text_secondary=text_secondary,
            hero_layout=hero_layout,
            hero_overlay=hero_overlay,
            logo_placement=logo_placement,
            card_shape=card_shape,
            card_layout=card_layout,
            card_shadow=card_shadow,
            price_style=price_style,
            button_shape=button_shape,
            button_style=button_style,
            button_size=button_size,
            motion_transition=motion_transition,
        )

        # Z1-06: block palette applies; accent/backdrop are warn-only in tour_actions.
        if zone_code == "Z1" and primary_color:
            from .harmony_feedback import assess_brand_colours

            assessment = assess_brand_colours(tokens)
            if assessment.blocked:
                raise ValueError(assessment.message)
        elif zone_code == "Z1" and background_color:
            from .harmony_feedback import assess_brand_colours_for_sub_step

            assessment = assess_brand_colours_for_sub_step("z1_backdrop", tokens)
            if assessment.blocked:
                raise ValueError(assessment.message)
        elif zone_code == "Z1" and surface_color:
            from .harmony_feedback import assess_brand_colours

            assessment = assess_brand_colours(tokens)
            if assessment.blocked:
                raise ValueError(assessment.message)

        cm.save_tokens(
            tokens,
            theme_name=tokens.colors.paletteName or "Custom Theme",
            change_summary={
                "zonesTouched": [zone_code],
                "humanSummary": f"Updated {zone_code} during zone tour.",
            },
        )
        cm.reload()
        return tokens
