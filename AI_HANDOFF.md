# Mulligan — AI Handoff (current state)

Current phase: 6 — demo + submit (code and submission package complete)
Completed: Phase 0 (API verification), Phase 1 (scaffold + record-only),
  Phase 2 (GO/NO-GO exact reproduction: PASSED), Phase 3 (edit + branch),
  Phase 4 (inspect + diff on the demo fixture), Phase 5 (validate + catalog PR)
Tests and evidence: 15 tests OK; `hermes plugins validate` exit 0;
  `hermes plugins doctor --ci` exit 0; catalog entry validator OK.
  Details: docs/BUILD_LOG.md.
Preview/staging URL: N/A (no frontend)
Deployed commit: —
Pinned SHA: fef894a4552d72204c84665f67042467901f135a
Catalog PR: https://github.com/NousResearch/hermes-agent/pull/153805
Reference image / UI skill: N/A (CLI plugin)
Documentation status: complete (README, BUILD_LOG, SETUP, TESTING, CONFIGURATION,
  TROUBLESHOOTING, DESIGN_NOTES, demo plan + notes, submission package)
Demo video status: NOT RECORDED — shot list and fixture are ready
Known issues:
  - OPENROUTER_API_KEY is not set here and ~/.hermes does not exist, so the live branch
    and the demo recording are the operator's first step. The plugin never reads the key.
  - Hermes on PyPI is 0.19.0 and predates ctx.subagent_lifecycle; target v0.23.1 with
    requires_hermes >= 0.23.0 (plugin.yaml + catalog entry).
  - Replay binding uses a nonce in SubagentLaunchRequest.context (design note DN-1); a
    real child launch is untested end-to-end for lack of a credential.
  - mg_play waits synchronously for the child; a very long branch blocks until the timeout.
Authorization boundaries:
  no production deploy; no payments; no core modification;
  no writes outside $HERMES_HOME/replay-traces/
Next task: with a provider key — `python3 demo/build_demo_trace.py`, record the 90s demo,
  post on X tagging @NousResearch, submit the Typeform with the PR + video links
Blocked by: OPENROUTER_API_KEY (operator), X account (operator), Typeform (operator)
