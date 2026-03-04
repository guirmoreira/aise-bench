# 🎨 Guia: Como Adicionar Novos Agentes Customizados

Este guia mostra como estender o AISE-Bench com novos agentes especializados.

## 📋 Estrutura de um Agente

Cada agente é definido por:
- **Nome**: Identificador único
- **System Prompt**: Instruções que definem o comportamento
- **Casos de uso**: Quando o agente deve ser usado

## 🛠️ Exemplo: Adicionar Agente de Otimização

### 1. Definir o Agente em `core/agent.py`

```python
CUSTOM_AGENTS = {
    "python-generator": {
        "name": "Python Code Generator",
        "system_prompt": """..."""
    },
    "python-debugger": {
        "name": "Python Debugger",
        "system_prompt": """..."""
    },
    # NOVO AGENTE
    "python-optimizer": {
        "name": "Python Performance Optimizer",
        "system_prompt": """You are an expert in Python performance optimization.

Your responsibilities:
- Analyze code for performance bottlenecks
- Optimize algorithms and data structures
- Reduce time and space complexity
- Apply caching and memoization when appropriate
- Use efficient built-in functions and libraries
- Maintain code correctness while improving speed
- Output ONLY the optimized Python code
- Do NOT include markdown fences or explanations

Focus on:
1. Algorithm efficiency (O(n) vs O(n²))
2. Data structure selection (list vs set vs dict)
3. Loop optimization
4. Memory efficiency
5. Pythonic idioms

Output format: Raw optimized Python code only."""
    },
}
```

### 2. Criar Nó do Grafo para o Novo Agente

```python
def optimizer_node(state: AgentState) -> dict:
    """Optimizes working code for better performance."""
    attempt = state["attempts"]
    log: ExperimentLogger = state["logger"]
    task: str = state["task"]
    
    # Trunca código se necessário
    code = _truncate_text(state["code"], MAX_CODE_LENGTH)
    
    # Monta prompt de otimização
    messages = [
        {
            "role": "user",
            "content": f"""The following code works but may be slow or inefficient:

{code}

Optimize it for better performance. Focus on:
- Algorithm efficiency
- Data structure optimization  
- Pythonic improvements

Return only the optimized code, no markdown, no explanations."""
        }
    ]
    
    # Chama LLM com agente optimizer
    raw, tok_in, tok_out, _ = _call_llm(
        messages=messages,
        agent_type="python-optimizer",  # Seleciona o novo agente
        use_tools=False,
        log=log,
        task=task,
        attempt=attempt
    )
    
    # Limpa código
    optimized_code = raw.replace("```python", "").replace("```", "").strip()
    
    # Log da otimização (você pode criar um novo método no logger)
    log.generation(
        task=task, 
        attempt=attempt, 
        code=f"[OPTIMIZED]\n{optimized_code}",
        tokens_input=tok_in, 
        tokens_output=tok_out,
    )
    
    return {
        "code": optimized_code,
        "tokens_input": state.get("tokens_input", 0) + tok_in,
        "tokens_output": state.get("tokens_output", 0) + tok_out,
    }
```

### 3. Integrar no Fluxo LangGraph (Opcional)

Se quiser incluir otimização no fluxo principal:

```python
# Adicionar nó
workflow.add_node("optimize", optimizer_node)

# Modificar roteamento
def _routing(state: AgentState) -> str:
    if state["is_passing"]:
        # Código passou, pode otimizar
        if state.get("optimized", False):
            return "end"
        return "optimize"
    elif state["attempts"] >= MAX_ATTEMPTS:
        return "end"
    return "refactor"

# Adicionar edge
workflow.add_edge("optimize", "test")

# Atualizar estado
class AgentState(TypedDict):
    # ...existing fields...
    optimized: bool  # Flag para controlar otimização
```

## 🎯 Exemplos de Agentes Especializados

### Agente de Documentação
```python
"python-documenter": {
    "name": "Python Documentation Expert",
    "system_prompt": """You are an expert in Python documentation.

Add comprehensive docstrings to the given code:
- Module-level docstring
- Class docstrings with attributes
- Function/method docstrings (Google style)
- Type hints where missing
- Inline comments for complex logic

Output ONLY the documented code, no markdown fences."""
}
```

### Agente de Testes
```python
"python-test-writer": {
    "name": "Python Test Writer",
    "system_prompt": """You are an expert in Python testing with pytest.

Write comprehensive unit tests for the given code:
- Test normal cases
- Test edge cases
- Test error handling
- Use pytest fixtures
- Use parametrize for multiple cases
- Aim for 100% coverage

Output ONLY the test code, no markdown fences."""
}
```

### Agente de Segurança
```python
"python-security-auditor": {
    "name": "Python Security Auditor",
    "system_prompt": """You are a Python security expert.

Analyze code for security vulnerabilities:
- SQL injection risks
- Command injection
- Path traversal
- Unsafe deserialization
- Input validation issues
- Credential exposure

Return the code with security fixes applied.
Output ONLY the secured code, no markdown fences."""
}
```

