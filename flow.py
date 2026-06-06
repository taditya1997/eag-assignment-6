from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any

import networkx as nx
from pydantic import BaseModel, Field

from persistence import NodeState, SessionStore, now_iso
from recovery import FailureKind, classify_failure
from sandbox import run_python
from skills import SkillCatalog, render_prompt


class NodeSpec(BaseModel):
    skill: str
    inputs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


CITY_FACTS = {
    "London": {
        "population": 8_866_000,
        "growth_rate": None,
        "delay": 1.20,
        "source": "demo city fact fixture",
    },
    "Paris": {
        "population": 2_115_000,
        "growth_rate": None,
        "delay": 0.90,
        "source": "demo city fact fixture",
    },
    "Berlin": {
        "population": 3_755_000,
        "growth_rate": None,
        "delay": 0.70,
        "source": "demo city fact fixture",
    },
    "Lagos": {
        "population": 16_536_000,
        "growth_rate": 3.78,
        "delay": 1.10,
        "source": "demo city growth fixture",
    },
    "Cairo": {
        "population": 10_230_000,
        "growth_rate": 2.05,
        "delay": 0.85,
        "source": "demo city growth fixture",
    },
    "Kinshasa": {
        "population": 17_032_000,
        "growth_rate": 3.45,
        "delay": 0.95,
        "source": "demo city growth fixture",
    },
}

RISK_FACTS = {
    "aluminum_rails": {
        "delay": 1.00,
        "text": "Aluminum rails near chloride mist need underside inspection because clean top faces can hide salt film at clamp joints.",
    },
    "frp_supports": {
        "delay": 0.75,
        "text": "FRP supports need tap checks after impact because glossy edges can hide delamination beneath the surface.",
    },
    "galvanized_brackets": {
        "delay": 0.60,
        "text": "Galvanized brackets need sealed cut ends because bright saw marks become early red-rust points in coastal air.",
    },
}


