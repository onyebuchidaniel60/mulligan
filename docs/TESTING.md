# Testing

## Unit (pytest, dev-only, not shipped in catalog pin)
- take() state machine: IDLE -> ARMED -> SERVING -> LIVE, DESYNC path
- Trace append/read round-trip; version field; coercion of non-JSON results
- mg_edit guards: not_a_tool_step, edit_already_set

## Integration
- Round-trip reproduction: scripted 3-step run with read_file ENOENT failure;
  mg_rewind --to last + mg_play -> assert identical step sequence, zero usage
  on served steps
- Branch: rewind to failing step, edit path, play -> assert branch succeeds and
  mg_diff reports first divergence at that step
- Desync injection: corrupt one served record -> assert fail-open to LIVE +
  DESYNC surfaced

## Acceptance (must pass before demo)
- A1: exact reproduction (above)
- A2: hermes plugins validate exits 0
- A3: mg_diff produces the demo's screenshot numbers
- A4: no files written outside $HERMES_HOME/replay-traces/

## Security
- S1: replaying a dangerous tool re-prompts (documented boundary; MVP demo
  uses non-dangerous tools so S1 is a documented limitation, not a passing test)
- S2: trace path traversal rejected
- S3: plugin declares exactly what it registers (validate enforces)

## Run
    pytest tests/
