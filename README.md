# Mulligan

Take a mulligan on any Hermes decision.

A Hermes Agent plugin that records runs, rewinds to any step, edits a decision,
and replays forward to compare counterfactual outcomes.

## What it does
- Records every LLM call and tool call to JSONL under $HERMES_HOME/replay-traces/
- mg_inspect shows a step-by-step timeline
- mg_rewind + mg_edit + mg_play re-executes from an edited past
- mg_diff compares the original and branch side by side

## The invariant that matters
Replaying with NO edit reproduces the original run step-for-step with:
- ZERO provider calls on served steps
- ZERO tool side effects on served steps

Only the branch (from the edited step forward) runs live.

## Determinism caveats
- The branch resamples the model. A counterfactual is *a* what-if, not *the* what-if.
- Parallel tool calls are ordered by tool_call id; sequential runs are exact.
- Traces are append-only; never mutated.

## Side-effect policy
- Replay-to-point is side-effect-free.
- Branch execution is LIVE. Approvals fire normally.
- mg_play prints a loud banner before launching the child session.

## Install
    cp -r mulligan ~/.hermes/plugins/
    hermes plugins validate

## Tools
    mg_list, mg_inspect, mg_rewind, mg_edit, mg_play, mg_diff

## N/A
No frontend, no database, no auth, no payments. Pure Python stdlib.
