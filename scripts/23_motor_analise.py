"""Etapa 4: motor generico de analise (Guia 1). Funciona para qualquer disciplina e perfil gravados em banco/estudos.db.
Uso:  python scripts/23_motor_analise.py [--perfil ID] [--universo ID] [--legado] [--comparar]
  --universo ID : usa outro universo (filtro de quais questoes entram; tabela `universos`, criada por scripts/25) em vez do do perfil.
  --comparar    : compara todos os universos no mesmo alvo (provas do grupo A do perfil) e grava a tabela em banco/analise/.
  --legado : reproduz a conta antiga (assunto provisorio, sem segundo ponto) para conferir contra scripts/11.
Saidas: banco/analise/<disciplina>_perfil<ID>.json e .md   (nao altera o banco, so le).
Regras (Guia 1 + 04-DECISOES-CONFIRMADAS): peso da questao = semelhanca (A,B,C) x recencia 0,5^(idade/meia-vida);
segundo ponto divide a questao (0,5 cada). Lente em branco = neutro (1). Examinador (lente 5) e lente 10 nao entram aqui.
"""
import argparse, json, math, sqlite3, sys, collections
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_escopo as LE      # perfil por bloco do edital (decisao 41)
import lib_perfil as LP      # perfil como arquivo na pasta do concurso (plano 06, Etapa 2b)

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "banco" / "estudos.db"
VALIDAS = ("valida", "revisar_texto")


def wilson(p, n, z=1.96):
    if n <= 0:
        return 0.0, 1.0
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


def carregar_perfil(con, pid):
    p = LP.perfil_do_arquivo(con, pid)       # o ARQUIVO perfil.toml da pasta do concurso manda (decisao 46)
    if p is None:
        sys.exit(f"Perfil {pid} não existe: nenhum perfil.toml em produtos/apostilas/ tem uma apostila com id = {pid}. "
                 "Crie com scripts/72_perfil.py (novo-concurso / nova-apostila). A tabela `perfis` do banco foi aposentada (decisão 47).")
    faltam = [rot for k, rot in (("disciplina_id", "disciplina"), ("cargo", "cargo"), ("banca", "banca"), ("carreira", "carreira")) if not p.get(k)]
    if faltam:
        sys.exit("Perfil incompleto. Faltam: " + ", ".join(faltam) + ". Informe e confirme antes de gerar.")
    if not p["confirmado_pelo_usuario"]:
        sys.exit(p.get("motivo_nao_confirmado") or "Perfil ainda não confirmado pelo usuário. Mostre o perfil e peça confirmação.")
    p["pesos"] = json.loads(p["pesos_grupo"])
    p["avisos_grupo"] = []
    p["orgao_ativo"] = False
    if p.get("orgao"):
        achou = con.execute("""select count(*) from provas where lower(instituicao)=lower(?) and lower(cargo)=lower(?) and lower(banca)=lower(?) and lower(carreira)=lower(?)""",
                            (p["orgao"], p["cargo"], p["banca"], p["carreira"])).fetchone()[0]
        if achou:
            p["orgao_ativo"] = True
        else:
            p["avisos_grupo"].append(f"O perfil pede o órgão {p['orgao']}, mas o banco não tem prova de {p['cargo']} · {p['banca']} desse órgão: usei a regra de estudo geral (grupo A = mesmo cargo e banca, qualquer órgão).")
    p["desc_grupos"] = descricao_grupos(p)
    p["universo"] = p["universo_arquivo"] if p.get("universo_arquivo") else carregar_universo(con, p.get("universo_id"))
    return p


def carregar_universo(con, uid):
    """Universo = filtro de quais questoes entram na conta. Sem universo: todas as questoes."""
    if uid is not None:
        r = con.execute("select id,nome,descricao,filtro from universos where id=?", (uid,)).fetchone()
        if not r:
            sys.exit(f"Universo {uid} não existe (veja a tabela universos).")
        return {"id": r[0], "nome": r[1], "descricao": r[2], "filtro": json.loads(r[3])}
    return {"id": None, "nome": "Todas as questões", "descricao": "Sem filtro.", "filtro": {}}


