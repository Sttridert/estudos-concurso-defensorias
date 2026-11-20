#!/usr/bin/env python3
"""Grupo C (Mapear): relatório de COBERTURA, só leitura (não grava nada).

Uso:  python -I scripts/mapear_cobertura.py [--banco ARQ] [--md ARQ]

Três quadros, sobre o catálogo v2 e o banco atual:
 1. Questões por disciplina: válidas, classificadas (e quantas "migrada" e quantas revisadas por humano) e sem classificação.
    "Disciplina com catálogo" = tem tópicos ativos; as outras aparecem à parte (não há onde classificar).
 2. Tópicos ativos por disciplina: com e sem nenhuma questão (principal ou secundária), e os novos do v2 sem questão.
 3. Editais reais classificados: frases, frases sem tópico principal, e tópicos das disciplinas do edital que nenhuma
    frase cobre e que ninguém declarou FORA ("sem julgamento").
Questão válida = situação 'valida' (a mesma regra do motor `23`).
"""
import sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    banco = Path(a[a.index("--banco") + 1]) if "--banco" in a else RAIZ / "banco" / "estudos.db"
    con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    q = lambda s, *p: con.execute(s, p).fetchall()
    L = ["# Cobertura do mapeamento (só leitura)", ""]

    com_cat = {i for (i,) in q("select distinct disciplina_id from pontos where ativo=1")}
    L += ["## 1. Questões válidas por disciplina", "",
          "| Disciplina | Válidas | Classificadas | Sem classificação | % classificada | Migrada (v1→v2) | Revisada por humano |", "|---|---|---|---|---|---|---|"]
    tot = [0, 0]
    sem_cat = []
    for did, nome in q("select id,nome from disciplinas order by nome"):
        v, c, m, r = q("""select count(*), count(k.questao_id), sum(coalesce(k.origem,'') like '%migrada%'), sum(coalesce(k.revisada,0))
                          from questoes qu left join classificacao k on k.questao_id=qu.id where qu.disciplina_id=? and qu.situacao='valida'""", did)[0]
        if not v:
            continue
        if did not in com_cat:
            sem_cat.append((nome, v)); continue
        tot[0] += v; tot[1] += c
        L.append(f"| {nome} | {v} | {c} | {v - c} | {100 * c // v}% | {m or 0} | {r or 0} |")
    L.append(f"| **Total (disciplinas com catálogo)** | {tot[0]} | {tot[1]} | {tot[0] - tot[1]} | {100 * tot[1] // max(1, tot[0])}% | | |")
    if sem_cat:
        L += ["", "Disciplinas SEM catálogo (nada a classificar até existir catálogo): " + "; ".join(f"{n} ({v})" for n, v in sem_cat) + "."]
    fora = q("""select count(*) from classificacao k join questoes qu on qu.id=k.questao_id where qu.situacao<>'valida'""")[0][0]
    L += ["", f"Classificações em questões que não são válidas (anulada, desatualizada, revisar_texto): {fora}."]

    L += ["", "## 2. Tópicos ativos por disciplina", "", "| Disciplina | Tópicos | Com questão | Sem questão | Sem questão e novos do v2 |", "|---|---|---|---|---|"]
    for did, nome in q("select id,nome from disciplinas where id in (select disciplina_id from pontos where ativo=1) order by nome"):
        n, comq, novos = q("""select count(*),
              sum(exists(select 1 from classificacao k where k.ponto_id=p.id or k.ponto2_id=p.id)),
              sum(not exists(select 1 from classificacao k where k.ponto_id=p.id or k.ponto2_id=p.id) and p.origem is not null and p.criado_em >= '2026-11-20')
              from pontos p where p.disciplina_id=? and p.ativo=1""", did)[0]
        L.append(f"| {nome} | {n} | {comq or 0} | {n - (comq or 0)} | {novos or 0} |")
    L += ["", "(\"Novos do v2\" = criados em 20/11/2026 ou depois; é uma aproximação pela data de criação.)"]

    L += ["", "## 3. Editais reais classificados", ""]
    for eid, nome in q("select distinct e.id,e.nome from editais e join edital_frases f on f.edital_id=e.id order by e.id"):
        nf = q("select count(*) from edital_frases where edital_id=?", eid)[0][0]
        sem_p = q("""select count(*) from edital_frases f where edital_id=? and not exists
                     (select 1 from edital_frase_destinos d where d.frase_id=f.id and d.papel='principal')""", eid)[0][0]
        discs = [d for (d,) in q("select distinct disciplina_id from edital_blocos where edital_id=?", eid)]
        sem_j = q(f"""select count(*) from pontos p where p.ativo=1 and p.disciplina_id in ({','.join('?' * len(discs)) or 'NULL'})
                      and not exists(select 1 from edital_frase_destinos d join edital_frases f on f.id=d.frase_id where d.ponto_id=p.id and f.edital_id=?)
                      and not exists(select 1 from edital_pontos_fora x where x.ponto_id=p.id and x.edital_id=?)""", *discs, eid, eid)[0][0]
        fora_n = q("select count(*) from edital_pontos_fora where edital_id=?", eid)[0][0]
        L.append(f"- **{nome}**: {nf} frases; {sem_p} sem tópico principal; {fora_n} tópicos declarados FORA; **{sem_j} tópicos sem julgamento** (nenhuma frase os cobre e ninguém os declarou fora).")
    saida = "\n".join(L) + "\n"
    if "--md" in a:
        Path(a[a.index("--md") + 1]).write_text(saida, encoding="utf-8")
    print(saida)


if __name__ == "__main__":
    main()
