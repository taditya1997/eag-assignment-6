#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))

    spec = importlib.util.spec_from_file_location("test_recovery", root / "tests" / "test_recovery.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load tests/test_recovery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.test_transient_failures_are_not_replanned()
    module.test_validation_failures_are_prompt_or_schema_errors()
    module.test_unknown_failures_are_upstream_failures()
    with tempfile.TemporaryDirectory() as tmp:
        module.test_critic_failure_splices_recovery_planner(Path(tmp))

    print("session8 recovery tests passed")


if __name__ == "__main__":
    main()
