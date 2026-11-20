#!/usr/bin/env python3
"""Grupo B (Catalogar): publica rascunhos v2 no banco (disciplina por disciplina ou em lote). A gravação só roda quando o usuário mandar.

Uso (sempre com `python -I`; é preciso dizer QUAIS rascunhos: --disciplina SLUG (repetível) ou --todas):
  python -I scripts/catalogar_publicar.py --simular --disciplina SLUG [--disciplina SLUG2 ...] [--banco ARQ] [--saida RELATORIO.json]
  python -I scripts/catalogar_publicar.py --aplicar --disciplina SLUG [...] [--banco ARQ] [--sim-do-usuario]     # GRAVA; no banco padrão exige --sim-do-usuario

--simular   NÃO toca no banco: roda a MESMA gravação dentro de uma cópia temporária do banco e mostra o resumo, ou o erro que a gravaria.
--aplicar   cópia do banco em banco/backup, uma transação única com conferências finais (se qualquer uma falhar, tudo é desfeito), depois regenera
            dados/catalogo e dados/classificacao (`71 exportar`) e põe os catálogos publicados em "provisório" no estado (lib_catalogo).

Regras (decisões 52 a 55):
  - Ponto que o rascunho MANTÉM (uid "v1:<código>"): o MESMO registro do banco é reaproveitado (mesmo id); mudam código, texto, descrição e assunto.
    Assim classificação, itens e frases de edital, fontes e propostas (tudo ligado por id) continuam valendo, sem cópia.
  - Ponto NOVO: linha nova. Disciplina nova (rascunho do zero): a disciplina é criada se ainda não existir (e não pode já ter pontos).
  - Ponto na lixeira com destino: fundido. O destino é um ponto do mesmo rascunho (`destino`) ou de OUTRA disciplina (`destino_externo`: {disciplina, codigo},
    código ATUAL do banco; ver `catalogar_novo.py destino`). As ligações vão para o destino e o ponto é arquivado (ativo = 0, código com sufixo #v1, #v2...).
  - Ponto adotado por uma disciplina nova (`movido_para`): o mesmo registro passa à disciplina nova (os dois rascunhos têm de ser publicados juntos).
  - Assunto mantido: mesmo registro; novo: linha nova; que some: apagado se nada o referencia, senão fica com sufixo #v1.
  - Classificação das questões: continua ligada ao mesmo registro; quando o ponto mudou de sentido (renomeado, movido, fundido, de outra disciplina)
    ganha, no campo origem, " | migrada <base> para <alvo>" (nunca "revisada"). A reclassificação fina é do grupo C.
"""
import collections
import datetime
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rascunho as R  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
CAT = RAIZ / "dados" / "catalogo"
TABELAS_PONTO = [("classificacao", "ponto_id"), ("classificacao", "ponto2_id"), ("edital_item_pontos", "ponto_id"), ("edital_frase_destinos", "ponto_id"),
                 ("edital_pontos", "ponto_id"), ("edital_pontos_fora", "ponto_id"), ("ponto_fontes", "ponto_id"), ("pontos_propostos", "ponto_id")]
ACOES_SEM_MUDANCA = {"mantido", "renumerado"}


