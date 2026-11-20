"""Biblioteca do grupo B (Catalogar): REVISÃO do conjunto de referência (gold set) pelo usuário (modo de revisão do editor, marco M4).

Dados (pasta `dados/referencia`, sobrescrevível nos testes):
  amostra_<data>.csv            a amostra (prova;numero;disciplina;ponto_atual;assunto_atual;ano)
  leitura_ia1.json, leitura_ia2.json   leituras às cegas da IA: {"prova|numero": "código do ponto"}
  linha_de_base_classificador_v1.json  previsões do classificador por código (leitor extra, opcional)
  referencia_ouro.csv           as respostas do USUÁRIO (chave;ponto_ouro;tipo;origem;nota;data); `origem` é sempre "usuario"

FILA em duas partes (ver `montar_fila`):
  1. TODAS as questões em que o rótulo atual, a IA 1 e a IA 2 não são unânimes ("sem_maioria": os três diferentes; "maioria": dois de três).
     É enumeração completa, sem erro de amostragem.
  2. Uma AMOSTRA ALEATÓRIA das unânimes ("controle", semente fixa), para estimar quantas vezes a unanimidade erra.
Responder só a primeira parte não permite estimar a taxa de erro geral; por isso as duas partes são separadas no resumo.

ESTIMATIVA do acerto do rótulo atual na amostra (`resumo`): estratificada. Nas não unânimes conta o que o usuário respondeu (todas); nas unânimes
usa a taxa de discordância da amostra de controle (intervalo de Wilson de 95%). Enquanto houver não unânime sem resposta, é só PARCIAL.

Este módulo NUNCA grava resposta por conta própria: `registrar_resposta` é chamado pela interface, a pedido do usuário.
"""
import csv
import datetime
import json
import math
import os
import random
import re
import sqlite3
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_disciplinas as LD  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PASTA_REF = RAIZ / "dados" / "referencia"          # os testes trocam esta pasta
BANCO = RAIZ / "banco" / "estudos.db"
CAMPOS_OURO = ["chave", "ponto_ouro", "tipo", "origem", "nota", "data"]
SEMENTE_CONTROLE = 20261122
N_CONTROLE = 15
LIMITE_NOTA = 500
MIN_CONTROLE = 10          # abaixo disso a estimativa de acerto vem com aviso de amostra pequena
FONTES = {"atual": "rótulo atual", "ia1": "IA, leitura 1", "ia2": "IA, leitura 2", "cod": "classificador por código"}


class ErroRevisao(Exception):
    """Pedido inválido (mensagem em português)."""


# ---------------------------------------------------------------- leitura dos arquivos
def _pasta(pasta):
    return Path(pasta or PASTA_REF)


