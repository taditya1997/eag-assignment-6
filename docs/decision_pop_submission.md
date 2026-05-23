# Decision Prompt And PoP Validation JSON

## Prompt

```text
You are the Decision layer in a four-layer agent.

Choose exactly one next action. Return only the typed JSON contract.

Rules:
- Use remember when the user explicitly provided a durable fact to store.
- Use final_answer when current observations and memory are sufficient.
- Use get_time for current time/date questions.
- Use currency_convert for exchange-rate conversions.
- Use web_search for current or external facts. Use fetch_url after search when
  snippets are insufficient or the user asks for details from a page.
- Use read_file/list_dir/create_file/update_file/edit_file for sandbox file
  tasks. File tools operate inside the MCP server sandbox.
- Do not repeat an action if its observation already answers the need.
- When near max_iterations, prefer final_answer with the best supported answer.

For next_action, fill the matching payload object and leave the others null.

```

## Validation JSON

```json
{
  "$defs": {
    "CreateFileArgs": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "minLength": 1,
          "title": "Path",
          "type": "string"
        },
        "content": {
          "title": "Content",
          "type": "string"
        }
      },
      "required": [
        "path",
        "content"
      ],
      "title": "CreateFileArgs",
      "type": "object"
    },
    "CurrencyConvertArgs": {
      "additionalProperties": false,
      "properties": {
        "amount": {
          "title": "Amount",
          "type": "number"
        },
        "from_currency": {
          "maxLength": 3,
          "minLength": 3,
          "title": "From Currency",
          "type": "string"
        },
        "to_currency": {
          "maxLength": 3,
          "minLength": 3,
          "title": "To Currency",
          "type": "string"
        }
      },
      "required": [
        "amount",
        "from_currency",
        "to_currency"
      ],
      "title": "CurrencyConvertArgs",
      "type": "object"
    },
    "EditFileArgs": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "minLength": 1,
          "title": "Path",
          "type": "string"
        },
        "find": {
          "minLength": 1,
          "title": "Find",
          "type": "string"
        },
        "replace": {
          "title": "Replace",
          "type": "string"
        },
        "replace_all": {
          "default": false,
          "title": "Replace All",
          "type": "boolean"
        }
      },
      "required": [
        "path",
        "find",
        "replace"
      ],
      "title": "EditFileArgs",
      "type": "object"
    },
    "FetchUrlArgs": {
      "additionalProperties": false,
      "properties": {
        "url": {
          "minLength": 1,
          "title": "Url",
          "type": "string"
        },
        "timeout": {
          "default": 20,
          "maximum": 60,
          "minimum": 5,
          "title": "Timeout",
          "type": "integer"
        }
      },
      "required": [
        "url"
      ],
      "title": "FetchUrlArgs",
      "type": "object"
    },
    "FinalAnswerArgs": {
      "additionalProperties": false,
      "properties": {
        "answer": {
          "minLength": 1,
          "title": "Answer",
          "type": "string"
        },
        "sources": {
          "items": {
            "type": "string"
          },
          "title": "Sources",
          "type": "array"
        }
      },
      "required": [
        "answer"
      ],
      "title": "FinalAnswerArgs",
      "type": "object"
    },
    "GetTimeArgs": {
      "additionalProperties": false,
      "properties": {
        "timezone": {
          "default": "UTC",
          "minLength": 1,
          "title": "Timezone",
          "type": "string"
        }
      },
      "title": "GetTimeArgs",
      "type": "object"
    },
    "ListDirArgs": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "default": ".",
          "title": "Path",
          "type": "string"
        }
      },
      "title": "ListDirArgs",
      "type": "object"
    },
    "ReadFileArgs": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "minLength": 1,
          "title": "Path",
          "type": "string"
        }
      },
      "required": [
        "path"
      ],
      "title": "ReadFileArgs",
      "type": "object"
    },
    "RememberArgs": {
      "additionalProperties": false,
      "properties": {
        "fact": {
          "minLength": 1,
          "title": "Fact",
          "type": "string"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "title": "Tags",
          "type": "array"
        }
      },
      "required": [
        "fact"
      ],
      "title": "RememberArgs",
      "type": "object"
    },
    "UpdateFileArgs": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "minLength": 1,
          "title": "Path",
          "type": "string"
        },
        "content": {
          "title": "Content",
          "type": "string"
        }
      },
      "required": [
        "path",
        "content"
      ],
      "title": "UpdateFileArgs",
      "type": "object"
    },
    "WebSearchArgs": {
      "additionalProperties": false,
      "properties": {
        "query": {
          "minLength": 1,
          "title": "Query",
          "type": "string"
        },
        "max_results": {
          "default": 3,
          "maximum": 5,
          "minimum": 1,
          "title": "Max Results",
          "type": "integer"
        }
      },
      "required": [
        "query"
      ],
      "title": "WebSearchArgs",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "next_action": {
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
      "title": "Next Action",
      "type": "string"
    },
    "rationale": {
      "title": "Rationale",
      "type": "string"
    },
    "web_search": {
      "anyOf": [
        {
          "$ref": "#/$defs/WebSearchArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "fetch_url": {
      "anyOf": [
        {
          "$ref": "#/$defs/FetchUrlArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "get_time": {
      "anyOf": [
        {
          "$ref": "#/$defs/GetTimeArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "currency_convert": {
      "anyOf": [
        {
          "$ref": "#/$defs/CurrencyConvertArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "read_file": {
      "anyOf": [
        {
          "$ref": "#/$defs/ReadFileArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "list_dir": {
      "anyOf": [
        {
          "$ref": "#/$defs/ListDirArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "create_file": {
      "anyOf": [
        {
          "$ref": "#/$defs/CreateFileArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "update_file": {
      "anyOf": [
        {
          "$ref": "#/$defs/UpdateFileArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "edit_file": {
      "anyOf": [
        {
          "$ref": "#/$defs/EditFileArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "remember": {
      "anyOf": [
        {
          "$ref": "#/$defs/RememberArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "final_answer": {
      "anyOf": [
        {
          "$ref": "#/$defs/FinalAnswerArgs"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "required": [
    "next_action",
    "rationale"
  ],
  "title": "DecisionOutput",
  "type": "object"
}
```
