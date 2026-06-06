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

run_query "Custom parallel fan-out" "s8_parallel" \
  "Parallel fan-out demo: compare corrosion risks for aluminum rails, FRP supports, and galvanized brackets."

run_query "Critic verdict pass" "s8_critic_pass" \
  "Critic pass: produce exactly three safety checks for coastal solar supports."

run_query "Critic verdict fail with recovery" "s8_critic_fail" \
  "Critic fail: produce exactly three safety checks for coastal solar supports."

run_query "Coder computation demo" "s8_coder" \
  "Coder computation demo: which two project budgets are closest among Alpha 128750, Beta 130500, Gamma 221000, and Delta 129100?"

run_query "New tabulator skill" "s8_tabulator" \
  "Tabulate the Session 8 demo evidence for base, parallel, critic, coder, and new-skill requirements."
