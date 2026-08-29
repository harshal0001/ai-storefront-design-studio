# Design Studio — Implementation Plan

> **Living tracker** for the AWS Prototype storefront customisation work.
> Update status and “Next up” as tasks land. Last reviewed: **2026-05-28** (RAP-38 Phase 4 pass — most Z1–Z6 stories were already implemented; added direct-style font-scale/button-size/button-press/text-colour + a separate `z1_accent` tour sub-step. Z1-04 photo-to-palette confirmed already shipped. Z2-02 hero carousel, Z4-04 featured toggle, and Z4-07/Z6-05 ripple now implemented (storefront.html JS). Z1-03 done via chat brand-palette (`parse_brand_palette` + `brandPaletteInput`); Z6-03 CTA copy marked out of scope (content/product DB, not the style table). All in-scope Z1–Z6 stories now resolved. Audit also reconciled items shipped via RAP-36/RAP-40: 3.26/6.4 agent memory, 6.1 CDK data stack, 6.2 Lambda/API, 6.5 OTEL — all now Done).

## Sources of truth

| Document | Location | Role |
|----------|----------|------|
| Core Flow Stories (CF-01 … CF-14) | [`docs/02-core-flow-stories.md`](../docs/02-core-flow-stories.md) | Merchant journey |
| Zone Customisations (Z1 … Z6) | [`docs/03-zone-customisations.md`](../docs/03-zone-customisations.md) | Per-zone style stories |
| Guardrails (G-01 … G-15) | [`docs/04-guardrails.md`](../docs/04-guardrails.md) | AI enforcement rules |
| Project overview | [`docs/01-overview.md`](../docs/01-overview.md) | CPO decisions, teams, platform |
| DynamoDB schema | [`DDB_Schema.md`](../DDB_Schema.md) | `StorefrontStyle`, `ThemePackage` |
| Architecture | [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Code layout, dev vs prod |
| CDK next steps | [`cdk/NEXT_STEPS.md`](./cdk/NEXT_STEPS.md) | Prod migration notes |


---

## Executive summary

| Area | Status |
|------|--------|
| **Prototype shell** (agent, UI, local API, preview) | 🟢 Largely done |
| **Local DynamoDB** (tables, compose, scripts) | 🟢 Done |
| **DDB integration in app code** | 🟢 Phase 1 core done (local) |
| **Full `tokens` schema + renderer** | 🟢 Phase 2 complete (`applyTheme` + CSS data attrs; QA flags on all save paths) |
| **Contextual editing** (section/element focus, direct style) | 🟢 Core done |
| **Dev reliability** (agent concurrency, Strict Mode startup) | 🟢 RAP-17 done |
| **Zone-scoped section colours** (focused chip, not whole page) | 🟢 Verified live 2026-05-26; card-face vs panel role resolved (RAP-38) + auto-refresh resolved (PR #26) |
| **Core flows CF-01 … CF-14** | 🟡 Partial (~80%) |
| **Zone stories Z1 … Z6** | 🟢 In-scope done (~95%); Z6-03 out of scope |

---

## Current state — what is done

### Infrastructure & data

| # | Item | Status | Notes |
|---|------|--------|-------|
| D-01 | DynamoDB Local via `docker-compose.yml` | ✅ Done | Host port **8001** (FastAPI uses 8000) |
| D-02 | `StorefrontStyle` table + GSIs + TTL | ✅ Done | `scripts/dynamodb-local-create-tables.sh` |
| D-03 | `ThemePackage` table | ✅ Done | `scripts/dynamodb-local-create-theme-package-table.sh` |
| D-04 | `example.env` / `.env.example` | ✅ Done | Endpoint + table names |
| D-05 | Seed theme packages (Tuscan, Modern, Bold) | ✅ Done | `scripts/seed_theme_packages.py` |

### Application prototype (`design_studio/`)

| # | Item | Status | Notes |
|---|------|--------|-------|
| A-01 | Strands agent + Bedrock (Nova Pro) | ✅ Done | `conversational_agent/agent.py` |
| A-02 | System prompt + conversation flow | ✅ Done | Discovery → vibe → packages → save |
| A-03 | Structured output (`AgentResponse`) | ✅ Done | vibe / theme / color options |
| A-04 | Color tools (palette, WCAG) | ✅ Done | `color_engine.py`, `tools.py` |
| A-05 | Font validation (Google Fonts) | ✅ Done | `fonts.json` whitelist |
| A-06 | `save_theme` + DynamoDB draft persistence | ✅ Done | `style_repository.py` + `ConfigManager` |
| A-07 | FastAPI dev server + REST API | ✅ Done | DDB undo/redo/publish wired in `server.py` |
| A-08 | React chat + live iframe preview | ✅ Done | `frontend/src/App.jsx` |
| A-09 | Clickable vibe / theme / color UI | ✅ Done | Pills, cards, “Surprise me” |
| A-16 | Zone tour — chat-first sub-steps | ✅ Done | `zone_tour_flow.py`, one question per message |
| A-17 | Zone tour — friendly area names | ✅ Done | `zone_catalog.py` (Brand Colours, Hero & Header, …) |
| A-18 | Zone tour — preview highlight + scroll | ✅ Done | `preview_html.inject_tour_highlight()` |
| A-19 | Z4 split backgrounds (Our Products vs All Products) | ✅ Done | `Z4S` / `Z4C` in `zone_scopes.py` + template |
| A-20 | Section + element focus (chips, preview click, text detect) | ✅ Done | `section_focus.py`; `section_focus` in API + `App.jsx` |
| A-21 | Direct style (no Bedrock) — buttons, hero, cards, geometry, italic | ✅ Done | `chat_fast_path.py` → `direct_style.py`, `page_colors.py` |
| A-22 | Product card fix phrases (border radius, layout) | ✅ Done | `product_card_requests.py`; scoped by focus |
| A-23 | Theme choice without Bedrock (`I choose "…"`) | ✅ Done | `theme_choice_actions.py`; `basedOnPackageId` on catalog apply |
| A-24 | Storefront blueprint + page context for agent | ✅ Done | `storefront_blueprint.py`, `page_context.py`, `get_storefront_page_context` tool |
| A-25 | Element-focused style within active focus | ✅ Done | `element_focused_style.py` |
| A-26 | Versions API (`lastModified` on dropdown) | ✅ Done | `api_response.version_api_payload` + `test_versions_api.py` |
| A-27 | Unit tests (focus, theme choice, page context, tour) | 🟡 Partial | 23 test modules; route tests for publish/undo/redo (`test_server_publish.py`, `test_server_undo_redo.py`) + DDB-local integration; broader `TestClient` coverage todo |
| A-28 | Code refactor — shared API/preview/fast-path modules | ✅ Done | `api_response.py`, `preview_html.py`, `chat_fast_path.py`, `chat_session.py`, `message_parsers.py`, `product_card_phrases.py` |
| A-29 | Zone tour exit + panel dismiss on complete | ✅ Done | Exit button/link + `build_tour_finished_response`; `useZoneTourSync` clears UI |
| A-30 | Per-merchant Strands lock + startup greeting race fix | ✅ Done | `_agent_locks`, `_invoke_agent` / `_invoke_agent_body`; PR #18; `test_persistence.py` |
| A-31 | React Strict Mode — abort + `parseJsonResponse` on startup | ✅ Done | `App.jsx` `AbortController`, `fetchZoneTour(signal)`, HTTP error handling |
| A-32 | Zone-scoped colour fast-path (section focus) | ✅ Done | Merged; **section scoping verified live 2026-05-26** (`zone_focused_colors.py`, `apply_style_tokens(zone_code=…)`). Card-face vs panel role resolved (RAP-38, `bugfix/RAP-38-scoped-card-colour`); auto-refresh resolved (PR #26) |
| A-10 | DDB undo / redo / version list | ✅ Done | `UNDO_STACK` + `STYLE#VERSION#*`; redo wired in `server.py` |
| A-14 | Theme package tools (`list` / `apply`) | ✅ Done | CF-02 from `ThemePackage` |
| A-15 | `save_mood_tags` → `STYLE_PROFILE` | ✅ Done | CF-01 profile persistence |
| A-11 | Compare before/after (split view) | ✅ Done | CF-11 partial |
| A-12 | AgentCore runtime + Docker + CDK stack | ✅ Done | Prod path; no DDB yet |
| A-13 | Terminal CLI | ✅ Done | `uv run design-studio` |

### Not done (gaps vs spec)

- Share preview (`PREVIEW#<token>`) not implemented.
- Real product catalogue in preview (CF-04).
- Zone tour still auto-starts after theme card choice (`theme_choice_actions._maybe_start_zone_tour`) — merchant-led start todo.
- Harmony nudges (CF-07), fun facts (CF-08), persona/tips (CF-13/14).
- JSON file fallback still available when `USE_DYNAMODB=false` — use `source example.env` + DynamoDB Local to avoid `storefront_*_{shop}.json` litter.

### Known issues / tech debt (from code review)

| Priority | Issue | Notes |
|----------|--------|-------|
| ~~**Critical**~~ | ~~Chat history not passed to Strands agent~~ | **Resolved (RAP-36)** — AgentCore Memory hooks (`agent_memory.py`) inject merchant context and persist interactions in dev (`server.py`) + runtime (`runtime.py`) |
| ~~**Critical**~~ | ~~Fast path can override **active zone tour**~~ | **Resolved** — active tour runs `try_handle_zone_tour_message` exclusively (`chat_fast_path.py` L85–92) |
| ~~**Critical**~~ | ~~All DynamoDB style writes fail (`Invalid attribute value type`)~~ | **Resolved (RAP-38)** — `save_tokens_with_history` sent pre-serialized items to the resource-owned client (`resource.meta.client`) which double-serialized them; now uses a dedicated low-level `boto3.client` for `transact_write_items` |
| **Critical** | No API auth / tenant isolation | Any client can `publish`/`reset` any `merchantId` on dev server |
| **Critical** | `runtime.py` ≠ dev server | No fast-path, preview HTML, or zone-tour enrichment in AgentCore path |
| **Critical** | `reset_shop` DDB query without pagination | May leave orphan version rows |
| **High** | Dual styling models (`StorefrontConfig.zone_overrides` vs `StyleTokens`) | `customize_zone` tool vs token path |
| **High** | Theme pending packages in-memory only | Lost on server restart |
| **High** | `save_mood_tags` requires DDB | Fails in JSON fallback mode |
| **High** | No route/integration tests for `server.py` | Handler regressions easy to miss |
| **High** | Frontend hardcodes `demo-merchant` | No real multi-tenant UI |
| ~~**Medium**~~ | ~~Focused colour hits **section panel, not card faces**; role inconsistent~~ | **Resolved (RAP-38)** — product zones (Z4S/Z4C) now route card/tile wording → `cardFace`, panel/section wording → `background`; focused card element stays on the fast-path (no leak to agent default). Branch `bugfix/RAP-38-scoped-card-colour` (commit `48c8c28`); rendered via `--sf-card-face` in `storefront.html` |
| ~~**Medium**~~ | ~~Preview iframe does **not auto-refresh** after an applied edit~~ | **Resolved (PR #26)** — `App.jsx` dropped the `key={previewKey}` remount and defers revoking the old blob URL until the new one is live; eliminates the blank/stale iframe. (Local `f8434d2` superseded by #26.) |

---

## Phases (recommended order)

```text
Phase 0 — Foundation          [██████████] 100%
Phase 1 — DDB persistence     [█████████░]  90%
Phase 2 — Tokens + renderer   [██████████] 100%
Phase 3 — Core flows (Must)   [████████░░]  80%  ← you are here
Phase 4 — Zones (Critical)    [█████████▓]  95%
Phase 5 — Should / Could      [██░░░░░░░░]  20%
Phase 6 — Production hardening [███████░░░]  70%
```

---

## Phase 0 — Foundation (complete)

| ID | Task | Status | Owner | Depends on |
|----|------|--------|-------|------------|
| 0.1 | Local DynamoDB compose + healthcheck | ✅ Done | — | — |
| 0.2 | Create both DDB tables from schema | ✅ Done | — | 0.1 |
| 0.3 | Document local dev in README | ✅ Done | — | 0.1 |
| 0.4 | This implementation plan | ✅ Done | — | — |

**Next up:** Merge zone-scoped colour PR · pass chat history to agent (3.26) · CF-10 publish UI · 3.18 optional tour start.

---

## Phase 1 — DynamoDB persistence

| ID | Task | Status | Priority | Maps to |
|----|------|--------|----------|---------|
| 1.1 | `style_repository.py` with `endpoint_url` from env | ✅ Done | P0 | DDB read patterns |
| 1.2 | `get_style_profile` / `put_style_profile` (`SK=STYLE_PROFILE`) | ✅ Done | P0 | CF-01 |
| 1.3 | `get_published` / `put_published` (`SK=STYLE#PUBLISHED`) | ✅ Done | P0 | Render hot path |
| 1.4 | `get_draft` / `put_draft` (`SK=STYLE#DRAFT`) | ✅ Done | P0 | CF-10 |
| 1.5 | Version append `STYLE#VERSION#<seq>` (FIFO, max 20) | ✅ Done | P0 | CF-09 |
| 1.6 | `UNDO_STACK` get/update (undo + redo stacks) | ✅ Done | P0 | CF-09 |
| 1.7 | `PREVIEW#<token>` put + GSI2 query + TTL | ⬜ Todo | P1 | CF-12 |
| 1.8 | `ThemePackage` scan/get + cache | ✅ Done | P0 | CF-02 |
| 1.9 | Seed script: 3 theme packages | ✅ Done | P0 | `scripts/seed_theme_packages.py` |
| 1.10 | `ConfigManager` → DDB (`USE_DYNAMODB` flag) | ✅ Done | P0 | Migration |
| 1.11 | `save_theme` / `apply_theme_package` → draft + version + undo | ✅ Done | P0 | Agent tools |
| 1.12 | `server.py` reads draft tokens for preview | ✅ Done | P0 | CF-04 preview |
| 1.13 | `POST /api/publish` endpoint | ✅ Done | P0 | CF-10 |
| 1.14 | Unit tests for repository (moto or local DDB) | 🟡 Partial | P1 | JSON-mode tests + `test_style_repository_ddb.py` (DDB-local, skips if down — RAP-38); broader coverage todo |

---

## Phase 2 — `tokens` model + storefront renderer

| ID | Task | Status | Priority | Maps to |
|----|------|--------|----------|---------|
| 2.1 | Pydantic `StyleTokens` matching `DDB_Schema.md` | ✅ Done | P0 | `style_tokens.py` |
| 2.2 | Mapper: `StorefrontConfig` ↔ `tokens` + preview theme | ✅ Done | P1 | `token_mapper.py` |
| 2.3 | `applyTheme()` — wire `geometry`, extended `colors` (danger/warn/success) | ✅ Done | P0 | Z1 |
| 2.4 | Hero: `data-hero-overlay`, `data-logo-placement`, `data-tagline-placement`, store name classes | ✅ Done | P0 | Z2-02 … Z2-05 |
| 2.5 | Product cards: shape, layout, shadow, price style, tap animation, featured | ✅ Done | P0 | Z4-01 … Z4-07 |
| 2.6 | Offer cards: `filterPreset` only (picture-level) | ✅ Done | P1 | Z5, CPO #2 |
| 2.7 | Buttons: shape, style, size, press animation | ✅ Done | P0 | Z6-01 … Z6-05 |
| 2.8 | Motion: `fadeTint` / `slideTint` / `none` on navigation | ✅ Done | P2 | Z1-07 |
| 2.9 | Set `harmonyChecked` / `contrastAA` on save after tool validation | ✅ Done | P0 | `recompute_quality_flags()` runs in `ConfigManager.save_tokens`/`apply_zone` → flags set on **every** edit path (RAP-38, `bugfix/RAP-38-quality-flags`) |
| 2.10 | Agent tools: `apply_zone_tour_choice` per zone group | ✅ Done | P1 | CF-05 |
| 2.14 | Direct style parser (buttons, hero, cards, geometry, page colours) | ✅ Done | P0 | `direct_style.py`, `page_colors.py` |
| 2.18 | Zone-scoped section colours when UI focus is set | ✅ Done | P0 | Merged + **verified live 2026-05-26** (scoped to section, no whole-page leak). Card-face vs panel role resolved (RAP-38); auto-refresh resolved (PR #26) |
| 2.15 | Element-focused updates within `section_focus` | ✅ Done | P0 | `element_focused_style.py` |
| 2.16 | Storefront blueprint + `get_storefront_page_context` tool | ✅ Done | P1 | `storefront_blueprint.py`, `page_context.py` |
| 2.17 | Server-side theme card selection (no Bedrock) | ✅ Done | P0 | `theme_choice_actions.py` |
| 2.11 | `zoneScopes` per-zone colour overrides (Z2–Z6) | ✅ Done | P0 | Z2–Z6 scoped preview |
| 2.12 | Chat sub-steps + server-side tour clicks | ✅ Done | P0 | `zone_tour_flow.py`, `zone_tour_actions.py` |
| 2.13 | Preview highlight + scroll to active zone | ✅ Done | P1 | `inject_tour_highlight()`, `.sf-tour-highlight` CSS |

---

## Phase 3 — Core flow stories

Priority legend: **Must** · **Should** · **Could** (from spec).

| ID | Story | Status | Phase | Implementation notes |
|----|-------|--------|-------|----------------------|
| CF-01 | Welcome & brand identity tags | 🟢 Done | 1–3 | Vibe pill persists tags via fast-path; profile injected into agent context (RAP-38) |
| CF-02 | Full storefront theme packages | 🟢 Done | 1–3 | DDB packages + `I choose "…"` + `basedOnPackageId` (tested) + mood-ranked offering (RAP-38) |
| CF-03 | AI generates initial options | 🟢 Done | — | Structured options + Surprise me |
| CF-04 | Live preview with real data | 🔴 Todo | 3+ | Mock `storeInfo` today; integrate product DB API |
| CF-05 | Zone-by-zone guided editing | 🟢 Done | 2–4 | Chat sub-steps, friendly names, preview highlight, `ZONE_TOUR` + `subStepIndex` |
| CF-06 | Non-technical language | 🟢 Done | — | System prompt; keep auditing responses |
| CF-07 | Component harmony guidance | 🔴 Todo | 3 | Post-selection checks in agent (rounded cards ↔ rounded buttons) |
| CF-08 | Fun facts during loading | 🔴 Todo | 3 | Frontend loading state + fact rotation (20+ facts) |
| CF-09 | Undo / redo (20 deep) | 🟢 Done | 1 | DDB `UNDO_STACK` + API wired |
| CF-10 | Save & publish | 🟢 Done | 1–3 | `/api/publish` + `rollbackUntil` + `changeSummary`; React Publish confirm modal (RAP-38) |
| CF-11 | Before/after comparison | 🟢 Done | — | Compare mode in preview panel |
| CF-12 | Share preview link | 🔴 Todo | 1 | `PREVIEW#<token>`, 72h TTL, public read-only Lambda |
| CF-13 | AI persona simulation | 🔴 Backlog | 5 | Could — post-MVP |
| CF-14 | Contextual design tips | 🔴 Backlog | 5 | Could — post-MVP |

### Phase 3 task breakdown

| ID | Task | Status | Priority |
|----|------|--------|----------|
| 3.1 | CF-01: Save mood/audience tags to `STYLE_PROFILE` on first session | ✅ Done | Must | Vibe pill → fast-path `record_vibe_selection` persists/merges tags (RAP-38) |
| 3.2 | CF-01: Agent reads profile on session start | ✅ Done | Must | `merchant_profile` injected into `build_page_context_for_agent` (RAP-38) |
| 3.3 | CF-02: Agent offers packages from `ThemePackage` + mood match | ✅ Done | Must | `list_theme_packages` ranks catalogue by saved `moodTags` (`rank_packages_by_mood`, RAP-38) |
| 3.4 | CF-02: `basedOnPackageId` on published/draft items | ✅ Done | Must | Catalogue choice stamps it on draft+version and it survives publish; custom (LLM) packages have no source id. Verified by tests (RAP-38) |
| 3.5 | CF-05: Zone tour state machine in agent + `list_zones` ordering | ✅ Done | Should |
| 3.6 | CF-05: Progress indicator in React (friendly area names, not Z1–Z6 codes) | ✅ Done | Should |
| 3.7 | CF-05: Z5 skip + positive explanation (Z5-02 script) | ✅ Done | Must |
| 3.15 | CF-05: One chat question per sub-step (2–4 buttons + free text) | ✅ Done | Must |
| 3.16 | CF-05: Options in chat bubbles (not sidebar dump) | ✅ Done | Must |
| 3.17 | CF-05: Preview outlines + scrolls to edited section | ✅ Done | Must |
| 3.18 | CF-05: Tour only on merchant request (remove auto-start) | ⬜ Todo | Should |
| 3.24 | CF-05: Exit tour + dismiss live panel when complete/cancelled | ✅ Done | `build_tour_finished_response`, Exit button, `useZoneTourSync` |
| 3.25 | Fast-path: defer direct/page style when zone tour active | ✅ Done | Critical | `chat_fast_path.py` — tour-only branch when `ZoneTourManager.is_active()` |
| 3.27 | RAP-17: Per-merchant agent lock + duplicate greeting prevention | ✅ Done | Must | `server.py`, `App.jsx` Strict Mode; tests in `test_persistence.py` |
| 3.28 | Zone-scoped background when section/element chip selected | ✅ Done | Should | Merged + **verified live 2026-05-26**; card-face vs panel role resolved (RAP-38); auto-refresh resolved (PR #26) |
| 3.26 | Pass conversation history into Strands agent | ✅ Done | Critical | AgentCore Memory hooks inject merchant context + persist interactions (`agent_memory.py`, RAP-36) |
| 3.8 | CF-07: Harmony check tool after zone edits | ⬜ Todo | Should |
| 3.9 | CF-08: Loading overlay + fun facts component | ⬜ Todo | Should |
| 3.10 | CF-09: Redo stack (fix stub in `server.py`) | ✅ Done | Must | `POST /api/redo` → repo or ConfigManager |
| 3.11 | CF-10: Publish API + confirmation + change summary | ✅ Done | Must | `/api/publish` returns `changeSummary`; React confirm modal shows it + rollback date (RAP-38) |
| 3.12 | CF-10: Rollback within 7 days (`rollbackUntil`) | ✅ Done | Must | Returned on publish response |
| 3.19 | Section/element focus in chat + preview | ✅ Done | Should | `section_focus.py`, chips, iframe click, `focusZone` query |
| 3.20 | Direct style + page colour without Bedrock | ✅ Done | Should | Server fast-path before tour/agent |
| 3.21 | Storefront blueprint injected into agent context | ✅ Done | Should | `page_context` prefix + `get_storefront_page_context` tool |
| 3.22 | Product card border-radius / layout fix phrases | ✅ Done | Must | `product_card_requests.py` |
| 3.23 | Versions dropdown with `lastModified` | ✅ Done | Should | `GET /api/versions/{id}` payload |
| 3.13 | CF-12: Generate preview link API + read-only page | ⬜ Todo | Should |
| 3.14 | CF-04: Product catalogue API integration in preview | ⬜ Todo | Must |

---

## Phase 4 — Zone customisation stories

### Z1 — Brand colours

| ID | Story | Status | Blocked by |
|----|-------|--------|------------|
| Z1-01 | Brand palette cards by mood | 🟢 Done | Tour `z1_palette` — 4–5 theme-package cards (`z1_tour_options.generate_z1_palette_options`); auto-skip when palette already configured |
| Z1-02 | Accent colour selection | 🟢 Done | Tour `z1_accent` — pairing rationale per swatch (complement/analogous/triad/split) |
| Z1-03 | Upload own palette | 🟢 Done | Chat brand-palette any format (names/hex/descriptions): `is_brand_palette_request` routes → agent maps to roles, offers 3 arrangements, validates contrast; explicit hexes stored in `brandPaletteInput` (RAP-38) |
| Z1-04 | Photo-to-palette extraction | 🟢 Done | Image upload → `palette.extract_palette` (PIL median-cut) → `build_palette_prompt` → agent theme packages |
| Z1-05 | Background colour | 🟢 Done | Tour `z1_backdrop` — four named presets (Pure White, Warm White, Light Grey, Soft Cream) |
| Z1-06 | Colour harmony validation | 🟢 Done | `harmony_feedback.assess_brand_colours` blocks bad Z1 tour saves (&lt;3:1 primary/bg, WCAG AA); warns on accent clash |
| Z1-07 | Subtle colour transitions | 🟢 Done | Tour `z1_motion` — Fade / Slide-tint / None → `motion.transition` |

### Z2 — Hero & header

| ID | Story | Status | Blocked by |
|----|-------|--------|------------|
| Z2-02 | Hero layout style | 🟢 Done | `syncHeroCarousel()` auto-advances banner dots in carousel mode + split layout CSS — demo on mock hero (real multi-image = CF-04) |
| Z2-03 | Tagline overlay placement | 🟢 Done | `data-tagline-placement` rendered (4 variants) |
| Z2-04 | Logo placement | 🟢 Done | `data-logo-placement` rendered (left/center/right) |
| Z2-05 | Store name styling | 🟢 Done | `data-store-name-style` rendered (subtle/balanced/bold) |
| Z2-06 | Hero / store-name **section** background (not whole page) | 🟢 Done | Section scoping **verified live 2026-05-26** (`zoneScopes.Z2.surface` when chip focused) |

### Z3 — Typography

| ID | Story | Status | Blocked by |
|----|-------|--------|------------|
| Z3-01 | Font pairing selection | 🟢 Done | Theme packages + validate_font |
| Z3-02 | Font size scaling | 🟢 Done | Direct-style phrases set `typography.scale` (RAP-38) |
| Z3-03 | Text colour customisation | 🟢 Done | Direct-style dark/light/hex → `textPrimary` (RAP-38) |

### Z4 — Product cards

| ID | Story | Status | Blocked by |
|----|-------|--------|------------|
| Z4-01 | Card shape & layout | 🟢 Done | Rendered; tour presets + `direct_style` + `product_card_requests` |
| Z4-02 | Card shadow & elevation | 🟢 Done | `data-card-shadow` rendered (flat/subtle/elevated/floating) |
| Z4-03 | Price display style | 🟢 Done | Four styles (bold red, accent, understated grey, badge pill); catalogue sample prices; mood-ranked `z4_prices` step |
| Z4-04 | Featured products styling | 🟢 Done | 3 styles render; `syncProductCardFeatured` highlights first card; `feature my product` direct phrase toggles it (which-products = CF-04) |
| Z4-07 | Tap animation | 🟢 Done | scaleDown/none + **ripple** now wired (`spawnRipple` JS on card tap) |
| Z4-09 | Click product card → scoped chat focus | 🟢 Done | Preview `postMessage` + `section_focus` |
| Z4-08 | Separate section backgrounds | 🟢 Done | `Z4S` / `Z4C` scoped surfaces |

### Z5 — Offer cards

| ID | Story | Status | Blocked by |
|----|-------|--------|------------|
| Z5-01 | View-only in preview | 🟢 Done | Renders + `data-offer-filter`; view-only by design |
| Z5-02 | Positive AI explanation | 🟢 Done | `acknowledge_offers_zone` + prompt |

### Z6 — Buttons & CTAs

| ID | Story | Status | Blocked by |
|----|-------|--------|------------|
| Z6-01 | Button shape | 🟢 Done | `data-button-shape` rendered; tour + direct style |
| Z6-02 | Button colour & style | 🟢 Done | `data-button-style` rendered; `z6_cta_colour` sub-step |
| Z6-03 | CTA text options | ⚪ Out of scope | **Content**, not style — CTA copy lives in the product DB, not `StorefrontStyle` (`DDB_Schema.md`). Tracked in the product/content workstream |
| Z6-04 | Button size | 🟢 Done | Direct-style phrases set `buttons.size` (RAP-38) |
| Z6-05 | Press animation | 🟢 Done | darken/scale + **ripple** all rendered (`spawnRipple` JS on button press) |

> **Note:** Z6-03 (CTA copy) is out of scope for `StorefrontStyle` per `DDB_Schema.md`. Track under product DB / content workstream.

---

## Phase 5 — Should / Could & guardrails

| ID | Task | Status | Maps to |
|----|------|--------|---------|
| 5.1 | Guardrail tests in agent tools (G-01, G-03, G-04, G-05, G-14) | ⬜ Todo | `docs/04-guardrails.md` |
| 5.2 | Block paid fonts → `headingFontFallbackFrom` | 🟡 Partial | Z3-01, G-03 — paid fonts blocked via Google-Fonts whitelist (`validate_font`); auto-fallback substitution todo |
| 5.3 | CF-13 persona simulation | ⬜ Backlog | Could |
| 5.4 | CF-14 contextual tips cards | ⬜ Backlog | Could |
| 5.5 | Screenshot service (`/api/screenshot`) | ✅ Done | Playwright optional extra; `/api/screenshot/agentcore` alias |

---

## Phase 6 — Production hardening

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 6.1 | `DesignStudioDataStack` CDK (DDB tables in AWS) | ✅ Done | `cdk/src/data-stack.ts` — both tables + GSIs + PITR (RAP-40) |
| 6.2 | Lambda/API Gateway for storefront + chat (replace FastAPI in prod) | ✅ Done | `lambda_backend/handler.py` + `cdk/src/api-stack.ts` (Function URL, bundles agent) |
| 6.3 | AgentCore + tenant-scoped DDB access (STS + LeadingKeys) | ⬜ Todo | Security model in NEXT_STEPS |
| 6.4 | Persist chat history + pass to agent / AgentCore `session_id` | ✅ Done | AgentCore Memory hooks wired in `server.py` + `runtime.py` (RAP-36) |
| 6.5 | Observability (OTEL already in container) | ✅ Done | `opentelemetry-instrument` in Dockerfile CMD + `aws-opentelemetry-distro` |
| 6.6 | E2E tests (Playwright) for CF-01 → CF-10 happy path | 🟡 Partial | `frontend/e2e-focus-test.mjs` (focus + card radius) |

---

## Sprint board — what to do next

### ✅ Done (mark complete in PRs)

- [x] D-01 … D-05 — Local DynamoDB, tables, env, seed packages
- [x] 0.1 … 0.4 — Phase 0 foundation
- [x] 1.1 … 1.13 — DDB repository, ConfigManager, tools, server (except 1.7 preview links)
- [x] 2.1 … 2.8, 2.10 … 2.17 — Tokens, renderer, zone tour, direct style, blueprint, theme choice
- [x] 3.5 … 3.7, 3.10, 3.12, 3.15 … 3.17, 3.19 … 3.23 — Tour UX, redo, focus, versions
- [x] A-16 … A-31 — Zone tour, focus, refactor modules, exit tour UX, RAP-17 concurrency
- [x] 3.24 — Zone tour exit + panel dismiss
- [x] 3.25 — Fast-path defers to active zone tour
- [x] 3.27 — RAP-17 agent lock + startup Strict Mode (PR #18)

### 🔜 Next in line (recommended sequence)

1. **3.28 / 2.18 / A-32** — Commit & PR zone-scoped section colours (`zone_focused_colors.py`)
2. **3.26** — Pass `chat_session` history into Strands agent (or AgentCore session)
3. **CF-10 UI** — Publish button + confirmation + change summary in React
4. **3.18** — Optional zone tour start (remove auto-start from `theme_choice_actions`)
5. **2.9** — `harmonyChecked` / `contrastAA` on direct-style and zone-tour saves
6. **1.7** — Share preview `PREVIEW#<token>` (CF-12)
7. **Route tests** — FastAPI `TestClient` for `/api/chat` empty-message race

### 📋 Backlog (after MVP path)

- CF-04 real catalogue · CF-07 harmony nudges · CF-08 fun facts · CF-12 share link
- Z6-03 CTA copy (content/product DB — out of scope for the style studio)
- Phase 6 tenant isolation (6.3) · full Playwright happy-path E2E (6.6)

---

## Progress log

| Date | Update |
|------|--------|
| 2026-05-20 | Plan created. Phase 0 complete (DDB local, tables, prototype baseline). |
| 2026-05-20 | `ThemePackage` table added locally (was missing after partial create). |
| 2026-05-20 | **Phase 1 core:** `style_repository.py`, `style_tokens.py`, `token_mapper.py`, DDB-backed `ConfigManager`, new agent tools, server undo/redo/publish, seed script. |
| 2026-05-20 | **CF-05:** Zone tour (`zone_tour.py`, `ZONE_TOUR` DDB item, 7 tour tools, progress bar UI, Z5 positive script). |
| 2026-05-20 | **CF-05 UX:** Chat-first sub-steps (`zone_tour_flow.py`), friendly zone names (`zone_catalog.py`), options in chat only, free-text matching, preview highlight/scroll, Z4S/Z4C split backgrounds. |
| 2026-05-22 | **Contextual editing:** `section_focus.py` (sections + elements, preview click, text detect), `direct_style.py` / `page_colors.py` server fast-path, `product_card_requests.py`, `element_focused_style.py`. |
| 2026-05-22 | **Agent context:** `storefront_blueprint.py`, `page_context.py`, `get_storefront_page_context` tool; blueprint in system prompt. |
| 2026-05-22 | **Theme choice:** `theme_choice_actions.py` — `I choose "…"` without Bedrock; `basedOnPackageId` on catalog apply; pending package cache. |
| 2026-05-22 | **Tests & API:** `test_section_focus`, `test_page_context`, `test_theme_choice_actions`, `test_element_focused_style`, `test_product_card_requests`, `test_versions_api`; redo endpoint verified. |
| 2026-05-22 | **Zone tour UX fix:** Exit customization (button + chat phrases); `zone_tour.active: false` on complete/cancel; frontend `useZoneTourSync` clears stuck panel. |
| 2026-05-22 | **Refactor:** Extracted `api_response`, `preview_html`, `chat_fast_path`, `chat_session`, `message_parsers`, `product_card_phrases`; slimmed `server.py`. |
| 2026-05-22 | **Code review:** Documented critical/high tech debt (history not to LLM, fast-path vs tour, auth, prod parity). |
| 2026-05-25 | **RAP-17 (PR #18):** Per-merchant `asyncio.Lock` around Strands; greeting `history` re-read under lock; `_invoke_agent_body` avoids nested lock; React startup `AbortController` + `parseJsonResponse`; regression tests in `test_persistence.py`. |
| 2026-05-25 | **Zone-scoped colours (WIP, local):** `zone_focused_colors.py` applies `tokens.zoneScopes` when section chip focused (fixes whole-page background bug); `apply_style_tokens(zone_code=…)`; compound colour names in `page_colors.py`. |
| 2026-05-25 | **Tests:** Suite at **106** passing (`test_zone_focused_colors`, expanded `test_persistence`). Marked **3.25** tour fast-path guard as done. |
| 2026-05-26 | **RAP-38 (bugfix):** Every DynamoDB style write failed — `save_tokens_with_history` passed `TypeSerializer`-encoded items to the *resource-owned* client (`resource.meta.client`), which serialized them again → `ValidationException: Invalid attribute value type` (direct style 500'd; agent path apologised). Fixed with a dedicated low-level `boto3.client` for `transact_write_items`. Verified live: `STYLE#DRAFT` / `STYLE#VERSION#0001` / `UNDO_STACK` persist with `buttons.shape=pill`. **Lesson:** suite runs `USE_DYNAMODB=false`, so the DDB write path was never exercised — 122 tests passed while all writes were broken. Added `test_style_repository_ddb.py` (DDB-local integration); suite now **123**. |
| 2026-05-26 | **Live verification sweep (Wave A + B).** Backend persistence ✅ end-to-end against DynamoDB Local: D-01/02/03/05, 1.3/1.4/1.5/1.6/1.8/1.9/1.12/1.13, A-06/07/10/26, CF-09, 3.10, 3.12, 3.23 (draft→version→undo/redo→versions→publish w/ 7-day rollback; 3 theme packages seeded). Frontend ✅: A-08/30/31 (chat + live preview, single greeting), A-21/2.5/2.7/2.14 (direct style), A-20/3.19/Z4-09 (click element → scoped focus), A-09/A-23/2.17/CF-02/CF-03 (clickable theme cards / vibe pills). Zone-scoped section colours (A-32/2.18/3.28/Z2-06) confirmed **scoped to the section** (no whole-page leak). Two issues logged for a follow-up bugfix: focused colour paints the section panel not the card faces (role inconsistent), and the preview doesn't auto-refresh. |
| 2026-05-26 | **B5 follow-up resolved.** Card-face scoping recovered onto `main` via `bugfix/RAP-38-scoped-card-colour` (cherry-picked `e459f68` → `48c8c28`; clean over PR #26): product zones (Z4S/Z4C) now distinguish card/tile wording (`cardFace`) from panel/section wording (`background`), with `--sf-card-face` rendering in `storefront.html`; 126 tests passing. **Preview auto-refresh** was independently fixed by **PR #26** (`App.jsx` drops the `key={previewKey}` remount + defers blob-URL revocation) — local `f8434d2` dropped as superseded. PR #26 also landed a code-review/security pass (CORS lockdown, merchantId validation, typed request bodies, generic error + correlation IDs, server-side screenshot HTML, `reset_zone` confirmation guard). |
| 2026-05-26 | **Phase 2 complete (2.9).** WCAG QA flags (`colors.harmonyChecked` / `contrastAA`) were only set on the `save_theme` path; direct style, page colours, zone tour, and scoped colour edits left them stale. Added `recompute_quality_flags()` and call it in `ConfigManager.save_tokens`/`apply_zone` so the flags track the live palette on **every** edit path (mirrors the existing contrast/harmony checks). +3 tests; suite **126** passing. Branch `bugfix/RAP-38-quality-flags`. Phase 2 now 100%. |

---

## Module layout (post-refactor)

| Module | Role |
|--------|------|
| `server.py` | FastAPI routes; `_agents` + `_agent_locks` per merchant; `chat` pipeline |
| `api_response.py` | `preview_payload`, `enrich_with_zone_tour`, tour/applied response builders |
| `preview_html.py` | `get_storefront_html`, theme injection, tour highlights |
| `chat_fast_path.py` | Ordered server-side handlers (no Bedrock); tour-exclusive when active |
| `zone_focused_colors.py` | Section-scoped colours → `zoneScopes` (WIP, not on main) |
| `chat_session.py` | In-memory chat history per merchant (dev only) |
| `message_parsers.py` | Shared `I choose`, skip, exit, zone-option parsers |
| `product_card_phrases.py` | Shared product-card regex patterns |
| `runtime.py` | AgentCore entry (no fast-path / preview yet) |

---

## Contextual editing — implementation reference

Merchants can focus a **section** (zone chip) or **element** (sub-chip / preview click) before typing. Server resolves focus, applies targeted updates without Bedrock when possible, then falls through to zone tour or agent.

**Request flow** (`POST /api/chat` → `run_fast_path()` then agent)

```text
message + focusZone / focusSectionId / focusElementId
  → merge_focus()
  → run_fast_path() in chat_fast_path.py:
       [if tour active] zone_tour only → else:
       apply_zone_focused_color (when UI focus) → apply_focused_element_style
       → direct_style → page_colors → product_card_fix → theme_choice → zone_tour start
  → else agent (+ page_context / focus prefix)     # Bedrock
```

**Key modules**

| File | Role |
|------|------|
| `chat_fast_path.py` | Orchestrates handlers; `direct_style_response()` |
| `section_focus.py` | Section/element definitions, `merge_focus`, highlight selectors |
| `element_focused_style.py` | Element-scoped updates |
| `direct_style.py` | NL → token fields |
| `page_colors.py` | Whole-page colour phrases + `resolve_color_from_text` |
| `zone_focused_colors.py` | Section-scoped background/surface via `zoneScopes` (WIP) |
| `product_card_requests.py` | Product card fixes (uses `product_card_phrases.py`) |
| `page_context.py` | Agent context snapshot |
| `storefront_blueprint.py` | Layout map + playbooks |
| `theme_choice_actions.py` | Theme card clicks without LLM |
| `frontend/src/hooks/useZoneTourSync.js` | Sync/clear zone tour state from API |
| `frontend/src/App.jsx` | Chat UI, section chips, tour bar, exit controls; `parseJsonResponse` on startup |

**RAP-17 startup flow** (`App.jsx` mount effect): fetch storefront (abortable) → `fetchZoneTour(signal)` → empty `POST /api/chat` for greeting. Server serializes Strands per `merchantId` and runs at most one `GREETING_PROMPT` when history is empty under lock.

**API fields:** `section_focus` (`zone`, `sectionId`, `elementId`, `label`, `displayLabel`, `highlightSelectors`, `source`), plus existing `zone_tour`, `html`, `message`.

---

## Zone tour — implementation reference (CF-05)

Merchant-facing areas (not Z-codes in UI):

| Code | UI name | Sub-steps (chat) |
|------|---------|------------------|
| Z1 | Brand Colours | Follow/accent → page backdrop → intro panels |
| Z2 | Hero & Header | Layout card → hero band colour |
| Z3 | Typography | Font pairing → intro panel colour |
| Z4 | Product Cards | Our Products bg → All Products bg → card layout → price accent |
| Z5 | Offer Cards | Info-only (platform-managed) + “Got it — continue” |
| Z6 | Buttons & CTAs | Button style → CTA colour |

**Key modules**

| File | Role |
|------|------|
| `zone_tour.py` | Tour state (`currentIndex`, `subStepIndex`, completed/skipped) in DDB `SK=ZONE_TOUR` |
| `zone_tour_flow.py` | Sub-step definitions, batched options, preview highlight selectors |
| `zone_tour_actions.py` | Server-side handling of clicks + free text (no Bedrock) |
| `zone_catalog.py` | Friendly labels + `applies_to` hints |
| `zone_color_presets.py` | Canonical swatches per zone (place-accurate descriptions) |
| `zone_presets.py` | Layout / typography / button presets |
| `zone_scopes.py` | `tokens.zoneScopes` for Z2–Z6 (and Z4S/Z4C) |
| `api_response.py` | `build_tour_response`, `build_tour_finished_response`, `enrich_with_zone_tour` |
| `preview_html.py` | `inject_tour_highlight()` in preview HTML |
| `message_parsers.py` | Exit / skip / choose phrase matching |

**Exit tour:** Merchant can click **Exit customization**, type `Exit zone customization`, or similar — handled in `zone_tour_actions` via `EXIT_ZONE_TOUR_RE`.

**API fields during tour:** `zone_tour` (incl. `current_prompt`, `sub_step_index`, `highlight_selectors`), `color_options` \| `zone_options`, `section_focus`, `message`. When tour ends: `zone_tour: { active: false, status: "completed"|"cancelled" }`.

---

## How to update this document

1. Change task **Status**: `✅ Done` · `🟡 Partial` · `⬜ Todo` · `🔴 Blocked` · `⬜ Backlog`
2. Move items in **Sprint board** checkboxes.
3. Add a row to **Progress log** when a phase milestone lands.
4. Adjust phase progress bars in the header.

---

## Quick commands

```bash
# DynamoDB Local (avoids storefront_*_{shop}.json files on disk)
cd design_studio && docker compose up -d dynamodb-local
source example.env
./scripts/dynamodb-local-create-tables.sh
uv run python scripts/seed_theme_packages.py

# Dev stack — must source example.env in each terminal
uv run design-server          # API :8000
cd frontend && npm run dev    # UI :5173
```
