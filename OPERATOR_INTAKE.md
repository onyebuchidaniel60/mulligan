# Operator Intake — Mulligan

| Input | Status | Source | Notes |
|---|---|---|---|
| Project = Mulligan | DECIDED | operator | counterfactual replay for Hermes |
| Scope = MVP per PROJECT_SPEC.md | DECIDED | operator | |
| Architecture fixed per ARCHITECTURE.md | DECIDED | operator | |
| OPENROUTER_API_KEY | **MISSING HERE** | env check | not in process env; `~/.hermes` does not exist. Operator must export it to record the live demo. Plugin never reads it. |
| Hermes installed | **YES — v0.23.1** | `hermes --version` | release tag `v0.23.1` from source tree. PyPI `hermes-agent` is 0.19.0 and too old (no `ctx.subagent_lifecycle`). |
| Demo failure case = read_file ENOENT | DECIDED | operator | non-dangerous, no approvals |
| Reference images | N/A | — | CLI plugin |
| UI skill (stageshow) | N/A | — | CLI plugin |
| Frontend / preview URL | N/A | — | CLI plugin |
| Database / auth / payments | N/A | — | CLI plugin |
| Budget ceiling | $0 | operator | stdlib only |
| Production authority | N/A | operator | catalog PR only |
| API surface answers (a)-(d) | **RESOLVED** | developer guide + v0.23.1 source | see below and docs/BUILD_LOG.md § Phase 0 |

## Phase 0 blocker detail — resolved

(a) `ctx.register_middleware(kind, callback)`; kinds `llm_execution`, `tool_execution`,
    `tool_request`, `llm_request`. Callbacks are keyword payloads, signature-narrowed:
    `llm_execution(request, original_request, next_call, **ctx)`,
    `tool_execution(tool_name, args, original_args, next_call, **ctx)`,
    `tool_request(tool_name, args, original_args, **ctx)`; context includes `session_id`,
    `task_id`, `turn_id`, `api_request_id`, `tool_call_id`. `next_call` is single-use.

(b) `ctx.subagent_lifecycle.launch(SubagentLaunchRequest(goal, context, role, model,
    provider, allowed_toolsets, parent_session_id, correlation_id, metadata))` →
    `SubagentHandle`. `blocked_tools`, `working_directory`, `timeout_seconds` are rejected.
    Child runs on a thread pool **in the same process**, so plugin module state is visible;
    but the child's `session_id` is new and `metadata` is not forwarded to middleware, so
    the replay binding must travel in `context` and be bound on first observed request.

(c) Order is `tool_request` → availability/guardrails/**approvals** → `tool_execution` →
    `post_tool_call`. So `tool_execution` runs AFTER approvals (as ARCHITECTURE.md assumes),
    and `tool_request` is the approval-safe place to apply a branch edit.

(d) `ctx.register_tool(name, toolset, schema, handler, check_fn, requires_env, is_async,
    description, emoji, override)`; handler is `def handler(args: dict, **kwargs) -> str`
    and must always return a JSON string and never raise.

Verdict: **architecture compatible; no open critical items.**
