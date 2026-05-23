#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 || $# -gt 5 ]]; then
  echo "Usage: $0 'query A' 'query B' 'query C run 1' 'query C run 2' ['query D']" >&2
  exit 2
fi

./scripts/clean_state.sh

n=0
for query in "$@"; do
  n=$((n + 1))
  echo
  if [[ $n -eq 4 ]]; then
    echo "===== Query C durable recall run, keeping state ====="
  fi
  echo "===== Query ${n} ====="
  echo "$query"
  uv run python agent6.py "$query"
done
