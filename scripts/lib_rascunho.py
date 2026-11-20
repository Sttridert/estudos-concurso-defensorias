"""Biblioteca do grupo B (Catalogar): modelo do RASCUNHO v2 do catálogo e as operações do editor visual (sem HTTP; testável).

O editor mexe só em um rascunho (arquivo), nunca no banco. O rascunho fica em `dados/catalogo/_rascunho_<disciplina>_v2.json` (o `_` impede que
o `71 aplicar` o trate como catálogo). Publicar o v2 é outra etapa (junto com a Fase 3) e passa pelo `71` e pelo estado do catálogo.

Modelo (aninhado; a ORDEM das listas é a ordem didática):
  assuntos: [ {uid, antigo, nome, descricao, pre_requisito, pontos: [ {uid, antigo, texto, descricao, origem} ]} ]
  lixeira: pontos apagados {uid, antigo, texto, descricao, assunto_uid, apagado_em, destino}   (destino = ponto que recebe as questões, ou null)
  lixeira_assuntos: assuntos apagados ou rebaixados {uid, antigo, nome, descricao, apagado_em, rebaixado_para}
  base_v1: cópia imutável do catálogo v1 (para o mapa antigo→novo)
  historico: {passado: [...], futuro: [...]}   (desfazer e refazer; guarda as listas acima)

IDENTIDADE: cada assunto e ponto tem um `uid` permanente. Os do v1 são `v1:<código antigo>`; os novos são `n:<8 hex>`. O CÓDIGO mostrado é
recalculado pela POSIÇÃO (`<prefixo><aa>.<pp>`), então arrastar um bloco muda o código sem perder a identidade. O mapa antigo→novo sai dos uids.

Operações (`aplicar_op`): mover_ponto, mover_assunto, editar_ponto, editar_assunto, novo_ponto, novo_assunto, apagar_ponto, restaurar_ponto,
apagar_assunto, restaurar_assunto, rebaixar_assunto, desfazer, refazer. Regra de segurança: apagar ponto que tem questões classificadas exige
`destino` (o ponto que as recebe); nada é apagado do banco (e o editor nem toca no banco).
"""
import copy
import csv
import datetime
import json
import os
import re
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalogar_diagnostico import PEQ_PONTOS, PEQ_PCT, GRANDE_PONTOS, GRANDE_PCT  # noqa: E402  (cortes do contrato, iguais aos do diagnóstico)
from catalogar_diagnostico import spearman  # noqa: E402
import statistics as st  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "dados" / "catalogo"          # os testes trocam esta pasta
BANCO = RAIZ / "banco" / "estudos.db"
LIMITE_HISTORICO = 100
CONTRATO = {"assuntos_min": 8, "assuntos_max": 15, "pontos_min": 3, "pontos_max": GRANDE_PONTOS,
            "peq_pontos": PEQ_PONTOS, "peq_pct": PEQ_PCT, "grande_pct": GRANDE_PCT, "evid_questoes": 3, "evid_itens": 5}


class ErroOp(Exception):
    """Operação inválida (mensagem em português, mostrada ao usuário)."""


# ---------------------------------------------------------------- arquivo
def arquivo(slug):
    return Path(PASTA) / f"_rascunho_{slug}_v2.json"


def existe(slug):
    return arquivo(slug).exists()


def carregar(slug):
    if not existe(slug):
        raise ErroOp(f"não há rascunho de '{slug}'. Crie a partir do catálogo atual.")
    return json.loads(arquivo(slug).read_text(encoding="utf-8"))


