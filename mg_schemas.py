"""Tool schemas — what the model sees."""

MG_LIST = {
    "name": "mg_list",
    "description": (
        "List recorded Mulligan runs (trace id, step count, goal, branch parent). "
        "Use this first to find the run you want to inspect or replay."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

MG_INSPECT = {
    "name": "mg_inspect",
    "description": (
        "Show the step-by-step timeline of one recorded run: each LLM call and tool call "
        "with its sequence number, tool name, a short digest of the arguments, and whether "
        "the step succeeded or failed. Use it to find the step where the run went wrong."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "Trace id from mg_list (e.g. r_20261111-193000_ab12)."},
            "limit": {"type": "integer", "description": "Maximum steps to render (default 40)."},
        },
        "required": ["run_id"],
    },
}

MG_REWIND = {
    "name": "mg_rewind",
    "description": (
        "Arm a replay of a recorded run: steps 0..to-1 will be served from the record, and "
        "execution becomes live at step `to`. Call mg_play afterwards to run the replay in a "
        "fresh child session. Omit `to` to reproduce the whole run (exact reproduction)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "Trace id to replay."},
            "to": {
                "type": "integer",
                "description": "Step index to branch at. Steps before it are served; it and everything after run live. Default: end of trace.",
            },
        },
        "required": ["run_id"],
    },
}

MG_EDIT = {
    "name": "mg_edit",
    "description": (
        "Edit one decision in an armed replay. The edit replaces the arguments of the tool "
        "call at `seq`, and the branch runs live from there. One edit per branch. "
        "Call mg_rewind first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "Trace id being replayed."},
            "seq": {"type": "integer", "description": "Sequence number of the tool call to edit (from mg_inspect)."},
            "args": {"type": "object", "description": "Replacement arguments for that tool call."},
            "tool": {"type": "string", "description": "Optional tool name guard; the edit applies only if the step calls this tool."},
        },
        "required": ["run_id", "seq", "args"],
    },
}

MG_PLAY = {
    "name": "mg_play",
    "description": (
        "Run the armed replay in a fresh child session: recorded steps are served with zero "
        "provider calls and zero tool side effects, then execution continues live from the "
        "branch point. Prints a banner first. Call mg_rewind (and optionally mg_edit) before it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "Trace id being replayed."},
            "timeout_seconds": {"type": "integer", "description": "How long to wait for the child session (default 600)."},
        },
        "required": ["run_id"],
    },
}

MG_DIFF = {
    "name": "mg_diff",
    "description": (
        "Compare two runs side by side: step counts, the first divergence, which branch steps "
        "were served deterministically versus executed live, and the outcome of each. "
        "Use it after mg_play to show what the edit changed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_a": {"type": "string", "description": "Baseline trace id."},
            "run_b": {"type": "string", "description": "Branch trace id."},
        },
        "required": ["run_a", "run_b"],
    },
}

ALL = (MG_LIST, MG_INSPECT, MG_REWIND, MG_EDIT, MG_PLAY, MG_DIFF)
