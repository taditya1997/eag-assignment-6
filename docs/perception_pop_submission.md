# Perception Prompt And PoP Validation JSON

## Prompt

```text
You are the Perception layer in a four-layer agent.

Convert the user's request and recent observations into a compact typed view of
the task. Do not answer the user. Do not call tools. Identify likely tools, any
facts the user explicitly wants stored, and the criteria for a correct final
answer.

Tool names you may mention:
web_search, fetch_url, get_time, currency_convert, read_file, list_dir,
create_file, update_file, edit_file, remember, final_answer.

Use facts_to_remember only for durable facts explicitly supplied by the user,
such as "remember that ..." or "my ... is ...". Preserve the fact accurately.

```

## Validation JSON

```json
{
  "additionalProperties": false,
  "properties": {
    "normalized_query": {
      "title": "Normalized Query",
      "type": "string"
    },
    "user_goal": {
      "title": "User Goal",
      "type": "string"
    },
    "query_type": {
      "enum": [
        "web_research",
        "time",
        "currency",
        "file_task",
        "memory_store",
        "memory_recall",
        "general"
      ],
      "title": "Query Type",
      "type": "string"
    },
    "likely_tools": {
      "items": {
        "enum": [
          "web_search",
          "fetch_url",
          "get_time",
          "currency_convert",
          "read_file",
          "list_dir",
          "create_file",
          "update_file",
          "edit_file",
          "remember",
          "final_answer"
        ],
        "type": "string"
      },
      "title": "Likely Tools",
      "type": "array"
    },
    "facts_to_remember": {
      "items": {
        "type": "string"
      },
      "title": "Facts To Remember",
      "type": "array"
    },
    "answer_must_include": {
      "items": {
        "type": "string"
      },
      "title": "Answer Must Include",
      "type": "array"
    },
    "completion_criteria": {
      "title": "Completion Criteria",
      "type": "string"
    }
  },
  "required": [
    "normalized_query",
    "user_goal",
    "query_type",
    "completion_criteria"
  ],
  "title": "PerceptionOutput",
  "type": "object"
}
```
