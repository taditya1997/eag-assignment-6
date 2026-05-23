from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from schemas import (
    MemoryFact,
    MemoryHit,
    MemoryRankingCandidate,
    MemoryRankingInput,
    MemoryRankingOutput,
    MemoryRecallInput,
    MemoryRecallOutput,
    MemoryWriteInput,
    MemoryWriteOutput,
    StrictModel,
)


MEMORY_PROMPT = """You are the Memory layer in a four-layer agent.

Given the user's current request and durable memory candidates, select only the
facts that are relevant to answering the current request. Return the typed JSON
contract only. Do not invent facts and do not include facts that are merely
topically similar.
"""


class MemoryStore(StrictModel):
    facts: list[MemoryFact] = Field(default_factory=list)


class FileMemory:
    def __init__(self, path: Path, llm: Any | None = None):
        self.path = path
        self.llm = llm

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def recall(self, request: MemoryRecallInput) -> MemoryRecallOutput:
        store = self._load()
        if not store.facts:
            return MemoryRecallOutput(hits=[], store_path=str(self.path))

        candidates = [
            MemoryRankingCandidate(fact_id=f.id, fact=f.fact, tags=f.tags)
            for f in store.facts
        ]
        ranking_request = MemoryRankingInput(
            query=request.query,
            candidates=candidates,
            max_facts=request.max_facts,
        )

        hits = self._rank_with_llm(ranking_request, store)
        if not hits:
            hits = self._rank_lexically(request.query, store.facts, request.max_facts)

        return MemoryRecallOutput(hits=hits[: request.max_facts], store_path=str(self.path))

    def remember(self, request: MemoryWriteInput) -> MemoryWriteOutput:
        store = self._load()
        now = datetime.now(UTC)
        fact_id = self._fact_id(request.fact)
        created = True
        fact = None

        for existing in store.facts:
            if existing.id == fact_id:
                existing.fact = request.fact.strip()
                existing.tags = sorted(set(existing.tags + request.tags))
                existing.source_query = request.source_query or existing.source_query
                existing.updated_at = now
                fact = existing
                created = False
                break

        if fact is None:
            fact = MemoryFact(
                id=fact_id,
                fact=request.fact.strip(),
                tags=sorted(set(request.tags)),
                source_query=request.source_query,
                created_at=now,
                updated_at=now,
            )
            store.facts.append(fact)

        self._save(store)
        return MemoryWriteOutput(fact=fact, created=created, store_path=str(self.path))

    def _rank_with_llm(
        self, request: MemoryRankingInput, store: MemoryStore
    ) -> list[MemoryHit]:
        if self.llm is None:
            return []
        try:
            response = self.llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Rank these durable memory candidates for the "
                            f"current request:\n{request.model_dump_json(indent=2)}"
                        ),
                    }
                ],
                system=MEMORY_PROMPT,
                auto_route="memory",
                response_format={
                    "type": "json_schema",
                    "schema": MemoryRankingOutput.model_json_schema(),
                    "name": "memory_ranking_output",
                    "strict": True,
                },
                max_tokens=1200,
                temperature=0.1,
            )
            parsed = response.get("parsed")
            if parsed is None:
                parsed = json.loads(response["text"])
            ranked = MemoryRankingOutput.model_validate(parsed)
        except Exception:
            return []

        facts_by_id = {fact.id: fact for fact in store.facts}
        valid_hits: list[MemoryHit] = []
        for hit in ranked.hits:
            fact = facts_by_id.get(hit.fact_id)
            if fact is None:
                continue
            valid_hits.append(
                MemoryHit(
                    fact_id=fact.id,
                    fact=fact.fact,
                    relevance=hit.relevance,
                    reason=hit.reason,
                )
            )
        return sorted(valid_hits, key=lambda h: h.relevance, reverse=True)

    def _rank_lexically(
        self, query: str, facts: list[MemoryFact], max_facts: int
    ) -> list[MemoryHit]:
        query_terms = self._terms(query)
        scored: list[MemoryHit] = []
        for fact in facts:
            fact_terms = self._terms(fact.fact + " " + " ".join(fact.tags))
            overlap = len(query_terms & fact_terms)
            if overlap == 0 and query_terms:
                continue
            relevance = 1.0 if not query_terms else min(1.0, overlap / len(query_terms))
            scored.append(
                MemoryHit(
                    fact_id=fact.id,
                    fact=fact.fact,
                    relevance=relevance,
                    reason="lexical overlap fallback",
                )
            )
        return sorted(scored, key=lambda h: h.relevance, reverse=True)[:max_facts]

    def _load(self) -> MemoryStore:
        if not self.path.exists():
            return MemoryStore()
        try:
            return MemoryStore.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return MemoryStore()

    def _save(self, store: MemoryStore) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(store.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _fact_id(fact: str) -> str:
        normalized = " ".join(fact.strip().lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {
            term.strip(".,:;!?()[]{}\"'").lower()
            for term in text.split()
            if len(term.strip(".,:;!?()[]{}\"'")) > 2
        }
