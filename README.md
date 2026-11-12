# Mulligan

Take a mulligan on any Hermes decision.

## Quickstart

Get from zero to a working replay in under 2 minutes.

### 1. Install

Prerequisite: Hermes Agent >= 0.23.0.

```
git clone https://github.com/onyebuchidaniel60/mulligan.git
cp -r mulligan ~/.hermes/plugins/
hermes plugins enable mulligan
hermes plugins list | grep mulligan   # table row: mulligan | enabled | 0.1.0
```

### 2. Record a run

Just use Hermes normally. Every LLM call and tool call is captured to
`~/.hermes/replay-traces/`. Run something that fails to see the debugger shine:

```
hermes chat
# ask the agent to read a file that doesn't exist, e.g.:
#   "read deploy/config.yaml"
# /exit
```

### 3. Inspect, rewind, replay

Open a new Hermes chat. The `mg_*` names are **agent tools, not shell commands** — ask for
them by name and the model calls them with these arguments:

```
hermes chat

> Use mg_list to find my run id.
> Use mg_inspect with run_id="r_...".
> Use mg_rewind with run_id="r_..." and to=<fail_seq>.
> Use mg_edit with run_id="r_...", seq=<fail_seq>, args={"path":"correct/path.yaml"}.
> Use mg_play with run_id="r_...".
> Use mg_diff with run_a="r_..." and run_b="<branch id printed by mg_play>".
```

What you'll see:
- The prefix replays with 0 model calls and 0 tool side effects
- Only the branch (from the edited step) runs live
- `mg_diff` shows the first divergence, both step counts, and how many steps were served
  versus executed live

### Demo

