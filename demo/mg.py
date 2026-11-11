#!/usr/bin/env python3
"""Thin CLI over the six Mulligan tools, for the demo recording.

Calls the *real* tool handlers in the installed plugin and prints the exact `text`
they return, so what you see on screen is the plugin's own output, not a mock-up.

Usage (from the repo root):
    python3 demo/mg.py list
    python3 demo/mg.py inspect r_demo_deploy
    python3 demo/mg.py rewind r_demo_deploy 13
    python3 demo/mg.py edit r_demo_deploy 13 '{"path":"config/prod.yaml"}'
    python3 demo/mg.py diff r_demo_deploy latest
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

PLUGIN_DIR = Path(os.environ.get("MULLIGAN_PLUGIN_DIR", str(Path.home() / ".hermes" / "plugins" / "mulligan")))
SESSION = os.environ.get("MULLIGAN_DEMO_SESSION", "demo-session")


def load_plugin():
    spec = importlib.util.spec_from_file_location(
        "mulligan_demo", PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["mulligan_demo"] = module
    spec.loader.exec_module(module)
    return module


class Ctx:
    """No subagent service: mg_play needs a live Hermes turn and is not run here."""

    subagent_lifecycle = None


def call(module, name: str, args: dict) -> dict:
    handler = getattr(module.tools, name)
    return json.loads(handler(args, ctx=Ctx(), session_id=SESSION))


def latest_branch(module, parent: str) -> str:
    runs = call(module, "mg_list", {}).get("runs") or []
    branches = [r for r in runs if r.get("branch_of") == parent]
    if not branches:
        raise SystemExit(f"no branch of {parent} recorded yet — run mg_play first")
    return max(branches, key=lambda r: r.get("created") or 0)["run_id"]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    command, rest = argv[0], argv[1:]
    module = load_plugin()

    if command == "list":
        out = call(module, "mg_list", {})
    elif command == "inspect":
        out = call(module, "mg_inspect", {"run_id": rest[0]})
    elif command == "rewind":
        out = call(module, "mg_rewind", {"run_id": rest[0], "to": int(rest[1]) if len(rest) > 1 else None})
    elif command == "edit":
        args = json.loads(rest[2]) if len(rest) > 2 else {}
        out = call(module, "mg_edit", {"run_id": rest[0], "seq": int(rest[1]), "args": args})
    elif command == "diff":
        run_b = latest_branch(module, rest[0]) if rest[1:2] == ["latest"] else rest[1]
        out = call(module, "mg_diff", {"run_a": rest[0], "run_b": run_b})
    else:
        print(f"unknown command {command}")
        return 2

    print(out.get("text", out))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
