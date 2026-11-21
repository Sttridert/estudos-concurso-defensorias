#!/usr/bin/env python3
"""Grupo A (Coletar), pista de editais: programa literal de um edital real. Reúne os antigos 50 e 56 e acrescenta `disciplinas`.

Uso (sempre com `python -I`):
  python -I scripts/coletar_programa_edital.py disciplinas "<pasta em provas/>"
      Só leitura. Lista TODAS as disciplinas que o PDF do edital traz (título no edital, tamanho do trecho e a sigla do catálogo
      quando for uma das disciplinas conhecidas). Serve para descobrir matérias fora do catálogo (Informática, Língua Portuguesa,
      Raciocínio Lógico...) e para saber, antes de extrair, o que o edital cobra.                                 (novo, A-5)
  python -I scripts/coletar_programa_edital.py extrair "<pasta em provas/>" --slug <slug> [--alvos CONST,ADM,...]
      Lê `provas/<pasta>/1. edital.pdf` e grava `dados/editais_reais/<slug>/programa.json`:
        edital               metadados (banca, carreira, cargo, órgão, ano, arquivo)
        disciplinas          lista de {codigo, disciplina_banco, titulo_no_edital, itens:[{ordem, rotulo, frases:[{id, texto}]}]}
        disciplinas_do_edital  (novo) todos os títulos que o PDF traz, com a sigla do catálogo ou nulo: mostra o que ficou de fora
      Texto ipsis litteris; só se juntam quebras de linha e palavras hifenizadas. Guardrail: cada frase é conferida contra o texto
      bruto do PDF (sem espaços nem hífens); se alguma não existir igual, o script lista e NÃO grava. Não altera o banco.   (antigo 50)
  python -I scripts/coletar_programa_edital.py acrescentar-bloco <slug> --codigo LP --disciplina "Língua Portuguesa" \\
        --titulo "LÍNGUA PORTUGUESA" --inicio "LÍNGUA PORTUGUESA:" --fim "LEGISLAÇÃO DA DEFENSORIA:"
      Acrescenta ao `programa.json` um bloco que o `extrair` não pega (Conhecimentos Gerais, Língua Portuguesa...), com o mesmo
      guardrail. Idempotente: substitui a disciplina de mesmo código.                                            (antigo 56)
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_programa_edital as LP   # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

import lib_disciplinas as LD   # noqa: E402  (fonte única: dados/disciplinas.json)
DISCIPLINA_BANCO = LD.nomes(extrair_edital_real=True)
ORDEM_PADRAO = LD.ordem_extracao()


def _pdf_do_edital(pasta):
    pdf = RAIZ / "provas" / pasta / "1. edital.pdf"
    if not pdf.exists():
        sys.exit(f"não achei {pdf}")
    return pdf


# ---------------------------------------------------------------- disciplinas (novo)
def disciplinas(pasta, tudo=False):
    pdf = _pdf_do_edital(pasta)
    todas = LP.listar_disciplinas(pdf)
    lista = todas if tudo else [d for d in todas if d["no_programa"]]
    print(f"{pasta}: {len(lista)} títulos na região do conteúdo programático"
          + (f" (o PDF traz {len(todas)} títulos ao todo; `--tudo` mostra todos)" if not tudo else " (todos os títulos do PDF)") + "\n")
    print(f"{'sigla':7} {'caracteres':>10}  título no edital")
    for d in lista:
        print(f"{d['codigo'] or '-':7} {d['caracteres']:10d}  {d['titulo_no_edital']}" + ("" if d["no_programa"] else "   [fora do programa]"))
    fora = [d for d in lista if d["codigo"] is None]
    print(f"\n{len(lista) - len(fora)} do catálogo; {len(fora)} fora do catálogo (sigla '-'). Podem incluir ruído (linha de tabela, "
          "nome de cargo); conferir no PDF. Disciplinas escritas com outra formatação (ex.: bloco \"CONHECIMENTOS GERAIS\") "
          "podem não aparecer: nesse caso use `acrescentar-bloco`.")


# ---------------------------------------------------------------- extrair (antigo 50)
def extrair(pasta_nome, slug, alvos):
    pasta = RAIZ / "provas" / pasta_nome
    pdf = _pdf_do_edital(pasta_nome)
    meta = LP.metadados()
    inv = {}
    rel = f"provas/{pasta.name}/1. edital.pdf"
    with open(RAIZ / "dados" / "coleta" / "inventario_editais_edital_geral.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["arquivo_local"].replace("\\", "/") == rel:
                inv = r
    bruto = LP.texto_bruto(pdf)
    disciplinas_, falhas = [], []
    for alvo in [x.strip().upper() for x in alvos.split(",") if x.strip()]:
        r = LP.processar(pasta, alvo, meta, dividir=LP.dividir_itens_tolerante)
        if not r["secoes"]:
            print(f"{alvo}: nenhuma seção encontrada")
            continue
        sec = max(r["secoes"], key=lambda s: s["caracteres"])
        itens, n = [], 0
        for k, it in enumerate(sec["itens"], 1):
            fr = []
            for f in it["frases"]:
                n += 1
                fr.append({"id": f"{alvo}-{n:03d}", "texto": f})
                if LP.compacto(f) not in bruto:
                    falhas.append(f"{alvo}-{n:03d}: {f[:90]!r}")
            itens.append({"ordem": k, "rotulo": it["item"] or None, "frases": fr})
        disciplinas_.append({"codigo": alvo, "disciplina_banco": DISCIPLINA_BANCO[alvo], "titulo_no_edital": sec["titulo_no_edital"],
                             "avisos": sec["avisos"], "itens": itens})
        print(f"{alvo:6} {len(itens):3d} itens {n:4d} frases  rótulos: {', '.join((i['rotulo'] or '-') for i in itens)[:150]}")
    if falhas:
        sys.exit("NÃO gravado: frases que não são cópia exata do PDF:\n  " + "\n  ".join(falhas))
    saida = RAIZ / "dados" / "editais_reais" / slug
    saida.mkdir(parents=True, exist_ok=True)
    edital = {"slug": slug, "pasta": pasta.name, "arquivo": rel, "banca": inv.get("banca", "?"), "orgao": inv.get("orgao"),
              "cargo": inv.get("cargo"), "ano": int(inv["ano_do_edital"]) if inv.get("ano_do_edital") else None}
    todas = LP.listar_disciplinas(pdf)
    (saida / "programa.json").write_text(json.dumps({"edital": edital, "disciplinas": disciplinas_, "disciplinas_do_edital": todas},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"gravado {saida / 'programa.json'}: {len(disciplinas_)} disciplinas, "
          f"{sum(len(i['frases']) for d in disciplinas_ for i in d['itens'])} frases; o PDF traz {len(todas)} títulos "
          f"({sum(1 for d in todas if d['codigo'] is None)} fora do catálogo; ver `disciplinas_do_edital`)")


# ---------------------------------------------------------------- acrescentar-bloco (antigo 56)
def acrescentar_bloco(a):
    pj = RAIZ / "dados" / "editais_reais" / a.slug / "programa.json"
    prog = json.loads(pj.read_text(encoding="utf-8"))
    pdf = RAIZ / prog["edital"]["arquivo"]
    bruto = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True).stdout.decode("utf-8", "replace")
    linhas = [l for l in bruto.splitlines() if not re.fullmatch(r"\s*\d{1,3}\s*", l)]
    texto = "\n".join(linhas)
    base = texto.index(a.apos)
    i = texto.index(a.inicio, base) + len(a.inicio)
    j = texto.index(a.fim, i)
    trecho = texto[i:j]

    # palavra hifenizada no fim da linha: junta sem hífen; se a parte da esquerda é sigla (2+ maiúsculas, ex.: "DPE-" + "AM")
    # ou a da direita começa em maiúscula, o hífen é do próprio nome e fica (defeito "DPEAM", 15/11/2026)
    def _junta(mt):
        esq, dir_ = mt.group(1), mt.group(2)
        return esq + "-" + dir_ if (esq.isupper() and len(esq) >= 2) or dir_[:1].isupper() else esq + dir_
    trecho = re.sub(r"(\w+)-\n(\w+)", _junta, trecho)
    trecho = re.sub(r"\s*\n\s*", " ", trecho).strip()
    frases, atual, prof = [], "", 0
    for k, ch in enumerate(trecho):
        atual += ch
        prof += ch == "("
        prof -= ch == ")"
        # "n.º 01/1990" e "1.762" não encerram a frase
        if ch == "." and prof == 0 and trecho[k + 1:k + 2] not in ("º", "ª") and not trecho[k + 1:k + 2].isdigit():
            frases.append(atual.strip())
            atual = ""
    if atual.strip():
        frases.append(atual.strip())
    comp = LP.compacto(texto)
    ruins = [f for f in frases if LP.compacto(f) not in comp]
    if ruins:
        sys.exit("NÃO gravado: frases que não são cópia exata do PDF:\n  " + "\n  ".join(ruins))
    antigo = next((d for d in prog["disciplinas"] if d["codigo"] == a.codigo), None)
    if a.item > 1 and antigo:
        antigo["itens"] = [i for i in antigo["itens"] if i["ordem"] != a.item]
        n0 = sum(len(i["frases"]) for i in antigo["itens"])
        antigo["itens"].append({"ordem": a.item, "rotulo": a.rotulo,
                                "frases": [{"id": f"{a.codigo}-{n0 + k:03d}", "texto": f} for k, f in enumerate(frases, 1)]})
        disc = antigo
    else:
        disc = {"codigo": a.codigo, "disciplina_banco": a.disciplina, "titulo_no_edital": a.titulo, "avisos": [],
                "itens": [{"ordem": a.item, "rotulo": a.rotulo,
                           "frases": [{"id": f"{a.codigo}-{k:03d}", "texto": f} for k, f in enumerate(frases, 1)]}]}
        prog["disciplinas"] = [d for d in prog["disciplinas"] if d["codigo"] != a.codigo] + [disc]
    pj.write_text(json.dumps(prog, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{a.codigo}: {len(frases)} frases gravadas em {pj}")
    for i in disc["itens"]:
        for f in i["frases"]:
            print(" ", f["id"], f["texto"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("disciplinas")
    d.add_argument("pasta")
    d.add_argument("--tudo", action="store_true", help="inclui os títulos fora da região do conteúdo programático")
    e = sub.add_parser("extrair")
    e.add_argument("pasta")
    e.add_argument("--slug", required=True)
    e.add_argument("--alvos", default=",".join(ORDEM_PADRAO))
    b = sub.add_parser("acrescentar-bloco")
    b.add_argument("slug")
    b.add_argument("--codigo", required=True)
    b.add_argument("--disciplina", required=True)
    b.add_argument("--titulo", required=True)
    b.add_argument("--inicio", required=True)
    b.add_argument("--fim", required=True)
    b.add_argument("--apos", default="CONTEÚDO PROGRAMÁTICO")
    b.add_argument("--item", type=int, default=1,
                   help="ordem do item; com 2 ou mais, o item é acrescentado ao bloco de mesmo --codigo (dois trechos do edital numa só disciplina)")
    b.add_argument("--rotulo", default=None, help="rótulo do item (ex.: o nome do trecho do edital)")
    x = ap.parse_args()
    if x.cmd == "disciplinas":
        disciplinas(x.pasta, x.tudo)
    elif x.cmd == "extrair":
        extrair(x.pasta, x.slug, x.alvos)
    else:
        acrescentar_bloco(x)


if __name__ == "__main__":
    main()
