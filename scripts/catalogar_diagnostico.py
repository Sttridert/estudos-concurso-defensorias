#!/usr/bin/env python3
"""Grupo B (Catalogar): diagnóstico do catálogo (só leitura). Mede o que o plano do grupo B chama de "métricas de guarda".

Uso (sempre com `python -I`):
  python -I scripts/catalogar_diagnostico.py [--disciplina SIGLA] [--gravar-linha-de-base ARQUIVO.json]

O que mede, por disciplina (valores de corte são HIPÓTESES iniciais do contrato do catálogo, a calibrar no piloto):
  1. Tamanho   assunto PEQUENO (até 2 pontos, ou menos de 4% das questões e menos de 4% dos itens da disciplina) e assunto GRANDE
               (mais de 8 pontos, ou mais de 25% das questões ou dos itens). Pequeno pede rebaixar a ponto ou fundir; grande pede dividir.
  2. Desencaixe  pontos (com 5 ou mais itens de edital ligados) mais parecidos, em palavras, com o centro de OUTRO assunto da mesma
               disciplina do que com o do próprio. É só triagem: sobreposição legítima também aparece.
  3. Sem tópico  itens do edital fictício sem ponto ligado (muitos são fragmentos genéricos: "Conceito.", "Disposições gerais.").
  4. Ordem     correlação de postos (Spearman) entre a ordem dos assuntos no catálogo (código) e a posição mediana dos seus itens nos
               editais (aproximada pela ordem de gravação das ocorrências em cada edital): mede se a ordem didática acompanha a dos editais.
  5. Cobertura questões da disciplina com ponto principal classificado.
Não altera nada. A mesma execução com `--gravar-linha-de-base` guarda os números em arquivo (uso: comparar catálogo v1 com v2).
"""
import collections
import datetime
import json
import math
import re
import sqlite3
import statistics as st
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_disciplinas as LD  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"

# valores iniciais do contrato do catálogo (hipóteses; ver docs/03-PENDENCIAS.md, bloco do grupo B)
PEQ_PONTOS, PEQ_PCT = 2, 4.0
GRANDE_PONTOS, GRANDE_PCT = 8, 25.0
MIN_ITENS_DESENCAIXE = 5

STOP = set("de da do das dos a o as os e em no na nos nas que para por com um uma ao se ou sao ser como mais sua seu pela pelo ante sobre entre ate art lei".split())


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def tok(s):
    return [w for w in re.findall(r"[a-z]{3,}", norm(s)) if w not in STOP]


