from __future__ import annotations

import json
from typing import Any

from schemas import DecisionInput, DecisionOutput


DECISION_PROMPT = """You are the Decision layer in a four-layer agent.

Choose exactly one next action. Return only the typed JSON contract.

Rules:
- Use remember when the user explicitly provided a durable fact to store.
- Use final_answer when current observations and memory are sufficient.
- Use get_time for current time/date questions.
- Use currency_convert for exchange-rate conversions.
- Use web_search for current or external facts. Use fetch_url after search when
  snippets are insufficient or the user asks for details from a page.
- Use read_file/list_dir/create_file/update_file/edit_file for sandbox file
  tasks. File tools operate inside the MCP server sandbox.
- Do not repeat an action if its observation already answers the need.
- When near max_iterations, prefer final_answer with the best supported answer.

For next_action, fill the matching payload object and leave the others null.
"""


class DecisionLayer:
    def __init__(self, llm: Any):
        self.llm = llm

    def run(self, request: DecisionInput) -> DecisionOutput:
        payload = request.model_dump_json(indent=2)
        response = self.llm.chat(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Decide the next agent action from this state:\n"
                        f"{payload}"
                    ),
                }
            ],
            system=DECISION_PROMPT,
            auto_route="decision",
            response_format={
                "type": "json_schema",
                "schema": DecisionOutput.model_json_schema(),
                "name": "decision_output",
                "strict": True,
            },
            max_tokens=1800,
            temperature=0.2,
        )
        parsed = response.get("parsed")
        if parsed is None:
            parsed = json.loads(response["text"])
        return DecisionOutput.model_validate(parsed)
