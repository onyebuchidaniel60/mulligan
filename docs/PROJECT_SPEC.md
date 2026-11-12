# Mulligan â€” Project Spec

## Purpose
Record a Hermes run, rewind to any step, edit a decision, replay forward, diff outcomes.
Take a mulligan on any agent decision.

## Users
Single role: Operator (Hermes user). No admin, no tenancy.

## MVP (must ship before 5PM EST Nov 11)
- Record llm_call + tool_call to JSONL under $HERMES_HOME/replay-traces/
- Tools: mg_list, mg_inspect, mg_rewind, mg_edit, mg_play, mg_diff
- Exact-reproduction invariant: no-edit replay reproduces the run step-for-step
  with ZERO provider calls and ZERO tool side effects
- hermes plugins validate exits 0
- Catalog entry pinned to a 40-char SHA
- <=90s demo on X tagging @NousResearch
- PR opened + Typeform submitted

## Non-goals
Web UI, database, auth, payments, cross-machine replay, editing model responses,
multi-branch replay, Hermes core modification, any runtime network fetch, self-update.

## Fixed architecture
- Replay runs in a FRESH CHILD SESSION via ctx.subagent_lifecycle.launch
  (NOT in-loop â€” never rewind the current conversation)
- Middleware: llm_execution, tool_execution (record + serve); tool_request (stub)
- Hooks: pre_tool_call, post_tool_call
- ReplayState keyed by session_id (no cross-session bleed)
- Pure Python stdlib only; traces append-only JSONL v1

## Business rules
R1 exact reproduction Â· R2 side-effect isolation while serving
R3 single edit per branch Â· R4 approval boundary (MVP demo uses non-dangerous tools)
R5 append-only traces Â· R6 writes only under $HERMES_HOME/replay-traces/
R7 no self-update / no runtime network fetch

## Submission checklist
[ ] hermes plugins validate passes
[ ] Catalog entry YAML pinned to 40-char SHA
[ ] README states determinism caveats + side-effect policy
[ ] <=90s demo posted on X, tagged @NousResearch
[ ] PR + Typeform submitted before 5PM EST Nov 11
