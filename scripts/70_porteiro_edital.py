#!/usr/bin/env python3
"""PORTEIRO DO EDITAL (decisão 41, plano 05, item A7). Só leitura; vale para QUALQUER edital com artefato no banco.

Uso:
  python -I scripts/70_porteiro_edital.py --edital <id | trecho do nome> [--disciplina "nome pedido"] [--universo ID] [--perfil ID]

O que faz:
  1. acha o edital (id ou trecho do nome/pasta) e confere se ele tem artefato (frases classificadas e blocos);
  2. lista os blocos (disciplinas) do edital, com: disciplina do catálogo, frases, pontos tocados e as questões que o bloco pegaria
     (questões classificadas, como principal ou secundário, em pontos tocados pelas frases do bloco, qualquer que seja a disciplina de origem);
  3. com --disciplina: casa o pedido com UM bloco (o nome do edital pode ser diferente do catálogo). Se a disciplina NÃO consta do edital,
     PARA (código de saída 2) e imprime as disciplinas que o edital tem, para o usuário escolher;
  4. diz o que falta para gerar (artefato, catálogo dos pontos tocados, comentários das questões, perfil confirmado).
--universo ID limita as questões ao universo (tabela universos); --perfil ID usa o universo do perfil e confere o perfil.
Nada é gravado.
"""
import argparse
import collections
import importlib.util
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_escopo as E  # noqa: E402

PARA_IGNORAR = {"direito", "direitos", "de", "da", "do", "das", "dos", "e", "a", "o", "em", "para", "com", "ao", "na", "no", "nos", "nas"}


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def fichas(con, edital_id):
    """um dicionário por bloco do edital"""
    out = []
    for sigla, titulo, disc_id, ordem in con.execute("select sigla,titulo_no_edital,disciplina_id,ordem from edital_blocos where edital_id=? order by ordem", (edital_id,)):
        nome_cat = con.execute("select nome from disciplinas where id=?", (disc_id,)).fetchone()[0] if disc_id else None
        nf = con.execute("select count(*) from edital_frases where edital_id=? and disciplina_edital=?", (edital_id, sigla)).fetchone()[0]
        out.append({"sigla": sigla, "titulo": E.titulo_legivel(con, titulo), "disciplina_id": disc_id, "catalogo": nome_cat, "frases": nf})
    return out


def casar(pedido, blocos):
    """blocos cujo nome (edital ou catálogo) ou sigla casa com o pedido"""
    p = norm(pedido)
    toks = [t for t in p.split() if t not in PARA_IGNORAR]
    exatos = [b for b in blocos if p == norm(b["sigla"]) or p in (norm(b["titulo"]), norm(b["catalogo"] or ""))]
    if exatos:       # nome igual ao do edital ou do catalogo tem prioridade ("Direito Civil" nao e "Direito Processual Civil")
        return exatos
    achou = []
    for b in blocos:
        alvos = [norm(b["titulo"]), norm(b["catalogo"] or ""), norm(b["sigla"])]
        if p == norm(b["sigla"]) or any(p and p in a for a in alvos[:2]) or (toks and any(all(any(w[:6] == t[:6] for w in a.split()) for t in toks) for a in alvos[:2])):
            achou.append(b)
    return achou


