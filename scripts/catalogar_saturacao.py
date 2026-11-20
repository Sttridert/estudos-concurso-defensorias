#!/usr/bin/env python3
"""Grupo B (Catalogar): teste de saturação de um universo de editais (só leitura).

Uso (sempre com `python -I`):
  python -I scripts/catalogar_saturacao.py [universo ...] [--simulacoes N]
      Sem argumento, roda todos os universos de `dados/universos_editais.json`.

Pergunta que responde: os editais do universo já bastam para conhecer os assuntos e pontos do cargo? Mede quantos assuntos e pontos
NOVOS cada edital traz, em ordem cronológica e na média de várias ordens aleatórias, e aplica o critério escrito no próprio arquivo
(escrito antes de ver o resultado): mínimo de editais, últimos N editais sem assunto novo e no máximo X% dos pontos vistos em um só edital.
O nível "item de texto" não é medido: a redação muda de edital para edital e nunca satura.

Ressalvas (declaradas na saída): (1) assunto e ponto vêm do catálogo atual, que foi usado para ligar os itens dos editais; "99% já visto"
mostra que o catálogo cobre bem os editais, não que está completo. (2) Só as disciplinas com edital fictício (9 de Direito) são medidas.
(3) O estimador Chao2 é um limite inferior do que ainda não foi visto. Edital do concurso-alvo (`edital_alvo`) fica fora da curva e vira
um teste de cobertura: quantos dos seus assuntos e pontos os demais editais já traziam.
"""
import collections
import json
import random
import sqlite3
import statistics as st
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
UNIVERSOS = RAIZ / "dados" / "universos_editais.json"

UNIDADES = {
    "assunto": ("select o.edital_id, pt.assunto_id from edital_item_ocorrencias o join edital_item_pontos p on p.item_id=o.item_id "
                "join pontos pt on pt.id=p.ponto_id"),
    "ponto": "select o.edital_id, p.ponto_id from edital_item_ocorrencias o join edital_item_pontos p on p.item_id=o.item_id",
}


def editais_do_universo(con, u, incluir_alvo=False):
    f = u["filtro"]
    excl = {int(k) for k in u.get("excluir_editais", {})}
    alvo = u.get("edital_alvo")
    out = []
    com_itens = {e for (e,) in con.execute("select distinct edital_id from edital_item_ocorrencias")}   # só editais com programa extraído
    for i, nome, carreira, cargo, ano in con.execute("select id,nome,carreira,cargo,ano from editais where tipo='real'"):
        if i not in com_itens and i != u.get("edital_alvo"):
            continue
        cargo = cargo or ""
        if i in excl or (alvo == i and not incluir_alvo):
            continue
        if f.get("carreira") and carreira != f["carreira"]:
            continue
        if f.get("cargo_prefixo") and not cargo.startswith(f["cargo_prefixo"]):
            continue
        if f.get("cargo_exclui") and f["cargo_exclui"] in cargo:
            continue
        if f.get("ano_min") and (ano or 0) < f["ano_min"]:
            continue
        if f.get("ano_max") and (ano or 9999) > f["ano_max"]:
            continue
        out.append((i, nome, ano))
    return sorted(out, key=lambda e: (e[2] or 0, e[0]))


def chao2(conjuntos):
    m = len(conjuntos)
    cont = collections.Counter(x for s in conjuntos for x in s)
    S = len(cont)
    q1 = sum(1 for v in cont.values() if v == 1)
    q2 = sum(1 for v in cont.values() if v == 2)
    est = S + ((m - 1) / m) * (q1 * q1 / (2 * q2) if q2 else q1 * (q1 - 1) / 2)
    return S, q1, q2, est