def em_universo(q, filtro):
    """Filtros combinados com E; dentro de cada lista, OU. Chaves: bancas, carreiras, cargos, cargos_prefixo (ex.: 'Analista'), instituicoes, ano_min, ano_max. Comparacao sem diferenciar maiusculas."""
    for chave, campo in (("bancas", "banca"), ("carreiras", "carreira"), ("cargos", "cargo"), ("instituicoes", "inst")):
        lista = filtro.get(chave)
        if lista and q[campo].casefold() not in {x.casefold() for x in lista}:
            return False
    prefixos = filtro.get("cargos_prefixo")
    if prefixos and not any(q["cargo"].casefold().startswith(x.casefold()) for x in prefixos):
        return False
    if filtro.get("ano_min") and q["ano"] < filtro["ano_min"]:
        return False
    if filtro.get("ano_max") and q["ano"] > filtro["ano_max"]:
        return False
    return True


def mesmo(a, b):
    return (a or "").casefold() == (b or "").casefold()


def grupo_da_prova(perfil, prova):
    """Sem orgao no perfil (estudo geral): A = mesma carreira, banca e cargo; B = mesma carreira e banca, outro cargo;
    C = o resto (outra banca ou outra carreira).
    Com orgao no perfil (concurso de um orgao, Guia 1 secao 4.4): A = mesmo orgao, carreira, banca e cargo;
    B = mesma carreira e banca (outro orgao ou outro cargo); C = o resto.
    Se o banco nao tiver nenhuma prova do orgao, volta para a regra de estudo geral (e avisa)."""
    igual_base = mesmo(prova["carreira"], perfil["carreira"]) and mesmo(prova["banca"], perfil["banca"])
    if not igual_base:
        return "C"
    cargo_igual = mesmo(prova["cargo"], perfil["cargo"])
    if perfil.get("orgao_ativo"):
        return "A" if cargo_igual and mesmo(prova["inst"], perfil["orgao"]) else "B"
    return "A" if cargo_igual else "B"


def descricao_grupos(perfil):
    if perfil.get("orgao_ativo"):
        return {"A": f"mesmo órgão ({perfil['orgao']}), carreira, banca e cargo", "B": "mesma carreira e banca, de outro órgão ou cargo", "C": "outra banca ou carreira"}
    return {"A": "mesma carreira, banca e cargo", "B": "mesma carreira e banca, outro cargo", "C": "outra banca ou outra carreira"}


def carregar_questoes(con, perfil, legado):
    esc = LE.escopo(con, perfil)       # perfil por bloco do edital (decisao 41); None = por disciplina do catalogo
    pontos = LE.pontos_do_escopo(con, perfil, esc)
    if esc is None:
        ass = {i: (c, n) for i, c, n in con.execute("select id,codigo,nome from assuntos where disciplina_id=?", (perfil["disciplina_id"],))}
    else:
        ass = LE.assuntos_do_escopo(con, pontos)
    cond, par = LE.clausula(esc, perfil["disciplina_id"])
    rows = con.execute(f"""select q.id,q.numero,q.situacao,p.nome,p.ano,p.banca,p.carreira,p.cargo,c.ponto_id,c.ponto2_id,c.assunto_provisorio_id,c.tipo_cobranca,p.instituicao,q.disciplina_id
        from questoes q join provas p on p.id=q.prova_id join classificacao c on c.questao_id=q.id
        where {cond}""", par).fetchall()
    qs = []
    for (qid, num, sit, prova, ano, banca, carr, cargo, p1, p2, aprov, tipo, inst, dq) in rows:
        p1, p2 = LE.efetivos(esc, perfil["disciplina_id"], dq, p1, p2, pontos)
        if esc is not None and not p1 and (dq != perfil["disciplina_id"] or aprov is None):
            continue        # questao de outra disciplina que o bloco nao toca; ou da disciplina, mas sem ponto no escopo nem assunto provisorio (decisao 54)
        g = grupo_da_prova(perfil, {"banca": banca, "carreira": carr, "cargo": cargo, "inst": inst})
        alvo = mesmo(carr, perfil["carreira"]) and mesmo(banca, perfil["banca"]) and mesmo(cargo, perfil["cargo"])
        idade = max(0, perfil["ano_referencia"] - ano)
        w = perfil["pesos"][g] * 0.5 ** (idade / perfil["meia_vida"])
        if legado or not p1:
            itens = [(None, aprov, 1.0)]
        elif p2:
            itens = [(p1, pontos[p1][2], 0.5), (p2, pontos[p2][2], 0.5)]
        else:
            itens = [(p1, pontos[p1][2], 1.0)]
        qs.append({"id": qid, "numero": num, "situacao": sit, "prova": prova, "ano": ano, "grupo": g, "alvo": alvo, "w": w, "itens": itens, "tipo": tipo,
                   "banca": banca or "", "carreira": carr or "", "cargo": cargo or "", "inst": inst or ""})
    return qs, ass, pontos


