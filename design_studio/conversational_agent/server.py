"""FastAPI dev server — REST API for the React Design Studio UI.

**Not deployed to production.** Production uses ``runtime.py`` (AgentCore) plus a
separate API layer (see ``cdk/NEXT_STEPS.md``).

Request pipeline for chat (``POST /api/chat``):
  1. Photo-to-palette extraction when an image is attached (Z1-04)
  2. ``run_fast_path()`` — zone tour + theme choice only when UI focus sends style to agent
  3. Strands agent with page / focus context (visualizes storefront via tools)

In-memory state (dev only):
  - ``_agents`` — one Strands agent per ``merchantId`` (with AgentCore Memory hooks)
  - ``_agent_sessions`` — memory session ID per merchant
  - ``chat_session`` — chat history per merchant for UI display (not passed to the LLM)

Run: ``uv run design-server`` (port 8000). Source ``example.env`` for DynamoDB Local.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agent import create_agent
from .agent_memory import memory_persist_context
from .api_response import (
    _repo,
    attach_section_focus,
    enrich_with_zone_tour,
    preview_payload,
    version_api_payload,
)
from .chat_fast_path import run_fast_path
from .chat_session import clear_history, get_history, set_history
from .config import GREETING_PROMPT
from .config_manager import ConfigManager
from .page_context import (
    build_page_context_for_agent,
    format_focused_style_message,
    format_page_context_message,
    format_zone_tour_agent_message,
    has_explicit_ui_focus,
    is_cross_page_style_request,
)
from .palette import (
    PaletteError,
    extract_palette,
    is_brand_palette_request,
    parse_brand_palette,
)
from .preview_html import get_storefront_html
from .palette_diversifier import diversify_theme_packages
from .response_models import AgentResponse
from .section_focus import format_focus_agent_prefix, list_sections_for_ui, merge_focus
from .shop_context import shop_context
from .style_repository import StyleRepository
from .theme_choice_actions import clear_pending_theme_packages, store_pending_theme_packages
from .zone_tour import ZoneTourManager

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Storefront Design Agent (Dev Server)",
    description="Local development server for the storefront design agent",
)

_CORS_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_MERCHANT_ID_PATTERN = re.compile(os.environ.get("MERCHANT_ID_REGEX", r"^[a-zA-Z0-9_-]{1,64}$"))


def _validate_merchant_id(merchant_id: str) -> str:
    """Validate merchantId format. Raises HTTPException 400 on invalid input."""
    if not merchant_id or not _MERCHANT_ID_PATTERN.match(merchant_id):
        raise HTTPException(status_code=400, detail="Invalid merchant ID format")
    return merchant_id


_agents: dict[str, Any] = {}  # Strands agent cache — one instance per merchantId
_agent_sessions: dict[str, str] = {}  # AgentCore Memory session ID per merchantId
_agent_locks: dict[str, asyncio.Lock] = {}  # Strands allows one in-flight call per agent


def get_agent(merchant_id: str):
    """Return a cached Strands agent for the merchant (created on first use)."""
    if merchant_id not in _agents:
        session_id = _agent_sessions.setdefault(merchant_id, str(uuid.uuid4()))
        _agents[merchant_id] = create_agent(
            merchant_id=merchant_id,
            session_id=session_id,
        )
        get_history(merchant_id)
    return _agents[merchant_id]


def _get_agent_lock(merchant_id: str) -> asyncio.Lock:
    """One lock per merchant — Strands rejects concurrent calls on the same agent."""
    if merchant_id not in _agent_locks:
        _agent_locks[merchant_id] = asyncio.Lock()
    return _agent_locks[merchant_id]


async def _invoke_agent_body(
    agent: Any,
    merchant_id: str,
    prompt: str,
    *,
    persist_message: str | None = None,
    persist_memory: bool = True,
) -> Any:
    """Run one Strands call (caller must hold ``_get_agent_lock`` when needed)."""
    with shop_context(merchant_id):
        with memory_persist_context(
            merchant_message=persist_message,
            enabled=persist_memory,
        ):
            return await asyncio.to_thread(
                lambda: agent(prompt, structured_output_model=AgentResponse)
            )


async def _invoke_agent(
    agent: Any,
    merchant_id: str,
    prompt: str,
    *,
    persist_message: str | None = None,
    persist_memory: bool = True,
) -> Any:
    """Run Strands agent call serially for this merchant (Bedrock in worker thread)."""
    async with _get_agent_lock(merchant_id):
        return await _invoke_agent_body(
            agent,
            merchant_id,
            prompt,
            persist_message=persist_message,
            persist_memory=persist_memory,
        )


class ChatRequest(BaseModel):
    merchantId: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    message: str = Field(max_length=9500)
    focusZone: str | None = None
    focusSectionId: str | None = None
    focusElementId: str | None = None
    image: str | None = Field(default=None, max_length=7_100_000)
    imageType: str | None = Field(default=None, max_length=50)


class MerchantRequest(BaseModel):
    merchantId: str = Field(default="demo-merchant", pattern=r"^[a-zA-Z0-9_-]{1,64}$")


class RestoreRequest(BaseModel):
    merchantId: str = Field(default="demo-merchant", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    versionId: int = Field(default=0, ge=0)


class ViewportConfig(BaseModel):
    width: int = Field(default=390, ge=100, le=3840)
    height: int = Field(default=900, ge=100, le=3840)


class ScreenshotRequest(BaseModel):
    merchantId: str = Field(default="demo-merchant", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    viewport: ViewportConfig = Field(default_factory=ViewportConfig)


def _merge_tour_advance_into_message(
    merchant_id: str,
    resp: dict[str, Any],
    tour_sub_step_before: tuple[str, int] | None,
) -> dict[str, Any]:
    """When the tour advanced during an agent turn, append the next step prompt to the reply."""
    if not tour_sub_step_before:
        return resp
    from .zone_tour import ZoneTourManager
    from .zone_tour_actions import _next_step_message

    mgr = ZoneTourManager(merchant_id)
    if not mgr.is_active():
        return resp
    step = mgr.current_step()
    if not step:
        return resp
    after = (step.code, mgr.get_sub_step_index())
    if after == tour_sub_step_before:
        return resp

    next_msg = _next_step_message(mgr, step)
    if not next_msg:
        return resp
    msg = (resp.get("message") or "").strip()
    if next_msg not in msg:
        resp["message"] = f"{msg}\n\n{next_msg}" if msg else next_msg
    if resp.get("type") in (None, "message", "applied"):
        resp["type"] = "zone_tour"
    return resp


def _agent_response_to_api(
    response: AgentResponse,
    merchant_id: str,
    focus,
    *,
    user_message: str = "",
    tour_option_ids_before: set[str] | None = None,
    tour_sub_step_before: tuple[str, int] | None = None,
) -> dict[str, Any]:
    """Map structured ``AgentResponse`` to JSON + preview payload + zone tour enrichment."""
    from .zone_tour_post_refresh import ensure_tour_options_refreshed_if_requested

    resp: dict[str, Any] = {
        "type": response.response_type,
        "message": response.message,
    }
    resp = attach_section_focus(resp, merchant_id, focus)
    if response.vibe_options:
        resp["vibe_options"] = [opt.model_dump() for opt in response.vibe_options]
    if response.theme_packages:
        packages = [pkg.model_dump() for pkg in response.theme_packages]
        packages = diversify_theme_packages(packages)
        store_pending_theme_packages(merchant_id, packages)
        resp["theme_packages"] = packages
    if response.color_options:
        resp["color_options"] = [opt.model_dump() for opt in response.color_options]
    if response.zone_tour:
        resp["zone_tour"] = response.zone_tour.model_dump()
    resp = ensure_tour_options_refreshed_if_requested(
        merchant_id,
        user_message,
        resp,
        option_ids_before=tour_option_ids_before,
    )
    resp = _merge_tour_advance_into_message(merchant_id, resp, tour_sub_step_before)
    return enrich_with_zone_tour(resp, merchant_id)


def build_palette_prompt(colors: list[str], message: str) -> str:
    """Compose the agent prompt for photo-to-palette extraction (Z1-04)."""
    color_list = ", ".join(colors)
    note = f' The merchant also said: "{message}".' if message.strip() else ""
    return (
        "The merchant uploaded a photo/logo. These are the dominant colours "
        f"extracted from it, most prominent first: {color_list}. "
        "Create exactly 3 distinct theme package arrangements built from these "
        "colours (you may lighten/darken or pick complementary neutrals where a "
        "palette needs a background or text colour, but keep the extracted "
        "colours as the clear foundation). Return them as theme_packages with "
        f"evocative names and descriptions.{note}"
    )


def build_brand_palette_prompt(message: str, colors: list[str]) -> str:
    """Compose the agent prompt for a merchant-supplied brand palette (Z1-03).

    The merchant may give hex codes, colour names, or descriptions ("my brand red");
    the agent interprets them, maps to roles, offers arrangements, and checks contrast.
    """
    hex_note = f" Explicit hex codes they gave: {', '.join(colors)}." if colors else ""
    return (
        "The merchant wants their own brand colours used across the storefront. "
        f'Their request: "{message}".{hex_note} '
        'Interpret any colour names or descriptions (e.g. "my brand red", "forest '
        'green") into concrete hex values, then map the colours to storefront roles '
        "(primary, accent, background; derive text/surface shades where needed). "
        "Create exactly 3 distinct theme package arrangements as theme_packages with "
        "evocative names and descriptions. Use check_color_accessibility to validate "
        "text-on-background contrast in each arrangement, and in your message warn the "
        "merchant if any pairing fails WCAG AA, suggesting a small adjustment."
    )


def _internal_error(e: Exception) -> HTTPException:
    """Log full exception, return generic error with correlation ID."""
    correlation_id = str(uuid.uuid4())[:8]
    logger.exception("Internal error [%s]", correlation_id)
    return HTTPException(
        status_code=500,
        detail=f"Internal error (ref: {correlation_id})",
    )


async def _run_agent(
    agent: Any,
    merchant_id: str,
    prompt: str,
    focus,
    *,
    persist_message: str | None = None,
    persist_memory: bool = True,
) -> dict[str, Any]:
    """Invoke the agent in a worker thread and build the enriched API response."""
    from .zone_tour import ZoneTourManager

    tour_mgr = ZoneTourManager(merchant_id)
    tour_ids_before = tour_mgr.get_cached_option_ids()
    tour_sub_before = (
        (tour_mgr.current_step().code, tour_mgr.get_sub_step_index())
        if tour_mgr.is_active() and tour_mgr.current_step()
        else None
    )
    user_text = (persist_message or prompt).strip()
    try:
        result = await _invoke_agent(
            agent,
            merchant_id,
            prompt,
            persist_message=persist_message,
            persist_memory=persist_memory,
        )
        response: AgentResponse = result.structured_output
        get_history(merchant_id).append({"role": "assistant", "content": response.message})
        resp = _agent_response_to_api(
            response,
            merchant_id,
            focus,
            user_message=user_text,
            tour_option_ids_before=tour_ids_before,
            tour_sub_step_before=tour_sub_before,
        )
        return resp
    except HTTPException:
        raise
    except Exception as e:
        raise _internal_error(e) from e


@app.get("/api/sections")
async def list_sections():
    return {"sections": list_sections_for_ui()}


@app.get("/api/storefront/{merchant_id}")
async def get_storefront(
    merchant_id: str,
    focusZone: str | None = None,
    focusElementId: str | None = None,
):
    _validate_merchant_id(merchant_id)
    focus = merge_focus(
        focus_zone=focusZone,
        focus_element_id=focusElementId,
        message="",
    )
    resp = preview_payload(
        merchant_id,
        focus_zone=focus.zone if focus else None,
        focus_element_id=focus.element_id if focus else None,
    )
    resp["sections"] = list_sections_for_ui()
    if focus:
        resp["section_focus"] = focus.to_api_dict()
    return enrich_with_zone_tour(resp, merchant_id)


@app.get("/api/zone-tour/{merchant_id}")
async def get_zone_tour(merchant_id: str):
    """Zone tour progress for the UI progress bar (CF-05)."""
    return ZoneTourManager(merchant_id).progress_dict()


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Main chat endpoint — routes between fast-path handlers and the Strands agent."""
    agent = get_agent(request.merchantId)
    focus = merge_focus(
        focus_zone=request.focusZone,
        focus_section_id=request.focusSectionId,
        focus_element_id=request.focusElementId,
        message=request.message,
    )

    # --- Branch 1: Photo upload → palette extraction → agent theme packages (Z1-04) ---
    if request.image:
        try:
            colors = extract_palette(request.image)
        except PaletteError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        agent_prompt = build_palette_prompt(colors, request.message)
        get_history(request.merchantId).append(
            {"role": "user", "content": request.message or "[uploaded a photo]"}
        )
        return await _run_agent(
            agent,
            request.merchantId,
            agent_prompt,
            focus,
            persist_message=request.message or "[uploaded a photo]",
        )

    # --- Branch 1b: Merchant-supplied brand palette (names, hexes, or descriptions) → Z1-03 ---
    if is_brand_palette_request(request.message):
        brand_palette = parse_brand_palette(request.message) or []
        repo = _repo(request.merchantId)
        if repo.enabled and brand_palette:
            repo.update_brand_palette(brand_palette, shop_uuid=request.merchantId)
        agent_prompt = build_brand_palette_prompt(request.message, brand_palette)
        get_history(request.merchantId).append({"role": "user", "content": request.message})
        return await _run_agent(
            agent,
            request.merchantId,
            agent_prompt,
            focus,
            persist_message=request.message,
        )

    if request.message.strip():
        # --- Branch 2: Non-empty message → fast path, then agent with rich context ---
        cross_page = is_cross_page_style_request(request.message)
        ui_focus = has_explicit_ui_focus(
            focus_zone=request.focusZone,
            focus_section_id=request.focusSectionId,
            focus_element_id=request.focusElementId,
        )
        # Focused UI edits and whole-page asks need tool orchestration, not phrase parsers.
        style_via_agent = ui_focus or cross_page
        fast = run_fast_path(
            request.merchantId,
            request.message,
            focus,
            allow_zone_tour=not cross_page,  # cross-page style must not hijack tour state
            style_via_agent=style_via_agent,
        )
        if fast:
            return fast

        tour_active = not cross_page and ZoneTourManager(request.merchantId).is_active()
        from .message_parsers import parse_zone_option_id as _parse_zone_option_id

        if tour_active and _parse_zone_option_id(request.message.strip()):
            from .zone_tour_actions import try_handle_zone_tour_message
            from .zone_tour_flow import current_sub_step, options_for_sub_step

            mgr = ZoneTourManager(request.merchantId)
            step = mgr.current_step()
            sub = current_sub_step(step.code, mgr.get_sub_step_index()) if step else None
            if step and sub:
                options_for_sub_step(step.code, sub, request.merchantId)
            retry = try_handle_zone_tour_message(request.merchantId, request.message.strip())
            if retry:
                return retry

        # Build agent prompt: cross-page gets full blueprint JSON; UI focus gets scoped workflow.
        if tour_active:
            agent_message = format_zone_tour_agent_message(request.merchantId, request.message)
        elif cross_page:
            agent_message = format_page_context_message(request.merchantId, request.message)
        elif ui_focus and focus:
            agent_message = format_focused_style_message(request.merchantId, request.message, focus)
        else:
            focus_prefix = format_focus_agent_prefix(focus)
            ctx_snapshot = build_page_context_for_agent(request.merchantId)
            agent_message = (
                focus_prefix
                + f"[Current preview look: {json.dumps(ctx_snapshot.get('look_and_feel_now', {}))}. "
                "Use get_storefront_page_context if you need the full page map or playbook.]\n\n"
                f"{request.message}"
            )

        get_history(request.merchantId).append({"role": "user", "content": request.message})
        return await _run_agent(
            agent,
            request.merchantId,
            agent_message,
            focus,
            persist_message=request.message,
        )

    # --- Branch 3: Empty message → greeting on first visit, else echo last assistant turn ---
    # Re-read history under the per-merchant lock so concurrent empty POSTs cannot
    # both run GREETING_PROMPT (Strict Mode / double-mount).
    async with _get_agent_lock(request.merchantId):
        history = get_history(request.merchantId)
        if not history:
            try:
                result = await _invoke_agent_body(
                    agent,
                    request.merchantId,
                    GREETING_PROMPT,
                    persist_memory=False,
                )
            except Exception as e:
                raise _internal_error(e) from e
            response: AgentResponse = result.structured_output
            set_history(
                request.merchantId,
                [{"role": "assistant", "content": response.message}],
            )
            return {
                "type": response.response_type,
                "message": response.message,
                "html": None,
                "version": 0,
                "totalVersions": 1,
                "sections": list_sections_for_ui(),
            }

        last_msg = history[-1]
        return {
            "type": "message",
            "message": last_msg.get("content", "How can I help?"),
            "html": None,
            "version": 0,
            "totalVersions": 1,
        }


