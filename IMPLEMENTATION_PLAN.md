# Mulligan â€” Implementation Plan

Phases are internal checkpoints. Test -> fix -> commit -> update AI_HANDOFF.md -> continue.
No routine operator approval stops. The only gate is Phase 0 API verification.

## Phase 0 â€” API verification spike (HARD GATE)
Objective: resolve the four API unknowns; complete OPERATOR_INTAKE.md.
Tasks:
  (a) Confirm ctx.register_middleware signature and callback kwargs
      (request, original_request, next_call, tool_name, args, session_id)
  (b) Confirm ctx.subagent_lifecycle.launch / SubagentLaunchRequest fields
      and whether plugin-module state is visible inside the child session
  (c) Confirm middleware ordering relative to approvals
      (does tool_execution run AFTER approval checks?)
  (d) Confirm ctx.register_tool handler signature and return contract
Acceptance: all four answers recorded with a doc citation in docs/BUILD_LOG.md;
            OPERATOR_INTAKE.md has zero open critical items.
Blocker rule: if any answer invalidates the fixed architecture, STOP and report.
Files: docs/BUILD_LOG.md, OPERATOR_INTAKE.md, AI_HANDOFF.md
Next: Phase 1

## Phase 1 â€” Scaffold + record-only
Objective: plugin loads, records traces.
Tasks: __init__.py, state.py, record-only llm_execution + tool_execution, hooks.
Acceptance: a 3-step scripted run produces a well-formed trace; validate passes.
Commit: feat: scaffold mulligan and record-only middleware
Next: Phase 2

## Phase 2 â€” Serve / exact reproduction (GO/NO-GO)
Objective: prove R1 + R2.
Tasks: take(), mg_rewind, mg_play (child launch), serving branch in middleware.
Acceptance: exact-reproduction test passes (identical step sequence, zero usage on
            served steps, zero tool invocations while serving).
Commit: feat: replay-to-point with exact reproduction
Next: Phase 3

## Phase 3 â€” Edit + branch
Objective: the differentiator works.
Tasks: mg_edit, branch-at-cursor live execution, edit guards.
Acceptance: rewinding to the failing step and editing the arg makes the branch succeed;
            branch trace is recorded to a new run_id.
Commit: feat: branch execution from edited step
Next: Phase 4

## Phase 4 â€” Inspect + diff
Objective: demo-grade output.
Tasks: mg_list, mg_inspect timeline, mg_diff side-by-side.
Acceptance: mg_diff reproduces the demo's numeric claims on the demo trace.
Commit: feat: inspector and counterfactual diff
Next: Phase 5

## Phase 5 â€” Validation + submission package
Objective: catalog-ready.
Tasks: README (determinism + side-effect policy), catalog entry YAML with 40-char SHA,
       hermes plugins validate clean, PR opened.
Acceptance: validate exit 0; PR open; entry pinned.
Commit: docs: README and catalog entry
Next: Phase 6

## Phase 6 â€” Demo + submit
Objective: submitted before 5PM EST Nov 11.
Tasks: record <=90s screen capture on the pinned build; post on X tagging
       @NousResearch; submit Typeform with PR + video links.
Acceptance: all three links exist and resolve.

## N/A phases (documented as skipped, not silently dropped)
- Phase 1 skeletal frontend + preview deploy: no frontend
- Phase 2 backend/DB/auth: no backend
- Phase 6 stageshow UI skill: no UI
- Phase 7 responsive/a11y/metadata/footer: no UI
- Phase 8 Playwright + Google TTS + <=3min: replaced by <=90s manual capture
- Phase 9 production release: replaced by catalog PR
