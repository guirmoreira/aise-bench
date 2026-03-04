"""
crawler.py — Busca por termos em arquivos do projeto e exporta os resultados.

Percorre recursivamente o diretório raiz do projeto (ou outro especificado),
busca por um ou mais termos nos arquivos texto e grava um JSON com os caminhos
e contagens de ocorrências:

    [{"path": "caminho/relativo/arquivo.py", "amount": 3}, ...]

Uso:
    python retrieval/crawler.py --term "variable" --output search_result.json
    python retrieval/crawler.py --term "def " "class " --output search_result.json
    python retrieval/crawler.py --term "TODO" --root ./core --output results/todo.json
    python retrieval/crawler.py --term "error" --case-sensitive --output search_result.json

Argumentos:
    --term          Um ou mais termos a buscar (obrigatório)
    --output        Arquivo JSON de saída  (padrão: retrieval/search_result.json)
    --root          Raiz do projeto a percorrer  (padrão: diretório pai deste script)
    --ext           Extensões a incluir  (padrão: mesmos do index_project.py)
    --exclude-dirs  Nomes de diretórios a ignorar
    --exclude-files Padrões de nome de arquivo a ignorar
    --max-file-kb   Tamanho máximo de arquivo em KB  (padrão: 500)
    --no-gitignore  Não lê o .gitignore para excluir arquivos
    --case-sensitive  Busca com diferenciação de maiúsculas/minúsculas
    --whole-word    Busca apenas palavras completas
    --no-sort       Não ordena resultados por quantidade de ocorrências
"""

import argparse
import fnmatch
import json
import os
import re
import time

# ---------------------------------------------------------------------------
# Defaults (espelhados do index_project.py para consistência)
# ---------------------------------------------------------------------------

DEFAULT_EXTENSIONS: tuple[str, ...] = (
    ".py", ".md", ".txt", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".env.example", ".sh",
    ".html", ".css", ".js", ".ts",
)

DEFAULT_EXCLUDE_DIRS: tuple[str, ...] = (
    ".env", "__pycache__", ".git",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "node_modules", "dist", "build", ".idea", ".vscode",
    "logs",
    "retrieval/data",
)

