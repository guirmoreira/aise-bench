MAX_ATTEMPTS = 10
OPENAI_API_URL = "http://127.0.0.1:1234/v1"
MODEL = "openai/qwen3-coder-30b"    # "openai/..." é para o LiteLLM usar o driver OpenAI

# Configurações de contexto para evitar estouro de tokens
MAX_CODE_LENGTH = 4000      # Tamanho máximo de código no prompt
MAX_ERROR_LENGTH = 2000     # Tamanho máximo de mensagem de erro
TEMPERATURE = 0.7           # Temperatura para geração
TIMEOUT = 120.0             # Timeout em segundos para chamadas LLM
