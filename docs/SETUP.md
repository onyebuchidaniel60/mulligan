# Setup

## Prerequisites
- Python 3.11+
- Git + git-lfs
- uv
- Hermes Agent installed
- OPENROUTER_API_KEY in ~/.hermes/.env

## Install the plugin
    cp -r mulligan ~/.hermes/plugins/
    hermes plugins validate

## Configure the provider
    # ~/.hermes/.env
    OPENROUTER_API_KEY=sk-or-...

    # ~/.hermes/config.yaml
    model:
      provider: openrouter
      default: ~anthropic/claude-sonnet-latest

Use a model with >=64K context (tool schemas + history).

## Verify
    hermes chat --provider openrouter --model '~anthropic/claude-sonnet-latest'
    ls -lh "${HERMES_HOME:-$HOME/.hermes}/replay-traces/"
