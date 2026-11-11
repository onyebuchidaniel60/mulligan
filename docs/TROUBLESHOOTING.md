# Troubleshooting

## Plugin not loading
- `hermes plugins validate ~/.hermes/plugins/mulligan` — fix anything that is not a ✓
- `hermes plugins list` shows the load error, including `requires_hermes` rejections
- Hermes < 0.23.0 has no `ctx.subagent_lifecycle`; the manifest floor refuses it

## "recording_disabled" / no traces
- Check `$HERMES_HOME/replay-traces/` is writable
- If `MULLIGAN_TRACE_DIR` is set, it must resolve inside `HERMES_HOME`; otherwise recording
  is refused by design and `mg_list` reports `trace_dir_outside_hermes_home`

## mg_play says "not_armed"
- Call `mg_rewind` in the **same chat session** first. The armed replay is keyed by session.

## mg_play says "launch_failed"
- The child session could not be created (usually provider credentials or config). The
  armed replay is preserved; fix the cause and call `mg_play` again.

## "no replay state was bound to the child session"
- The child's first request did not carry the replay nonce, so serving never started and
  the child ran live. Check that the child received the launch `context`.

## mg_diff shows DESYNC
- The child asked for a step that does not match the record (usually a non-deterministic
  tool result such as a timestamp or random id). Mulligan failed open to live and recorded
  the desync; the branch still ran.

## Branch re-prompts for approval
- Expected. The branch is live and `tool_execution` runs after approvals. Only
  replay-to-point is silent. Scope the demo to non-dangerous tools.

## A served step returned a synthetic end-of-turn response
- The model asked for another completion after the record ended. Mulligan returns a
  synthetic response and appends a `synthetic` record rather than making a hidden provider
  call. `mg_diff` will show the extra step.

## provides_middleware warning
- Hermes treats `provides_middleware` as an unknown manifest field at v1 (debug-level) but
  `hermes plugins validate` uses it to diff declared vs registered middleware. Keep it: it
  is required for catalog admission.
