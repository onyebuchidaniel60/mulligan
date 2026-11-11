# Mulligan — AI Handoff (current state)

Current phase: 6 — demo recorded; submission is operator-only
Completed: Phase 0 (API verification), Phase 1 (scaffold + record-only),
  Phase 2 (GO/NO-GO exact reproduction: PASSED), Phase 3 (edit + branch),
  Phase 4 (inspect + diff), Phase 5 (validate + catalog PR),
  Phase 6 (real dry run PASSED, live replay PASSED, 43.8s demo recorded)
Tests and evidence: 16 tests OK; `hermes plugins validate` exit 0;
  `hermes plugins doctor --ci` exit 0; real `hermes chat` trace with an error step;
  live `mg_play` 13 served / 0 provider calls / no desync.
  Raw commands and output: docs/BUILD_LOG.md § Phase 6 execution.
Preview/staging URL: N/A (no frontend)
Deployed commit: —
HEAD: see `git rev-parse HEAD` (docs + demo assets ahead of the pin; accepted)
Pinned SHA: fef894a4552d72204c84665f67042467901f135a  (PR untouched)
Catalog PR: https://github.com/NousResearch/hermes-agent/pull/153805
Reference image / UI skill: N/A (CLI plugin)
Documentation status: complete
Demo video status: RECORDED — demo/mulligan-90s.mp4, 43.8s, 1600x900, silent
Known issues:
  - The video has no audio track (VHS is silent); narration is optional and the
    operator's call.
  - The live tail after the branch point is model-dependent (2-4 steps observed), so
    `mg_diff`'s live count varies; the plan states this.
  - mg_play waits synchronously for the child (6-9s observed; timeout default 600s).
  - Mulligan needs plugins.isolation: in_process (the default); under host isolation the
    child would not see the armed replay.
Authorization boundaries:
  no production deploy; no payments; no core modification;
  no writes outside $HERMES_HOME/replay-traces/
Next task: operator posts on X tagging @NousResearch and submits the Typeform with the PR
  and video links
Blocked by: nothing on the engineering side
