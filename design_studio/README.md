# Design Studio

A conversational AI agent that helps merchants design their storefront themes through friendly, natural dialogue. Built with [Strands Agents](https://strandsagents.com/) and deployable to [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/).

## Features

- **Conversational Design Flow**: Discovers business type → asks about vibe → presents 2-3 complete theme packages → applies on selection
- **Color Science**: Uses [coloraide](https://facelessuser.github.io/coloraide/) for harmonious palette generation (analogous, complementary, triadic, etc.)
- **WCAG Accessibility**: Validates color contrast ratios for text readability
- **Google Fonts**: Validates font selections against Google Fonts library
- **Structured Output**: Returns clickable options (vibes, themes, colors) for rich UI interactions
- **Zone tour (CF-05)**: Chat-first customization by area (Brand Colours, Hero & Header, …) — one question per step, preview highlight
- **Live Preview**: Changes apply instantly to the storefront preview; active zone outlined and scrolled into view

## Implementation plan

Living task tracker (Core Flows, Zone Customisations, DDB, progress): **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)**

## Architecture

```
design_studio/
├── conversational_agent/
│   ├── agent.py             # Core agent definition (shared)
│   ├── response_models.py   # Pydantic models for structured output
│   ├── tools.py             # Agent tools (color, font, theme, zone tour)
│   ├── server.py            # FastAPI dev server (local only)
│   ├── zone_tour.py         # CF-05 tour state (DDB ZONE_TOUR)
│   ├── zone_tour_flow.py    # Sub-steps, batched chat options, highlight selectors
│   ├── zone_tour_actions.py # Server-side tour clicks + free text
│   ├── api_response.py      # Preview payloads, zone tour enrichment (shared API)
│   ├── preview_html.py      # Theme injection + preview highlights
│   ├── chat_fast_path.py    # Server-side handlers without Bedrock
│   ├── chat_session.py      # Dev-server chat history
│   ├── message_parsers.py   # Shared chat phrase parsers
│   ├── product_card_phrases.py # Shared product-card regex patterns
│   ├── storefront_blueprint.py # Page layout, tokens→preview map, agent playbooks
│   ├── prompts/storefront_blueprint.md # Full agent reference (loaded into system prompt)
│   ├── zone_catalog.py      # Friendly area names + place hints
│   ├── zone_color_presets.py / zone_presets.py / zone_scopes.py
│   ├── runtime.py           # AgentCore entrypoint (production)
│   ├── main.py              # CLI for terminal testing
│   ├── style_tokens.py / token_mapper.py / style_repository.py
│   ├── color_engine.py      # Color utilities
│   └── config_manager.py    # Theme persistence
├── frontend/                # React UI
│   ├── src/
│   │   ├── App.jsx
│   │   ├── hooks/useZoneTourSync.js
│   │   ├── utils/zoneChatIntro.js
│   │   └── styles.css
│   └── package.json
├── storefront.html          # Storefront template
└── pyproject.toml
```

**Key separation:**
- `agent.py` — Core logic, shared between dev and prod
- `server.py` — FastAPI wrapper for local development (not deployed)
- `runtime.py` — AgentCore handler for production deployment

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for frontend)
- AWS credentials configured for Bedrock access
- Docker (for local DynamoDB)
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) (to create local tables)

## Local DynamoDB

Style data is defined in [`DDB_Schema.md`](../DDB_Schema.md) (`StorefrontStyle`, `ThemePackage`).

```bash
cd design_studio

# Start DynamoDB Local (host port 8001 — FastAPI uses 8000)
docker compose up -d dynamodb-local

# Create both tables (first time, or after container restart — in-memory DB is empty)
./scripts/dynamodb-local-create-tables.sh

# Or only ThemePackage if the style table already exists:
./scripts/dynamodb-local-create-theme-package-table.sh
```

One-off AWS CLI (from repo root, with `example.env`):

```bash
source example.env
aws dynamodb create-table \
  --table-name "$DYNAMODB_THEME_PACKAGE_TABLE" \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions AttributeName=packageId,AttributeType=S \
  --key-schema AttributeName=packageId,KeyType=HASH \
  --endpoint-url "$DYNAMODB_ENDPOINT" \
  --region "$AWS_REGION"
```

Environment variables (see `.env.example`):

| Variable | Host default | In Docker network |
|----------|--------------|-------------------|
| `DYNAMODB_ENDPOINT` | `http://127.0.0.1:8001` | `http://dynamodb-local:8000` |
| `DYNAMODB_STYLE_TABLE` | `StorefrontStyle` | same |
| `DYNAMODB_THEME_PACKAGE_TABLE` | `ThemePackage` | same |

Stop: `docker compose down`

Seed starter theme packages (CF-02):

```bash
source ../example.env
uv run python scripts/seed_theme_packages.py
```

