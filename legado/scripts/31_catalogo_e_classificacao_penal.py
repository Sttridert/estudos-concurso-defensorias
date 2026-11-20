"""Direito Penal: grava assuntos, catalogo de pontos e classificacao das questoes (rascunho da IA, 13/11/2026).
Fontes: dados/catalogo_assuntos_direito_penal.csv, dados/catalogo_pontos_direito_penal.csv,
        dados/classificacao_penal_analista.csv (prova;numero;ponto;ponto2;detalhe;tipo_cobranca).
Idempotente: atualiza textos e substitui a classificacao das questoes listadas. Nada aqui foi conferido por humano.
"""
import csv, sqlite3, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
con = sqlite3.connect(RAIZ / "banco" / "estudos.db")
con.execute("PRAGMA foreign_keys=ON")
hoje = datetime.date.today().isoformat()
agora = datetime.datetime.now().isoformat(timespec="seconds")
ler = lambda nome: list(csv.DictReader(open(DADOS / nome, encoding="utf-8"), delimiter=";"))

disc = con.execute("select id from disciplinas where nome='Direito Penal'").fetchone()[0]

for a in ler("catalogo_assuntos_direito_penal.csv"):
    r = con.execute("select id from assuntos where disciplina_id=? and codigo=?", (disc, a["codigo"])).fetchone()
    if r:
        con.execute("update assuntos set nome=?, descricao=? where id=?", (a["nome"], a["descricao"], r[0]))
    else:
        con.execute("insert into assuntos(disciplina_id,codigo,nome,descricao) values(?,?,?,?)", (disc, a["codigo"], a["nome"], a["descricao"]))
ass = {c: i for i, c in con.execute("select id, codigo from assuntos where disciplina_id=?", (disc,))}

pontos = ler("catalogo_pontos_direito_penal.csv")
for p in pontos:
    r = con.execute("select id from pontos where disciplina_id=? and codigo=?", (disc, p["codigo"])).fetchone()
    if r:
        con.execute("update pontos set assunto_id=?, texto=?, descricao=? where id=?", (ass[p["assunto"]], p["texto"], p["descricao"], r[0]))
    else:
        con.execute("insert into pontos(disciplina_id,assunto_id,codigo,texto,descricao,origem,criado_em) values(?,?,?,?,?,?,?)",
                    (disc, ass[p["assunto"]], p["codigo"], p["texto"], p["descricao"], "edital DPE-AM 2026 e provas FCC de Analista (IA, rascunho)", hoje))
pid = {c: (i, a) for i, c, a in con.execute("select id, codigo, assunto_id from pontos where disciplina_id=?", (disc,))}

cls = ler("classificacao_penal_analista.csv")
for c in cls:
    q = con.execute("select q.id, q.disciplina_id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?",
                    (c["prova"], int(c["numero"]))).fetchone()
    assert q, c
    assert q[1] == disc, ("questao nao e de Direito Penal no banco", c)
    p1, a1 = pid[c["ponto"]]
    p2 = pid[c["ponto2"]][0] if c["ponto2"] else None
    con.execute("delete from classificacao where questao_id=?", (q[0],))
    con.execute("""insert into classificacao(questao_id,ponto_id,ponto2_id,assunto_provisorio_id,detalhe,tipo_cobranca,origem,confianca,revisada,atualizado_em)
                   values(?,?,?,?,?,?,?,?,0,?)""", (q[0], p1, p2, a1, c["detalhe"], c["tipo_cobranca"], "IA (rascunho) 13/11/2026", "media", agora))

sem = con.execute("""select p.nome, q.numero from questoes q join provas p on p.id=q.prova_id left join classificacao c on c.questao_id=q.id
                     where q.disciplina_id=? and p.banca='FCC' and p.cargo like 'Analista%' and c.ponto_id is null""", (disc,)).fetchall()
con.execute("insert into log_alteracoes(quem,o_que) values('script 31', ?)",
            (f"Direito Penal: {len(ass)} assuntos, {len(pontos)} pontos, {len(cls)} questoes classificadas (rascunho)",))
con.commit()
print(f"{len(ass)} assuntos, {len(pontos)} pontos, {len(cls)} questoes classificadas")
print("questoes de Penal de Analista FCC sem ponto:", sem or "nenhuma")