def _amostra(pasta):
    arqs = sorted(_pasta(pasta).glob("amostra_*.csv"))
    if not arqs:
        raise ErroRevisao("não há amostra (arquivo amostra_*.csv) na pasta de referência.")
    with open(arqs[-1], encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _chave(r):
    return f"{r['prova']}|{r['numero']}"


def _leitores(pasta):
    amostra = _amostra(pasta)
    out = {"atual": {_chave(r): r["ponto_atual"] for r in amostra}}
    for nome in ("ia1", "ia2"):
        p = _pasta(pasta) / f"leitura_{nome}.json"
        if not p.exists():
            raise ErroRevisao(f"falta a leitura da IA ({p.name}); a fila precisa das duas leituras.")
        out[nome] = json.loads(p.read_text(encoding="utf-8"))
    p = _pasta(pasta) / "linha_de_base_classificador_v1.json"
    if p.exists():
        prev = json.loads(p.read_text(encoding="utf-8")).get("previsoes", {})
        out["cod"] = {k: v["ponto"] for k, v in prev.items() if v.get("ponto")}
    return amostra, out


def classificar(atual, ia1, ia2):
    """('unanime'|'maioria'|'sem_maioria', subtipo, código da maioria). subtipo da maioria: 'atual_diverge' (as duas IA concordam entre si e
    discordam do rótulo atual) ou 'ia_dissidente' (o rótulo atual concorda com uma das IA)."""
    votos = Counter([atual, ia1, ia2])
    cod, n = votos.most_common(1)[0]
    if n == 3:
        return "unanime", None, cod
    if n == 2:
        return "maioria", ("atual_diverge" if ia1 == ia2 != atual else "ia_dissidente"), cod
    return "sem_maioria", None, None


def _ouro(pasta):
    p = _pasta(pasta) / "referencia_ouro.csv"
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return {r["chave"]: r for r in csv.DictReader(f, delimiter=";")}


def _gravar_ouro(pasta, dados):
    p = _pasta(pasta) / "referencia_ouro.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_OURO, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(dados.values())
    os.replace(tmp, p)


# ---------------------------------------------------------------- a fila
def _tipos_da_fila(pasta, n_controle, semente):
    """[(chave, tipo, subtipo, código_da_maioria)] na ordem da fila: sem_maioria, maioria (atual_diverge antes de ia_dissidente), controle."""
    amostra, L = _leitores(pasta)
    chaves = [_chave(r) for r in amostra]
    ordem = {k: i for i, k in enumerate(chaves)}
    nao, unanimes = [], []
    for k in chaves:
        tipo, sub, cod = classificar(L["atual"][k], L["ia1"][k], L["ia2"][k])
        (unanimes if tipo == "unanime" else nao).append((k, tipo, sub, cod))
    peso = {("sem_maioria", None): 0, ("maioria", "atual_diverge"): 1, ("maioria", "ia_dissidente"): 2}
    nao.sort(key=lambda x: (peso[(x[1], x[2])], ordem[x[0]]))
    sorteadas = sorted(random.Random(semente).sample(unanimes, min(n_controle, len(unanimes))), key=lambda x: ordem[x[0]])
    return nao + [(k, "controle", None, cod) for k, _, _, cod in sorteadas]


def _catalogo(con, sigla, cache):
    if sigla in cache:
        return cache[sigla]
    r = con.execute("select id from disciplinas where nome=?", (LD.nome(sigla),)).fetchone()
    lista = []
    if r:
        for cod, nome, ac, an in con.execute("select pt.codigo, pt.texto, a.codigo, a.nome from pontos pt join assuntos a on a.id=pt.assunto_id "
                                             "where pt.disciplina_id=? and pt.ativo=1 order by pt.codigo", (r[0],)):
            lista.append({"codigo": cod, "nome": nome, "assunto_codigo": ac, "assunto_nome": an})
    cache[sigla] = lista
    return lista


def montar_fila(pasta=None, banco=None, n_controle=N_CONTROLE, semente=SEMENTE_CONTROLE):
    """A fila de revisão, com o texto da questão, as opções (códigos distintos entre os leitores) e a resposta do usuário, se houver."""
    amostra, L = _leitores(pasta)
    info = {_chave(r): r for r in amostra}
    ouro = _ouro(pasta)
    banco = Path(banco or BANCO)
    con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    try:
        cache = {}
        itens = []
        for n, (k, tipo, sub, cod_m) in enumerate(_tipos_da_fila(pasta, n_controle, semente), 1):
            r = info[k]
            prova, numero = k.rsplit("|", 1)
            q = con.execute("select q.enunciado, q.alt_a, q.alt_b, q.alt_c, q.alt_d, q.alt_e, q.gabarito from questoes q join provas p on p.id=q.prova_id "
                            "where p.nome=? and q.numero=?", (prova, int(numero))).fetchone()
            cat = _catalogo(con, r["disciplina"], cache)
            por_cod = {c["codigo"]: c for c in cat}
            candidatos = {}                                      # código -> fontes, na ordem atual, ia1, ia2, (cod)
            for fonte in ("atual", "ia1", "ia2") + (("cod",) if tipo != "controle" else ()):
                c = L.get(fonte, {}).get(k)
                if c:
                    candidatos.setdefault(c, []).append(fonte)
            opcoes = []
            for i, (c, fontes) in enumerate(candidatos.items()):
                ponto = por_cod.get(c, {})
                opcoes.append({"letra": "ABCDEFGH"[i], "codigo": c, "nome": ponto.get("nome", "?"), "assunto_codigo": ponto.get("assunto_codigo"),
                               "assunto_nome": ponto.get("assunto_nome"), "fontes": fontes})
            resp = ouro.get(k)
            itens.append({"n": n, "chave": k, "tipo": tipo, "subtipo": sub, "disciplina": r["disciplina"], "prova": prova, "numero": int(numero),
                          "enunciado": q[0] if q else "(questão não encontrada no banco)",
                          "alternativas": [q[i] for i in range(1, 6)] if q else [], "gabarito": q[6] if q else None,
                          "opcoes": opcoes, "catalogo": cat,
                          "resposta": ({"ponto_ouro": resp["ponto_ouro"], "nota": resp["nota"], "data": resp["data"]} if resp else None)})
    finally:
        con.close()
    return itens


def progresso(itens):
    por = {}
    for it in itens:
        d = por.setdefault(it["tipo"], {"total": 0, "respondidas": 0})
        d["total"] += 1
        d["respondidas"] += it["resposta"] is not None
    return {"total": len(itens), "respondidas": sum(1 for it in itens if it["resposta"]), "por_tipo": por}


# ---------------------------------------------------------------- respostas
def _validar(pasta, banco, chave, n_controle, semente):
    tipos = {k: t for k, t, _, _ in _tipos_da_fila(pasta, n_controle, semente)}
    if chave not in tipos:
        raise ErroRevisao("esta questão não está na fila de revisão.")
    return tipos[chave]


def registrar_resposta(chave, ponto_ouro, nota="", pasta=None, banco=None, n_controle=N_CONTROLE, semente=SEMENTE_CONTROLE):
    """Grava a decisão do USUÁRIO. `ponto_ouro`: código de um ponto ativo da disciplina da questão, ou 'NENHUM' (a nota é obrigatória nesse caso).
    Só aceita questões da fila. Sobrescreve resposta anterior da mesma questão."""
    tipo = _validar(pasta, banco, chave, n_controle, semente)
    nota = (nota or "").strip()
    if len(nota) > LIMITE_NOTA:
        raise ErroRevisao(f"a nota passa de {LIMITE_NOTA} caracteres.")
    ponto_ouro = (ponto_ouro or "").strip()
    if ponto_ouro.upper() == "NENHUM":
        if len(nota) < 3:
            raise ErroRevisao("para \"nenhum ponto serve\", escreva uma nota curta dizendo o que falta no catálogo.")
        ponto_ouro = "NENHUM"
    else:
        amostra = {_chave(r): r for r in _amostra(pasta)}
        banco = Path(banco or BANCO)
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        try:
            validos = {c["codigo"] for c in _catalogo(con, amostra[chave]["disciplina"], {})}
        finally:
            con.close()
        if ponto_ouro not in validos:
            raise ErroRevisao(f"'{ponto_ouro}' não é um ponto ativo da disciplina desta questão.")
    ouro = _ouro(pasta)
    ouro[chave] = {"chave": chave, "ponto_ouro": ponto_ouro, "tipo": tipo, "origem": "usuario", "nota": nota, "data": datetime.date.today().isoformat()}
    _gravar_ouro(pasta, ouro)
    return ouro[chave]


def desfazer_resposta(chave, pasta=None):
    ouro = _ouro(pasta)
    if chave not in ouro:
        raise ErroRevisao("esta questão não tem resposta para desfazer.")
    del ouro[chave]
    _gravar_ouro(pasta, ouro)


# ---------------------------------------------------------------- resumo e estimativa
def wilson(k, n, z=1.96):
    """Intervalo de Wilson para uma proporção k/n; (None, None) sem dados."""
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centro - meia), min(1.0, centro + meia)


