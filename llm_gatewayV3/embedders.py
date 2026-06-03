"""Embedding providers for the Session 7 gateway.

The chat gateway stays V3-compatible. This module adds the one Session 7
capability: a fixed-dimension embedding failover ring.
"""

from __future__ import annotations

import os
import time
from collections import deque
from typing import Literal

import httpx


TaskType = Literal["retrieval_document", "retrieval_query"]
EMBED_DIM = 768
MAX_INPUT_CHARS = 8000
BACKOFF_STEPS = [5, 10, 15]


class EmbedderError(Exception):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


class EmbedRateState:
    def __init__(self, rpm: int, cooldown: float):
        self.rpm = rpm
        self.cooldown = cooldown
        self.calls_minute: deque[float] = deque()
        self.last_call = 0.0
        self.unavailable_until = 0.0
        self.unavailable_reason = ""
        self.backoff_step = 0

    def _gc(self) -> None:
        cutoff = time.time() - 60
        while self.calls_minute and self.calls_minute[0] < cutoff:
            self.calls_minute.popleft()

    def can_use(self) -> tuple[bool, str]:
        self._gc()
        now = time.time()
        if now < self.unavailable_until:
            remaining = self.unavailable_until - now
            return False, f"backoff: {self.unavailable_reason} ({remaining:.0f}s left)"
        if self.cooldown > 0:
            wait = self.cooldown - (now - self.last_call)
            if wait > 0:
                return False, f"cooldown ({wait:.1f}s)"
        if self.rpm > 0 and len(self.calls_minute) >= self.rpm:
            return False, f"RPM limit ({self.rpm}/min)"
        return True, ""

    def record(self) -> None:
        now = time.time()
        self.calls_minute.append(now)
        self.last_call = now
        self.backoff_step = 0
        self.unavailable_until = 0.0
        self.unavailable_reason = ""

    def mark_failure(self, reason: str) -> None:
        idx = min(self.backoff_step, len(BACKOFF_STEPS) - 1)
        self.backoff_step += 1
        self.unavailable_until = time.time() + BACKOFF_STEPS[idx]
        self.unavailable_reason = reason[:80]

    def snapshot(self) -> dict:
        self._gc()
        now = time.time()
        return {
            "rpm_used": len(self.calls_minute),
            "rpm_limit": self.rpm,
            "cooldown_s": self.cooldown,
            "cooldown_remaining": max(0.0, self.cooldown - (now - self.last_call)) if self.last_call else 0.0,
            "backoff_remaining": max(0.0, self.unavailable_until - now),
            "backoff_reason": self.unavailable_reason if now < self.unavailable_until else "",
            "backoff_step": self.backoff_step,
        }


class EmbeddingProvider:
    name: str = ""
    model: str = ""
    state: EmbedRateState

    async def embed(self, text: str, task_type: TaskType) -> dict:
        raise NotImplementedError


class OllamaEmbedder(EmbeddingProvider):
    name = "ollama"

    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.state = EmbedRateState(rpm=0, cooldown=0.0)

    async def embed(self, text: str, task_type: TaskType) -> dict:
        prefix = "search_query: " if task_type == "retrieval_query" else "search_document: "
        body = {"model": self.model, "prompt": prefix + text}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.base_url}/api/embeddings", json=body)
        if response.status_code != 200:
            raise EmbedderError(
                f"ollama HTTP {response.status_code}: {response.text[:200]}",
                status=response.status_code,
            )
        data = response.json()
        vector = data.get("embedding") or []
        if not vector:
            raise EmbedderError(f"ollama returned no embedding: {str(data)[:200]}")
        return {"embedding": [float(v) for v in vector], "model": self.model, "dim": len(vector)}


class GeminiEmbedder(EmbeddingProvider):
    name = "gemini"
    _TASK_MAP = {
        "retrieval_document": "RETRIEVAL_DOCUMENT",
        "retrieval_query": "RETRIEVAL_QUERY",
    }

    def __init__(
        self,
        api_key: str,
        model: str,
        output_dim: int = EMBED_DIM,
        rpm: int = 5,
        cooldown: float = 5.0,
    ):
        self.api_key = api_key
        self.model = model
        self.output_dim = output_dim
        self.state = EmbedRateState(rpm=rpm, cooldown=cooldown)

    async def embed(self, text: str, task_type: TaskType) -> dict:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model}:embedContent?key={self.api_key}"
        )
        body = {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
            "taskType": self._TASK_MAP[task_type],
            "outputDimensionality": self.output_dim,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=body)
        if response.status_code != 200:
            raise EmbedderError(
                f"gemini HTTP {response.status_code}: {response.text[:200]}",
                status=response.status_code,
            )
        data = response.json()
        vector = ((data.get("embedding") or {}).get("values")) or []
        if not vector:
            raise EmbedderError(f"gemini returned no embedding: {str(data)[:200]}")
        return {"embedding": [float(v) for v in vector], "model": self.model, "dim": len(vector)}


def build_embedders() -> tuple[list[EmbeddingProvider], list[str]]:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("EMBED_OLLAMA_MODEL", "nomic-embed-text")
    fallback_provider = os.getenv("EMBED_FALLBACK_PROVIDER", "gemini").lower()
    fallback_model = os.getenv("EMBED_FALLBACK_MODEL", "gemini-embedding-001")

    registry: dict[str, EmbeddingProvider] = {
        "ollama": OllamaEmbedder(ollama_model, ollama_url),
    }
    if fallback_provider == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if key:
            registry["gemini"] = GeminiEmbedder(
                key,
                fallback_model,
                rpm=int(os.getenv("EMBED_GEMINI_RPM", "60")),
                cooldown=float(os.getenv("EMBED_GEMINI_COOLDOWN", "0")),
            )

    order_env = os.getenv("EMBED_ORDER", f"ollama,{fallback_provider}")
    order = [name.strip() for name in order_env.split(",") if name.strip()]
    embedders = [registry[name] for name in order if name in registry]
    return embedders, [embedder.name for embedder in embedders]


async def embed_with_failover(
    embedders: list[EmbeddingProvider],
    text: str,
    task_type: TaskType,
    explicit: str | None = None,
) -> tuple[str, dict, list[dict], int]:
    attempts: list[dict] = []
    candidates = embedders
    if explicit:
        candidates = [embedder for embedder in embedders if embedder.name == explicit]
        if not candidates:
            raise EmbedderError(f"unknown embedder '{explicit}'", status=400)

    last_error: Exception | None = None
    start = time.time()
    for embedder in candidates:
        ok, why = embedder.state.can_use()
        if not ok:
            attempts.append({"provider": embedder.name, "reason": why})
            if explicit:
                raise EmbedderError(f"{embedder.name} unavailable: {why}", status=429)
            continue
        try:
            result = await embedder.embed(text, task_type)
            embedder.state.record()
            latency_ms = int((time.time() - start) * 1000)
            return embedder.name, result, attempts, latency_ms
        except Exception as exc:
            last_error = exc
            reason = str(exc)[:200]
            embedder.state.mark_failure(reason)
            attempts.append({"provider": embedder.name, "reason": reason})
            if explicit:
                raise

    raise EmbedderError(
        f"all embedders unavailable. attempts={attempts}. last_error={last_error}",
        status=503,
    )
