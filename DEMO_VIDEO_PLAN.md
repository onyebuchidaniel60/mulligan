# Mulligan — Demo (≤90s)

## Pre-recording status

Executed 2026-11-11/12. Raw commands and output: `docs/BUILD_LOG.md` § Phase 6 execution.

| Step | Result |
|---|---|
| **1. Credential** | `grep -c '^OPENROUTER_API_KEY=' ~/.hermes/.env` → **1** (present; value never printed) |
| **2. Demo trace** | `r_demo_deploy` — **15 steps** (seq 0..14), first error at **13** (`read_file config/prod.yml`) |
| **3. Plugin installed** | copied to `~/.hermes/plugins/mulligan`, `hermes plugins enable mulligan` → **enabled**, v0.1.0 |
| **4. Real `hermes chat` dry run** | **PASSED** — real trace `r_20261111-222558_7697`, 5 steps, `read_file` File-not-found at step 1, annotated `error` by `post_tool_call` |
| **5. Video** | `demo/mulligan-90s.mp4` — **43.8 s**, 1600×900, H.264, **no audio track** (VHS records silent; add narration separately) |
| **SHA pin** | unchanged at `fef894a4552d72204c84665f67042467901f135a`; HEAD is newer. Accepted as-is; the PR was not touched |
| **Fixture-to-plan check** | Plan and fixture agree: **15 steps, fails at 13**. The brief's "14 steps" is wrong — the fixture is ground truth |

### What the live replay actually did

`mg_play` in a real child session: **13 steps served (7 llm + 6 tool), 0 provider calls,
0 tool invocations, no DESYNC**, then `2–4` live steps depending on what the model does
after the edit. Reproduced twice, `~6–9s` per replay.

### A real defect the dry run caught (fixture, not plugin)

The first live replay desynced at step 1. The **plugin recorded correctly** — in the real
trace every tool step's `tool_call_id` matches the id in the preceding assistant message.
The **fixture** did not: it derived `tool_call_id` from the step index and used tool names
Hermes does not have (`list_files`, `grep`), which Hermes auto-repaired (`list_files` →
`write_file`), so the child's calls never matched. Fixed in `demo/build_demo_trace.py`:
ids are taken from the preceding assistant message, and only real tools
(`read_file`, `search_files`) are used. Step count and failure index unchanged.

The first branch also showed the model deploying with `config/staging.yaml` even after the
edit, so the branch failed elsewhere. The fixture goal and failing path were made coherent
(`config/prod.yml` → edited to `config/prod.yaml`), and the demo workspace was moved out of
the repo so it does not inherit `AGENTS.md` ("no production deploy").

## Recording

VHS tape: `demo/mulligan.tape` → `demo/mulligan-90s.mp4`

```bash
cd /root/mulligan && vhs demo/mulligan.tape
```

The tape drives real commands: `demo/mg.py` calls the installed plugin's tool handlers and
prints their exact output; the replay beat runs a real `hermes chat --oneshot` session
against `~/.hermes/replay-traces/r_demo_deploy.jsonl`.

VHS needs a browser for its renderer; under root it must run sandboxless (the local
Chromium was wrapped with `--no-sandbox`). Not a plugin concern — a recording-tool concern.

## Story (as recorded)

**Title** — "MULLIGAN · Take a mulligan on any Hermes decision." A recorded run: 15 steps,
breaks at step 13.

**`mg_list`** — one run in `~/.hermes/replay-traces`.

**`mg_inspect r_demo_deploy`** — 15-step timeline, red at 13
(`read_file({"path": "config/prod.yml"})` → FileNotFoundError), "first failing step: 13".

**Rewind / edit / replay** — a real chat session calls `mg_rewind`, `mg_edit`, `mg_play`.
On screen: `before {"path": "config/prod.yml"}` / `after {"path": "config/prod.yaml"}`,
the replay banner, `Served: 7 llm + 6 tool steps (13 total)`, `Live: … (model-dependent)`.

**`mg_diff r_demo_deploy latest`** — A: 15 steps, FAILED at 13. B: branch, no failing step.
"steps 0..12 served deterministically, N executed live", first divergence at 13
(different tool arguments), then the side-by-side table with `≠` at step 13.

**Tagline** — "Rewind. Edit. Replay. Take a mulligan on any Hermes decision."

## Narration

Optional for the technical demo (the tape is silent). If added, keep it tied to what is on
screen and under 90s total. Suggested lines:

- 0–6s: "The agent broke at step 13. Normally you re-run from scratch."
- 6–18s: "Mulligan recorded every LLM call and tool call. Here's the timeline — red at 13."
- 18–32s: "Rewind to 13, change one decision: prod.yml becomes prod.yaml."
- 32–40s: "Replay runs in a fresh child session. Thirteen steps served from the record,
  zero provider calls, zero side effects. Only the edited step and after run live."
- 40–50s: "Diff: same run on the left, counterfactual on the right, first divergence at 13."

## Redaction

- The fixture contains no real paths, prompts, or operator data.
- Never show `OPENROUTER_API_KEY`, `~/.hermes/.env`, or `auth.json`.
- The recording uses `~/.hermes` as the profile; traces from other sessions were removed
  before the take.

## Output

- `demo/mulligan-90s.mp4` — 43.8s, 1600×900, silent
- `demo/mulligan.tape` — the reproducible tape
- `demo/query.txt` — the chat prompt used in the replay beat
- `demo/mg.py` — CLI over the real tool handlers
- `demo/build_demo_trace.py` — deterministic fixture
- `demo/notes.md` — production notes

## Remaining operator actions

1. Optional: add narration to `demo/mulligan-90s.mp4` (it is silent).
2. Post on X tagging `@NousResearch`.
3. Submit the Typeform with the PR link
   (https://github.com/NousResearch/hermes-agent/pull/153805) and the video.