def freq(qs, chaves, nivel):
    """nivel 'a' = assunto, 'p' = ponto. Cada questao reparte seu peso entre seus itens."""
    soma = collections.defaultdict(float)
    bruto = collections.defaultdict(float)
    for q in qs:
        for pt, a, f in q["itens"]:
            k = a if nivel == "a" else pt
            if k is None:
                continue
            soma[k] += q["w"] * f
            bruto[k] += f
    tot = sum(soma.values())
    s2 = sum(q["w"] ** 2 for q in qs)
    neff = tot * tot / s2 if s2 else 0
    out = {}
    for k in chaves:
        p = soma[k] / tot if tot else 0
        lo, hi = wilson(p, neff)
        out[k] = {"peso": soma[k], "n": bruto[k], "p": p, "lo": lo, "hi": hi}
    return out, tot, neff


def top(f, k):
    return [c for c, _ in sorted(f.items(), key=lambda kv: -kv[1]["p"])[:k]]


def grupos(f, K):
    uni = 1 / K
    return {c: ("Cai muito" if v["lo"] > uni else "Cai pouco" if v["hi"] < uni else "Cai às vezes") for c, v in f.items()}


def retro(qs, chaves, nivel, k):
    provas = {}
    for q in qs:
        provas.setdefault(q["prova"], {"ano": q["ano"], "grupo": q["grupo"], "alvo": q["alvo"], "qs": []})["qs"].append(q)

    def acerto(info, top_set):
        hit = tot = 0.0
        for q in info["qs"]:
            for pt, a, f in q["itens"]:
                kk = a if nivel == "a" else pt
                tot += f
                hit += f if kk in top_set else 0
        return hit, tot

    temporal, loo = [], []
    for nome, info in sorted(provas.items(), key=lambda kv: (kv[1]["ano"], kv[0])):
        if not info["alvo"]:
            continue
        antes = [q for q in qs if q["ano"] < info["ano"]]
        if len(antes) >= 30:
            fa, _, _ = freq(antes, chaves, nivel)
            h, t = acerto(info, set(top(fa, k)))
            temporal.append({"prova": nome, "n": round(t, 1), "acertos": round(h, 1), "pct": round(100 * h / t, 1)})
        resto = [q for q in qs if q["prova"] != nome]
        fa, _, _ = freq(resto, chaves, nivel)
        h, t = acerto(info, set(top(fa, k)))
        loo.append({"prova": nome, "n": round(t, 1), "acertos": round(h, 1), "pct": round(100 * h / t, 1)})

    def med(L):
        return round(100 * sum(r["acertos"] for r in L) / sum(r["n"] for r in L), 1) if L else None

    return {"k": k, "temporal": temporal, "loo": loo, "media_temporal": med(temporal), "media_loo": med(loo), "acaso": round(100 * k / len(chaves), 1)}


