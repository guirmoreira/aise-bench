from typing import TypedDict
from langgraph.graph import StateGraph, END
from litellm import completion
from .sandbox import run_code_in_sandbox
from langsmith import traceable

class AgentState(TypedDict):
    requirement: str
    oracle: str
    code: str
    errors: str
    attempts: int
    is_passing: bool

@traceable(run_type="llm")
def generator_node(state: AgentState):
    prompt = f"Tarefa: {state['requirement']}\nEscreva apenas o código Python."
    # O LiteLLM enviará o trace para o LangSmith automaticamente se as chaves estiverem no .env
    response = completion(model="gpt-5-mini", messages=[{"role": "user", "content": prompt}])
    return {"code": response.choices[0].message.content.strip().replace("```python", "").replace("```", ""), "attempts": state['attempts'] + 1}

def tester_node(state: AgentState):
    success, logs = run_code_in_sandbox(state['code'], state['oracle'])
    return {"is_passing": success, "errors": logs}

@traceable(run_type="llm")
def refactor_node(state: AgentState):
    prompt = f"O código falhou com o erro: {state['errors']}\nCorrija-o:\n{state['code']}"
    response = completion(model="gpt-5-mini", messages=[{"role": "user", "content": prompt}])
    return {"code": response.choices[0].message.content.strip(), "attempts": state['attempts'] + 1}

# Lógica de controle do Grafo
workflow = StateGraph(AgentState)
workflow.add_node("gen", generator_node)
workflow.add_node("test", tester_node)
workflow.add_node("refactor", refactor_node)

workflow.set_entry_point("gen")
workflow.add_edge("gen", "test")
workflow.add_conditional_edges("test", lambda x: "end" if x["is_passing"] or x["attempts"] >= 3 else "refactor", {"end": END, "refactor": "refactor"})
workflow.add_edge("refactor", "test")

agent_executor = workflow.compile()