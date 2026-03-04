#!/usr/bin/env python3
"""
test_setup.py — Script de validação da configuração do AISE-Bench

Verifica se todas as dependências e configurações estão corretas antes
de rodar experimentos completos.
"""

import os
import sys
from pathlib import Path


def check_env_vars():
    """Verifica variáveis de ambiente essenciais."""
    print("🔍 Verificando variáveis de ambiente...")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  ⚠️  OPENAI_API_KEY não encontrada (ok se usar API local com dummy-key)")
    else:
        print(f"  ✅ OPENAI_API_KEY encontrada: {api_key[:10]}...")

    return True


def check_dependencies():
    """Verifica se todas as dependências estão instaladas."""
    print("\n🔍 Verificando dependências...")

    required = {
        "litellm": "LiteLLM",
        "langgraph": "LangGraph",
        "docker": "Docker Python SDK",
        "pydantic": "Pydantic",
        "dotenv": "python-dotenv",
    }

    missing = []
    for module, name in required.items():
        try:
            __import__(module)
            print(f"  ✅ {name}")
        except ImportError:
            print(f"  ❌ {name} - NÃO INSTALADO")
            missing.append(module)

    if missing:
        print(f"\n❌ Instale as dependências faltantes:")
        print(f"   pip install {' '.join(missing)}")
        return False

    return True


def check_docker():
    """Verifica se o Docker está rodando."""
    print("\n🔍 Verificando Docker...")

    try:
        import docker
        client = docker.from_env()
        client.ping()
        print("  ✅ Docker está rodando")
        return True
    except Exception as e:
        print(f"  ❌ Docker não está acessível: {e}")
        print("     Inicie o Docker Desktop e tente novamente")
        return False


def check_config():
    """Verifica se os arquivos de configuração existem."""
    print("\n🔍 Verificando configuração...")

    if not Path("exp_config.py").exists():
        print("  ❌ exp_config.py não encontrado")
        return False
    print("  ✅ exp_config.py encontrado")

    if not Path("data/dataset.json").exists():
        print("  ⚠️  data/dataset.json não encontrado")
    else:
        print("  ✅ data/dataset.json encontrado")

    return True


def test_litellm_connection():
    """Testa conexão básica com LiteLLM."""
    print("\n🔍 Testando conexão LiteLLM...")

    try:
        from litellm import completion

        from exp_config import MODEL, OPENAI_API_URL

        print(f"  📝 Modelo configurado: {MODEL}")
        print(f"  🌐 API URL: {OPENAI_API_URL}")

        # Teste simples
        print("  🧪 Enviando teste básico (2+2=?)...")
        response = completion(
            model=MODEL,
            messages=[
                {"role": "user", "content": "What is 2+2? Answer with just the number."}],
            max_tokens=10,
            api_base=OPENAI_API_URL,
            api_key=os.environ.get("OPENAI_API_KEY", "dummy-key"),
        )

        answer = response.choices[0].message.content.strip()
        print(f"  💬 Resposta do modelo: {answer}")

        if "4" in answer:
            print("  ✅ LiteLLM está funcionando corretamente!")
            return True
        else:
            print("  ⚠️  Resposta inesperada, mas conexão OK")
            return True

    except Exception as e:
        print(f"  ❌ Erro ao testar LiteLLM: {e}")
        print("\n  Possíveis soluções:")
        print("  - Verifique se o servidor local está rodando")
        print("  - Verifique OPENAI_API_URL em exp_config.py")
        print("  - Verifique OPENAI_API_KEY no arquivo .env")
        print(f"  - Teste manualmente: curl {OPENAI_API_URL}/models")
        return False


def main():
    """Executa todos os testes."""
    print("=" * 60)
    print("AISE-Bench - Validação de Configuração")
    print("=" * 60)

    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except:
        pass

    checks = [
        check_dependencies(),
        check_docker(),
        check_config(),
        check_env_vars(),
        test_litellm_connection(),
    ]

    print("\n" + "=" * 60)
    if all(checks):
        print("✅ TUDO OK! Você pode rodar: python main.py")
    else:
        print("❌ Alguns problemas foram encontrados. Corrija-os antes de prosseguir.")
    print("=" * 60)

    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
    sys.exit(main())
