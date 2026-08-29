# Architecture Document

## Overview

The Storefront Design Agent is a conversational AI system that helps merchants design their storefront themes through natural dialogue. It combines LLM creativity with color science to generate accessible, harmonious designs.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐         ┌─────────────────┐         ┌─────────────┐  │
│   │   React UI      │         │   Terminal CLI  │         │  External   │  │
│   │   (frontend/)   │         │   (main.py)     │         │  Clients    │  │
│   └────────┬────────┘         └────────┬────────┘         └──────┬──────┘  │
│            │                           │                         │         │
└────────────┼───────────────────────────┼─────────────────────────┼─────────┘
             │ HTTP                       │ Direct                  │ HTTP
             ▼                           ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               API LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────┐     ┌─────────────────────────────────┐  │
│   │      FastAPI Server         │     │      AgentCore Runtime          │  │
│   │      (server.py)            │     │      (runtime.py)               │  │
│   │                             │     │                                 │  │
│   │  • Session management       │     │  • Lambda-style handler         │  │
│   │  • Version history          │     │  • Stateless invocation         │  │
│   │  • HTML generation          │     │  • Production scaling           │  │
│   │  • DEV ONLY                 │     │  • PRODUCTION                   │  │
│   └──────────────┬──────────────┘     └───────────────┬─────────────────┘  │
│                  │                                     │                    │
└──────────────────┼─────────────────────────────────────┼────────────────────┘
                   │                                     │
                   └──────────────────┬──────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AGENT LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         Strands Agent                                │  │
│   │                         (agent.py)                                   │  │
│   │                                                                      │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │  │
│   │  │    Model     │  │   System     │  │          Tools             │ │  │
│   │  │  (config.py) │  │   Prompt     │  │        (tools.py)          │ │  │
│   │  │              │  │  (prompts/)  │  │                            │ │  │
│   │  │ Nova Pro     │  │              │  │ • generate_color_palette   │ │  │
│   │  │ Claude       │  │ Personality  │  │ • validate_color_and_info  │ │  │
│   │  │ etc.         │  │ Flow         │  │ • check_color_accessibility│ │  │
│   │  │              │  │ Rules        │  │ • validate_font            │ │  │
│   │  └──────────────┘  └──────────────┘  │ • save_theme               │ │  │
│   │                                       │ • customize_zone           │ │  │
│   │                                       │ • etc.                     │ │  │
│   │                                       └────────────────────────────┘ │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     Structured Output                                │  │
│   │                   (response_models.py)                               │  │
│   │                                                                      │  │
│   │  AgentResponse { message, response_type, vibe_options,              │  │
│   │                  theme_packages, color_options }                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             DOMAIN LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐  │
│   │   Color Engine    │  │   Config Manager  │  │    Domain Models      │  │
│   │ (color_engine.py) │  │(config_manager.py)│  │     (models.py)       │  │
│   │                   │  │                   │  │                       │  │
│   │ • Palette gen     │  │ • Load/save JSON  │  │ • StorefrontConfig    │  │
│   │ • WCAG contrast   │  │ • Theme state     │  │ • Zone enum           │  │
│   │ • Color harmonies │  │                   │  │ • BorderRadius        │  │
│   │ • Font validation │  │                   │  │ • Spacing             │  │
│   └───────────────────┘  └───────────────────┘  └───────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            EXTERNAL SERVICES                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐  │
│   │  Amazon Bedrock   │  │   Google Fonts    │  │   Local Storage       │  │
│   │                   │  │   (validation)    │  │   (JSON config)       │  │
│   │ • Nova Pro        │  │                   │  │                       │  │
│   │ • Claude          │  │ • Font list       │  │ • storefront_config   │  │
│   │ • Converse API    │  │ • Availability    │  │   .json               │  │
│   └───────────────────┘  └───────────────────┘  └───────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Presentation Layer

#### React Frontend (`frontend/`)
- Single-page application for visual interaction
- Split view: chat panel + live storefront preview
- Renders structured options as clickable pills/cards
- Communicates with backend via REST API

#### Terminal CLI (`main.py`)
- Simple REPL for testing without UI
- Direct agent invocation
- Useful for prompt development

### 2. API Layer

#### FastAPI Server (`server.py`) — Development Only
```
NOT deployed to production. Local development only.
```

Responsibilities:
- **Session Management**: Maintains agent instances per merchant
- **Conversation History**: Tracks message history for context
- **Version Control**: Stores HTML snapshots for undo/redo
- **HTML Generation**: Injects theme into storefront template

