# Design Notes

## Name
Mulligan â€” a free do-over. The tagline is "take a mulligan on any Hermes decision."

## Key decision: fresh child session, not in-loop replay
Rewinding the current conversation is unsafe â€” the state is already past step N.
Instead, mg_play launches a fresh child via ctx.subagent_lifecycle.launch.
The child's middleware serves steps 0..N-1 from the recorded trace, then goes live.

## Why middleware, not hooks
Hooks observe. Middleware replaces. Serving a recorded response requires replacing
next_call. Hooks cannot do this.

## Why single-edit-per-branch
Multiple simultaneous edits create a branch tree that the MVP cannot meaningfully
diff. One edit is enough to demonstrate the value.

## Why non-dangerous tools in the demo
tool_execution runs AFTER approvals. Serving a recorded result there does not
prevent the approval prompt from firing. Scoping the demo to read_file avoids
the re-prompt problem without requiring the tool_request rename workaround.

## What we deliberately did not build
- Editing model responses (adds complexity without changing the story)
- Multi-branch (the diff would need a tree view)
- Web UI (the CLI is enough and pure Python is a catalog advantage)
- Desktop panel (nice-to-have, not needed for the demo)
