"""Mulligan — record a Hermes run, rewind, edit a decision, replay, diff.

Registers six tools, three middleware kinds and two observer hooks through the public
``ctx`` API only. No core patching, no private state, stdlib only.
"""

from __future__ import annotations

import functools
import logging

from . import mg_hooks as hooks, mg_middleware as middleware, mg_schemas as schemas, mg_tools as tools

logger = logging.getLogger(__name__)

__version__ = "0.1.0"

_REQUIRED_MIDDLEWARE = ("llm_execution", "tool_execution", "tool_request")


def register(ctx) -> None:
    """Wire tools, hooks and middleware. Called once by the Hermes plugin loader."""
    for schema in schemas.ALL:
        name = schema["name"]
        handler = getattr(tools, name)
        ctx.register_tool(
            name=name,
            toolset="mulligan",
            schema=schema,
            handler=functools.partial(handler, ctx=ctx),
            description=schema["description"].split(".")[0],
        )

    try:
        ctx.register_hook("pre_tool_call", hooks.pre_tool_call)
        ctx.register_hook("post_tool_call", hooks.post_tool_call)
    except Exception as exc:  # pragma: no cover - loader surfaces this
        logger.warning("mulligan: hook registration failed: %s", exc)

    for kind in _REQUIRED_MIDDLEWARE:
        callback = {
            "llm_execution": middleware.on_llm_execution,
            "tool_execution": middleware.on_tool_execution,
            "tool_request": middleware.on_tool_request,
        }[kind]
        ctx.register_middleware(kind, callback)

    logger.debug("mulligan %s registered", __version__)
