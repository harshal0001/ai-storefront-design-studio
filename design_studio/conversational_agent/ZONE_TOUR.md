# Zone tour — module map

Zone-by-zone storefront customization (Z1–Z6). Swatch clicks use the fast path (no Bedrock).

| File | Responsibility |
|------|----------------|
| `zone_tour.py` | Tour state (`ZoneTourManager`), persistence, apply entry point |
| `zone_tour_types.py` | `ZoneSubStep`, `StepKind` (shared datatypes) |
| `zone_tour_flow.py` | Sub-steps (`ZONE_SUB_STEPS`), option batches, chat copy |
| `zone_tour_actions.py` | `try_handle_zone_tour_message` — clicks, skip, exit |
| `zone_tour_advance.py` | Advance sub-step after a successful apply |
| `zone_tour_token_apply.py` | Per-zone `StyleTokens` updates |
| `zone_tour_color_apply.py` | Colour swatch → tokens + confirmation text |
| `zone_tour_swatch_errors.py` | Hints when a swatch id did not resolve |
| `zone_option_cache.py` | Validate `optionCache` for the active sub-step |
| `zone_option_resolver.py` | Resolve `zone option <id>` to option dicts |
| `zone_dynamic_options.py` | Generate mood-aware options |
| `z1_tour_options.py`, `z4_tour_options.py` | Zone-specific presets |
| `zone_focused_suggestions.py` | UI zone focus + “more options” → swatch buttons (no hex in chat) |

**Tour click path:** `zone_tour_actions` → `zone_option_resolver` → `zone_tour_color_apply` / `zone_tour_token_apply` → save tokens → preview refresh.

**Focus click path:** `chat_fast_path` → `zone_focused_suggestions` → `color_options` in chat → swatch click applies `zoneScopes`.
