from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from decision import DECISION_PROMPT
from perception import PERCEPTION_PROMPT
from schemas import DecisionOutput, PerceptionOutput


payload = {
    "perception": {
        "prompt": PERCEPTION_PROMPT,
        "validation_schema": PerceptionOutput.model_json_schema(),
    },
    "decision": {
        "prompt": DECISION_PROMPT,
        "validation_schema": DecisionOutput.model_json_schema(),
    },
}

out = ROOT / "docs" / "pop_validation.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(out)

perception_out = ROOT / "docs" / "perception_pop_submission.md"
perception_out.write_text(
    "# Perception Prompt And PoP Validation JSON\n\n"
    "## Prompt\n\n"
    f"```text\n{PERCEPTION_PROMPT}\n```\n\n"
    "## Validation JSON\n\n"
    "```json\n"
    f"{json.dumps(PerceptionOutput.model_json_schema(), indent=2)}\n"
    "```\n",
    encoding="utf-8",
)
print(perception_out)

decision_out = ROOT / "docs" / "decision_pop_submission.md"
decision_out.write_text(
    "# Decision Prompt And PoP Validation JSON\n\n"
    "## Prompt\n\n"
    f"```text\n{DECISION_PROMPT}\n```\n\n"
    "## Validation JSON\n\n"
    "```json\n"
    f"{json.dumps(DecisionOutput.model_json_schema(), indent=2)}\n"
    "```\n",
    encoding="utf-8",
)
print(decision_out)
