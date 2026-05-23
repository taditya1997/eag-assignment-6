from __future__ import annotations

import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from memory import FileMemory
from schemas import ActionInput, ActionOutput, MemoryWriteInput, RememberAction


class ActionLayer:
    def __init__(self, mcp_server: Path, memory: FileMemory):
        self.mcp_server = mcp_server
        self.memory = memory
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "ActionLayer":
        self._stack = AsyncExitStack()
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(self.mcp_server)],
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def run(self, request: ActionInput) -> ActionOutput:
        action = request.action
        if isinstance(action, RememberAction):
            written = self.memory.remember(
                MemoryWriteInput(
                    fact=action.fact,
                    source_query=request.source_query,
                    tags=action.tags,
                )
            )
            raw_json = written.model_dump_json(indent=2)
            return ActionOutput(
                iteration=request.iteration,
                action="remember",
                ok=True,
                summary=f"Stored durable fact: {written.fact.fact}",
                raw_json=raw_json,
            )

        if action.kind == "final_answer":
            return ActionOutput(
                iteration=request.iteration,
                action="final_answer",
                ok=True,
                summary=action.answer,
                raw_json=action.model_dump_json(indent=2),
            )

        if self._session is None:
            raise RuntimeError("ActionLayer must be used as an async context manager")

        args = action.model_dump(exclude={"kind"}, exclude_none=True)
        try:
            result = await self._session.call_tool(action.kind, arguments=args)
            raw_json, summary = self._serialize_result(result)
            ok = not bool(getattr(result, "isError", False))
            return ActionOutput(
                iteration=request.iteration,
                action=action.kind,
                ok=ok,
                summary=summary,
                raw_json=raw_json,
            )
        except Exception as exc:
            return ActionOutput(
                iteration=request.iteration,
                action=action.kind,
                ok=False,
                summary=f"{type(exc).__name__}: {exc}",
                raw_json=json.dumps({"error": str(exc), "type": type(exc).__name__}),
            )

    @staticmethod
    def _serialize_result(result: Any) -> tuple[str, str]:
        if hasattr(result, "model_dump"):
            data = result.model_dump(mode="json")
        else:
            data = result
        raw_json = json.dumps(data, ensure_ascii=True, indent=2)

        content = getattr(result, "content", None)
        text_parts: list[str] = []
        if content:
            for item in content:
                text = getattr(item, "text", None)
                if text:
                    text_parts.append(text)

        summary = "\n".join(text_parts).strip() or raw_json
        if len(summary) > 1600:
            summary = summary[:1600] + "... [truncated]"
        return raw_json, summary
