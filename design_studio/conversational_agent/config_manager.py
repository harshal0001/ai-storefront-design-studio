"""High-level persistence for merchant storefront style.

**Primary path (production / local dev):** ``StyleRepository`` + DynamoDB when
``USE_DYNAMODB=true`` and ``DYNAMODB_ENDPOINT`` are set. All tokens, version history,
undo/redo, and zone tour state live in ``StorefrontStyle``.

**JSON fallback (tests only):** Per-shop files under ``DESIGN_STUDIO_DATA_DIR`` or CWD:
  - ``storefront_config.json`` — legacy ``StorefrontConfig`` (zone_overrides)
  - ``storefront_tokens_{shop}.json`` — current ``StyleTokens``
  - ``storefront_history_{shop}.json`` — local undo stack (max ``MAX_LOCAL_HISTORY``)

``guard_json_write()`` raises if DynamoDB is enabled so the dev server never silently
creates ``storefront_history_*.json`` beside the source tree.

Also bridges legacy ``StorefrontConfig`` with ``StyleTokens`` via ``token_mapper``.
Prefer ``save_tokens()`` for new code.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import StorefrontConfig, BorderRadius, Spacing, Zone, ZoneStyle
from .style_repository import StyleRepository
from .style_tokens import StyleTokens
from .token_mapper import (
    apply_zone_override,
    recompute_quality_flags,
    storefront_config_to_tokens,
    tokens_to_storefront_config,
)
from .zone_scopes import normalize_product_zone_scopes

DEFAULT_SHOP_UUID = os.environ.get("DEFAULT_SHOP_UUID", "demo-merchant")
MAX_LOCAL_HISTORY = 20


def _data_dir() -> Path:
    """Directory for JSON fallback files (tests set DESIGN_STUDIO_DATA_DIR to tmp_path)."""
    raw = os.environ.get("DESIGN_STUDIO_DATA_DIR", "").strip()
    return Path(raw) if raw else Path(".")


def default_config_path() -> Path:
    """Current default config file (respects ``DESIGN_STUDIO_DATA_DIR``)."""
    return _data_dir() / "storefront_config.json"


def _file_mtime_iso(path: Path) -> str:
    if not path.exists():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _theme_change_summary(theme_name: str) -> dict[str, str]:
    if theme_name:
        return {"humanSummary": f'Applied theme "{theme_name}".'}
    return {"humanSummary": "Applied theme."}


class ConfigManager:
    """Facade for loading/saving a merchant's theme, versions, and undo/redo.

    Caches ``_tokens`` and ``_config`` until ``reload()`` is called.
    """

    def __init__(
        self,
        shop_uuid: str = DEFAULT_SHOP_UUID,
        config_path: Path | str | None = None,
    ):
        self.shop_uuid = shop_uuid
        self.config_path = Path(config_path or default_config_path())
        self._repo = StyleRepository(shop_uuid=shop_uuid)
        self._config: StorefrontConfig | None = None
        self._tokens: StyleTokens | None = None

    @property
    def uses_dynamodb(self) -> bool:
        return self._repo.enabled

    def guard_json_write(self) -> None:
        """Block accidental JSON writes when DynamoDB is the configured backend."""
        if self.uses_dynamodb:
            raise RuntimeError(
                f"Refusing JSON persistence for shop {self.shop_uuid!r}: "
                "DynamoDB is enabled (USE_DYNAMODB + DYNAMODB_ENDPOINT)."
            )

    @property
    def tokens(self) -> StyleTokens:
        if self._tokens is None:
            if self.uses_dynamodb:
                # STYLE#DRAFT or STYLE#PUBLISHED via StyleRepository.get_effective_tokens
                self._tokens = self._repo.get_effective_tokens(self.shop_uuid)
            else:
                # Test fallback: tokens file, else derive from legacy config JSON
                token_path = self._tokens_path()
                if token_path.exists():
                    with open(token_path) as f:
                        self._tokens = StyleTokens.from_ddb_map(json.load(f))
                else:
                    self._tokens = storefront_config_to_tokens(self.load())
            self._tokens = normalize_product_zone_scopes(self._tokens)
        return self._tokens

    @property
    def config(self) -> StorefrontConfig:
        if self._config is None:
            if not self.uses_dynamodb:
                self._config = self.load()
            else:
                profile = self._repo.get_style_profile(self.shop_uuid) or {}
                meta = self._repo.get_effective_meta(self.shop_uuid)
                summary = meta.get("changeSummary") or {}
                self._config = tokens_to_storefront_config(
                    self.tokens,
                    theme_name=self.tokens.colors.paletteName,
                    theme_description=summary.get("humanSummary", "")
                    if isinstance(summary, dict)
                    else "",
                    mood_summary=", ".join(profile.get("moodTags", [])),
                )
        return self._config

    def reload(self) -> None:
        self._config = None
        self._tokens = None

    def _tokens_path(self) -> Path:
        return self.config_path.with_name(f"storefront_tokens_{self.shop_uuid}.json")

    def _history_path(self) -> Path:
        return self.config_path.with_name(f"storefront_history_{self.shop_uuid}.json")

    def _save_tokens_file(self, tokens: StyleTokens) -> None:
        self.guard_json_write()
        with open(self._tokens_path(), "w") as f:
            json.dump(tokens.to_ddb_map(), f, indent=2)

    def _load_history(self) -> dict[str, Any]:
        path = self._history_path()
        if not path.exists():
            return {"undoStack": [], "redoStack": [], "currentIndex": -1}
        with open(path) as f:
            return json.load(f)

    def _save_history(self, history: dict[str, Any]) -> None:
        self.guard_json_write()
        with open(self._history_path(), "w") as f:
            json.dump(history, f, indent=2)

    def _push_history_snapshot(self, tokens: StyleTokens) -> None:
        """Append to local undo stack — JSON fallback only (DDB uses STYLE#VERSION#*)."""
        history = self._load_history()
        stack = list(history.get("undoStack") or [])
        stack.append(tokens.to_ddb_map())
        if len(stack) > MAX_LOCAL_HISTORY:
            stack = stack[-MAX_LOCAL_HISTORY:]
        history["undoStack"] = stack
        history["redoStack"] = []
        history["currentIndex"] = len(stack) - 1
        self._save_history(history)

    def list_local_version_summaries(self) -> list[dict]:
        """Version list for JSON fallback (includes lastModified for the UI)."""
        history = self._load_history()
        stack = history.get("undoStack") or []
        idx = int(history.get("currentIndex", max(0, len(stack) - 1)))
        mtime = _file_mtime_iso(self.config_path)
        if not stack:
            return [
                {
                    "versionId": 0,
                    "versionSeq": 0,
                    "label": "Version 1",
                    "isCurrent": True,
                    "lastModified": mtime,
                    "branch": "current",
                }
            ]
        return [
            {
                "versionId": i,
                "versionSeq": i,
                "label": f"Version {i + 1}",
                "isCurrent": i == idx,
                "lastModified": mtime,
                "branch": "current",
            }
            for i in range(len(stack))
        ]

    def can_undo(self) -> bool:
        if self.uses_dynamodb:
            return self._repo.can_undo(self.shop_uuid)
        history = self._load_history()
        return int(history.get("currentIndex", -1)) > 0

    def can_redo(self) -> bool:
        if self.uses_dynamodb:
            return self._repo.can_redo(self.shop_uuid)
        return len(self._load_history().get("redoStack") or []) > 0

    def version_index(self) -> tuple[int, int]:
        if self.uses_dynamodb:
            summaries = self._repo.list_version_summaries(self.shop_uuid)
            if not summaries:
                return 0, 1
            current_idx = next(
                (i for i, s in enumerate(summaries) if s.get("isCurrent")),
                len(summaries) - 1,
            )
            return current_idx, len(summaries)
        history = self._load_history()
        stack = history.get("undoStack") or []
        idx = int(history.get("currentIndex", -1))
        if idx < 0 or not stack:
            return 0, max(len(stack), 1)
        return idx, len(stack)

    def undo(self) -> StyleTokens | None:
        if self.uses_dynamodb:
            tokens = self._repo.undo(self.shop_uuid)
            if tokens:
                self.reload()
            return tokens

        history = self._load_history()
        idx = int(history.get("currentIndex", -1))
        if idx <= 0:
            return None

        redo = list(history.get("redoStack") or [])
        stack = history["undoStack"]
        redo.append(stack[idx])
        history["redoStack"] = redo
        history["currentIndex"] = idx - 1
        self._save_history(history)

        tokens = StyleTokens.from_ddb_map(stack[history["currentIndex"]])
        self._tokens = tokens
        self._config = tokens_to_storefront_config(
            tokens, theme_name=tokens.colors.paletteName or "Custom Theme"
        )
        self._save_tokens_file(tokens)
        self.save(self._config)
        return tokens

    def restore_local_index(self, index: int) -> StyleTokens | None:
        """Jump to a snapshot in local undo stack (JSON fallback)."""
        history = self._load_history()
        stack = history.get("undoStack") or []
        if index < 0 or index >= len(stack):
            return None
        history["currentIndex"] = index
        history["redoStack"] = []
        self._save_history(history)
        tokens = StyleTokens.from_ddb_map(stack[index])
        self._tokens = tokens
        self._config = tokens_to_storefront_config(
            tokens, theme_name=tokens.colors.paletteName or "Custom Theme"
        )
        self._save_tokens_file(tokens)
        self.save(self._config)
        return tokens

    def redo(self) -> StyleTokens | None:
        if self.uses_dynamodb:
            tokens = self._repo.redo(self.shop_uuid)
            if tokens:
                self.reload()
            return tokens

        history = self._load_history()
        redo = list(history.get("redoStack") or [])
        if not redo:
            return None

        target = redo.pop()
        stack = list(history.get("undoStack") or [])
        stack.append(target)
        if len(stack) > MAX_LOCAL_HISTORY:
            stack = stack[-MAX_LOCAL_HISTORY:]
        history["undoStack"] = stack
        history["redoStack"] = redo
        history["currentIndex"] = len(stack) - 1
        self._save_history(history)

        tokens = StyleTokens.from_ddb_map(target)
        self._tokens = tokens
        self._config = tokens_to_storefront_config(
            tokens, theme_name=tokens.colors.paletteName or "Custom Theme"
        )
        self._save_tokens_file(tokens)
        self.save(self._config)
        return tokens

    def load(self) -> StorefrontConfig:
        if not self.config_path.exists():
            return StorefrontConfig()
        with open(self.config_path) as f:
            data = json.load(f)
        return self._from_dict(data)

    def save(
        self,
        config: StorefrontConfig | None = None,
        *,
        based_on_package_id: str | None = None,
        change_summary: dict | None = None,
    ) -> int:
        config = config or self._config or StorefrontConfig()
        tokens = storefront_config_to_tokens(config)
        self._config = config
        self._tokens = tokens

        if self.uses_dynamodb:
            version = self._repo.save_tokens_with_history(
                tokens,
                shop_uuid=self.shop_uuid,
                based_on_package_id=based_on_package_id,
                change_summary=change_summary or _theme_change_summary(config.theme_name),
            )
            return version

        self.guard_json_write()
        data = self._to_dict(config)
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)
        return 1

    def save_tokens(
        self,
        tokens: StyleTokens,
        *,
        theme_name: str = "",
        mood_summary: str = "",
        based_on_package_id: str | None = None,
        change_summary: dict[str, Any] | None = None,
    ) -> int:
        tokens = normalize_product_zone_scopes(tokens)
        tokens = recompute_quality_flags(tokens)
        self._tokens = tokens
        self._config = tokens_to_storefront_config(
            tokens,
            theme_name=theme_name,
            mood_summary=mood_summary,
        )
        if self.uses_dynamodb:
            return self._repo.save_tokens_with_history(
                tokens,
                shop_uuid=self.shop_uuid,
                based_on_package_id=based_on_package_id,
                change_summary=change_summary or _theme_change_summary(theme_name),
            )
        # JSON path: legacy config file + tokens file + local undo snapshot
        self.save(self._config)
        self._save_tokens_file(tokens)
        self._push_history_snapshot(tokens)
        return len(self._load_history().get("undoStack") or [])

    def apply_zone(self, zone: Zone, style: ZoneStyle) -> int:
        tokens = apply_zone_override(self.tokens, zone, style)
        tokens = recompute_quality_flags(tokens)
        if zone not in self.config.zone_overrides:
            self.config.zone_overrides[zone] = ZoneStyle()
        zs = self.config.zone_overrides[zone]
        if style.primary_color:
            zs.primary_color = style.primary_color
        if style.background_color:
            zs.background_color = style.background_color
        if style.border_radius:
            zs.border_radius = style.border_radius
        self._tokens = tokens
        if self.uses_dynamodb:
            return self._repo.save_tokens_with_history(
                tokens,
                shop_uuid=self.shop_uuid,
                change_summary={
                    "zonesTouched": [zone.value],
                    "humanSummary": f"Customized {zone.value}.",
                },
            )
        self.save(self.config)
        self._save_tokens_file(tokens)
        self._push_history_snapshot(tokens)
        return 1

    def reset(self) -> None:
        """Wipe merchant style + tour state (DDB ``reset_shop`` or delete local JSON files)."""
        from .zone_tour import ZoneTourManager

        self._config = StorefrontConfig()
        self._tokens = StyleTokens()
        if self.uses_dynamodb:
            self._repo.reset_shop(self.shop_uuid)
        ZoneTourManager(
            self.shop_uuid,
            self._repo,
            config_path=self.config_path,
        ).cancel()
        if not self.uses_dynamodb and self.config_path.exists():
            self.config_path.unlink()
        token_path = self._tokens_path()
        if token_path.exists():
            token_path.unlink()
        history_path = self._history_path()
        if history_path.exists():
            history_path.unlink()

    def _to_dict(self, config: StorefrontConfig) -> dict[str, Any]:
        return {
            "theme_name": config.theme_name,
            "theme_description": config.theme_description,
            "mood_summary": config.mood_summary,
            "primary_color": config.primary_color,
            "primary_color_name": config.primary_color_name,
            "secondary_color": config.secondary_color,
            "secondary_color_name": config.secondary_color_name,
            "accent_color": config.accent_color,
            "accent_color_name": config.accent_color_name,
            "background_color": config.background_color,
            "background_color_name": config.background_color_name,
            "surface_color": config.surface_color,
            "surface_color_name": config.surface_color_name,
            "text_primary": config.text_primary,
            "text_secondary": config.text_secondary,
            "heading_font": config.heading_font,
            "body_font": config.body_font,
            "default_border_radius": config.default_border_radius.value,
            "default_spacing": config.default_spacing.value,
            "zone_overrides": {
                zone.value: {
                    "primary_color": style.primary_color,
                    "background_color": style.background_color,
                    "border_radius": style.border_radius.value if style.border_radius else None,
                }
                for zone, style in config.zone_overrides.items()
            },
        }

    def _from_dict(self, data: dict[str, Any]) -> StorefrontConfig:
        zone_overrides = {}
        for zone_str, style_data in data.get("zone_overrides", {}).items():
            zone = Zone(zone_str)
            br = style_data.get("border_radius")
            zone_overrides[zone] = ZoneStyle(
                primary_color=style_data.get("primary_color"),
                background_color=style_data.get("background_color"),
                border_radius=BorderRadius(br) if br else None,
            )

        return StorefrontConfig(
            theme_name=data.get("theme_name", ""),
            theme_description=data.get("theme_description", ""),
            mood_summary=data.get("mood_summary", ""),
            primary_color=data.get("primary_color", ""),
            primary_color_name=data.get("primary_color_name", ""),
            secondary_color=data.get("secondary_color", ""),
            secondary_color_name=data.get("secondary_color_name", ""),
            accent_color=data.get("accent_color", ""),
            accent_color_name=data.get("accent_color_name", ""),
            background_color=data.get("background_color", ""),
            background_color_name=data.get("background_color_name", ""),
            surface_color=data.get("surface_color", ""),
            surface_color_name=data.get("surface_color_name", ""),
            text_primary=data.get("text_primary", ""),
            text_secondary=data.get("text_secondary", ""),
            heading_font=data.get("heading_font", ""),
            body_font=data.get("body_font", ""),
            default_border_radius=BorderRadius(data.get("default_border_radius", "rounded")),
            default_spacing=Spacing(data.get("default_spacing", "normal")),
            zone_overrides=zone_overrides,
        )
