# Mulligan â€” Architecture

## Runtime placement
Plugin registers middleware, hooks, and six tools via public ctx APIs.
No core patching. No private-dict manipulation.

## Replay model (the key decision)
Replay is NOT in-loop. mg_play launches a fresh child session via
ctx.subagent_lifecycle.launch(...). That child's middleware serves steps
0..N-1 from the parent's recorded trace, then switches to live at step N.
This avoids corrupting a diverged conversation and uses only public APIs.

## Middleware contract (VERIFY IN PHASE 0)
llm_execution:
  if serving and a matching record exists -> return recorded response, skip next_call
  else -> call next_call and (if recording) append
tool_execution:
  same shape for tool results
  serving happens AFTER approvals; MVP demo uses non-dangerous tools
  so replay does not re-prompt on every served step
tool_request:
  optional rename workaround for dangerous tools (POST-MVP)

## State
ReplayState keyed by session_id:
  { serving, recording, trace, cursor, branch_at, edits }
Module-level registry; no cross-session bleed.

## Trace format
JSONL v1; header line then llm_call/tool_call records; append-only; never mutated.

## Failure modes
- Desync at served step -> fail open to LIVE + log + surface as DESYNC in mg_diff
- Child launch fails -> typed error, state preserved, retry allowed
- Unwritable trace dir -> disable recording, surface in mg_list

## What this plugin does NOT touch
- Hermes core code or private internals
- .env / auth.json
- Any path outside $HERMES_HOME/replay-traces/
- Network (no fetch, no self-update)
