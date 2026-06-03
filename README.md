# Agent 6 Assignment

Four-layer agent for the Session 6 target queries:

- `perception.py` extracts the user goal into a typed Pydantic contract.
- `memory.py` persists durable facts in `state/memory.json` and retrieves them through a typed memory contract.
- `decision.py` selects exactly one typed next action.
- `action.py` executes tools through the provided MCP server over stdio.
- `agent6.py` wires the layers into a loop.
- `schemas.py` contains the Pydantic v2 contracts used at every boundary.

All LLM calls go through `llm_gatewayV3` on `http://localhost:8101`. The agent does not call provider SDKs directly.

## Session 7 RAG Additions

Session 7 keeps the four-layer architecture intact and adds vector retrieval
under Memory:

- `POST /v1/embed` on the gateway returns 768-dimensional embeddings.
- `MemoryFact.embedding` stores optional vectors for durable facts and indexed chunks.
- `state/index.faiss` and `state/index_ids.json` persist the FAISS index beside `state/memory.json`.
- `index_document(path)` chunks a sandbox document into searchable Memory facts.
- `search_knowledge(query, k)` searches previously indexed chunks.

Perception remains tool-blind. Tool-selection guidance lives in Decision and in
the MCP tool docstrings.

## Assignment Demo Runbook

This repo is prepared for the Session 7 RAG assignment demo.

## Submission Summary

This project extends the Session 6 four-role agent with Session 7 vector
retrieval while preserving the original architecture:

- Perception stays tool-blind and emits intent-level task state.
- Decision chooses one next action and sees the MCP tool catalogue.
- Action dispatches MCP tools.
- Memory stores durable facts and indexed document chunks.
- The gateway exposes `/v1/embed` for 768-dimensional embeddings.
- FAISS persists vector search state in `state/index.faiss` plus
  `state/index_ids.json`.

The custom RAG application is a document-retrieval demo over a 50-item corpus:
`demo_corpus/custom/solar_support_field_guide.md`. It contains 50 compact
incident cards about coastal solar support inspection, corrosion, coating
limits, torque records, handoff problems, and defect-report evidence.

The demo proves both exact retrieval and semantic retrieval. Exact queries ask
about terms like `ASTM B117` and `Z275`. Semantic queries use different wording
from the source cards, such as "shiny-looking rail" and "crews repeat old work",
and vector retrieval still returns the right cards.

## Submitted Logs

The captured terminal logs are committed under `docs/`:

- `docs/custom_rag_traces.txt` - complete custom RAG demo:
  - indexes the 50-card field guide;
  - confirms vector search with cosine similarity;
  - answers five custom queries;
  - includes the no-corpus comparison after reset.
- `docs/custom_no_corpus_trace.txt` - standalone no-corpus comparison trace.
- `docs/base_query_a_trace.txt` - base Query A smoke trace.
- `docs/base_query_b_trace.txt` - base Query B smoke trace.
- `docs/session7_base_traces.txt` - captured base-query run log from local
  testing.

Important excerpts from the complete custom trace:

```text
Custom index:
chunks_indexed: 4
reason: vector search cosine similarity 0.779

Custom Q1:
ASTM B117 salt spray data is comparative, not a complete service-life prediction.

Custom Q2:
Z275 sheet coating is not a universal marine answer near chloride sources.

Custom Q3 semantic recall:
Card 01 explains that a rail can look clean while chloride film remains underside.

Custom Q4 semantic recall:
Card 13 and Card 33 explain handoff drift and repeated old work.

Custom Q5 synthesis:
A defect report should include row ID, weather, close photo, context photo,
torque value, coating reading, and repair decision.

No-corpus comparison:
search_knowledge returned result: []
final answer: no available matching evidence.
```

### Start the gateway

Terminal 1:

```bash
cd "/Users/adityathakur/Desktop/Personal Project/eag-assignment-6"
.venv/bin/python llm_gatewayV3/main.py
```

Health checks:

```bash
curl -s http://localhost:8101/v1/providers | python3 -m json.tool
curl -s http://localhost:8101/v1/embedders | python3 -m json.tool
```

### Prepare the sandbox corpus

Terminal 2:

```bash
cd "/Users/adityathakur/Desktop/Personal Project/eag-assignment-6"
./scripts/prepare_demo_corpus.sh
```

This resets `state/`, recreates `sandbox/`, and copies the demo corpora into
the MCP sandbox.

### Run the eight base queries

```bash
./scripts/run_session7_base_queries.sh | tee docs/session7_base_traces.txt
```

The script runs queries A through H with the iteration limits from the Session 7
brief. Queries F2, G, and H intentionally reuse the index produced by F1.

### Run the custom RAG corpus demo

```bash
./scripts/run_custom_rag_queries.sh | tee docs/custom_rag_traces.txt
```

The custom demo indexes a 50-card field guide and then asks five questions. Q3
and Q4 are semantic-recall questions whose wording does not match the relevant
card titles directly.

## Corpus Manifest

