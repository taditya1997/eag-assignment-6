from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llm_json import call_json_contract
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

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover - dependency may be absent until uv sync.
    faiss = None

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None


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

    @property
    def index_path(self) -> Path:
        return self.path.parent / "index.faiss"

    @property
    def index_ids_path(self) -> Path:
        return self.path.parent / "index_ids.json"

    def clear(self) -> None:
        for path in (self.path, self.index_path, self.index_ids_path):
            if path.exists():
                path.unlink()

    def recall(self, request: MemoryRecallInput) -> MemoryRecallOutput:
        store = self._load()
        if not store.facts:
            return MemoryRecallOutput(hits=[], store_path=str(self.path))

        vector_hits = self._rank_vector(request.query, store, request.max_facts)
        if vector_hits:
            return MemoryRecallOutput(
                hits=vector_hits[: request.max_facts],
                store_path=str(self.path),
            )

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
        return self._write_fact(
            request.fact,
            tags=request.tags,
            source_query=request.source_query,
            task_type="retrieval_document",
        )

    def add_fact(
        self,
        fact: str,
        *,
        tags: list[str] | None = None,
        source_query: str = "",
    ) -> MemoryWriteOutput:
        return self._write_fact(
            fact,
            tags=tags or [],
            source_query=source_query,
            task_type="retrieval_document",
        )

    def search_facts(
        self,
        query: str,
        *,
        max_facts: int = 5,
        required_tags: set[str] | None = None,
    ) -> list[tuple[MemoryHit, MemoryFact]]:
        store = self._load()
        if not store.facts:
            return []

        hits = self._rank_vector(query, store, max_facts, required_tags=required_tags)
        if not hits:
            hits = self._rank_lexically(
                query,
                store.facts,
                max_facts,
                required_tags=required_tags,
            )

        facts_by_id = {fact.id: fact for fact in store.facts}
        return [
            (hit, facts_by_id[hit.fact_id])
            for hit in hits
            if hit.fact_id in facts_by_id
        ][:max_facts]

    def _write_fact(
        self,
        fact_text: str,
        *,
        tags: list[str],
        source_query: str,
        task_type: str,
    ) -> MemoryWriteOutput:
        store = self._load()
        now = datetime.now(UTC)
        text = fact_text.strip()
        fact_id = self._fact_id(text)
        normalized_tags = sorted({tag.strip().lower() for tag in tags if tag.strip()})
        embedding = self._try_embed(text, task_type=task_type)
        created = True
        fact = None

        for existing in store.facts:
            if existing.id == fact_id:
                text_changed = existing.fact != text
                existing.fact = text
                existing.tags = sorted(set(existing.tags + normalized_tags))
                existing.source_query = source_query or existing.source_query
                existing.updated_at = now
                if embedding is not None or text_changed:
                    existing.embedding = embedding
                fact = existing
                created = False
                break

        if fact is None:
            fact = MemoryFact(
                id=fact_id,
                fact=text,
                tags=normalized_tags,
                embedding=embedding,
                source_query=source_query,
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
            ranked = call_json_contract(
                self.llm,
                model_type=MemoryRankingOutput,
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
                name="memory_ranking_output",
                max_tokens=1200,
                temperature=0.1,
            )
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

    def _rank_vector(
        self,
        query: str,
        store: MemoryStore,
        max_facts: int,
        *,
        required_tags: set[str] | None = None,
    ) -> list[MemoryHit]:
        if np is None:
            return []
        query_embedding = self._try_embed(query, task_type="retrieval_query")
        if not query_embedding:
            return []

        if faiss is None:
            return self._rank_vector_numpy(
                query_embedding,
                store.facts,
                max_facts,
                required_tags=required_tags,
            )

        index, index_ids = self._load_or_rebuild_index(store)
        if index is None or not index_ids:
            return []

        facts_by_id = {fact.id: fact for fact in store.facts}
        q = self._as_vector(query_embedding, index.d)
        if q is None:
            return []
        faiss.normalize_L2(q)
        search_k = len(index_ids) if required_tags else min(len(index_ids), max(max_facts * 4, max_facts))
        scores, positions = index.search(q, search_k)

        hits: list[MemoryHit] = []
        for score, pos in zip(scores[0].tolist(), positions[0].tolist()):
            if pos < 0 or pos >= len(index_ids):
                continue
            fact = facts_by_id.get(index_ids[pos])
            if fact is None:
                continue
            if required_tags and not required_tags.issubset(set(fact.tags)):
                continue
            relevance = max(0.0, min(1.0, float(score)))
            hits.append(
                MemoryHit(
                    fact_id=fact.id,
                    fact=fact.fact,
                    relevance=relevance,
                    reason=f"vector search cosine similarity {float(score):.3f}",
                )
            )
            if len(hits) >= max_facts:
                break
        return hits

    def _rank_vector_numpy(
        self,
        query_embedding: list[float],
        facts: list[MemoryFact],
        max_facts: int,
        *,
        required_tags: set[str] | None = None,
    ) -> list[MemoryHit]:
        embedded = self._embedded_facts(facts, required_tags=required_tags)
        if not embedded:
            return []
        dim = len(embedded[0].embedding or [])
        q = self._as_vector(query_embedding, dim)
        if q is None:
            return []
        vectors = np.asarray([fact.embedding for fact in embedded], dtype="float32")
        vectors = self._normalize(vectors)
        q = self._normalize(q)
        scores = vectors @ q[0]
        ranked = sorted(
            zip(scores.tolist(), embedded),
            key=lambda item: item[0],
            reverse=True,
        )
        return [
            MemoryHit(
                fact_id=fact.id,
                fact=fact.fact,
                relevance=max(0.0, min(1.0, float(score))),
                reason=f"vector search cosine similarity {float(score):.3f} (numpy fallback)",
            )
            for score, fact in ranked[:max_facts]
        ]

    def _rank_lexically(
        self,
        query: str,
        facts: list[MemoryFact],
        max_facts: int,
        *,
        required_tags: set[str] | None = None,
    ) -> list[MemoryHit]:
        query_terms = self._terms(query)
        scored: list[MemoryHit] = []
        for fact in facts:
            if required_tags and not required_tags.issubset(set(fact.tags)):
                continue
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

    def _load_or_rebuild_index(
        self, store: MemoryStore
    ) -> tuple[Any | None, list[str]]:
        if faiss is None or np is None:
            return None, []

        embedded = self._embedded_facts(store.facts)
        if not embedded:
            self._unlink_index()
            return None, []

        ids = [fact.id for fact in embedded]
        dim = len(embedded[0].embedding or [])
        if self.index_path.exists() and self.index_ids_path.exists():
            try:
                saved_ids = json.loads(self.index_ids_path.read_text(encoding="utf-8"))
                index = faiss.read_index(str(self.index_path))
                if saved_ids == ids and index.d == dim:
                    return index, saved_ids
            except Exception:
                pass

        return self._write_index(embedded)

    def _write_index(self, embedded: list[MemoryFact]) -> tuple[Any | None, list[str]]:
        if faiss is None or np is None or not embedded:
            return None, []

        dim = len(embedded[0].embedding or [])
        vectors = np.asarray([fact.embedding for fact in embedded], dtype="float32")
        vectors = self._normalize(vectors)
        index = faiss.IndexFlatIP(dim)
        index.add(vectors)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        ids = [fact.id for fact in embedded]
        self.index_ids_path.write_text(json.dumps(ids, indent=2), encoding="utf-8")
        return index, ids

    def _embedded_facts(
        self,
        facts: list[MemoryFact],
        *,
        required_tags: set[str] | None = None,
    ) -> list[MemoryFact]:
        embedded = [
            fact
            for fact in facts
            if fact.embedding
            and (not required_tags or required_tags.issubset(set(fact.tags)))
        ]
        if not embedded:
            return []
        dim = len(embedded[0].embedding or [])
        return [fact for fact in embedded if len(fact.embedding or []) == dim]

    def _try_embed(self, text: str, *, task_type: str) -> list[float] | None:
        if self.llm is None or not hasattr(self.llm, "embed"):
            return None
        try:
            response = self.llm.embed(text, task_type=task_type)
            embedding = response.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                return None
            return [float(value) for value in embedding]
        except Exception:
            return None

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
        self._load_or_rebuild_index(store)

    def _unlink_index(self) -> None:
        for path in (self.index_path, self.index_ids_path):
            if path.exists():
                path.unlink()

    @staticmethod
    def _as_vector(values: list[float], dim: int):
        if np is None or len(values) != dim:
            return None
        return np.asarray([values], dtype="float32")

    @staticmethod
    def _normalize(vectors):
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

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
