#!/usr/bin/env python3
"""GRUPO F (Produzir): compara o motor de análise (`23`) dos perfis com uma base de regressão. Não altera o projeto nem o banco.

Uso:
  python -I scripts/produzir_regressao.py [--base banco/base-regressao-AAAA-MM-DD] [--perfil ID ...] [--mostrar-tudo]

O que faz:
  1. copia o projeto (scripts, dados, perfis de produtos/apostilas e o banco) para uma pasta temporária, porque o motor lê o banco por caminho fixo;
  2. roda `23_motor_analise.py` em cada perfil (todos os que existem nos `perfil.toml`, ou só os dados em --perfil);
  3. compara cada saída (.json) com a da base, campo a campo (sem olhar a ordem das chaves), e diz quais perfis mudaram e onde.
Código de saída: 0 = todos idênticos; 1 = alguma diferença ou falha. A base padrão é a mais recente de banco/base-regressao-*.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_perfil as LP  # noqa: E402

COPIAR = ("scripts", "dados")


def base_padrao():
    bases = sorted((RAIZ / "banco").glob("base-regressao-*"))
    return bases[-1] if bases else None


def ids_dos_perfis(raiz):
    """ids de todas as apostilas nos perfil.toml de `raiz`, em ordem"""
    ids = []
    for arq in sorted((raiz / "produtos" / "apostilas").glob("*/perfil.toml")):
        for a in LP.ler(arq).get("apostila", []):
            if a.get("id") is not None:
                ids.append(a["id"])
    return sorted(ids)


def copiar_projeto(origem, destino):
    for nome in COPIAR:
        shutil.copytree(origem / nome, destino / nome, ignore=shutil.ignore_patterns("__pycache__"))
    (destino / "banco").mkdir()
    shutil.copy2(origem / "banco" / "estudos.db", destino / "banco" / "estudos.db")
    for arq in (origem / "produtos" / "apostilas").glob("*/perfil.toml"):
        alvo = destino / "produtos" / "apostilas" / arq.parent.name
        alvo.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arq, alvo / "perfil.toml")


def rodar_motor(copia, pid):
    """roda o 23 na cópia; devolve (ok, mensagem)"""
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(copia / "scripts" / "23_motor_analise.py"), "--perfil", str(pid)],
                       capture_output=True, text=True, encoding="utf-8", cwd=copia)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def diferencas(a, b, caminho=""):
    """lista de textos 'caminho: base X, agora Y' onde os dois valores diferem (compara dicionários por chave, listas por posição)"""
    if type(a) is not type(b):
        return [f"{caminho or '/'}: base {_curto(a)}, agora {_curto(b)}"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append(f"{caminho}/{k}: só agora")
            elif k not in b:
                out.append(f"{caminho}/{k}: só na base")
            else:
                out += diferencas(a[k], b[k], f"{caminho}/{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{caminho}: base com {len(a)} itens, agora {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diferencas(x, y, f"{caminho}[{i}]")
        return out
    return [] if a == b else [f"{caminho}: base {_curto(a)}, agora {_curto(b)}"]


def _curto(x):
    t = json.dumps(x, ensure_ascii=False)
    return t if len(t) <= 60 else t[:57] + "..."


def comparar_pasta(analise_base, analise_nova, pids_pedidos=None):
    """compara os .json da base com os gerados; devolve (identicos, mudaram{nome: [dif]}, faltando[nomes], sobrando[nomes])"""
    base = {p.name: p for p in analise_base.glob("*.json")}
    nova = {p.name: p for p in analise_nova.glob("*.json")}
    if pids_pedidos:
        sufixos = tuple(f"_perfil{i}.json" for i in pids_pedidos)
        base = {k: v for k, v in base.items() if k.endswith(sufixos)}
        nova = {k: v for k, v in nova.items() if k.endswith(sufixos)}
    identicos, mudaram = [], {}
    for nome in sorted(set(base) & set(nova)):
        d = diferencas(json.loads(base[nome].read_text(encoding="utf-8")), json.loads(nova[nome].read_text(encoding="utf-8")))
        if d:
            mudaram[nome] = d
        else:
            identicos.append(nome)
    return identicos, mudaram, sorted(set(base) - set(nova)), sorted(set(nova) - set(base))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", help="pasta da base de regressão (padrão: a mais recente em banco/)")
    ap.add_argument("--perfil", type=int, action="append", help="só este perfil (pode repetir)")
    ap.add_argument("--mostrar-tudo", action="store_true", help="mostra todas as diferenças (padrão: as 15 primeiras por perfil)")
    a = ap.parse_args()
    base = Path(a.base) if a.base else base_padrao()
    if base is None or not (base / "analise").is_dir():
        sys.exit("Base de regressão não encontrada (esperado banco/base-regressao-*/analise). Use --base.")
    base = base if base.is_absolute() else RAIZ / base
    ids = a.perfil or ids_dos_perfis(RAIZ)
    print(f"Base: {base.relative_to(RAIZ) if base.is_relative_to(RAIZ) else base}  |  perfis: {', '.join(map(str, ids))}")
    with tempfile.TemporaryDirectory(prefix="regressao_") as tmp:
        copia = Path(tmp) / "projeto"
        copia.mkdir()
        copiar_projeto(RAIZ, copia)
        falhas = {}
        for pid in ids:
            ok, msg = rodar_motor(copia, pid)
            if not ok:
                falhas[pid] = msg.splitlines()[-1] if msg else "falhou sem mensagem"
        identicos, mudaram, faltando, sobrando = comparar_pasta(base / "analise", copia / "banco" / "analise", a.perfil)
    for pid, msg in falhas.items():
        print(f"FALHOU  perfil {pid}: {msg}")
    for nome in identicos:
        print(f"idêntico  {nome}")
    for nome, dif in mudaram.items():
        print(f"MUDOU     {nome}: {len(dif)} diferenças")
        for d in dif if a.mostrar_tudo else dif[:15]:
            print("            " + d)
        if not a.mostrar_tudo and len(dif) > 15:
            print(f"            ... (+{len(dif) - 15}; use --mostrar-tudo)")
    for nome in faltando:
        print(f"SÓ NA BASE  {nome} (o motor não gerou)")
    for nome in sobrando:
        print(f"SÓ AGORA    {nome} (a base não tem)")
    ruim = bool(falhas or mudaram or faltando or sobrando)
    print(f"\nResultado: {len(identicos)} idênticos, {len(mudaram)} mudaram, {len(falhas)} falharam, {len(faltando)} só na base, {len(sobrando)} só agora.")
    sys.exit(1 if ruim else 0)


if __name__ == "__main__":
    main()
