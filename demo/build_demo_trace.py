#!/usr/bin/env python3
"""Write the deterministic Mulligan demo trace.

This is a *fixture*: it writes a recorded run in the exact JSONL v1 format the plugin
produces, with no model and no tool side effects. It exists so the demo's inspect /
rewind / diff beats are reproducible, and so a replay has a deterministic prefix that
can be served with zero provider calls.

Usage:
    HERMES_HOME=/tmp/mulligan-demo python3 demo/build_demo_trace.py
    # -> $HERMES_HOME/replay-traces/r_demo_deploy.jsonl

The run: "deploy using config/prod.yaml" — the agent reads the deployment files and then
fails at step 13 on a typo'd config path (config/prod.yml). mg_edit fixes it to
config/prod.yaml.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mg_state import TraceWriter, digest  # noqa: E402  (plugin module, stdlib only)

RUN_ID = "r_demo_deploy"
GOAL = "Deploy the service using the production config at config/prod.yaml and report the result."


def _response(index: int, *, content: str | None = None, calls: list | None = None) -> dict:
    tool_calls = [
        {
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)},
        }
        for call_id, name, args in (calls or [])
    ]
    return {
        "id": f"chatcmpl-demo-{index}",
        "object": "chat.completion",
        "model": "demo-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls" if tool_calls else "stop",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls or None,
                },
            }
        ],
        "usage": {"prompt_tokens": 900 + index * 120, "completion_tokens": 40, "total_tokens": 940 + index * 120},
    }


def _assistant(response: dict) -> dict:
    message = response["choices"][0]["message"]
    return {
        "content": message.get("content"),
        "tool_calls": [
            {
                "id": call["id"],
                "name": call["function"]["name"],
                "arguments": call["function"]["arguments"],
            }
            for call in (message.get("tool_calls") or [])
        ],
    }


PLAN = [
    ("llm", "Find the deployment files before touching anything.",
     [("call_00", "search_files", {"pattern": "*", "target": "files", "path": "."})]),
    ("tool", "search_files", {"pattern": "*", "target": "files", "path": "."},
     {"ok": True, "total_count": 4, "files": ["README.md", "deploy.sh", "config/base.yaml", "config/prod.yaml"]}, "ok"),
    ("llm", None, [("call_01", "read_file", {"path": "README.md"})]),
    ("tool", "read_file", {"path": "README.md"},
     {"ok": True, "content": "# demo-service\nDeploy with ./deploy.sh <config path>\n"}, "ok"),
    ("llm", None, [("call_02", "read_file", {"path": "deploy.sh"})]),
    ("tool", "read_file", {"path": "deploy.sh"},
     {"ok": True, "content": "#!/bin/sh\nset -eu\nCONFIG=\"$1\"\npython -m demo_service --config \"$CONFIG\"\n"}, "ok"),
    ("llm", None, [("call_03", "search_files", {"pattern": "CONFIG", "target": "content", "path": "deploy.sh"})]),
    ("tool", "search_files", {"pattern": "CONFIG", "target": "content", "path": "deploy.sh"},
     {"ok": True, "matches": [{"line": 3, "text": "CONFIG=\"$1\""}]}, "ok"),
    ("llm", None, [("call_04", "read_file", {"path": "config/base.yaml"})]),
    ("tool", "read_file", {"path": "config/base.yaml"},
     {"ok": True, "content": "service: demo\nreplicas: 2\nregion: us-east-1\n"}, "ok"),
    ("llm", None, [("call_05", "read_file", {"path": "config/prod.yaml"})]),
    ("tool", "read_file", {"path": "config/prod.yaml"},
     {"ok": True, "content": "service: demo\nreplicas: 4\nregion: us-east-1\n"}, "ok"),
    ("llm", None, [("call_06", "read_file", {"path": "config/prod.yml"})]),
    ("tool", "read_file", {"path": "config/prod.yml"},
     {"ok": False, "error": "FileNotFoundError: config/prod.yml"}, "error"),
]

FINAL = (14, "I could not read config/prod.yml, so I stopped before deploying.")


def build() -> Path:
    writer = TraceWriter(
        RUN_ID,
        {
            "run_id": RUN_ID,
            "created": 1762900000.0,
            "session_id": "demo-session",
            "parent_session_id": None,
            "goal": GOAL,
            "branch_of": None,
            "branch_at": None,
            "fixture": True,
            "note": "deterministic demo fixture written by demo/build_demo_trace.py",
        },
    )
    seq = 0
    last_call_id = ""
    for entry in PLAN:
        kind = entry[0]
        if kind == "llm":
            _, content, calls = entry
            last_call_id = calls[0][0] if calls else ""
            response = _response(seq, content=content, calls=calls)
            writer.append(
                {
                    "type": "llm_call",
                    "seq": seq,
                    "session_id": "demo-session",
                    "ts": 1762900000.0 + seq,
                    "model": "demo-model",
                    "provider": "demo",
                    "message_count": 2 + seq,
                    "request_digest": digest({"seq": seq}),
                    "response": response,
                    "assistant": _assistant(response),
                    "usage": response["usage"],
                }
            )
        else:
            _, tool_name, args, result, status = entry
            call_id = last_call_id
            writer.append(
                {
                    "type": "tool_call",
                    "seq": seq,
                    "session_id": "demo-session",
                    "ts": 1762900000.0 + seq,
                    "tool_name": tool_name,
                    "tool_call_id": call_id,
                    "args": args,
                    "result": json.dumps(result),
                    "truncated": False,
                    "args_digest": digest(args),
                }
            )
            writer.append(
                {
                    "type": "tool_status",
                    "seq": seq,
                    "session_id": "demo-session",
                    "status": status,
                    "duration_ms": 3 + seq,
                }
            )
        seq += 1

    index, content = FINAL
    response = _response(index, content=content)
    writer.append(
        {
            "type": "llm_call",
            "seq": seq,
            "session_id": "demo-session",
            "ts": 1762900000.0 + seq,
            "model": "demo-model",
            "provider": "demo",
            "message_count": 2 + seq,
            "request_digest": digest({"seq": seq}),
            "response": response,
            "assistant": _assistant(response),
            "usage": response["usage"],
        }
    )
    return writer.path


def build_branch_fixture() -> Path:
    """A deterministic stand-in for what mg_play produces after the edit.

    Only for docs and screenshots on a machine with no provider credential. A real
    ``mg_play`` writes exactly this shape (header with ``branch_of``/``branch_at``, then
    only the steps that ran live) from the child session.
    """
    writer = TraceWriter(
        "r_demo_branch",
        {
            "run_id": "r_demo_branch",
            "created": 1762900100.0,
            "session_id": "demo-session-child",
            "parent_session_id": "demo-session",
            "goal": GOAL,
            "branch_of": RUN_ID,
            "branch_at": 13,
            "fixture": True,
            "note": "stand-in for a live branch; mg_play writes this shape for real",
        },
    )
    writer.append(
        {
            "type": "tool_call",
            "seq": 13,
            "session_id": "demo-session-child",
            "ts": 1762900100.0,
            "tool_name": "read_file",
            "tool_call_id": "call_13",
            "args": {"path": "config/prod.yaml"},
            "result": json.dumps({"ok": True, "content": "service: demo\nreplicas: 4\nregion: us-east-1\n"}),
            "truncated": False,
            "args_digest": digest({"path": "config/prod.yaml"}),
        }
    )
    writer.append(
        {
            "type": "tool_status",
            "seq": 13,
            "session_id": "demo-session-child",
            "status": "ok",
            "duration_ms": 4,
        }
    )
    response = _response(
        14,
        content="Read config/prod.yaml (the edited path). Deploy script would run with 4 replicas in us-east-1.",
    )
    writer.append(
        {
            "type": "llm_call",
            "seq": 14,
            "session_id": "demo-session-child",
            "ts": 1762900101.0,
            "model": "demo-model",
            "provider": "demo",
            "message_count": 17,
            "request_digest": digest({"seq": 14}),
            "response": response,
            "assistant": _assistant(response),
            "usage": response["usage"],
        }
    )
    return writer.path


if __name__ == "__main__":
    path = build()
    print(f"wrote {path}")
    print(f"run_id: {RUN_ID}")
    if "--with-branch-fixture" in sys.argv:
        branch = build_branch_fixture()
        print(f"wrote {branch}")
        print("run_id: r_demo_branch (documentation stand-in; mg_play writes the real one)")