def analisar(con, perfil, legado=False, universo=None):
    universo = universo or perfil["universo"]
    qs_all, ass, pontos = carregar_questoes(con, perfil, legado)
    qs_all = [q for q in qs_all if em_universo(q, universo["filtro"])]
    if not [q for q in qs_all if q["situacao"] in VALIDAS]:
        sys.exit(f"O universo «{universo['nome']}» não tem nenhuma questão válida nesta disciplina. Escolha outro universo.")
    cod_ass = {i: c for i, (c, n) in ass.items()}
    nome_ass = {c: n for _, (c, n) in ass.items()}
    for q in qs_all:
        q["itens"] = [(pt, cod_ass[a], f) for pt, a, f in q["itens"]]
    qs = [q for q in qs_all if q["situacao"] in VALIDAS]
    usados_a = sorted({a for q in qs for _, a, _ in q["itens"]})
    f_a, tot, neff = freq(qs, usados_a, "a")
    g_a = grupos(f_a, len(usados_a))
    res = {"perfil": {k: perfil[k] for k in ("id", "nome", "banca", "carreira", "cargo", "ano_referencia", "meia_vida", "pesos")},
           "modo": "legado" if legado else "pontos",
           "universo": {"id": universo["id"], "nome": universo["nome"], "filtro": universo["filtro"]},
           "n_total": len(qs_all), "n_validas": len(qs), "n_anuladas_ou_fora": len(qs_all) - len(qs),
           "n_provas": len({q["prova"] for q in qs}), "provas_por_grupo": {g: len({q["prova"] for q in qs if q["grupo"] == g}) for g in "ABC"},
           "soma_pesos": round(tot, 2), "n_efetivo": round(neff, 1), "K_assuntos": len(usados_a)}
    res["assuntos"] = {c: {"nome": nome_ass[c], "n": round(v["n"], 1), "peso": round(v["peso"], 2), "p": round(100 * v["p"], 1),
                           "lo": round(100 * v["lo"], 1), "hi": round(100 * v["hi"], 1),
                           "provas": len({q["prova"] for q in qs for _, a, _ in q["itens"] if a == c}), "grupo": g_a[c]} for c, v in f_a.items()}
    acum = 0
    n80 = 0
    for c in sorted(f_a, key=lambda c: -f_a[c]["p"]):
        acum += f_a[c]["p"]
        n80 += 1
        if acum >= 0.8:
            break
    res["n_assuntos_80pct"] = n80
    cob = collections.defaultdict(float)
    for q in qs:
        cob[q["tipo"]] += q["w"]
    tc = sum(cob.values())
    res["cobranca_pct"] = {k: round(100 * v / tc, 1) for k, v in sorted(cob.items(), key=lambda kv: -kv[1])}
    res["retro_assuntos"] = retro(qs, usados_a, "a", 4)
    if not legado:
        chaves_p = sorted({pt for q in qs for pt, _, _ in q["itens"] if pt})
        f_p, _, _ = freq(qs, chaves_p, "p")
        g_p = grupos(f_p, len(chaves_p))
        res["K_pontos"] = len(chaves_p)
        res["pontos"] = {pontos[p][0]: {"texto": pontos[p][1], "assunto": cod_ass[pontos[p][2]], "n": round(v["n"], 1), "peso": round(v["peso"], 2),
                                       "p": round(100 * v["p"], 1), "lo": round(100 * v["lo"], 1), "hi": round(100 * v["hi"], 1),
                                       "provas": len({q["prova"] for q in qs for pt, _, _ in q["itens"] if pt == p}), "grupo": g_p[p]} for p, v in f_p.items()}
        res["pontos_com_1_questao"] = sum(1 for p in chaves_p if f_p[p]["n"] <= 1)
        res["pontos_sem_questao"] = sorted(pontos[p][0] for p in pontos if p not in chaves_p)
        res["good_turing_pontos_pct"] = round(100 * res["pontos_com_1_questao"] / len(qs), 1)
        res["retro_pontos"] = retro(qs, chaves_p, "p", 10)
    res["avisos"] = list(perfil["avisos_grupo"])
    res["grupos_desc"] = perfil["desc_grupos"]
    grupos_presentes = [g for g in "ABC" if res["provas_por_grupo"][g]]
    if len(grupos_presentes) == 1:
        res["avisos"].append(f"Neste universo todas as provas são do grupo {grupos_presentes[0]}: o peso de semelhança é igual para todas e só a recência diferencia.")
    if not any(q["alvo"] for q in qs):
        res["avisos"].append("Nenhuma prova do tipo do perfil (mesma carreira, banca e cargo) no universo: o teste retroativo não tem alvo.")
    if res["provas_por_grupo"]["A"] < 5:
        res["avisos"].append("Menos de 5 provas do grupo A: teste retroativo é ruído (Guia 1, seção 8).")
    if res["n_efetivo"] < 100:
        res["avisos"].append("Número efetivo pequeno: faixas de Wilson largas.")
    return res


