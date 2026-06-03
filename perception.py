from __future__ import annotations
from typing import Any

from llm_json import call_json_contract
from schemas import PerceptionInput, PerceptionOutput


PERCEPTION_PROMPT = """You are the Perception layer in a four-layer agent.

Convert the user's request and recent observations into a compact typed view of
the task. Do not answer the user. Do not call tools. Describe the user's intent,
any durable facts the user explicitly wants stored, and the criteria for a
correct final answer. Keep the view at the intent/capability level and do not
name concrete external actions.

Use the durable-facts list only for facts explicitly supplied by the user, such
as personal dates or stable preferences. Preserve the fact accurately.
"""


class PerceptionLayer:
    def __init__(self, llm: Any):
        self.llm = llm

    def run(self, request: PerceptionInput) -> PerceptionOutput:
        payload = request.model_dump_json(indent=2)
        return call_json_contract(
            self.llm,
            model_type=PerceptionOutput,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Perceive this agent state and return the typed JSON "
                        f"contract only:\n{payload}"
                    ),
                }
            ],
            system=PERCEPTION_PROMPT,
            auto_route="perception",
            name="perception_output",
            max_tokens=1200,
            temperature=0.2,
        )
