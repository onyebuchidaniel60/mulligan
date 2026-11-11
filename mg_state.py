"""Mulligan trace store and replay registry.

Standard library only. The only paths this module ever writes are under
``$HERMES_HOME/replay-traces/`` (or ``MULLIGAN_TRACE_DIR`` when it resolves inside
``HERMES_HOME``). Traces are append-only JSONL, version 1.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TRACE_VERSION = 1
MAX_FIELD_CHARS = 2_000_000
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# Mode names used by ReplayState.mode.
IDLE = "idle"
ARMED = "armed"
SERVING = "serving"
LIVE = "live"
DONE = "done"


class TraceError(Exception):
    """Typed trace-store failure (surfaced to the model as JSON, never raised)."""


# --------------------------------------------------------------------------- paths


def hermes_home() -> Path:
    """Active Hermes home. Public API first, environment fallback second."""
    for module_name, attr in (("hermes_constants", "get_hermes_home"), ("hermes_cli.config", "get_hermes_home")):
        try:
            module = __import__(module_name, fromlist=[attr])
            getter = getattr(module, attr)
            return Path(getter())
        except Exception:
            continue
    override = os.environ.get("HERMES_HOME")
    return Path(override) if override else Path.home() / ".hermes"


def trace_root() -> tuple[Path | None, str | None]:
    """Resolve the trace directory, refusing anything outside ``HERMES_HOME``."""
    home = hermes_home()
    override = os.environ.get("MULLIGAN_TRACE_DIR")
    candidate = Path(override).expanduser() if override else home / "replay-traces"
    try:
        resolved = candidate.resolve()
        base = home.resolve()
    except OSError as exc:  # pragma: no cover - defensive
        return None, f"unresolvable_trace_dir: {exc}"
    if resolved != base and base not in resolved.parents:
        return None, "trace_dir_outside_hermes_home"
    return resolved, None


def ensure_root() -> Path:
    root, err = trace_root()
    if root is None:
        raise TraceError(err or "trace_dir_unavailable")
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TraceError(f"trace_dir_unwritable: {exc}") from exc
    return root


def validate_run_id(run_id: str) -> str:
    text = (run_id or "").strip()
    if not _RUN_ID_RE.match(text):
        raise TraceError("invalid_run_id")
    return text


def run_path(run_id: str) -> Path:
    root = ensure_root()
    path = (root / f"{validate_run_id(run_id)}.jsonl").resolve()
    if path.parent != root:
        raise TraceError("invalid_run_id")
    return path


def new_run_id(prefix: str = "r") -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    return f"{prefix}_{stamp}_{secrets.token_hex(2)}"


def new_nonce() -> str:
    return f"MULLIGAN-{secrets.token_hex(8)}"


# ------------------------------------------------------------------- JSON coercion


def jsonable(value: Any, _depth: int = 0) -> Any:
    """Coerce arbitrary provider/tool payloads into JSON-safe data.

    Prefers the SDK/pydantic ``model_dump`` path so a recorded response keeps every
    field the provider returned. Unknown objects fall back to ``__dict__`` and then
    ``repr`` rather than aborting the record.
    """
    if _depth > 24:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item, _depth + 1) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item, _depth + 1) for key, item in value.items()}
    for attr in ("model_dump", "to_dict", "dict"):
        fn = getattr(value, attr, None)
        if callable(fn):
            try:
                dumped = fn()
            except Exception:
                continue
            if dumped is not value:
                return jsonable(dumped, _depth + 1)
    data = getattr(value, "__dict__", None)
    if isinstance(data, dict):
        return {k: jsonable(v, _depth + 1) for k, v in data.items() if not k.startswith("_")}
    return repr(value)


def digest(value: Any) -> str:
    try:
        canon = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        canon = repr(value)
    return hashlib.sha256(canon.encode("utf-8", "replace")).hexdigest()


def clip(text: Any, limit: int = MAX_FIELD_CHARS) -> tuple[Any, bool]:
    """Bound a stored string. Returns ``(value, truncated)``."""
    if not isinstance(text, str) or len(text) <= limit:
        return text, False
    return text[:limit], True


# ------------------------------------------------------------------ trace reading


def read_trace(run_id: str) -> list[dict]:
    path = run_path(run_id)
    if not path.is_file():
        raise TraceError("unknown_run_id")
    records: list[dict] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("mulligan: skipping malformed trace line in %s", path.name)
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def load_header(records: list[dict]) -> dict:
    for record in records:
        if record.get("type") == "header":
            return record
    return {}


def load_steps(records: list[dict]) -> list[dict]:
    """Ordered llm_call / tool_call steps (status annotations are folded in)."""
    steps = [r for r in records if r.get("type") in ("llm_call", "tool_call")]
    steps.sort(key=lambda r: int(r.get("seq", 0)))
    return steps


def annotate(records: list[dict]) -> list[dict]:
    """Fold ``tool_status`` / ``branch`` annotations into the step list."""
    status = {}
    for record in records:
        if record.get("type") == "tool_status" and "seq" in record:
            status[int(record["seq"])] = record
    view = []
    for step in load_steps(records):
        item = dict(step)
        note = status.get(int(step.get("seq", -1)))
        if note:
            item["status"] = note.get("status") or item.get("status")
            item["duration_ms"] = note.get("duration_ms")
            item["error_type"] = note.get("error_type")
        elif step.get("type") == "tool_call":
            # Fallback when no post_tool_call annotation survived (older trace, or a
            # tool that never reached the hook because it was blocked).
            item["status"] = _result_status(step.get("result"))
        view.append(item)
    return view


def _result_status(result: Any) -> str:
    payload = result
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return "ok"
    if isinstance(payload, dict):
        if payload.get("ok") is False or payload.get("error"):
            return "error"
    return "ok"


def list_runs() -> list[dict]:
    root, err = trace_root()
    if root is None:
        raise TraceError(err or "trace_dir_unavailable")
    if not root.is_dir():
        return []
    runs = []
    for path in sorted(root.glob("*.jsonl")):
        try:
            records = read_trace(path.stem)
        except TraceError:
            continue
        header = load_header(records)
        steps = load_steps(records)
        runs.append(
            {
                "run_id": path.stem,
                "created": header.get("created") or path.stat().st_mtime,
                "steps": len(steps),
                "session_id": header.get("session_id"),
                "branch_of": header.get("branch_of"),
                "branch_at": header.get("branch_at"),
                "goal": header.get("goal"),
                "bytes": path.stat().st_size,
            }
        )
    runs.sort(key=lambda r: r["created"] or 0)
    return runs


# ------------------------------------------------------------------- trace writing


class TraceWriter:
    """Append-only JSONL writer. Never truncates, never rewrites."""

    def __init__(self, run_id: str, header: dict):
        self.run_id = run_id
        self.path = run_path(run_id)
        self._lock = threading.Lock()
        fresh = not self.path.exists()
        with self.path.open("a", encoding="utf-8") as fh:
            if fresh:
                fh.write(json.dumps({**header, "v": TRACE_VERSION, "type": "header"}, ensure_ascii=False) + "\n")

    def append(self, record: dict) -> None:
        line = json.dumps({**record, "v": TRACE_VERSION}, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")


# --------------------------------------------------------------------- replay state

# Exact provider/tool objects for replays that happen in the same process as the
# recording (the normal case: replay runs in a child session of the same Hermes).
_OBJECTS: dict[tuple[str, int], Any] = {}
_OBJECTS_ORDER: list[tuple[str, int]] = []
_OBJECTS_LIMIT = 512


def remember_object(run_id: str, seq: int, obj: Any) -> None:
    key = (run_id, seq)
    _OBJECTS[key] = obj
    _OBJECTS_ORDER.append(key)
    while len(_OBJECTS_ORDER) > _OBJECTS_LIMIT:
        _OBJECTS.pop(_OBJECTS_ORDER.pop(0), None)


def recall_object(run_id: str, seq: int) -> Any:
    return _OBJECTS.get((run_id, seq))


def _namespace(value: Any) -> Any:
    """Rebuild an attribute-access object tree from a recorded JSON snapshot."""
    if isinstance(value, dict):
        return _Namespace({k: _namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_namespace(v) for v in value]
    return value


class _Namespace:
    """Minimal attribute-access shim used only when the live object is gone."""

    def __init__(self, data: dict):
        self.__dict__.update(data)

    def get(self, key: str, default: Any = None) -> Any:
        return self.__dict__.get(key, default)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"_Namespace({sorted(self.__dict__)})"


@dataclass
class ReplayState:
    """Per-session replay bookkeeping. One instance per session_id, never shared."""

    session_id: str
    mode: str = LIVE
    # Recording
    run_id: str | None = None
    writer: TraceWriter | None = None
    seq: int = 0
    goal: str | None = None
    recorded_tools: dict[str, int] = field(default_factory=dict)
    # Serving
    serving_run: str | None = None
    steps: list[dict] = field(default_factory=list)
    cursor: int = 0
    served_seqs: set[int] = field(default_factory=set)
    branch_at: int | None = None
    edit: dict | None = None
    parent_session_id: str | None = None
    # Counters / diagnostics
    served_llm: int = 0
    served_tool: int = 0
    live_llm: int = 0
    live_tool: int = 0
    desync: dict | None = None
    error: str | None = None
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # -- recording ---------------------------------------------------------

    def _start_recording(self, *, branch_of: str | None = None, branch_at: int | None = None) -> None:
        if self.writer is not None:
            return
        run_id = new_run_id("b" if branch_of else "r")
        header = {
            "run_id": run_id,
            "created": time.time(),
            "session_id": self.session_id,
            "parent_session_id": self.parent_session_id,
            "goal": self.goal,
            "branch_of": branch_of,
            "branch_at": branch_at,
        }
        try:
            self.writer = TraceWriter(run_id, header)
            self.run_id = run_id
            if branch_at is not None:
                self.seq = int(branch_at)
        except (TraceError, OSError) as exc:
            self.error = f"recording_disabled: {exc}"
            self.writer = None

    def record_llm(self, request: Any, response: Any, context: dict) -> None:
        if self.error:
            return
        self._start_recording()
        if self.writer is None:
            return
        assistant, usage = summarize_response(response)
        record = {
            "type": "llm_call",
            "seq": self.seq,
            "session_id": self.session_id,
            "ts": time.time(),
            "model": context.get("model"),
            "provider": context.get("provider"),
            "message_count": _message_count(request),
            "request_digest": digest(_messages(request)),
            "response": jsonable(response),
            "assistant": assistant,
            "usage": usage,
        }
        try:
            self.writer.append(record)
        except OSError as exc:
            self.error = f"trace_write_failed: {exc}"
            return
        remember_object(self.run_id or "", self.seq, response)
        self.seq += 1

    def record_tool(self, tool_name: str, args: Any, result: Any, context: dict) -> None:
        if self.error:
            return
        self._start_recording()
        if self.writer is None:
            return
        payload, truncated = clip(result)
        record = {
            "type": "tool_call",
            "seq": self.seq,
            "session_id": self.session_id,
            "ts": time.time(),
            "tool_name": tool_name,
            "tool_call_id": context.get("tool_call_id") or "",
            "args": jsonable(args),
            "result": jsonable(payload),
            "truncated": truncated,
            "args_digest": digest(args),
        }
        try:
            self.writer.append(record)
        except OSError as exc:
            self.error = f"trace_write_failed: {exc}"
            return
        if context.get("tool_call_id"):
            self.recorded_tools[str(context["tool_call_id"])] = self.seq
        remember_object(self.run_id or "", self.seq, result)
        self.seq += 1

    def annotate_tool(self, tool_call_id: str, status: str, duration_ms: Any, **extra: Any) -> None:
        seq = self.recorded_tools.pop(str(tool_call_id or ""), None)
        if seq is None or self.writer is None:
            return
        record = {
            "type": "tool_status",
            "seq": seq,
            "session_id": self.session_id,
            "status": status,
            "duration_ms": duration_ms,
            **{k: v for k, v in extra.items() if v is not None},
        }
        try:
            self.writer.append(record)
        except OSError:
            pass

    # -- serving -----------------------------------------------------------

    def to_live(self) -> None:
        """Branch point reached: stop serving and record the rest of the run."""
        if self.mode != SERVING:
            return
        self.mode = LIVE
        self._start_recording(branch_of=self.serving_run, branch_at=self.cursor)

    def take_llm(self) -> dict | None:
        """Return the recorded llm step to serve, or None to go live."""
        with self.lock:
            if self.mode != SERVING:
                return None
            if self.branch_at is not None and self.cursor >= self.branch_at:
                self.to_live()
                return None
            if self.cursor >= len(self.steps):
                self.mode = DONE
                return None
            step = self.steps[self.cursor]
            if step.get("type") != "llm_call":
                self._desync("llm_call", str(step.get("type")), step)
                return None
            self.cursor += 1
            self.served_llm += 1
            return step

    def take_tool(self, tool_name: str, tool_call_id: str) -> dict | None:
        """Return the recorded tool step to serve, or None to execute live.

        Matching is by ``tool_call_id`` first, so parallel tool calls may arrive in any
        order (they run on a thread pool). The cursor advances only past steps that
        have actually been served.
        """
        with self.lock:
            if self.mode != SERVING:
                return None
            if self.branch_at is not None and self.cursor >= self.branch_at:
                self.to_live()
                return None
            index = self._find_tool_step(tool_name, tool_call_id)
            if index is None:
                if self.cursor >= len(self.steps):
                    self.mode = DONE
                else:
                    self._desync(tool_name, str(self.steps[self.cursor].get("tool_name")), self.steps[self.cursor])
                return None
            step = self.steps[index]
            self.served_seqs.add(index)
            self._advance()
            self.served_tool += 1
            return step

    def _advance(self) -> None:
        while self.cursor < len(self.steps) and self.cursor in self.served_seqs:
            self.cursor += 1

    def _find_tool_step(self, tool_name: str, tool_call_id: str) -> int | None:
        while self.cursor < len(self.steps) and self.cursor in self.served_seqs:
            self.cursor += 1
        if self.cursor >= len(self.steps):
            return None
        if tool_call_id:
            for index in range(self.cursor, len(self.steps)):
                step = self.steps[index]
                if index in self.served_seqs:
                    continue
                if step.get("type") == "tool_call" and step.get("tool_call_id") == tool_call_id:
                    return index
        step = self.steps[self.cursor]
        if step.get("type") == "tool_call" and step.get("tool_name") == tool_name:
            return self.cursor
        return None

    def _desync(self, expected: str, actual: str, step: dict) -> None:
        if self.desync is None:
            self.desync = {
                "seq": self.cursor,
                "expected": expected,
                "actual": actual,
                "tool_name": step.get("tool_name"),
            }
            logger.warning("mulligan: desync at seq %s (expected %s, saw %s) — failing open to live",
                           self.cursor, expected, actual)
            if self.writer is not None:
                try:
                    self.writer.append(
                        {
                            "type": "desync",
                            "seq": self.cursor,
                            "expected": expected,
                            "actual": actual,
                            "tool_name": step.get("tool_name"),
                        }
                    )
                except OSError:  # pragma: no cover - defensive
                    pass
        self.mode = LIVE
        self._start_recording(branch_of=self.serving_run, branch_at=self.cursor)

    # -- rendering ---------------------------------------------------------

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "serving_run": self.serving_run,
            "mode": self.mode,
            "cursor": self.cursor,
            "steps": len(self.steps),
            "branch_at": self.branch_at,
            "served_llm": self.served_llm,
            "served_tool": self.served_tool,
            "live_llm": self.live_llm,
            "live_tool": self.live_tool,
            "desync": self.desync,
            "error": self.error,
        }


# ------------------------------------------------------------------------- registry

_SESSIONS: dict[str, ReplayState] = {}
_SESSIONS_LOCK = threading.RLock()


def get_state(session_id: str) -> ReplayState | None:
    with _SESSIONS_LOCK:
        return _SESSIONS.get(session_id or "")


def get_or_create(session_id: str, mode: str = LIVE) -> ReplayState:
    with _SESSIONS_LOCK:
        state = _SESSIONS.get(session_id)
        if state is None:
            state = ReplayState(session_id=session_id, mode=mode)
            _SESSIONS[session_id] = state
        return state


def drop_state(session_id: str) -> None:
    with _SESSIONS_LOCK:
        _SESSIONS.pop(session_id, None)


def find_child_state(parent_session_id: str, serving_run: str) -> ReplayState | None:
    """The replay state created for the child session mg_play just launched."""
    with _SESSIONS_LOCK:
        for session_id, candidate in _SESSIONS.items():
            if session_id == parent_session_id:
                continue
            if candidate.parent_session_id != parent_session_id:
                continue
            if candidate.serving_run != serving_run:
                continue
            return candidate
    return None


@dataclass
class PendingReplay:
    """A replay armed by mg_rewind, waiting for its child session to appear."""

    parent_session_id: str
    run_id: str
    nonce: str
    steps: list[dict]
    branch_at: int
    edit: dict | None = None
    created: float = field(default_factory=time.time)
    consumed: bool = False

    def consume(self, session_id: str) -> ReplayState:
        self.consumed = True
        state = ReplayState(
            session_id=session_id,
            mode=SERVING,
            serving_run=self.run_id,
            steps=self.steps,
            cursor=0,
            branch_at=self.branch_at,
            edit=self.edit,
            parent_session_id=self.parent_session_id,
        )
        with _SESSIONS_LOCK:
            _SESSIONS[session_id] = state
        return state


_PENDING: PendingReplay | None = None
_PENDING_LOCK = threading.RLock()


def arm(pending: PendingReplay) -> None:
    global _PENDING
    with _PENDING_LOCK:
        _PENDING = pending


def pending() -> PendingReplay | None:
    with _PENDING_LOCK:
        return _PENDING


def clear_pending() -> None:
    global _PENDING
    with _PENDING_LOCK:
        _PENDING = None


def bind_from_request(request: Any, session_id: str) -> ReplayState | None:
    """Bind an armed replay to the child session whose request carries its nonce."""
    with _PENDING_LOCK:
        pending_replay = _PENDING
        if pending_replay is None or pending_replay.consumed:
            return None
        if session_id and session_id == pending_replay.parent_session_id:
            return None
        if not _contains(request, pending_replay.nonce):
            return None
        clear_pending()
        logger.info("mulligan: replay %s bound to session %s", pending_replay.run_id, session_id)
        return pending_replay.consume(session_id)


def _contains(value: Any, needle: str) -> bool:
    try:
        blob = json.dumps(jsonable(value), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        blob = repr(value)
    return needle in blob


# ------------------------------------------------------------------ response shape


def summarize_response(response: Any) -> tuple[dict | None, dict | None]:
    """Extract the assistant message and usage from a provider response."""
    assistant = None
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if choices:
        message = getattr(choices[0], "message", None)
        if message is None and isinstance(choices[0], dict):
            message = choices[0].get("message")
        if message is not None:
            content = getattr(message, "content", None)
            raw_calls = getattr(message, "tool_calls", None)
            if raw_calls is None and isinstance(message, dict):
                content = message.get("content")
                raw_calls = message.get("tool_calls")
            calls = []
            for call in raw_calls or []:
                fn = getattr(call, "function", None) or (call.get("function") if isinstance(call, dict) else None)
                calls.append(
                    {
                        "id": getattr(call, "id", None) or (call.get("id") if isinstance(call, dict) else None),
                        "name": getattr(fn, "name", None) or (fn.get("name") if isinstance(fn, dict) else None),
                        "arguments": getattr(fn, "arguments", None) or (fn.get("arguments") if isinstance(fn, dict) else None),
                    }
                )
            assistant = {"content": content, "tool_calls": calls}
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    return assistant, jsonable(usage) if usage is not None else None


def _messages(request: Any) -> Any:
    if isinstance(request, dict):
        return request.get("messages", request.get("input"))
    return None


def _message_count(request: Any) -> int | None:
    messages = _messages(request)
    return len(messages) if isinstance(messages, list) else None


def goal_from_request(request: Any) -> str | None:
    """Best-effort original user turn, used as the child's goal."""
    messages = _messages(request)
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, list):
            content = " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
        text = str(content or "").strip()
        if text:
            return text[:4000]
    return None
