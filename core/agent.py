"""
agent.py — Motor agêntico usando LiteLLM como backend de inferência.

Fluxo LangGraph:
    gen ──► test ──► [pass/max_attempts → END | fail → refactor] ──► test (loop)

Extensibilidade:
    - CUSTOM_TOOLS   : ferramentas disponíveis para o agente
    - CUSTOM_AGENTS  : personas/agentes especializados com prompts específicos
"""

import json
import os
import time
from typing import Any, Callable, TypedDict

from langgraph.graph import END, StateGraph
from litellm import completion
from pydantic import BaseModel, Field

from exp_config import (MAX_ATTEMPTS, MAX_CODE_LENGTH, MAX_ERROR_LENGTH, MODEL,
                        OPENAI_API_URL, TEMPERATURE, TIMEOUT)

from .logging import ExperimentLogger
from .sandbox import run_code_in_sandbox

# ──────────────────────────────────────────────
# 1. Estado do grafo
# ──────────────────────────────────────────────


class AgentState(TypedDict):
    requirement: str
    oracle: str
    task: str               # dataset task name — used in log metadata
    code: str
    errors: str
    attempts: int
    is_passing: bool
    logger: ExperimentLogger
    # --- metrics accumulated across the whole task ---
    tokens_input: int       # cumulative prompt tokens across all LLM calls
    tokens_output: int      # cumulative completion tokens across all LLM calls
    task_start_time: float  # time.monotonic() set by generator_node on attempt #1


# ──────────────────────────────────────────────
# 2. Ferramentas customizadas (Function Calling)
# ──────────────────────────────────────────────

class RunTestsParams(BaseModel):
    code: str = Field(description="Python code to validate")
    oracle: str = Field(description="Test suite to run against the code")


def run_tests_tool(code: str, oracle: str) -> dict:
    """Executes code inside an isolated Docker sandbox and returns pass/fail + logs"""
    success, logs = run_code_in_sandbox(code, oracle)
    return {"success": success, "logs": logs}


# Definição de ferramentas para function calling (formato OpenAI)
CUSTOM_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "run_tests_tool",
            "description": "Executes code inside an isolated Docker sandbox and returns pass/fail + logs",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to validate"
                    },
                    "oracle": {
                        "type": "string",
                        "description": "Test suite to run against the code"
                    }
                },
                "required": ["code", "oracle"]
            }
        }
    }
]

# Mapeamento de nomes de funções para callables
TOOL_FUNCTIONS: dict[str, Callable] = {
    "run_tests_tool": run_tests_tool,
}


# ──────────────────────────────────────────────
# 3. Agentes personalizados (personas)
# ──────────────────────────────────────────────

CUSTOM_AGENTS: dict[str, dict] = {
    "python-generator": {
        "name": "Python Code Generator",
        "system_prompt": """You are an expert Python developer specializing in writing clean, idiomatic, and correct Python code.

Your responsibilities:
- Write ONLY executable Python code
- Use standard library whenever possible
- Follow PEP 8 style guidelines
- Write concise, readable code
- Do NOT include markdown code fences (```)
- Do NOT include explanations or comments unless critical
- Focus on correctness first, then readability

Output format: Raw Python code only, no markdown, no explanations."""
    },
    "python-debugger": {
        "name": "Python Debugger",
        "system_prompt": """You are an expert Python debugging specialist.

Your responsibilities:
- Analyze failing code and error messages carefully
- Identify the root cause of the error
- Fix the bug with minimal changes
- Return ONLY the corrected Python code
- Do NOT include markdown code fences (```)
- Do NOT include explanations
- Preserve the original logic when possible

Output format: Raw corrected Python code only, no markdown, no explanations."""
    },
}


# ──────────────────────────────────────────────
# 4. Helper: chamar LiteLLM
# ──────────────────────────────────────────────

def _truncate_text(text: str, max_length: int) -> str:
    """Trunca texto mantendo o final (mais importante para erros)."""
    if len(text) <= max_length:
        return text
    return "...[truncated]...\n" + text[-max_length:]


def _call_llm(
    messages: list[dict],
    agent_type: str = "python-generator",
    use_tools: bool = False,
    log: ExperimentLogger | None = None,
    task: str = "",
    attempt: int = 0,
) -> tuple[str, int, int, list[dict] | None]:
    """
    Chama LiteLLM com o modelo configurado e retorna:
    (resposta, tokens_input, tokens_output, tool_calls)

    Args:
        messages: Lista de mensagens no formato OpenAI
        agent_type: Tipo de agente (determina o system prompt)
        use_tools: Se True, inclui ferramentas disponíveis
        log: Logger para registrar chamadas de ferramentas
        task: Nome da task (para logging)
        attempt: Número da tentativa (para logging)
    """
    # Adiciona system prompt do agente
    agent_config = CUSTOM_AGENTS.get(
        agent_type, CUSTOM_AGENTS["python-generator"])
    full_messages = [
        {"role": "system", "content": agent_config["system_prompt"]}
    ] + messages

    # Prepara parâmetros da chamada
    call_params = {
        "model": MODEL,
        "messages": full_messages,
        "temperature": TEMPERATURE,
        "timeout": TIMEOUT,
        "api_base": OPENAI_API_URL,
        "api_key": os.environ.get("OPENAI_API_KEY", "dummy-key"),
    }    # Adiciona tools se solicitado
    if use_tools:
        call_params["tools"] = CUSTOM_TOOLS
        call_params["tool_choice"] = "auto"

    # Loga o prompt completo antes de enviar à LLM
    if log:
        log.prompt_sent(
            task=task,
            attempt=attempt,
            agent=agent_type,
            messages=full_messages,
        )

    try:
        response = completion(**call_params)

        # Extrai tokens
        usage = response.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        # Extrai resposta
        choice = response.choices[0]
        message = choice.message

        # Verifica se há tool calls
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls and log:
            # Processa tool calls
            for tool_call in tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                log.hook_tool_call(task=task, tool=func_name, args=func_args)

                # Executa a ferramenta
                if func_name in TOOL_FUNCTIONS:
                    result = TOOL_FUNCTIONS[func_name](**func_args)
                    passed = result.get("success")
                    logs = result.get("logs", "")
                    log.hook_tool_result(
                        task=task, tool=func_name, passed=passed, logs=logs)

        content = message.content or ""
        return content, tokens_in, tokens_out, tool_calls

    except Exception as e:
        error_msg = str(e)
        if log:
            log.sdk_error(task=task, attempt=attempt,
                          context="llm_call", detail=error_msg)
        raise RuntimeError(f"LiteLLM call failed: {error_msg}")


