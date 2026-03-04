import json
import os
import time

import pandas as pd
from dotenv import load_dotenv

from core.agent import agent_executor
from core.logging import ExperimentLogger

from exp_config import MODEL

load_dotenv()

DATASET = "data/dataset.json"


def run_bench():
    log = ExperimentLogger()

    with open(DATASET, encoding="utf-8") as f:
        tasks = json.load(f)

    log.run_start(model=MODEL, dataset=DATASET)

    results = []
    for task in tasks:
        log.task_start(task=task["name"], requirement=task["prompt"])

        task_start = time.time()
        final_state = agent_executor.invoke({
            "requirement": task["prompt"],
            "oracle": task["test"],
            "task": task["name"],
            "attempts": 0,
            "is_passing": False,
            "logger": log,
            "code": "",
            "errors": "",
            "tokens_input": 0,
            "tokens_output": 0,
            "task_start_time": 0.0,
        })
        task_elapsed = time.time() - task_start

        passed = final_state["is_passing"]
        total_attempts = final_state["attempts"]
        tokens_input = final_state.get("tokens_input", 0)
        tokens_output = final_state.get("tokens_output", 0)

        log.task_end(
            task=task["name"],
            passed=passed,
            total_attempts=total_attempts,
            elapsed_s=task_elapsed,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        )

        results.append({
            "task": task["name"],
            "passed": passed,
            "total_attempts": total_attempts,
            "elapsed_s": task_elapsed,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
        })

    passed_count = sum(1 for r in results if r["passed"])
    log.run_end(total_tasks=len(results), passed=passed_count)

    print(f"Full log: logs/{log.run_id}.log")


if __name__ == "__main__":
    run_bench()
