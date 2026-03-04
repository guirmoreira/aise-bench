import os
import tempfile

import docker
import docker.errors

client = docker.from_env()


def run_code_in_sandbox(code: str, test_code: str, timeout: int = 10) -> tuple[bool, str]:
    """Executa código e teste em ambiente isolado via Docker.

    Escreve o script em um arquivo temporário no host e o monta como
    volume somente-leitura no container — funciona em Windows (NpipeSocket),
    Linux e macOS sem nenhum hack de socket.
    """
    full_script = f"{code}\n\n{test_code}"

    # Cria arquivo temporário no host; delete=False porque o Docker precisa
    # que o arquivo ainda exista quando o container for iniciado.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(full_script)
        host_path = tmp.name

    # No Windows o caminho precisa usar barras normais para o bind mount
    host_path_docker = host_path.replace("\\", "/")

    container = None
    try:
        container = client.containers.run(
            image="python:3.11-slim",
            command=["python", "/sandbox/script.py"],
            volumes={host_path_docker: {
                "bind": "/sandbox/script.py", "mode": "ro"}},
            remove=False,
            stdout=True,
            stderr=True,
            network_disabled=True,
            mem_limit="128m",
            detach=True,
        )

        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", 1)
        except Exception:
            container.kill()
            return False, f"Timeout: o código não terminou em {timeout}s"

        logs = container.logs(stdout=True, stderr=True).decode("utf-8")
        return exit_code == 0, logs

    except docker.errors.DockerException as e:
        return False, f"Erro Docker: {e}"
    except Exception as e:
        return False, str(e)
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass
        try:
            os.unlink(host_path)
        except Exception:
            pass
            pass
