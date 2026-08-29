"""In-memory chat histories for the dev server (not used in AgentCore production).

Append-only log per ``merchant_id`` for UI display. **Not yet wired** into Strands
agent invocations — each ``agent()`` call still receives a single message string.
See IMPLEMENTATION_PLAN task 3.26.
"""

from __future__ import annotations

from typing import Any

_histories: dict[str, list[dict[str, Any]]] = {}


def get_history(merchant_id: str) -> list[dict[str, Any]]:
    return _histories.setdefault(merchant_id, [])


def append_exchange(merchant_id: str, user_message: str, assistant_message: str) -> None:
    history = get_history(merchant_id)
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": assistant_message})


def clear_history(merchant_id: str) -> None:
    _histories.pop(merchant_id, None)


def set_history(merchant_id: str, messages: list[dict[str, Any]]) -> None:
    _histories[merchant_id] = messages
