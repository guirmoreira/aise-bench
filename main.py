import json
import os

import pandas as pd
from dotenv import load_dotenv
from langsmith import traceable

from core.agent import agent_executor

load_dotenv()

# Ativa o LangSmith para logging científico
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "Mestrado"


@traceable
def run_bench():
    # Exemplo de Dataset: histórias de usuário + oráculos (testes)
    with open("data/dataset.json") as f:
        tasks = json.load(f)

    results = []
    for task in tasks:
        print(f"🚀 Testando: {task['name']}")

        # Executa o grafo agêntico
        final_state = agent_executor.invoke({
            "requirement": task["prompt"],
            "oracle": task["test"],
            "attempts": 0,
            "is_passing": False
        })

        results.append({
            "task": task["name"],
            "passed": final_state["is_passing"],
            "total_attempts": final_state["attempts"]
        })

    # Exporta para CSV para análise estatística no seu artigo/dissertação
    df = pd.DataFrame(results)
    df.to_csv("resultados_experimento.csv", index=False)
    print("✅ Experimento concluído. Resultados salvos.")


if __name__ == "__main__":
    run_bench()if __name__ == "__main__":
    run_bench()