@app.post("/api/undo")
async def undo(request: MerchantRequest):
    merchant_id = _validate_merchant_id(request.merchantId)
    repo = _repo(merchant_id)

    if repo.enabled:
        tokens = repo.undo(merchant_id)
    else:
        tokens = ConfigManager(shop_uuid=merchant_id).undo()
    if tokens is None:
        raise HTTPException(status_code=400, detail="Nothing to undo")

    return preview_payload(merchant_id)


@app.post("/api/redo")
async def redo(request: MerchantRequest):
    merchant_id = _validate_merchant_id(request.merchantId)
    repo = _repo(merchant_id)

    if repo.enabled:
        tokens = repo.redo(merchant_id)
    else:
        tokens = ConfigManager(shop_uuid=merchant_id).redo()
    if tokens is None:
        raise HTTPException(status_code=400, detail="Nothing to redo")

    return enrich_with_zone_tour(preview_payload(merchant_id), merchant_id)


@app.post("/api/publish")
async def publish(request: MerchantRequest):
    """Publish draft to live style (CF-10)."""
    merchant_id = _validate_merchant_id(request.merchantId)
    repo = _repo(merchant_id)
    if not repo.enabled:
        raise HTTPException(status_code=503, detail="DynamoDB not configured")

    published = repo.publish_draft(merchant_id)
    if not published:
        raise HTTPException(status_code=400, detail="No draft to publish")

    return {
        "message": "Theme published to your live storefront.",
        "html": get_storefront_html(merchant_id),
        "publishedAt": published.get("publishedAt"),
        "rollbackUntil": published.get("rollbackUntil"),
        "changeSummary": (published.get("changeSummary") or {}).get("humanSummary", ""),
    }


