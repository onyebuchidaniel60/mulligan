# Setup

## Prerequisites
- Python 3.11+
- Hermes Agent **>= 0.23.0** (`ctx.subagent_lifecycle`; 0.19.0 and older do not have it)
- `OPENROUTER_API_KEY` (or any configured provider) in the Hermes profile — only needed to
  record a live run and to execute a branch

## Install the plugin
```
cp -r mulligan ~/.hermes/plugins/
hermes plugins validate ~/.hermes/plugins/mulligan
hermes plugins enable mulligan
```

From the catalog, `hermes plugins install mulligan` does the same at a pinned commit.

## Configure the provider
```
hermes chat --provider openrouter --model '~anthropic/claude-sonnet-latest'
```
Use a model with >=64K context (tool schemas + history).

## Verify
```
hermes plugins list                      # mulligan enabled
ls -lh "${HERMES_HOME:-$HOME/.hermes}/replay-traces/"
mg_list                                  # inside a chat session
```

## Deterministic demo without a provider
```
HERMES_HOME=/tmp/mulligan-demo python3 demo/build_demo_trace.py --with-branch-fixture
```
Then point Hermes at that `HERMES_HOME` and use `mg_inspect` / `mg_rewind` / `mg_edit` /
`mg_diff` on `r_demo_deploy`. `mg_play` still needs a provider for the live branch.
