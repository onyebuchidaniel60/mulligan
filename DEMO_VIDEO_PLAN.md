# Mulligan — Demo (≤90s)

Capture: manual screen recording (OBS / QuickTime). No Playwright — CLI only.
Deadline: 5PM EST Nov 11.

## Reality check on the numbers

The demo fixture has **15 steps** and fails at **step 13**. A replay to that point serves
**13 steps deterministically** and executes **2 live**. These are the numbers from
`demo/build_demo_trace.py` and `mg_diff`; do not narrate different ones.

## Prep (once, before recording)

```bash
export HERMES_HOME=$HOME/.mulligan-demo
mkdir -p "$HERMES_HOME"
python3 demo/build_demo_trace.py          # writes r_demo_deploy (15 steps, fails at 13)
hermes plugins enable mulligan
hermes chat --provider openrouter --model '~anthropic/claude-sonnet-latest'
```

The baseline is a fixture so the inspect/rewind/edit beats never drift. The *branch* is a
real live run and needs `OPENROUTER_API_KEY`.

## Story (5 beats)

**0–10s — the problem**
Overlay: "The agent broke at step 13. Normally you re-run from scratch."

**10–28s — inspect**
```
mg_inspect run_id=r_demo_deploy
```
Timeline: 15 steps, red at 13 (`read_file config/staging.yaml` → FileNotFoundError).

**28–42s — rewind + edit**
```
mg_rewind run_id=r_demo_deploy to=13
mg_edit run_id=r_demo_deploy seq=13 args={"path":"config/prod.yaml"}
```
Point at the "before / after" lines.

**42–70s — play**
```
mg_play run_id=r_demo_deploy
```
The banner prints. Steps 0–12 flash past as "served from the record, 0 provider calls,
0 side effects". Step 13 executes live with the edited path and succeeds; the loop
continues live to the answer.

**70–85s — diff**
```
mg_diff run_a=r_demo_deploy run_b=<branch id printed by mg_play>
```
Side by side: A fails at 13, B has no failing step, "steps 0..12 served deterministically,
2 executed live", first divergence at step 13 (different tool arguments).

**85–90s — tagline**
"Rewind. Edit. Replay. Take a mulligan on any Hermes decision."

## Narration

Tied to what is on screen. One continuous voice track, no long silences, no describing
anything that is not visible.

## Redaction

- Use the fixture baseline only; it contains no real paths or prompts.
- Never show `OPENROUTER_API_KEY`, `~/.hermes/.env`, or `auth.json`.
- If a live branch prints a provider error, cut and re-record; do not show keys.

## Output

- `demo/mulligan-90s.mp4` (≤90s, audio + video verified)
- `demo/script.md` (this file)
- `demo/notes.md` (production notes)

## Submission

- Post on X tagging `@NousResearch`
- Submit the Typeform with the PR link + video link
