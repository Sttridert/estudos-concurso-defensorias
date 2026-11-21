#!/usr/bin/env python3
"""GRUPO F (Produzir): "o que está desatualizado?" Só leitura.

Uso:
  python -I scripts/produzir_status.py [--perfil ID ...] [--detalhe]

Para cada perfil: o semáforo (bloqueia, avisa, informa) e se a apostila gerada está em dia, comparando a impressão digital registrada na última
geração (`impressoes.json`, na pasta do concurso) com a impressão do que existe hoje (perfil, catálogo, edital do bloco, questões, classificação,
comentários e código gerador). Apostila gerada antes do registro aparece como "sem registro". Código de saída: 0 sempre (é um relatório).
"""
import argparse
import sqlite3
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import lib_perfil as LP  # noqa: E402
import lib_semaforo as S  # noqa: E402

BANCO = AQUI.parent / "banco" / "estudos.db"
SIMBOLO = {S.BLOQUEIA: "[BLOQUEIA]", S.AVISA: "[avisa]   ", S.INFORMA: "[informa] "}


def situacao_da_apostila(con, perfil):
    """(texto, em_dia) da apostila do perfil"""
    reg = S.ler_registro(perfil)
    if not reg:
        return "sem registro (gerada antes da impressão digital, ou nunca gerada): regerar para registrar", False
    mudou = S.desatualizado(reg, S.insumos(con, perfil))
    if mudou:
        return f"DESATUALIZADA desde {reg.get('gerada_em', '?')}: mudou " + "; ".join(mudou), False
    return f"em dia (gerada em {reg.get('gerada_em', '?')})", True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perfil", type=int, action="append")
    ap.add_argument("--detalhe", action="store_true", help="mostra também os itens 'informa'")
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    ids = a.perfil or sorted(x["id"] for arq in LP.achar_arquivos() for x in LP.ler(arq).get("apostila", []) if x.get("id") is not None)
    em_dia = 0
    for pid in ids:
        perfil = S.carregar_perfil(con, pid)
        if perfil is None:
            print(f"Perfil {pid}: não existe\n")
            continue
        achados = S.verificar(con, perfil)
        texto, ok = situacao_da_apostila(con, perfil)
        em_dia += ok
        print(f"Perfil {pid} · {perfil['nome']}")
        print(f"  apostila: {texto}")
        for x in achados:
            if x.nivel != S.INFORMA or a.detalhe:
                print(f"  {SIMBOLO[x.nivel]} {x.texto}")
        print()
    print(f"{em_dia} de {len(ids)} apostilas em dia.")


if __name__ == "__main__":
    main()
