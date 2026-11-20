#!/usr/bin/env python3
"""Acrescenta ao `programa.json` de um edital real um bloco que o script 50 não extrai (ex.: Conhecimentos Gerais, Língua Portuguesa).

Uso:  python -I scripts/56_acrescentar_bloco_ao_programa.py <slug> --codigo LP --disciplina "Língua Portuguesa" \
        --titulo "LÍNGUA PORTUGUESA" --inicio "LÍNGUA PORTUGUESA:" --fim "LEGISLAÇÃO DA DEFENSORIA:"

Lê o PDF do edital indicado em `programa.json`, pega o texto entre `--inicio` e `--fim` (primeira ocorrência de `--inicio` depois de
`--apos`, se dado), junta quebras de linha e palavras hifenizadas no fim da linha, divide em frases (uma por ponto final fora de
parênteses) e acrescenta a disciplina (um item sem rótulo, como o bloco de ECA). Guardrail: cada frase tem de existir igual no
texto bruto do PDF (sem espaços e hífens), senão não grava. Idempotente: substitui a disciplina de mesmo código. Não altera o banco.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def compacto(s):
    return re.sub(r"[\s\-–]+", "", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug"); ap.add_argument("--codigo", required=True); ap.add_argument("--disciplina", required=True)
    ap.add_argument("--titulo", required=True); ap.add_argument("--inicio", required=True); ap.add_argument("--fim", required=True)
    ap.add_argument("--apos", default="CONTEÚDO PROGRAMÁTICO")
    ap.add_argument("--item", type=int, default=1, help="ordem do item; com 2 ou mais, o item é acrescentado ao bloco de mesmo --codigo (ex.: dois trechos do edital numa só disciplina)")
    ap.add_argument("--rotulo", default=None, help="rótulo do item (ex.: o nome do trecho do edital)")
    a = ap.parse_args()
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
    # palavra hifenizada no fim da linha: junta sem hifen; se a parte da esquerda e sigla (2+ maiusculas, ex.: "DPE-" + "AM")
    # ou a da direita comeca em maiuscula, o hifen e do proprio nome e fica (defeito "DPEAM", 15/11/2026)
    def _junta(mt):
        esq, dir_ = mt.group(1), mt.group(2)
        return esq + "-" + dir_ if (esq.isupper() and len(esq) >= 2) or dir_[:1].isupper() else esq + dir_
    trecho = re.sub(r"(\w+)-\n(\w+)", _junta, trecho)
    trecho = re.sub(r"\s*\n\s*", " ", trecho).strip()
    frases, atual, prof = [], "", 0
    for k, ch in enumerate(trecho):
        atual += ch
        prof += ch == "("; prof -= ch == ")"
        if ch == "." and prof == 0 and trecho[k + 1:k + 2] not in ("º", "ª") and not trecho[k + 1:k + 2].isdigit():     # "n.º 01/1990" e "1.762" não encerram a frase
            frases.append(atual.strip()); atual = ""
    if atual.strip():
        frases.append(atual.strip())
    comp = compacto(texto)
    ruins = [f for f in frases if compacto(f) not in comp]
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


if __name__ == "__main__":
    main()
