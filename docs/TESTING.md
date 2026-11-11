# Testing

The suite drives **Hermes's real middleware chain** (`hermes_cli.middleware`) through a live
`PluginManager`, not a re-implementation of it. That is what makes "zero provider calls,
zero tool side effects" a measurement instead of a claim.

Run:

```
HERMES_SOURCE=/path/to/hermes \
PYTHONPATH=/path/to/hermes \
python3 -m unittest discover -s tests -v
```

## Coverage

`tests/test_phase1_record.py` — record-only
- 3-step scripted run produces a well-formed JSONL v1 trace (header, llm_call, tool_call,
  tool_status annotation, monotonically increasing seq)
- Mulligan's own `mg_*` calls are never recorded
- trace dir resolves inside `HERMES_HOME`; an override outside it is refused

`tests/test_phase2_replay.py` — exact reproduction (GO/NO-GO)
- no-edit replay reproduces every step with **0 provider calls**, **0 tool invocations**,
  and the recorded file unchanged byte for byte
- the served response is the exact recorded object; after clearing the in-memory cache the
  JSON snapshot still rebuilds a usable response
- a session without the nonce is not served and does not steal the armed replay
- parallel tool calls are matched by `tool_call_id` when they arrive out of order
- desync fails open to live and is recorded as a `desync` record

`tests/test_phase3_branch.py` — edit + branch
- rewind to the failing step, edit the arguments, play: exactly one live tool call with the
  edited arguments, a new run with `branch_of`/`branch_at`, the original trace untouched
- `mg_diff` aligns the branch with the parent's served prefix, reports the first divergence
  and the reason, and shows A failing where B does not

## Acceptance

- A1 exact reproduction — `test_no_edit_replay_reproduces_every_step_with_zero_calls`
- A2 `hermes plugins validate .` exits 0
- A3 `mg_diff` on the demo fixture reproduces the demo's numbers
  (`demo/build_demo_trace.py`, 15 steps, fails at 13, 13 served + 2 live)
- A4 no files written outside `$HERMES_HOME/replay-traces/`

## Security

- S1 replaying a dangerous tool still re-prompts (documented boundary — `tool_execution`
  is after approvals; the demo uses non-dangerous tools)
- S2 trace path traversal rejected (`invalid_run_id`, `trace_dir_outside_hermes_home`)
- S3 the manifest declares exactly what `register()` registers
  (`verify` runs the capability probe and diffs it)

## Not covered by tests (needs a provider credential)

A real `ctx.subagent_lifecycle.launch` into a live child. The launch + binding + serving
plumbing is exercised with an inline stand-in for the service
(`test_mg_play_launches_a_child_with_the_nonce_and_reports_serving`,
`test_edit_at_failing_step_makes_the_branch_succeed`). The end-to-end run requires
`OPENROUTER_API_KEY`, which is not present in the build environment.