@app.post("/api/reset")
async def reset(request: MerchantRequest):
    merchant_id = _validate_merchant_id(request.merchantId)

    ConfigManager(shop_uuid=merchant_id).reset()

    if merchant_id in _agents:
        del _agents[merchant_id]
    # Clears per-merchant memory session; shared memory resource ID stays process-cached.
    _agent_sessions.pop(merchant_id, None)
    _agent_locks.pop(merchant_id, None)
    clear_history(merchant_id)
    clear_pending_theme_packages(merchant_id)

    return enrich_with_zone_tour(preview_payload(merchant_id), merchant_id)


@app.get("/api/versions/{merchant_id}")
async def get_versions(merchant_id: str):
    _validate_merchant_id(merchant_id)
    repo = _repo(merchant_id)
    if repo.enabled:
        return version_api_payload(repo.list_version_summaries(merchant_id))
    return version_api_payload(ConfigManager(shop_uuid=merchant_id).list_local_version_summaries())


@app.post("/api/restore")
async def restore_version(request: RestoreRequest):
    merchant_id = _validate_merchant_id(request.merchantId)
    repo = _repo(merchant_id)

    if repo.enabled:
        summaries = repo.list_version_summaries(merchant_id)
        if request.versionId >= len(summaries):
            raise HTTPException(status_code=400, detail="Invalid version")
        seq = summaries[request.versionId]["versionSeq"]
        repo.restore_version(seq, merchant_id)
    else:
        cm = ConfigManager(shop_uuid=merchant_id)
        if not cm.restore_local_index(request.versionId):
            raise HTTPException(status_code=400, detail="Invalid version")

    return preview_payload(merchant_id)


