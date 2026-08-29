# Storefront — Overview

> Project context for the AI Storefront Customisation prototype. Use this as the canonical summary of objective, teams, platform, and the CPO-approved key decisions that constrain all stories.

**AI Storefront Customization (Prototype Spec)**
_Prototyping engagement · May–June 2026_

## Project metadata

- **Objective:** Enable merchants to customise their AI-generated storefront via natural-language chat, with live preview, version history, and publish approval.
- **Teams:** cloud provider prototyping team · integration partner · platform product team
- **Duration:** 2–3 weeks
- **Platform:** React split-pane (chat + live iframe), Lambda → Bedrock Claude Sonnet, DynamoDB version store
- **Storefront:** <(see storefront.html in this repo)>

## Key decisions from CPO review

These decisions are binding constraints on every story and guardrail in this spec.

1. Structure & order of storefront sections is FIXED — merchants cannot reorder zones
2. Offer cards (Z5): minimal customisation — structure stays standard (Smart label, discount badge, expiry, store name). Only picture-level beautification allowed
3. Paid fonts: find closest free Google Font — no paid font licensing in scope
4. Section spacing: CPO prefers not to change spacing freely — keep within tight guardrails
5. Every change should offer 3–5 colour options or 2–3 shape/layout options
6. Add full storefront "packages" (2–3 pre-designed themes) as starting points
7. AI guides component compatibility, prevents mismatched zone styles
8. Conversation must feel pleasant, fun, and non-technical, like talking to a human designer
9. Fun facts & promotional tips shown during AI processing (e.g. "Did you know Friday promos work best for aperitivo bars?")
10. Tags: AI-generated first (3–5 from store profile), freeform via portal later, reviewed before go-live