The agent persists styles to DynamoDB when `DYNAMODB_ENDPOINT` is set (`USE_DYNAMODB=true` in `example.env`). Draft, versions, and undo use `StorefrontStyle`.

## Local Development

### 1. Install dependencies

```bash
cd design_studio
uv sync
```

### 2. Run the backend

**Bedrock** needs real AWS credentials (SSO or `aws configure`).
**DynamoDB Local** uses dummy `DYNAMODB_*` keys only — do not export `AWS_ACCESS_KEY_ID=local` for the server.

```bash
aws sso login   # or ensure ~/.aws/credentials is valid for Bedrock

source ../example.env   # DYNAMODB_ENDPOINT only (not fake AWS creds)

uv run design-server

# Or terminal CLI (for quick testing)
uv run design-studio
```

The API server runs at http://localhost:8000

### 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

**Pointing at the deployed Lambda** (instead of local backend):

Create `frontend/.env.local` (gitignored):

```bash
VITE_API_TARGET=https://<function-url-id>.lambda-url.eu-central-1.on.aws
VITE_CF_ORIGIN_SECRET=<secret-from-secrets-manager>
```

Without `.env.local`, the Vite proxy defaults to `http://localhost:8000` with no origin secret header (local dev mode).

### Screenshot capture (optional)

The preview **Screenshot** button renders the current HTML to PNG via Playwright:

```bash
uv sync --extra screenshot
uv run playwright install chromium
```

Without this extra, the endpoint returns `503` with install instructions.

### Troubleshooting: `UnrecognizedClientException` / invalid security token

This means Bedrock received **invalid AWS credentials**, usually because `example.env` used to set `AWS_ACCESS_KEY_ID=local` for DynamoDB and that overrode your real profile.

**Fix:**

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
aws sso login   # or: aws sts get-caller-identity  (should succeed)
source ../example.env
uv run design-server
```

Confirm Bedrock access in the account/region your model uses (`eu.amazon.nova-pro-v1:0` → EU, often `eu-south-1`).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/storefront/{merchant_id}` | Get storefront HTML + zone tour state/options |
| GET | `/api/zone-tour/{merchant_id}` | Zone tour progress only |
| POST | `/api/chat` | Send message to agent |
| POST | `/api/undo` | Undo last change |
| POST | `/api/redo` | Redo change |
| POST | `/api/reset` | Reset to defaults |
| POST | `/api/screenshot` | Capture preview HTML as PNG (Playwright) |
| GET | `/api/versions/{merchant_id}` | Get version history |
| POST | `/api/restore` | Restore specific version |

### Chat Request

```json
{
  "merchantId": "demo-merchant",
  "message": "I run a cozy coffee shop"
}
```

### Chat Response

```json
{
  "type": "vibe_options",
  "message": "Love it! A cozy coffee shop — I can already picture the warm atmosphere...",
  "vibe_options": [
    {"name": "Warm & cozy", "description": "inviting, handcrafted, personal"},
    {"name": "Modern & minimal", "description": "clean, sleek, sophisticated"}
  ],
  "html": "...",
  "version": 1,
  "totalVersions": 2
}
```

During an active zone tour, responses also include `zone_tour` (progress + `current_prompt`), and a small batch of `color_options` or `zone_options` for the current chat sub-step only.

## Production Deployment (AgentCore)

The `runtime.py` module provides the AgentCore entrypoint:

```python
from conversational_agent.runtime import handler

# AgentCore invokes this
response = handler({"message": "Hello", "session_id": "abc123"})
```

Deploy to AgentCore:

```bash
bedrock-agentcore deploy
```

## Agent Tools

| Tool | Description |
|------|-------------|
| `generate_color_palette` | Generate harmonious colors from a seed |
| `validate_color_and_get_info` | Validate hex color and get contrast info |
| `check_color_accessibility` | Check WCAG contrast ratio |
| `get_harmony_types` | List available color harmonies |
| `get_available_fonts` | List Google Fonts by category |
| `validate_font` | Check if font exists in Google Fonts |
| `save_theme` | Save complete theme to storefront |
| `apply_style_tokens` | Apply hero/buttons/product-card tokens immediately (direct style commands) |
| `get_current_theme` | Get current theme settings |
| `list_zones` | List customizable storefront zones |
| `customize_zone` | Apply custom styling to a zone |
| `reset_zone` | Reset zone to global theme |
| `reset_all` | Reset storefront to defaults |

## Conversation Flow

1. **Discovery**: Agent asks about the business, then about desired vibe
2. **Theme Presentation**: Agent presents 2-3 complete theme packages with colors, fonts, and styling
3. **Selection**: User picks a theme → agent saves it immediately
4. **Customization**: Agent offers to tweak individual zones with color options

## Configuration

The agent uses Amazon Nova Pro by default:

```python
AGENT_MODEL = "eu.amazon.nova-pro-v1:0"
```

Override in `agent.py` or pass to `create_agent(model="...")`.

## License

See the root [README](../README.md).
