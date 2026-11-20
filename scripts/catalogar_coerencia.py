#!/usr/bin/env python3
"""Grupo B (Catalogar): diagnóstico de COERÊNCIA ESTRUTURAL do catálogo (só leitura; não usa banco nem questões).

Uso (sempre com `python -I`):
  python -I scripts/catalogar_coerencia.py DISCIPLINA [--rascunho]
    DISCIPLINA = nome do arquivo em dados/catalogo, sem .json (ex.: direito-penal)
    --rascunho = lê dados/catalogo/_rascunho_<DISCIPLINA>_v2.json (o v2 do editor) em vez do catálogo v1

Aplica a seção 10 do docs/01-METODO.md. É triagem por palavras: um aviso é pergunta para o usuário, não erro provado.
Verificações:
  1. Assunto com um tópico só (ou nenhum): rebaixar a tópico de um vizinho.
  2. Assunto-gaveta: tópicos com pouca palavra em comum entre si (e vários tópicos): dividir.
  3. Nomes repetidos ou muito parecidos (entre tópicos da disciplina, e entre assuntos).
  4. Nome (de assunto ou tópico) com "e" ou vírgula que junta ideias; "e outros"; "geral" sozinho.
  5. Mesmo conteúdo em dois tópicos: descrições muito parecidas entre tópicos de assuntos diferentes (ou do mesmo).
"""
import itertools
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAT = RAIZ / "dados" / "catalogo"
STOP = set("de da do das dos a o as os e em no na nos nas que para por com um uma ao se ou sao ser como mais sua seu pela pelo sobre entre ate art lei ".split())
LIM_NOME = 0.7      # parecença dos nomes (maior entre Jaccard e contenção) para "muito parecidos"
LIM_DESC = 0.4      # Jaccard das descrições para "mesmo conteúdo"
LIM_GAVETA = 0.06   # coesão média abaixo disso, com 5+ tópicos, sugere gaveta
MIN_GAVETA = 5


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


MARCA = re.compile(r"\[tema compartilhado com [^\]]*\]")   # a marca de tema interdisciplinar (decisão 55) não conta como conteúdo


def toks(s):
    return {w for w in re.findall(r"[a-z]{3,}", MARCA.sub(" ", norm(s))) if w not in STOP}


def cont(a, b):
    """Fração do menor conjunto contida no outro (pega "lei penal no tempo" dentro de "lei penal no espaço, tempo e lugar")."""
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def jac(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def carregar(slug, rascunho):
    """Devolve lista de assuntos [{codigo, nome, topicos:[{codigo, nome, desc}]}], nos dois formatos."""
    if rascunho:
        d = json.loads((CAT / f"_rascunho_{slug}_v2.json").read_text(encoding="utf-8"))
        out = []
        for i, a in enumerate(d["assuntos"], 1):
            out.append({"codigo": a.get("antigo") or f"novo{i}", "nome": a["nome"],
                        "topicos": [{"codigo": p.get("antigo") or p["uid"], "nome": p["texto"], "desc": p.get("descricao") or ""} for p in a.get("pontos", [])]})
        return out
    d = json.loads((CAT / f"{slug}.json").read_text(encoding="utf-8"))
    por = {}
    for p in d["pontos"]:
        if p.get("ativo", 1):
            por.setdefault(p["assunto"], []).append({"codigo": p["codigo"], "nome": p["texto"], "desc": p.get("descricao") or ""})
    return [{"codigo": a["codigo"], "nome": a["nome"], "topicos": por.get(a["codigo"], [])} for a in d["assuntos"]]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    slug, rasc = args[0], "--rascunho" in sys.argv
    ass = carregar(slug, rasc)
    topicos = [(a, t) for a in ass for t in a["topicos"]]
    print(f"== COERÊNCIA ESTRUTURAL: {slug} ({'rascunho v2' if rasc else 'catálogo v1'}): {len(ass)} assuntos, {len(topicos)} tópicos (sem usar questões)\n")
    n = 0

    print("-- 1. Assuntos com um tópico só (ou nenhum)")
    for a in ass:
        if len(a["topicos"]) <= 1:
            n += 1
            print(f"   {a['codigo']} '{a['nome']}': {len(a['topicos'])} tópico(s)")

    print("\n-- 2. Possíveis assuntos-gaveta (tópicos com pouca palavra em comum)")
    for a in ass:
        ts = a["topicos"]
        if len(ts) < MIN_GAVETA:
            continue
        bag = [toks(t["nome"] + " " + t["desc"]) for t in ts]
        media = sum(jac(x, y) for x, y in itertools.combinations(bag, 2)) / (len(ts) * (len(ts) - 1) / 2)
        if media < LIM_GAVETA:
            n += 1
            print(f"   {a['codigo']} '{a['nome']}': {len(ts)} tópicos, coesão {media:.3f} (corte {LIM_GAVETA})")

    print("\n-- 3. Nomes repetidos ou muito parecidos")
    nomes = [(a["codigo"], "assunto", a["nome"]) for a in ass] + [(t["codigo"], "tópico", t["nome"]) for _, t in topicos]
    for (c1, k1, n1), (c2, k2, n2) in itertools.combinations(nomes, 2):
        if k1 != k2:
            continue
        a1, a2 = toks(n1), toks(n2)
        j = max(jac(a1, a2), cont(a1, a2) if min(len(a1), len(a2)) >= 2 else 0)
        if j >= LIM_NOME or norm(n1) == norm(n2):
            n += 1
            print(f"   {c1} '{n1}'  ~  {c2} '{n2}' (parecença {j:.2f})")

    print("\n-- 4. Nomes que juntam ideias ('e', vírgula), 'e outros' ou 'geral' sozinho")
    for cod, k, nome in nomes:
        x = norm(nome)
        motivos = []
        if re.search(r"\be outros?\b", x):
            motivos.append("'e outros'")
        if re.fullmatch(r"\W*(geral|gerais|disposicoes gerais)\W*", x):
            motivos.append("'geral' sozinho")
        partes = len(re.split(r"\s+e\s+|,", x))
        if partes >= (2 if k == "assunto" else 3) and not motivos:
            motivos.append(f"junta {partes} ideias")
        if motivos:
            n += 1
            print(f"   {cod} ({k}) '{nome}': {', '.join(motivos)}")

    print("\n-- 5. Mesmo conteúdo em dois tópicos (descrições muito parecidas)")
    for (a1, t1), (a2, t2) in itertools.combinations(topicos, 2):
        j = jac(toks(t1["nome"] + " " + t1["desc"]), toks(t2["nome"] + " " + t2["desc"]))
        if j >= LIM_DESC:
            n += 1
            onde = "mesmo assunto" if a1 is a2 else f"{a1['codigo']} e {a2['codigo']}"
            print(f"   {t1['codigo']} '{t1['nome'][:45]}'  ~  {t2['codigo']} '{t2['nome'][:45]}' ({onde}; {j:.2f})")

    print(f"\n-> {n} aviso(s). Triagem por palavras: o usuário decide; nada foi alterado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
