# Submission checklist

Status as of the last commit. Update this file, not the memories of the people involved.

## Build

- [x] Plugin loads through a real `PluginManager` (6 tools, 2 hooks, 3 middleware kinds)
- [x] `hermes plugins validate` exits 0
- [x] `hermes plugins doctor --ci` exits 0
- [x] stdlib only — no `python_dependencies`, no third-party imports
- [x] No `.pyc`, no binaries, no archives committed
- [x] Declared capabilities match registrations (validator diffs them)
- [x] `requires_hermes: ">=0.23.0"` in `plugin.yaml` and in the catalog entry

## Quality gates

- [x] Phase 2 GO/NO-GO: no-edit replay reproduces every step with **0 provider calls**,
      **0 tool invocations**, **0 bytes changed** in the record
- [x] Phase 3: rewind + edit + play branches live, records a new run, original untouched
- [x] Phase 4: `mg_diff` matches the demo fixture's numbers (15 steps, failure at 13,
      13 served + 2 live)
- [x] Tests drive the real middleware chain, not a re-implementation

## Submission package

- [x] `README.md` — determinism caveats + side-effect policy + disclosures
- [x] `submission/plugin-catalog/mulligan.yaml` — 40-char SHA pin
- [x] `submission/PR_BODY.md` — what it does, surfaces used, rule 13 disclosure
- [x] PR opened against `NousResearch/hermes-agent` (see `submission/PR_URL.txt`)
- [ ] ≤90s demo recorded on the pinned build (`demo/mulligan-90s.mp4`)
- [ ] Demo posted on X tagging `@NousResearch`
- [ ] Typeform submitted with the PR + video links

## Known limitation (documented, not hidden)

A live `ctx.subagent_lifecycle.launch` needs a provider credential, which is not present in
the build environment. The launch + binding + serving plumbing is covered with an inline
stand-in for the service; the end-to-end run is the operator's first step when recording.
