# Storefront blueprint (agent reference)

Read this as the **ground truth** for what exists in the mobile preview (`storefront.html`). The layout order is **fixed** — merchants only change **look and feel** (colours, fonts, shapes), not content or section order.

## Page map (top → bottom)

| # | What the merchant sees | Zone | Main tokens / tools |
|---|------------------------|------|---------------------|
| 1 | Hero banner photo + scrim | Z2 | `hero.overlay`, `apply_style_tokens` |
| 2 | Logo on banner | Z2 | `hero.logoPlacement` |
| 3 | Store name & tagline band | Z2, Z3 | `hero.storeNameStyle`, `colors.surface` |
| 4 | **Follow** button | Z6, Z1 | `buttons.*`, `colors.primary` |
| 5 | Store intro text | Z3 | `typography.*`, `colors.surface` |
| 6 | Offer / coupon cards | Z5 | **View only** — `acknowledge_offers_zone`; filter preset optional |
| 7 | **Our Products** carousel | Z4S | `zoneScopes.Z4S`, `productCards.*` |
| 8 | **All Products & Services** | Z4C | `zoneScopes.Z4C`, `productCards.*` |
| 9 | Store details & opening hours | Z3 | `typography.*`, text colours |
| 10 | **Get Directions** bar | Z6 | `buttons.*`, `colors.surface` |

## How theme reaches the preview

1. **save_theme** / **apply_theme_package** → writes `tokens` (colours, fonts, hero, cards, buttons) to storage.
2. **token_mapper** converts tokens → JSON theme (`primaryColor`, `headingFont`, `hero`, `zoneScopes`, …).
3. Server **injects** that JSON into `storefront.html` and returns HTML to the iframe.
4. Browser **applyTheme()** sets CSS variables on `.sf-frame`:
   - `backgroundColor` → page backdrop (`--sf-color-page`)
   - `surfaceColor` → white panels (`--color-white`) — intro, hero info, footer
   - Fonts, radius, spacing, `data-*` on zones for hero/cards/buttons
5. **apply_style_tokens** / tour choices update tokens and refresh the same path.

## What you can and cannot change

| Can change | Cannot change |
|------------|----------------|
| Colours (global Z1 or per-zone) | Moving/hiding sections |
| Google Fonts + text scale + italic | Underline, strikethrough |
| Hero scrim, logo side, store name weight | Offer card layout (Z5) |
| Product grid layout/shape/price colour | Product names, prices, images |
| Button shape/style/colour | Copy, logo image, business hours text |

## Tool pick chart

| Situation | Tool(s) |
|-----------|-----------|
| Unsure what exists / whole-page ask | **get_storefront_page_context** first |
| Concrete style (“pill buttons”, “dark scrim”) | **apply_style_tokens** |
| Active zone tour + swatch step | Server handles clicks; else **apply_zone_tour_choice** |
| New brand from discovery | **apply_theme_package** or **save_theme** |
| Pink/blue **entire** storefront | **apply_style_tokens**(background_color, surface_color, clear_zone_color_overrides=true) |

## Worked examples (follow exactly)

### Example A — Whole storefront pink background
**Merchant:** “Make the background pink for the complete storefront.”

1. `get_storefront_page_context()` (optional if you already know the playbook)
2. `apply_style_tokens(background_color=#FFC0CB, surface_color=#FFC0CB, clear_zone_color_overrides=true)`
3. Reply: confirm **hero band, intro, gaps, product areas, footer** are pink; text was adjusted for readability. `response_type=applied`.

**Do not** call unrelated params (italic, grid3, etc.). **Do not** say backgrounds are unsupported.

### Example B — All text italic
**Merchant:** “Make all the text italic.”

1. `apply_style_tokens(heading_style=italic, body_style=italic)`
2. Reply: italic applies to intro, store info, hours, product text — not offer card images. `response_type=applied`.

### Example C — Bold store name only
**Merchant:** “Bold store name.”

1. `apply_style_tokens(store_name_style=bold)` — **not** body_style
2. Reply: only the name in the hero band. `response_type=applied`.

### Example D — Hero + buttons in one message
**Merchant:** “Dark scrim on the banner and pill buttons.”

1. `apply_style_tokens(hero_overlay=darkScrim, button_shape=pill)` — single call
2. Reply: point to banner overlay and Follow/coupon buttons. `response_type=applied`.

### Example E — Theme package then tour
**Merchant:** “I like Modern Minimalist.”

1. `apply_theme_package(...)` or `save_theme(...)`
2. Tour may start — call `get_zone_tour_status`, ask one question at a time; **do not** dump all swatches in JSON (server injects buttons).

## During zone tour

- Friendly names only: **Brand Colours**, **Hero & Header**, **Typography**, **Product Cards**, **Offer Cards**, **Buttons & CTAs**.
- Server shows **one question** + 2–4 chat buttons; merchant can also type hex or colour names.
- Your `message` = one short question; `response_type=zone_tour`.
- Z5: read-only script → **acknowledge_offers_zone** or wait for “Got it — continue”.

## Always explain *where*

After applying, tell the merchant **which part of the preview** changed (e.g. “Our Products background”, “Follow button”, “whole page backdrop”). They are looking at the phone preview on the right — reference it.
