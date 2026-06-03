from __future__ import annotations
from typing import Any

from llm_json import call_json_contract
from schemas import DecisionInput, DecisionOutput


DECISION_PROMPT = """You are the Decision layer in a four-layer agent.

Choose exactly one next action. Return only the typed JSON contract.

Rules:
- Use remember when the user explicitly provided a durable fact to store.
- Use final_answer when current observations and memory are sufficient. The
  final answer must directly satisfy the user's requested output. Never use
  final_answer to say you still need to inspect, process, synthesize, or do a
  next step; choose the needed action instead.
- For web-research final answers, use the search result titles/snippets and
  fetched text already visible in observations. Do not answer with only a list
  of URLs when the user asked for a synthesis, recommendation, comparison, or
  numbered list.
- Use get_time for current time/date questions.
- Use currency_convert for exchange-rate conversions.
- Use web_search for current or external facts. Use fetch_url after search when
  snippets are insufficient or the user asks for details from a page.
- Use read_file/list_dir/create_file/update_file/edit_file for sandbox file
  tasks. File tools operate inside the MCP server sandbox.
- If the user asks to create reminders and no calendar/reminder tool exists,
  create plain-text reminder files in the sandbox with create_file, one file
  per reminder. Use root-level filenames unless a directory is known to exist.
  After the fact is remembered and the files are created, final_answer should
  name the remembered fact and the reminder files.
- Use index_document when a sandbox document must become searchable across
  later turns or runs. For one-shot inspection of a file's contents, use
  read_file instead.
- Use search_knowledge for questions over documents that have already been
  indexed into Memory. Prefer it to re-reading source files when the indexed
  chunks are the relevant corpus.
- If search_knowledge returns no chunks for a question that explicitly asks
  about indexed knowledge, use final_answer to say the indexed corpus has no
  available matching evidence. Do not switch to web_search for that same
  indexed-corpus question.
- Do not repeat the same action with the same arguments. If a page or search
  was already tried and did not expose a cleaner answer, use the best available
  evidence instead of trying the same source again.
- If exact weather details remain unclear after a weather source was searched
  or fetched, answer with a caveat and recommend the most weather-robust option.
- On the final iteration, choose final_answer. Never spend the final iteration
  on another tool call.

For next_action, fill the matching payload object and leave the others null.
"""

FINAL_ITERATION_PROMPT = DECISION_PROMPT + """

Final-iteration override:
You are already on the final allowed iteration. You must set next_action to
final_answer and fill final_answer.answer from the observations and memory
already visible. Do not choose any other action.

The final answer must be useful. Never say only that you could not extract the
answer or provide only links if the observations contain search titles,
snippets, or fetched text. For recommendation tasks, list the requested options,
state any uncertainty as a caveat, and still make the best supported
recommendation from the evidence already visible.
"""


class DecisionLayer:
    def __init__(self, llm: Any):
        self.llm = llm

    def run(self, request: DecisionInput) -> DecisionOutput:
        payload = request.model_dump_json(indent=2)
        result = call_json_contract(
            self.llm,
            model_type=DecisionOutput,
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
            name="decision_output",
            max_tokens=1800,
            temperature=0.2,
        )
        if request.iteration >= request.max_iterations and result.next_action != "final_answer":
            return call_json_contract(
                self.llm,
                model_type=DecisionOutput,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Produce the final answer from this agent state. "
                            "Do not call another tool.\n"
                            f"{payload}"
                        ),
                    }
                ],
                system=FINAL_ITERATION_PROMPT,
                auto_route="decision",
                name="decision_output",
                max_tokens=1800,
                temperature=0.1,
            )
        return result
