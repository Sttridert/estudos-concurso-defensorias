#!/usr/bin/env python3
"""Grupo B (Catalogar), M6: publicação ÚNICA dos rascunhos v2 no banco. A simulação (--simular) não grava nada; a gravação (--aplicar) só roda quando o usuário mandar.

Uso (sempre com `python -I`):
  python -I scripts/catalogar_publicar.py --simular [--banco ARQ] [--saida RELATORIO.json]
  python -I scripts/catalogar_publicar.py --aplicar [--banco ARQ] [--sim-do-usuario]   # GRAVA; no banco padrão exige --sim-do-usuario

Desenho (decisões 52 a 55; a gravação real só será escrita depois de o usuário aprovar este relatório):
  - Tópico (ponto) que o v2 MANTÉM (uid "v1:<código antigo>"): o MESMO registro do banco é reaproveitado (mesmo id); mudam código, texto,
    descrição e assunto. Assim todas as ligações por id (classificação, itens e frases de edital, fontes, propostas) continuam valendo, sem cópia.
  - Tópico NOVO: linha nova. Tópico FUNDIDO (lixeira com destino) ou APAGADO com destino: as ligações são reapontadas ao destino e o registro
    é arquivado (ativo = 0, código com sufixo "#v1"). Tópico que MUDA DE DISCIPLINA (Penal PE02 para Criminologia): o mesmo registro passa à disciplina nova.
  - Assunto mantido: o mesmo registro é reaproveitado; novo: linha nova; removido: só some se nada mais o referencia, senão fica com sufixo "#v1".
  - Classificação das questões: continua ligada ao mesmo registro. Quando o tópico mudou de sentido (renomeado, movido, fundido, mudou de disciplina),
    a classificação é marcada "migrada" (nunca "revisada"); a reclassificação fina é do grupo C.
  - Antes de gravar: cópia do banco em banco/backup, registro em log_alteracoes, depois `71 exportar` regenera dados/catalogo e dados/classificacao.
A simulação confere se o banco ainda bate com a base v1 de cada rascunho e conta o que cada operação toca.
"""
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rascunho as R  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
CAT = RAIZ / "dados" / "catalogo"
TABELAS_PONTO = [("classificacao", "ponto_id"), ("classificacao", "ponto2_id"), ("edital_item_pontos", "ponto_id"), ("edital_frase_destinos", "ponto_id"),
                 ("edital_pontos", "ponto_id"), ("edital_pontos_fora", "ponto_id"), ("ponto_fontes", "ponto_id"), ("pontos_propostos", "ponto_id")]
# tópicos que migram para OUTRA disciplina como fusão (código v1 do banco -> (rascunho, código v1 do destino)); None = a decidir
DESTINOS_FUSAO = {"PI06.01": ("direito-penal", "PE13.01"), "PI06.02": ("direito-administrativo", "AD14.03"), "PI06.03": ("direito-constitucional", "CO02.02")}
ACOES_SEM_MUDANCA = {"mantido", "renumerado"}