Endpoints:
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/storefront/{id}` | GET | Get current storefront HTML |
| `/api/chat` | POST | Send message, get structured response |
| `/api/undo` | POST | Revert to previous version |
| `/api/redo` | POST | Restore reverted version |
| `/api/reset` | POST | Reset to default theme |
| `/api/versions/{id}` | GET | List version history |
| `/api/restore` | POST | Restore specific version |

#### AgentCore Runtime (`runtime.py`) — Production
```
Deployed to Amazon Bedrock AgentCore for production.
```

Responsibilities:
- **Stateless Handler**: Lambda-style invocation
- **Structured Output**: Returns typed responses
- **Scaling**: AgentCore handles infrastructure

Interface:
```python
def handler(event: dict, context=None) -> dict:
    """
    event: {"message": str, "session_id": str}
    returns: {"message": str, "type": str, "vibe_options": [...], ...}
    """
```

### 3. Agent Layer

#### Core Agent (`agent.py`)
The central component that orchestrates the conversation.

```python
def create_agent(model=None, system_prompt=None) -> Agent:
    return Agent(
        model=model or AGENT_MODEL,
        system_prompt=system_prompt or load_system_prompt(),
        tools=AGENT_TOOLS,
    )
```

**Agent Loop** (managed by Strands):
1. Receive user message
2. Model processes with system prompt context
3. Model may call tools (color generation, validation, etc.)
4. Tool results feed back to model
5. Model generates structured response
6. Response returned to caller

#### Configuration (`config.py`)
Externalized settings:
```python
AGENT_MODEL = os.environ.get("AGENT_MODEL", "eu.amazon.nova-pro-v1:0")
GREETING_PROMPT = "A new merchant just opened..."
```

#### System Prompt (`prompts/system_prompt.md`)
Defines agent personality and behavior:
- **Personality**: Warm, encouraging, design-focused
- **Conversation Flow**: Discovery → Vibe → Themes → Customization
- **Tool Usage**: When/how to use each tool
- **Structured Output**: Response format specification

#### Structured Output (`response_models.py`)
Pydantic models for typed responses:

```python
class AgentResponse(BaseModel):
    message: str                           # Conversational text
    response_type: str                     # greeting|vibe_options|theme_packages|...
    vibe_options: List[VibeOption] | None  # Mood choices
    theme_packages: List[ThemePackage] | None  # Complete themes
    color_options: List[ColorOption] | None    # Zone colors (batched per sub-step during tour)
```

#### Zone tour (CF-05)

Chat-first area customization after theme save. State in DynamoDB `SK=ZONE_TOUR` (`subStepIndex` + `currentIndex`).

```
zone_tour_flow.py     → sub-step definitions + highlight CSS selectors
zone_tour_actions.py  → handle "zone option <id>" + free text without Bedrock
server.py             → _enrich_with_zone_tour() injects current batch only
                      → inject_tour_highlight() scrolls/outlines preview section
App.jsx               → options in chat; compact progress bar with friendly names
```

Scoped colours: `tokens.zoneScopes` (Z2, Z3, Z4S, Z4C, Z4 accent, Z6) applied in `storefront.html` `applyTheme()`.

### 4. Domain Layer

#### Color Engine (`color_engine.py`)
Color science utilities powered by [coloraide](https://facelessuser.github.io/coloraide/).

**About coloraide**: A Python library for color manipulation that supports 100+ color spaces (sRGB, OKLCH, Lab, etc.), color interpolation, gamut mapping, and delta-E color difference calculations. It enables perceptually uniform color transformations — critical for generating harmonious palettes that look balanced to the human eye rather than just mathematically spaced. The library handles color space conversions internally, so harmonies computed in OKLCH (perceptually uniform) are output as hex codes for CSS.

| Function | Purpose |
|----------|---------|
| `generate_palette_from_seed()` | Create harmonious palettes |
| `check_contrast_ratio()` | WCAG contrast calculation |
| `is_accessible()` | AA/AAA compliance check |
| `adjust_for_contrast()` | Auto-fix low contrast |
| `get_contrast_color()` | Best text color for background |

**Supported Harmonies**:
- `analogous` — Adjacent colors, serene
- `complement` — Opposite colors, vibrant
- `triad` — Three equidistant, balanced
- `split` — Complement adjacent, subtle
- `mono` — Single hue variations, cohesive

#### Config Manager (`config_manager.py`)
Persists theme state to JSON:

```python
class ConfigManager:
    def __init__(self):
        self._config = self._load()

    def save(self):
        # Write to storefront_config.json

    @property
    def config(self) -> StorefrontConfig:
        return self._config
