from __future__ import annotations

import asyncio

from flow import DemoDAGAgent
from persistence import SessionStore
from recovery import FailureKind, classify_failure
from skills import SkillCatalog


def test_transient_failures_are_not_replanned() -> None:
    samples = [
        "HTTPStatusError: 503 Service Unavailable",
        "502 Bad Gateway from provider",
        "Gateway timeout after retries",
        "ConnectionError: socket closed",
        "request timed out",
    ]
    for sample in samples:
        assert classify_failure(sample) == FailureKind.TRANSIENT


def test_validation_failures_are_prompt_or_schema_errors() -> None:
    samples = [
        "ValidationError: nodes.0.skill field required",
        "malformed planner JSON",
        "invalid json from worker",
        "pydantic validation error",
    ]
    for sample in samples:
        assert classify_failure(sample) == FailureKind.VALIDATION_ERROR


def test_unknown_failures_are_upstream_failures() -> None:
    assert classify_failure("critic verdict failed requested evidence check") == FailureKind.UPSTREAM_FAILURE


def test_critic_failure_splices_recovery_planner(tmp_path) -> None:
    catalog = SkillCatalog.load("agent_config.yaml")
    store = SessionStore("critic_splice_test", root=tmp_path)
    agent = DemoDAGAgent(
        query="Critic fail: produce exactly three safety checks for coastal solar supports.",
        session_id="critic_splice_test",
        catalog=catalog,
        store=store,
    )

    result = asyncio.run(agent.run())

    labels = {attrs["label"]: attrs for _, attrs in agent.graph.nodes(data=True)}
    assert "recovery_critic_safety_checks_out" in labels
    assert labels["out"]["status"] == "skipped"
    assert labels["out_recovered"]["status"] == "complete"
    assert "Critic passed" in result["final_answer"]
