"""
core/logging.py — Structured experiment logger for AISE-Bench.

Each log line follows the format:
    yyyy-mm-dd hh:mm:ss:ms [KEY] {metadata} value

Where:
    KEY      — event type (e.g. GENERATION, TEST_RESULT, TASK_END)
    metadata — JSON object with contextual dimensions for analysis
    value    — the main payload of the event (string, possibly multi-line)

A new log file named  <run_id>.log  is created per experiment run.
run_id = sha1(iso_timestamp)[:8]  — short, unique, reproducible.

Usage:
    from core.logging import ExperimentLogger

    logger = ExperimentLogger()          # creates logs/<run_id>.log
    logger.run_start(model="gpt-4.1", dataset="dataset.json")
    logger.task_start(task="fibonacci_memo", requirement="...")
    logger.generation(task="fibonacci_memo", attempt=1, code="...")
    logger.test_result(task="fibonacci_memo", attempt=1,
                       passed=False, output="AssertionError ...")
    logger.refactor(task="fibonacci_memo", attempt=2, error="...", code="...")
    logger.task_end(task="fibonacci_memo", passed=True, total_attempts=2)
    logger.run_end(total_tasks=5, passed=4)
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_LOGS_DIR = Path("logs")


def _now() -> str:
    """Return current UTC timestamp as  yyyy-mm-dd hh:mm:ss:ms."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S:") + f"{now.microsecond // 1000:04d}"


def _make_run_id() -> str:
    """Short deterministic ID based on the wall-clock at logger creation."""
    now = datetime.now(timezone.utc)
    raw = now.isoformat()
    millis = int(now.timestamp() * 1000)
    return f"{millis}-{hashlib.sha1(raw.encode()).hexdigest()[:8]}"


def _serialize_meta(meta: dict[str, Any]) -> str:
    return json.dumps(meta, ensure_ascii=False, separators=(", ", ": "))


def _indent_value(value: str, spaces: int = 4) -> str:
    """Indent every line of a multi-line value for readable log files."""
    if "\n" not in value:
        return value
    pad = " " * spaces
    lines = value.splitlines()
    # First line stays on the same line as the metadata; rest are indented.
    return lines[0] + "\n" + "\n".join(pad + ln for ln in lines[1:])


# ---------------------------------------------------------------------------
# ExperimentLogger
# ---------------------------------------------------------------------------

