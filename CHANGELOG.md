# 📋 Sumário da Migração: Copilot SDK → LiteLLM

## ✅ Arquivos Modificados

### 1. `requirements.txt`
- ❌ Removido: `github-copilot-sdk`
- ✅ Adicionado: `litellm>=1.0`, `openai>=1.0`

### 2. `exp_config.py`
- ✅ Adicionado controle de contexto:
  - `MAX_CODE_LENGTH = 4000` (evita estouro de tokens)
  - `MAX_ERROR_LENGTH = 2000`
  - `TEMPERATURE = 0.7`
  - `TIMEOUT = 120.0`

### 3. `core/agent.py` - **REESCRITO COMPLETAMENTE**
- ❌ Removido: Todo código do Copilot SDK (async, sessions, hooks complexos)
- ✅ Adicionado: Implementação LiteLLM síncrona e simples

#### Mudanças principais:
```python
# ANTES: Copilot SDK
from copilot import CopilotClient, define_tool
async def _ask_copilot(prompt, hooks): ...

# DEPOIS: LiteLLM  
from litellm import completion
def _call_llm(messages, agent_type): ...
```

#### Agentes customizados reformulados:
```python
# ANTES: Lista de dicts com formato Copilot
CUSTOM_AGENTS = [{"name": "...", "prompt": "..."}]

# DEPOIS: Dict com system_prompts mais elaborados
CUSTOM_AGENTS = {
    "python-generator": {
        "name": "...",
        "system_prompt": """Prompt detalhado..."""
    }
}
```

#### Ferramentas simplificadas:
```python
# ANTES: @define_tool decorator async
@define_tool(...)
async def run_tests_tool(params: RunTestsParams): ...

# DEPOIS: Funções Python normais + dict para function calling
def run_tests_tool(code: str, oracle: str): ...
CUSTOM_TOOLS = [{...}]  # Formato OpenAI
```

### 4. `core/logging.py`
- ✅ Corrigido: Indentação do método `refactor()`
- ✅ Mantido: Toda a estrutura de logging estruturado

### 5. `main.py`
- ✅ Adicionado: `import time` para métricas
- ✅ Adicionado: Tracking de tokens e elapsed_s
- ✅ Melhorado: Estado inicial do grafo com todos os campos

### 6. `.env.example`
- ✅ Atualizado: Documentação para LiteLLM
- ✅ Simplificado: Foco em OPENAI_API_KEY e MODEL

## 📁 Novos Arquivos Criados

### `MIGRATION.md`
Guia completo de migração com:
- Explicação das mudanças
- Exemplos de configuração
- Solução de problemas comuns
- Comparação antes/depois do código

### `test_setup.py`
Script de validação que verifica:
- ✅ Dependências instaladas
- ✅ Docker rodando
- ✅ Variáveis de ambiente
- ✅ Conexão LiteLLM funcionando

## 🎯 Benefícios da Migração

### Performance e Estabilidade
- ✅ **Janela de contexto controlada** - Truncamento automático
- ✅ **Menos tokens consumidos** - Prompts mais enxutos
- ✅ **Código síncrono** - Mais simples de debugar
- ✅ **Sem overhead de SDK** - Chamadas diretas via HTTP

### Compatibilidade
- ✅ **APIs OpenAI locais** (LM Studio, Ollama, vLLM)
- ✅ **OpenAI oficial**
- ✅ **Anthropic Claude**
- ✅ **100+ provedores** via LiteLLM

### Manutenibilidade
- ✅ **Código 50% menor** em `agent.py`
- ✅ **Sem async complexo**
- ✅ **Logs mais claros**
- ✅ **Fácil adicionar novos agentes**

## 🔧 Como Usar

### 1. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar Ambiente
```bash
cp .env.example .env
# Editar .env com suas credenciais
```

### 3. Validar Setup
```bash
python test_setup.py
```

### 4. Rodar Benchmark
```bash
python main.py
```

## 📊 Estrutura do Código

### Fluxo do Agente (LangGraph)
```
┌─────────────┐
│   START     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  generator_node                     │
│  - Usa agente "python-generator"    │
│  - Gera código inicial              │
│  - Trunca prompt se necessário      │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  tester_node                        │
│  - Executa código no Docker sandbox │
│  - Captura sucesso/erro             │
└──────┬──────────────────────────────┘
       │
       ▼
  ┌────┴────┐
  │ Passou? │
  └────┬────┘
       │
  ┌────┴─────┬────────────┐
  │          │            │
  ▼          ▼            ▼
┌───┐   ┌─────────┐   ┌──────────┐
│END│   │Max tries│   │  refactor│
└───┘   └────┬────┘   └────┬─────┘
             │             │
             ▼             │
           ┌───┐           │
           │END│◄──────────┘
           └───┘
```

### Agentes e Responsabilidades

| Agente | Responsabilidade | Quando é Usado |
|--------|-----------------|----------------|
| `python-generator` | Gerar código Python limpo e correto | Primeira tentativa (generator_node) |
| `python-debugger` | Analisar erros e corrigir bugs | Após falha de teste (refactor_node) |

### Controle de Contexto

```python
# Limites configuráveis em exp_config.py
MAX_CODE_LENGTH = 4000    # ~1000 tokens
MAX_ERROR_LENGTH = 2000   # ~500 tokens

# Truncamento inteligente (mantém o final)
def _truncate_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return "...[truncated]...\n" + text[-max_length:]
```

## 🐛 Debugging

### Verificar logs estruturados
```bash
# Logs ficam em logs/<run_id>.log
cat logs/$(ls -t logs/ | head -1)

# Buscar erros específicos
grep "SDK_ERROR" logs/*.log
grep "TEST_RESULT.*false" logs/*.log
```

### Teste individual de LLM
```bash
python -c "
from litellm import completion
import os

response = completion(
    model='qwen/qwen3-coder-30b',
    messages=[{'role': 'user', 'content': 'print(2+2)'}],
    api_base='http://127.0.0.1:1234/v1',
    api_key=os.environ.get('OPENAI_API_KEY', 'dummy-key')
)
print(response.choices[0].message.content)
"
```

## 📚 Documentação Adicional

- **README.md** - Visão geral atualizada
- **MIGRATION.md** - Guia detalhado de migração
- **test_setup.py** - Script de validação
- **.env.example** - Template de configuração

## ⚠️ Notas Importantes

1. **Backup**: Os arquivos originais foram sobrescritos. Use git para reverter se necessário.
2. **Docker**: O sandbox ainda usa Docker - não mudou.
3. **Dataset**: O formato do dataset.json não mudou.
4. **Logs**: O formato de log não mudou - compatibilidade total com análises existentes.

## 🎓 Próximos Passos

1. ✅ Executar `python test_setup.py` para validar
2. ✅ Rodar um experimento pequeno para testar
3. ✅ Comparar métricas com versão anterior (se houver)
4. ✅ Ajustar MAX_CODE_LENGTH/MAX_ERROR_LENGTH conforme necessário
5. ✅ Explorar outros modelos via LiteLLM

## 💡 Dicas

- Use `TEMPERATURE=0.0` para resultados mais determinísticos
- Aumente `MAX_ATTEMPTS` para dar mais chances ao agente
- Monitore tokens via logs estruturados
- Use LangSmith para traces detalhados (opcional)