# ──────────────────────────────────────────────
# 5. Nós do grafo LangGraph
# ──────────────────────────────────────────────

def generator_node(state: AgentState) -> dict:
    """Generates Python code from the requirement using LiteLLM."""
    attempt = state["attempts"] + 1
    log: ExperimentLogger = state["logger"]
    task: str = state["task"]

    # Record wall-clock start on the very first attempt
    start_time = state.get("task_start_time") or time.monotonic()

    # Trunca requirement se necessário para evitar estouro de contexto
    requirement = _truncate_text(state["requirement"], MAX_CODE_LENGTH)

    # Monta mensagens
    messages = [
        {
            "role": "user",
            "content": f"""Task: {requirement}

Write the Python code to solve this task. Output only executable Python code, no markdown fences, no explanations."""
        }
    ]

    # Chama LLM
    raw, tok_in, tok_out, _ = _call_llm(
        messages=messages,
        agent_type="python-generator",
        use_tools=False,
        log=log,
        task=task,
        attempt=attempt
    )

    # Limpa código (remove markdown se o modelo insistir)
    code = raw.replace("```python", "").replace("```", "").strip()

    log.generation(
        task=task,
        attempt=attempt,
        code=code,
        tokens_input=tok_in,
        tokens_output=tok_out,
    )

    return {
        "code": code,
        "attempts": attempt,
        "task_start_time": start_time,
        "tokens_input": state.get("tokens_input", 0) + tok_in,
        "tokens_output": state.get("tokens_output", 0) + tok_out,
    }


def tester_node(state: AgentState) -> dict:
    """Runs the code in the Docker sandbox and captures the result."""
    log: ExperimentLogger = state["logger"]
    task: str = state["task"]
    attempt: int = state["attempts"]

    success, logs = run_code_in_sandbox(state["code"], state["oracle"])
    logs_clean = logs.strip() if logs else ""

    log.test_result(
        task=task,
        attempt=attempt,
        passed=success,
        output=logs_clean
    )

    return {
        "is_passing": success,
        "errors": logs_clean
    }


def refactor_node(state: AgentState) -> dict:
    """Fixes the code based on the sandbox error."""
    attempt = state["attempts"] + 1
    log: ExperimentLogger = state["logger"]
    task: str = state["task"]

    # Trunca código e erro para evitar estouro de contexto
    code = _truncate_text(state["code"], MAX_CODE_LENGTH)
    error = _truncate_text(state["errors"], MAX_ERROR_LENGTH)

    # Monta mensagens para debug
    messages = [
        {
            "role": "user",
            "content": f"""The following Python code failed with this error:

ERROR:
{error}

FAILING CODE:
{code}

Fix the bug and return only the corrected Python code. No markdown fences, no explanations."""
        }
    ]

    # Chama LLM com agente debugger
    raw, tok_in, tok_out, _ = _call_llm(
        messages=messages,
        agent_type="python-debugger",
        use_tools=False,
        log=log,
        task=task,
        attempt=attempt
    )

    # Limpa código
    code = raw.replace("```python", "").replace("```", "").strip()

    log.refactor(
        task=task,
        attempt=attempt,
        error=state["errors"],
        code=code,
        tokens_input=tok_in,
        tokens_output=tok_out,
    )

    return {
        "code": code,
        "attempts": attempt,
        "tokens_input": state.get("tokens_input", 0) + tok_in,
        "tokens_output": state.get("tokens_output", 0) + tok_out,
    }


# ──────────────────────────────────────────────
# 6. Construção e compilação do grafo
# ──────────────────────────────────────────────

def _routing(state: AgentState) -> str:
    """Decide se continua tentando ou encerra."""
    if state["is_passing"] or state["attempts"] >= MAX_ATTEMPTS:
        return "end"
    return "refactor"


# Constrói o workflow
workflow = StateGraph(AgentState)
workflow.add_node("gen", generator_node)
workflow.add_node("test", tester_node)
workflow.add_node("refactor", refactor_node)

workflow.set_entry_point("gen")
workflow.add_edge("gen", "test")
workflow.add_conditional_edges(
    "test",
    _routing,
    {"end": END, "refactor": "refactor"}
)
workflow.add_edge("refactor", "test")

agent_executor = workflow.compile()