class ExperimentLogger:
    """Writes structured log lines to both stdout and a per-run .log file."""

    def __init__(self, logs_dir: str | Path = _LOGS_DIR) -> None:
        self.run_id = _make_run_id()
        self._dir = Path(logs_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

        self._log_path = self._dir / f"{self.run_id}.log"
        self._fh = self._log_path.open("a", encoding="utf-8")

        # Write a blank separator if the file already existed (shouldn't
        # happen with a fresh run_id, but defensive).
        if self._fh.tell() > 0:
            self._fh.write("\n")

    # ------------------------------------------------------------------
    # Public API — one method per semantic event
    # ------------------------------------------------------------------

    def run_start(self, *, model: str, dataset: str) -> None:
        self._write(
            key="RUN_START",
            meta={"run_id": self.run_id, "model": model, "dataset": dataset},
            value=f"Experiment started — model={model} dataset={dataset}",
        )

    def run_end(self, *, total_tasks: int, passed: int) -> None:
        failed = total_tasks - passed
        rate = round(passed / total_tasks * 100, 2) if total_tasks else 0.0
        self._write(
            key="RUN_END",
            meta={
                "run_id": self.run_id,
                "total_tasks": total_tasks,
                "passed": passed,
                "failed": failed,
                "success_rate_pct": rate,
            },
            value=(
                f"Experiment finished — "
                f"{passed}/{total_tasks} tasks passed ({rate}%)"
            ),
        )
        self._fh.close()

    def task_start(self, *, task: str, requirement: str) -> None:
        self._write(
            key="TASK_START",
            meta={"run_id": self.run_id, "task": task},
            value=requirement,
        )

    def task_end(
        self,
        *,
        task: str,
        passed: bool,
        total_attempts: int,
        elapsed_s: float = 0.0,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
        tokens_total = tokens_input + tokens_output
        self._write(
            key="TASK_END",
            meta={
                "run_id": self.run_id,
                "task": task,
                "passed": passed,
                "total_attempts": total_attempts,
                "elapsed_s": round(elapsed_s, 3),
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "tokens_total": tokens_total,
            },
            value=(
                f"passed={passed} total_attempts={total_attempts} "
                f"elapsed_s={round(elapsed_s, 3)} tokens_total={tokens_total}"
            ),
        )

    def generation(
        self,
        *,
        task: str,
        attempt: int,
        code: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
        self._write(
            key="GENERATION",
            meta={
                "run_id": self.run_id,
                "task": task,
                "attempt": attempt,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "tokens_total": tokens_input + tokens_output, },
            value=f"<code>\n{code}\n</code>",
        )

    def prompt_sent(
        self,
        *,
        task: str,
        attempt: int,
        agent: str,
        messages: list,
    ) -> None:
        """Logs the full prompt (list of messages) sent to the LLM."""
        import json as _json
        self._write(
            key="PROMPT_SENT",
            meta={
                "run_id": self.run_id,
                "task": task,
                "attempt": attempt,
                "agent": agent,
                "n_messages": len(messages),
            },
            value=_json.dumps(messages, ensure_ascii=False, indent=2),
        )

    def test_result(
        self, *, task: str, attempt: int, passed: bool, output: str
    ) -> None:
        self._write(
            key="TEST_RESULT",
            meta={
                "run_id": self.run_id,
                "task": task,
                "attempt": attempt,
                "passed": passed,
            },
            value=output if output else "(no output)",
        )

    def refactor(
        self,
        *,
        task: str,
        attempt: int,
        error: str,
        code: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
        tokens_total = tokens_input + tokens_output
        # Log the error that triggered the refactor, then the new code.
        self._write(
            key="REFACTOR_INPUT",
            meta={
                "run_id": self.run_id,
                "task": task,
                "attempt": attempt,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "tokens_total": tokens_total,
            },
            value=error if error else "(no error message)",
        )
        self._write(
            key="REFACTOR_OUTPUT",
            meta={
                "run_id": self.run_id,
                "task": task,
                "attempt": attempt,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "tokens_total": tokens_total,
            },
            value=code,
        )

    def sdk_error(self, *, task: str, attempt: int, context: str, detail: str) -> None:
        self._write(
            key="SDK_ERROR",
            meta={
                "run_id": self.run_id,
                "task": task,
                "attempt": attempt,
                "context": context,
            },
            value=detail if detail else "(empty error object)",
        )

    def sdk_timeout(self, *, task: str, attempt: int, model: str, timeout_s: float) -> None:
        self._write(
            key="SDK_TIMEOUT",
            meta={
                "run_id": self.run_id,
                "task": task,
                "attempt": attempt,
                "model": model,
                "timeout_s": timeout_s,
            },
            value=f"No response from model within {timeout_s}s",
        )

    def hook_tool_call(self, *, task: str, tool: str, args: dict) -> None:
        self._write(
            key="HOOK_TOOL_CALL",
            meta={"run_id": self.run_id, "task": task, "tool": tool},
            value=json.dumps(args, ensure_ascii=False),
        )

    def hook_tool_result(
        self, *, task: str, tool: str, passed: bool | None, logs: str
    ) -> None:
        self._write(
            key="HOOK_TOOL_RESULT",
            meta={
                "run_id": self.run_id,
                "task": task,
                "tool": tool,
                "passed": passed,
            },
            value=logs if logs else "(no output)",
        )

    # ------------------------------------------------------------------
    # Low-level writer
    # ------------------------------------------------------------------

    def _write(self, *, key: str, meta: dict[str, Any], value: str) -> None:
        timestamp = _now()
        meta_str = _serialize_meta(meta)
        value_str = _indent_value(value.strip())

        line = f"{timestamp} [{key}] {{{meta_str}}} {value_str}\n\n"

        # Console (stdout)
        sys.stdout.write(line)
        sys.stdout.flush()

        # File
        self._fh.write(line)
        self._fh.flush()

    # ------------------------------------------------------------------
    # Context-manager support  (with ExperimentLogger() as log: ...)
    # ------------------------------------------------------------------

    def __enter__(self) -> "ExperimentLogger":
        return self

    def __exit__(self, *_) -> None:
        if not self._fh.closed:
            self._fh.close()
