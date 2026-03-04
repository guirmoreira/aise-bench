# AISE-Bench: Framework de Pesquisa para Engenharia de Software Agêntica

Este repositório contém uma **bancada de experimentos** desenvolvida para a pesquisa de Mestrado em Ciências da Computação. O objetivo é avaliar o desempenho de Agentes de IA (LLMs) em tarefas de Engenharia de Software através de um ciclo iterativo de auto-correção (*Self-Healing*).

## 🚀 Visão Geral da Arquitetura

Diferente de abordagens *Zero-Shot*, este framework implementa um **Grafo de Estados Agêntico** utilizando `LangGraph` com **LiteLLM** como backend de inferência unificado. O fluxo simula o comportamento humano:

1. **Geração:** O LLM propõe uma solução inicial usando o agente `python-generator`.
2. **Validação (Oráculo):** O código é executado em um **Sandbox Docker** isolado.
3. **Refatoração:** Se o teste falhar, o agente `python-debugger` recebe o erro (Traceback) e tenta corrigir o código.

### Por que LiteLLM?

- ✅ **Interface unificada** para múltiplos provedores (OpenAI, Anthropic, modelos locais)
- ✅ **Gerenciamento eficiente de contexto** - evita estouro de tokens
- ✅ **Compatibilidade** com APIs OpenAI locais (LM Studio, Ollama, vLLM)
- ✅ **Métricas de tokens** precisas para análise de custo

### Agentes Customizados

- **python-generator**: Especializado em gerar código Python limpo e correto
- **python-debugger**: Especializado em análise de erros e correção de bugs

### Métricas de Pesquisa

O framework está preparado para extrair:

* **Success Rate (SR):** Taxa de sucesso na primeira tentativa.
* **Agentic Recovery Rate ($R_r$):** Capacidade do agente se recuperar após erros.
* **Token/Cost Efficiency:** Custo computacional por tarefa resolvida.

---

## 🛠️ Requisitos Prévios

Antes de rodar os experimentos, certifique-se de ter instalado:

* **Python 3.10+**
* **Docker Desktop:** Necessário para rodar o sandbox isolado.
* **Conta no LangSmith:** Para visualização dos traces e logs científicos.

---

## ⚙️ Configuração do Ambiente

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/aise-bench.git
cd aise-bench

```


2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

```


3. Instale as dependências:
```bash
uv pip install -r requirements.txt

```


4. Crie um arquivo **`.env`** na raiz do projeto com as seguintes chaves:

```env
# --- PROVEDORES DE LLM ---
# Você pode usar um ou mais, o LiteLLM fará a ponte.
OPENAI_API_KEY=sk-proj-xxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxx

# --- OBSERVABILIDADE (LANGSMITH) ---
# Essencial para salvar os traces da sua pesquisa
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_API_KEY=lsv2_pt_xxxxxx
LANGSMITH_PROJECT="Mestrado-Eng-Software"

# --- OPCIONAL: LLMs LOCAIS (OLLAMA) ---
# Se for usar modelos locais, aponte a base_url
# LITELLM_LOCAL_MODEL_URL=http://localhost:11434

```

---

## 🧪 Executando os Experimentos

### 1. Preparação do Dataset

Edite o arquivo `data/dataset.json` incluindo as histórias de usuário e os oráculos (testes unitários) que deseja testar.

### 2. Rodar a Bancada

Para iniciar a bateria de testes em todos os modelos configurados:

```bash
python main.py

```

Os resultados serão exibidos no console e exportados para `resultados_experimento.csv` para análise estatística futura (R ou Python/Pandas).

---

## 🔬 Rigor Científico & Sandbox

Para garantir a **reprodutibilidade**, todos os códigos gerados pelos agentes são executados dentro do container Docker `python:3.11-slim`.

* **Isolamento:** Rede desativada durante a execução (`network_disabled=True`).
* **Limitação de Recursos:** Memória limitada a 128MB para evitar ataques de negação de serviço ou loops infinitos gerados pela IA.

---

## 📈 Visualização de Resultados

Acesse o painel do **LangSmith** para visualizar o "pensamento" do agente em cada etapa. Isso é fundamental para a escrita da sua dissertação, permitindo analisar por que um agente falhou em uma correção específica.

---

### Próximo Passo

Gostaria que eu gerasse um **exemplo de script de análise em Pandas** para processar o `resultados_experimento.csv` e gerar os gráficos de taxa de sucesso automaticamente para o seu relatório?