class DemoDAGAgent:
    def __init__(
        self,
        *,
        query: str,
        session_id: str,
        catalog: SkillCatalog,
        store: SessionStore,
        resume: bool = False,
        stop_after_complete: int | None = None,
    ) -> None:
        self.query = query
        self.session_id = session_id
        self.catalog = catalog
        self.store = store
        self.stop_after_complete = stop_after_complete
        self.completed_count = 0
        self.layer_summaries: list[dict[str, Any]] = []

        if resume:
            self.query = self.store.load_query()
            self.graph = self.store.load_graph()
            self.store.reset_running_nodes(self.graph)
        else:
            self.graph = nx.DiGraph()
            self.graph.graph["session"] = session_id
            self.graph.graph["query"] = query
            self.graph.graph["recovery_counts"] = {}
            self.store.init(query)
            self._add_node(
                "planner",
                ["USER_QUERY"],
                {"label": "planner", "phase": "initial"},
                persist=True,
            )
            self.store.save_graph(self.graph)

    def _next_node_id(self) -> str:
        highest = 0
        for node_id in self.graph.nodes:
            if node_id.startswith("n") and node_id[1:].isdigit():
                highest = max(highest, int(node_id[1:]))
        return f"n{highest + 1:03d}"

    def _add_node(
        self,
        skill: str,
        inputs: list[str],
        metadata: dict[str, Any],
        *,
        persist: bool = True,
    ) -> str:
        self.catalog.get(skill)
        node_id = self._next_node_id()
        label = metadata.get("label") or node_id
        metadata = {**metadata, "label": label}
        state = NodeState(
            node_id=node_id,
            skill=skill,
            label=label,
            inputs=inputs,
            metadata=metadata,
        )
        self.graph.add_node(
            node_id,
            skill=skill,
            label=label,
            inputs=inputs,
            metadata=metadata,
            status="pending",
        )
        if persist:
            self.store.save_node(state)
            self.store.save_graph(self.graph)
        return node_id

    def _node_by_label(self, label: str) -> str:
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("label") == label:
                return node_id
        raise KeyError(f"no node label {label!r}")

    def _label(self, node_id: str) -> str:
        return str(self.graph.nodes[node_id].get("label") or node_id)

    def _state(self, node_id: str) -> NodeState:
        return self.store.load_node(node_id)

    def _save_state(self, state: NodeState) -> None:
        self.graph.nodes[state.node_id]["status"] = state.status
        self.graph.nodes[state.node_id]["result"] = state.result
        self.graph.nodes[state.node_id]["error"] = state.error
        self.graph.nodes[state.node_id]["inputs"] = state.inputs
        self.graph.nodes[state.node_id]["metadata"] = state.metadata
        self.store.save_node(state)
        self.store.save_graph(self.graph)

    def _resolve_input_ref(self, ref: str) -> Any:
        if ref == "USER_QUERY":
            return self.query
        if ref.startswith("n:"):
            node_id = self._node_by_label(ref[2:])
            return self._state(node_id).result
        return ref

    def _resolved_inputs_for(self, state: NodeState) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for ref in state.inputs:
            resolved[ref] = self._resolve_input_ref(ref)
        return resolved

    def _ready_nodes(self) -> list[str]:
        ready: list[str] = []
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("status") != "pending":
                continue
            predecessors = list(self.graph.predecessors(node_id))
            if all(self.graph.nodes[pred].get("status") in {"complete", "skipped"} for pred in predecessors):
                ready.append(node_id)
        return ready

    def _has_unfinished(self) -> bool:
        return any(
            attrs.get("status") in {"pending", "running"}
            for _, attrs in self.graph.nodes(data=True)
        )

    def _edge_sources_from_inputs(self, inputs: list[str], parent_id: str) -> list[str]:
        sources = []
        for ref in inputs:
            if ref.startswith("n:"):
                sources.append(self._node_by_label(ref[2:]))
        return sources or [parent_id]

    def extend_from(self, parent_id: str, raw_nodes: list[dict[str, Any]]) -> list[str]:
        specs = [NodeSpec.model_validate(raw) for raw in raw_nodes]
        new_ids: list[str] = []

        for spec in specs:
            node_id = self._add_node(spec.skill, spec.inputs, spec.metadata, persist=True)
            new_ids.append(node_id)

        for node_id, spec in zip(new_ids, specs, strict=True):
            for source in self._edge_sources_from_inputs(spec.inputs, parent_id):
                if source != node_id:
                    self.graph.add_edge(source, node_id)

        self._insert_critics_for(new_ids)
        self.store.save_graph(self.graph)
        return new_ids

    def _insert_critics_for(self, candidate_sources: list[str]) -> None:
        for source in list(candidate_sources):
            source_skill = self.graph.nodes[source]["skill"]
            if not self.catalog.get(source_skill).critic:
                continue
            for _, child in list(self.graph.out_edges(source)):
                if self.graph.nodes[child]["skill"] == "critic":
                    continue
                source_label = self._label(source)
                child_label = self._label(child)
                critic_label = f"critic_{source_label}_{child_label}"
                if any(attrs.get("label") == critic_label for _, attrs in self.graph.nodes(data=True)):
                    continue
                source_state = self._state(source)
                critic_id = self._add_node(
                    "critic",
                    [f"n:{source_label}"],
                    {
                        "label": critic_label,
                        "source_label": source_label,
                        "target_child": child,
                        "question": source_state.metadata.get("question", ""),
                        "required_bullets": source_state.metadata.get("required_bullets"),
                    },
                    persist=True,
                )
                self.graph.remove_edge(source, child)
                self.graph.add_edge(source, critic_id)
                self.graph.add_edge(critic_id, child)

                child_state = self._state(child)
                child_state.inputs = [
                    f"n:{critic_label}" if ref == f"n:{source_label}" else ref
                    for ref in child_state.inputs
                ]
                self.graph.nodes[child]["inputs"] = child_state.inputs
                self._save_state(child_state)

    def _ensure_internal_successors(self, node_id: str) -> None:
        skill = self.graph.nodes[node_id]["skill"]
        successors = self.catalog.get(skill).internal_successors
        if not successors:
            return
        label = self._label(node_id)
        for successor_skill in successors:
            existing = [
                child
                for child in self.graph.successors(node_id)
                if self.graph.nodes[child].get("metadata", {}).get("internal_of") == node_id
                and self.graph.nodes[child].get("skill") == successor_skill
            ]
            if existing:
                continue
            successor_id = self._add_node(
                successor_skill,
                [f"n:{label}"],
                {
                    "label": f"{successor_skill}_{label}",
                    "internal_of": node_id,
                },
                persist=True,
            )
            self.graph.add_edge(node_id, successor_id)
        self.store.save_graph(self.graph)

    async def run(self) -> dict[str, Any]:
        print(f"SESSION: {self.session_id}")
        print(f"QUERY: {self.query}")

        while self._has_unfinished():
            ready = self._ready_nodes()
            if not ready:
                print("NO READY NODES: stopping because the graph cannot advance.")
                break

            layer_start = time.perf_counter()
            print(
                "READY LAYER: "
                + ", ".join(f"{node_id}:{self.graph.nodes[node_id]['skill']}[{self._label(node_id)}]" for node_id in ready)
            )
            results = await asyncio.gather(*(self._run_one(node_id) for node_id in ready), return_exceptions=True)
            layer_elapsed = time.perf_counter() - layer_start
            branch_sum = 0.0
            branch_max = 0.0

            for node_id, result in zip(ready, results, strict=True):
                if isinstance(result, Exception):
                    self._mark_failed(node_id, result)
                    elapsed = self._state(node_id).elapsed_s or 0.0
                else:
                    elapsed = result
                branch_sum += elapsed
                branch_max = max(branch_max, elapsed)

            self.layer_summaries.append(
                {
                    "nodes": ready,
                    "wall_s": round(layer_elapsed, 3),
                    "branch_sum_s": round(branch_sum, 3),
                    "branch_max_s": round(branch_max, 3),
                }
            )
            print(
                f"LAYER WALL: {layer_elapsed:.3f}s | "
                f"BRANCH SUM: {branch_sum:.3f}s | MAX BRANCH: {branch_max:.3f}s"
            )

            if self.stop_after_complete and self.completed_count >= self.stop_after_complete:
                print(
                    f"SIMULATED STOP: completed {self.completed_count} nodes; "
                    f"resume with `.venv/bin/python flow.py --resume {self.session_id}`"
                )
                break

        final = self._final_answer()
        print("\nFINAL ANSWER:")
        print(final)
        print("\nNODE SUMMARY:")
        for node_id in self.graph.nodes:
            state = self._state(node_id)
            print(
                f"{node_id} {state.skill:<16} label={state.label:<28} "
                f"status={state.status:<8} elapsed={state.elapsed_s if state.elapsed_s is not None else '-'}"
            )
        return {"final_answer": final, "layers": self.layer_summaries}

    async def _run_one(self, node_id: str) -> float:
        state = self._state(node_id)
        start = time.perf_counter()
        state.status = "running"
        state.started_at = now_iso()
        resolved_inputs = self._resolved_inputs_for(state)
        state.prompt = render_prompt(
            self.catalog,
            state.skill,
            query=self.query,
            inputs=resolved_inputs,
            memory_hits=[],
        )
        self._save_state(state)

        try:
            result = await self._dispatch(state, resolved_inputs)
        except Exception:
            raise

        elapsed = time.perf_counter() - start
        state = self._state(node_id)
        state.status = "complete"
        state.result = result
        state.error = None
        state.finished_at = now_iso()
        state.elapsed_s = round(elapsed, 3)
        self._save_state(state)
        self.completed_count += 1

        print(
            f"[{node_id}] {state.skill}: {self._short_result(result)} "
            f"(elapsed {elapsed:.3f}s)"
        )

        if state.skill == "planner":
            self.extend_from(node_id, result.get("nodes", []))
        elif state.skill == "critic":
            self._handle_critic_result(node_id, result)
        else:
            self._ensure_internal_successors(node_id)

        return elapsed

    def _mark_failed(self, node_id: str, exc: Exception) -> None:
        state = self._state(node_id)
        state.status = "failed"
        state.error = str(exc)
        state.finished_at = now_iso()
        state.elapsed_s = state.elapsed_s or 0.0
        self._save_state(state)
        kind = classify_failure(str(exc))
        print(f"[{node_id}] failed ({kind.value}): {exc}")
        if kind == FailureKind.UPSTREAM_FAILURE and state.skill != "planner":
            self._queue_recovery_planner(node_id, str(exc), target_child=node_id)

    def _handle_critic_result(self, critic_id: str, result: dict[str, Any]) -> None:
        if result.get("verdict") == "pass":
            return
        critic_state = self._state(critic_id)
        target_child = critic_state.metadata.get("target_child")
        if target_child and target_child in self.graph:
            child_state = self._state(target_child)
            if child_state.status == "pending":
                child_state.status = "skipped"
                child_state.error = f"blocked by critic fail: {result.get('rationale')}"
                self._save_state(child_state)
                print(f"[{target_child}] skipped after critic fail")
        self._queue_recovery_planner(critic_id, result.get("rationale", "critic failed"), target_child=target_child)

    def _queue_recovery_planner(self, failed_node: str, rationale: str, *, target_child: str | None) -> None:
        target = target_child or failed_node
        counts = self.graph.graph.setdefault("recovery_counts", {})
        if counts.get(target, 0) >= 1:
            print(f"RECOVERY CAP: not queueing another planner for {target}")
            return
        counts[target] = counts.get(target, 0) + 1
        failed_label = self._label(failed_node)
        recovery_id = self._add_node(
            "planner",
            [f"n:{failed_label}"],
            {
                "label": f"recovery_{failed_label}",
                "phase": "recovery",
                "failure_report": rationale,
                "target_child": target,
            },
            persist=True,
        )
        self.graph.add_edge(failed_node, recovery_id)
        self.store.save_graph(self.graph)
        print(f"RECOVERY: queued {recovery_id} after {failed_node}")

    async def _dispatch(self, state: NodeState, inputs: dict[str, Any]) -> dict[str, Any]:
        skill = state.skill
        if skill == "planner":
            return self._run_planner(state, inputs)
        if skill == "researcher":
            return await self._run_researcher(state)
        if skill == "distiller":
            return self._run_distiller(state, inputs)
        if skill == "critic":
            return self._run_critic(state, inputs)
        if skill == "coder":
            return self._run_coder(state, inputs)
        if skill == "sandbox_executor":
            return self._run_sandbox(inputs)
        if skill in {"formatter", "summariser", "retriever", "browser"}:
            return self._run_formatter(state, inputs)
        if skill in self.catalog.skills:
            return self._run_prompt_only_skill(state, inputs)
        raise KeyError(f"no demo dispatcher for skill {skill}")

    def _run_planner(self, state: NodeState, inputs: dict[str, Any]) -> dict[str, Any]:
        if state.metadata.get("phase") == "recovery":
            return {
                "rationale": "Recover from critic failure by producing a corrected distillation.",
                "nodes": [
                    {
                        "skill": "distiller",
                        "inputs": ["USER_QUERY"],
                        "metadata": {
                            "label": "recovered_checks",
                            "question": "Produce exactly three coastal support safety checks.",
                            "required_bullets": 3,
                            "fail_first": False,
                            "recovered": True,
                        },
                    },
                    {
                        "skill": "formatter",
                        "inputs": ["n:recovered_checks"],
                        "metadata": {"label": "out_recovered"},
                    },
                ],
            }

        query = self.query.lower()
        if query.strip() == "say hello." or query.strip() == "say hello":
            nodes = [
                {
                    "skill": "formatter",
                    "inputs": ["USER_QUERY"],
                    "metadata": {"label": "out", "answer": "Hello! The Session 8 DAG is awake."},
                }
            ]
            rationale = "The query only needs a terminal formatter."
        elif "claude_shannon" in query or "claude shannon" in query:
            nodes = [
                {
                    "skill": "researcher",
                    "inputs": ["USER_QUERY"],
                    "metadata": {
                        "label": "shannon_page",
                        "question": "Fetch the Claude Shannon page and retain dates and contributions.",
                        "fixture": "shannon",
                    },
                },
                {
                    "skill": "distiller",
                    "inputs": ["n:shannon_page"],
                    "metadata": {
                        "label": "shannon_fields",
                        "question": "Extract birth date, death date, and three information theory contributions.",
                        "fixture": "shannon",
                    },
                },
                {
                    "skill": "formatter",
                    "inputs": ["n:shannon_fields"],
                    "metadata": {"label": "out"},
                },
            ]
            rationale = "Fetch, extract, critic-check, then answer."
        elif "london" in query and "paris" in query and "berlin" in query:
            nodes = self._city_plan(["London", "Paris", "Berlin"], label="compare")
            rationale = "Three independent city researchers feed one computation node."
        elif "lagos" in query and "cairo" in query and "kinshasa" in query:
            nodes = self._city_plan(["Lagos", "Cairo", "Kinshasa"], label="fastest_growth")
            rationale = "Three independent growth researchers feed one computation node."
        elif "/nonexistent/path.txt" in query:
            nodes = [
                {
                    "skill": "formatter",
                    "inputs": ["USER_QUERY"],
                    "metadata": {
                        "label": "out",
                        "answer": "I cannot read /nonexistent/path.txt because the path does not exist in the demo workspace.",
                    },
                }
            ]
            rationale = "The path is impossible, so fail gracefully without dispatching work."
        elif "parallel fan-out demo" in query:
            nodes = [
                {
                    "skill": "researcher",
                    "inputs": ["USER_QUERY"],
                    "metadata": {
                        "label": key,
                        "fixture": "risk",
                        "risk_key": key,
                        "question": value["text"],
                    },
                }
                for key, value in RISK_FACTS.items()
            ]
            nodes.append(
                {
                    "skill": "formatter",
                    "inputs": [f"n:{key}" for key in RISK_FACTS],
                    "metadata": {"label": "out"},
                }
            )
            rationale = "Three independent material checks can run in parallel."
        elif "critic pass" in query:
            nodes = self._critic_demo_plan(fail_first=False)
            rationale = "Produce a verifiable three-bullet result and let the Critic pass it."
        elif "critic fail" in query:
            nodes = self._critic_demo_plan(fail_first=True)
            rationale = "Produce an intentionally incomplete draft so the Critic forces recovery."
        elif "coder computation demo" in query:
            nodes = [
                {
                    "skill": "coder",
                    "inputs": ["USER_QUERY"],
                    "metadata": {"label": "budget_compare", "fixture": "budgets"},
                },
                {
                    "skill": "formatter",
                    "inputs": ["n:budget_compare"],
                    "metadata": {"label": "out"},
                },
            ]
            rationale = "The result depends on exact arithmetic, so route through Coder."
        elif "tabulate" in query or "tabulator" in query:
            nodes = [
                {
                    "skill": "tabulator",
                    "inputs": ["USER_QUERY"],
                    "metadata": {"label": "evidence_table", "table_kind": "session8_evidence"},
                },
                {
                    "skill": "formatter",
                    "inputs": ["n:evidence_table"],
                    "metadata": {"label": "out"},
                },
            ]
            rationale = "The new Tabulator skill can format the assignment evidence."
        else:
            nodes = [
                {
                    "skill": "formatter",
                    "inputs": ["USER_QUERY"],
                    "metadata": {"label": "out", "answer": "I can answer this directly in the formatter."},
                }
            ]
            rationale = "Direct answer."

        return {"rationale": rationale, "nodes": nodes}

    def _city_plan(self, cities: list[str], *, label: str) -> list[dict[str, Any]]:
        nodes = [
            {
                "skill": "researcher",
                "inputs": ["USER_QUERY"],
                "metadata": {
                    "label": city.lower(),
                    "city": city,
                    "question": f"Find population and growth facts for {city}.",
                },
            }
            for city in cities
        ]
        nodes.extend(
            [
                {
                    "skill": "coder",
                    "inputs": [f"n:{city.lower()}" for city in cities],
                    "metadata": {"label": label},
                },
                {
                    "skill": "formatter",
                    "inputs": [f"n:{label}"],
                    "metadata": {"label": "out"},
                },
            ]
        )
        return nodes

    def _critic_demo_plan(self, *, fail_first: bool) -> list[dict[str, Any]]:
        return [
            {
                "skill": "distiller",
                "inputs": ["USER_QUERY"],
                "metadata": {
                    "label": "safety_checks",
                    "question": "Produce exactly three coastal support safety checks.",
                    "required_bullets": 3,
                    "fail_first": fail_first,
                },
            },
            {
                "skill": "formatter",
                "inputs": ["n:safety_checks"],
                "metadata": {"label": "out"},
            },
        ]

    async def _run_researcher(self, state: NodeState) -> dict[str, Any]:
        if state.metadata.get("fixture") == "shannon":
            await asyncio.sleep(0.30)
            text = (
                "Claude Elwood Shannon was born on 30 April 1916 and died on "
                "24 February 2001. He founded information theory, introduced "
                "the bit as a measure of information, connected Boolean algebra "
                "to switching circuits, and analyzed communication over noisy channels."
            )
            return {
                "kind": "research",
                "source": "https://en.wikipedia.org/wiki/Claude_Shannon",
                "text": text,
            }

        if state.metadata.get("fixture") == "risk":
            key = state.metadata["risk_key"]
            fact = RISK_FACTS[key]
            await asyncio.sleep(float(fact["delay"]))
            return {
                "kind": "research",
                "source": "demo solar support field fixture",
                "topic": key,
                "text": fact["text"],
            }

        city = state.metadata.get("city")
        if not city or city not in CITY_FACTS:
            await asyncio.sleep(0.20)
            return {"kind": "research", "text": "No fixture was configured for this researcher."}
        fact = CITY_FACTS[city]
        await asyncio.sleep(float(fact["delay"]))
        growth = fact["growth_rate"]
        growth_text = f" Growth rate is {growth:.2f}%." if growth is not None else ""
        return {
            "kind": "research",
            "city": city,
            "population": fact["population"],
            "growth_rate": growth,
            "source": fact["source"],
            "text": f"{city} population is {fact['population']:,}.{growth_text}",
        }

    def _run_distiller(self, state: NodeState, inputs: dict[str, Any]) -> dict[str, Any]:
        if state.metadata.get("fixture") == "shannon":
            return {
                "kind": "distilled",
                "birth_date": "30 April 1916",
                "death_date": "24 February 2001",
                "contributions": [
                    "Founded information theory and formalized information entropy.",
                    "Popularized the bit as a unit for measuring information.",
                    "Analyzed reliable communication over noisy channels.",
                ],
                "source": "https://en.wikipedia.org/wiki/Claude_Shannon",
                "text": "Birth: 30 April 1916; death: 24 February 2001; contributions: entropy, bit, noisy-channel communication.",
            }

        if state.metadata.get("required_bullets"):
            bullets = [
                "Inspect shaded clamp lips for chloride film before approving torque.",
                "Seal galvanized cut ends and document coating readings near salt exposure.",
                "Close handoff records with row ID, torque value, photos, and repair decision.",
            ]
            if state.metadata.get("fail_first"):
                bullets = bullets[:2]
            return {
                "kind": "distilled",
                "bullets": bullets,
                "text": "\n".join(f"- {bullet}" for bullet in bullets),
                "required_bullets": state.metadata["required_bullets"],
            }

        return {"kind": "distilled", "text": json.dumps(inputs, indent=2)}

    def _run_critic(self, state: NodeState, inputs: dict[str, Any]) -> dict[str, Any]:
        upstream = next(iter(inputs.values())) if inputs else {}
        required_bullets = state.metadata.get("required_bullets")
        if required_bullets:
            text = str((upstream or {}).get("text", ""))
            bullet_count = sum(1 for line in text.splitlines() if line.strip().startswith("- "))
            verdict = "pass" if bullet_count == int(required_bullets) else "fail"
            return {
                "kind": "critic",
                "verdict": verdict,
                "rationale": f"Expected {required_bullets} bullet lines and counted {bullet_count}.",
                "upstream": upstream,
            }

        if (upstream or {}).get("birth_date") and (upstream or {}).get("death_date") and len((upstream or {}).get("contributions", [])) >= 3:
            return {
                "kind": "critic",
                "verdict": "pass",
                "rationale": "The extracted Shannon fields include both dates and at least three contributions.",
                "upstream": upstream,
            }

        return {
            "kind": "critic",
            "verdict": "fail",
            "rationale": "Required fields are missing from the upstream result.",
            "upstream": upstream,
        }

    def _run_coder(self, state: NodeState, inputs: dict[str, Any]) -> dict[str, Any]:
        if state.metadata.get("fixture") == "budgets":
            budgets = {
                "Alpha": 128_750,
                "Beta": 130_500,
                "Gamma": 221_000,
                "Delta": 129_100,
            }
            pair, diff = self._closest_pair(budgets)
            code = self._closest_pair_code("budgets", budgets)
            return {
                "kind": "code",
                "code": code,
                "summary": f"Alpha and Delta are closest, with a budget difference of {diff:,}.",
                "computed": {"closest_pair": pair, "difference": diff, "unit": "budget dollars"},
            }

        city_rows = [value for value in inputs.values() if isinstance(value, dict) and value.get("city")]
        if not city_rows:
            return {
                "kind": "code",
                "code": "print('no computable inputs')",
                "summary": "No computable inputs were available.",
                "computed": {},
            }

        if all(row.get("growth_rate") is not None for row in city_rows):
            data = {row["city"]: row["growth_rate"] for row in city_rows}
            fastest = max(data, key=data.get)
            code = (
                f"growth_rates = {json.dumps(data, sort_keys=True)}\n"
                "fastest = max(growth_rates, key=growth_rates.get)\n"
                "print({'fastest': fastest, 'growth_rate': growth_rates[fastest]})\n"
            )
            return {
                "kind": "code",
                "code": code,
                "summary": f"{fastest} is growing fastest at {data[fastest]:.2f}%.",
                "computed": {"fastest": fastest, "growth_rate": data[fastest], "unit": "percent"},
            }

        populations = {row["city"]: row["population"] for row in city_rows}
        pair, diff = self._closest_pair(populations)
        code = self._closest_pair_code("populations", populations)
        return {
            "kind": "code",
            "code": code,
            "summary": f"{pair[0]} and {pair[1]} are closest in size, with a population difference of {diff:,}.",
            "computed": {"closest_pair": pair, "difference": diff, "unit": "people"},
        }

    def _run_sandbox(self, inputs: dict[str, Any]) -> dict[str, Any]:
        upstream = next(iter(inputs.values())) if inputs else {}
        code = str((upstream or {}).get("code") or "print('no code')")
        result = run_python(code)
        return {"kind": "sandbox", **result.as_dict()}

    def _run_prompt_only_skill(self, state: NodeState, inputs: dict[str, Any]) -> dict[str, Any]:
        if state.metadata.get("table_kind") == "session8_evidence":
            table = """| Requirement | Evidence |
| --- | --- |
| Base queries | `docs/session8_base_traces.txt` contains hello, A, I, J, and K/resume runs. |
| Parallel fan-out | Researcher layer runs three independent branches and logs wall time near max branch, not branch sum. |
| Critic pass/fail | `docs/session8_assignment_proofs.txt` includes one pass and one fail with recovery planner splice. |
| Coder skill | `prompts/coder.md` emits Python; coder nodes feed `sandbox_executor`. |
| New skill | `tabulator` is added in `agent_config.yaml` with `prompts/tabulator.md`; no Executor edit is needed for its plan. |"""
            return {"kind": "table", "markdown": table}
        return {
            "kind": "prompt_only",
            "skill": state.skill,
            "text": f"{state.skill} completed with inputs: {json.dumps(inputs, sort_keys=True)[:500]}",
        }

    def _run_formatter(self, state: NodeState, inputs: dict[str, Any]) -> dict[str, Any]:
        if state.metadata.get("answer"):
            return {"kind": "answer", "text": state.metadata["answer"]}

        values = [value for value in inputs.values() if isinstance(value, dict)]
        if len(values) == 1 and values[0].get("kind") == "critic":
            critic = values[0]
            upstream = critic.get("upstream") or {}
            if upstream.get("birth_date"):
                contributions = "\n".join(f"{idx}. {item}" for idx, item in enumerate(upstream["contributions"], start=1))
                text = (
                    f"Claude Shannon was born on {upstream['birth_date']} and died on {upstream['death_date']}.\n\n"
                    f"Three key contributions:\n{contributions}"
                )
            elif upstream.get("bullets"):
                text = "The Critic passed the verifiable three-item list:\n" + "\n".join(
                    f"- {bullet}" for bullet in upstream["bullets"]
                )
            else:
                text = critic.get("rationale", "Critic result was received.")
            return {"kind": "answer", "text": text}

        if len(values) == 1 and values[0].get("kind") == "code":
            computed = values[0].get("computed", {})
            if "closest_pair" in computed:
                pair = computed["closest_pair"]
                text = (
                    f"The two closest are {pair[0]} and {pair[1]}, with a difference of "
                    f"{computed['difference']:,} {computed['unit']}."
                )
            elif "fastest" in computed:
                text = (
                    f"{computed['fastest']} is growing fastest at "
                    f"{computed['growth_rate']:.2f}%."
                )
            else:
                text = values[0].get("summary", "The computation completed.")
            return {"kind": "answer", "text": text}

        if len(values) == 1 and values[0].get("kind") == "table":
            return {"kind": "answer", "text": values[0]["markdown"]}

        if values and all(value.get("kind") == "research" for value in values):
            lines = [f"- {value.get('topic', value.get('city', 'item'))}: {value.get('text')}" for value in values]
            return {"kind": "answer", "text": "Parallel research results:\n" + "\n".join(lines)}

        text = "\n".join(str(value.get("text") or value) for value in values) or "Done."
        return {"kind": "answer", "text": text}

    def _closest_pair(self, data: dict[str, int | float]) -> tuple[list[str], int | float]:
        names = list(data)
        best_pair: tuple[str, str] | None = None
        best_diff = math.inf
        for i, left in enumerate(names):
            for right in names[i + 1 :]:
                diff = abs(data[left] - data[right])
                if diff < best_diff:
                    best_diff = diff
                    best_pair = (left, right)
        assert best_pair is not None
        return list(best_pair), int(best_diff) if float(best_diff).is_integer() else best_diff

    def _closest_pair_code(self, variable_name: str, data: dict[str, int | float]) -> str:
        return (
            f"{variable_name} = {json.dumps(data, sort_keys=True)}\n"
            "names = list(" + variable_name + ")\n"
            "best_pair = None\n"
            "best_diff = None\n"
            "for i, left in enumerate(names):\n"
            "    for right in names[i + 1:]:\n"
            f"        diff = abs({variable_name}[left] - {variable_name}[right])\n"
            "        if best_diff is None or diff < best_diff:\n"
            "            best_pair = (left, right)\n"
            "            best_diff = diff\n"
            "print({'closest_pair': best_pair, 'difference': best_diff})\n"
        )

    def _final_answer(self) -> str:
        formatter_nodes = [
            node_id
            for node_id, attrs in self.graph.nodes(data=True)
            if attrs.get("skill") == "formatter" and attrs.get("status") == "complete"
        ]
        if formatter_nodes:
            latest = sorted(formatter_nodes)[-1]
            result = self._state(latest).result or {}
            return str(result.get("text") or result)
        failed = [
            f"{node_id}: {attrs.get('error')}"
            for node_id, attrs in self.graph.nodes(data=True)
            if attrs.get("status") == "failed"
        ]
        return "No final formatter completed." + ("\n" + "\n".join(failed) if failed else "")

    def _short_result(self, result: dict[str, Any]) -> str:
        if "rationale" in result:
            return result["rationale"]
        if "verdict" in result:
            return f"{result['verdict']} - {result.get('rationale')}"
        if "summary" in result:
            return result["summary"]
        if "text" in result:
            return str(result["text"]).replace("\n", " ")[:180]
        if "stdout" in result:
            return f"exit={result.get('exit_code')} stdout={str(result.get('stdout')).strip()[:120]}"
        if "markdown" in result:
            return "generated evidence table"
        return json.dumps(result, sort_keys=True)[:180]


def session_id_for(query: str) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in query.lower()).strip("_")
    slug = "_".join(part for part in slug.split("_") if part)[:36] or "session"
    return f"s8_{slug}_{uuid.uuid4().hex[:6]}"


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Session 8 DAG demo runner")
    parser.add_argument("query", nargs="?", help="User query to run")
    parser.add_argument("--session", help="Session id to write/read")
    parser.add_argument("--resume", help="Resume an existing session id")
    parser.add_argument("--config", default="agent_config.yaml")
    parser.add_argument("--stop-after-complete", type=int, help="Stop after N completed nodes to demonstrate resume")
    args = parser.parse_args()

    if args.resume:
        session_id = args.resume
        store = SessionStore(session_id)
        query = store.load_query()
        resume = True
    else:
        if not args.query:
            raise SystemExit("query is required unless --resume is used")
        query = args.query
        session_id = args.session or session_id_for(query)
        store = SessionStore(session_id)
        resume = False

    catalog = SkillCatalog.load(Path(args.config))
    agent = DemoDAGAgent(
        query=query,
        session_id=session_id,
        catalog=catalog,
        store=store,
        resume=resume,
        stop_after_complete=args.stop_after_complete,
    )
    await agent.run()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