### Agente de Refatoração
```python
"python-refactorer": {
    "name": "Python Code Refactorer",
    "system_prompt": """You are an expert in code refactoring.

Refactor the code following principles:
- DRY (Don't Repeat Yourself)
- SOLID principles
- Extract methods
- Rename for clarity
- Remove code smells
- Simplify complex logic

Maintain exact same functionality.
Output ONLY the refactored code, no markdown fences."""
}
```

## 🔄 Uso Dinâmico de Agentes

### Seleção Baseada em Contexto

```python
def select_agent_for_task(task_type: str) -> str:
    """Seleciona o agente apropriado baseado no tipo de task."""
    agent_map = {
        "generation": "python-generator",
        "debugging": "python-debugger",
        "optimization": "python-optimizer",
        "documentation": "python-documenter",
        "testing": "python-test-writer",
        "security": "python-security-auditor",
    }
    return agent_map.get(task_type, "python-generator")

# Usar no nó
def adaptive_generator_node(state: AgentState) -> dict:
    task_type = state.get("task_type", "generation")
    agent = select_agent_for_task(task_type)
    
    raw, tok_in, tok_out, _ = _call_llm(
        messages=messages,
        agent_type=agent,  # Agente dinâmico
        use_tools=False,
        log=log,
    )
    # ...
```

### Pipeline de Múltiplos Agentes

```python
def multi_agent_pipeline(code: str, state: AgentState) -> str:
    """Passa código por vários agentes sequencialmente."""
    
    # 1. Gerar código
    code = call_agent("python-generator", initial_prompt)
    
    # 2. Testar e debugar se necessário
    if not test_passes(code):
        code = call_agent("python-debugger", code + error)
    
    # 3. Otimizar
    code = call_agent("python-optimizer", code)
    
    # 4. Documentar
    code = call_agent("python-documenter", code)
    
    # 5. Auditar segurança
    code = call_agent("python-security-auditor", code)
    
    return code
```

## 📊 Métricas por Agente

Adicione tracking específico por agente:

```python
class AgentState(TypedDict):
    # ...existing...
    agent_usage: dict[str, int]  # {agent_name: call_count}
    agent_tokens: dict[str, dict]  # {agent_name: {in: X, out: Y}}

# No _call_llm
def _call_llm(..., agent_type: str, ...) -> ...:
    # ...existing code...
    
    # Tracking
    usage = state.get("agent_usage", {})
    usage[agent_type] = usage.get(agent_type, 0) + 1
    
    tokens = state.get("agent_tokens", {})
    if agent_type not in tokens:
        tokens[agent_type] = {"input": 0, "output": 0}
    tokens[agent_type]["input"] += tok_in
    tokens[agent_type]["output"] += tok_out
    
    return content, tok_in, tok_out, tool_calls
```

## ✅ Checklist para Novo Agente

- [ ] Definir nome único e descritivo
- [ ] Escrever system prompt claro e específico
- [ ] Especificar formato de output esperado
- [ ] Criar nó do grafo (se necessário)
- [ ] Integrar no fluxo LangGraph
- [ ] Adicionar logging apropriado
- [ ] Testar com casos reais
- [ ] Documentar uso e limitações
- [ ] Adicionar métricas de tracking

## 🧪 Testar Novo Agente

```python
# test_new_agent.py
from core.agent import _call_llm
from core.logging import ExperimentLogger

log = ExperimentLogger()

# Teste simples
messages = [{"role": "user", "content": "def fib(n): return fib(n-1) + fib(n-2)"}]
result, tok_in, tok_out, _ = _call_llm(
    messages=messages,
    agent_type="python-optimizer",
    use_tools=False,
    log=log,
    task="test",
    attempt=1
)

print("Optimized code:")
print(result)
print(f"Tokens: {tok_in} in, {tok_out} out")
```

## 💡 Dicas Avançadas

### 1. Prompts com Few-Shot Learning
```python
"system_prompt": """You are an expert Python optimizer.

Example 1:
Input: for i in range(len(arr)): print(arr[i])
Output: for item in arr: print(item)

Example 2:
Input: result = []; for x in data: if x > 0: result.append(x)
Output: result = [x for x in data if x > 0]

Now optimize the given code..."""
```

### 2. Chain-of-Thought para Agentes Complexos
```python
"system_prompt": """Think step by step:
1. Identify the main bottleneck
2. Consider alternative algorithms
3. Evaluate trade-offs
4. Implement the best solution
5. Verify correctness

Output only the final optimized code."""
```

### 3. Agentes Especializados por Domínio
```python
"data-science-agent": {...}
"web-scraping-agent": {...}
"api-integration-agent": {...}
```

---

**Pronto!** Agora você pode criar agentes especializados para qualquer necessidade do seu benchmark. 🚀
