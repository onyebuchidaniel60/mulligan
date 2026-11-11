# Demo production notes

## Environment used

| Item | Value |
|---|---|
| Hermes Agent | v0.23.1 (release tag `v0.23.1`) |
| Plugin pin | the commit this directory was recorded at (see `git rev-parse HEAD`) |
| Terminal | 110×32, dark theme, font 15–16pt |
| Capture | single continuous window, 1080p, 30fps |

## Why the baseline is a fixture

`demo/build_demo_trace.py` writes a recorded run in the plugin's real JSONL v1 format —
15 steps, failing at step 13 — with no model and no side effects. Using it for the
inspect/rewind/edit beats means the video is reproducible and contains no
operator-specific paths or prompts.

The **branch** is not a fixture: `mg_play` launches a real child session and runs the live
tail against the configured provider. That is the part that needs a credential.

## Recording checklist

1. `export HERMES_HOME=$HOME/.mulligan-demo` before starting Hermes, so the traces are
   separate from your real profile.
2. `python3 demo/build_demo_trace.py` — writes `r_demo_deploy`.
3. `mg_inspect` once off-camera so the terminal is warm and the output is scrolled to top.
4. Keep `mg_list` out of the video if the profile has other runs.
5. Re-check `mg_diff`'s run ids before the final take; `mg_play` prints the branch id.
6. Verify duration ≤90s and that audio actually plays before uploading.

## Failure modes to avoid on camera

- **"not_armed"** — `mg_rewind` must run in the same chat session as `mg_play`.
- **Branch re-prompts for approval** — expected for dangerous tools; the demo uses
  `read_file`, which never prompts.
- **DESYNC line in `mg_diff`** — the record no longer matches the child's calls; rebuild
  the fixture and re-record.

## Post-production

- Trim dead air only; keep the banner and the diff visible long enough to read.
- No music needed; if added, keep it under the narration.
- Burn in the tagline at 85–90s: "Rewind. Edit. Replay. Take a mulligan on any Hermes
  decision."
