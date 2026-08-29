# Storefront Design Studio

A conversational AI agent that lets merchants restyle their online storefront by chatting with an
AI "designer" — no design skills or technical knowledge required. The merchant describes their
business and the vibe they want, the agent proposes complete theme packages, and every change is
applied instantly to a live preview with full version history, undo/redo and guardrails.

Built with [Strands Agents](https://strandsagents.com/) on Amazon Bedrock, a FastAPI backend, a
React/Vite frontend, DynamoDB for persistence, and deployable to
[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) via AWS CDK.

> This repository is a prototype built during a short prototyping engagement. Account IDs,
> hostnames and organisation names have been replaced with placeholders.

## What it does

- **Guided design conversation** — discovers the business type → asks about the desired vibe →
  presents 2–3 complete theme packages (colours, fonts, shapes) → applies the chosen one.
- **Zone tour** — chat-first customisation area by area (brand colours, hero & header, buttons,
  product cards, footer…), one question per step, with the active zone highlighted in the preview.
- **Colour science** — harmonious palettes (analogous, complementary, triadic…) generated with
  [coloraide](https://facelessuser.github.io/coloraide/) and validated for WCAG contrast.
- **Google Fonts** — font suggestions validated against the Google Fonts catalogue
  (`design_studio/fonts.json`).
- **Live preview** — theme tokens are injected into the storefront HTML and rendered in an iframe;
  changes are visible immediately.
- **Version history** — every change is versioned with undo, redo, restore and reset.
- **Guardrails** — fixed section order, limited spacing changes, curated option sets
  (3–5 colour or 2–3 shape options per step). See `docs/04-guardrails.md`.
- **Structured responses** — the agent returns clickable option chips (vibes, themes, colours)
  rather than free text only.

## Repository layout

```
.
├── design_studio/            # The application
│   ├── conversational_agent/ # Python agent, tools, FastAPI dev server, AgentCore runtime
│   ├── frontend/             # React + Vite split-pane UI (chat + live preview)
│   ├── lambda_backend/       # Lambda handler for the deployed API
│   ├── cdk/                  # AWS CDK stacks (data, API, agent runtime, frontend, observability)
│   ├── scripts/              # DynamoDB Local table creation + seed scripts
│   ├── tests/                # pytest suite
│   ├── storefront.html       # Storefront template used for previews
│   ├── ARCHITECTURE.md       # Detailed architecture document
│   ├── IMPLEMENTATION_PLAN.md# Feature/story tracker
│   └── README.md             # Detailed developer guide (API, tools, troubleshooting)
├── docs/                     # Product spec: overview, core-flow stories, zone customisations, guardrails
├── infra/                    # OpenTofu (Terraform) sandbox infrastructure + bootstrap scripts
├── DDB_Schema.md             # DynamoDB table design (StorefrontStyle, ThemePackage)
├── packageStorefront/        # Static reference pages/assets for the storefront
├── sample_frontend_from_demo/# Early demo frontend (reference only)
├── netlify-storefront.html   # Original static storefront the template was derived from
└── storefront.html           # Root copy of the storefront template
```

## Architecture at a glance

```
React UI (chat + iframe preview)
        │ HTTP /api/*
        ▼
FastAPI dev server  ──or──  Lambda (Function URL) → AgentCore Runtime
        │
        ▼
Strands Agent (Amazon Bedrock model, e.g. Nova Pro / Claude)
   tools: palette generation, WCAG checks, font validation,
          save_theme, customize_zone, reset_*, zone tour …
        │
        ▼
DynamoDB (StorefrontStyle: drafts, versions, tour state · ThemePackage: starter themes)
```

See [`design_studio/ARCHITECTURE.md`](design_studio/ARCHITECTURE.md) for the full picture.

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 18+
- Docker (for DynamoDB Local)
- AWS CLI v2 and AWS credentials with access to Amazon Bedrock (`aws sso login` or `aws configure`)

## Running locally

All commands below are run from `design_studio/`.

### 1. Start DynamoDB Local and create tables

```bash
cd design_studio
docker compose up -d dynamodb-local          # listens on host port 8001
./scripts/dynamodb-local-create-tables.sh    # creates StorefrontStyle + ThemePackage
```

The in-memory database is empty after every container restart — re-run the create script.

### 2. Configure the environment

`example.env` contains safe defaults for local development (DynamoDB Local endpoint, table
names, region). Source it in every shell that runs the backend:

```bash
source example.env
```

Bedrock needs **real** AWS credentials from your profile/SSO. Do **not** set
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` to `local` — the DynamoDB Local dummy keys are
provided via the separate `DYNAMODB_*` variables. Optionally override the model with
`AGENT_MODEL` (default `eu.amazon.nova-pro-v1:0`).

### 3. Install and run the backend

```bash
uv sync
uv run python scripts/seed_theme_packages.py   # seed starter theme packages (once)
uv run design-server                            # API at http://localhost:8000
```

For a quick terminal-only session without the UI: `uv run design-studio`.

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev                                     # http://localhost:5173
```

The Vite dev server proxies `/api` to `http://localhost:8000`. To point the UI at a deployed
backend instead, create `frontend/.env.local`:

```bash
VITE_API_TARGET=https://<function-url-id>.lambda-url.<region>.on.aws
VITE_CF_ORIGIN_SECRET=<secret>
```

### 5. Try it

Open http://localhost:5173, then type something like *"I run a cozy coffee shop"* and follow
the conversation. Use the toolbar for undo/redo/reset and version history.

### Optional: screenshots

The preview **Screenshot** button renders the current HTML to PNG with Playwright:

```bash
uv sync --extra screenshot
uv run playwright install chromium
```

## Running the tests

```bash
cd design_studio
uv sync --extra dev
uv run pytest
```

## Deploying to AWS

The `design_studio/cdk/` project defines CDK stacks for the DynamoDB tables, the Lambda API,
the AgentCore agent runtime (built from `design_studio/Dockerfile`), the static frontend and
observability. See [`design_studio/cdk/README.md`](design_studio/cdk/README.md) and
[`design_studio/cdk/NEXT_STEPS.md`](design_studio/cdk/NEXT_STEPS.md).

`infra/` contains the OpenTofu configuration and bootstrap scripts used for the sandbox
account (OIDC-based CI authentication, remote state, tagging conventions). Account IDs there
are placeholders — fill in `infra/tofu/env_config/environments.properties` for your own
accounts. See [`infra/README.md`](infra/README.md).

## Key documents

| Document | Purpose |
|---|---|
| `docs/01-overview.md` | Objective, platform, binding product decisions |
| `docs/02-core-flow-stories.md` | Core conversation flows (CF-01 … CF-14) |
| `docs/03-zone-customisations.md` | Per-zone customisation stories (Z1 … Z9) |
| `docs/04-guardrails.md` | Guardrails and constraints |
| `DDB_Schema.md` | DynamoDB data model |
| `design_studio/README.md` | API reference, agent tools, troubleshooting |

## License

No license has been granted for this code. It is published for reference and portfolio purposes.
