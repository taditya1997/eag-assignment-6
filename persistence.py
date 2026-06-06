from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import networkx as nx
from networkx.readwrite import json_graph
from pydantic import BaseModel, Field


Status = Literal["pending", "running", "complete", "failed", "skipped"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.replace(tmp, path)


class SessionLoadError(RuntimeError):
    pass


class NodeState(BaseModel):
    node_id: str
    skill: str
    label: str
    inputs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: Status = "pending"
    result: dict[str, Any] | None = None
    error: str | None = None
    prompt: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_s: float | None = None
    recovery_attempts: int = 0


class SessionStore:
    def __init__(self, session_id: str, *, root: str | Path = "state/sessions") -> None:
        self.session_id = session_id
        self.root = Path(root) / session_id
        self.nodes_dir = self.root / "nodes"

    @property
    def graph_path(self) -> Path:
        return self.root / "graph.json"

    @property
    def query_path(self) -> Path:
        return self.root / "query.txt"

    def init(self, query: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        self.query_path.write_text(query)

    def load_query(self) -> str:
        return self.query_path.read_text()

    def node_path(self, node_id: str) -> Path:
        return self.nodes_dir / f"{node_id}.json"

    def save_node(self, state: NodeState) -> None:
        atomic_write_json(self.node_path(state.node_id), state.model_dump(mode="json"))

    def load_node(self, node_id: str) -> NodeState:
        path = self.node_path(node_id)
        try:
            return NodeState.model_validate_json(path.read_text())
        except Exception as exc:  # noqa: BLE001 - surface the path in the message.
            raise SessionLoadError(f"failed to load {path}: {exc}") from exc

    def save_graph(self, graph: nx.DiGraph) -> None:
        atomic_write_json(self.graph_path, json_graph.node_link_data(graph))

    def load_graph(self) -> nx.DiGraph:
        try:
            data = json.loads(self.graph_path.read_text())
            graph = json_graph.node_link_graph(data, directed=True)
        except Exception as exc:  # noqa: BLE001 - surface the path in the message.
            raise SessionLoadError(f"failed to load {self.graph_path}: {exc}") from exc
        return graph

    def reset_running_nodes(self, graph: nx.DiGraph) -> None:
        for node_id, attrs in graph.nodes(data=True):
            if attrs.get("status") == "running":
                attrs["status"] = "pending"
                state = self.load_node(node_id)
                state.status = "pending"
                state.error = "reset from running during resume"
                self.save_node(state)
        self.save_graph(graph)
