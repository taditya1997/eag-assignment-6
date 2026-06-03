#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"

run_agent() {
  local label="$1"
  local max_iterations="$2"
  local query="$3"
  echo
  echo "===== ${label} ====="
  echo "${query}"
  if ! "${PYTHON_BIN}" agent6.py "${query}" --max-iterations "${max_iterations}"; then
    echo "First attempt failed, waiting 25s for provider recovery and retrying ${label}..."
    sleep 25
    "${PYTHON_BIN}" agent6.py "${query}" --max-iterations "${max_iterations}"
  fi
}

./scripts/prepare_demo_corpus.sh

run_agent "Custom index - 50-card corpus" 5 "Index the file corpus/solar_support_field_guide.md. Confirm that the coastal solar support field guide is searchable."

run_agent "Custom Q1 - Exact standard recall" 4 "In the indexed field guide, what warning is given about ASTM B117 salt spray data?"
run_agent "Custom Q2 - Exact coating recall" 4 "In the indexed field guide, what does it say about Z275 coating near chloride sources?"
run_agent "Custom Q3 - Semantic recall: pretty surface, weak joint" 4 "Which indexed card explains why a shiny-looking rail can still hide a joint reliability problem after damp seaside mornings?"
run_agent "Custom Q4 - Semantic recall: work repeats after handoff" 4 "Which indexed cards explain why crews repeat old work and miss new problems after maintenance handoffs?"
run_agent "Custom Q5 - Multi-card evidence bundle" 4 "Across the indexed field guide, what evidence should a good support defect report include, and why are context photos important?"

echo
echo "===== No-corpus comparison ====="
if ! "${PYTHON_BIN}" agent6.py "Across the indexed field guide, what warning is given about ASTM B117 salt spray data?" --reset-state --max-iterations 3; then
  echo "First no-corpus comparison failed, waiting 25s for provider recovery and retrying..."
  sleep 25
  "${PYTHON_BIN}" agent6.py "Across the indexed field guide, what warning is given about ASTM B117 salt spray data?" --reset-state --max-iterations 3
fi
