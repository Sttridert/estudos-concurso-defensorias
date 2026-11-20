#!/usr/bin/env python3
"""Etapa 4 do plano do edital fictício geral: extrai o programa de uma disciplina de cada edital.

Uso:  python -I scripts/40_extrair_programas.py DH|PENAL|EXEC [--so "trecho do nome da pasta"]

Lê `provas/*/1. edital.pdf` (menos cargos de apoio), acha a seção da disciplina, divide em itens
(pela numeração do próprio edital) e em frases, e grava `dados/programas_editais/<disciplina>/<pasta>.json`.
Não altera o banco. Regras de cópia (CLAUDE.md): texto literal; só se juntam quebras de linha e
palavras hifenizadas no fim da linha. Hifenização duvidosa fica marcada em `avisos`.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_programa_edital import metadados, processar   # noqa: E402  (núcleo agora na biblioteca do grupo A)

RAIZ = Path(__file__).resolve().parent.parent
PROVAS = RAIZ / "provas"
SAIDA = RAIZ / "dados" / "programas_editais"


def main():
    alvo = sys.argv[1].upper()
    so = None
    if "--so" in sys.argv:
        so = sys.argv[sys.argv.index("--so") + 1]
    meta = metadados()
    (SAIDA / alvo).mkdir(parents=True, exist_ok=True)
    print(f"{'edital':62} {'banca':10} secoes  itens  frases  caracteres")
    for pasta in sorted(PROVAS.iterdir()):
        if not (pasta / "1. edital.pdf").exists() or pasta.name == "NOVAS" or "Assistente" in pasta.name:
            continue
        if "Analista Jurídico (2)" in pasta.name:      # mesmo arquivo do Analista Jurídico 2022
            continue
        if so and so not in pasta.name:
            continue
        r = processar(pasta, alvo, meta)
        (SAIDA / alvo / f"{pasta.name}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        ni = sum(len(s["itens"]) for s in r["secoes"]); nf = sum(len(i["frases"]) for s in r["secoes"] for i in s["itens"])
        nc = sum(s["caracteres"] for s in r["secoes"])
        print(f"{pasta.name[:62]:62} {r['banca'][:10]:10} {len(r['secoes']):5d} {ni:6d} {nf:7d} {nc:10d}")


if __name__ == "__main__":
    main()
