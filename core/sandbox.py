import docker
import os

client = docker.from_env()

def run_code_in_sandbox(code, test_code, timeout=10):
    """Executa código e teste em ambiente isolado."""
    full_script = f"{code}\n\n{test_code}"
    try:
        container = client.containers.run(
            image="python:3.11-slim",
            command=f"python -c \"{full_script}\"",
            remove=True,
            stdout=True, stderr=True,
            network_disabled=True,
            mem_limit="128m", # Limite de memória por segurança
            timeout=timeout
        )
        return True, container.decode('utf-8')
    except Exception as e:
        error_msg = str(e.stderr.decode('utf-8')) if hasattr(e, 'stderr') else str(e)
        return False, error_msg