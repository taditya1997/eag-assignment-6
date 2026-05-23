# Agent 6 Assignment

Four-layer agent for the Session 6 target queries:

- `perception.py` extracts the user goal into a typed Pydantic contract.
- `memory.py` persists durable facts in `state/memory.json` and retrieves them through a typed memory contract.
- `decision.py` selects exactly one typed next action.
- `action.py` executes tools through the provided MCP server over stdio.
- `agent6.py` wires the layers into a loop.
- `schemas.py` contains the Pydantic v2 contracts used at every boundary.

All LLM calls go through `llm_gatewayV3` on `http://localhost:8101`. The agent does not call provider SDKs directly.

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
