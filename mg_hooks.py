"""Mulligan observer hooks.

Hooks are read-only here: they only annotate the trace written by the middleware.
``post_tool_call`` is authoritative for tool status (``ok`` / ``error`` / ``blocked`` /
``cancelled``) and duration, which the middleware cannot see.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import mg_state as state

logger = logging.getLogger(__name__)

OWN_TOOL_PREFIX = "mg_"

_STARTS: dict[str, float] = {}


def pre_tool_call(**kwargs: Any) -> None:
    tool_name = str(kwargs.get("tool_name") or "")
    if tool_name.startswith(OWN_TOOL_PREFIX):
        return
    tool_call_id = str(kwargs.get("tool_call_id") or "")
    if tool_call_id:
        _STARTS[tool_call_id] = time.monotonic()
        if len(_STARTS) > 1024:
            for key in list(_STARTS)[:512]:
                _STARTS.pop(key, None)


def post_tool_call(**kwargs: Any) -> None:
    tool_name = str(kwargs.get("tool_name") or "")
    if tool_name.startswith(OWN_TOOL_PREFIX):
        return
    session_id = str(kwargs.get("session_id") or "")
    replay = state.get_state(session_id)
    if replay is None:
        return
    tool_call_id = str(kwargs.get("tool_call_id") or "")
    duration = kwargs.get("duration_ms")
    if duration is None and tool_call_id in _STARTS:
        duration = int((time.monotonic() - _STARTS.pop(tool_call_id)) * 1000)
    _STARTS.pop(tool_call_id, None)
    replay.annotate_tool(
        tool_call_id,
        str(kwargs.get("status") or "ok"),
        duration,
        error_type=kwargs.get("error_type"),
        error_message=(str(kwargs.get("error_message"))[:500] if kwargs.get("error_message") else None),
    )
