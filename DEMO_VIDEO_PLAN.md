# Mulligan â€” Demo Video Plan

Target: <=90 seconds (hackathon limit, overrides the workflow's <=3min default).
Capture: manual screen recording (OBS / QuickTime). No Playwright â€” CLI only.

## Story (5 beats)
0-10s  Overlay: "The agent broke the build at step 12. Normally you re-run from scratch."
10-25s mg_inspect r_01 -- timeline shows 14 steps, red at 12 (wrong config path).
25-40s mg_rewind r_01 --to 9; mg_edit r_01 --seq 9 --args '{"path":"config/prod.yaml"}'
       -- fork marker appears on the timeline.
40-65s mg_play -- steps 1-8 flash by as "served from record, 0 model calls,
       0 side effects"; step 9 executes live; loop continues; agent succeeds at 13.
65-80s mg_diff r_01 r_02 -- side-by-side: red 14 steps / failed at 12
       vs green 11 steps / passed. "8 steps deterministic, 3 live."
80-90s Tagline: "Rewind. Edit. Replay. Take a mulligan on any Hermes decision."

## Narration
Concise, tied to visible actions. No narration describing something not on screen.
Keep one continuous voice track; no long silences.

## Redaction
- Blur or omit any trace content that could leak operator-specific paths or prompts
- No API keys, no private URLs
- Use the scripted demo trace only

## Output
- File: demo/mulligan-90s.mp4
- Script: demo/script.md
- Production notes: demo/notes.md
- Verify: duration <=90s, audio plays, video plays

## Submission
- Post on X, tag @NousResearch
- Submit Typeform with PR link + video link
- Deadline: 5PM EST Nov 11
