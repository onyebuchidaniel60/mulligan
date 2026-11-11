"""Mulligan middleware: record every step, serve recorded steps during replay.

Ordering facts this module relies on (Hermes developer guide, "Middleware →
Execution Order → Tool Calls"):

    tool_request  -> availability checks / guardrails / approvals
    tool_execution -> post_tool_call hooks

So serving in ``tool_execution`` happens *after* approvals (it cannot suppress an
approval prompt), and a branch edit applied in ``tool_request`` is exactly what the
guardrails and the human approve.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import mg_state as state

logger = logging.getLogger(__name__)

OWN_TOOL_PREFIX = "mg_"


def _session(kwargs: dict) -> str:
    return str(kwargs.get("session_id") or "")


def _is_own_tool(tool_name: str | None) -> bool:
    return bool(tool_name) and str(tool_name).startswith(OWN_TOOL_PREFIX)


def _context(kwargs: dict) -> dict:
    return {
        "model": kwargs.get("model"),
        "provider": kwargs.get("provider"),
        "tool_call_id": kwargs.get("tool_call_id"),
    }


# --------------------------------------------------------------------- llm calls


def on_llm_execution(**kwargs: Any) -> Any:
    """Serve a recorded provider response, or call the provider once and record it."""
    request = kwargs.get("request")
    next_call = kwargs["next_call"]
    session_id = _session(kwargs)

    replay = state.get_state(session_id)
    if replay is None:
        replay = state.bind_from_request(request, session_id)

    if replay is not None and replay.mode == state.SERVING:
        step = replay.take_llm()
        if step is not None:
            served = _serve_llm(replay, step)
            if served is not _MISSING:
                logger.debug("mulligan: served llm step %s for %s", step.get("seq"), session_id)
                return served
            # Snapshot unusable: fall through to a live call rather than lie.
            logger.warning("mulligan: llm step %s has no replayable payload; going live", step.get("seq"))
        elif replay.mode == state.DONE:
            return _terminal_response(replay)

    response = next_call(request)

    recorder = state.get_state(session_id)
    if recorder is None:
        recorder = state.get_or_create(session_id, state.LIVE)
        if recorder.goal is None:
            recorder.goal = state.goal_from_request(request)
    if recorder.mode in (state.LIVE, state.ARMED, state.IDLE):
        recorder.live_llm += 1
        recorder.record_llm(request, response, _context(kwargs))
    return response


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover
        return "<missing>"


_MISSING = _Missing()


def _serve_llm(replay: state.ReplayState, step: dict) -> Any:
    seq = int(step.get("seq", -1))
    live = state.recall_object(replay.serving_run or "", seq)
    if live is not None:
        return live
    snapshot = step.get("response")
    if snapshot is None:
        return _MISSING
    return state._namespace(snapshot)  # attribute-access shim, same shape as recorded


def _terminal_response(replay: state.ReplayState) -> Any:
    """Safety net: the trace is exhausted and no branch was requested.

    Reaching this path means the child asked for another completion after the
    recorded run had already finished. Returning a synthetic end-of-turn response
    keeps the exact-reproduction promise (zero provider calls) and records the
    deviation honestly.
    """
    seq = replay.seq
    if replay.writer is not None:
        try:
            replay.writer.append(
                {
                    "type": "synthetic",
                    "seq": seq,
                    "session_id": replay.session_id,
                    "reason": "replay_complete_no_further_steps",
                    "ts": time.time(),
                }
            )
        except OSError:  # pragma: no cover - defensive
            pass
    content = (
        f"Mulligan replay complete: {len(replay.steps)} recorded steps reproduced "
        "with no provider calls."
    )
    return state._namespace(
        {
            "id": "mulligan-replay-end",
            "model": "mulligan",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content, "tool_calls": []},
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    )


# -------------------------------------------------------------------- tool calls


def on_tool_request(**kwargs: Any) -> dict | None:
    """Apply a branch edit before approvals see the call (so the human approves the edit)."""
    tool_name = str(kwargs.get("tool_name") or "")
    if _is_own_tool(tool_name):
        return None
    replay = state.get_state(_session(kwargs))
    if replay is None or not replay.edit:
        return None
    edit = replay.edit
    if int(edit.get("seq", -1)) != replay.cursor:
        return None
    if edit.get("tool") and edit["tool"] != tool_name:
        return None
    new_args = edit.get("args") or {}
    if new_args == kwargs.get("args"):
        return None
    return {
        "args": dict(new_args),
        "source": "mulligan",
        "reason": f"branch edit at step {edit.get('seq')}",
    }


def on_tool_execution(**kwargs: Any) -> Any:
    """Serve a recorded tool result, or execute once and record it."""
    tool_name = str(kwargs.get("tool_name") or "")
    args = kwargs.get("args")
    next_call = kwargs["next_call"]
    session_id = _session(kwargs)
    context = _context(kwargs)

    if _is_own_tool(tool_name):
        return next_call(args)

    replay = state.get_state(session_id)
    if replay is not None and replay.mode == state.SERVING:
        step = replay.take_tool(tool_name, str(context.get("tool_call_id") or ""))
        if step is not None:
            seq = int(step.get("seq", -1))
            live = state.recall_object(replay.serving_run or "", seq)
            if live is not None:
                return live
            if "result" in step:
                return step["result"]
            logger.warning("mulligan: tool step %s has no replayable payload; executing live", seq)

    result = next_call(args)
    recorder = state.get_state(session_id)
    if recorder is None:
        recorder = state.get_or_create(session_id, state.LIVE)
    if recorder.mode in (state.LIVE, state.ARMED, state.IDLE):
        recorder.live_tool += 1
        recorder.record_tool(tool_name, args, result, context)
    return result