def medir(con, uid, u, crit, simulacoes):
    eds = editais_do_universo(con, u)
    ids = [e[0] for e in eds]
    print(f"\n=== Universo '{uid}': {u['nome']}")
    print(f"    {len(ids)} editais (filtro {u['filtro']}); excluídos por extração incompleta: {sorted(u.get('excluir_editais', {}))}; "
          f"edital-alvo fora da curva: {u.get('edital_alvo')}")
    if len(ids) < 2:
        print("    poucos editais para medir.")
        return None
    res = {}
    random.seed(1)
    for un in crit["unidades"]:
        dados = {}
        for e, x in con.execute(UNIDADES[un]):
            if e in ids:
                dados.setdefault(e, set()).add(x)
        sets = [dados.get(e, set()) for e in ids]
        total = len(set().union(*sets))

        def curva(ordem):
            vistos, out = set(), []
            for s in ordem:
                novos = len(s - vistos)
                vistos |= s
                out.append((len(vistos), novos))
            return out
        cron = curva(sets)
        rnd = [curva(random.sample(sets, len(sets))) for _ in range(simulacoes)]
        S, q1, q2, est = chao2(sets)
        print(f"  -- nível {un}: {total} distintos")
        print("     n editais | já visto (média de ordens aleatórias) | novos no n-ésimo (média)")
        for n in [n for n in (3, 5, 8, 10, 12, 15, 20, 25, 30, 35) if n <= len(sets)]:
            acum = st.mean(r[n - 1][0] for r in rnd)
            novos = st.mean(r[n - 1][1] for r in rnd)
            print(f"     {n:>9} | {acum:8.0f} ({100 * acum / total:5.1f}%)                   | {novos:6.1f}")
        print(f"     vistos em um só edital: {q1} ({100 * q1 / S:.1f}% dos distintos); em dois: {q2}; Chao2 estima {est:.0f} (faltariam cerca de {est - S:.0f})")
        print("     novos por edital, em ordem cronológica:", [n for _, n in cron])
        res[un] = {"sem_novos_no_fim": all(n == 0 for _, n in cron[-crit["ultimos_sem_assunto_novo"]:]), "pct_um_edital": 100 * q1 / S, "total": total}
    # veredito
    ok_min = len(ids) >= crit["minimo_editais"]
    ok_fim = res["assunto"]["sem_novos_no_fim"]
    ok_um = res["ponto"]["pct_um_edital"] <= crit["max_pontos_vistos_em_um_edital_pct"]
    print(f"  -- VEREDITO (critério escrito em {crit['escrito_em']}):")
    print(f"     mínimo de {crit['minimo_editais']} editais: {'passa' if ok_min else 'NÃO passa'} ({len(ids)})")
    print(f"     últimos {crit['ultimos_sem_assunto_novo']} editais sem assunto novo: {'passa' if ok_fim else 'NÃO passa'}")
    print(f"     pontos vistos em um só edital: {res['ponto']['pct_um_edital']:.1f}% (máximo {crit['max_pontos_vistos_em_um_edital_pct']}%): "
          f"{'passa' if ok_um else 'NÃO passa'}")
    veredito = "BASE SUFICIENTE (catálogo pode ser fechado)" if (ok_min and ok_fim and ok_um) else "BASE INSUFICIENTE (catálogo fecha como provisório; coletar mais editais)"
    print(f"     => {veredito}")
    # teste de cobertura do edital-alvo
    alvo = u.get("edital_alvo")
    if alvo:
        print(f"  -- Edital-alvo {alvo}: cobertura pelos {len(ids)} editais do universo")
        for un in crit["unidades"]:
            vistos = set()
            alvo_set = set()
            for e, x in con.execute(UNIDADES[un]):
                if e in ids:
                    vistos.add(x)
                elif e == alvo:
                    alvo_set.add(x)
            falt = alvo_set - vistos
            print(f"     {un}: {len(alvo_set) - len(falt)} de {len(alvo_set)} já vistos ({100 * (len(alvo_set) - len(falt)) / max(len(alvo_set), 1):.0f}%); "
                  f"o alvo traz {len(falt)} que o universo não tinha")
    return veredito


def main():
    args = sys.argv[1:]
    sim = 300
    if "--simulacoes" in args:
        i = args.index("--simulacoes")
        sim = int(args[i + 1])
        del args[i:i + 2]
    cfg = json.loads(UNIVERSOS.read_text(encoding="utf-8"))
    crit = cfg["criterio_de_saturacao"]
    ids = args or list(cfg["universos"])
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    print(f"Critério (escrito em {crit['escrito_em']}, valores iniciais): mínimo {crit['minimo_editais']} editais; últimos "
          f"{crit['ultimos_sem_assunto_novo']} sem assunto novo; no máximo {crit['max_pontos_vistos_em_um_edital_pct']}% dos pontos vistos em um só edital.")
    for uid in ids:
        if uid not in cfg["universos"]:
            sys.exit(f"universo '{uid}' não existe. Há: {', '.join(cfg['universos'])}")
        medir(con, uid, cfg["universos"][uid], crit, sim)
    print("\nRessalvas: assunto e ponto vêm do catálogo atual, usado na ligação dos itens (em parte circular); só as 9 disciplinas de Direito com "
          "edital fictício são medidas; o Chao2 é um limite inferior.")


if __name__ == "__main__":
    main()
