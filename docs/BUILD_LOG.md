# Mulligan — Build Log

## Phase 0 — API verification spike

Status: **COMPLETE** — all four questions answered from the Hermes developer guide and
cross-checked against the shipped source at tag `v0.23.1`.

### Environment used for verification

| Item | Value |
|---|---|
| Hermes Agent | **v0.23.1** (release tag `v0.23.1`, 2026-11-10), installed from the source tree (`HERMES_NIX_BUILD=1 pip install --target`), run as `PYTHONPATH=/opt/hermes23:/opt/hermes-pkg hermes` |
| Middleware contract | `hermes.middleware.v1` / observer `hermes.observer.v1` |
| PyPI `hermes-agent` | **0.19.0 — too old.** It has no `agent/subagent_lifecycle.py` and no `ctx.subagent_lifecycle`. See finding E5. |

Source of truth for the signatures below is the running code, not prose:

```
$ python3 -c "from hermes_cli.plugins_context import PluginContext; import inspect; \
    print(inspect.signature(PluginContext.register_middleware)); \
    print(inspect.signature(PluginContext.register_tool))"
register_middleware: (self, kind: 'str', callback: 'Callable') -> 'PluginRegistration'
register_tool: (self, name: 'str', toolset: 'str', schema: 'dict', handler: 'Callable',
  check_fn: 'Callable | None' = None, requires_env: 'list | None' = None,
  is_async: 'bool' = False, description: 'str' = '', emoji: 'str' = '',
  override: 'bool' = False) -> 'Optional[PluginRegistration]'
PluginContext.subagent_lifecycle present: True
```

---

### (a) `ctx.register_middleware` signature and callback kwargs

**Answer.**

`ctx.register_middleware(kind: str, callback: Callable) -> PluginRegistration`.
`kind` must be one of `hermes_cli.middleware.VALID_MIDDLEWARE` =
`{"llm_request", "llm_execution", "tool_request", "tool_execution"}`; an unknown kind
warns but is still stored.

Callbacks are invoked with **keyword arguments only**, and Hermes narrows the payload to
the parameters your signature names (so `def cb(**kwargs)` gets everything, `def cb(tool_name, args)`
gets just those two). Every execution callback receives `next_call`, plus:

| Kind | Payload keys |
|---|---|
| `llm_request` | `request`, `original_request` |
| `llm_execution` | `request`, `original_request`, `next_call` |
| `tool_request` | `tool_name`, `args`, `original_args` |
| `tool_execution` | `tool_name`, `args`, `original_args`, `next_call` |

Every kind additionally receives runtime context: `session_id`, `task_id`, `turn_id`,
`api_request_id`, `provider`, `model`, `api_mode`, `tool_call_id` (tool kinds),
`platform`, `api_call_count`, and the schema-version fields
`telemetry_schema_version="hermes.observer.v1"` and
`middleware_schema_version="hermes.middleware.v1"`.

Intake item (a) listed `(request, original_request, next_call, tool_name, args, session_id)`.
That set is **correct but not exhaustive**: the tool kinds also carry `original_args`, and
`original_request` is not sent to `tool_execution`. Implementations must accept `**kwargs`.

**Precision correction found during verification:** `next_call` is **single-use per frame**.
Calling it twice raises
`RuntimeError("... next_call() called more than once; downstream execution is single-use")`
(`hermes_cli/middleware.py::_run_execution_chain`). Serving code must therefore either
short-circuit *without* calling `next_call`, or call it exactly once.

**Source citations.**
- Developer guide → Extending → Plugins → **Middleware** → "Contract"
  (`https://hermes-agent.nousresearch.com/docs/developer-guide/middleware#contract`),
  including the kind/return table.
- Developer guide → **Middleware** → "Safety Notes": "Execution middleware should call
  `next_call(...)` exactly once unless it is intentionally short-circuiting execution."
- Code: `hermes_cli/middleware.py` (`VALID_MIDDLEWARE`, `run_llm_execution_middleware`,
  `run_tool_execution_middleware`, `_run_execution_chain`).

---

### (b) `ctx.subagent_lifecycle.launch` / `SubagentLaunchRequest`, and child-session state visibility

**Answer.**

`ctx.subagent_lifecycle` is a `SubagentLifecycleService` (property on `PluginContext`).
`service.launch(request) -> SubagentHandle`. The request fields are exactly:

```
goal                  # required, non-empty, <= 16000 chars
context               # optional str, <= 32000 chars
role                  # "leaf" (default) or "orchestrator"
model, provider
allowed_toolsets      # narrows the child; unknown/parent-broadening sets rejected
blocked_tools         # REJECTED at validation
working_directory     # REJECTED ("isolated task environments")
parent_session_id
correlation_id        # unique per parent session
metadata              # JSON-serializable, <= 8192 bytes
timeout_seconds       # REJECTED ("configure delegation timeout explicitly")
```

`SubagentHandle` is a frozen dataclass (`contract_version`, `subagent_id`,
`parent_session_id`, `correlation_id`, `created_at`, `provider`, `model`, `role`,
`depth`, `capability`) and is serializable via `to_dict()`.
`service.wait(handle, timeout_seconds=...)` / `service.result(handle)` / `status` /
`cancel` / `steer` / `reconnect` complete the surface.

**Child state visibility — the answer that mattered for the architecture:**
plugin module state **is** visible inside the child, in the default configuration.

- `plugins.isolation` defaults to `ISOLATION_IN_PROCESS` (`hermes_cli/plugin_isolation.py`:
  an unknown value "warns and means in-process"), so plugin code runs in the Hermes process.
- `launch()` submits the child to `_EXECUTOR = _DaemonExecutor(max_workers=8, ...)`
  (`agent/subagent_lifecycle.py`) — a thread pool in the same interpreter, and the child is
  built with `_build_child_preserving_parent_tools(...)`, so it is a normal `AIAgent`
  driving `agent/conversation_loop.py` and `agent/tool_executor.py`, which call the same
  global middleware chain (`_delivery_manager()`).

**However, state is shared but identity is not.** The child gets a *new* `session_id`,
which the parent cannot know at `launch()` time. `SubagentLaunchRequest.metadata` is not
forwarded into the middleware payload, so it cannot be read from `llm_execution` /
`tool_execution`. The middleware context carries `session_id` and `task_id`, nothing the
plugin set. Therefore the replay binding **must** be carried in `context` (or `goal`)
and recovered from the child's first request payload — i.e. passed via context, not
assumed.

This is compatible with the fixed architecture: `ReplayState` stays keyed by
`session_id`; the only addition is an explicit, public "arm → bind on first observed
request that carries the replay nonce" step. See Design Note DN-1 below.

**Source citations.**
- Developer guide → **Public Subagent Lifecycle API**
  (`https://hermes-agent.nousresearch.com/docs/developer-guide/subagent-lifecycle-api`):
  field list, "The facade also works when a plugin runs under `plugins.isolation: host`",
  fail-closed request rules.
- Code: `agent/subagent_lifecycle.py` (`SubagentLaunchRequest`, `_REQUEST_REJECTIONS`,
  `_EXECUTOR`, `launch`), `hermes_cli/plugins_context.py::subagent_lifecycle`,
  `hermes_cli/plugin_isolation.py::isolation_mode`.
- Public-API allowlist: `agent.subagent_lifecycle` is a listed public module
  (developer guide → **Public plugin API**), so importing `SubagentLaunchRequest` is legal.

---

### (c) Middleware ordering relative to approvals

**Answer: `tool_execution` runs AFTER approval checks.** Documented order for every tool call:

1. Parse and coerce model-provided tool arguments.
2. Apply `tool_request` middleware.
3. Normal pre-execution path: tool availability checks, observer block directives,
   guardrails, and **approval checks**.
4. Run tool execution through `tool_execution` middleware.
5. Emit `post_tool_call` observer hooks.
6. Apply `transform_tool_result` hooks.

Consequences for Mulligan, all already assumed by `ARCHITECTURE.md`:
- Serving a recorded result inside `tool_execution` cannot suppress an approval prompt
  that step 3 already raised. The MVP demo therefore stays on non-dangerous tools
  (`read_file` with a bad path), exactly as `PROJECT_SPEC.md` R4 says.
- `tool_request` runs *before* approvals, so a branch edit applied there is what guardrails
  and the human approve. That is the safe place to apply `mg_edit`, and it is what this
  implementation does.

**Source citations.**
- Developer guide → **Middleware** → "Execution Order → Tool Calls" (numbered list above).
- Developer guide → **Middleware** → "Safety Notes": "Tool request middleware runs before
  approvals. If it mutates file paths, commands, URLs, or arguments, the mutated values are
  what guardrails and approvals evaluate."
