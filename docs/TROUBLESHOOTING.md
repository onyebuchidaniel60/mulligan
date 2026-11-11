# Troubleshooting

## Plugin not loading
- Check hermes plugins validate output
- Confirm plugin.yaml exists at the plugin root
- Confirm __init__.py defines register(ctx)

## Traces not appearing
- Check $HERMES_HOME/replay-traces/ is writable
- Run mg_list â€” if it says "recording disabled", the dir was unwritable at startup

## mg_play says not_armed
- Call mg_rewind before mg_play

## mg_diff shows DESYNC
- The trace diverged earlier than expected (usually a tool result with a
  timestamp or random id)
- The branch still ran; the diff is honest about where determinism ended

## Branch re-prompts for approval
- Expected. Branch execution is live. Only replay-to-point is silent.
- Scope the demo to non-dangerous tools to avoid this.

## provides_middleware warning flood
- Known loader bug. Validate still passes. Do not chase it.