def para_md(r, disc):
    L = [f"# Análise — {disc} (perfil {r['perfil']['id']}: {r['perfil']['nome']})", "",
         f"Universo: **{r['universo']['nome']}** (filtro: {json.dumps(r['universo']['filtro'], ensure_ascii=False) if r['universo']['filtro'] else 'nenhum'}).", "",
         f"Modo: **{r['modo']}**. Banca {r['perfil']['banca']}, cargo {r['perfil']['cargo']}, ano de referência {r['perfil']['ano_referencia']}, meia-vida {r['perfil']['meia_vida']} anos, pesos {r['perfil']['pesos']}.", "",
         f"Amostra: {r['n_validas']} questões válidas de {r['n_total']} ({r['n_anuladas_ou_fora']} fora: anuladas/desatualizadas) em {r['n_provas']} provas (grupos {r['provas_por_grupo']}; A = {r['grupos_desc']['A']}; B = {r['grupos_desc']['B']}; C = {r['grupos_desc']['C']}). Soma dos pesos {r['soma_pesos']}; **número efetivo {r['n_efetivo']}**.", ""]
    for a in r["avisos"]:
        L.append(f"> Aviso: {a}")
    L += ["", "## Assuntos", "", "| Assunto | Nome | Questões | % | Faixa (Wilson) | Provas | Grupo |", "|---|---|---|---|---|---|---|"]
    for c, v in sorted(r["assuntos"].items(), key=lambda kv: -kv[1]["p"]):
        L.append(f"| {c} | {v['nome']} | {v['n']} | {v['p']} | {v['lo']}–{v['hi']} | {v['provas']} | {v['grupo']} |")
    ra = r["retro_assuntos"]
    L += ["", f"Concentração: {r['n_assuntos_80pct']} de {r['K_assuntos']} assuntos somam 80%.", f"Tipo de cobrança (ponderado, %): {r['cobranca_pct']}", "",
          f"Teste retroativo (assuntos, top {ra['k']}): temporal {ra['media_temporal']}% · uma prova escondida {ra['media_loo']}% · acaso {ra['acaso']}%."]
    if "pontos" in r:
        L += ["", "## Pontos", "", "| Ponto | Texto | Assunto | Questões | % | Faixa | Provas | Grupo |", "|---|---|---|---|---|---|---|---|"]
        for c, v in sorted(r["pontos"].items(), key=lambda kv: -kv[1]["p"]):
            L.append(f"| {c} | {v['texto']} | {v['assunto']} | {v['n']} | {v['p']} | {v['lo']}–{v['hi']} | {v['provas']} | {v['grupo']} |")
        rp = r["retro_pontos"]
        L += ["", f"Pontos com 1 questão só: {r['pontos_com_1_questao']} ({r['good_turing_pontos_pct']}% das questões; indício de pontos ainda não vistos, Good-Turing). Pontos sem nenhuma questão válida: {', '.join(r['pontos_sem_questao']) or 'nenhum'}.",
              f"Teste retroativo (pontos, top {rp['k']}): temporal {rp['media_temporal']}% · uma prova escondida {rp['media_loo']}% · acaso {rp['acaso']}%."]
    return "\n".join(L) + "\n"


