# Mulligan â€” Persistent implementation rules

## Source of truth
docs/PROJECT_SPEC.md, docs/ARCHITECTURE.md, docs/IMPLEMENTATION_PLAN.md.
Architecture is FIXED. Do not redesign. Do not expand scope.

## Autonomy
- Run ONE consolidated operator intake before coding (Phase 0).
- Then execute Phases 1-6 sequentially and continuously.
- No routine approval stops. No mockup gates. No phase-by-phase prompts.
- Stop ONLY for:
    * a Phase 0 API answer that invalidates the fixed architecture
    * missing critical credential with no safe fallback
    * a serious security/data-loss risk
    * an action outside granted authority (production deploy, payments, etc.)

## Hard boundaries (non-negotiable)
- Never modify Hermes core. Public ctx APIs only.
- Never read .env / auth.json directly.
- Never bypass Hermes approvals.
- Never write outside $HERMES_HOME/replay-traces/.
- Never fetch or replace plugin files at runtime (no self-update).
- Pure Python stdlib only. No .pyc, no binaries, no archives.

## Quality gates (internal, not approval stops)
- Phase 2: exact-reproduction test passes (0 provider calls, 0 side effects).
- Phase 4: mg_diff matches the demo's claims on the demo trace.
- Phase 5: hermes plugins validate exits 0; 40-char SHA pinned.

## Evidence discipline
At each checkpoint, record:
  - test output
  - commit SHA
  - update to docs/AI_HANDOFF.md
  - update to docs/BUILD_LOG.md
Never claim success without evidence. If a test cannot be run, state why.

## Submission (Phase 6)
- <=90s demo posted on X, tagged @NousResearch
- PR opened against NousResearch/hermes-agent plugin catalog
- Typeform submitted
- Deadline: 5PM EST Nov 11

## N/A
No frontend. No database. No auth system. No payments. No deployment targets
beyond the catalog PR. Do not invent these.