def carregar_rascunhos(slugs=None):
    """Rascunhos v2 de `CAT`. `slugs` = lista (só esses; todos têm de existir) ou None (todos)."""
    out = {}
    for p in sorted(CAT.glob("_rascunho_*_v2.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if slugs is None or d["slug"] in slugs:
            out[d["slug"]] = d
    faltam = [s for s in (slugs or []) if s not in out]
    if faltam:
        raise SystemExit("sem rascunho v2 para: " + ", ".join(faltam))
    return out


def _arquivar_codigo(con, tabela, disciplina_id, codigo):
    """Código com sufixo #v1, #v2... que ainda não existe na disciplina (publicações sucessivas não colidem)."""
    n = 1
    while con.execute(f"select 1 from {tabela} where disciplina_id=? and codigo=?", (disciplina_id, f"{codigo}#v{n}")).fetchone():
        n += 1
    return f"{codigo}#v{n}"


def _gravar(con, drafts):
    """Grava a publicação dentro da transação aberta. Devolve o resumo; levanta AssertionError se uma conferência falhar."""
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
    nomes_publicados = {d["disciplina"] for d in drafts.values()}

    # ---- 0. disciplinas novas
    for slug, d in drafts.items():
        nome = d["disciplina"]
        if d.get("do_zero"):
            tem = con.execute("select count(*) from pontos p join disciplinas di on di.id=p.disciplina_id where di.nome=?", (nome,)).fetchone()[0]
            assert not tem, f"{nome}: é um rascunho do zero, mas a disciplina já tem pontos no banco (use o editor a partir do catálogo atual)"
        if nome not in disc_id:
            disc_id[nome] = con.execute("insert into disciplinas(nome) values (?)", (nome,)).lastrowid
            resumo["disciplinas criadas"] += 1

    def banco_do_ponto(d, uid):
        """(disciplina, código) do registro do banco que corresponde a um ponto v1 do rascunho (pode ser adotado de outra disciplina)."""
        b = d["base_v1"]["pontos"][uid]
        if b.get("banco"):
            return b["banco"]["disciplina"], b["banco"]["codigo"], True
        return d["disciplina"], b["codigo"], False

    # ---- 1. plano: o que muda de sentido, fusões (tudo resolvido ANTES de mexer em códigos)
    cods_final, marcar = {}, collections.defaultdict(set)      # marcar: rótulo -> ids de ponto cuja classificação ganha a marca
    ids_mantidos = {}                                          # (slug, uid) -> id do registro
    fusoes = []                                                # (slug do rascunho, entrada da lixeira, id origem)
    for slug, d in drafts.items():
        cods_final[slug] = R.codigos(d)
        mapa = {m["uid"]: m for m in R.mapa(d)}
        rotulo = f" | migrada {d['versao_base']} para {d['versao_alvo']}"
        for a in d["assuntos"]:
            for p in a["pontos"]:
                if not p.get("antigo"):
                    continue
                disc, cod, adotado = banco_do_ponto(d, p["uid"])
                assert (disc, cod) in pts, f"{d['disciplina']}: o ponto {cod} de '{disc}' não existe no banco (o banco mudou depois do rascunho?)"
                if adotado and disc != d["disciplina"]:
                    assert disc in nomes_publicados, f"{d['disciplina']} adotou {cod} de '{disc}', que precisa ser publicada junto (use --disciplina nas duas)"
                rid = pts[(disc, cod)]
                ids_mantidos[(slug, p["uid"])] = rid
                acao = "mudou de disciplina" if (adotado and disc != d["disciplina"]) else mapa[p["uid"]]["acao"]
                resumo[f"mantidos: {acao}"] += 1
                if acao not in ACOES_SEM_MUDANCA:
                    marcar[rotulo].add(rid)
        for x in d.get("lixeira", []):
            if x.get("movido_para"):
                assert x["movido_para"] in drafts, f"{d['disciplina']}: o ponto {x['antigo']} foi adotado por '{x['movido_para']}', que precisa ser publicado junto"
                continue                                       # o registro é reaproveitado pela disciplina que o adotou
            assert (d["disciplina"], x["antigo"]) in pts, f"{d['disciplina']}: o ponto da lixeira {x['antigo']} não existe no banco"
            src = pts[(d["disciplina"], x["antigo"])]
            assert x.get("destino") or x.get("destino_externo"), f"ponto sem destino: {d['disciplina']} {x['antigo']} (defina o destino ou use catalogar_novo.py destino)"
            fusoes.append((slug, x, src))
            marcar[rotulo].add(src)

    # ---- 2. marca "migrada" na classificação (antes de reapontar)
    for rotulo, ids in marcar.items():
        con.execute("create temp table _marcar(id integer primary key)")
        con.executemany("insert into _marcar values (?)", [(i,) for i in ids])
        n = con.execute("""update classificacao set origem = coalesce(origem,'') || ?, atualizado_em = ?
                           where (ponto_id in (select id from _marcar) or ponto2_id in (select id from _marcar))
                             and coalesce(origem,'') not like ?""", (rotulo, agora, f"%{rotulo}%")).rowcount
        resumo["classificações marcadas migrada (questões)"] += n
        con.execute("drop table _marcar")

    # ---- 3. códigos provisórios em todas as linhas das disciplinas afetadas (evita choque da regra de código único)
    afetadas = [disc_id[d["disciplina"]] for d in drafts.values()]
    marcas_disc = ",".join("?" * len(afetadas))
    con.execute(f"update pontos set codigo = '~' || id where disciplina_id in ({marcas_disc})", afetadas)
    con.execute(f"update assuntos set codigo = '~' || id where disciplina_id in ({marcas_disc})", afetadas)

    # ---- 4. assuntos e pontos do rascunho
    ids_final = dict(ids_mantidos)
    for slug, d in drafts.items():
        nome, did = d["disciplina"], disc_id[d["disciplina"]]
        cods = cods_final[slug]
        for a in d["assuntos"]:
            if a.get("antigo") and (nome, a["antigo"]) in ass:
                aid = ass[(nome, a["antigo"])]
                con.execute("update assuntos set codigo=?, nome=?, descricao=? where id=?", (cods[a["uid"]], a["nome"], a.get("descricao"), aid))
                resumo["assuntos atualizados"] += 1
            else:
                aid = con.execute("insert into assuntos(disciplina_id,codigo,nome,descricao) values (?,?,?,?)", (did, cods[a["uid"]], a["nome"], a.get("descricao"))).lastrowid
                resumo["assuntos inseridos"] += 1
            for p in a["pontos"]:
                if p.get("antigo"):
                    rid = ids_mantidos[(slug, p["uid"])]
                    con.execute("update pontos set disciplina_id=?, assunto_id=?, codigo=?, texto=?, descricao=?, ativo=1 where id=?",
                                (did, aid, cods[p["uid"]], p["texto"], p.get("descricao"), rid))
                    resumo["pontos atualizados (mesmo id)"] += 1
                else:
                    ids_final[(slug, p["uid"])] = con.execute(
                        "insert into pontos(disciplina_id,assunto_id,codigo,texto,descricao,origem,ativo,criado_em) values (?,?,?,?,?,?,1,?)",
                        (did, aid, cods[p["uid"]], p["texto"], p.get("descricao"), p.get("origem") or "rascunho v2", hoje)).lastrowid
                    resumo["pontos inseridos"] += 1

    # ---- 5. fusões: reaponta as ligações, depois arquiva o ponto de origem
    for slug, x, src in fusoes:
        d = drafts[slug]
        de = x.get("destino_externo")
        if de:
            assert (de["disciplina"], de["codigo"]) in pts, f"destino externo inexistente: {de}"
            dst, mesma = pts[(de["disciplina"], de["codigo"])], False
        else:
            vivo = R._destino_final(d, x["uid"])
            assert vivo and (slug, vivo) in ids_final, f"{d['disciplina']}: o destino de {x['antigo']} não está mais no rascunho"
            dst, mesma = ids_final[(slug, vivo)], True
        con.execute("update classificacao set ponto_id=? where ponto_id=?", (dst, src))
        con.execute("update classificacao set ponto2_id=? where ponto2_id=?", (dst, src))
        con.execute("update classificacao set ponto2_id=NULL where ponto2_id=ponto_id")
        for tb, col in TABELAS_PONTO:
            if tb == "classificacao":
                continue
            con.execute(f"update or ignore {tb} set {col}=? where {col}=?", (dst, src))
            con.execute(f"delete from {tb} where {col}=?", (src,))
        antigo_ass = con.execute("select assunto_id from pontos where id=?", (src,)).fetchone()[0]
        novo_ass = con.execute("select assunto_id from pontos where id=?", (dst,)).fetchone()[0] if mesma else antigo_ass
        con.execute("update pontos set ativo=0, codigo=?, assunto_id=? where id=?",
                    (_arquivar_codigo(con, "pontos", disc_id[d["disciplina"]], cod_ponto[src]), novo_ass, src))
        resumo["pontos fundidos e arquivados"] += 1

    # ---- 6. assuntos que somem
    for slug, d in drafts.items():
        for x in d.get("lixeira_assuntos", []):
            aid = ass.get((d["disciplina"], x["antigo"]))
            if aid is None:
                continue
            con.execute("update classificacao set assunto_provisorio_id=NULL where assunto_provisorio_id=?", (aid,))
            if con.execute("select count(*) from pontos where assunto_id=?", (aid,)).fetchone()[0]:
                con.execute("update assuntos set codigo=? where id=?", (_arquivar_codigo(con, "assuntos", disc_id[d["disciplina"]], cod_assunto[aid]), aid))
                resumo["assuntos arquivados (ainda têm pontos arquivados)"] += 1
            else:
                con.execute("delete from assuntos where id=?", (aid,))
                resumo["assuntos removidos"] += 1

    # ---- 7. conferências finais (se falhar, a transação inteira é desfeita)
    for slug, d in drafts.items():
        did = disc_id[d["disciplina"]]
        pts_ativos = {c for (c,) in q("select codigo from pontos where disciplina_id=? and ativo=1", (did,))}
        ass_todos = {c for (c,) in q("select codigo from assuntos where disciplina_id=? and codigo not like '%#v%'", (did,))}
        esp_p = {cods_final[slug][p["uid"]] for a in d["assuntos"] for p in a["pontos"]}
        esp_a = {cods_final[slug][a["uid"]] for a in d["assuntos"]}
        assert pts_ativos == esp_p, f"{d['disciplina']}: pontos ativos diferem do rascunho ({len(pts_ativos)} contra {len(esp_p)})"
        assert ass_todos == esp_a, f"{d['disciplina']}: assuntos diferem do rascunho ({len(ass_todos)} contra {len(esp_a)})"
    assert q("select count(*) from classificacao")[0][0] == n_classif_antes, "o número de classificações mudou"
    assert q("select count(*) from classificacao c join pontos p on p.id=c.ponto_id where p.ativo=0")[0][0] == 0, "classificação ainda aponta para ponto arquivado"
    assert q("select count(*) from classificacao c join pontos p on p.id=c.ponto2_id where p.ativo=0")[0][0] == 0, "ponto2 ainda aponta para ponto arquivado"
    assert q("select count(*) from pontos where codigo like '~%'")[0][0] == 0 and q("select count(*) from assuntos where codigo like '~%'")[0][0] == 0, "sobrou código provisório"
    assert not q("pragma foreign_key_check"), "violação de chave estrangeira"
    resumo["rascunhos publicados"] = len(drafts)
    resumo["classificações no banco"] = n_classif_antes
    con.execute("insert into log_alteracoes(quem,o_que) values (?,?)",
                ("catalogar_publicar", "publicação de catálogos (" + ", ".join(drafts) + "): " + "; ".join(f"{k}: {v}" for k, v in resumo.items())))
    return resumo


def _escolher(args):
    """Rascunhos escolhidos na linha de comando, ou None se faltar escolher."""
    slugs = [args[i + 1] for i, x in enumerate(args) if x == "--disciplina" and i + 1 < len(args)]
    if "--todas" in args:
        return carregar_rascunhos()
    if not slugs:
        return None
    return carregar_rascunhos(slugs)


def _mostrar(resumo):
    for k, v in sorted(resumo.items()):
        print(f"   {k:60} {v}")


def simular_cmd(args):
    drafts = _escolher(args)
    if drafts is None:
        print("Diga quais rascunhos: --disciplina SLUG (repetível) ou --todas.")
        return 2
    banco = Path(args[args.index("--banco") + 1]) if "--banco" in args else BANCO
    saida = Path(args[args.index("--saida") + 1]) if "--saida" in args else None
    pasta = Path(tempfile.mkdtemp(prefix="ensaio_publicar_"))
    try:
        copia = pasta / "ensaio.db"
        shutil.copyfile(banco, copia)
        con = sqlite3.connect(copia)
        con.isolation_level = None
        con.execute("PRAGMA foreign_keys=ON")
        print(f"== ENSAIO DA PUBLICAÇÃO ({len(drafts)} rascunho(s): {', '.join(drafts)}) numa cópia temporária; o banco NÃO é tocado\n")
        try:
            con.execute("BEGIN IMMEDIATE")
            resumo = _gravar(con, drafts)
            con.execute("ROLLBACK")
        except Exception as e:                      # noqa: BLE001
            con.execute("ROLLBACK")
            print("A GRAVAÇÃO FALHARIA (e seria desfeita):", type(e).__name__, e)
            return 1
        finally:
            con.close()
        print("A gravação funcionaria. O que ela faria:")
        _mostrar(resumo)
        if saida:
            saida.write_text(json.dumps(dict(resumo), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print("\nrelatório gravado em", saida)
        return 0
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def aplicar_cmd(args):
    banco = Path(args[args.index("--banco") + 1]) if "--banco" in args else BANCO
    padrao = banco.resolve() == BANCO.resolve()
    if padrao and "--sim-do-usuario" not in args:
        print("RECUSADO: gravar no banco padrão exige --sim-do-usuario (só depois de o usuário mandar gravar).")
        return 2
    drafts = _escolher(args)
    if drafts is None:
        print("RECUSADO: diga quais rascunhos: --disciplina SLUG (repetível) ou --todas.")
        return 2
    if padrao:
        etiqueta = "todas" if "--todas" in args else "_".join(drafts)[:60]
        dest = RAIZ / "banco" / "backup" / f"estudos_antes_publicar_{etiqueta}_{datetime.date.today().isoformat()}.db"
        if dest.exists():
            dest = dest.with_name(dest.stem + datetime.datetime.now().strftime("_%H%M%S") + ".db")
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
    except Exception as e:                          # noqa: BLE001
        con.execute("ROLLBACK")
        print("DESFEITO (nada foi gravado):", type(e).__name__, e)
        return 1
    finally:
        con.close()
    print("GRAVADO:")
    _mostrar(resumo)
    if padrao:
        import importlib.util
        import lib_catalogo as LC
        spec = importlib.util.spec_from_file_location("catalogo71", Path(__file__).resolve().parent / "71_catalogo_e_classificacao.py")
        m71 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m71)
        con2 = sqlite3.connect(banco)
        m71.exportar(con2, CAT, RAIZ / "dados" / "classificacao")
        con2.close()
        for slug, d in drafts.items():
            LC.definir(slug, "provisorio", f"publicação do rascunho {d['versao_alvo']} em {datetime.date.today().isoformat()}; nenhuma classificação revisada por humano; "
                                          "reclassificação fina é do grupo C", versao=d["versao_alvo"],
                       riscos=["rascunho da IA aprovado pelo usuário; classificação migrada pelo mapa, não revisada"])
    return 0


def main():
    args = sys.argv[1:]
    if "--aplicar" in args:
        return aplicar_cmd(args)
    if "--simular" in args:
        return simular_cmd(args)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
