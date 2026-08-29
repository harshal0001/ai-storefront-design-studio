# Zone Customisations

> Per-zone customisation stories. Zones (Z1–Z6) are presented in fixed structural order; merchants customise within each zone but cannot reorder them. Z5 (Offer Cards) is platform-controlled — see `Z5-01`/`Z5-02`. Each story includes the options the AI should offer first.

**Design Studio prototype (CF-05):** Merchants see **friendly area names** (Brand Colours, Hero & Header, …) in chat — not Z-codes. The server walks through **sub-steps** (one question, 2–4 buttons, optional free text) and highlights the matching preview section. See `design_studio/IMPLEMENTATION_PLAN.md` → *Zone tour — implementation reference*.

## Zone & story index

- **Z1 — BRAND COLOURS**
  - [`Z1-01` — Primary Colour by Mood](#z1-01-primary-colour-by-mood) · _Critical_
  - [`Z1-02` — Accent Colour Selection](#z1-02-accent-colour-selection) · _Critical_
  - [`Z1-03` — Upload Own Colour Palette](#z1-03-upload-own-colour-palette) · _Critical_
  - [`Z1-04` — Photo-to-Palette Extraction](#z1-04-photo-to-palette-extraction) · _Critical_
  - [`Z1-05` — Background Colour](#z1-05-background-colour) · _Critical_
  - [`Z1-06` — Colour Harmony Validation](#z1-06-colour-harmony-validation) · _Medium_
  - [`Z1-07` — Subtle Colour Transitions](#z1-07-subtle-colour-transitions) · _Low_
- **Z2 — HERO & HEADER**
  - [`Z2-02` — Hero Layout Style](#z2-02-hero-layout-style) · _Critical_
  - [`Z2-03` — Hero Text / Tagline Overlay](#z2-03-hero-text-tagline-overlay) · _Critical_
  - [`Z2-04` — Store Logo Placement](#z2-04-store-logo-placement) · _Critical_
  - [`Z2-05` — Store Name Styling](#z2-05-store-name-styling) · _Critical_
- **Z3 — TYPOGRAPHY**
  - [`Z3-01` — Font Pairing Selection](#z3-01-font-pairing-selection) · _Critical_
  - [`Z3-02` — Font Size Scaling](#z3-02-font-size-scaling) · _High_
  - [`Z3-03` — Text Colour Customisation](#z3-03-text-colour-customisation) · _Critical_
- **Z4 — PRODUCT CARDS**
  - [`Z4-01` — Card Shape & Layout](#z4-01-card-shape-layout) · _Critical_
  - [`Z4-02` — Card Shadow & Elevation](#z4-02-card-shadow-elevation) · _Medium_
  - [`Z4-03` — Price Display Style](#z4-03-price-display-style) · _Medium_
  - [`Z4-04` — Featured Products Styling](#z4-04-featured-products-styling) · _High_
  - [`Z4-07` — Product Card Tap Animation](#z4-07-product-card-tap-animation) · _Low_
- **Z5 — OFFER CARDS**
  - [`Z5-01` — Offer Cards View-Only](#z5-01-offer-cards-view-only) · _Critical_
  - [`Z5-02` — Offer Card Positive Explanation](#z5-02-offer-card-positive-explanation) · _Critical_
- **Z6 — BUTTONS & CTAs**
  - [`Z6-01` — Button Shape](#z6-01-button-shape) · _Critical_
  - [`Z6-02` — Button Colour & Style](#z6-02-button-colour-style) · _Critical_
  - [`Z6-03` — CTA Text Options](#z6-03-cta-text-options) · _Medium_
  - [`Z6-04` — Button Size](#z6-04-button-size) · _High_
  - [`Z6-05` — Button Press Animation](#z6-05-button-press-animation) · _Low_

---

## Z1 — BRAND COLOURS

### Z1-01 — Primary Colour by Mood

**Priority:** Critical

#### User story

As a merchant, I want to describe a mood (warm, premium, fresh) and have the AI suggest primary colour palettes.

#### Acceptance criteria

- AI shows 4-5 palette options based on mood/tags
- Each palette previewed on live storefront
- Merchant can pick one OR say 'I want green' and AI adjusts
- Selected primary persists across all zones
- Palette includes primary + accent + neutral

#### Options AI suggests first

4-5 palette cards named with personality ('Sunset Warmth', 'Ocean Trust'). Mini-preview of storefront in each palette.

### Z1-02 — Accent Colour Selection

**Priority:** Critical

#### User story

As a merchant, I want to pick an accent colour that complements my primary.

#### Acceptance criteria

- AI shows 4 accent options pre-matched to primary
- Accent previewed on buttons, links, prices
- Merchant can request a specific accent
- AI explains why each pairing works

#### Options AI suggests first

4 accent options matched to primary. Shows accent on buttons, links, highlights.

### Z1-03 — Upload Own Colour Palette

**Priority:** Critical

#### User story

As a merchant, I want to provide my own brand palette so the AI uses my exact brand colours.

#### Acceptance criteria

- Merchant can provide colour names, hex codes, or descriptions ('my brand red')
- AI maps provided colours to storefront roles (primary, accent, bg)
- Shows 2-3 arrangement options
- Validates contrast and warns if needed

#### Options AI suggests first

Merchant provides colours in any format. AI maps to roles and shows 2-3 arrangements.

### Z1-04 — Photo-to-Palette Extraction

**Priority:** Critical

#### User story

As a merchant, I want to upload a photo or logo and have the AI extract a colour palette from it.

#### Acceptance criteria

- Upload button for photo/logo
- AI extracts 4-6 dominant colours
- Presents 3 palette arrangements from extracted colours
- Each arrangement previewed on storefront

#### Options AI suggests first

Upload photo/logo. AI extracts colours. Shows 3 arrangements on storefront preview.

### Z1-05 — Background Colour

**Priority:** Critical

#### User story

As a merchant, I want to change the page background colour of my storefront.

#### Acceptance criteria

- AI shows 4 background options (white, warm white, grey, cream)
- Each previewed on full storefront
- Merchant can describe preference ('warmer', 'cooler')
- AI warns if chosen bg reduces readability

#### Options AI suggests first

4 options: Pure White, Warm White, Light Grey, Soft Cream. Full storefront preview.

### Z1-06 — Colour Harmony Validation

**Priority:** Medium

#### User story

As a merchant, I want the AI to warn me if my colour choices clash.

#### Acceptance criteria

- AI auto-checks after each colour pick
- If clash detected, explains in plain language
- Suggests 3 fix alternatives
- Blocks combos with contrast < 3:1
- Uses colour wheel logic (complementary, analogous)

#### Options AI suggests first

Auto-check after every pick. Plain language warnings. 3 alternatives suggested.

### Z1-07 — Subtle Colour Transitions

**Priority:** Low

#### User story

As a merchant, I want subtle colour transitions when customers navigate my storefront.

#### Acceptance criteria

- AI shows 3 animation options
- Each previewed live on storefront
- 'None' always available
- AI recommends based on brand tags

#### Options AI suggests first

3 options: Fade (0.3s), Slide-tint (0.4s), None. Live preview each.

## Z2 — HERO & HEADER

### Z2-02 — Hero Layout Style

**Priority:** Critical

#### User story

As a merchant, I want to choose between different hero layout styles.

#### Acceptance criteria

- AI shows 2-3 hero layouts
- Each previewed with merchant's real content
- Merchant can pick or describe preference
- Layout respects mobile-first design

#### Options AI suggests first

2-3 layouts: full-width, split image+text, carousel. Previewed with real content.

### Z2-03 — Hero Text / Tagline Overlay

**Priority:** Critical

#### User story

As a merchant, I want to add a tagline or welcome message on my hero.

#### Acceptance criteria

- 3 text placement options shown
- AI suggests tagline based on merchant category
- Merchant can type their own tagline
- Max 40 characters
- Auto-scrim applied if text hard to read on image

#### Options AI suggests first

3 placements: Centre, Bottom-left, Bottom-right. AI suggests tagline. 40 char limit.

### Z2-04 — Store Logo Placement

**Priority:** Critical

#### User story

As a merchant, I want my logo displayed in the header area.

#### Acceptance criteria

- 3 logo placement options shown
- Auto-resize to fit header
- AI warns if logo resolution too low
- Merchant can upload new logo

#### Options AI suggests first

3 placements: Left, Centre, Inside hero. Auto-resize.

### Z2-05 — Store Name Styling

**Priority:** Critical

#### User story

As a merchant, I want to adjust how my store name looks in the header.

#### Acceptance criteria

- 3-4 styling options (weight, size, colour)
- AI recommends based on logo presence
- If logo uploaded, name can be more subtle
- Merchant can say 'make it bigger' or 'more bold'

#### Options AI suggests first

3-4 combos of weight/size/colour from Z1 palette. AI adjusts based on logo.

## Z3 — TYPOGRAPHY

### Z3-01 — Font Pairing Selection

**Priority:** Critical

#### User story

As a merchant, I want to choose a heading + body font combo from AI-suggested pairings.

#### Acceptance criteria

- AI shows 4 font pair cards with heading + body samples
- Pairs named with personality
- Merchant can pick or say 'I want something more modern'
- If merchant requests paid font (e.g. Gotham), AI finds closest free match

#### Options AI suggests first

4 font pair cards named ('Classic Duo', 'Modern Pair'). Heading + body shown in use.

### Z3-02 — Font Size Scaling

**Priority:** High

#### User story

As a merchant, I want to adjust text sizes so important info stands out.

#### Acceptance criteria

- AI shows 3 scale options
- Each previewed on real storefront content
- Merchant can say 'bigger headings' or 'make it compact'
- Sizes stay within allowed range (like Confluence)
- AI recommends based on audience tags

#### Options AI suggests first

3 scales: Compact (14/12rpx), Standard (16/14rpx), Generous (18/16rpx).

### Z3-03 — Text Colour Customisation

**Priority:** Critical

#### User story

As a merchant, I want to choose text colours that work with my background.

#### Acceptance criteria

- AI shows 4 options per text type (heading/body)
- Each shows contrast ratio against background
- Merchant can say 'darker' or 'warmer'
- AI blocks any combo that fails WCAG AA

#### Options AI suggests first

4 options per type: black, dark grey, brand-tinted, warm dark. Contrast shown.

## Z4 — PRODUCT CARDS

### Z4-01 — Card Shape & Layout

**Priority:** Critical

#### User story

As a merchant, I want to choose how my product cards look — shape and layout.

#### Acceptance criteria

- AI shows shape options (rounded, sharp, circular image)
- AI shows layout options (2-col grid, 3-col, list, featured+grid)
- Previewed with real products
- Merchant can say 'I want rounded cards in a grid'
- AI warns if product images too small for grid

#### Options AI suggests first

Shapes: rounded, sharp, circular. Layouts: 2-col, 3-col, list, featured+grid.

### Z4-02 — Card Shadow & Elevation

**Priority:** Medium

#### User story

As a merchant, I want to control depth/shadow on my product cards.

#### Acceptance criteria

- AI shows 4 shadow/depth options
- Each previewed with tap state
- Merchant can say 'more shadow' or 'flat please'
- AI recommends based on brand tags

#### Options AI suggests first

4 options: Flat, Subtle, Elevated, Floating. Preview tap state.

### Z4-03 — Price Display Style

**Priority:** Medium

#### User story

As a merchant, I want to choose how prices appear on my product cards.

#### Acceptance criteria

- AI shows 4 price display styles
- Each shown with sample prices from catalogue
- Merchant can say 'make prices stand out more'
- AI recommends based on brand (premium→understated, value→bold)

#### Options AI suggests first

4 options: Bold red, Accent colour, Understated grey, Badge pill.

### Z4-04 — Featured Products Styling

**Priority:** High

#### User story

As a merchant, I want to highlight featured products so my best sellers stand out.

#### Acceptance criteria

- Featured section has distinct card style options
- Options: larger card, different colour, badge ('Best Seller')
- Merchant describes desired featured look
- AI applies only to featured section
- Regular cards remain visually distinct

#### Options AI suggests first

Larger card, different colour, or badge. Applied to featured only.

### Z4-07 — Product Card Tap Animation

**Priority:** Low

#### User story

As a merchant, I want a subtle animation when customers tap a product card.

#### Acceptance criteria

- AI shows 3 animation options + 'None'
- Each previewed with tap simulation
- Merchant can say 'no animation' or 'something subtle'

#### Options AI suggests first

3 options: Scale-down, Ripple, None. Tap simulation preview.

## Z5 — OFFER CARDS

### Z5-01 — Offer Cards View-Only

**Priority:** Critical

#### User story

As a merchant, I can see how offer cards look in my storefront preview but I cannot change them.

#### Acceptance criteria

- Offer cards visible in storefront preview
- No edit controls shown for this zone
- AI explains positively why offers are platform-managed
- Offers rendered from platform API

#### Options AI suggests first

N/A — No options. Platform styling shown in preview.

### Z5-02 — Offer Card Positive Explanation

**Priority:** Critical

#### User story

As a merchant, I want the AI to explain why offer cards look the way they do, in a positive way.

#### Acceptance criteria

- AI proactively explains during zone tour
- Tone: 'We A/B test these to maximise your sales'
- Never uses 'restricted' or 'not allowed'
- Links to support if merchant has questions

#### Options AI suggests first

AI explains during tour. Positive tone. Support link available.

## Z6 — BUTTONS & CTAs

### Z6-01 — Button Shape

**Priority:** Critical

#### User story

As a merchant, I want to choose the shape of my buttons — rounded, pill, or sharp.

#### Acceptance criteria

- AI shows 4 shape options
- Each previewed on multiple button types (cart, details, follow)
- Merchant can say 'I want square buttons' and AI does it
- AI suggests shapes that match Z4 card shape
- Harmony warning if shapes clash across zones

#### Options AI suggests first

4 options: Sharp, Subtle rounded, Rounded, Full pill. Previewed on all button types.

### Z6-02 — Button Colour & Style

**Priority:** Critical

#### User story

As a merchant, I want to customise my button colours to match my brand.

#### Acceptance criteria

- AI shows 4 button styles derived from Z1 palette
- Each previewed in context (product card, hero)
- Merchant can say 'make them bolder' or 'more subtle'
- Primary CTA must remain prominent (filled or outlined)

#### Options AI suggests first

4 styles: Filled, Outlined, Soft, Ghost. Colours from Z1 palette.

### Z6-03 — CTA Text Options

**Priority:** Medium

#### User story

As a merchant, I want to choose the text on my CTA buttons.

#### Acceptance criteria

- AI suggests 4 Italian text options per CTA type
- Options range from formal to playful
- Merchant can suggest their own text
- Max 20 characters
- AI recommends based on brand tone

#### Options AI suggests first

4 text options per CTA. Cart: 'Aggiungi al Carrello', 'Lo Voglio!', etc. Max 20 chars.

### Z6-04 — Button Size

**Priority:** High

#### User story

As a merchant, I want to control how large my buttons are.

#### Acceptance criteria

- AI shows 3 size options in context
- Each previewed on product card
- Merchant can say 'bigger' or 'smaller'
- Minimum size enforced for touch-friendliness

#### Options AI suggests first

3 options: Compact (64rpx), Standard (80rpx), Large (96rpx). In-context preview.

### Z6-05 — Button Press Animation

**Priority:** Low

#### User story

As a merchant, I want to choose what happens when customers press my buttons.

#### Acceptance criteria

- AI shows 3 press animations + 'None'
- Each previewed with tap simulation
- Merchant can say 'no animation' or pick one
- AI recommends based on brand personality

#### Options AI suggests first

3 options: Darken, Scale, Ripple. Tap simulation preview.
