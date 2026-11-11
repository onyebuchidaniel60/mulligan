# Mulligan — AI Handoff (current state)

Current phase: 4 — inspect + diff (demo trace)
Completed: Phase 0 (API verification), Phase 1 (scaffold + record-only),
  Phase 2 (GO/NO-GO exact reproduction: PASSED), Phase 3 (edit + branch)
Tests and evidence: `python3 -m unittest discover -s tests -v` → 14 tests OK.
  `hermes plugins validate /root/mulligan` → exit 0.
  Details with the measured invariants: docs/BUILD_LOG.md § Phase 1-3.
Preview/staging URL: N/A (no frontend)
Deployed commit: —
Reference image / UI skill: N/A (CLI plugin)
Documentation status: PROJECT_SPEC, ARCHITECTURE, IMPLEMENTATION_PLAN, AGENTS,
  BUILD_LOG (Phase 0-3), OPERATOR_INTAKE (zero open critical items)
Demo video status: script drafted (demo/script.md), not recorded
Known issues:
  - OPENROUTER_API_KEY is NOT set in this environment and ~/.hermes does not exist.
    Blocks a live model run and the recorded demo. The plugin never reads the key.
  - Hermes 0.19.0 on PyPI predates ctx.subagent_lifecycle; target is v0.23.1 with
    requires_hermes >= 0.23.0 (plugin.yaml and catalog entry).
  - Replay binding uses a nonce in SubagentLaunchRequest.context (design note DN-1).
    A real child launch needs a provider credential; the binding + serving path is
    proven with an inline fake of ctx.subagent_lifecycle in tests.
  - mg_play waits synchronously for the child; a very long branch will block the tool
    call until the timeout (documented in README).
Authorization boundaries:
  no production deploy; no payments; no core modification;
  no writes outside $HERMES_HOME/replay-traces/
Next task: Phase 4 — generate the demo trace, verify mg_inspect / mg_diff output
  matches the demo narration numbers, then README + catalog entry + PR
Blocked by: nothing