def salvar(d):
    """Grava com troca atômica e guarda a versão anterior como `.bak`."""
    d["atualizado_em"] = datetime.datetime.now().isoformat(timespec="seconds")
    alvo = arquivo(d["slug"])
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if alvo.exists():
        alvo.with_suffix(".bak").write_bytes(alvo.read_bytes())
    fd, tmp = tempfile.mkstemp(dir=str(alvo.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, alvo)


def catalogos_disponiveis():
    """[{slug, disciplina, tem_rascunho}] dos catálogos v1 (arquivos de `dados/catalogo` sem `_`)."""
    out = []
    for p in sorted(Path(PASTA).glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            nome = json.loads(p.read_text(encoding="utf-8"))["disciplina"]
        except Exception:
            continue
        out.append({"slug": p.stem, "disciplina": nome, "tem_rascunho": existe(p.stem)})
    return out


# ---------------------------------------------------------------- criação a partir do v1
def criar_de_v1(slug, sobrescrever=False):
    """Cria o rascunho v2 como cópia do catálogo v1 (arquivo `dados/catalogo/<slug>.json`). Não sobrescreve sem pedir."""
    if existe(slug) and not sobrescrever:
        raise ErroOp(f"já existe rascunho de '{slug}'.")
    fonte = Path(PASTA) / f"{slug}.json"
    if not fonte.exists():
        raise ErroOp(f"não há catálogo v1 '{slug}'.")
    v1 = json.loads(fonte.read_text(encoding="utf-8"))
    m = re.match(r"[A-Za-z]+", v1["assuntos"][0]["codigo"])
    prefixo = m.group(0) if m else "X"
    assuntos, base_ass, base_pts = [], {}, {}
    por_assunto = {a["codigo"]: [] for a in v1["assuntos"]}
    for p in v1["pontos"]:
        if p.get("ativo", 1) and p["assunto"] in por_assunto:
            por_assunto[p["assunto"]].append(p)
    for a in sorted(v1["assuntos"], key=lambda x: x["codigo"]):
        auid = "v1:" + a["codigo"]
        pontos = []
        for p in sorted(por_assunto[a["codigo"]], key=lambda x: x["codigo"]):
            puid = "v1:" + p["codigo"]
            pontos.append({"uid": puid, "antigo": p["codigo"], "texto": p["texto"], "descricao": p.get("descricao"), "origem": p.get("origem")})
            base_pts[puid] = {"codigo": p["codigo"], "texto": p["texto"], "assunto_uid": auid}
        assuntos.append({"uid": auid, "antigo": a["codigo"], "nome": a["nome"], "descricao": a.get("descricao"), "pre_requisito": None, "pontos": pontos})
        base_ass[auid] = {"codigo": a["codigo"], "nome": a["nome"]}
    d = {"slug": slug, "disciplina": v1["disciplina"], "prefixo": prefixo, "versao_base": "v1", "versao_alvo": "v2",
         "criado_em": datetime.datetime.now().isoformat(timespec="seconds"), "estado": "rascunho",
         "assuntos": assuntos, "lixeira": [], "lixeira_assuntos": [], "base_v1": {"assuntos": base_ass, "pontos": base_pts},
         "historico": {"passado": [], "futuro": []}}
    salvar(d)
    return d


# ---------------------------------------------------------------- códigos pela posição
def codigos(d):
    """{uid: código} de assuntos e pontos, pela posição atual (assunto e ponto numerados a partir de 1)."""
    out = {}
    for ai, a in enumerate(d["assuntos"], 1):
        out[a["uid"]] = f"{d['prefixo']}{ai:02d}"
        for pi, p in enumerate(a["pontos"], 1):
            out[p["uid"]] = f"{d['prefixo']}{ai:02d}.{pi:02d}"
    return out


def achar_assunto(d, uid):
    for i, a in enumerate(d["assuntos"]):
        if a["uid"] == uid:
            return i, a
    raise ErroOp(f"assunto '{uid}' não encontrado.")


def achar_ponto(d, uid):
    for a in d["assuntos"]:
        for i, p in enumerate(a["pontos"]):
            if p["uid"] == uid:
                return a, i, p
    raise ErroOp(f"ponto '{uid}' não encontrado (ou está na lixeira).")


def _na_lixeira(d, uid):
    for i, p in enumerate(d["lixeira"]):
        if p["uid"] == uid:
            return i, p
    raise ErroOp(f"ponto '{uid}' não está na lixeira.")


def _limitar(i, n):
    if i is None:
        return n
    return max(0, min(int(i), n))


def _texto(v, campo):
    v = (v or "").strip()
    if not v:
        raise ErroOp(f"{campo} não pode ficar vazio.")
    return v


# ---------------------------------------------------------------- contagens (só leitura do banco)
def contar(codigos_antigos, banco=None):
    """{código antigo do ponto: (questões classificadas, itens de edital ligados)}; só leitura do banco."""
    banco = Path(banco or BANCO)
    out = {c: (0, 0) for c in codigos_antigos}
    if not codigos_antigos or not banco.exists():
        return out
    con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    try:
        for c in codigos_antigos:
            r = con.execute("select id from pontos where codigo=?", (c,)).fetchone()
            if not r:
                continue
            q = con.execute("select count(*) from classificacao where ponto_id=?", (r[0],)).fetchone()[0]
            i = con.execute("select count(distinct item_id) from edital_item_pontos where ponto_id=?", (r[0],)).fetchone()[0]
            out[c] = (q, i)
    finally:
        con.close()
    return out


def _antigos(d):
    cods = {p["antigo"] for a in d["assuntos"] for p in a["pontos"] if p.get("antigo")}
    cods |= {p["antigo"] for p in d["lixeira"] if p.get("antigo")}
    return cods


def _destino_final(d, uid):
    """Segue a cadeia de destinos da lixeira até um ponto que está nos assuntos; None se não houver."""
    vistos = set()
    por_uid = {p["uid"]: p for p in d["lixeira"]}
    while uid in por_uid and uid not in vistos:
        vistos.add(uid)
        uid = por_uid[uid].get("destino")
        if uid is None:
            return None
    return uid if uid and uid not in por_uid else None


def contagens_efetivas(d, banco=None, cont=None):
    """{uid do ponto: (questões, itens)} contando também o que foi fundido nele (pontos da lixeira com `destino`)."""
    cont = cont if cont is not None else contar(_antigos(d), banco)
    ef = {}
    for a in d["assuntos"]:
        for p in a["pontos"]:
            ef[p["uid"]] = list(cont.get(p.get("antigo"), (0, 0)))
    for p in d["lixeira"]:
        alvo = _destino_final(d, p["uid"])
        if alvo in ef:
            q, i = cont.get(p.get("antigo"), (0, 0))
            ef[alvo][0] += q
            ef[alvo][1] += i
    return {k: tuple(v) for k, v in ef.items()}


# ---------------------------------------------------------------- operações
def _snap(d):
    return {k: copy.deepcopy(d[k]) for k in ("assuntos", "lixeira", "lixeira_assuntos")}


def _restaurar_snap(d, s):
    for k in ("assuntos", "lixeira", "lixeira_assuntos"):
        d[k] = copy.deepcopy(s[k])


def _novo_uid():
    return "n:" + uuid.uuid4().hex[:8]


def _agora():
    return datetime.datetime.now().isoformat(timespec="seconds")


def op_mover_ponto(d, op, ctx):
    a0, i, p = achar_ponto(d, op["uid"])
    _, destino = achar_assunto(d, op["para_assunto"])
    a0["pontos"].pop(i)
    destino["pontos"].insert(_limitar(op.get("indice"), len(destino["pontos"])), p)


def op_mover_assunto(d, op, ctx):
    i, a = achar_assunto(d, op["uid"])
    d["assuntos"].pop(i)
    d["assuntos"].insert(_limitar(op.get("indice"), len(d["assuntos"])), a)


def op_editar_ponto(d, op, ctx):
    _, _, p = achar_ponto(d, op["uid"])
    if "texto" in op:
        p["texto"] = _texto(op["texto"], "o nome do ponto")
    if "descricao" in op:
        p["descricao"] = (op["descricao"] or "").strip() or None


def op_editar_assunto(d, op, ctx):
    _, a = achar_assunto(d, op["uid"])
    if "nome" in op:
        a["nome"] = _texto(op["nome"], "o nome do assunto")
    if "descricao" in op:
        a["descricao"] = (op["descricao"] or "").strip() or None
    if "pre_requisito" in op:
        pr = op["pre_requisito"] or None
        if pr:
            achar_assunto(d, pr)
            if pr == a["uid"]:
                raise ErroOp("um assunto não pode ser pré-requisito de si mesmo.")
        a["pre_requisito"] = pr


def op_novo_ponto(d, op, ctx):
    _, a = achar_assunto(d, op["assunto"])
    p = {"uid": _novo_uid(), "antigo": None, "texto": _texto(op.get("texto"), "o nome do ponto"), "descricao": (op.get("descricao") or "").strip() or None,
         "origem": "criado no editor"}
    a["pontos"].insert(_limitar(op.get("indice"), len(a["pontos"])), p)


def op_novo_assunto(d, op, ctx):
    a = {"uid": _novo_uid(), "antigo": None, "nome": _texto(op.get("nome"), "o nome do assunto"), "descricao": (op.get("descricao") or "").strip() or None,
         "pre_requisito": None, "pontos": []}
    d["assuntos"].insert(_limitar(op.get("indice"), len(d["assuntos"])), a)


def op_apagar_ponto(d, op, ctx):
    a, i, p = achar_ponto(d, op["uid"])
    destino = op.get("destino") or None
    if destino:
        if destino == p["uid"]:
            raise ErroOp("o destino não pode ser o próprio ponto.")
        achar_ponto(d, destino)                      # tem de estar nos assuntos
    q = ctx["efetivas"].get(p["uid"], (0, 0))[0]
    if q > 0 and not destino:
        raise ErroOp(f"este ponto tem {q} questões classificadas: escolha o ponto que as recebe (destino) ou mova o bloco em vez de apagar.")
    a["pontos"].pop(i)
    for outro in d["lixeira"]:                       # quem foi fundido neste ponto passa a apontar para o novo destino
        if outro.get("destino") == p["uid"]:
            outro["destino"] = destino
    d["lixeira"].append({"uid": p["uid"], "antigo": p.get("antigo"), "texto": p["texto"], "descricao": p.get("descricao"),
                         "assunto_uid": a["uid"], "apagado_em": _agora(), "destino": destino})


def op_restaurar_ponto(d, op, ctx):
    i, p = _na_lixeira(d, op["uid"])
    _, a = achar_assunto(d, op["assunto"])
    d["lixeira"].pop(i)
    a["pontos"].insert(_limitar(op.get("indice"), len(a["pontos"])),
                       {"uid": p["uid"], "antigo": p.get("antigo"), "texto": p["texto"], "descricao": p.get("descricao"), "origem": "restaurado da lixeira"})


def op_apagar_assunto(d, op, ctx):
    i, a = achar_assunto(d, op["uid"])
    if a["pontos"]:
        raise ErroOp("o assunto ainda tem pontos: mova-os, apague-os ou use 'rebaixar a ponto'.")
    d["assuntos"].pop(i)
    d["lixeira_assuntos"].append({"uid": a["uid"], "antigo": a.get("antigo"), "nome": a["nome"], "descricao": a.get("descricao"),
                                  "apagado_em": _agora(), "rebaixado_para": None})
    for outro in d["assuntos"]:
        if outro.get("pre_requisito") == a["uid"]:
            outro["pre_requisito"] = None


def op_restaurar_assunto(d, op, ctx):
    for i, a in enumerate(d["lixeira_assuntos"]):
        if a["uid"] == op["uid"]:
            if a.get("rebaixado_para"):
                raise ErroOp("este assunto foi rebaixado a ponto; desfaça a operação em vez de restaurar.")
            d["lixeira_assuntos"].pop(i)
            d["assuntos"].insert(_limitar(op.get("indice"), len(d["assuntos"])),
                                 {"uid": a["uid"], "antigo": a.get("antigo"), "nome": a["nome"], "descricao": a.get("descricao"), "pre_requisito": None, "pontos": []})
            return
    raise ErroOp("assunto não está na lixeira.")


def op_rebaixar_assunto(d, op, ctx):
    """Assunto pequeno vira um ponto de outro assunto; os pontos dele são fundidos no novo ponto."""
    i, a = achar_assunto(d, op["uid"])
    if op["para_assunto"] == a["uid"]:
        raise ErroOp("escolha outro assunto como destino.")
    _, alvo = achar_assunto(d, op["para_assunto"])
    novo = {"uid": _novo_uid(), "antigo": None, "texto": a["nome"], "descricao": a.get("descricao"), "origem": f"assunto {a.get('antigo') or a['uid']} rebaixado a ponto"}
    alvo["pontos"].insert(_limitar(op.get("indice"), len(alvo["pontos"])), novo)
    for p in a["pontos"]:
        d["lixeira"].append({"uid": p["uid"], "antigo": p.get("antigo"), "texto": p["texto"], "descricao": p.get("descricao"),
                             "assunto_uid": a["uid"], "apagado_em": _agora(), "destino": novo["uid"]})
    d["assuntos"].pop(i)
    d["lixeira_assuntos"].append({"uid": a["uid"], "antigo": a.get("antigo"), "nome": a["nome"], "descricao": a.get("descricao"),
                                  "apagado_em": _agora(), "rebaixado_para": novo["uid"]})
    for outro in d["assuntos"]:
        if outro.get("pre_requisito") == a["uid"]:
            outro["pre_requisito"] = None


OPERACOES = {"mover_ponto": op_mover_ponto, "mover_assunto": op_mover_assunto, "editar_ponto": op_editar_ponto, "editar_assunto": op_editar_assunto,
             "novo_ponto": op_novo_ponto, "novo_assunto": op_novo_assunto, "apagar_ponto": op_apagar_ponto, "restaurar_ponto": op_restaurar_ponto,
             "apagar_assunto": op_apagar_assunto, "restaurar_assunto": op_restaurar_assunto, "rebaixar_assunto": op_rebaixar_assunto}


def aplicar_op(slug, op, banco=None):
    """Aplica uma operação ao rascunho, guarda o histórico e grava. Devolve o rascunho novo."""
    d = carregar(slug)
    nome = op.get("op")
    h = d.setdefault("historico", {"passado": [], "futuro": []})
    if nome == "desfazer":
        if not h["passado"]:
            raise ErroOp("nada para desfazer.")
        h["futuro"].append(_snap(d))
        _restaurar_snap(d, h["passado"].pop())
        salvar(d)
        return d
    if nome == "refazer":
        if not h["futuro"]:
            raise ErroOp("nada para refazer.")
        h["passado"].append(_snap(d))
        _restaurar_snap(d, h["futuro"].pop())
        salvar(d)
        return d
    if nome not in OPERACOES:
        raise ErroOp(f"operação desconhecida: {nome!r}.")
    antes = _snap(d)
    ctx = {"efetivas": contagens_efetivas(d, banco)}
    try:
        OPERACOES[nome](d, op, ctx)
    except KeyError as e:
        raise ErroOp(f"falta o campo {e} na operação {nome}.")
    h["passado"].append(antes)
    h["passado"] = h["passado"][-LIMITE_HISTORICO:]
    h["futuro"] = []
    salvar(d)
    return d


# ---------------------------------------------------------------- visão, diagnóstico e mapa
def diagnostico(d, banco=None, cont=None):
    """Números do contrato ao vivo: assuntos pequenos e grandes, pontos por assunto, pontos sem evidência."""
    cont = cont if cont is not None else contar(_antigos(d), banco)
    ef = contagens_efetivas(d, banco, cont)
    cods = codigos(d)
    tq = sum(q for q, _ in ef.values()) or 1
    ti = sum(i for _, i in ef.values()) or 1
    por_assunto, avisos, sem_evid = [], [], []
    for a in d["assuntos"]:
        q = sum(ef.get(p["uid"], (0, 0))[0] for p in a["pontos"])
        i = sum(ef.get(p["uid"], (0, 0))[1] for p in a["pontos"])
        pq, pi = 100 * q / tq, 100 * i / ti
        n = len(a["pontos"])
        flags = []
        if n <= CONTRATO["peq_pontos"] or (pq < CONTRATO["peq_pct"] and pi < CONTRATO["peq_pct"]):
            flags.append("pequeno")
        if n > CONTRATO["pontos_max"] or pq > CONTRATO["grande_pct"] or pi > CONTRATO["grande_pct"]:
            flags.append("grande")
        por_assunto.append({"uid": a["uid"], "codigo": cods[a["uid"]], "nome": a["nome"], "pontos": n, "questoes": q, "itens": i,
                            "pct_questoes": round(pq, 1), "pct_itens": round(pi, 1), "flags": flags})
        for p in a["pontos"]:
            qq, ii = ef.get(p["uid"], (0, 0))
            if p.get("antigo") and qq < CONTRATO["evid_questoes"] and ii < CONTRATO["evid_itens"]:
                sem_evid.append(p["uid"])
    na = len(d["assuntos"])
    if not CONTRATO["assuntos_min"] <= na <= CONTRATO["assuntos_max"]:
        avisos.append(f"{na} assuntos; o contrato pede de {CONTRATO['assuntos_min']} a {CONTRATO['assuntos_max']}.")
    return {"assuntos": na, "pontos": sum(len(a["pontos"]) for a in d["assuntos"]), "por_assunto": por_assunto, "pontos_sem_evidencia": sem_evid, "avisos": avisos,
            "pequenos": sum("pequeno" in x["flags"] for x in por_assunto), "grandes": sum("grande" in x["flags"] for x in por_assunto)}


def visao(d, banco=None):
    """O que a interface precisa: o rascunho com códigos calculados, contagens por ponto, diagnóstico e estado do histórico."""
    cont = contar(_antigos(d), banco)
    ef = contagens_efetivas(d, banco, cont)
    cods = codigos(d)
    v = {k: d[k] for k in ("slug", "disciplina", "prefixo", "versao_base", "versao_alvo", "estado", "atualizado_em")}
    acoes = {m["uid"]: m for m in mapa(d)}
    ordem = ordem_didatica(d, banco)
    v["ordem"] = {"rho": ordem["rho"], "assuntos_com_dados": ordem["assuntos_com_dados"]}
    v["assuntos"] = [{"uid": a["uid"], "codigo": cods[a["uid"]], "antigo": a.get("antigo"), "nome": a["nome"], "descricao": a.get("descricao"),
                      "pre_requisito": a.get("pre_requisito"), "acao": acoes.get(a["uid"], {}).get("acao", "mantido"),
                      "ordem": ordem["por_assunto"].get(a["uid"]),
                      "pontos": [{"uid": p["uid"], "codigo": cods[p["uid"]], "antigo": p.get("antigo"), "texto": p["texto"], "descricao": p.get("descricao"),
                                  "questoes": ef.get(p["uid"], (0, 0))[0], "itens": ef.get(p["uid"], (0, 0))[1], "novo": not p.get("antigo"),
                                  "acao": acoes.get(p["uid"], {}).get("acao", "mantido"),
                                  "texto_antigo": acoes.get(p["uid"], {}).get("texto_antigo") if "renomeado" in acoes.get(p["uid"], {}).get("acao", "") else None}
                                 for p in a["pontos"]]} for a in d["assuntos"]]
    v["lixeira"] = [{"uid": p["uid"], "antigo": p.get("antigo"), "texto": p["texto"], "destino": p.get("destino"), "assunto_uid": p.get("assunto_uid"),
                     "destino_codigo": cods.get(_destino_final(d, p["uid"]) or "")} for p in d["lixeira"]]
    v["lixeira_assuntos"] = d["lixeira_assuntos"]
    v["diagnostico"] = diagnostico(d, banco, cont)
    v["pode_desfazer"] = bool(d["historico"]["passado"])
    v["pode_refazer"] = bool(d["historico"]["futuro"])
    return v


def mapa(d):
    """Mapa antigo→novo (por uid): uma linha por assunto e ponto do v1 e por item novo. `uid` identifica o item no rascunho."""
    cods = codigos(d)
    base = d["base_v1"]
    linhas = []
    ass_atual = {a["uid"]: a for a in d["assuntos"]}
    pt_atual = {p["uid"]: (a, p) for a in d["assuntos"] for p in a["pontos"]}
    lixa = {a["uid"]: a for a in d["lixeira_assuntos"]}
    for uid, b in base["assuntos"].items():
        if uid in ass_atual:
            a = ass_atual[uid]
            acao = "renomeado" if a["nome"] != b["nome"] else ("mantido" if cods[uid] == b["codigo"] else "renumerado")
            linhas.append({"uid": uid, "tipo": "assunto", "antigo": b["codigo"], "novo": cods[uid], "acao": acao, "destino": "", "texto_antigo": b["nome"], "texto_novo": a["nome"]})
        else:
            la = lixa.get(uid, {})
            alvo = la.get("rebaixado_para")
            linhas.append({"uid": uid, "tipo": "assunto", "antigo": b["codigo"], "novo": "", "acao": "rebaixado a ponto" if alvo else "apagado",
                           "destino": cods.get(alvo, "") if alvo else "", "texto_antigo": b["nome"], "texto_novo": ""})
    for uid, b in base["pontos"].items():
        if uid in pt_atual:
            a, p = pt_atual[uid]
            mudou_pai, mudou_texto = a["uid"] != b["assunto_uid"], p["texto"] != b["texto"]
            if mudou_pai and mudou_texto:
                acao = "movido e renomeado"
            elif mudou_pai:
                acao = "movido"
            elif mudou_texto:
                acao = "renomeado"
            else:
                acao = "mantido" if cods[uid] == b["codigo"] else "renumerado"
            linhas.append({"uid": uid, "tipo": "ponto", "antigo": b["codigo"], "novo": cods[uid], "acao": acao, "destino": "", "texto_antigo": b["texto"], "texto_novo": p["texto"]})
        else:
            alvo = _destino_final(d, uid)
            linhas.append({"uid": uid, "tipo": "ponto", "antigo": b["codigo"], "novo": "", "acao": "fundido" if alvo else "apagado", "destino": cods.get(alvo, "") if alvo else "",
                           "texto_antigo": b["texto"], "texto_novo": ""})
    for a in d["assuntos"]:
        if not a.get("antigo"):
            linhas.append({"uid": a["uid"], "tipo": "assunto", "antigo": "", "novo": cods[a["uid"]], "acao": "novo", "destino": "", "texto_antigo": "", "texto_novo": a["nome"]})
        for p in a["pontos"]:
            if not p.get("antigo"):
                linhas.append({"uid": p["uid"], "tipo": "ponto", "antigo": "", "novo": cods[p["uid"]], "acao": "novo", "destino": "", "texto_antigo": "", "texto_novo": p["texto"]})
    return linhas


def exportar_mapa(d):
    """Grava `_mapa_<slug>_v1_v2.csv` (separador ;) e devolve o caminho."""
    arq = Path(PASTA) / f"_mapa_{d['slug']}_v1_v2.csv"
    linhas = mapa(d)
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["tipo", "antigo", "novo", "acao", "destino", "texto_antigo", "texto_novo"], delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
    return arq


def questoes_do_ponto(d, uid, banco=None, limite=40):
    """Questões já classificadas (no v1) no ponto e no que foi fundido nele: [{prova, numero, trecho}]. Só leitura do banco."""
    banco = Path(banco or BANCO)
    antigos = []
    _, _, p = achar_ponto(d, uid)
    if p.get("antigo"):
        antigos.append(p["antigo"])
    for outro in d["lixeira"]:
        if _destino_final(d, outro["uid"]) == uid and outro.get("antigo"):
            antigos.append(outro["antigo"])
    if not antigos or not banco.exists():
        return []
    con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    try:
        marcas = ",".join("?" * len(antigos))
        rows = con.execute(f"select pr.nome, q.numero, q.enunciado from classificacao c join pontos pt on pt.id=c.ponto_id "
                           f"join questoes q on q.id=c.questao_id join provas pr on pr.id=q.prova_id where pt.codigo in ({marcas}) "
                           f"order by pr.ano desc, pr.nome, q.numero limit ?", (*antigos, limite)).fetchall()
    finally:
        con.close()
    return [{"prova": r[0], "numero": r[1], "trecho": re.sub(r"\s+", " ", r[2] or "")[:240]} for r in rows]


# ---------------------------------------------------------------- v1 de referência, ordem didática e comparação (M3)
def rascunho_v1(d):
    """O catálogo v1 como um rascunho SOMENTE LEITURA (reconstruído de `base_v1`), para reusar visão, diagnóstico e ordem."""
    base = d["base_v1"]
    assuntos = []
    for auid, a in sorted(base["assuntos"].items(), key=lambda kv: kv[1]["codigo"]):
        pontos = [{"uid": puid, "antigo": p["codigo"], "texto": p["texto"], "descricao": None}
                  for puid, p in sorted(base["pontos"].items(), key=lambda kv: kv[1]["codigo"]) if p["assunto_uid"] == auid]
        assuntos.append({"uid": auid, "antigo": a["codigo"], "nome": a["nome"], "descricao": None, "pre_requisito": None, "pontos": pontos})
    return {"slug": d["slug"], "disciplina": d["disciplina"], "prefixo": d["prefixo"], "versao_base": d["versao_base"], "versao_alvo": d["versao_base"],
            "estado": "v1 (somente leitura)", "atualizado_em": d.get("criado_em"), "assuntos": assuntos, "lixeira": [], "lixeira_assuntos": [],
            "base_v1": base, "historico": {"passado": [], "futuro": []}}


_cache_pos = {}


def _posicoes_por_codigo(banco, disciplina_nome):
    """{código do ponto (v1): {item: posições 0..1 do item nos editais}}. A posição de um item é a ordem de gravação das ocorrências dentro de cada
    edital (e disciplina), normalizada; só entram editais com 5 ou mais itens da disciplina (mesmo critério do `catalogar_diagnostico`)."""
    banco = Path(banco or BANCO)
    chave = (str(banco), disciplina_nome, banco.stat().st_mtime if banco.exists() else 0)
    if chave in _cache_pos:
        return _cache_pos[chave]
    out = {}
    if banco.exists():
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        try:
            con.execute("select 1 from edital_item_ocorrencias limit 1")      # banco sem as tabelas de edital: sem posições
            r = con.execute("select id from disciplinas where nome=?", (disciplina_nome,)).fetchone()
            if r:
                por_edital = {}
                for _, item, edital in con.execute("select o.id, o.item_id, o.edital_id from edital_item_ocorrencias o join edital_itens i on i.id=o.item_id "
                                                   "where i.disciplina_id=? order by o.id", (r[0],)):
                    por_edital.setdefault(edital, []).append(item)
                pos_item = {}
                for lista in por_edital.values():
                    n = len(lista)
                    if n < 5:
                        continue
                    for k, item in enumerate(lista):
                        pos_item.setdefault(item, []).append(k / (n - 1))
                for cod, item in con.execute("select pt.codigo, p.item_id from edital_item_pontos p join pontos pt on pt.id=p.ponto_id where pt.disciplina_id=?", (r[0],)):
                    if item in pos_item:
                        out.setdefault(cod, {})[item] = pos_item[item]
        except sqlite3.OperationalError:
            out = {}
        finally:
            con.close()
    _cache_pos[chave] = out
    return out


def _assunto_por_antigo(d):
    """{código antigo do ponto: uid do assunto atual dele}, seguindo as fusões (ponto na lixeira com destino)."""
    pt_ass = {p["uid"]: a["uid"] for a in d["assuntos"] for p in a["pontos"]}
    m = {p["antigo"]: a["uid"] for a in d["assuntos"] for p in a["pontos"] if p.get("antigo")}
    for p in d["lixeira"]:
        if p.get("antigo"):
            alvo = _destino_final(d, p["uid"])
            if alvo in pt_ass:
                m[p["antigo"]] = pt_ass[alvo]
    return m


def _ponto_por_antigo(d):
    """{código antigo do ponto: uid do ponto atual que o contém (ele mesmo ou aquele em que foi fundido)}."""
    atuais = {p["uid"] for a in d["assuntos"] for p in a["pontos"]}
    m = {p["antigo"]: p["uid"] for a in d["assuntos"] for p in a["pontos"] if p.get("antigo")}
    for p in d["lixeira"]:
        if p.get("antigo"):
            alvo = _destino_final(d, p["uid"])
            if alvo in atuais:
                m[p["antigo"]] = alvo
    return m


def ordem_didatica(d, banco=None):
    """Correlação (Spearman) entre a ORDEM dos assuntos do rascunho e a posição mediana dos itens deles nos editais, e a posição típica de cada
    assunto. Só entram assuntos com 5 ou mais itens com posição; menos de 4 assuntos com dados não dá correlação. É uma pista, não a regra."""
    pos = _posicoes_por_codigo(banco, d["disciplina"])
    m = _assunto_por_antigo(d)
    por_ass = defaultdict(dict)                       # assunto -> {item: posições}: um item ligado a dois pontos do mesmo assunto conta uma vez
    for cod, itens in pos.items():
        if m.get(cod):
            por_ass[m[cod]].update(itens)
    xs, ys, dados = [], [], {}
    for i, a in enumerate(d["assuntos"]):
        lista = [x for ps in por_ass.get(a["uid"], {}).values() for x in ps]
        if len(lista) >= 5:
            med = st.median(lista)
            xs.append(i)
            ys.append(med)
            dados[a["uid"]] = {"mediana": round(med, 3), "n": len(lista)}
    rho = spearman(xs, ys) if xs else None
    atual = [a["uid"] for a in d["assuntos"] if a["uid"] in dados]
    editais = sorted(atual, key=lambda u: dados[u]["mediana"])
    for k, u in enumerate(atual, 1):
        dados[u]["pos_atual"] = k
    for k, u in enumerate(editais, 1):
        dados[u]["pos_editais"] = k
    return {"rho": None if rho is None else round(rho, 3), "assuntos_com_dados": len(dados), "por_assunto": dados}


def _resumo_estrutura(d, banco):
    dg = diagnostico(d, banco)
    o = ordem_didatica(d, banco)
    return {"assuntos": dg["assuntos"], "pontos": dg["pontos"], "pequenos": dg["pequenos"], "grandes": dg["grandes"],
            "pouca_evidencia": len(dg["pontos_sem_evidencia"]), "ordem_rho": o["rho"], "ordem_assuntos_com_dados": o["assuntos_com_dados"]}


def comparacao(d, banco=None):
    """Métricas de estrutura do v1 e do v2 lado a lado, e o resumo das mudanças (contagem por ação do mapa)."""
    acoes = Counter(m["acao"] for m in mapa(d))
    return {"v1": _resumo_estrutura(rascunho_v1(d), banco), "v2": _resumo_estrutura(d, banco), "mudancas": dict(acoes)}


def visao_v1(d, banco=None):
    """Visão do catálogo v1 (somente leitura), no mesmo formato de `visao`."""
    return visao(rascunho_v1(d), banco)


def _metricas(reais, previstos):
    n = len(reais)
    if not n:
        return None
    from catalogar_referencia import kappa, macro_f1
    acerto = sum(a == b for a, b in zip(reais, previstos)) / n
    maioria = max(Counter(reais).values()) / n
    return {"classes": len(set(reais)), "acuracia": round(acerto, 3), "acaso_maioria": round(maioria, 3), "kappa": round(kappa(reais, previstos), 3),
            "macro_f1": round(macro_f1(reais, previstos), 3)}


def metricas_classificacao(d, banco=None, folds=5):
    """Mede o classificador por código (TF-IDF, centroide mais próximo, validação cruzada) com os rótulos v1 e com os rótulos MIGRADOS para o v2
    (pelo mapa: cada questão vai para o ponto atual que contém o ponto antigo dela). Mesmas questões e mesmas partes nas duas medidas.
    CUIDADO: fundir classes aumenta a acurácia por si só (há menos classes para errar). Por isso o `kappa`, que desconta o acaso, é a medida principal;
    `acaso_maioria` é a acurácia de quem sempre chuta a classe mais comum."""
    from catalogar_referencia import validacao_cruzada
    banco = Path(banco or BANCO)
    base = d["base_v1"]
    ass_cod = {u: a["codigo"] for u, a in base["assuntos"].items()}
    pt_ass_v1 = {p["codigo"]: ass_cod[p["assunto_uid"]] for p in base["pontos"].values()}
    cods = codigos(d)
    pt_atual = _ponto_por_antigo(d)
    ass_do_ponto = {p["uid"]: a["uid"] for a in d["assuntos"] for p in a["pontos"]}
    if not banco.exists() or not pt_ass_v1:
        return {"questoes": 0, "aviso": "sem banco ou sem pontos."}
    con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    try:
        marcas = ",".join("?" * len(pt_ass_v1))
        rows = con.execute(f"select q.id, q.enunciado, q.alt_a, q.alt_b, q.alt_c, q.alt_d, q.alt_e, pt.codigo from classificacao c "
                           f"join questoes q on q.id=c.questao_id join pontos pt on pt.id=c.ponto_id "
                           f"where pt.codigo in ({marcas}) and q.situacao='valida' order by q.id", tuple(pt_ass_v1)).fetchall()
    finally:
        con.close()
    dados = []
    for qid, enun, a1, a2, a3, a4, a5, cod in rows:
        uid2 = pt_atual.get(cod)
        if not uid2:
            continue
        dados.append({"qid": qid, "disc_id": 0, "enunciado": enun, "alt_a": a1, "alt_b": a2, "alt_c": a3, "alt_d": a4, "alt_e": a5,
                      "ponto": cod, "assunto": pt_ass_v1[cod], "ponto2": cods[uid2], "assunto2": cods[ass_do_ponto[uid2]]})
    n = len(dados)
    if n < 30:
        return {"questoes": n, "aviso": f"só {n} questões classificadas nesta disciplina: pouco para medir (o mínimo útil é cerca de 30)."}
    prev = {nivel: validacao_cruzada(dados, folds, nivel) for nivel in ("ponto", "assunto", "ponto2", "assunto2")}

    def medir(nivel):
        reais = [r[nivel] for r in dados]
        previstos = [prev[nivel].get(r["qid"], (None, 0))[0] for r in dados]
        return _metricas(reais, previstos)
    return {"questoes": n, "folds": folds, "v1": {"ponto": medir("ponto"), "assunto": medir("assunto")},
            "v2": {"ponto": medir("ponto2"), "assunto": medir("assunto2")},
            "aviso": "Fundir classes aumenta a acurácia por si só; compare pelo kappa (desconta o acaso) e pelo macro-F1."}
