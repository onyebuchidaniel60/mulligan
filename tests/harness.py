"""Test harness: load Mulligan through a real Hermes PluginManager.

Tests exercise the *real* dispatch path (``hermes_cli.middleware``), not a
hand-rolled imitation of it, so "zero provider calls" and "zero tool side effects"
mean what they say. Dev-only: this file is never imported by the plugin at runtime.

Run:  HERMES_SOURCE=/opt/hermes23 python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def load_hermes() -> None:
    """Make the Hermes tree importable (PYTHONPATH is preferred, this is a fallback)."""
    source = os.environ.get("HERMES_SOURCE")
    if source and source not in sys.path:
        sys.path.insert(0, source)


class HermesRun:
    """A loaded plugin inside a scratch HERMES_HOME."""

    def __init__(self):
        load_hermes()
        self.home = Path(tempfile.mkdtemp(prefix="mulligan-test-"))
        self.plugin_dir = self.home / "plugins" / "mulligan"
        self.plugin_dir.mkdir(parents=True)
        for name in ("__init__.py", "mg_state.py", "mg_middleware.py", "mg_hooks.py", "mg_schemas.py", "mg_tools.py", "plugin.yaml"):
            shutil.copy2(PLUGIN_ROOT / name, self.plugin_dir / name)
        (self.home / "config.yaml").write_text("plugins:\n  enabled: [mulligan]\n", encoding="utf-8")
        self._old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = str(self.home)

        from hermes_cli import plugins as plugins_mod
        from hermes_cli.plugins import PluginManager

        self.manager = PluginManager()
        self.manager.discover_and_load()
        self._plugins_mod = plugins_mod
        self._old_getter = plugins_mod.get_plugin_manager
        plugins_mod.get_plugin_manager = lambda: self.manager

        entry = self.manager._plugins["mulligan"]
        self.module = entry.module
        assert self.module is not None, f"plugin failed to load: {entry}"
        self.state = self.module.mg_state
        self.tools = self.module.mg_tools

        # Per-test isolation of module state.
        self.state._SESSIONS.clear()
        self.state.clear_pending()
        self.state._OBJECTS.clear()
        self.state._OBJECTS_ORDER.clear()

        from hermes_cli.middleware import (
            run_llm_execution_middleware,
            run_tool_execution_middleware,
        )

        self.run_llm = run_llm_execution_middleware
        self.run_tool = run_tool_execution_middleware

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self._plugins_mod.get_plugin_manager = self._old_getter
        if self._old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self._old_home
        shutil.rmtree(self.home, ignore_errors=True)

    def __enter__(self) -> "HermesRun":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- provider / tool doubles -------------------------------------------

    def llm(self, session_id: str, request: dict, response: Any, counter: list | None = None) -> Any:
        """One provider call through the real execution chain."""

        def next_call(payload):
            if counter is not None:
                counter.append(payload)
            return response

        return self.run_llm(
            request,
            next_call,
            original_request=request,
            session_id=session_id,
            task_id=session_id,
            turn_id="turn-1",
            api_request_id="api-1",
            provider="test",
            model="test-model",
            api_mode="chat_completions",
        )

    def tool(
        self,
        session_id: str,
        tool_name: str,
        args: dict,
        result: Any,
        tool_call_id: str,
        counter: list | None = None,
    ) -> Any:
        """One tool execution through the real request + execution chain.

        Mirrors ``agent/tool_executor.py``: ``tool_request`` runs first and its payload is
        what execution middleware (and the base dispatcher) see.
        """
        from hermes_cli.middleware import apply_tool_request_middleware

        applied = apply_tool_request_middleware(
            tool_name,
            args,
            session_id=session_id,
            task_id=session_id,
            tool_call_id=tool_call_id,
            turn_id="turn-1",
            api_request_id="api-1",
        )
        effective = applied.payload if isinstance(applied.payload, dict) else args

        def next_call(payload):
            if counter is not None:
                counter.append((tool_name, payload))
            return result

        from hermes_cli.plugins import invoke_hook

        invoke_hook(
            "pre_tool_call",
            tool_name=tool_name,
            args=effective,
            task_id=session_id,
            session_id=session_id,
            tool_call_id=tool_call_id,
            turn_id="turn-1",
            api_request_id="api-1",
        )
        value = self.run_tool(
            tool_name,
            effective,
            next_call,
            original_args=args,
            session_id=session_id,
            task_id=session_id,
            tool_call_id=tool_call_id,
            turn_id="turn-1",
            api_request_id="api-1",
            middleware_trace=list(applied.trace),
        )
        status = "ok"
        try:
            parsed = json.loads(value) if isinstance(value, str) else value
            if isinstance(parsed, dict) and (parsed.get("ok") is False or parsed.get("error")):
                status = "error"
        except (TypeError, ValueError):
            pass
        invoke_hook(
            "post_tool_call",
            tool_name=tool_name,
            args=effective,
            result=value,
            task_id=session_id,
            session_id=session_id,
            tool_call_id=tool_call_id,
            turn_id="turn-1",
            api_request_id="api-1",
            status=status,
            duration_ms=1,
        )
        return value

    # -- tools --------------------------------------------------------------

    def call(self, name: str, args: dict, session_id: str = "sess-parent") -> dict:
        handler = getattr(self.tools, name, None)
        if handler is None:  # pragma: no cover - test wiring bug
            raise AssertionError(f"no such tool {name}")
        ctx = _FakeCtx(self)
        return json.loads(handler(args, ctx=ctx, session_id=session_id))


class _FakeCtx:
    """Minimal ctx for handler-level tests (subagent lifecycle is faked per test)."""

    def __init__(self, run: HermesRun, service: Any = None):
        self._run = run
        self.subagent_lifecycle = service


# --------------------------------------------------------------------- doubles


def response(content: str | None = None, tool_calls: list | None = None, usage: dict | None = None) -> Any:
    """An OpenAI-shaped response object with attribute access."""
    calls = [
        SimpleNamespace(
            id=call["id"],
            type="function",
            function=SimpleNamespace(name=call["name"], arguments=json.dumps(call["arguments"])),
        )
        for call in (tool_calls or [])
    ]
    message = SimpleNamespace(role="assistant", content=content, tool_calls=calls or None)
    return SimpleNamespace(
        id="chatcmpl-test",
        model="test-model",
        choices=[SimpleNamespace(index=0, message=message, finish_reason="tool_calls" if calls else "stop")],
        usage=SimpleNamespace(**(usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})),
    )


def tool_result(ok: bool, **payload: Any) -> str:
    return json.dumps({"ok": ok, **payload})
