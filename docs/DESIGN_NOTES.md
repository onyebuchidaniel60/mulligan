# Design Notes

## Name
Mulligan — a free do-over. Tagline: "take a mulligan on any Hermes decision."

## Key decision: fresh child session, not in-loop replay
Rewinding the current conversation is unsafe — that state is already past step N.
`mg_play` arms a replay and launches a fresh child via `ctx.subagent_lifecycle.launch`.
The child serves steps 0..N-1 from the record, then goes live.

The child's `session_id` is new and `SubagentLaunchRequest.metadata` is not forwarded into
the middleware payload, so the binding travels in `context` as a nonce and is recovered
from the child's first request. `ReplayState` stays keyed by `session_id`; the parent's
state is never touched. One armed replay is consumed by exactly one child.

## Why middleware, not hooks
Hooks observe. Middleware replaces. Serving a recorded response requires short-circuiting
`next_call`. Hooks cannot do that.

## Ordering facts that shaped the design (verified in Phase 0)
`tool_request` runs **before** availability checks, guardrails and approvals.
`tool_execution` runs **after** them.

Therefore:
- the branch edit is applied in `tool_request`, so the human approves the edited call;
- serving in `tool_execution` cannot suppress an approval prompt, so replaying a dangerous
  tool still asks. The MVP demo uses `read_file`, which never prompts.

## Serving is ordinal, not prompt-matched
The replay child has its own system prompt and session id, so its requests will not be
byte-identical to the parent's. Matching is by recorded order (LLM) and `tool_call_id`
(tools). That is what makes the reproduction exact *for the recorded steps* while the live
tail diverges naturally.

## Why single-edit-per-branch
Multiple simultaneous edits create a branch tree the MVP cannot meaningfully diff. One edit
is enough to demonstrate the value.

## Same-process objects, cross-process snapshots
A replay in the same process returns the exact recorded provider object. After a restart
the response is rebuilt from the JSON snapshot as an attribute-compatible object. Both paths
are tested.

## What we deliberately did not build
- Editing model responses (complexity without changing the story)
- Multi-branch (the diff would need a tree view)
- Web UI (the CLI is enough and pure Python is a catalog advantage)
- Desktop panel (not needed for the demo)
