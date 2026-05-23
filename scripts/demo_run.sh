#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "Usage: $0 'query A' 'query B' 'query C run 1' 'query C run 2' 'query D'" >&2
  exit 2
fi

UV_BIN="${UV_BIN:-uv}"
GATEWAY_URL="${LLM_GATEWAY_V3_URL:-http://localhost:8101}"
OUT="${OUT:-docs/demo_terminal_output.txt}"

mkdir -p docs

echo "Checking gateway at ${GATEWAY_URL}..."
if ! curl -fsS "${GATEWAY_URL}/v1/providers" >/dev/null; then
  echo "Gateway is not running. Start it in another terminal with:"
  echo "  ${UV_BIN} run python llm_gatewayV3/main.py"
  exit 1
fi

{
  echo "Demo captured on: $(date)"
  echo "Repository: https://github.com/taditya1997/eag-assignment-6"
  echo
  echo "Cleaning state..."
  ./scripts/clean_state.sh

  n=0
  for query in "$@"; do
    n=$((n + 1))
    echo
    if [[ $n -eq 4 ]]; then
      echo "===== Query C durable-memory recall run, keeping state ====="
    fi
    echo "===== Query ${n} ====="
    echo "QUERY: ${query}"
    "${UV_BIN}" run python agent6.py "${query}" --max-iterations 8
  done
} | tee "${OUT}"

echo
echo "Saved terminal output to ${OUT}"
