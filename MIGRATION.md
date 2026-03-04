# Guia de Migração: Copilot SDK → LiteLLM

## Mudanças Principais

### 1. Backend de Inferência
- **Antes:** GitHub Copilot SDK (python)
- **Depois:** LiteLLM (interface unificada para LLMs)

### 2. Vantagens da Migração
- ✅ Menor consumo de tokens (truncamento inteligente)
- ✅ Compatibilidade com APIs locais (LM Studio, Ollama, vLLM)
- ✅ Compatibilidade com OpenAI, Anthropic, etc.
- ✅ Sem problemas de janela de contexto
- ✅ Código mais simples e manutenível

### 3. Estrutura Mantida
- ✅ Custom Agents (python-generator, python-debugger)
- ✅ Custom Tools (run_tests_tool)
- ✅ Sistema de logging estruturado
- ✅ Fluxo LangGraph (gen → test → refactor)

## Configuração

### Dependências
```bash
pip install litellm>=1.0 openai>=1.0 langgraph pydantic>=2.0 docker python-dotenv
```

### Variáveis de Ambiente (.env)
```bash
# Chave API (use "dummy-key" para APIs locais)
OPENAI_API_KEY=sk-your-key-here

# Modelo (formato: provider/model)
MODEL=qwen/qwen3-coder-30b

# URL da API (para servidores locais)
OPENAI_API_URL=http://127.0.0.1:1234/v1
```

### Configuração em exp_config.py
```python
MAX_ATTEMPTS = 10
OPENAI_API_URL = "http://127.0.0.1:1234/v1"
MODEL = "qwen/qwen3-coder-30b"

# Controle de contexto (evita estouro)
MAX_CODE_LENGTH = 4000      # Tamanho máximo de código no prompt
MAX_ERROR_LENGTH = 2000     # Tamanho máximo de mensagem de erro
TEMPERATURE = 0.7
TIMEOUT = 120.0
```

## Exemplos de Uso

### APIs Locais (LM Studio, Ollama)
```python
# exp_config.py
MODEL = "qwen/qwen3-coder-30b"
OPENAI_API_URL = "http://127.0.0.1:1234/v1"

# .env
OPENAI_API_KEY=dummy-key
```

### OpenAI Oficial
```python
# exp_config.py
MODEL = "gpt-4"
OPENAI_API_URL = "https://api.openai.com/v1"

# .env
OPENAI_API_KEY=sk-proj-seu-token-real
```

### Anthropic Claude
```python
# exp_config.py
MODEL = "claude-3-opus-20240229"
OPENAI_API_URL = ""  # LiteLLM detecta automaticamente

# .env
ANTHROPIC_API_KEY=sk-ant-seu-token
```

## Mudanças no Código

### Antes (Copilot SDK)
```python
from copilot import CopilotClient, define_tool

@define_tool(description="...")
async def run_tests_tool(params: RunTestsParams) -> dict:
    pass

async def _ask_copilot(prompt: str, hooks: dict) -> str:
    client = CopilotClient()
    await client.start()
    session = await client.create_session({...})
    # ... código assíncrono complexo
```

### Depois (LiteLLM)
```python
from litellm import completion

def run_tests_tool(code: str, oracle: str) -> dict:
    pass

def _call_llm(messages: list[dict], agent_type: str) -> tuple:
    response = completion(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        api_base=OPENAI_API_URL,
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    # ... código síncrono simples
```

## Agentes Customizados

### Estrutura dos Agentes
```python
CUSTOM_AGENTS = {
    "python-generator": {
        "name": "Python Code Generator",
        "system_prompt": """You are an expert Python developer..."""
    },
    "python-debugger": {
        "name": "Python Debugger", 
        "system_prompt": """You are a debugging expert..."""
    }
}
```

### Uso nos Nós do Grafo
```python
def generator_node(state: AgentState) -> dict:
    raw, tok_in, tok_out, _ = _call_llm(
        messages=[{"role": "user", "content": prompt}],
        agent_type="python-generator",  # Seleciona o agente
        use_tools=False,
        log=log,
    )
    return {"code": raw, "tokens_input": tok_in, ...}
```

## Controle de Contexto

O código agora trunca automaticamente textos longos:

```python
def _truncate_text(text: str, max_length: int) -> str:
    """Trunca texto mantendo o final (mais importante para erros)."""
    if len(text) <= max_length:
        return text
    return "...[truncated]...\n" + text[-max_length:]

# Uso
requirement = _truncate_text(state["requirement"], MAX_CODE_LENGTH)
error = _truncate_text(state["errors"], MAX_ERROR_LENGTH)
```

## Métricas de Tokens

Todas as chamadas agora retornam métricas precisas:

```python
raw, tok_in, tok_out, _ = _call_llm(...)

# Acumulado no estado
return {
    "tokens_input": state.get("tokens_input", 0) + tok_in,
    "tokens_output": state.get("tokens_output", 0) + tok_out,
}
```

## Execução

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar .env
cp .env.example .env
# Editar .env com suas credenciais

# 3. Iniciar servidor local (LM Studio, Ollama, etc)
# ou usar API externa (OpenAI, Anthropic)

# 4. Rodar benchmark
python main.py

# 5. Ver logs
cat logs/<run_id>.log
```

## Solução de Problemas

### Erro: "LiteLLM call failed"
- Verifique se o servidor local está rodando
- Verifique OPENAI_API_URL e OPENAI_API_KEY
- Teste com `curl http://127.0.0.1:1234/v1/models`

### Estouro de Contexto
- Ajuste MAX_CODE_LENGTH e MAX_ERROR_LENGTH em exp_config.py
- Use modelos com janela de contexto maior
- Reduza o tamanho das tasks no dataset

### Timeout
- Aumente TIMEOUT em exp_config.py
- Verifique latência do servidor
- Use modelos mais rápidos

## Recursos Adicionais

- [Documentação LiteLLM](https://docs.litellm.ai/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [LM Studio](https://lmstudio.ai/) - Servidor local para modelos
- [Ollama](https://ollama.ai/) - Alternativa ao LM Studio