def resumo(pasta=None, banco=None, n_controle=N_CONTROLE, semente=SEMENTE_CONTROLE):
    """Quantas respostas há, como o usuário se posiciona e a estimativa de acerto do rótulo atual (estratificada)."""
    amostra, L = _leitores(pasta)
    chaves = [_chave(r) for r in amostra]
    fila = _tipos_da_fila(pasta, n_controle, semente)
    ouro = _ouro(pasta)
    n_total = len(chaves)
    n_unan = sum(1 for k in chaves if classificar(L["atual"][k], L["ia1"][k], L["ia2"][k])[0] == "unanime")
    nao = [(k, t, s, c) for k, t, s, c in fila if t != "controle"]
    ctrl = [(k, t, s, c) for k, t, s, c in fila if t == "controle"]
    por_tipo = {}
    for k, t, _, _ in fila:
        d = por_tipo.setdefault(t, {"total": 0, "respondidas": 0})
        d["total"] += 1
        d["respondidas"] += k in ouro
    # não unânimes
    nu = {"total": len(nao), "respondidas": 0, "com_atual": 0, "com_dupla_ia": 0, "outro": 0, "nenhum": 0}
    for k, t, s, c in nao:
        r = ouro.get(k)
        if not r:
            continue
        nu["respondidas"] += 1
        h = r["ponto_ouro"]
        if h == "NENHUM":
            nu["nenhum"] += 1
        elif h == L["atual"][k]:
            nu["com_atual"] += 1
        elif L["ia1"][k] == L["ia2"][k] == h:
            nu["com_dupla_ia"] += 1
        else:
            nu["outro"] += 1
    # controle
    n_c = sum(1 for k, _, _, _ in ctrl if k in ouro)
    k_c = sum(1 for k, _, _, cod in ctrl if k in ouro and ouro[k]["ponto_ouro"] != cod)
    lo, hi = wilson(k_c, n_c)
    controle = {"total": len(ctrl), "respondidas": n_c, "discordou": k_c, "taxa_discordancia": (k_c / n_c) if n_c else None,
                "ic95": [lo, hi] if n_c else None}
    # acordo do humano com cada leitor (entre respostas que não são NENHUM)
    acordo = {}
    for fonte in ("atual", "ia1", "ia2"):
        n = k = 0
        for ch, r in ouro.items():
            if r["ponto_ouro"] != "NENHUM" and ch in L[fonte]:
                n += 1
                k += r["ponto_ouro"] == L[fonte][ch]
        acordo[fonte] = {"n": n, "acordo": (k / n) if n else None}
    # estimativa estratificada do acerto do rótulo atual
    est = None
    if n_c and n_total:
        ok_nao = nu["com_atual"]
        p = k_c / n_c
        completa = nu["respondidas"] == nu["total"]
        acerto = (n_unan * (1 - p) + ok_nao) / n_total
        lo_a = (n_unan * (1 - hi) + ok_nao) / n_total
        hi_a = (n_unan * (1 - lo) + ok_nao) / n_total
        avisos = []
        if not completa:
            avisos.append("PARCIAL: ainda há questões não unânimes sem resposta; os acertos delas contam como erro do rótulo atual.")
        if n_c < MIN_CONTROLE:
            avisos.append(f"Amostra de controle pequena ({n_c} respondidas; o ideal é {MIN_CONTROLE} ou mais): o intervalo é muito largo e a estimativa pontual "
                          "não é confiável.")
        est = {"completa": completa, "acerto_rotulo_atual": acerto, "ic95": [lo_a, hi_a], "questoes_da_amostra": n_total, "unanimes": n_unan,
               "controle_respondidas": n_c, "aviso": " ".join(avisos) or None}
    return {"fila": progresso([{"tipo": t, "resposta": ouro.get(k)} for k, t, _, _ in fila]), "por_tipo": por_tipo, "nao_unanimes": nu, "controle": controle,
            "acordo_humano": acordo, "estimativa": est}
