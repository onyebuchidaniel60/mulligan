# Add mulligan — counterfactual replay (record, rewind, edit, replay, diff)

## What it does

Mulligan records a Hermes run and lets you take a mulligan on any decision: rewind to a
step, change one tool argument, replay forward in a fresh child session, and diff the
counterfactual against the original.

```
mg_list · mg_inspect · mg_rewind · mg_edit · mg_play · mg_diff
```

The invariant that matters: **replaying with no edit reproduces the recorded run step for
step with zero provider calls and zero tool side effects.** It is enforced by a test that
drives Hermes's real `hermes_cli.middleware` chain through a live `PluginManager`, so it is
measured rather than asserted.

## Surfaces used

| Surface | Used for |
|---|---|
| `llm_execution` middleware | record the provider response; serve it on replay |
| `tool_execution` middleware | record the tool result; serve it on replay |
| `tool_request` middleware | apply the branch edit before approvals see the call |
| `pre_tool_call` / `post_tool_call` hooks | tool status and duration |
| `ctx.subagent_lifecycle.launch` | replay in a fresh child session, never in-loop |
| `ctx.register_tool` | the six tools |

No core patching, no private state, no imports outside the documented public API.

## Why the design is approval-correct

The middleware contract puts `tool_request` before approvals and `tool_execution` after
them. So the branch edit is what guardrails and the human approve, while serving a recorded
result in `tool_execution` cannot suppress an approval prompt. Replaying a dangerous tool
still asks; the demo deliberately uses `read_file`.

## Disclosure (rule 13)

- **Writes trace files.** Append-only JSONL under `$HERMES_HOME/replay-traces/` for every
  session while the plugin is enabled. Traces contain prompts, tool arguments and tool
  results — treat them as sensitive; nothing is uploaded anywhere.
- **Child session on replay.** `mg_play` launches a Hermes child session. The served prefix
  makes zero provider calls; the live tail spends tokens on the configured provider.
- **No network, no credentials, no shell, no background processes, no self-update.** The
  plugin never reads `.env`, `auth.json`, or any credential store, and never bypasses or
  auto-answers an approval.
- **Deterministic caveat, stated in the README:** a branch resamples the model, so it is *a*
  what-if, not *the* what-if. If the child desyncs from the record, Mulligan fails open to
  live execution, records the desync, and `mg_diff` reports it.

## Validation

```
$ hermes plugins validate /path/to/mulligan
✓ manifest ✓ loadable ✓ capability probe ✓ declared tools/hooks/middleware
✓ built-in tool collisions ✓ security scan ✓ no core override
Validation passed.   (exit 0)

$ hermes plugins doctor /path/to/mulligan --ci
OK: runtime discovery, manifest parsing, import, and registration passed
registrations: 6 tool(s), 2 hook(s)   (exit 0)
```

Requires Hermes `>=0.23.0` (`ctx.subagent_lifecycle`); declared in `plugin.yaml` and in the
catalog entry.

## Tests

```
HERMES_SOURCE=/path/to/hermes PYTHONPATH=/path/to/hermes \
  python3 -m unittest discover -s tests -v
Ran 15 tests — OK
```

Covers: trace shape, trace-dir containment, exact reproduction (0 provider calls / 0 tool
invocations / 0 bytes changed), replay from a JSON snapshot after losing the live object,
nonce binding isolation, out-of-order parallel tools, desync fail-open, edit guards, branch
recording under a new run id, and `mg_diff` alignment with the parent's served prefix.
