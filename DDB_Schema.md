# Storefront Customisation — DynamoDB Schema

Scope decision (locked in this iteration): **this table stores styles only**. Merchant content (banner image, logo, intro text, tag pills, product list, CTA copy, tagline text, featured-product picks) lives in the product DB and is fetched separately by the renderer. The agent generates *only* the visual tokens that drive the look-and-feel layer.

Two tables:
1. `StorefrontStyle` — per-shop style data (drafts, published, version history, undo stack, share previews, style profile).
2. `ThemePackage` — global pre-built theme packages (CPO #6, 2–3 starting points like Tuscan Workshop / Modern Minimalist / Bold & Bright).

Maps to:
- The themeable surfaces of `storefront.html` (CSS custom properties + `data-*` attributes on `.sf-frame`)
- Core Flow Stories CF-01 .. CF-14 (style-relevant ones only)
- Zone Customisation Stories Z1 .. Z6 (style-relevant fields only)
- CPO Review decisions (fixed zone order, picture-level-only Z5, theme packages, paid-font substitution)

---

## Table 1 — `StorefrontStyle`

### Keys and common attributes

| Attribute | Type | Role |
|---|---|---|
| `PK` | String | Partition key — always `MERCHANT#<shopUuid>` |
| `SK` | String | Sort key — see namespaces below |
| `type` | String | Redundant copy of item class; used as GSI1 PK |
| `version` | Number | Monotonically increasing per shop |
| `updatedAt` | String (ISO-8601) | GSI1 SK |
| `ttl` | Number | Epoch seconds — DDB native TTL on `PREVIEW` items only |

### Sort-key namespaces

| SK pattern | Item type | Cardinality per shop | Purpose |
|---|---|---|---|
| `STYLE_PROFILE` | Style inputs from the merchant | 1 | CF-01 mood tags, uploaded/extracted brand palette — inputs the agent re-uses across sessions |
| `STYLE#PUBLISHED` | Live style tokens | 1 | What the frontend reads on render |
| `STYLE#DRAFT` | Work-in-progress | 0..1 | Agent writes here during a session; merchant promotes via CF-10 |
| `STYLE#VERSION#<seq>` | Historical version | up to 20, FIFO | `seq` zero-padded to 4 digits so lexical sort = chronological |
| `UNDO_STACK` | Undo/redo pointer + stacks | 1 | CF-09 |
| `ZONE_TOUR` | Guided zone tour progress | 0..1 | CF-05 — `currentIndex`, `subStepIndex`, completed/skipped |
| `PREVIEW#<token>` | Share-preview snapshot | 0..N | CF-12, 72h native TTL |

### GSIs

- **GSI1 — `type-updatedAt-index`**: PK = `type`, SK = `updatedAt`. Audit queries like "all styles modified in the last hour".
- **GSI2 — `previewToken-index`** (sparse): PK = `previewToken`. Direct lookup for share-preview URLs without needing the `shopUuid`.

---

## Parameter taxonomy

The agent generates a single `tokens` blob inside every `STYLE#*` item. Every field maps to either a CSS custom property the template already reads, or a `data-*` attribute on `.sf-frame`, or a class hook the renderer flips.

```
tokens
├── colors              (Z1 — Brand Colours)
├── typography          (Z3 — Typography)
├── geometry            (drives RADIUS_MAP + SPACING_MAP presets)
├── hero                (Z2 — Hero & Header, style-only fields)
├── productCards        (Z4 — Product Cards, style-only fields)
├── offerCards          (Z5 — picture-level beautification only, per CPO #2)
├── buttons             (Z6 — Buttons & CTAs, style-only fields)
├── motion              (Z1-07 — transitions)
└── zoneScopes          (optional per-zone colour overrides — Z2, Z3, Z4S, Z4C, Z4, Z6)
```

`zoneScopes` holds scoped `colors` for preview sections without changing global `tokens.colors` (Z1 sets globals via `save_theme` / tour Brand Colours steps).

Every enum is a closed token vocabulary so the agent can't hallucinate values the template can't render.

---

## Item schemas

### 1. STYLE_PROFILE — per-shop, single item

Style-relevant inputs only. Mood tags and the extracted palette are agent inputs that need to survive across sessions. Business category tags / logo image / intro copy are content and live in the product DB.

```json
{
  "PK": "MERCHANT#demo-shop-uuid",
  "SK": "STYLE_PROFILE",
  "type": "STYLE_PROFILE",
  "shopUuid": "demo-shop-uuid",
  "merchantCategory": "cafe_bar",
  "moodTags": ["modern", "warm", "artisan"],
  "audienceTags": ["aperitivo", "students"],
  "brandPaletteInput": {
    "source": "photoExtracted",
    "extractedColors": ["#A12B43", "#F1E6D2", "#1A1A1A", "#7A5D3B"]
  },
  "createdAt": "2026-05-20T10:00:00Z",
  "updatedAt": "2026-05-20T10:30:00Z"
}
```

`brandPaletteInput.source` ∈ `manual` | `photoExtracted` (Z1-03 / Z1-04). The source image itself is content and is not stored here — the renderer can pull it from the product DB if/when needed.

### 2. STYLE — published, draft, and version snapshots (same schema)

```json
{
  "PK": "MERCHANT#demo-shop-uuid",
  "SK": "STYLE#PUBLISHED",
  "type": "STYLE",
  "styleState": "published",
  "styleId": "sty_2026_05_20_a3f9",
  "version": 14,
  "basedOnPackageId": "tuscan_workshop",
  "createdBy": "agent",
  "agentSessionId": "sess-9b1e2",
  "agentPrompt": "make it warmer and a bit more rustic",
  "createdAt": "2026-05-20T10:00:00Z",
  "publishedAt": "2026-05-20T11:00:00Z",
  "rollbackUntil": "2026-05-27T11:00:00Z",
  "updatedAt": "2026-05-20T11:00:00Z",

  "tokens": {

    "colors": {
      "primary":        "#B63F81",
      "accent":         "#9E3570",
      "secondary":      "#2C2C2C",
      "background":     "#F8F9FA",
      "surface":        "#FFFFFF",
      "textPrimary":    "#3B3B4D",
      "textSecondary":  "#5F6E7D",
      "danger":         "#D72F4D",
      "warn":           "#C34F03",
      "success":        "#0A600A",
      "paletteName":    "Sunset Warmth",
      "harmonyChecked": true,
      "contrastAA":     true
    },

    "typography": {
      "headingFont":              "Montserrat",
      "bodyFont":                 "Roboto",
      "headingFontFallbackFrom":  null,
      "scale":                    "standard",
      "pairingName":              "Modern Pair"
    },

    "geometry": {
      "borderRadiusPreset": "rounded",
      "spacingPreset":      "normal"
    },

    "hero": {
      "layout":            "fullWidth",
      "overlay":           "autoScrim",
      "logoPlacement":     "right",
      "taglinePlacement":  "center",
      "storeNameStyle":    "balanced"
    },

    "productCards": {
      "shape":          "rounded",
      "layout":         "grid2",
      "shadow":         "subtle",
      "priceStyle":     "accentColor",
      "tapAnimation":   "scaleDown",
      "featured": {
        "enabled":      false,
        "style":        "largerCard"
      }
    },

    "offerCards": {
      "merchantCanCustomise": false,
      "imageBeautification": {
        "filterPreset": "warm"
      }
    },

    "buttons": {
      "shape":          "rounded",
      "style":          "filled",
      "size":           "standard",
      "pressAnimation": "scale"
    },

    "motion": {
      "transition": "fadeTint"
    }
  },

  "changeSummary": {
    "zonesTouched":  ["Z1", "Z4"],
    "humanSummary":  "Switched to a warmer palette and rounder product cards."
  }
}
```

#### Enum vocabularies (rock-solid set the agent must pick from)

| Field | Allowed values | Maps to |
|---|---|---|
| `colors.primary` / `accent` / `secondary` / `background` / `surface` / `textPrimary` / `textSecondary` / `danger` / `warn` / `success` | 6-digit hex, validated for WCAG AA contrast vs `background` and `surface` | CSS vars `--sf-color-*`, `--color-*` |
| `colors.harmonyChecked` / `contrastAA` | boolean — agent must set true after Z1-06 / Z3-03 checks pass | renderer doesn't read these; used for audit |
| `typography.headingFont` / `bodyFont` | Google Fonts family names only (no paid fonts — CPO #3) | dynamic `<link>` injection in `applyTheme()` |
| `typography.headingFontFallbackFrom` | string or `null` — set if AI substituted a paid font request (Z3-01) | audit only |
| `typography.scale` | `compact` \| `standard` \| `generous` | future `--sf-font-scale-*` set (Z3-02) |
| `geometry.borderRadiusPreset` | `sharp` \| `soft` \| `rounded` \| `pill` | `RADIUS_MAP` in template |
| `geometry.spacingPreset` | `compact` \| `normal` \| `spacious` | `SPACING_MAP` in template |
| `hero.layout` | `fullWidth` \| `splitImageText` \| `carousel` | Z2-02 — needs render work for non-fullWidth |
| `hero.overlay` | `none` \| `lightScrim` \| `autoScrim` \| `darkScrim` | `data-hero-overlay` |
| `hero.logoPlacement` | `left` \| `center` \| `right` | `data-logo-placement` (Z2-04 — placement only; logo image is content) |
| `hero.taglinePlacement` | `none` \| `center` \| `bottomLeft` \| `bottomRight` | `data-tagline-placement` (Z2-03 — placement only; text is content) |
| `hero.storeNameStyle` | `subtle` \| `balanced` \| `bold` | Z2-05; CSS class on `.sf-info__head` |
| `productCards.shape` | `rounded` \| `sharp` \| `circularImage` | Z4-01 |
| `productCards.layout` | `grid2` \| `grid3` \| `list` \| `featuredPlusGrid` | Z4-01 |
| `productCards.shadow` | `flat` \| `subtle` \| `elevated` \| `floating` | Z4-02 |
| `productCards.priceStyle` | `boldRed` \| `accentColor` \| `understatedGrey` \| `badgePill` | Z4-03 |
| `productCards.tapAnimation` | `none` \| `scaleDown` \| `ripple` | Z4-07 |
| `productCards.featured.enabled` | boolean | Z4-04 — agent toggles; the *which products* selection is content |
| `productCards.featured.style` | `largerCard` \| `differentColor` \| `badge` | Z4-04 |
| `offerCards.imageBeautification.filterPreset` | `null` \| `warm` \| `cool` \| `vivid` | Z5 (CPO #2 — picture-level only) |
| `buttons.shape` | `sharp` \| `subtleRounded` \| `rounded` \| `pill` | Z6-01 |
| `buttons.style` | `filled` \| `outlined` \| `soft` \| `ghost` | Z6-02 |
| `buttons.size` | `compact` \| `standard` \| `large` | Z6-04 |
| `buttons.pressAnimation` | `none` \| `darken` \| `scale` \| `ripple` | Z6-05 |
| `motion.transition` | `none` \| `fadeTint` \| `slideTint` | Z1-07 |

### 2. ZONE_TOUR (CF-05)

Persists guided editing progress for the Design Studio chat UI. Not used on the public render path.

```json
{
  "PK": "MERCHANT#demo-shop-uuid",
  "SK": "ZONE_TOUR",
  "type": "ZONE_TOUR",
  "status": "active",
  "currentIndex": 2,
  "subStepIndex": 1,
  "completed": ["Z1", "Z2"],
  "skipped": [],
  "updatedAt": "2026-05-20T14:00:00Z"
}
```

| Field | Meaning |
|---|---|
| `currentIndex` | Index into tour areas (0 = Brand Colours … 5 = Buttons & CTAs) |
| `subStepIndex` | Index within the current area's chat sub-steps (see `zone_tour_flow.py`) |
| `completed` / `skipped` | Area codes `Z1` … `Z6` finished or skipped |

### 3. UNDO_STACK (CF-09)

```json
{
  "PK":              "MERCHANT#demo-shop-uuid",
  "SK":              "UNDO_STACK",
  "type":            "UNDO_STACK",
  "currentVersion":  14,
  "undoStack":       [10, 11, 12, 13, 14],
  "redoStack":       [15, 16],
  "maxDepth":        20,
  "updatedAt":       "2026-05-20T11:00:00Z"
}
```

Each entry refers to a `STYLE#VERSION#<seq>` item. When `len(undoStack) + len(redoStack) > 20`, evict the oldest `STYLE#VERSION` item.

### 4. PREVIEW (CF-12 — 72h share link, planned)

**Implementation status:** schema-ready only. `IMPLEMENTATION_PLAN.md` still tracks CF-12 as todo; no API currently writes `PREVIEW#<token>` items or serves public read-only preview links.

```json
{
  "PK":             "MERCHANT#demo-shop-uuid",
  "SK":             "PREVIEW#abc123xyz",
  "type":           "PREVIEW",
  "previewToken":   "abc123xyz",
  "styleVersion":   14,
  "tokensSnapshot": { "...": "inlined tokens — read-only" },
  "createdAt":      "2026-05-20T11:00:00Z",
  "expiresAt":      "2026-05-23T11:00:00Z",
  "ttl":            1716462000
}
```

`ttl` is the native DynamoDB TTL attribute (epoch seconds). DDB auto-deletes after expiry.

---

## Table 2 — `ThemePackage`

Global, pre-built starting points (CPO #6). Small table — expected 2–3 rows, occasionally more if marketing adds seasonal themes.

| Attribute | Type | Role |
|---|---|---|
| `packageId` | String | Partition key. Stable slug e.g. `tuscan_workshop`, `modern_minimalist`, `bold_and_bright` |
| `displayName` | String | UI label |
| `description` | String | One-liner shown in the picker |
| `moodMatch` | List\<String> | Tags the agent uses to match a merchant's `moodTags` |
| `previewImageUrl` | String | Thumbnail for the picker |
| `tokens` | Map | Same shape as `STYLE.tokens` — drop-in starting point |
| `active` | Boolean | Soft-disable without deletion |
| `updatedAt` | String | Audit |

### Example

```json
{
  "packageId":       "tuscan_workshop",
  "displayName":     "Tuscan Workshop",
  "description":     "Warm ivory background, earthy palette, rounded cards, friendly fonts.",
  "moodMatch":       ["warm", "rustic", "artisan", "cozy"],
  "previewImageUrl": "s3://storefront-static/packages/tuscan_workshop.png",
  "active":          true,
  "updatedAt":       "2026-05-15T08:00:00Z",
  "tokens": {
    "colors": {
      "primary": "#A86B3F", "accent": "#7A4A1E", "secondary": "#2C2419",
      "background": "#FBF6EE", "surface": "#FFFFFF",
      "textPrimary": "#2C2419", "textSecondary": "#6E5A41",
      "danger": "#D72F4D", "warn": "#C34F03", "success": "#0A600A",
      "paletteName": "Tuscan Earth", "harmonyChecked": true, "contrastAA": true
    },
    "typography": {
      "headingFont": "Playfair Display", "bodyFont": "Lora",
      "headingFontFallbackFrom": null, "scale": "standard",
      "pairingName": "Classic Duo"
    },
    "geometry":     { "borderRadiusPreset": "rounded", "spacingPreset": "normal" },
    "hero":         { "layout": "fullWidth", "overlay": "lightScrim",
                      "logoPlacement": "center", "taglinePlacement": "center",
                      "storeNameStyle": "balanced" },
    "productCards": { "shape": "rounded", "layout": "grid2", "shadow": "subtle",
                      "priceStyle": "understatedGrey", "tapAnimation": "scaleDown",
                      "featured": { "enabled": false, "style": "largerCard" } },
    "offerCards":   { "merchantCanCustomise": false,
                      "imageBeautification": { "filterPreset": "warm" } },
    "buttons":      { "shape": "subtleRounded", "style": "filled",
                      "size": "standard", "pressAnimation": "darken" },
    "motion":       { "transition": "fadeTint" }
  }
}
```

---

## Read patterns

**Storefront render (frontend, hot path):**
1. `GetItem(StorefrontStyle, PK=MERCHANT#<shopUuid>, SK=STYLE#PUBLISHED)` — single point read, < 5 ms.
2. Pass `item.tokens` to `applyTheme()` (already in template). Set the three `data-*` attributes on `#sf-root`. Renderer-side work needed to wire the new tokens (card shadow, price style, button shape/style/size, motion, etc.) to CSS vars / `data-*` attributes / class hooks — schema is ready for it.

**Agent during a customisation session:**
1. `GetItem(SK=STYLE#DRAFT)` — or seed from `STYLE#PUBLISHED` on first turn.
2. After each change: `PutItem(SK=STYLE#DRAFT)` and append `STYLE#VERSION#<next-seq>`.
3. Update `UNDO_STACK` (push to `undoStack`, clear `redoStack`).
4. If `len(undoStack) + len(redoStack) > 20`: delete the oldest `STYLE#VERSION#<seq>` and drop its seq from `undoStack`.

**Undo / Redo (CF-09):**
1. `GetItem(SK=UNDO_STACK)`.
2. Pop last from `undoStack` to `redoStack` (or vice versa for redo).
3. `GetItem(SK=STYLE#VERSION#<targetSeq>)`, copy `tokens` into `STYLE#DRAFT`.

**Publish (CF-10):**
1. Read `STYLE#DRAFT`.
2. Write `STYLE#PUBLISHED` (overwrite) with `publishedAt = now`, `rollbackUntil = now + 7 days`.
3. Append new `STYLE#VERSION#<seq>` from the published payload.
4. Optionally delete `STYLE#DRAFT`.

**Rollback within 7 days (CF-10):**
1. Find the prior published version via `UNDO_STACK` or by scanning `STYLE#VERSION#*` by `publishedAt`.
2. Re-publish that snapshot.

**Share preview (CF-12 — planned):**
1. Generate token, `PutItem(SK=PREVIEW#<token>)` with `ttl = now + 72h` and `tokensSnapshot` inlined.
2. Public URL hits a Lambda that does `Query(GSI2, previewToken=<token>)` → returns the snapshot read-only.

**Package picker (CF-02):**
1. On agent startup: `Scan(ThemePackage)` filtered to `active=true`. Cache in memory; table is ≤ 10 rows.

---

## Why this shape

**Single `tokens` blob, not flattened columns.** The whole style is read as a unit on every storefront render. Splitting into per-zone items would mean N round-trips on every page load and zero benefit — a full token blob is ~2 KB, nowhere near the 400 KB item limit.

**Enums, not free strings, for everything style-related.** Every field that drives a renderer branch is a closed enum so the agent cannot hallucinate values the template can't render. Hex codes are the only "open" style values, and they get a harmony + WCAG-AA contrast check before the agent is allowed to set `harmonyChecked: true` / `contrastAA: true`.

**Drafts and published are separate items, versions are a series.** Mirrors the manifest-file pattern from the S3-vs-DDB Investigation: a published item is the atomic snapshot pointer, versions are immutable history, undo is moving the pointer (non-destructive). Single-version restore is one read + one write.

**Packages in their own table.** Cleaner ops surface — independent IAM, independent throughput, no risk of a package edit accidentally hitting a hot merchant partition.

**Z5 is in the schema but minimal.** Keeping the key path open means future picture-level filters can land without a migration. Card structure stays platform-managed per CPO #2.

**No content here.** Tagline text, CTA copy, logo URL, banner URL, business tag pills, featured product UUIDs, badge text — all content, all in the product DB. This table is purely the *look* of the storefront.
