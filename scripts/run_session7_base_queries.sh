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
run_agent "Query A - Shannon Wikipedia" 3 "Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory."

./scripts/prepare_demo_corpus.sh
run_agent "Query B - Tokyo activities and weather" 8 "Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate."

./scripts/prepare_demo_corpus.sh
run_agent "Query C1 - Mom birthday remember" 4 "My mom's birthday is 15 May 2026. Remember that and create reminders for two weeks before and on the day."
run_agent "Query C2 - Mom birthday recall" 3 "When is mom's birthday?"

./scripts/prepare_demo_corpus.sh
run_agent "Query D - Asyncio synthesis" 6 "Search for \"Python asyncio best practices\", read the top 3 results, and give me a short numbered list of the advice they agree on."

./scripts/prepare_demo_corpus.sh
run_agent "Query E - Single-document index" 5 "Index the file papers/attention.md and tell me what the three key contributions of the Transformer architecture are according to this paper."

./scripts/prepare_demo_corpus.sh
run_agent "Query F1 - Index all papers" 11 "Index every .md file under papers/. Confirm how many chunks were indexed in total."
run_agent "Query F2 - Cross-run document recall" 3 "Across the papers I have indexed, what do they say about chain-of-thought reasoning?"
run_agent "Query G - Synonym recall" 4 "Across these papers, how do they handle the credit assignment problem?"
run_agent "Query H - Cross-document synthesis" 3 "Compare how the ReAct paper and the Chain-of-Thought paper differ in their treatment of intermediate reasoning."
