# Configuration

## Environment variables
| Var | Purpose | Req | Scope |
|---|---|---|---|
| `HERMES_HOME` | Base dir; traces under `$HERMES_HOME/replay-traces/` | set by Hermes | Runtime |
| `MULLIGAN_TRACE_DIR` | Override the trace dir. Must resolve **inside** `HERMES_HOME`, otherwise recording is disabled and `mg_list` says so | No | Runtime |
| `OPENROUTER_API_KEY` | Provider for live runs and live branches | Yes, to record/play live | Hermes-managed |

The plugin never reads `OPENROUTER_API_KEY`, `.env`, or `auth.json`. Hermes owns provider
auth; Mulligan only sees the request/response payloads the middleware is handed.

## Trace directory
Default: `$HERMES_HOME/replay-traces/`
Override: `MULLIGAN_TRACE_DIR` (must resolve under `HERMES_HOME`; traversal is rejected)

Files: one `<run_id>.jsonl` per run, append-only. `run_id` matches
`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`.

## Manifest
`plugin.yaml` declares exactly what `register()` registers — `provides_tools`,
`provides_hooks`, `provides_middleware`. `hermes plugins validate` runs a capability probe
and fails if the declarations drift from reality.

`requires_hermes: ">=0.23.0"` is enforced by the loader: on an older Hermes the plugin is
skipped rather than half-loaded.