def carregar_rascunhos():
    out = {}
    for p in sorted(CAT.glob("_rascunho_*_v2.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[d["slug"]] = d
    return out


SUFIXO_MIGRADA = " | migrada v1 para v2"


def _gravar(con, drafts):
    """Grava a publicação dentro da transação aberta. Devolve o resumo; levanta AssertionError se uma conferência falhar."""
    import datetime
    agora = datetime.datetime.now().isoformat(timespec="seconds")
    hoje = datetime.date.today().isoformat()
    q = lambda s, p=(): con.execute(s, p).fetchall()  # noqa: E731
    disc_id = {n: i for i, n in q("select id,nome from disciplinas")}
    pts = {(d, c): i for i, d, c in q("select p.id,di.nome,p.codigo from pontos p join disciplinas di on di.id=p.disciplina_id")}
    ass = {(d, c): i for i, d, c in q("select a.id,di.nome,a.codigo from assuntos a join disciplinas di on di.id=a.disciplina_id")}
    cod_ponto = {i: c for (d, c), i in pts.items()}
    cod_assunto = {i: c for (d, c), i in ass.items()}
    n_classif_antes = q("select count(*) from classificacao")[0][0]
    resumo = collections.Counter()

    origem_crim = {}
    if "criminologia" in drafts:
        cat = json.loads((CAT / "criminologia.json").read_text(encoding="utf-8"))
        for p in cat["pontos"]:
            m = re.search(r"migrado de (PE\d\d\.\d\d)", p.get("origem") or "")
            if m:
                origem_crim[p["codigo"]] = m.group(1)
        nome_c = drafts["criminologia"]["disciplina"]
        if nome_c not in disc_id:
            disc_id[nome_c] = con.execute("insert into disciplinas(nome) values (?)", (nome_c,)).lastrowid
            resumo["disciplina criada"] += 1

    def id_ponto_v1(slug, d, cod):
        if slug == "criminologia":
            return pts[("Direito Penal", origem_crim[cod])]
        return pts[(d["disciplina"], cod)]

    # ---- 1. plano: o que muda de sentido, fusões, assuntos que somem (tudo resolvido ANTES de mexer em códigos)
    cods_final, mapas = {}, {}
    marcar = set()
    fusoes = []                                   # (id origem, id destino, mesma disciplina?)
    for slug, d in drafts.items():
        cods_final[slug] = R.codigos(d)
        mapas[slug] = {m["uid"]: m for m in R.mapa(d)}
        for a in d["assuntos"]:
            for p in a["pontos"]:
                if p.get("antigo"):
                    rid = id_ponto_v1(slug, d, p["antigo"])
                    acao = "mudou de disciplina" if slug == "criminologia" else mapas[slug][p["uid"]]["acao"]
                    if acao not in ACOES_SEM_MUDANCA:
                        marcar.add(rid)
        for x in d.get("lixeira", []):
            nome = d["disciplina"]
            if "Criminologia" in (x.get("nota") or "") and nome == "Direito Penal":
                continue                           # o registro já é reaproveitado pela Criminologia
            src = pts[(nome, x["antigo"])]
            if x.get("destino"):
                dst, mesma = pts[(nome, x["destino"].replace("v1:", ""))], True
            elif x["antigo"] in DESTINOS_FUSAO and DESTINOS_FUSAO[x["antigo"]][1]:
                s2, c2 = DESTINOS_FUSAO[x["antigo"]]
                dst, mesma = pts[(drafts[s2]["disciplina"], c2)], False
            else:
                raise AssertionError(f"ponto sem destino: {nome} {x['antigo']}")
            fusoes.append((src, dst, mesma))
            marcar.add(src)

    # ---- 2. marca "migrada" na classificação (antes de reapontar)
    if marcar:
        con.execute("create temp table _marcar(id integer primary key)")
        con.executemany("insert into _marcar values (?)", [(i,) for i in marcar])
        n = con.execute("""update classificacao set origem = coalesce(origem,'') || ?, atualizado_em = ?
                           where (ponto_id in (select id from _marcar) or ponto2_id in (select id from _marcar))
                             and coalesce(origem,'') not like '%migrada v1 para v2%'""", (SUFIXO_MIGRADA, agora)).rowcount
        resumo["classificações marcadas migrada (questões)"] = n
        con.execute("drop table _marcar")

    # ---- 3. códigos provisórios em todas as linhas das disciplinas afetadas (evita choque da regra de código único)
    afetadas = [disc_id[d["disciplina"]] for d in drafts.values()]
    marcas_disc = ",".join("?" * len(afetadas))
    con.execute(f"update pontos set codigo = '~' || id where disciplina_id in ({marcas_disc})", afetadas)
    con.execute(f"update assuntos set codigo = '~' || id where disciplina_id in ({marcas_disc})", afetadas)

    # ---- 4. assuntos e pontos do v2
    for slug, d in drafts.items():
        nome, did = d["disciplina"], disc_id[d["disciplina"]]
        cods = cods_final[slug]
        for a in d["assuntos"]:
            if a.get("antigo") and slug != "criminologia":
                aid = ass[(nome, a["antigo"])]
                con.execute("update assuntos set codigo=?, nome=?, descricao=? where id=?", (cods[a["uid"]], a["nome"], a.get("descricao"), aid))
                resumo["assuntos atualizados"] += 1
            else:
                aid = con.execute("insert into assuntos(disciplina_id,codigo,nome,descricao) values (?,?,?,?)", (did, cods[a["uid"]], a["nome"], a.get("descricao"))).lastrowid
                resumo["assuntos inseridos"] += 1
            for p in a["pontos"]:
                if p.get("antigo"):
                    rid = id_ponto_v1(slug, d, p["antigo"])
                    con.execute("update pontos set disciplina_id=?, assunto_id=?, codigo=?, texto=?, descricao=?, ativo=1 where id=?",
                                (did, aid, cods[p["uid"]], p["texto"], p.get("descricao"), rid))
                    resumo["pontos atualizados (mesmo id)"] += 1
                else:
                    con.execute("insert into pontos(disciplina_id,assunto_id,codigo,texto,descricao,origem,ativo,criado_em) values (?,?,?,?,?,?,1,?)",
                                (did, aid, cods[p["uid"]], p["texto"], p.get("descricao"), p.get("origem") or "rascunho v2", hoje))
                    resumo["pontos inseridos"] += 1

    # ---- 5. fusões: reaponta as ligações, depois arquiva o ponto de origem
    for src, dst, mesma in fusoes:
        con.execute("update classificacao set ponto_id=? where ponto_id=?", (dst, src))
        con.execute("update classificacao set ponto2_id=? where ponto2_id=?", (dst, src))
        con.execute("update classificacao set ponto2_id=NULL where ponto2_id=ponto_id")
        for tb, col in TABELAS_PONTO:
            if tb == "classificacao":
                continue
            con.execute(f"update or ignore {tb} set {col}=? where {col}=?", (dst, src))
            con.execute(f"delete from {tb} where {col}=?", (src,))
        novo_ass = con.execute("select assunto_id from pontos where id=?", (dst,)).fetchone()[0] if mesma else con.execute("select assunto_id from pontos where id=?", (src,)).fetchone()[0]
        con.execute("update pontos set ativo=0, codigo=?, assunto_id=? where id=?", (cod_ponto[src] + "#v1", novo_ass, src))
        resumo["pontos fundidos e arquivados"] += 1

    # ---- 6. assuntos que somem
    for slug, d in drafts.items():
        for x in d.get("lixeira_assuntos", []):
            aid = ass.get((d["disciplina"], x["antigo"]))
            if aid is None:
                continue
            con.execute("update classificacao set assunto_provisorio_id=NULL where assunto_provisorio_id=?", (aid,))
            if con.execute("select count(*) from pontos where assunto_id=?", (aid,)).fetchone()[0]:
                con.execute("update assuntos set codigo=? where id=?", (cod_assunto[aid] + "#v1", aid))
                resumo["assuntos arquivados (ainda têm pontos arquivados)"] += 1
            else:
                con.execute("delete from assuntos where id=?", (aid,))
                resumo["assuntos removidos"] += 1

    # ---- 7. conferências finais (se falhar, a transação inteira é desfeita)
    for slug, d in drafts.items():
        did = disc_id[d["disciplina"]]
        esperado = {c for u, c in cods_final[slug].items() if not u.startswith("v1:") or "." in u}
        pts_ativos = {c for (c,) in q("select codigo from pontos where disciplina_id=? and ativo=1", (did,))}
        ass_todos = {c for (c,) in q("select codigo from assuntos where disciplina_id=? and codigo not like '%#v1'", (did,))}
        esp_p = {cods_final[slug][p["uid"]] for a in d["assuntos"] for p in a["pontos"]}
        esp_a = {cods_final[slug][a["uid"]] for a in d["assuntos"]}
        assert pts_ativos == esp_p, f"{d['disciplina']}: pontos ativos diferem do v2 ({len(pts_ativos)} contra {len(esp_p)})"
        assert ass_todos == esp_a, f"{d['disciplina']}: assuntos diferem do v2 ({len(ass_todos)} contra {len(esp_a)})"
    assert q("select count(*) from classificacao")[0][0] == n_classif_antes, "o número de classificações mudou"
    assert q("select count(*) from classificacao c join pontos p on p.id=c.ponto_id where p.ativo=0")[0][0] == 0, "classificação ainda aponta para ponto arquivado"
    assert q("select count(*) from classificacao c join pontos p on p.id=c.ponto2_id where p.ativo=0")[0][0] == 0, "ponto2 ainda aponta para ponto arquivado"
    assert q("select count(*) from pontos where codigo like '~%'")[0][0] == 0 and q("select count(*) from assuntos where codigo like '~%'")[0][0] == 0, "sobrou código provisório"
    assert not q("pragma foreign_key_check"), "violação de chave estrangeira"
    resumo["classificações no banco"] = n_classif_antes
    con.execute("insert into log_alteracoes(quem,o_que) values (?,?)",
                ("catalogar_publicar", "publicação única dos catálogos v2 (M6): " + "; ".join(f"{k}: {v}" for k, v in resumo.items())))
    return resumo


def aplicar_cmd(args):
    import datetime
    banco = Path(args[args.index("--banco") + 1]) if "--banco" in args else BANCO
    padrao = banco.resolve() == BANCO.resolve()
    if padrao and "--sim-do-usuario" not in args:
        print("RECUSADO: gravar no banco padrão exige --sim-do-usuario (só depois de o usuário mandar gravar).")
        return 2
    drafts = carregar_rascunhos()
    if len(drafts) != 12:
        print(f"RECUSADO: esperava 12 rascunhos v2 e achei {len(drafts)}.")
        return 2
    if padrao:
        dest = RAIZ / "banco" / "backup" / f"estudos_antes_publicar_v2_{datetime.date.today().isoformat()}.db"
        origem = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        copia = sqlite3.connect(dest)
        origem.backup(copia)
        copia.close()
        origem.close()
        print("cópia do banco:", dest)
    con = sqlite3.connect(banco)
    con.isolation_level = None
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.execute("BEGIN IMMEDIATE")
        resumo = _gravar(con, drafts)
        con.execute("COMMIT")
    except Exception as e:                        # noqa: BLE001
        con.execute("ROLLBACK")
        print("DESFEITO (nada foi gravado):", type(e).__name__, e)
        return 1
    print("GRAVADO:")
    for k, v in resumo.items():
        print(f"   {k:60} {v}")
    if padrao:
        import importlib.util
        import lib_catalogo as LC
        spec = importlib.util.spec_from_file_location("catalogo71", Path(__file__).resolve().parent / "71_catalogo_e_classificacao.py")
        m71 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m71)
        con2 = sqlite3.connect(banco)
        m71.exportar(con2, CAT, RAIZ / "dados" / "classificacao")
        con2.close()
        for slug in drafts:
            LC.definir(slug, "provisorio", "publicação única dos catálogos v2 (M6, 20/11/2026); nenhuma classificação revisada por humano; reclassificação fina é do grupo C",
                       versao="v2", riscos=["rascunho da IA homologado em amostra pelo usuário; classificação migrada pelo mapa, não revisada"])
    return 0


def main():
    args = sys.argv[1:]
    if "--aplicar" in args:
        return aplicar_cmd(args)
    if "--simular" not in args:
        print("Rode com --simular (só leitura) ou --aplicar (grava).")
        return 2
    banco = Path(args[args.index("--banco") + 1]) if "--banco" in args else BANCO
    saida = Path(args[args.index("--saida") + 1]) if "--saida" in args else None
    con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    q = lambda s, p=(): con.execute(s, p).fetchall()  # noqa: E731
    drafts = carregar_rascunhos()
    disc_id = {n: i for i, n in q("select id,nome from disciplinas")}
    pts = {}                                   # (disciplina, codigo) -> (id, texto, assunto codigo)
    for i, d, c, t, ac in q("select p.id,di.nome,p.codigo,p.texto,a.codigo from pontos p join disciplinas di on di.id=p.disciplina_id join assuntos a on a.id=p.assunto_id"):
        pts[(d, c)] = (i, t, ac)
    ass = {(d, c): (i, n) for i, d, c, n in q("select a.id,di.nome,a.codigo,a.nome from assuntos a join disciplinas di on di.id=a.disciplina_id")}
    refs = collections.defaultdict(lambda: collections.Counter())    # ponto id -> {tabela.coluna: n}
    for tb, col in TABELAS_PONTO:
        for pid, n in q(f"select {col},count(*) from {tb} where {col} is not null group by {col}"):
            refs[pid][f"{tb}.{col}"] = n
    aviso, problemas = [], []
    resumo = {}
    linhas_class = collections.Counter()
    sem_destino = []

    # ---- origem dos tópicos de Criminologia: PE02.nn do Direito Penal (campo origem "migrado de PE02.nn")
    origem_crim = {}
    if "criminologia" in drafts:
        for a in drafts["criminologia"]["base_v1"]["pontos"].items():
            pass
        cat = json.loads((CAT / "criminologia.json").read_text(encoding="utf-8"))
        for p in cat["pontos"]:
            m = re.search(r"migrado de (PE\d\d\.\d\d)", p.get("origem") or "")
            if m:
                origem_crim[p["codigo"]] = m.group(1)

    def linha_banco(slug, d, cod_v1):
        """Registro do banco que corresponde ao código v1 do rascunho."""
        if slug == "criminologia":
            return pts.get(("Direito Penal", origem_crim.get(cod_v1, "")))
        return pts.get((d["disciplina"], cod_v1))

    print(f"== SIMULAÇÃO DA PUBLICAÇÃO ÚNICA (M6): {len(drafts)} rascunhos v2; banco {banco.name}; NADA É GRAVADO\n")
    destino_final = {}          # (slug, uid) -> id do registro do banco que recebe
    total = collections.Counter()
    for slug, d in drafts.items():
        nome = d["disciplina"]
        cods = R.codigos(d)
        mapa = {m["uid"]: m for m in R.mapa(d)}
        base_pts = d["base_v1"]["pontos"]
        r = collections.Counter()
        # confere que o banco ainda bate com a base v1 do rascunho
        for uid, b in base_pts.items():
            lb = linha_banco(slug, d, b["codigo"])
            if lb is None:
                problemas.append(f"{nome}: o ponto v1 {b['codigo']} não existe no banco (o banco mudou depois do rascunho?)")
            elif lb[1] != b["texto"]:
                aviso.append(f"{nome}: o texto de {b['codigo']} no banco difere do da base v1 do rascunho")
        # tópicos mantidos e novos
        for a in d["assuntos"]:
            for p in a["pontos"]:
                novo_cod = cods[p["uid"]]
                if p.get("antigo"):
                    b = base_pts.get(p["uid"])
                    lb = linha_banco(slug, d, b["codigo"]) if b else None
                    if lb is None:
                        continue
                    destino_final[(slug, p["uid"])] = lb[0]
                    acao = mapa[p["uid"]]["acao"]
                    nq = sum(v for k, v in refs[lb[0]].items() if k.startswith("classificacao"))
                    r["mantidos (mesmo id)"] += 1
                    if slug == "criminologia":
                        r["mudam de disciplina (Penal para Criminologia)"] += 1
                        acao = "mudou de disciplina"
                    if acao not in ACOES_SEM_MUDANCA:
                        linhas_class["migrada (tópico mudou de sentido: " + acao + ")"] += refs[lb[0]]["classificacao.ponto_id"] + refs[lb[0]]["classificacao.ponto2_id"]
                        r["com classificação marcada migrada"] += 1
                    else:
                        linhas_class["sem mudança de sentido (" + acao + ")"] += refs[lb[0]]["classificacao.ponto_id"] + refs[lb[0]]["classificacao.ponto2_id"]
                else:
                    r["novos (linha nova)"] += 1
        # fundidos / apagados
        for x in d.get("lixeira", []):
            cod = x["antigo"]
            lb = pts.get((nome, cod))
            nota = x.get("nota") or ""
            if "Criminologia" in nota and nome == "Direito Penal":
                r["saem para a Criminologia (mesmo registro)"] += 1
                continue
            if lb is None:
                problemas.append(f"{nome}: o ponto da lixeira {cod} não existe no banco")
                continue
            if x.get("destino"):
                dest_uid = x["destino"]
                dest_id = destino_final.get((slug, dest_uid))
                if dest_id is None:
                    # destino pode ser tópico mantido ainda não processado nesta rodada
                    dcod = dest_uid.replace("v1:", "")
                    dl = pts.get((nome, dcod))
                    dest_id = dl[0] if dl else None
                r["fundidos em outro tópico da mesma disciplina"] += 1
            elif cod in DESTINOS_FUSAO:
                s2, c2 = DESTINOS_FUSAO[cod]
                dest = pts.get((drafts[s2]["disciplina"], c2)) if c2 else None
                if dest is None:
                    sem_destino.append((nome, cod, x["texto"], sum(refs[lb[0]].values()), refs[lb[0]]["classificacao.ponto_id"]))
                r["fundidos em tópico de OUTRA disciplina"] += 1
            else:
                sem_destino.append((nome, cod, x["texto"], sum(refs[lb[0]].values()), refs[lb[0]]["classificacao.ponto_id"]))
                r["apagados sem destino"] += 1
                continue
            linhas_class["migrada (tópico fundido)"] += refs[lb[0]]["classificacao.ponto_id"] + refs[lb[0]]["classificacao.ponto2_id"]
            r["ligações a reapontar (todas as tabelas)"] += sum(refs[lb[0]].values())
        # assuntos
        a_antigos = {a["antigo"] for a in d["assuntos"] if a.get("antigo")}
        r["assuntos mantidos (mesmo id)"] += len(a_antigos)
        r["assuntos novos"] += sum(1 for a in d["assuntos"] if not a.get("antigo"))
        r["assuntos que somem (rebaixados ou apagados)"] += len(d.get("lixeira_assuntos", []))
        if slug == "criminologia":
            r["assuntos novos"] += r.pop("assuntos mantidos (mesmo id)", 0)   # CR01 não existe no banco
            r["assuntos mantidos (mesmo id)"] = 0
        if nome not in disc_id:
            r["DISCIPLINA NOVA no banco"] = 1
        resumo[nome] = dict(r)
        total.update(r)
        print(f"-- {nome}" + ("   (disciplina nova)" if nome not in disc_id else ""))
        for k, v in r.items():
            print(f"   {k:55} {v:5d}")

    print("\n== CLASSIFICAÇÃO DAS QUESTÕES (linhas ponto_id + ponto2_id afetadas)")
    for k, v in sorted(linhas_class.items(), key=lambda x: -x[1]):
        print(f"   {k:70} {v:5d}")
    tot_cls = q("select count(*) from classificacao where ponto_id is not null")[0][0] + q("select count(*) from classificacao where ponto2_id is not null")[0][0]
    print(f"   (total de ligações de classificação no banco: {tot_cls})")

    # ---- colisões ao reapontar (chaves primárias) e referências aos assuntos que somem
    print("\n== CONFERÊNCIAS DA GRAVAÇÃO")
    fusoes = []                                # (id origem, id destino)
    for slug, d in drafts.items():
        nome = d["disciplina"]
        for x in d.get("lixeira", []):
            lb = pts.get((nome, x["antigo"]))
            if lb is None or "Criminologia" in (x.get("nota") or ""):
                continue
            if x.get("destino"):
                dl = pts.get((nome, x["destino"].replace("v1:", "")))
            elif x["antigo"] in DESTINOS_FUSAO and DESTINOS_FUSAO[x["antigo"]][1]:
                s2, c2 = DESTINOS_FUSAO[x["antigo"]]
                dl = pts.get((drafts[s2]["disciplina"], c2))
            else:
                dl = None
            if dl:
                fusoes.append((lb[0], dl[0]))
    colisoes = collections.Counter()
    for o, dst in fusoes:
        for tb, col, outra in (("edital_item_pontos", "ponto_id", "item_id"), ("edital_pontos", "ponto_id", "edital_id"),
                               ("edital_pontos_fora", "ponto_id", "edital_id"), ("ponto_fontes", "ponto_id", "edital_origem")):
            n = q(f"select count(*) from {tb} a where a.{col}=? and exists (select 1 from {tb} b where b.{col}=? and b.{outra}=a.{outra})", (o, dst))[0][0]
            colisoes[tb] += n
    print(f"   {len(fusoes)} fusões; ligações que já existem no destino (serão mescladas sem duplicar): " + (", ".join(f"{k} {v}" for k, v in colisoes.items() if v) or "nenhuma"))
    for slug, d in drafts.items():
        for x in d.get("lixeira_assuntos", []):
            ai = ass.get((d["disciplina"], x["antigo"]))
            if ai:
                n = q("select count(*) from classificacao where assunto_provisorio_id=?", (ai[0],))[0][0]
                print(f"   assunto que some: {d['disciplina']} {x['antigo']} '{x['nome'][:44]}': {n} classificações o citam como assunto provisório (serão limpas)")
    print("\n== PONTOS QUE PEDEM DECISÃO ANTES DE GRAVAR (sem destino)")
    for nome, cod, texto, n, nq in sem_destino:
        print(f"   {nome} {cod} '{texto[:60]}': {n} ligações no banco, {nq} questões com ele como ponto principal")
    if not sem_destino:
        print("   nenhum")
    print("\n== AVISOS")
    for a in aviso:
        print("   " + a)
    if not aviso:
        print("   nenhum")
    print("\n== PROBLEMAS (impedem a gravação)")
    for pr in problemas:
        print("   " + pr)
    if not problemas:
        print("   nenhum")
    print("\n== O QUE A GRAVAÇÃO FARIA (não está implementada)")
    for passo in ("cópia do banco em banco/backup", "criar a disciplina Criminologia", "códigos em duas fases (provisórios, depois definitivos) para não violar a regra de código único",
                  "atualizar pontos e assuntos mantidos; inserir os novos; reapontar e arquivar os fundidos (ativo = 0, sufixo #v1)",
                  "marcar a classificação dos tópicos que mudaram de sentido como 'migrada' (revisada continua 0)",
                  "registrar tudo em log_alteracoes; atualizar dados/catalogo/_estado.json (v2, provisório)",
                  "rodar `71 exportar` (regenera dados/catalogo e dados/classificacao) e o motor `23` nos 11 perfis, comparando com banco/base-regressao-2026-11-16/"):
        print("   - " + passo)
    if saida:
        saida.write_text(json.dumps({"resumo": resumo, "classificacao": dict(linhas_class), "sem_destino": sem_destino, "avisos": aviso, "problemas": problemas},
                                    ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("\nrelatório gravado em", saida)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
