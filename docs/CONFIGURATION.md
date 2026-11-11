# Configuration

## Environment variables
| Var | Purpose | Req | Scope |
|---|---|---|---|
| OPENROUTER_API_KEY | Provider for the run being recorded | Yes (to record) | Hermes-managed |
| HERMES_HOME | Base dir; traces under $HERMES_HOME/replay-traces/ | Implicit | Runtime |
| MULLIGAN_TRACE_DIR | Override trace dir (tests only) | No | Must resolve under HERMES_HOME |

The plugin never reads OPENROUTER_API_KEY directly. Hermes manages it.

## Trace directory
Default: $HERMES_HOME/replay-traces/
Override: MULLIGAN_TRACE_DIR (must resolve under $HERMES_HOME)

## Manifest
See plugin.yaml. provides_tools, provides_hooks, provides_middleware must
exactly match what register() registers.
