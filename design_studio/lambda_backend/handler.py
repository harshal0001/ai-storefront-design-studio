"""Lambda Function URL backend for the deployed Design Studio API.

The production SPA calls this function through CloudFront. The function keeps
non-LLM routes local and proxies chat requests to the AgentCore Runtime.
"""

from __future__ import annotations

import base64
import json
import os
from decimal import Decimal
from typing import Any

import boto3
import botocore.config
import botocore.exceptions
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

from conversational_agent.api_response import (
    enrich_with_zone_tour,
    preview_payload,
    version_api_payload,
)
from conversational_agent.chat_fast_path import run_fast_path
from conversational_agent.config_manager import ConfigManager
from conversational_agent.message_parsers import is_brand_palette_request
from conversational_agent.page_context import (
    has_explicit_ui_focus,
    is_cross_page_style_request,
)
from conversational_agent.preview_html import get_storefront_html
from conversational_agent.section_focus import list_sections_for_ui, merge_focus
from conversational_agent.style_repository import StyleRepository
from conversational_agent.theme_choice_actions import store_pending_theme_packages
from conversational_agent.zone_tour import ZoneTourManager

logger = Logger(service="design-studio-api")
tracer = Tracer(service="design-studio-api")
metrics = Metrics(namespace="DesignStudio", service="design-studio-api")

