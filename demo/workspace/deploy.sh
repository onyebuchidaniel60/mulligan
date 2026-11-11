#!/bin/sh
set -eu
CONFIG="$1"
if [ ! -f "$CONFIG" ]; then
  echo "deploy: config not found: $CONFIG" >&2
  exit 2
fi
echo "deployed demo-service with $CONFIG"