def comparar(con, perfil):
    """Compara todos os universos cadastrados no MESMO alvo: as provas do grupo A do perfil (de qualquer universo).
    Para cada prova-alvo, treina com as questoes do universo que nao sejam dessa prova (temporal: so anos anteriores)
    e mede quantas questoes da prova caem nos 4 assuntos mais frequentes. Assim os universos sao comparaveis entre si."""
    qs_all, ass, pontos = carregar_questoes(con, perfil, False)
    cod_ass = {i: c for i, (c, n) in ass.items()}
    for q in qs_all:
        q["itens"] = [(pt, cod_ass[a], f) for pt, a, f in q["itens"]]
    validas = [q for q in qs_all if q["situacao"] in VALIDAS]
    chaves = sorted({a for q in validas for _, a, _ in q["itens"]})
    alvos = collections.defaultdict(list)
    for q in validas:
        if q["alvo"]:
            alvos[(q["ano"], q["prova"])].append(q)
    linhas = []
    for uid, nome, filtro in con.execute("select id,nome,filtro from universos order by id").fetchall():
        filtro = json.loads(filtro)
        U = [q for q in validas if em_universo(q, filtro)]
        if not U:
            continue
        s2 = sum(q["w"] ** 2 for q in U)
        neff = (sum(q["w"] for q in U) ** 2 / s2) if s2 else 0
        res_t = [0.0, 0.0]
        res_l = [0.0, 0.0]
        for (ano, prova), alvo in sorted(alvos.items()):
            n = sum(fr for q in alvo for _, a, fr in q["itens"])
            treino = [q for q in U if q["prova"] != prova]
            if treino:
                f, _, _ = freq(treino, chaves, "a")
                t4 = set(top(f, 4))
                res_l[0] += sum(fr for q in alvo for _, a, fr in q["itens"] if a in t4)
                res_l[1] += n
            antes = [q for q in treino if q["ano"] < ano]
            if len(antes) >= 30:
                f, _, _ = freq(antes, chaves, "a")
                t4 = set(top(f, 4))
                res_t[0] += sum(fr for q in alvo for _, a, fr in q["itens"] if a in t4)
                res_t[1] += n

        def pct(r):
            return round(100 * r[0] / r[1], 1) if r[1] else None

        linhas.append({"id": uid, "nome": nome, "provas": len({q["prova"] for q in U}), "questoes": len(U), "n_efetivo": round(neff, 1),
                       "temporal": pct(res_t), "loo": pct(res_l), "n_alvo_temporal": round(res_t[1]), "n_alvo_loo": round(res_l[1])})
    acaso = round(400 / len(chaves), 1)
    L = [f"# Comparação de universos — perfil {perfil['id']} ({perfil['nome']})", "",
         f"Alvo fixo: as {len(alvos)} provas do tipo do perfil (mesma carreira, banca e cargo, de qualquer órgão) (banca {perfil['banca']}, cargo {perfil['cargo']}). Para cada universo, o modelo é treinado só com as questões do universo (sem a prova-alvo) e mede quantas questões da prova caem nos 4 assuntos mais frequentes. Acaso: {acaso}%.", "",
         "| Universo | Provas | Questões | N efetivo | Temporal | Uma prova escondida |", "|---|---|---|---|---|---|"]
    for l in sorted(linhas, key=lambda x: -(x["loo"] or 0)):
        L.append(f"| {l['nome']} | {l['provas']} | {l['questoes']} | {l['n_efetivo']} | {l['temporal']}% (n={l['n_alvo_temporal']}) | {l['loo']}% (n={l['n_alvo_loo']}) |")
    L += ["", "Leitura: diferenças de poucos pontos entre universos são ruído (as provas-alvo somam poucas questões). Não escolha o universo só pelo maior número; escolha pelo que representa o seu concurso e use esta tabela para ver se o universo mais estreito perde ou ganha de verdade.",
          "Aviso: os universos que contêm as provas-alvo as usam para prever umas às outras (sempre sem a própria prova avaliada); universos sem elas (ex.: só Promotor) preveem de fora."]
    return linhas, "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Motor de análise (Guia 1) de um perfil; grava banco/analise/<disciplina>_perfil<ID>.json e .md (só lê o banco).")
    ap.add_argument("--perfil", type=int, default=1, help="id do perfil (padrão: 1)")
    ap.add_argument("--universo", type=int, help="usa outro universo (filtro de quais questões entram) em vez do do perfil")
    ap.add_argument("--legado", action="store_true", help="reproduz a conta antiga (assunto provisório, sem segundo ponto)")
    ap.add_argument("--comparar", action="store_true", help="compara todos os universos no mesmo alvo e grava a tabela em banco/analise/")
    args = ap.parse_args()
    pid, legado = args.perfil, args.legado
    con = sqlite3.connect(DB)
    perfil = carregar_perfil(con, pid)
    if args.universo is not None:
        perfil["universo"] = carregar_universo(con, args.universo)
    disc = con.execute("select nome from disciplinas where id=?", (perfil["disciplina_id"],)).fetchone()[0]
    out = BASE / "banco" / "analise"
    out.mkdir(exist_ok=True)
    if args.comparar:
        linhas, md = comparar(con, perfil)
        arq = out / f"{disc.lower().replace(' ', '_')}_perfil{pid}_comparacao_universos.md"
        arq.write_text(md, encoding="utf-8")
        for l in linhas:
            print(l["id"], l["nome"], "| provas", l["provas"], "| n ef.", l["n_efetivo"], "| temporal", l["temporal"], "| LOO", l["loo"])
        print("gravado:", arq)
        return
    r = analisar(con, perfil, legado)
    padrao = r["universo"]["id"] in (None, perfil.get("universo_id"))
    stem = f"{disc.lower().replace(' ', '_')}_perfil{pid}" + ("" if padrao else f"_universo{r['universo']['id']}") + ("_legado" if legado else "")
    (out / f"{stem}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{stem}.md").write_text(para_md(r, disc), encoding="utf-8")
    ra = r["retro_assuntos"]
    print(f"{stem}: n efetivo {r['n_efetivo']} | válidas {r['n_validas']} | retro assuntos temporal {ra['media_temporal']} LOO {ra['media_loo']} acaso {ra['acaso']}")
    if "retro_pontos" in r:
        rp = r["retro_pontos"]
        print("pontos: temporal", rp["media_temporal"], "LOO", rp["media_loo"], "acaso", rp["acaso"])


if __name__ == "__main__":
    main()
