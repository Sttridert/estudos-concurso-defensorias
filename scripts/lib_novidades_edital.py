"""GRUPO F (Produzir): o que há de NOVO num edital em relação aos editais anteriores do mesmo cargo e órgão (seção "O que há de novo neste edital").

A comparação é pelo TEXTO literal das frases do programa (`dados/editais_reais/<slug>/programa.json`, feito pelo `coletar_programa_edital.py`),
não pelos tópicos do catálogo (só os editais mais recentes foram classificados). Compara-se frase com frase, sem olhar acento, caixa nem pontuação:
  igual a alguma frase dos editais anteriores     -> não é novidade (não aparece)
  parecida (razão >= LIMIAR) com alguma anterior   -> "reescrita" (ex.: a Lei 14.133/2021 no lugar da Lei 8.666/93)
  sem parecida                                      -> "nova"
O que SAIU do edital não é calculado nem mostrado (decisão do usuário, 20/11/2026).

  carregar_programa(slug)            -> {"ano", "nome", "blocos": {sigla: [(rótulo, frase)]}}
  comparar(atuais, anteriores)       -> [{"rotulo", "texto", "situacao"}]   (atuais: [(rótulo, frase)]; anteriores: [[frase]], uma lista por edital)
"""
import difflib
import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LIMIAR = 0.75
NOVA, REESCRITA = "nova", "reescrita"


def normalizar(texto):
    t = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def arquivo_programa(slug):
    return RAIZ / "dados" / "editais_reais" / slug / "programa.json"


def carregar_programa(slug):
    """programa literal de um edital: blocos por sigla, cada um com a lista (rótulo do item, frase) na ordem do edital"""
    d = json.loads(arquivo_programa(slug).read_text(encoding="utf-8"))
    blocos = {x["codigo"]: [(i.get("rotulo") or "s/n", f["texto"]) for i in x["itens"] for f in i["frases"]] for x in d["disciplinas"]}
    ed = d.get("edital") or {}
    return {"ano": ed.get("ano"), "nome": ed.get("nome") or slug, "blocos": blocos}


def comparar(atuais, anteriores, limiar=LIMIAR):
    """frases de `atuais` que não existem (iguais) em nenhum edital anterior, com a situação 'nova' ou 'reescrita'"""
    antes = {normalizar(t) for lista in anteriores for t in lista}
    antes.discard("")
    lista_antes = sorted(antes)
    out = []
    for rotulo, texto in atuais:
        n = normalizar(texto)
        if not n or n in antes:
            continue
        parecida = difflib.get_close_matches(n, lista_antes, n=1, cutoff=limiar)
        out.append({"rotulo": rotulo, "texto": texto, "situacao": REESCRITA if parecida else NOVA})
    return out
