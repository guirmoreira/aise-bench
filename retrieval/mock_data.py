"""
mock_data.py — Gerador de estrutura de pastas e arquivos mock para testes de retrieval.

Uso:
    python mock_data.py --tokens 1000 --depth 3 --min-file-size 50 --max-file-size 200
    python mock_data.py --purge
    python mock_data.py --tokens 500 --depth 2 --min-file-size 50 --max-file-size 150 --cherry "frase secreta aqui"
    python mock_data.py --export-json output.json

Argumentos:
    tokens          Quantidade total de tokens a distribuir entre os arquivos
    depth           Profundidade máxima da árvore de pastas
    min-file-size   Quantidade mínima de tokens por arquivo
    max-file-size   Quantidade máxima de tokens por arquivo
    --purge         Apaga todo o conteúdo de retrieval/data/ sem gerar nada novo
    --cherry TEXT   Insere a frase TEXT no meio de um arquivo .txt escolhido aleatoriamente
    --export-json   Exporta todos os arquivos como um JSON [{path, content}, ...]

Saída:
    Estrutura de pastas/arquivos criada em retrieval/data/
"""

import argparse
import json
import math
import os
import random
import shutil
import string

# ---------------------------------------------------------------------------
# Corpus lorem ipsum — palavras base para geração de texto
# ---------------------------------------------------------------------------

_LOREM_WORDS: list[str] = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua enim ad minim veniam quis nostrud "
    "exercitation ullamco laboris nisi aliquip ex ea commodo consequat duis aute "
    "irure in reprehenderit voluptate velit esse cillum eu fugiat nulla pariatur "
    "excepteur sint occaecat cupidatat non proident sunt culpa qui officia deserunt "
    "mollit anim id est laborum curabitur pretium tincidunt lacus nulla gravida orci "
    "a odio tempus rhoncus nec hendrerit ipsum quisque ultrices laoreet ante "
    "habitasse platea dictumst vitae risus commodo viverra maecenas accumsan "
    "lacinia posuere cubilia curae pellentesque suscipit ligula luctus etiam "
    "faucibus cursus urna fusce aliquet pede volutpat diam ut varius vestibulum "
    "vulputate nisl purus pretium feugiat condimentum proin egestas dapibus "
    "malesuada portitor duis felis orci pulvinar interdum dictum tristique "
    "scelerisque auctor elementum senectus netus malesuada fames turpis egestas "
    "venenatis sagittis neque sodales penatibus magnis dis parturient montes "
    "nascetur ridiculus mus praesent blandit laoreet nibh donec semper sapien "
    "convallis posuere morbi leo risus porta feugiat at varius vel phasellus "
    "imperdiet quam viverra congue erat lacinia quis veniam facilisi cras ornare "
    "arcu dui vivamus arcu felis bibendum ut tristique aenean augue quam elementum "
    "pulvinar etiam non quam lacus suspendisse faucibus interdum posuere lorem "
    "ipsum dolor sit amet consectetur adipiscing elit pellentesque habitant morbi"
).split()


def _generate_lorem(num_tokens: int) -> str:
    """
    Gera texto lorem ipsum com exatamente `num_tokens` palavras.
    Cada palavra é contada como 1 token (aproximação simples).
    """
    if num_tokens <= 0:
        return ""
    words = [random.choice(_LOREM_WORDS) for _ in range(num_tokens)]
    # Organiza em parágrafos de ~15 a 25 palavras
    paragraphs: list[str] = []
    i = 0
    while i < len(words):
        chunk_size = random.randint(15, 25)
        chunk = words[i: i + chunk_size]
        sentence = " ".join(chunk).capitalize() + "."
        paragraphs.append(sentence)
        i += chunk_size
    return "\n\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Geração de nomes aleatórios
# ---------------------------------------------------------------------------

_ADJECTIVES = [
    "red", "blue", "fast", "slow", "bright", "dark", "cold", "warm",
    "deep", "soft", "hard", "quiet", "loud", "sharp", "smooth", "rough",
    "light", "heavy", "wide", "narrow", "tall", "short", "old", "new",
    "clean", "dirty", "open", "closed", "full", "empty",
]

