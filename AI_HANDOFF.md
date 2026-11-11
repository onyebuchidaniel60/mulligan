# Mulligan — AI Handoff (current state)

Current phase: 1 — scaffold + record-only
Completed: Phase 0 API verification (all four items answered with citations)
Tests and evidence: docs/BUILD_LOG.md § Phase 0 — Hermes v0.23.1 running, API signatures
  read from the installed source, ordering confirmed from the middleware guide
Preview/staging URL: N/A (no frontend)
Deployed commit: —
Reference image / UI skill: N/A (CLI plugin)
Documentation status: PROJECT_SPEC, ARCHITECTURE, IMPLEMENTATION_PLAN, AGENTS, BUILD_LOG
  (Phase 0 complete), OPERATOR_INTAKE (zero open critical items)
Demo video status: not started (<=90s, Phase 6)
Known issues:
  - PyPI hermes-agent 0.19.0 predates ctx.subagent_lifecycle; target is v0.23.1 and
    requires_hermes >= 0.23.0 (both plugin.yaml and catalog entry)
  - OPENROUTER_API_KEY is NOT set in this environment and ~/.hermes does not exist.
    Blocks a live model run and the recorded demo, not the build or validate.
  - Replay binding: child session_id is unknown at launch; bind via a nonce placed in
    SubagentLaunchRequest.context (design note DN-1 in docs/BUILD_LOG.md)
Authorization boundaries:
  no production deploy; no payments; no core modification;
  no writes outside $HERMES_HOME/replay-traces/
Next task: Phase 1 — plugin scaffold, record-only llm_execution + tool_execution, hooks,
  well-formed JSONL trace, hermes plugins validate exit 0
Blocked by: nothing