@app.post("/api/screenshot")
@app.post("/api/screenshot/agentcore")
async def screenshot_storefront(request: ScreenshotRequest):
    """Capture current storefront preview as PNG. HTML is generated server-side."""
    from .preview_html import get_storefront_html
    from .screenshot_service import capture_and_upload

    merchant_id = _validate_merchant_id(request.merchantId)
    try:
        html = get_storefront_html(merchant_id)
        result = await capture_and_upload(
            html, merchant_id, request.viewport.width, request.viewport.height
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail="Screenshot service unavailable") from e
    except HTTPException:
        raise
    except Exception as e:
        raise _internal_error(e) from e

    return JSONResponse(
        content=result,
        headers={"X-Screenshot-Time-Ms": str(result["timeMs"])},
    )


# Backward-compatible aliases for tests and external imports
_preview_payload = preview_payload
_enrich_with_zone_tour = enrich_with_zone_tour
_version_api_payload = version_api_payload


def _require_dynamodb_persistence() -> None:
    """Design server must not silently write JSON history files into the repo directory.

    ``USE_DYNAMODB=false`` is allowed (pytest JSON fallback). Otherwise
    ``DYNAMODB_ENDPOINT`` must be set — typically via ``source example.env``.
    """
    use = os.environ.get("USE_DYNAMODB", "true").lower()
    if use in ("0", "false", "no"):
        return
    endpoint = (os.environ.get("DYNAMODB_ENDPOINT") or "").strip()
    if not endpoint:
        raise SystemExit(
            "DynamoDB persistence is required for design-server. "
            "Set DYNAMODB_ENDPOINT (run: cd design_studio && source example.env)."
        )

    if not StyleRepository().enabled:
        raise SystemExit(
            "DynamoDB persistence is misconfigured (USE_DYNAMODB=true but endpoint missing)."
        )


def run_server():
    _require_dynamodb_persistence()
    import logging
    import uvicorn

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s:     %(name)s — %(message)s",
        )
    logging.getLogger("conversational_agent").setLevel(logging.INFO)
    logging.getLogger("botocore.parsers").setLevel(logging.WARNING)

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