_AGENT_CLIENT = None
_ORIGIN_SECRET: str | None = None


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle Function URL payload v2 requests."""
    if _method(event) == "OPTIONS":
        return _empty_response(204)

    if not _origin_secret_matches(event):
        metrics.add_metric(name="AuthFailure", unit=MetricUnit.Count, value=1)
        return _text_response(403, "forbidden")

    try:
        return _dispatch(event)
    except ValueError as exc:
        metrics.add_metric(name="ClientError", unit=MetricUnit.Count, value=1)
        logger.warning("Client error", error=str(exc), path=_path(event))
        return _json_response(400, {"detail": str(exc)})
    except LookupError as exc:
        return _json_response(404, {"detail": str(exc)})
    except Exception:
        metrics.add_metric(name="ServerError", unit=MetricUnit.Count, value=1)
        logger.exception("Unhandled error", path=_path(event))
        return _json_response(500, {"detail": "Internal server error"})


def _dispatch(event: dict[str, Any]) -> dict[str, Any]:
    method = _method(event)
    path = _path(event)
    metrics.add_dimension(
        name="Route", value=f"{method} {path.split('/')[2] if path.count('/') >= 2 else path}"
    )

    if method == "POST" and path == "/api/chat":
        return _json_response(200, _chat(_json_body(event)))

    if method == "GET" and path.startswith("/api/storefront/"):
        merchant_id = _path_tail(path, "/api/storefront/")
        return _json_response(200, _storefront(event, merchant_id))

    if method == "GET" and path.startswith("/api/versions/"):
        merchant_id = _path_tail(path, "/api/versions/")
        repo = _repo(merchant_id)
        return _json_response(200, version_api_payload(repo.list_version_summaries(merchant_id)))

    if method == "GET" and path.startswith("/api/zone-tour/"):
        merchant_id = _path_tail(path, "/api/zone-tour/")
        return _json_response(200, ZoneTourManager(merchant_id).progress_dict())

    if method == "POST" and path == "/api/restore":
        return _json_response(200, _restore(_json_body(event)))

    if method == "POST" and path == "/api/undo":
        return _json_response(200, _undo(_json_body(event)))

    if method == "POST" and path == "/api/redo":
        return _json_response(200, _redo(_json_body(event)))

    if method == "POST" and path == "/api/publish":
        return _json_response(200, _publish(_json_body(event)))

    if method == "POST" and path == "/api/reset":
        return _json_response(200, _reset(_json_body(event)))

    if method == "POST" and path in ("/api/screenshot", "/api/screenshot/agentcore"):
        return _json_response(200, _screenshot(_json_body(event)))

    raise LookupError("Not found")


@tracer.capture_method
def _chat(body: dict[str, Any]) -> dict[str, Any]:
    merchant_id = _required_str(body, "merchantId")
    session_id = str(body.get("sessionId") or body.get("session_id") or f"{merchant_id}-default")
    message = str(body.get("message") or "")

    logger.append_keys(merchant_id=merchant_id, session_id=session_id)
    tracer.put_annotation(key="MerchantId", value=merchant_id)

    # Deterministic handlers (theme-card choice, direct style edits, zone tour) resolve
    # server-side without a Bedrock round trip. This both speeds up the common cases and
    # avoids the CloudFront origin timeout (504) that slow LLM turns were hitting.
    fast_response = _try_fast_path(body, merchant_id, message)
    if fast_response is not None:
        metrics.add_metric(name="FastPathHit", unit=MetricUnit.Count, value=1)
        return fast_response

    # TODO(auth): replace merchantId from the body with verified JWT claims.
    agent_response = _invoke_agent_runtime(
        {
            "message": message,
            "session_id": session_id,
            "merchant_id": merchant_id,
        },
        session_id=session_id,
    )

    # Remember any theme cards the agent just offered so a follow-up `I choose "…"`
    # can be applied by the fast path without another (timeout-prone) Bedrock call.
    packages = agent_response.get("theme_packages") if isinstance(agent_response, dict) else None
    if packages:
        store_pending_theme_packages(merchant_id, packages)

    return agent_response


def _try_fast_path(body: dict[str, Any], merchant_id: str, message: str) -> dict[str, Any] | None:
    """Run deterministic chat handlers; return an API payload or None for the agent.

    Mirrors the dev server's chat routing: image uploads and brand-palette requests
    always need the agent, focused/cross-page edits orchestrate via agent tools, and
    everything else tries the phrase parsers first.
    """
    if not message.strip():
        return None
    # Image-to-palette extraction is agent-only (and PIL is not bundled in the Lambda).
    if body.get("image"):
        return None
    if is_brand_palette_request(message):
        return None

    focus_zone = body.get("focusZone")
    focus_section_id = body.get("focusSectionId")
    focus_element_id = body.get("focusElementId")
    focus = merge_focus(
        focus_zone=focus_zone,
        focus_section_id=focus_section_id,
        focus_element_id=focus_element_id,
        message=message,
    )

    cross_page = is_cross_page_style_request(message)
    style_via_agent = (
        has_explicit_ui_focus(
            focus_zone=focus_zone,
            focus_section_id=focus_section_id,
            focus_element_id=focus_element_id,
        )
        or cross_page
    )

    return run_fast_path(
        merchant_id,
        message,
        focus,
        allow_zone_tour=not cross_page,
        style_via_agent=style_via_agent,
    )


@tracer.capture_method
def _storefront(event: dict[str, Any], merchant_id: str) -> dict[str, Any]:
    params = event.get("queryStringParameters") or {}
    focus = merge_focus(
        focus_zone=params.get("focusZone"),
        focus_element_id=params.get("focusElementId"),
        message="",
    )
    response = preview_payload(
        merchant_id,
        focus_zone=focus.zone if focus else None,
        focus_element_id=focus.element_id if focus else None,
    )
    response["sections"] = list_sections_for_ui()
    if focus:
        response["section_focus"] = focus.to_api_dict()
    return enrich_with_zone_tour(response, merchant_id)


@tracer.capture_method
def _restore(body: dict[str, Any]) -> dict[str, Any]:
    merchant_id = _required_str(body, "merchantId")
    version_id = int(body.get("versionId", 0))
    repo = _repo(merchant_id)
    summaries = repo.list_version_summaries(merchant_id)
    if version_id < 0 or version_id >= len(summaries):
        raise ValueError("Invalid version")
    seq = summaries[version_id]["versionSeq"]
    repo.restore_version(seq, merchant_id)
    return preview_payload(merchant_id)


@tracer.capture_method
def _undo(body: dict[str, Any]) -> dict[str, Any]:
    merchant_id = _required_str(body, "merchantId")
    if _repo(merchant_id).undo(merchant_id) is None:
        raise ValueError("Nothing to undo")
    return preview_payload(merchant_id)


@tracer.capture_method
def _redo(body: dict[str, Any]) -> dict[str, Any]:
    merchant_id = _required_str(body, "merchantId")
    if _repo(merchant_id).redo(merchant_id) is None:
        raise ValueError("Nothing to redo")
    return enrich_with_zone_tour(preview_payload(merchant_id), merchant_id)


@tracer.capture_method
def _publish(body: dict[str, Any]) -> dict[str, Any]:
    merchant_id = _required_str(body, "merchantId")
    published = _repo(merchant_id).publish_draft(merchant_id)
    if not published:
        raise ValueError("No draft to publish")
    metrics.add_metric(name="ThemePublished", unit=MetricUnit.Count, value=1)
    return {
        "message": "Theme published to your live storefront.",
        "html": get_storefront_html(merchant_id),
        "publishedAt": published.get("publishedAt"),
        "rollbackUntil": published.get("rollbackUntil"),
    }


@tracer.capture_method
def _reset(body: dict[str, Any]) -> dict[str, Any]:
    merchant_id = _required_str(body, "merchantId")
    ConfigManager(shop_uuid=merchant_id).reset()
    return enrich_with_zone_tour(preview_payload(merchant_id), merchant_id)


@tracer.capture_method
def _screenshot(body: dict[str, Any]) -> dict[str, Any]:
    import asyncio

    from conversational_agent.screenshot_service import capture_and_upload

    merchant_id = _required_str(body, "merchantId")
    viewport = body.get("viewport") or {}
    width = int(viewport.get("width", 390))
    height = int(viewport.get("height", 900))

    html = get_storefront_html(merchant_id)
    result = asyncio.run(capture_and_upload(html, merchant_id, width, height))
    metrics.add_metric(name="ScreenshotCaptured", unit=MetricUnit.Count, value=1)
    return result


@tracer.capture_method
def _invoke_agent_runtime(payload: dict[str, Any], *, session_id: str) -> dict[str, Any]:
    arn = os.environ.get("AGENT_RUNTIME_ARN", "").strip()
    if not arn:
        raise RuntimeError("AGENT_RUNTIME_ARN is not configured")

    response = _agent_client().invoke_agent_runtime(
        agentRuntimeArn=arn,
        qualifier=os.environ.get("AGENT_RUNTIME_QUALIFIER", "live"),
        runtimeSessionId=session_id,
        payload=json.dumps(payload).encode("utf-8"),
    )
    raw_body = response["response"]
    if hasattr(raw_body, "read"):
        raw_body = raw_body.read()
    if isinstance(raw_body, bytes):
        raw_body = raw_body.decode("utf-8")
    if isinstance(raw_body, str):
        return json.loads(raw_body)
    if isinstance(raw_body, dict):
        return raw_body
    raise RuntimeError("AgentCore returned an unsupported response body")


def _agent_client():
    global _AGENT_CLIENT
    if _AGENT_CLIENT is None:
        # read_timeout must exceed the expected agent invocation time to prevent
        # socket timeouts triggering retries while the first request still runs
        # (same-session retries cause ConcurrencyException in the container).
        _AGENT_CLIENT = boto3.client(
            "bedrock-agentcore",
            region_name=os.environ.get("AWS_REGION", "eu-north-1"),
            config=botocore.config.Config(
                retries={"mode": "adaptive", "max_attempts": 3},
                tcp_keepalive=True,
                max_pool_connections=10,
                read_timeout=180,
                connect_timeout=5,
            ),
        )
    return _AGENT_CLIENT


def _repo(merchant_id: str) -> StyleRepository:
    return StyleRepository(shop_uuid=merchant_id)


def _origin_secret_matches(event: dict[str, Any]) -> bool:
    expected = _get_origin_secret()
    if not expected:
        return True
    return _headers(event).get("x-cf-origin-secret") == expected


def _get_origin_secret() -> str | None:
    global _ORIGIN_SECRET
    if _ORIGIN_SECRET is not None:
        return _ORIGIN_SECRET or None

    # Legacy: direct env var (local dev)
    direct = os.environ.get("CF_ORIGIN_SECRET")
    if direct:
        _ORIGIN_SECRET = direct
        return direct

    # Production: fetch from Secrets Manager by ARN
    secret_arn = os.environ.get("CF_ORIGIN_SECRET_ARN")
    if not secret_arn:
        _ORIGIN_SECRET = ""
        return None

    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "eu-north-1"))
    resp = client.get_secret_value(SecretId=secret_arn)
    _ORIGIN_SECRET = resp["SecretString"]
    return _ORIGIN_SECRET


def _json_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON body") from exc
    if not isinstance(body, dict):
        raise ValueError("JSON body must be an object")
    return body


def _required_str(body: dict[str, Any], key: str) -> str:
    value = str(body.get(key) or "").strip()
    if not value:
        raise ValueError(f"Missing required field: {key}")
    return value


def _path_tail(path: str, prefix: str) -> str:
    value = path[len(prefix) :].strip("/")
    if not value:
        raise LookupError("Not found")
    return value


def _method(event: dict[str, Any]) -> str:
    return str((event.get("requestContext") or {}).get("http", {}).get("method") or "").upper()


def _path(event: dict[str, Any]) -> str:
    return str(event.get("rawPath") or "/")


def _headers(event: dict[str, Any]) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}


def _json_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": _response_headers("application/json"),
        "body": json.dumps(body, default=_json_default),
        "isBase64Encoded": False,
    }


def _text_response(status_code: int, body: str) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": _response_headers("text/plain; charset=utf-8"),
        "body": body,
        "isBase64Encoded": False,
    }


def _empty_response(status_code: int) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": _response_headers("text/plain; charset=utf-8"),
        "body": "",
        "isBase64Encoded": False,
    }


# Security headers applied to every API response (OWASP LLM05 — Improper Output Handling).
# Tight CSP is safe here: this layer only serves JSON/text, never HTML.
_SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
}


def _response_headers(content_type: str) -> dict[str, str]:
    return {
        "content-type": content_type,
        "access-control-allow-origin": os.environ.get("CORS_ALLOW_ORIGIN", "*"),
        "access-control-allow-headers": "content-type,x-cf-origin-secret",
        "access-control-allow-methods": "GET,POST,OPTIONS",
        **_SECURITY_HEADERS,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