```

#### Domain Models (`models.py`)
Core data structures:

```python
class StorefrontConfig:
    theme_name: str
    primary_color: str      # Hex + creative name
    secondary_color: str
    accent_color: str
    background_color: str
    surface_color: str
    heading_font: str       # Google Font
    body_font: str
    default_border_radius: BorderRadius  # sharp|soft|rounded|pill
    default_spacing: Spacing             # compact|normal|spacious
    zone_overrides: dict[Zone, ZoneStyle]

class Zone(Enum):
    HERO_BANNER = "hero_banner"
    STORE_LOGO = "store_logo"
    # ... 12 customizable zones
```

### 5. Tools (`tools.py`)

Agent tools bridge LLM reasoning with domain logic:

| Tool | Input | Output | Side Effects |
|------|-------|--------|--------------|
| `generate_color_palette` | seed_color, harmony, count | Palette with contrast info | None |
| `validate_color_and_get_info` | hex_color | Validation + variants | None |
| `check_color_accessibility` | fg, bg colors | WCAG analysis | None |
| `get_harmony_types` | — | Available harmonies | None |
| `get_available_fonts` | — | Categorized font list | None |
| `validate_font` | font_name | Availability check | None |
| `save_theme` | Full theme params | Confirmation | Writes config |
| `get_current_theme` | — | Current settings | None |
| `list_zones` | — | Customizable zones | None |
| `customize_zone` | zone, colors, radius | Confirmation | Updates config |
| `reset_zone` | zone_name | Confirmation | Updates config |
| `reset_all` | — | Confirmation | Resets config |

## Data Flow

### Conversation Flow

```
User: "I run a cozy coffee shop"
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Agent receives message                                          │
│                                                                 │
│ 1. Model interprets: coffee shop → warm, inviting atmosphere   │
│ 2. Model decides: ask about vibe preferences                    │
│ 3. Model generates structured response:                         │
│    {                                                            │
│      "message": "A cozy coffee shop! I love it...",            │
│      "response_type": "vibe_options",                          │
│      "vibe_options": [                                          │
│        {"name": "Warm & cozy", "description": "inviting..."},  │
│        {"name": "Modern & minimal", "description": "clean..."} │
│      ]                                                          │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Frontend renders clickable vibe pills                           │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
User clicks: "Warm & cozy"
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Agent receives "Warm & cozy"                                    │
│                                                                 │
│ 1. Model interprets: warm vibe for coffee shop                 │
│ 2. Model calls: generate_color_palette("#8B4513", "analogous") │
│ 3. Tool returns: [#8B4513, #A0522D, #CD853F, #DEB887, #F5DEB3] │
│ 4. Model calls: generate_color_palette("#2F4F4F", "complement")│
│ 5. Tool returns: [#2F4F4F, #4F7F7F, ...]                       │
│ 6. Model names colors creatively                                │
│ 7. Model generates theme packages                               │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
User: "I like Tuscan Workshop"
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Agent receives selection                                        │
│                                                                 │
│ 1. Model calls: save_theme(theme_name="Tuscan Workshop", ...)  │
│ 2. Tool writes: storefront_config.json                         │
│ 3. Tool returns: "Theme saved!"                                │
│ 4. Model generates confirmation                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Server regenerates HTML with new theme                          │
│ Frontend updates preview iframe                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Theme Application Flow

```
storefront_config.json
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ ConfigManager.config                                            │
│   theme_name: "Tuscan Workshop"                                │
│   primary_color: "#C45B28"                                     │
│   heading_font: "Playfair Display"                             │
│   ...                                                           │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ get_storefront_html()                                           │
│                                                                 │
│ 1. Read storefront.html template                               │
│ 2. Build theme JS object from config                           │
│ 3. Inject: storeInfo.theme = {...}                             │
│ 4. Return modified HTML                                         │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ storefront.html (in iframe)                                     │
│                                                                 │
│ applyTheme(theme) {                                            │
│   document.documentElement.style.setProperty(                   │
│     '--primary-color', theme.primaryColor                      │
│   );                                                            │
│   // Load Google Fonts                                          │
│   // Apply to all elements                                      │
│ }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Deployment Architecture

### Local Development

```
┌─────────────┐     HTTP      ┌─────────────┐     Bedrock    ┌─────────────┐
│   Browser   │◄────────────►│   FastAPI   │◄──────────────►│   Amazon    │
│   :5173     │              │   :8000     │    Converse    │   Bedrock   │
└─────────────┘              └─────────────┘                 └─────────────┘
                                    │
                                    ▼
                             ┌─────────────┐
                             │    Local    │
                             │    JSON     │
                             └─────────────┘
```

### Production (AgentCore)

```
┌─────────────┐     HTTP      ┌─────────────┐                ┌─────────────┐
│   Client    │◄────────────►│  AgentCore  │◄──────────────►│   Amazon    │
│   App       │              │   Runtime   │    Managed     │   Bedrock   │
└─────────────┘              └─────────────┘                 └─────────────┘
                                    │
                                    ▼
                             ┌─────────────┐
                             │  AgentCore  │
                             │   Memory    │
                             └─────────────┘
```

**AgentCore Benefits**:
- Auto-scaling based on load
- Managed infrastructure
- Built-in memory for sessions
- Observability and tracing
- No server management

### Architecture Decision Records

#### ADR-001: Screenshot route in the API Lambda (not a separate function)

**Decision:** The `/api/screenshot` endpoint is handled by the same Lambda function that serves `/api/chat`, `/api/storefront`, and all other routes.

**Context:** Screenshots in production use AgentCore Browser (remote Chromium via CDP WebSocket) + S3 upload. The Lambda acts as a thin orchestrator — it does not run a local browser binary.

**Alternatives considered:**
- **Separate Lambda** — would allow independent timeout/memory/concurrency config. Rejected because the screenshot path is lightweight (remote browser call + S3 PUT), similar in profile to the chat path, and a second function doubles operational surface without meaningful benefit at current scale.
- **Step Functions wrapper** — unnecessary for a synchronous 10-30s operation that fits within the 180s Lambda timeout.

**Consequences:**
- Shared concurrency pool between chat and screenshot (acceptable: screenshots are infrequent).
- Shared 180s timeout (acceptable: screenshots complete in 10-30s, chat in 5-60s).
- Single deployment artifact reduces operational overhead.
- If screenshot load grows disproportionately, revisit by extracting to a dedicated function with its own reserved concurrency.

---

## Observability

### Stack: `DesignStudioObservability` (CDK)

One-time per-account/region setup that enables AgentCore GenAI Observability:

1. **CloudWatch Logs resource policy** — allows X-Ray to ingest spans into `aws/spans` and `/aws/application-signals/data` log groups (required for Transaction Search)
2. **X-Ray trace segment destination** — routes trace segments to CloudWatch Logs via `UpdateTraceSegmentDestination` custom resource
3. **CloudWatch dashboard** (`DesignStudio-Observability`) — comprehensive metrics view

### Lambda Backend (`lambda_backend/handler.py`)

Instrumented with [AWS Lambda Powertools](https://docs.powertools.aws.dev/lambda/python/latest/) (v3):

| Utility | Purpose |
|---------|---------|
| **Logger** | Structured JSON logs with correlation IDs (`xray_trace_id`, `merchant_id`, `session_id`) |
| **Tracer** | X-Ray distributed tracing with `@capture_method` on each route handler |
| **Metrics** | CloudWatch EMF custom metrics (namespace: `DesignStudio`) |

**Custom metrics** (not available from managed sources — Function URLs lack API Gateway error counting):
- `ClientError` — application 4xx responses
- `ServerError` — application 5xx responses
- `AuthFailure` — origin secret mismatch (403)
- `ThemePublished` — business metric
- `ScreenshotCaptured` — business metric
- `ColdStart` — auto-captured by Powertools

**Environment variables** (set in CDK `api-stack.ts`):
```
POWERTOOLS_SERVICE_NAME=design-studio-api
POWERTOOLS_METRICS_NAMESPACE=DesignStudio
POWERTOOLS_LOG_LEVEL=INFO
POWERTOOLS_TRACER_CAPTURE_RESPONSE=false  # responses exceed X-Ray 64KB UDP limit
```

### AgentCore Runtime (`conversational_agent/`)

- **OTEL auto-instrumentation**: `aws-opentelemetry-distro==0.12.2` in the container image. AgentCore Runtime auto-instruments Bedrock calls, tool executions, and HTTP requests.
- **Structured logging**: `observability.py` provides a shared Powertools `Logger` instance (service: `design-studio-agent`) with `merchant_id` and `session_id` context.
- **Custom metrics**: `AgentInvocation` (success count), `AgentError` (exception count) — not available from any managed source.

### Trace Flow

```
Browser → CloudFront → Lambda (X-Ray active tracing, Powertools Tracer)
                          │
                          ├── DynamoDB (auto-instrumented by X-Ray SDK)
                          │
                          └── AgentCore Runtime (OTEL → CloudWatch)
                                   │
                                   ├── Bedrock InvokeModel (auto-instrumented)
                                   ├── Tool executions (auto-instrumented)
                                   └── AgentCore Browser (auto-instrumented)
```

### Operational Notes

- **X-Ray UDP limit**: `POWERTOOLS_TRACER_CAPTURE_RESPONSE` must be `false` in production — storefront HTML responses exceed the 64KB subsegment metadata limit, causing `OSError: Message too long`.
- **AgentCore concurrency**: Strands agents do not support concurrent invocations on the same instance. AgentCore routes same-session requests to the same container. The Lambda `read_timeout` (180s) must match or exceed the Lambda timeout to prevent premature socket timeouts triggering retries that hit a busy container (causes `ConcurrencyException`).
- **Transaction Search prerequisite**: The OTEL exporter in the agent container will log `400: The OTLP API is supported with CloudWatch Logs as a Trace Segment Destination` until the `DesignStudioObservability` stack's custom resource successfully runs. Alternatively, the stack the custome resource can be ignored, and you can 'Enable Transaction search' manually in the Cloudwactch console

---

## Extension Points

### Adding New Tools

1. Define tool in `tools.py`:
```python
@tool
def my_new_tool(param: str) -> str:
    """Tool description for the LLM.

    Args:
        param: What this parameter does.

    Returns:
        What the tool returns.
    """
    # Implementation
    return result
```

2. Add to `AGENT_TOOLS` in `agent.py`

3. Update system prompt if needed

### Adding New Response Types

1. Add model to `response_models.py`:
```python
class NewOption(BaseModel):
    field: str = Field(description="...")
```

2. Add to `AgentResponse`:
```python
class AgentResponse(BaseModel):
    # ...existing fields...
    new_options: Optional[List[NewOption]] = None
```

3. Update system prompt with new response_type

4. Handle in frontend

### Changing Models

Environment variable:
```bash
AGENT_MODEL=us.anthropic.claude-sonnet-4-20250514-v1:0 uv run design-server
```

Or in code:
```python
agent = create_agent(model="us.anthropic.claude-sonnet-4-20250514-v1:0")
```

### Customizing the Prompt

Edit `prompts/system_prompt.md` — no code changes needed.

## Security Considerations

1. **Input Validation**: Pydantic models validate all structured input/output
2. **Color Validation**: Hex codes validated before use
3. **Font Validation**: Only Google Fonts allowed (no arbitrary URLs)
4. **Sandbox Preview**: Storefront renders in sandboxed iframe
5. **No PII Storage**: Theme config contains no personal data

## Performance Considerations

1. **Model Selection**: Nova Pro balances speed and capability
2. **Tool Efficiency**: Tools return minimal necessary data
3. **Caching**: Font list cached in constants
4. **Streaming**: Strands supports streaming (not yet exposed in API)

## Testing Strategy

| Level | What | How |
|-------|------|-----|
| Unit | Color engine, validators | pytest |
| Integration | Tool execution | pytest with mocks |
| Agent | Conversation flows | Terminal CLI |
| E2E | Full UI flow | Manual + Playwright |

## File Reference

```
design_studio/
├── design_studio/
│   ├── __init__.py           # Package exports
│   ├── agent.py              # Agent factory (shared)
│   ├── config.py             # Configuration loading
│   ├── response_models.py    # Pydantic response types
│   ├── tools.py              # Agent tools
│   ├── models.py             # Domain models
│   ├── color_engine.py       # Color science
│   ├── config_manager.py     # Theme persistence
│   ├── constants.py          # Static data (fonts, etc.)
│   ├── server.py             # FastAPI (dev only)
│   ├── runtime.py            # AgentCore (prod)
│   ├── main.py               # CLI entry
│   └── prompts/
│       └── system_prompt.md  # Agent personality
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # React app
│   │   └── styles.css        # UI styles
│   ├── package.json
│   └── vite.config.js
├── storefront.html           # Preview template
├── pyproject.toml            # Python config
├── README.md                 # Quick start
└── ARCHITECTURE.md           # This document
```
