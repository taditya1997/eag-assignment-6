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