[Watch the 51-second demo](https://x.com/Turnttfup99/status/2120677423532417107)

Music in the demo: "Plathe (Beatless Ambient Mix)" by POA, CC BY 3.0, via Jamendo.

A Hermes Agent plugin that records a run, rewinds to any step, edits one decision, replays
forward, and diffs the counterfactual against the original.

```
mg_list      recorded runs
mg_inspect   step-by-step timeline, failing step highlighted
mg_rewind    serve steps 0..N-1 from the record, go live at N
mg_edit      replace the arguments of one tool call (one edit per branch)
mg_play      run the replay in a fresh child session
mg_diff      side-by-side comparison, first divergence, served vs live
```

[See it in action →](https://x.com/Turnttfup99/status/2120677423532417107)

## The invariant that matters

Replaying with **no edit** reproduces the recorded run step for step with:

- **0 provider calls** on served steps
- **0 tool invocations** on served steps
- **0 bytes changed** in the recorded trace

Only the branch (from the cut-off forward) runs live. This is enforced by tests that drive
Hermes's real middleware chain (`tests/test_phase2_replay.py`).

## How it works

| Surface | Used for |
|---|---|
| `llm_execution` middleware | record the provider response, or serve it on replay |
| `tool_execution` middleware | record the tool result, or serve it on replay |
| `tool_request` middleware | apply a branch edit before approvals see the call |
| `pre_tool_call` / `post_tool_call` hooks | tool status (`ok`/`error`) and duration |
| `ctx.subagent_lifecycle.launch` | replay in a fresh child session, never in-loop |

Two ordering facts from the Hermes middleware contract shape the design:

- `tool_request` runs **before** approvals, so an edited argument is what guardrails and
  the human approve.
- `tool_execution` runs **after** approvals, so serving a recorded result cannot suppress
  an approval prompt. Replaying a dangerous tool therefore still asks; the demo uses
  non-dangerous tools.

Replay does not rewind the current conversation. `mg_play` arms a replay, launches a fresh
child session, and binds that child to the record through a nonce carried in the child's
launch context. The child serves the recorded prefix, then continues live.

## Determinism caveats

- **A counterfactual is *a* what-if, not *the* what-if.** The branch resamples the model.
- Served steps are replayed **in recorded order**, not by re-asking the provider. Parallel
  tool calls are matched by `tool_call_id`, so out-of-order arrival still serves the right
  result.
- Same-process replays return the exact recorded provider object. A replay after a restart
  rebuilds an attribute-compatible response from the JSON snapshot.
- If the model asks for one more completion after the record ends, Mulligan returns a
  synthetic end-of-turn response and appends a `synthetic` record to the trace. It never
  makes a hidden provider call and never pretends the step was recorded.
- If a served step does not match what the child asks for (a desync), Mulligan fails open
  to live execution, appends a `desync` record, and `mg_diff` reports it.
- `response` snapshots are recorded as JSON. Non-JSON provider objects are coerced through
  their `model_dump`/`to_dict`/`__dict__` path.

## Side-effect policy

- **Replay-to-point is side-effect free.** Served LLM and tool steps never reach the
  provider or the tool.
- **The branch is LIVE.** Tools run, approvals fire normally, and the child's calls are
  recorded to a new run id.
- `mg_play` prints a loud banner before launching the child.

## Requirements

- Hermes Agent **>= 0.23.0** (`ctx.subagent_lifecycle`). Hermes 0.19.0 and older do not
  have it; the plugin declares the floor in `plugin.yaml` and refuses to load earlier.
- Python standard library only. No dependencies, no network calls, no binaries.
- `plugins.isolation: in_process` (the default). Mulligan keeps its replay registry in
  module state so a child session can see what the parent armed; under
  `plugins.isolation: host` the plugin runs in a separate process and replay state would
  not be shared.

## Install

```
hermes plugins install mulligan          # from the catalog
# or, from a checkout:
cp -r mulligan ~/.hermes/plugins/
hermes plugins validate ~/.hermes/plugins/mulligan
hermes plugins enable mulligan
```

Traces land in `$HERMES_HOME/replay-traces/` (one JSONL file per run, append-only).

## Try it

```
> Record a run that fails, then:
  mg_list
  mg_inspect run_id=r_20261111-193000_ab12
  mg_rewind run_id=r_... to=13
  mg_edit run_id=r_... seq=13 args={"path":"config/prod.yaml"}
  mg_play run_id=r_...
  mg_diff run_a=r_... run_b=b_...
```

`demo/build_demo_trace.py` writes a deterministic fixture run if you want the same output
without a provider:

```
HERMES_HOME=/tmp/mulligan-demo python3 demo/build_demo_trace.py --with-branch-fixture
```

## Configuration

| Variable | Purpose | Required |
|---|---|---|
| `HERMES_HOME` | traces go to `$HERMES_HOME/replay-traces/` | set by Hermes |
| `MULLIGAN_TRACE_DIR` | override the trace dir; must resolve **inside** `HERMES_HOME` | no |

The plugin never reads `.env`, `auth.json`, or any credential. Hermes owns provider auth;
Mulligan only sees the request/response payloads the middleware is handed.

## Disclosures

- Writes trace files under `$HERMES_HOME/replay-traces/` for every session while enabled.
  Traces contain prompts, tool arguments and tool results, so treat them as sensitive.
- Replay launches a child Hermes session. The served prefix costs no tokens; the live
  branch does.
- No network access, no shell execution, no background processes, no self-update.
- No approvals are bypassed or auto-answered.

## Testing

```
HERMES_SOURCE=/path/to/hermes PYTHONPATH=/path/to/hermes python3 -m unittest discover -s tests -v
hermes plugins validate .
```

## Documentation

- [Project Spec](docs/PROJECT_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Setup](docs/SETUP.md)
- [Configuration](docs/CONFIGURATION.md)
- [Testing](docs/TESTING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Design Notes](docs/DESIGN_NOTES.md)
- [Build Log](docs/BUILD_LOG.md)

## N/A

No frontend, no database, no auth system, no payments. Pure Python standard library.