def postos(valores):
    """Postos com média nos empates."""
    ordem = sorted(range(len(valores)), key=lambda i: valores[i])
    r = [0.0] * len(valores)
    i = 0
    while i < len(ordem):
        j = i
        while j + 1 < len(ordem) and valores[ordem[j + 1]] == valores[ordem[i]]:
            j += 1
        for k in range(i, j + 1):
            r[ordem[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 4:
        return None
    rx, ry = postos(x), postos(y)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def main():
    args = sys.argv[1:]
    so = None
    saida = None
    if "--disciplina" in args:
        so = args[args.index("--disciplina") + 1].upper()
    if "--gravar-linha-de-base" in args:
        saida = Path(args[args.index("--gravar-linha-de-base") + 1])
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    q = lambda s: con.execute(s).fetchall()  # noqa: E731
    disc = {i: n for i, n in q("select id,nome from disciplinas")}
    sigla_de = {LD.nome(s): s for s in LD.SIGLAS}
    ass = {i: (d, cod, nome) for i, d, cod, nome in q("select id,disciplina_id,codigo,nome from assuntos")}
    pts = q("select id,disciplina_id,assunto_id,codigo,texto from pontos where ativo=1")
    pt_ass = {p[0]: p[2] for p in pts}
    pdisc = {p[0]: p[1] for p in pts}
    npts = collections.Counter(p[2] for p in pts)
    nq = collections.Counter()
    for (pid,) in q("select ponto_id from classificacao where ponto_id is not null"):
        if pid in pt_ass:
            nq[pt_ass[pid]] += 1
    items_por_ponto = collections.defaultdict(set)
    for it, pid in q("select item_id,ponto_id from edital_item_pontos"):
        items_por_ponto[pid].add(it)
    ni = collections.Counter()
    for pid, s in items_por_ponto.items():
        if pid in pt_ass:
            ni[pt_ass[pid]] += len(s)
    tot_q, tot_i = collections.Counter(), collections.Counter()
    for a, (d, _, _) in ass.items():
        tot_q[d] += nq[a]
        tot_i[d] += ni[a]

    resultado = {"gerado_em": datetime.date.today().isoformat(), "cortes": {"peq_pontos": PEQ_PONTOS, "peq_pct": PEQ_PCT, "grande_pontos": GRANDE_PONTOS,
                                                                           "grande_pct": GRANDE_PCT, "min_itens_desencaixe": MIN_ITENS_DESENCAIXE},
                 "por_disciplina": {}}

    # ---- 1. tamanho
    print("== 1. TAMANHO DOS ASSUNTOS (cortes iniciais: pequeno = até 2 pontos ou <4% das questões e dos itens; grande = >8 pontos ou >25%)")
    peq_total = grande_total = 0
    ass_total = 0
    for d in sorted({v[0] for v in ass.values()}):
        sg = sigla_de.get(disc[d], "?")
        if so and sg != so:
            continue
        lista = [(a, v) for a, v in ass.items() if v[0] == d]
        peq, grande = [], []
        for a, (_, cod, nome) in sorted(lista, key=lambda x: x[1][1]):
            pq = 100 * nq[a] / max(tot_q[d], 1)
            pi = 100 * ni[a] / max(tot_i[d], 1)
            linha = f"{cod:7} {nome[:50]:50} pontos={npts[a]:2d} questões={nq[a]:3d} ({pq:4.1f}%) itens={ni[a]:4d} ({pi:4.1f}%)"
            if npts[a] <= PEQ_PONTOS or (pq < PEQ_PCT and pi < PEQ_PCT):
                peq.append((cod, linha))
            if npts[a] > GRANDE_PONTOS or pq > GRANDE_PCT or pi > GRANDE_PCT:
                grande.append((cod, linha))
        ass_total += len(lista)
        peq_total += len(peq)
        grande_total += len(grande)
        ns = sorted(npts[a] for a, _ in lista if npts[a] > 0)
        print(f"\n{disc[d]} ({sg}): {len(lista)} assuntos; pontos por assunto: mínimo {ns[0] if ns else 0}, mediana {ns[len(ns) // 2] if ns else 0}, máximo {ns[-1] if ns else 0}")
        for cod, linha in peq:
            print("   pequeno:", linha)
        for cod, linha in grande:
            print("   GRANDE: ", linha)
        resultado["por_disciplina"].setdefault(sg, {}).update({"assuntos": len(lista), "pequenos": [c for c, _ in peq], "grandes": [c for c, _ in grande]})
    print(f"\n-> {peq_total} pequenos e {grande_total} grandes, de {ass_total} assuntos")
    resultado["assuntos_total"], resultado["assuntos_pequenos"], resultado["assuntos_grandes"] = ass_total, peq_total, grande_total

    # ---- 2. desencaixe
    item_txt = {i: t for i, t in q("select id,texto from edital_itens")}
    doc = {}
    for p in pts:
        its = items_por_ponto.get(p[0], ())
        if len(its) >= MIN_ITENS_DESENCAIXE:
            doc[p[0]] = collections.Counter(tok(p[4] + " " + " ".join(item_txt[i] for i in its)))
    df = collections.Counter(w for d in doc.values() for w in d)
    N = len(doc)

    def vec(d):
        v = {w: (1 + math.log(n)) * math.log(N / df[w]) for w, n in d.items() if df.get(w)}
        nr = math.sqrt(sum(x * x for x in v.values())) or 1
        return {w: x / nr for w, x in v.items()}
    V = {p: vec(d) for p, d in doc.items()}

    def cos(a, b):
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(w, 0) for w, x in a.items())

    def cent(ids):
        s = collections.defaultdict(float)
        for i in ids:
            for w, x in V[i].items():
                s[w] += x
        nr = math.sqrt(sum(x * x for x in s.values())) or 1
        return {w: x / nr for w, x in s.items()}
    por_ass = collections.defaultdict(list)
    for p in V:
        por_ass[pt_ass[p]].append(p)
    info = {p[0]: (p[3], p[4]) for p in pts}
    mis, tot = [], 0
    for p in V:
        a = pt_ass[p]
        d = pdisc[p]
        if so and sigla_de.get(disc[d]) != so:
            continue
        outros = [x for x in por_ass[a] if x != p]
        if len(outros) < 2:
            continue
        own = cos(V[p], cent(outros))
        best = max(((cos(V[p], cent(por_ass[b])), b) for b in por_ass if b != a and ass[b][0] == d and len(por_ass[b]) >= 2), default=(0, None))
        tot += 1
        if best[0] > own:
            mis.append((d, p, a, best[1], own, best[0]))
    print(f"\n== 2. DESENCAIXE (pontos com {MIN_ITENS_DESENCAIXE}+ itens; similaridade em palavras; só triagem): {len(mis)} de {tot} pontos ({100 * len(mis) / max(tot, 1):.0f}%) "
          "ficam mais próximos de OUTRO assunto da mesma disciplina")
    cnt = collections.Counter(m[0] for m in mis)
    for d, n in cnt.most_common():
        print(f"   {disc[d][:42]:42} {n}")
        resultado["por_disciplina"].setdefault(sigla_de.get(disc[d], "?"), {})["desencaixados"] = n
    for m in sorted(mis, key=lambda m: -(m[5] - m[4]))[:8]:
        print(f"   {info[m[1]][0]} '{info[m[1]][1][:42]}' está em {ass[m[2]][1]} '{ass[m[2]][2][:26]}' ({m[4]:.2f}); mais próximo de {ass[m[3]][1]} '{ass[m[3]][2][:26]}' ({m[5]:.2f})")
    resultado["desencaixe"] = {"pontos_medidos": tot, "desencaixados": len(mis), "pct": round(100 * len(mis) / max(tot, 1), 1)}

    # ---- 3. itens sem tópico
    print("\n== 3. ITENS DO EDITAL FICTÍCIO SEM PONTO LIGADO")
    sem = q("select d.nome,count(*),sum(i.flags like '%fragmento gen%') from edital_itens i join disciplinas d on d.id=i.disciplina_id "
            "where i.id not in (select item_id from edital_item_pontos) group by d.nome")
    tot_it = dict(q("select d.nome,count(*) from edital_itens i join disciplinas d on d.id=i.disciplina_id group by d.nome"))
    s_tot = i_tot = 0
    for nome, n, frag in sem:
        if so and sigla_de.get(nome) != so:
            continue
        print(f"   {nome[:42]:42} {n:4d} de {tot_it[nome]:4d} ({100 * n / tot_it[nome]:4.1f}%), dos quais {frag or 0} fragmentos genéricos")
        s_tot += n
        i_tot += tot_it[nome]
        resultado["por_disciplina"].setdefault(sigla_de.get(nome, "?"), {})["itens_sem_ponto"] = n
    print(f"-> {s_tot} de {i_tot} itens ({100 * s_tot / max(i_tot, 1):.1f}%)")
    resultado["itens_sem_ponto"] = {"sem_ponto": s_tot, "total": i_tot}

    # ---- 4. ordem
    ordem_occ = collections.defaultdict(list)
    for oid, it, e, d in q("select o.id,o.item_id,o.edital_id,i.disciplina_id from edital_item_ocorrencias o join edital_itens i on i.id=o.item_id order by o.id"):
        ordem_occ[(e, d)].append((oid, it))
    pos_por_assunto = collections.defaultdict(list)
    # item -> pontos -> assunto
    item_ass = collections.defaultdict(set)
    for pid, its in items_por_ponto.items():
        if pid in pt_ass:
            for it in its:
                item_ass[it].add(pt_ass[pid])
    for (e, d), lst in ordem_occ.items():
        n = len(lst)
        if n < 5:
            continue
        for k, (oid, it) in enumerate(lst):
            for a in item_ass.get(it, ()):
                if ass[a][0] == d:
                    pos_por_assunto[a].append(k / (n - 1))
    print("\n== 4. ORDEM DIDÁTICA: correlação (Spearman) entre a ordem dos assuntos no catálogo e a posição mediana nos editais (aproximada pela ordem de gravação)")
    resultado["ordem"] = {}
    for d in sorted({v[0] for v in ass.values()}):
        sg = sigla_de.get(disc[d], "?")
        if so and sg != so:
            continue
        xs, ys = [], []
        for a, (dd, cod, nome) in sorted(ass.items(), key=lambda x: x[1][1]):
            if dd == d and len(pos_por_assunto.get(a, ())) >= 5:
                m = re.search(r"(\d+)$", cod)
                xs.append(int(m.group(1)) if m else len(xs))
                ys.append(st.median(pos_por_assunto[a]))
        r = spearman(xs, ys)
        print(f"   {disc[d][:42]:42} {('%.2f' % r) if r is not None else 'sem dados'}  ({len(xs)} assuntos com 5+ ocorrências)")
        resultado["ordem"][sg] = None if r is None else round(r, 3)

    # ---- 5. cobertura de questões
    print("\n== 5. QUESTÕES VÁLIDAS DA DISCIPLINA COM PONTO PRINCIPAL")
    cob = q("select d.nome,count(*),sum(c.ponto_id is not null) from questoes q join disciplinas d on d.id=q.disciplina_id "
            "left join classificacao c on c.questao_id=q.id where q.situacao='valida' group by d.nome")
    resultado["cobertura_questoes"] = {}
    for nome, n, c in cob:
        sg = sigla_de.get(nome)
        if sg and (not so or sg == so):
            print(f"   {nome[:42]:42} {c or 0:4d} de {n:4d} ({100 * (c or 0) / n:4.1f}%)")
            resultado["cobertura_questoes"][sg] = {"classificadas": c or 0, "validas": n}
    if saida:
        saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("\nlinha de base gravada em", saida)


if __name__ == "__main__":
    main()
