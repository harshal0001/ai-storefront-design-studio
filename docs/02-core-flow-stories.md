# Core Flow Stories

> User stories covering the end-to-end merchant journey: onboarding, AI-driven option generation, live preview, harmony guidance, undo/redo, publishing and post-publish features. Each story is independently addressable by its Story ID (e.g. `CF-03`).

## Story index

- [`CF-01` — Welcome & Brand Identity Tags](#cf-01-welcome-brand-identity-tags) · _Must_
- [`CF-02` — Full Storefront Theme Packages](#cf-02-full-storefront-theme-packages) · _Must_
- [`CF-03` — AI Generates Initial Options](#cf-03-ai-generates-initial-options) · _Must_
- [`CF-04` — Live Preview with Real Data](#cf-04-live-preview-with-real-data) · _Must_
- [`CF-05` — Zone-by-Zone Guided Editing](#cf-05-zone-by-zone-guided-editing) · _Should_
- [`CF-06` — Non-Technical Conversational Language](#cf-06-non-technical-conversational-language) · _Must_
- [`CF-07` — AI Component Harmony Guidance](#cf-07-ai-component-harmony-guidance) · _Should_
- [`CF-08` — Fun Facts During Loading](#cf-08-fun-facts-during-loading) · _Should_
- [`CF-09` — Undo / Redo Changes](#cf-09-undo-redo-changes) · _Must_
- [`CF-10` — Save & Publish](#cf-10-save-publish) · _Must_
- [`CF-11` — Before/After Comparison](#cf-11-before-after-comparison) · _Should_
- [`CF-12` — Share Preview Link](#cf-12-share-preview-link) · _Should_
- [`CF-13` — AI Persona Simulation](#cf-13-ai-persona-simulation) · _Could_
- [`CF-14` — Contextual Design Tips](#cf-14-contextual-design-tips) · _Could_

---

## CF-01 — Welcome & Brand Identity Tags

**Priority:** Must

### User story

As a merchant, I want to describe my brand personality so the AI understands my style before suggesting anything.

### Acceptance criteria

- AI asks friendly opening questions: 'What's your vibe?'
- Merchant selects 3-5 mood tags (modern, playful, elegant, rustic, bold, etc.)
- Tags displayed as tappable pills
- AI confirms with a warm summary
- Tags stored in merchant profile for all future suggestions

### AI behaviour

AI greets merchant warmly, makes it feel like a conversation not a form. After tags: 'Love it! So you're going for a [tag1], [tag2] vibe — I've got some great ideas for you!'

---

## CF-02 — Full Storefront Theme Packages

**Priority:** Must

### User story

As a merchant, I want to select from 2-3 complete storefront theme packages so I can get a great look instantly without editing zone by zone.

### Acceptance criteria

- AI generates 2-3 complete theme packages based on brand tags
- Each package applies coordinated changes: colours, fonts, card shapes, buttons, hero
- Packages named with personality: 'Tuscan Workshop', 'Modern Minimalist', 'Bold & Bright'
- Merchant picks one as starting point
- Can then tweak individual zones after

### AI behaviour

Merchant says 'I want my store to feel like a Tuscan artisan workshop' and AI applies warm ivory bg, rounded corners, earthy palette, friendly fonts — everything at once. 'Beautiful idea! Here's what I suggest...'

---

## CF-03 — AI Generates Initial Options

**Priority:** Must

### User story

As a merchant, I want the AI to generate visual options for every change so I always pick from previews, never type values.

### Acceptance criteria

- Every customisation presents 3-5 visual option cards
- Colours: 4-5 palette options
- Shapes: 2-3 layout options
- Options labelled with friendly names ('Sunset Warmth', 'Ocean Calm')
- Tapping an option applies it to live preview instantly
- 'Surprise me' button generates a fresh set

### AI behaviour

AI: 'Here are your options — tap to try, tap again to switch. Want me to cook up more?' Never shows raw hex codes, font sizes, or pixel values.

---

## CF-04 — Live Preview with Real Data

**Priority:** Must

### User story

As a merchant, I want to see my actual products in the preview so I can judge how changes really look.

### Acceptance criteria

- Preview loads merchant's real product catalogue
- Shows actual product images, names, prices
- Preview updates in < 2 seconds after each change
- Scrollable full-storefront preview

### AI behaviour

AI: 'I'm using your real products so you can see exactly how customers will experience your store!'

---

## CF-05 — Zone-by-Zone Guided Editing

**Priority:** Should

### User story

As a merchant, I want the AI to walk me through each zone one at a time so I'm not overwhelmed.

### Acceptance criteria

- AI presents **areas** sequentially (friendly names: Brand Colours, Hero & Header, … — not Z1–Z6 in UI)
- **One chat question per sub-step** with 2–4 clickable options (like theme packages); merchant can also type in chat
- Preview **highlights and scrolls** to the section being edited
- Z5 (Offers) info-only with positive explanation
- Merchant can skip any area
- Progress indicator shows completion (compact bar + chat history)

### Implementation (prototype)

- `zone_tour_flow.py` — sub-step batches; `zone_tour_actions.py` — server-side clicks/free text
- `ZONE_TOUR` DDB item with `subStepIndex`; API injects current batch via `_enrich_with_zone_tour()`
- React: options in chat bubbles only; `inject_tour_highlight()` in preview HTML

### AI behaviour

AI: 'Let's start with your **brand colours** — first, which accent for your Follow button?' *(2 swatches in chat)* After choice: 'Lovely — now the backdrop behind your product sections?' Preview highlights the relevant block.

---

## CF-06 — Non-Technical Conversational Language

**Priority:** Must

### User story

As a merchant, I want the AI to use everyday language so I never feel confused by technical design terms.

### Acceptance criteria

- AI never says 'hex code', 'RGB', 'rpx', 'border-radius', 'opacity'
- Uses 'more red / less red', 'rounder / sharper', 'bigger / smaller'
- If merchant gives a technical term (e.g. '#FF6B35'), AI accepts it but responds in plain language
- Conversation feels like talking to a knowledgeable friend, not a design tool

### AI behaviour

Merchant: 'My brand colour is FF6B35.' AI: 'Great, that's a warm orange! Here are 4 options around that shade — which feels most like you?' Merchant: 'More pinkish.' AI: 'Going pinker! How about these three?'

---

## CF-07 — AI Component Harmony Guidance

**Priority:** Should

### User story

As a merchant, I want the AI to guide me toward selections that look good together so my storefront is cohesive.

### Acceptance criteria

- AI checks cross-zone harmony after each selection
- Warns if choices clash (e.g. sharp cards with pill buttons)
- Suggests matching alternatives: 'Your rounded cards would look great with rounded buttons too'
- Never blocks, just guides
- Ensures theme package consistency when doing zone-by-zone edits

### AI behaviour

Joanna: 'Components need to look well together.' AI guides matching: 'Since you picked rounded cards, these rounded buttons would complement them nicely. Want to see?'

---

## CF-08 — Fun Facts During Loading

**Priority:** Should

### User story

As a merchant, I want to see entertaining facts while the AI generates options so waiting feels short.

### Acceptance criteria

- Rotating fun facts appear during any AI generation
- Mix of: design trivia, colour psychology, platform promo tips ('Best butcher promotions work on Tuesdays!'), brand fun facts
- Smooth fade transitions
- Minimum 20 unique facts in rotation
- Disappears once options are ready (like Claude Design)

### AI behaviour

Fun facts keep it light: 'Did you know blue increases trust by 34%?' or 'Tip: merchants on the platform who run weekend promos see 22% more engagement!'

---

## CF-09 — Undo / Redo Changes

**Priority:** Must

### User story

As a merchant, I want to undo any change so I can experiment without fear.

### Acceptance criteria

- Undo button reverts last change with animation
- Redo button re-applies
- Full history stack (up to 20 changes)
- AI acknowledges naturally

### AI behaviour

AI: 'Changed your mind? No problem — back to where we were!' On redo: 'Welcome back to that look!'

---

## CF-10 — Save & Publish

**Priority:** Must

### User story

As a merchant, I want to save my customisation and publish it to my live storefront.

### Acceptance criteria

- Save draft at any time
- Publish requires confirmation
- AI generates summary of all changes
- Rollback available for 7 days post-publish

### AI behaviour

AI: 'Ready to go live? Here's everything we changed — take a look! Hit publish when you're happy, or save as draft to sleep on it!'

---

## CF-11 — Before/After Comparison

**Priority:** Should

### User story

As a merchant, I want to see my storefront before and after changes side-by-side so I can confirm improvements.

### Acceptance criteria

- Split-screen or slider comparison view
- Swipe/drag divider between before and after
- Labels: 'Before' / 'Your New Look'
- Available at any time during editing, not just publish
- Inspired by Framer / Shopify comparison patterns

### AI behaviour

AI: 'Want to see how far we've come? Swipe to compare your old look with the new one!'

---

## CF-12 — Share Preview Link

**Priority:** Should

### User story

As a merchant, I want to share a preview link with colleagues so they can see changes before publishing.

### Acceptance criteria

- Generate shareable preview URL
- Link expires after 72 hours
- View-only (no editing)
- Shows current draft state
- Inspired by Shopify Rollouts sharing

### AI behaviour

AI: 'Want a second opinion? I'll generate a preview link you can share with your team!'

---

## CF-13 — AI Persona Simulation

**Priority:** Could

### User story

As a merchant, I want the AI to show how different customer types would experience my storefront.

### Acceptance criteria

- AI simulates 3 personas: first-time visitor, returning customer, deal hunter
- Each persona narrates their experience
- Highlights what catches attention per persona
- Suggests improvements based on persona reactions
- Inspired by Shopify SimGym concept

### AI behaviour

AI: 'Let me show you how different customers would see your store! Meet Sofia — she's browsing for the first time...'

---

## CF-14 — Contextual Design Tips

**Priority:** Could

### User story

As a merchant, I want the AI to proactively suggest design improvements based on best practices.

### Acceptance criteria

- AI offers tips contextually during editing (not interrupting)
- Tips appear as subtle cards: 'Pro tip: ...'
- Based on accessibility, conversion, readability research
- Dismissable and never repeated
- Inspired by Duda Copilot contextual suggestions

### AI behaviour

AI: 'Quick tip — studies show buttons with rounded corners get 22% more taps. Want me to round yours a bit?' Only when relevant, never pushy.

---