def carregar_23():
    spec = importlib.util.spec_from_file_location("m23", RAIZ / "scripts" / "23_motor_analise.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def questoes_do_bloco(con, edital_id, sigla, disc_id, filtro, m23):
    """(total, por disciplina de origem, sem comentário, ids) das questões que o bloco pegaria, no universo"""
    esc = E.escopo(con, {"bloco_edital": sigla, "edital_id": edital_id})
    cond, par = E.clausula(esc, disc_id)
    rows = con.execute(f"""select q.id,q.disciplina_id,q.situacao,p.banca,p.carreira,p.cargo,p.instituicao,p.ano,c.ponto_id,c.ponto2_id,
                           (select count(*) from comentarios co where co.questao_id=q.id) from questoes q join provas p on p.id=q.prova_id
                           join classificacao c on c.questao_id=q.id where c.ponto_id is not null and {cond}""", par).fetchall()
    por_disc, sem_com, ids = collections.Counter(), 0, []
    for qid, dq, sit, banca, carr, cargo, inst, ano, p1, p2, ncom in rows:
        if filtro and not m23.em_universo({"banca": banca or "", "carreira": carr or "", "cargo": cargo or "", "inst": inst or "", "ano": ano}, filtro):
            continue
        if sit not in m23.VALIDAS:
            continue
        # questão de outra disciplina só vale se algum ponto dela é tocado pelo bloco
        if dq != disc_id and p1 not in esc["toca"] and p2 not in esc["toca"]:
            continue
        por_disc[dq] += 1
        sem_com += 0 if ncom else 1
        ids.append(qid)
    return len(ids), por_disc, sem_com, ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edital", required=True)
    ap.add_argument("--disciplina")
    ap.add_argument("--universo", type=int)
    ap.add_argument("--perfil", type=int)
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    m23 = carregar_23()
    # 1. o edital
    if a.edital.isdigit():
        eds = con.execute("select id,nome,tipo from editais where id=?", (int(a.edital),)).fetchall()
    else:
        eds = con.execute("select id,nome,tipo from editais where tipo='real' and nome like ?", (f"%{a.edital}%",)).fetchall()
    if not eds:
        sys.exit(f"Edital «{a.edital}» não está no banco. Se o PDF está em provas/, monte o artefato: scripts 50, 51 e 52 (decisão 35).")
    if len(eds) > 1:
        sys.exit("Mais de um edital casa com o pedido: " + "; ".join(f"{i} = {n}" for i, n, _ in eds))
    eid, enome, _ = eds[0]
    print(f"Edital {eid}: {enome}")
    n_fr = con.execute("select count(*) from edital_frases where edital_id=?", (eid,)).fetchone()[0]
    if not n_fr or not E.tem_blocos(con, eid):
        sys.exit("FALTA: este edital não tem artefato no banco (frases e blocos). Rode coletar_programa_edital.py extrair, 51_classificar_edital.py e 52_gravar_edital_classificado.py.")
    perfil = None
    universo_id = a.universo
    if a.perfil:
        import lib_perfil as LP
        perfil = LP.perfil_do_arquivo(con, a.perfil)
        if perfil is None:
            sys.exit(f"Perfil {a.perfil} não existe: nenhum perfil.toml tem uma apostila com id = {a.perfil} (a tabela `perfis` foi aposentada).")
        universo_id = universo_id or perfil["universo_id"]
    filtro = {}
    if universo_id:
        r = con.execute("select nome,filtro from universos where id=?", (universo_id,)).fetchone()
        if not r:
            sys.exit(f"Universo {universo_id} não existe.")
        filtro = json.loads(r[1])
        print(f"Universo: {r[0]}")
    else:
        print("Universo: todas as questões (use --universo para filtrar)")
    blocos = fichas(con, eid)
    nomes = {i: n for i, n in con.execute("select id,nome from disciplinas")}
    print(f"\nO edital tem {len(blocos)} blocos (disciplinas do cargo):\n")
    dados = {}
    for b in blocos:
        esc = E.escopo(con, {"bloco_edital": b["sigla"], "edital_id": eid})
        n, por_disc, sem_com, ids = questoes_do_bloco(con, eid, b["sigla"], b["disciplina_id"], filtro, m23)
        dados[b["sigla"]] = (esc, n, por_disc, sem_com)
        orig = ", ".join(f"{nomes[d]} {k}" for d, k in por_disc.most_common())
        print(f"  [{b['sigla']}] {b['titulo']}")
        print(f"      catálogo: {b['catalogo']} | {b['frases']} frases | {len(esc['toca'])} pontos tocados | {n} questões ({orig or 'nenhuma'}) | {sem_com} sem comentário")
    if not a.disciplina:
        return
    # 3. casar o pedido com um bloco
    achou = casar(a.disciplina, blocos)
    print()
    if not achou:
        # a disciplina do catalogo pode nao ser bloco do edital e estar DENTRO de um bloco (ex.: o edital poe uma materia como item de outra)
        p_ = norm(a.disciplina)
        cat = [(i, n) for i, n in nomes.items() if p_ and (p_ in norm(n) or norm(n) in p_)]
        dentro = collections.Counter()
        for did, _n in cat:
            for sigla, n_pts in con.execute("""select f.disciplina_edital, count(distinct d.ponto_id) from edital_frase_destinos d join edital_frases f on f.id=d.frase_id
                                               join pontos pt on pt.id=d.ponto_id where f.edital_id=? and pt.disciplina_id=? group by 1""", (eid, did)):
                dentro[sigla] += n_pts
        if dentro:
            sigla, n_pts = dentro.most_common(1)[0]
            achou = [b for b in blocos if b["sigla"] == sigla]
            print(f"«{a.disciplina}» não é bloco próprio do edital {eid}: o edital a traz DENTRO do bloco [{sigla}] {achou[0]['titulo']} ({n_pts} pontos dela são tocados por frases desse bloco).")
            print("Pela decisão 41, a apostila é a do bloco, e as questões dessa disciplina entram nela.")
    if not achou:
        print(f"A disciplina «{a.disciplina}» NÃO consta do edital {eid}. Não vou continuar.")
        print("Disciplinas que o edital tem: " + "; ".join(f"{b['titulo']}" for b in blocos))
        sys.exit(2)
    if len(achou) > 1:
        print(f"«{a.disciplina}» casa com mais de um bloco; escolha um: " + "; ".join(f"[{b['sigla']}] {b['titulo']}" for b in achou))
        sys.exit(3)
    b = achou[0]
    esc, n, por_disc, sem_com = dados[b["sigla"]]
    print(f"«{a.disciplina}» = bloco [{b['sigla']}] {b['titulo']} (catálogo: {b['catalogo']}).")
    print("Para gerar a apostila falta conferir:")
    falta = []
    pts_sem = con.execute("select count(*) from pontos where disciplina_id=?", (b["disciplina_id"],)).fetchone()[0]
    if not pts_sem:
        falta.append("o catálogo da disciplina não tem pontos")
    if n == 0:
        falta.append("nenhuma questão classificada nos pontos do bloco (classificar as questões)")
    if sem_com:
        falta.append(f"{sem_com} questões sem comentário (comentar antes de gerar; decisão 40)")
    sem_class = con.execute("select count(*) from questoes q left join classificacao c on c.questao_id=q.id where q.disciplina_id=? and c.questao_id is null", (b["disciplina_id"],)).fetchone()[0]
    if sem_class:
        falta.append(f"{sem_class} questões da disciplina «{b['catalogo']}» ainda sem classificação (no banco todo; só as do universo importam)")
    if perfil is None:
        falta.append("perfil por bloco: criar com bloco_edital='" + b["sigla"] + "', mostrar ao usuário e obter a confirmação")
    else:
        if perfil.get("bloco_edital") != b["sigla"]:
            falta.append(f"o perfil {perfil['id']} tem bloco_edital={perfil.get('bloco_edital')!r}; para este bloco deveria ser {b['sigla']!r}")
        if not perfil["confirmado_pelo_usuario"]:
            falta.append(f"o perfil {perfil['id']} ainda não foi confirmado pelo usuário")
    for f in falta:
        print("  - " + f)
    if not falta:
        print("  nada: pode gerar (23 e 24 com --edital-artefato).")


if __name__ == "__main__":
    main()
