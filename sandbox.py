from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass


ALLOWED_ENV = {"PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE"}
OUTPUT_LIMIT = 1_000_000


@dataclass(frozen=True)
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False

    def as_dict(self) -> dict:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
        }


def run_python(code: str, *, timeout_s: int = 30) -> SandboxResult:
    """Run generated Python in a temp directory.

    This is a demo usability boundary, not a security sandbox. It catches common
    mistakes and gives the DAG an execution branch, but it is not meant for
    hostile code.
    """

    env = {key: value for key, value in os.environ.items() if key in ALLOWED_ENV}
    with tempfile.TemporaryDirectory(prefix="s8_sandbox_") as tmpdir:
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=tmpdir,
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return SandboxResult(
                stdout=(exc.stdout or "")[:OUTPUT_LIMIT],
                stderr=(exc.stderr or "")[:OUTPUT_LIMIT],
                exit_code=124,
                timed_out=True,
            )

    return SandboxResult(
        stdout=(proc.stdout or "")[:OUTPUT_LIMIT],
        stderr=(proc.stderr or "")[:OUTPUT_LIMIT],
        exit_code=proc.returncode,
        timed_out=False,
    )
