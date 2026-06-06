#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
SUFFIX="${SESSION_SUFFIX:-$(date +%Y%m%d%H%M%S)}"

run_query() {
  local title="$1"
  local session="$2"
  local query="$3"
  echo
  echo "===== ${title} ====="
  "$PYTHON_BIN" flow.py "$query" --session "${session}_${SUFFIX}"
}

run_query "Base hello" "s8_hello" "Say hello."

run_query "Base A - Shannon Wikipedia" "s8_A" \
  "Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory."

run_query "Base I - three city populations parallel fan-out" "s8_I" \
  "Find the populations of London, Paris, Berlin and tell me which two are closest in size."

run_query "Base J - graceful failure" "s8_J" \
  "Read /nonexistent/path.txt and tell me what's in it."

echo
echo "===== Base K - resume stop point ====="
"$PYTHON_BIN" flow.py \
  "For Lagos, Cairo, and Kinshasa, find current populations and growth rates and tell me which is growing fastest." \
  --session "s8_K_${SUFFIX}" \
  --stop-after-complete 4

echo
echo "===== Base K - resumed ====="
"$PYTHON_BIN" flow.py --resume "s8_K_${SUFFIX}"
