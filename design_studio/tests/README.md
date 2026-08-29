# Tests

Starter test suite for the parts of the design agent that don't need AWS
credentials — the color science layer, the Bedrock-free agent tools, and
the config-persistence layer.

## Running

```bash
uv sync --extra dev
uv run pytest                    # full suite
uv run pytest -v                 # verbose
uv run pytest --cov=conversational_agent   # with coverage
```

## What's covered

| File | What it tests |
|---|---|
| `test_color_engine.py` | `validate_hex`, `normalize_hex`, WCAG contrast (`check_contrast_ratio`, `is_accessible`, `get_contrast_color`), `adjust_for_contrast`, `get_lighter`/`get_darker`, `generate_palette_from_seed` for all six harmonies, `is_valid_google_font`. |
| `test_tools.py` | The Bedrock-free `@tool` functions: `validate_color_and_get_info`, `check_color_accessibility`, `get_harmony_types`, `get_available_fonts` (regression for the `fonts.json` wiring), `validate_font`. |
| `test_config_manager.py` | `ConfigManager` save/load round-trip, default values, zone-override serialization. Always uses `tmp_path` so tests never touch your CWD. |

## What's *not* covered (yet)

- Tools that mutate `ConfigManager` and require an agent loop (`save_theme`,
  `customize_zone`, `reset_zone`, `reset_all`) — those need integration tests
  against a real Bedrock-backed agent.
- The FastAPI `server.py` endpoints — being replaced by the Lambda per
  `cdk/NEXT_STEPS.md`, not worth investing in now.
- The AgentCore `runtime.py` entrypoint — needs a deployed runtime to exercise.
