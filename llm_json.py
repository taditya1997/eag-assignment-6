from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


def call_json_contract(
    llm: Any,
    *,
    model_type: type[T],
    messages: list[dict[str, str]],
    system: str,
    auto_route: str,
    name: str,
    max_tokens: int,
    temperature: float,
) -> T:
    schema = model_type.model_json_schema()
    try:
        response = llm.chat(
            messages=messages,
            system=system,
            auto_route=auto_route,
            response_format={
                "type": "json_schema",
                "schema": schema,
                "name": name,
                "strict": True,
            },
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except httpx.HTTPStatusError as exc:
        # Gemini can occasionally produce schema-shaped JSON that the gateway's
        # strict JSON Schema validator rejects, which returns 503 before the
        # caller can validate. Retry as JSON mode, then keep the Pydantic
        # contract as the layer boundary.
        if exc.response.status_code not in (502, 503):
            raise
        response = llm.chat(
            messages=messages
            + [
                {
                    "role": "user",
                    "content": (
                        "Return only a JSON object that validates against this "
                        f"schema:\n{json.dumps(schema)}"
                    ),
                }
            ],
            system=system,
            auto_route=auto_route,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            temperature=0,
        )

    parsed = response.get("parsed")
    if parsed is None:
        parsed = json.loads(response["text"])
    return model_type.model_validate(parsed)
