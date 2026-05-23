from __future__ import annotations

import json
from typing import Any

from schemas import PerceptionInput, PerceptionOutput


PERCEPTION_PROMPT = """You are the Perception layer in a four-layer agent.

Convert the user's request and recent observations into a compact typed view of
the task. Do not answer the user. Do not call tools. Identify likely tools, any
facts the user explicitly wants stored, and the criteria for a correct final
answer.

Tool names you may mention:
web_search, fetch_url, get_time, currency_convert, read_file, list_dir,
create_file, update_file, edit_file, remember, final_answer.

Use facts_to_remember only for durable facts explicitly supplied by the user,
such as "remember that ..." or "my ... is ...". Preserve the fact accurately.
"""


class PerceptionLayer:
    def __init__(self, llm: Any):
        self.llm = llm

    def run(self, request: PerceptionInput) -> PerceptionOutput:
        payload = request.model_dump_json(indent=2)
        response = self.llm.chat(
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
            response_format={
                "type": "json_schema",
                "schema": PerceptionOutput.model_json_schema(),
                "name": "perception_output",
                "strict": True,
            },
            max_tokens=1200,
            temperature=0.2,
        )
        parsed = response.get("parsed")
        if parsed is None:
            parsed = json.loads(response["text"])
        return PerceptionOutput.model_validate(parsed)