_NOUNS = [
    "river", "stone", "forest", "cloud", "flame", "echo", "shadow",
    "bridge", "tower", "field", "valley", "ridge", "creek", "meadow",
    "harbor", "island", "canyon", "desert", "glacier", "prairie",
    "archive", "module", "vector", "cluster", "index", "node", "branch",
    "layer", "sector", "domain",
]


def _random_name(used: set[str]) -> str:
    """Gera um nome único no formato <adjetivo>_<substantivo>_<hex>."""
    for _ in range(1000):
        name = f"{random.choice(_ADJECTIVES)}_{random.choice(_NOUNS)}_{random.randint(0, 0xFFFF):04x}"
        if name not in used:
            used.add(name)
            return name
    # fallback extremamente improvável
    fallback = "item_" + "".join(random.choices(string.hexdigits[:16], k=8))
    used.add(fallback)
    return fallback


# ---------------------------------------------------------------------------
# Planejamento da árvore de diretórios
# ---------------------------------------------------------------------------

def _plan_tree(
    tokens_remaining: int,
    current_depth: int,
    max_depth: int,
    min_file: int,
    max_file: int,
    used_names: set[str],
) -> dict:
    """
    Retorna um dict representando um nó da árvore:
        {
            "files": [int, ...],   # lista com tamanho (tokens) de cada arquivo
            "subdirs": [dict, ...]  # sub-árvores
        }

    A alocação de tokens é feita de cima para baixo; cada nível consome
    uma parte dos tokens restantes para seus próprios arquivos e distribui
    o restante pelos sub-diretórios.
    """
    node: dict = {"files": [], "subdirs": [], "name": _random_name(used_names)}

    if tokens_remaining <= 0:
        return node

    # Decide quantos arquivos criar neste nó (0 a 4)
    max_files_here = max(0, tokens_remaining // max(min_file, 1))
    num_files = random.randint(0, min(4, max_files_here))

    tokens_for_files = 0
    for _ in range(num_files):
        if tokens_remaining - tokens_for_files < min_file:
            break
        size = random.randint(
            min_file,
            min(max_file, tokens_remaining - tokens_for_files)
        )
        node["files"].append(size)
        tokens_for_files += size

    tokens_remaining -= tokens_for_files

    # Se ainda há profundidade disponível e tokens sobrando, cria sub-pastas
    if current_depth < max_depth and tokens_remaining >= min_file:
        num_subdirs = random.randint(
            1, min(4, max(1, tokens_remaining // max(min_file, 1))))
        # Distribui tokens entre os sub-diretórios de forma aleatória
        if num_subdirs > 0:
            splits = sorted(random.sample(
                range(min_file, tokens_remaining + 1),
                k=min(num_subdirs - 1, tokens_remaining - min_file)
            )) if tokens_remaining > min_file * num_subdirs else []

            # Garante parcelas mínimas
            budgets: list[int] = []
            remaining = tokens_remaining
            for i in range(num_subdirs):
                if i == num_subdirs - 1:
                    budgets.append(remaining)
                else:
                    share = random.randint(
                        min_file,
                        max(min_file, remaining -
                            min_file * (num_subdirs - i - 1))
                    )
                    budgets.append(share)
                    remaining -= share
                    if remaining < min_file:
                        break

            for budget in budgets:
                if budget < min_file:
                    continue
                child = _plan_tree(
                    tokens_remaining=budget,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                    min_file=min_file,
                    max_file=max_file,
                    used_names=used_names,
                )
                node["subdirs"].append(child)

    return node


# ---------------------------------------------------------------------------
# Escrita da árvore em disco
# ---------------------------------------------------------------------------

def _write_tree(node: dict, base_path: str, used_file_names: set[str]) -> tuple[int, int]:
    """
    Cria recursivamente pastas e arquivos conforme o plano.
    Retorna (total_files_created, total_tokens_written).
    """
    os.makedirs(base_path, exist_ok=True)

    total_files = 0
    total_tokens = 0

    for token_count in node["files"]:
        fname = _random_name(used_file_names) + ".txt"
        fpath = os.path.join(base_path, fname)
        content = _generate_lorem(token_count)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        total_files += 1
        total_tokens += token_count

    for child in node["subdirs"]:
        child_path = os.path.join(base_path, child["name"])
        f_count, t_count = _write_tree(child, child_path, used_file_names)
        total_files += f_count
        total_tokens += t_count

    return total_files, total_tokens


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _default_data_dir() -> str:
    """Retorna o caminho padrão de retrieval/data/ relativo a este script."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def purge(output_dir: str | None = None) -> None:
    """
    Remove todo o conteúdo de `output_dir` (padrão: retrieval/data/).
    O diretório raiz é mantido, apenas seu conteúdo é apagado.
    """
    data_dir = output_dir or _default_data_dir()
    if not os.path.exists(data_dir):
        print(f"[mock_data] Nada a remover: {data_dir} não existe.")
        return
    for entry in os.listdir(data_dir):
        entry_path = os.path.join(data_dir, entry)
        if os.path.isdir(entry_path):
            shutil.rmtree(entry_path)
        else:
            os.remove(entry_path)
    print(f"[mock_data] ✓ Conteúdo de '{data_dir}' removido.")


def insert_cherry(cherry: str, output_dir: str | None = None) -> None:
    """
    Escolhe aleatoriamente um arquivo .txt dentro de `output_dir` e insere
    `cherry` no meio do seu conteúdo (entre os parágrafos centrais).

    Args:
        cherry:     Frase a ser inserida.
        output_dir: Diretório base (padrão: retrieval/data/).
    """
    data_dir = output_dir or _default_data_dir()

    # Coleta todos os .txt recursivamente
    txt_files: list[str] = []
    for root, _, files in os.walk(data_dir):
        for fname in files:
            if fname.endswith(".txt"):
                txt_files.append(os.path.join(root, fname))

    if not txt_files:
        print("[mock_data] Nenhum arquivo .txt encontrado. Gere dados primeiro.")
        return

    chosen = random.choice(txt_files)
    with open(chosen, "r", encoding="utf-8") as f:
        content = f.read()

    paragraphs = content.split("\n\n")
    mid = len(paragraphs) // 2
    paragraphs.insert(mid, cherry)

    with open(chosen, "w", encoding="utf-8") as f:
        f.write("\n\n".join(paragraphs))

    rel_path = os.path.relpath(chosen, data_dir)
    print(f"[mock_data] ✓ Cherry inserida em: {rel_path}")
    print(f"            Frase : \"{cherry}\"")


def export_json(output_file: str, data_dir: str | None = None) -> None:
    """
    Percorre recursivamente `data_dir` e grava um JSON com a lista de todos
    os arquivos no formato:
        [{"path": "caminho/relativo/arquivo.txt", "content": "..."}, ...]

    Args:
        output_file: Caminho do arquivo JSON de saída.
        data_dir:    Diretório base (padrão: retrieval/data/).
    """
    base_dir = data_dir or _default_data_dir()

    if not os.path.exists(base_dir):
        print(f"[mock_data] Diretório não encontrado: {base_dir}")
        return

    records: list[dict] = []
    for root, _, files in os.walk(base_dir):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, base_dir).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                records.append({"path": rel_path, "content": content})
            except Exception as exc:
                print(
                    f"[mock_data] Aviso: não foi possível ler '{rel_path}': {exc}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"[mock_data] ✓ JSON exportado: {output_file}")
    print(f"            Arquivos incluídos: {len(records)}")


def generate(
    tokens: int,
    depth: int,
    min_file_size: int,
    max_file_size: int,
    output_dir: str | None = None,
    clean: bool = False,
) -> None:
    """
    Gera a estrutura mock de dados.

    Args:
        tokens:        Total de tokens a distribuir.
        depth:         Profundidade máxima de pastas.
        min_file_size: Tokens mínimos por arquivo.
        max_file_size: Tokens máximos por arquivo.
        output_dir:    Caminho de saída (padrão: retrieval/data/ ao lado deste script).
        clean:         Se True, apaga e recria o diretório de saída antes de gerar.
    """
    # Validações básicas
    if min_file_size < 1:
        raise ValueError("min_file_size deve ser >= 1")
    if max_file_size < min_file_size:
        raise ValueError("max_file_size deve ser >= min_file_size")
    if depth < 1:
        raise ValueError("depth deve ser >= 1")
    if tokens < min_file_size:
        raise ValueError("tokens deve ser >= min_file_size")

    # Diretório de saída
    if output_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "data")

    if clean and os.path.exists(output_dir):
        shutil.rmtree(output_dir)
        print(f"[mock_data] Diretório existente removido: {output_dir}")

    print(f"[mock_data] Planejando árvore com {tokens} tokens, profundidade={depth}, "
          f"arquivo={min_file_size}–{max_file_size} tokens...")

    used_dir_names: set[str] = set()
    used_file_names: set[str] = set()

    tree = _plan_tree(
        tokens_remaining=tokens,
        current_depth=1,
        max_depth=depth,
        min_file=min_file_size,
        max_file=max_file_size,
        used_names=used_dir_names,
    )

    print(f"[mock_data] Escrevendo arquivos em: {output_dir}")
    root_path = os.path.join(output_dir, tree["name"])
    total_files, total_tokens = _write_tree(tree, root_path, used_file_names)

    print(f"[mock_data] ✓ Concluído!")
    print(f"            Arquivos criados : {total_files}")
    print(f"            Tokens escritos  : {total_tokens} / {tokens}")
    print(f"            Raiz             : {root_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera estrutura de pastas e arquivos lorem ipsum para testes de retrieval.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tokens", type=int, default=None,
        help="Total de tokens a distribuir entre os arquivos",
    )
    parser.add_argument(
        "--depth", type=int, default=None,
        help="Profundidade máxima da árvore de pastas",
    )
    parser.add_argument(
        "--min-file-size", type=int, default=None,
        dest="min_file_size",
        help="Tokens mínimos por arquivo",
    )
    parser.add_argument(
        "--max-file-size", type=int, default=None,
        dest="max_file_size",
        help="Tokens máximos por arquivo",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        dest="output_dir",
        help="Diretório de saída (padrão: retrieval/data/ ao lado do script)",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Remove e recria o diretório de saída antes de gerar",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Semente para reprodutibilidade (opcional)",
    )
    # --- novas opções ---
    parser.add_argument(
        "--purge", action="store_true",
        help="Apaga todo o conteúdo de retrieval/data/ sem gerar nada novo",
    )
    parser.add_argument(
        "--cherry", type=str, default=None, metavar="TEXTO",
        help="Insere a frase TEXTO no meio de um arquivo .txt aleatório",
    )
    parser.add_argument(
        "--export-json", type=str, default=None, metavar="ARQUIVO",
        dest="export_json",
        help="Exporta todos os arquivos como JSON [{path, content}] para ARQUIVO",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        print(f"[mock_data] Seed: {args.seed}")

    # --purge: apenas limpa, sem gerar
    if args.purge:
        purge(output_dir=args.output_dir)

    # --cherry: insere frase em arquivo existente
    elif args.cherry is not None:
        insert_cherry(cherry=args.cherry, output_dir=args.output_dir)

    # --export-json: exporta estrutura para JSON
    elif args.export_json is not None:
        export_json(output_file=args.export_json, data_dir=args.output_dir)

    # modo padrão: gerar estrutura de dados
    else:
        missing = [
            name for name, val in [
                ("--tokens", args.tokens),
                ("--depth", args.depth),
                ("--min-file-size", args.min_file_size),
                ("--max-file-size", args.max_file_size),
            ] if val is None
        ]
        if missing:
            print(
                f"[mock_data] Erro: os seguintes argumentos são obrigatórios para geração: {', '.join(missing)}")
            raise SystemExit(1)

        generate(
            tokens=args.tokens,
            depth=args.depth,
            min_file_size=args.min_file_size,
            max_file_size=args.max_file_size,
            output_dir=args.output_dir,
            clean=args.clean,
        )
