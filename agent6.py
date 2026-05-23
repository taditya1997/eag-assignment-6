from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from action import ActionLayer
from decision import DecisionLayer
from llm_gatewayV3.client import LLM
from memory import FileMemory
from perception import PerceptionLayer
from schemas import (
    ActionInput,
    AgentResult,
    DecisionInput,
    FinalAnswerAction,
    MemoryRecallInput,
    PerceptionInput,
    ToolObservation,
)


ROOT = Path(__file__).parent
DEFAULT_STATE = ROOT / "state" / "memory.json"
DEFAULT_MCP_SERVER = ROOT / "mcp_server.py"


def _compact_observation(obs: ToolObservation, raw_limit: int = 3000) -> ToolObservation:
    raw = obs.raw_json
    if len(raw) > raw_limit:
        raw = raw[:raw_limit] + "... [truncated]"
    return obs.model_copy(update={"raw_json": raw})


async def run_agent(
    query: str,
    *,
    max_iterations: int = 8,
    state_path: Path = DEFAULT_STATE,
    mcp_server: Path = DEFAULT_MCP_SERVER,
    gateway_url: str | None = None,
    reset_state: bool = False,
    trace: bool = True,
) -> AgentResult:
    load_dotenv(ROOT / ".env")
    llm = LLM(base_url=gateway_url or os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101"))
    memory = FileMemory(state_path, llm=llm)
    if reset_state:
        memory.clear()

    perception = PerceptionLayer(llm)
    decision = DecisionLayer(llm)
    observations: list[ToolObservation] = []

    async with ActionLayer(mcp_server, memory) as action_layer:
        for iteration in range(1, max_iterations + 1):
            compact_observations = [_compact_observation(obs) for obs in observations]
            perceived = perception.run(
                PerceptionInput(query=query, observations=compact_observations)
            )
            recalled = memory.recall(
                MemoryRecallInput(query=query, perception=perceived, max_facts=5)
            )
            plan = decision.run(
                DecisionInput(
                    query=query,
                    perception=perceived,
                    memory=recalled,
                    observations=compact_observations,
                    iteration=iteration,
                    max_iterations=max_iterations,
                )
            )
            action = plan.to_action()

            if trace:
                print(f"[{iteration}] perception: {perceived.query_type} -> {perceived.user_goal}")
                print(f"[{iteration}] decision: {action.kind} ({plan.rationale})")

            if isinstance(action, FinalAnswerAction):
                if trace and action.sources:
                    print(f"[{iteration}] sources: {', '.join(action.sources)}")
                return AgentResult(
                    query=query,
                    answer=action.answer,
                    iterations=iteration,
                    observations=observations,
                )

            observation = await action_layer.run(
                ActionInput(iteration=iteration, action=action, source_query=query)
            )
            observations.append(_compact_observation(observation, raw_limit=6000))
            if trace:
                status = "ok" if observation.ok else "error"
                print(f"[{iteration}] action {status}: {observation.summary}")

    raise RuntimeError(
        f"Agent did not converge within {max_iterations} iterations for query: {query}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Session 6 four-layer agent.")
    parser.add_argument("query", help="User query to answer")
    parser.add_argument("--max-iterations", type=int, default=8)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--mcp-server", type=Path, default=DEFAULT_MCP_SERVER)
    parser.add_argument("--gateway-url", default=None)
    parser.add_argument("--reset-state", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Only print the final answer")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await run_agent(
        args.query,
        max_iterations=args.max_iterations,
        state_path=args.state_path,
        mcp_server=args.mcp_server,
        gateway_url=args.gateway_url,
        reset_state=args.reset_state,
        trace=not args.quiet,
    )
    if not args.quiet:
        print()
    print("FINAL ANSWER:")
    print(result.answer)
    print(f"ITERATIONS: {result.iterations}")


if __name__ == "__main__":
    asyncio.run(main())