- Code: `agent/tool_executor.py` (`_run_agent_tool_request_middleware`,
  `_run_agent_tool_execution_middleware`).

---

### (d) `ctx.register_tool` handler signature and return contract

**Answer.**

```
ctx.register_tool(name, toolset, schema, handler, check_fn=None, requires_env=None,
                  is_async=False, description="", emoji="", override=False)
    -> PluginRegistration | None
```

Handler contract (developer guide, Step 4 "Key rules for handlers"):

1. **Signature:** `def my_handler(args: dict, **kwargs) -> str`
2. **Return:** always a JSON string — success and errors alike.
3. **Never raise:** catch everything and return error JSON.
4. **`**kwargs`** opts into injected context (`task_id`, `session_id`, `conversation_id`,
   `user_task`, `parent_agent`, ...). Hermes forwards only the names your signature declares.
5. Key per-conversation state on `conversation_id`, not `session_id` — `session_id` changes
   when a rotating compression replaces the transcript segment.

Note for Mulligan: rule 5 is about *tool state*, not replay identity. Replay serving must
key on `session_id` because the middleware payload carries `session_id` and the child's
first request is what binds the replay. Traces therefore store both ids.

`override=False` is mandatory here: registering a name owned by another toolset without
`override=True` returns `None` and only warns; overriding a built-in needs the operator
grant `plugins.entries.<id>.allow_tool_override: true`. Mulligan registers six new names
and needs no override.

**Source citations.**
- Developer guide → **Build a Hermes Plugin** → Step 4, and "Conditional tool availability" /
  "Overriding a built-in tool"
  (`https://hermes-agent.nousresearch.com/docs/developer-guide/plugins`).
- Code: `hermes_cli/plugins_context.py::register_tool`.

---

### Phase 0 findings that change the plan

**E5 — released PyPI package is too old (environment, not architecture).**
`pip install hermes-agent` yields 0.19.0, which has no `agent/subagent_lifecycle.py` and no
`ctx.subagent_lifecycle`; the fixed architecture cannot run on it. The current release tag
is `v0.23.1` (2026-11-10), which has every API above. Consequence: the plugin declares
`requires_hermes: ">=0.23.0"` in `plugin.yaml` **and** in the catalog entry, and all
verification runs against `v0.23.1`. No design change.

**DN-1 — replay binding (design note, within the fixed architecture).**
`mg_play` arms one `PendingReplay` (trace id, cursor, edit, nonce) in module state keyed by
the *parent* `session_id`, then launches the child with the nonce embedded in
`SubagentLaunchRequest.context`. The child's first `llm_execution` call is scanned for the
nonce and, on a match, a `ReplayState` is created **keyed by the child's `session_id`** and
bound to the armed replay. No cross-session bleed: the parent's state is never touched, and
one armed replay is consumed by exactly one child session.

**BLOCKER-1 (operator action, not blocking the build) — no provider credential here.**
`OPENROUTER_API_KEY` does not resolve in this environment and `~/.hermes` does not exist.
The plugin never reads the key (Hermes owns provider auth), so build, unit/integration tests
and `hermes plugins validate` are unaffected. A *live* model run and the recorded demo
require the operator to export the key / create `~/.hermes`. Exact-reproduction is proven
against the real middleware dispatch with an instrumented fake provider instead (Phase 2),
and the gap is stated in the handoff rather than papered over.

### Compatibility verdict

**All four answers are compatible with `ARCHITECTURE.md`.** No redesign required.
`tool_execution` sits after approvals (as assumed), `tool_request` sits before them (so the
branch edit is approval-correct), child sessions share plugin module state (so the
module-level registry works), and tool handlers follow `(args, **kwargs) -> JSON str`.
Phase 0 gate: **PASSED**. Proceeding to Phase 1.

## Phase 1 — Scaffold + record-only

Status: NOT STARTED

## Phase 2 — Serve / exact reproduction (GO/NO-GO)

Status: NOT STARTED
Acceptance: exact-reproduction test passes with zero provider calls, zero side effects

## Phase 3 — Edit + branch

Status: NOT STARTED

## Phase 4 — Inspect + diff

Status: NOT STARTED

## Phase 5 — Validation + submission

Status: NOT STARTED

## Phase 6 — Demo + submit

Status: NOT STARTED
Deadline: 5PM EST Nov 11
