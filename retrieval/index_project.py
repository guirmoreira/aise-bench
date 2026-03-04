"""
index_project.py — Indexa os arquivos reais do projeto em um JSON para retrieval.

Percorre recursivamente o diretório raiz do projeto (ou outro especificado),
coleta o conteúdo de cada arquivo texto e grava um JSON no mesmo formato
usado pelo mock_data.py:

    [{"path": "caminho/relativo/arquivo.py", "content": "..."}, ...]

Uso:
    python retrieval/index_project.py --output context.json
    python retrieval/index_project.py --root . --output retrieval/index.json --ext .py .md
    python retrieval/index_project.py --output context.json --exclude-dirs .venv __pycache__ logs

Argumentos:
    --output        Arquivo JSON de saída  (obrigatório)
    --root          Raiz do projeto a indexar  (padrão: diretório pai deste script)
    --ext           Extensões a incluir, ex: .py .md .txt  (padrão: veja DEFAULT_EXTENSIONS)
    --exclude-dirs  Nomes de diretórios a ignorar  (padrão: veja DEFAULT_EXCLUDE_DIRS)
    --exclude-files Padrões de nome de arquivo a ignorar  (padrão: veja DEFAULT_EXCLUDE_FILES)
    --max-file-kb   Tamanho máximo de arquivo em KB; maiores são pulados  (padrão: 500)
    --no-gitignore  Não lê o .gitignore para excluir arquivos
"""

import argparse
import fnmatch
import json
import os
import sys
import time

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_EXTENSIONS: tuple[str, ...] = (
    ".py", ".md", ".txt", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".env.example", ".sh",
    ".html", ".css", ".js", ".ts",
)

DEFAULT_EXCLUDE_DIRS: tuple[str, ...] = (
    ".env", "__pycache__", ".git",
    # ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "node_modules", "dist", "build", ".idea", ".vscode",
    "logs",               # logs de experimento — geralmente ruído
    "retrieval/data",     # dados mock gerados pelo mock_data.py
)