Base paper corpus copied to `sandbox/papers/`:

- `attention.md` - Transformer contributions: self-attention, multi-head attention, parallel sequence computation, positional encodings.
- `chain_of_thought.md` - Linear intermediate reasoning traces and stepwise inference.
- `react.md` - Interleaved reasoning, actions, and observations.
- `dpo.md` - Preference optimization and pairwise training signals.
- `lora.md` - Parameter-efficient adaptation through low-rank updates.

Custom RAG corpus copied to `sandbox/corpus/`:

- `solar_support_field_guide.md` - 50 incident cards about coastal solar support inspection, corrosion, maintenance evidence, FRP, HDG/Z275, ASTM B117 caveats, torque records, isolation, and handoff failures.

## Custom Query Set

These five queries are used by `scripts/run_custom_rag_queries.sh`:

1. `In the indexed field guide, what warning is given about ASTM B117 salt spray data?`
2. `In the indexed field guide, what does it say about Z275 coating near chloride sources?`
3. `Which indexed card explains why a shiny-looking rail can still hide a joint reliability problem after damp seaside mornings?`
4. `Which indexed cards explain why crews repeat old work and miss new problems after maintenance handoffs?`
5. `Across the indexed field guide, what evidence should a good support defect report include, and why are context photos important?`

No-corpus comparison:

```bash
.venv/bin/python agent6.py \
  "Across the indexed field guide, what warning is given about ASTM B117 salt spray data?" \
  --reset-state --max-iterations 3
```

With an empty Memory index, `search_knowledge` has no chunks to return. The
agent should either say it cannot answer from indexed knowledge or provide an
unsupported/empty result, which is the comparison point for the indexed run.

## Architecture Proof

Perception must stay tool-blind:

```bash
rg -n "web_search|fetch_url|get_time|currency_convert|read_file|list_dir|create_file|update_file|edit_file|index_document|search_knowledge|remember|final_answer" perception.py
```

Expected result: no matches.

## Setup

Install dependencies with uv:

```bash
uv --version
uv sync
```

Create your local env file and add at least one working gateway provider key:

```bash
cp .env.example .env
```

`mcp_server.py` also reads this `.env`. `TAVILY_API_KEY` is optional; without it, `web_search` falls back to DDG.

If `fetch_url` fails because Chromium is missing, run the Crawl4AI setup once:

```bash
uv run crawl4ai-setup
```

## Run The Gateway

Start LLM Gateway V3 in one terminal:

```bash
uv run python llm_gatewayV3/main.py
```

Check it:

```bash
curl -s http://localhost:8101/v1/routers | python -m json.tool
```

## Run A Query

In another terminal:

```bash
uv run python agent6.py "YOUR QUERY HERE"
```

Useful flags:

```bash
uv run python agent6.py "YOUR QUERY HERE" --reset-state
uv run python agent6.py "YOUR QUERY HERE" --max-iterations 8
uv run python agent6.py "YOUR QUERY HERE" --quiet
```

Clean state between attempts:

```bash
./scripts/clean_state.sh
```

## Record The Working Demo

Start the gateway in terminal 1:

```bash
uv run python llm_gatewayV3/main.py
```

Run and capture the four-query demo in terminal 2:

```bash
./scripts/demo_run.sh \
  "TARGET QUERY A" \
  "TARGET QUERY B" \
  "TARGET QUERY C RUN 1" \
  "TARGET QUERY C RUN 2" \
  "TARGET QUERY D"
```

This writes `docs/demo_terminal_output.txt`. Use the same terminal session for the YouTube screen recording.

## Four Target Queries

The exact four target query texts were not included in the files supplied to this workspace. Once you paste the assignment's four query strings, run:

```bash
./scripts/run_four_queries.sh \
  "TARGET QUERY A" \
  "TARGET QUERY B" \
  "TARGET QUERY C RUN 1" \
  "TARGET QUERY C RUN 2" \
  "TARGET QUERY D"
```

For Query C's durable-memory check, do not clean `state/` between run 1 and run 2. The first run writes `state/memory.json`; the second run reads it.

## Captured Output

Paste the clean-state terminal output for the real four target queries here after running them on your machine with API keys configured.

```text
TARGET QUERY A OUTPUT:
<not captured here because the target query text and provider keys were not supplied>

TARGET QUERY B OUTPUT:
<not captured here because the target query text and provider keys were not supplied>

TARGET QUERY C RUN 1 OUTPUT:
<not captured here because the target query text and provider keys were not supplied>

TARGET QUERY C RUN 2 OUTPUT:
<not captured here because the target query text and provider keys were not supplied>

TARGET QUERY D OUTPUT:
<not captured here because the target query text and provider keys were not supplied>
```

## Prompt And Validation JSON

Generate the perception and decision prompt/schema proof file:

```bash
uv run python scripts/export_pop_validation.py
```

The generated file is `docs/pop_validation.json`.

## YouTube Demo

Add the YouTube demonstration link here after recording the four end-to-end runs:

```text
YouTube: <paste link>
```