DEFAULT_EXCLUDE_FILES: tuple[str, ...] = (
    "*.pyc", "*.pyo", "*.pyd",
    "*.log",
    "*.csv",
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


def _build_pattern(terms: list[str], case_sensitive: bool, whole_word: bool) -> re.Pattern:
    """
    Compila um padrão regex que casa qualquer um dos termos.
    Se whole_word=True, envolve cada termo com \\b (word boundary).
    """
    escaped = [re.escape(t) for t in terms]
    if whole_word:
        escaped = [rf"\b{t}\b" for t in escaped]
    joined = "|".join(escaped)
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(joined, flags)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def crawl(
    terms: list[str],
    root: str,
    output_file: str,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    exclude_dirs: tuple[str, ...] = DEFAULT_EXCLUDE_DIRS,
    exclude_files: tuple[str, ...] = DEFAULT_EXCLUDE_FILES,
    max_file_kb: int = 500,
    use_gitignore: bool = True,
    case_sensitive: bool = False,
    whole_word: bool = False,
    sort_results: bool = True,
) -> None:
    """
    Percorre `root` recursivamente, busca pelos `terms` em cada arquivo
    e grava `output_file` com os arquivos que contêm ao menos uma ocorrência:
        [{"path": "relativo/ao/root", "amount": N}, ...]

    Args:
        terms:          Lista de termos a buscar.
        root:           Diretório raiz.
        output_file:    Caminho do JSON de saída.
        extensions:     Extensões de arquivo a considerar.
        exclude_dirs:   Diretórios a ignorar.
        exclude_files:  Padrões de arquivo a ignorar.
        max_file_kb:    Tamanho máximo de arquivo a processar (KB).
        use_gitignore:  Se True, aplica padrões do .gitignore.
        case_sensitive: Se True, busca com diferenciação de maiúsculas.
        whole_word:     Se True, busca apenas palavras completas.
        sort_results:   Se True, ordena por `amount` decrescente.
    """
    root = os.path.abspath(root)
    pattern = _build_pattern(terms, case_sensitive, whole_word)
    gitignore_patterns = _load_gitignore_patterns(
        root) if use_gitignore else []
    exclude_dirs_set = {d.strip("/").split("/")[-1] for d in exclude_dirs}

    results: list[dict] = []
    stats = {"checked": 0, "matched": 0, "skipped_ext": 0,
             "skipped_size": 0, "skipped_binary": 0}

    start_time = time.monotonic()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")

        # Filtra sub-diretórios in-place
        dirnames[:] = [
            d for d in sorted(dirnames)
            if d not in exclude_dirs_set
            and not _matches_any(d, gitignore_patterns)
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
                stats["skipped_ext"] += 1
                continue

            # Nome de arquivo excluído
            if _matches_any(fname, list(exclude_files)):
                stats["skipped_ext"] += 1
                continue

            # Padrões do .gitignore
            if _matches_any(fname, gitignore_patterns) or _matches_any(rel_path, gitignore_patterns):
                stats["skipped_ext"] += 1
                continue

            # Tamanho máximo
            try:
                size_kb = os.path.getsize(fpath) / 1024
            except OSError:
                continue
            if size_kb > max_file_kb:
                stats["skipped_size"] += 1
                continue

            # Binário
            if not _is_text_file(fpath):
                stats["skipped_binary"] += 1
                continue

            # Lê e busca
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue

            stats["checked"] += 1
            matches = pattern.findall(content)
            amount = len(matches)

            if amount > 0:
                stats["matched"] += 1
                results.append({"path": rel_path, "amount": amount})

    elapsed = time.monotonic() - start_time

    # Ordena por quantidade decrescente
    if sort_results:
        results.sort(key=lambda r: r["amount"], reverse=True)

    # Grava JSON
    abs_output = os.path.abspath(output_file)
    os.makedirs(os.path.dirname(abs_output) or ".", exist_ok=True)
    with open(abs_output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    size_bytes = os.path.getsize(abs_output)
    size_str = (
        f"{size_bytes / (1024 * 1024):.2f} MB"
        if size_bytes >= 1024 * 1024
        else f"{size_bytes / 1024:.1f} KB"
    )
    total_occurrences = sum(r["amount"] for r in results)

    print(f"\n[crawler] ✓ Busca concluída")
    print(f"          Termos buscados  : {terms}")
    print(f"          Case-sensitive   : {case_sensitive}")
    print(f"          Whole-word       : {whole_word}")
    print(f"          Arquivos checados: {stats['checked']}")
    print(f"          Arquivos com match: {stats['matched']}")
    print(f"          Ocorrências totais: {total_occurrences:,}")
    print(f"          Tempo de busca   : {elapsed:.2f}s")
    print(f"          Saída            : {abs_output}")
    print(f"          Tamanho do JSON  : {size_str}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    default_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_output = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "search_result.json"
    )

    parser = argparse.ArgumentParser(
        description="Busca termos em arquivos do projeto e exporta resultados em JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--term", nargs="+", required=True, metavar="TERMO",
        help="Um ou mais termos a buscar nos arquivos",
    )
    parser.add_argument(
        "--output", default=default_output, metavar="ARQUIVO",
        help="Arquivo JSON de saída",
    )
    parser.add_argument(
        "--root", default=default_root, metavar="DIR",
        help="Diretório raiz a percorrer",
    )
    parser.add_argument(
        "--ext", nargs="+", default=list(DEFAULT_EXTENSIONS), metavar="EXT",
        help="Extensões de arquivo a incluir",
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
        help="Tamanho máximo de arquivo em KB",
    )
    parser.add_argument(
        "--no-gitignore", action="store_true", dest="no_gitignore",
        help="Não usa .gitignore para filtrar arquivos",
    )
    parser.add_argument(
        "--case-sensitive", action="store_true", dest="case_sensitive",
        help="Busca com diferenciação de maiúsculas/minúsculas",
    )
    parser.add_argument(
        "--whole-word", action="store_true", dest="whole_word",
        help="Busca apenas palavras completas (word boundary)",
    )
    parser.add_argument(
        "--no-sort", action="store_true", dest="no_sort",
        help="Não ordena resultados por quantidade de ocorrências",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    print(f"[crawler] Raiz          : {os.path.abspath(args.root)}")
    print(f"[crawler] Termos        : {args.term}")
    print(f"[crawler] Saída         : {os.path.abspath(args.output)}")
    print(f"[crawler] Case-sensitive: {args.case_sensitive}")
    print(f"[crawler] Whole-word    : {args.whole_word}")
    print()

    crawl(
        terms=args.term,
        root=args.root,
        output_file=args.output,
        extensions=tuple(args.ext),
        exclude_dirs=tuple(args.exclude_dirs),
        exclude_files=tuple(args.exclude_files),
        max_file_kb=args.max_file_kb,
        use_gitignore=not args.no_gitignore,
        case_sensitive=args.case_sensitive,
        whole_word=args.whole_word,
        sort_results=not args.no_sort,
    )
