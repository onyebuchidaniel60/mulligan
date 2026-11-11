# Deployment

N/A â€” this is a plugin, not a deployed service.

## Distribution
- Open a PR against NousResearch/hermes-agent plugin catalog
- Catalog entry is a single .yaml file pinned to a 40-char commit SHA
- Human maintainer review; no self-serve registry
- Updates require a new PR that bumps the SHA and is re-reviewed

## Install for users
    hermes plugins install mulligan

## No production deployment
There is no production environment. The catalog listing IS the distribution.
