from __future__ import annotations

import json
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


def _retryable_status(exc: httpx.HTTPStatusError) -> bool:
    return exc.response.status_code in (429, 502, 503)


def _chat_with_retries(llm: Any, *, attempts: int = 3, **kwargs: Any) -> dict:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return llm.chat(**kwargs)
        except httpx.HTTPStatusError as exc:
            if not _retryable_status(exc) or attempt == attempts - 1:
                raise
            last_exc = exc
            time.sleep(6 * (attempt + 1))
        except httpx.RequestError as exc:
            if attempt == attempts - 1:
                raise
            last_exc = exc
            time.sleep(3 * (attempt + 1))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("LLM chat retry loop exited unexpectedly")


def _parse_json_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            obj, _ = decoder.raw_decode(text[start:])
            return obj
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
    return json.loads(text)


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
        response = _chat_with_retries(
            llm,
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
        response = _chat_with_retries(
            llm,
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
        parsed = _parse_json_text(response["text"])
    try:
        return model_type.model_validate(parsed)
    except (ValidationError, json.JSONDecodeError, TypeError, ValueError):
        repair = _chat_with_retries(
            llm,
            messages=messages
            + [
                {
                    "role": "assistant",
                    "content": response.get("text", json.dumps(parsed)),
                },
                {
                    "role": "user",
                    "content": (
                        "Return only a JSON object that validates against this "
                        f"schema:\n{json.dumps(schema)}"
                    ),
                },
            ],
            system=system,
            auto_route=auto_route,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            temperature=0,
        )
        repaired = repair.get("parsed")
        if repaired is None:
            repaired = _parse_json_text(repair["text"])
        return model_type.model_validate(repaired)
