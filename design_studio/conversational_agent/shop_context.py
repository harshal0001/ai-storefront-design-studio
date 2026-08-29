"""Per-request merchant scope for agent tools (Strands has no built-in shop id).

Uses ``contextvars`` so ``get_shop_uuid()`` works inside tool callbacks without threading
``merchantId`` through every function. Set via ``shop_context(merchant_id)`` in
``server.py`` / ``runtime.py`` around each agent invocation.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from .config_manager import DEFAULT_SHOP_UUID

_shop_uuid: ContextVar[str] = ContextVar("shop_uuid", default=DEFAULT_SHOP_UUID)


def get_shop_uuid() -> str:
    """Shop partition key for the current agent invocation (PK=MERCHANT#<uuid>)."""
    return _shop_uuid.get()


@contextmanager
def shop_context(shop_uuid: str) -> Iterator[None]:
    """Bind tools to a merchant for the duration of an HTTP / AgentCore request."""
    token = _shop_uuid.set(shop_uuid)
    try:
        yield
    finally:
        _shop_uuid.reset(token)