DEFAULT_EXCLUDE_FILES: tuple[str, ...] = (
    "*.pyc", "*.pyo", "*.pyd",
    "*.log",
    "*.csv",               # resultados de experimentos costumam ser grandes
    "*.lock",
    ".DS_Store",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_gitignore_patterns(root: str) -> list[str]:
    """Lê .gitignore na raiz e retorna lista de padrões glob."""
    gitignore_path = os.path.join(root, ".gitignore")
    patterns: list[str] = []
    if not os.path.exists(gitignore_path):
        return patterns
    with open(gitignore_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line.rstrip("/"))
    return patterns


def _matches_any(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def _is_text_file(path: str, sample_bytes: int = 8192) -> bool:
    """Heurística simples: verifica se o arquivo não contém bytes nulos."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_bytes)
        return b"\x00" not in chunk
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def index_project(
    root: str,
    output_file: str,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    exclude_dirs: tuple[str, ...] = DEFAULT_EXCLUDE_DIRS,
    exclude_files: tuple[str, ...] = DEFAULT_EXCLUDE_FILES,
    max_file_kb: int = 500,
    use_gitignore: bool = True,
) -> None:
    """
    Percorre `root` recursivamente e grava `output_file` com todos os
    arquivos texto correspondentes às `extensions`, no formato:        [{"path": "relativo/ao/root", "content": "..."}, ...]
    """
    root = os.path.abspath(root)
    gitignore_patterns = _load_gitignore_patterns(
        root) if use_gitignore else []

    # Normaliza exclude_dirs para comparação de basename
    exclude_dirs_set = {d.strip("/").split("/")[-1] for d in exclude_dirs}

    records: list[dict] = []
    skipped_binary = 0
    skipped_size = 0
    skipped_ext = 0
    total_content_chars = 0

    start_time = time.monotonic()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")

        # ── Filtra sub-diretórios in-place (evita descer neles) ──────────
        dirnames[:] = [
            d for d in sorted(dirnames)
            if d not in exclude_dirs_set
            and not _matches_any(d, gitignore_patterns)
            # também exclui se o caminho relativo completo bate algum exclude_dirs
            and not any(
                (rel_dir + "/" + d).startswith(excl.strip("/"))
                for excl in exclude_dirs
            )
        ]

        for fname in sorted(filenames):
            fpath = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(fpath, root).replace("\\", "/")

            # Extensão
            _, ext = os.path.splitext(fname)
            if ext.lower() not in extensions:
                skipped_ext += 1
                continue

            # Nome de arquivo excluído
            if _matches_any(fname, list(exclude_files)):
                skipped_ext += 1
                continue

            # Padrões do .gitignore
            if _matches_any(fname, gitignore_patterns) or _matches_any(rel_path, gitignore_patterns):
                skipped_ext += 1
                continue

            # Tamanho máximo
            try:
                size_kb = os.path.getsize(fpath) / 1024
            except OSError:
                continue
            if size_kb > max_file_kb:
                skipped_size += 1
                print(f"  [skip: size {size_kb:.0f} KB] {rel_path}")
                continue

            # Binário
            if not _is_text_file(fpath):
                skipped_binary += 1
                print(f"  [skip: binary] {rel_path}")
                continue

            # Lê conteúdo
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError as exc:
                print(f"  [skip: read error — {exc}] {rel_path}")
                continue

            records.append({"path": rel_path, "content": content})
            total_content_chars += len(content)

    elapsed = time.monotonic() - start_time
    abs_output = os.path.abspath(output_file)
    os.makedirs(os.path.dirname(abs_output) or ".", exist_ok=True)
    with open(abs_output, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    size_bytes = os.path.getsize(abs_output)
    if size_bytes >= 1024 * 1024:
        size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        # Tokens: aproximação por espaços (melhor heurística sem deps extras)
        size_str = f"{size_bytes / 1024:.1f} KB"
    approx_tokens = total_content_chars // 4

    print(f"\n[index_project] ✓ JSON exportado : {abs_output}")
    print(f"                Tamanho do arquivo: {size_str}")
    print(f"                Tempo de indexação: {elapsed:.2f}s")
    print(f"                Tokens aprox.     : {approx_tokens:,}")
    print(f"                Arquivos incluídos: {len(records)}")
    print(f"                Pulados (ext/excl): {skipped_ext}")
    print(f"                Pulados (tamanho) : {skipped_size}")
    print(f"                Pulados (binários): {skipped_binary}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    # Raiz padrão = diretório pai do script (raiz do projeto)
    default_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    parser = argparse.ArgumentParser(
        description="Indexa arquivos do projeto em um JSON [{path, content}].",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output", required=True, metavar="ARQUIVO",
        help="Arquivo JSON de saída",
    )
    parser.add_argument(
        "--root", default=default_root, metavar="DIR",
        help="Diretório raiz a indexar",
    )
    parser.add_argument(
        "--ext", nargs="+", default=list(DEFAULT_EXTENSIONS), metavar="EXT",
        help="Extensões de arquivo a incluir (ex: .py .md .txt)",
    )
    parser.add_argument(
        "--exclude-dirs", nargs="+", default=list(DEFAULT_EXCLUDE_DIRS),
        dest="exclude_dirs", metavar="DIR",
        help="Nomes de diretórios a ignorar",
    )
    parser.add_argument(
        "--exclude-files", nargs="+", default=list(DEFAULT_EXCLUDE_FILES),
        dest="exclude_files", metavar="PADRÃO",
        help="Padrões glob de nomes de arquivo a ignorar",
    )
    parser.add_argument(
        "--max-file-kb", type=int, default=500, dest="max_file_kb",
        help="Tamanho máximo de arquivo em KB (maiores são pulados)",
    )
    parser.add_argument(
        "--no-gitignore", action="store_true", dest="no_gitignore",
        help="Não usa .gitignore para filtrar arquivos",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    print(f"[index_project] Raiz    : {os.path.abspath(args.root)}")
    print(f"[index_project] Saída   : {os.path.abspath(args.output)}")
    print(f"[index_project] Extensões: {args.ext}")
    print(f"[index_project] Excluindo dirs: {args.exclude_dirs}")
    print()

    index_project(
        root=args.root,
        output_file=args.output,
        extensions=tuple(args.ext),
        exclude_dirs=tuple(args.exclude_dirs),
        exclude_files=tuple(args.exclude_files),
        max_file_kb=args.max_file_kb,
        use_gitignore=not args.no_gitignore,
    )
