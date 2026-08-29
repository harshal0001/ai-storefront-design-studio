"""Undo/redo API behavior."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from conversational_agent import server
from conversational_agent.server import MerchantRequest
from conversational_agent.style_tokens import StyleTokens


def test_undo_returns_400_when_stack_empty(monkeypatch):
    repo = MagicMock()
    repo.enabled = True
    repo.undo.return_value = None
    monkeypatch.setattr(server, "_repo", lambda merchant_id: repo)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.undo(MerchantRequest(merchantId="shop-1")))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Nothing to undo"
    repo.undo.assert_called_once_with("shop-1")


def test_redo_returns_400_when_stack_empty(monkeypatch):
    repo = MagicMock()
    repo.enabled = True
    repo.redo.return_value = None
    monkeypatch.setattr(server, "_repo", lambda merchant_id: repo)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.redo(MerchantRequest(merchantId="shop-1")))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Nothing to redo"
    repo.redo.assert_called_once_with("shop-1")


def test_undo_returns_preview_when_operation_succeeds(monkeypatch):
    repo = MagicMock()
    repo.enabled = True
    repo.undo.return_value = StyleTokens()
    monkeypatch.setattr(server, "_repo", lambda merchant_id: repo)
    monkeypatch.setattr(
        server,
        "preview_payload",
        lambda merchant_id: {"merchantId": merchant_id, "html": "<html></html>"},
    )

    response = asyncio.run(server.undo(MerchantRequest(merchantId="shop-1")))

    assert response == {"merchantId": "shop-1", "html": "<html></html>"}
