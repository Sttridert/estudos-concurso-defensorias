"""Etapa 3: liga cada uma das 159 questoes de DH a um ponto do catalogo (e, se houver, a um 2o ponto).
Classificacao feita pela IA (rascunho; usuario confere). Ordem = ordem de dados/classificacao_dh.csv.
Cada item: 'DHxx.yy' ou 'DHxx.yy/DHxx.zz' (principal/secundario)."""
import csv, sqlite3, datetime
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
M = """
04.06;01.05;03.02;05.02;03.01;08.05/08.04;10.01;06.03;10.02;09.02;08.10;08.07;08.04/09.02;01.02;04.01;01.01;04.06;04.05;10.04;10.03
07.02;09.02;04.09;08.05;03.03;10.09;09.01/05.03;05.02;03.02;04.05;10.05;08.02;02.05/04.01;09.02;01.04;08.01;04.06/07.02;05.02;08.01;08.01
08.02;08.04/08.03;04.05;06.01;05.02;08.04/03.03;04.02;06.03;04.04;08.03;06.02;06.01;04.07;06.03;05.02;06.01
03.03;09.01;02.03;03.04;02.01;06.01/08.04;08.04;08.06;08.02;09.03;08.07;01.01;04.08;04.05;08.07;03.01
06.01;04.04;04.08;08.10;07.04;01.02;03.03/03.02;09.01/03.03;08.01/04.06;04.01;05.03;07.02
10.05;02.03/02.02;03.03/03.04;04.03/08.03;10.10/04.08;10.01;05.02/10.10;03.01
01.04;08.01;05.03;01.04;08.03;09.03;10.03;08.02/10.08
05.01;01.04;08.03;04.07;01.04;04.04;04.04;03.02/03.03
07.02;04.04;06.02;08.04;08.11;04.06
10.05;08.08;08.10;04.07;08.04;08.09;08.05;08.01;03.04
03.03;10.06;02.03;06.02;10.07;01.03;02.01;06.04
08.03;10.08;08.05;08.02/04.02;07.01
02.03;08.03;08.08;08.03;08.11;05.03/04.07;08.06;07.04;08.01;04.05;10.02
08.10;06.02;04.03;09.01/04.07;02.04;07.03;06.03/07.01
06.01;06.03;03.02;09.02;04.02
"""
cods = [("DH" + x.strip()) if "/" not in x else "/".join("DH" + y for y in x.strip().split("/")) for x in M.replace("\n", ";").split(";") if x.strip()]
rows = list(csv.DictReader(open(BASE / "dados" / "classificacao_dh.csv", encoding="utf-8"), delimiter=";"))
assert len(cods) == len(rows) == 159, (len(cods), len(rows))
con = sqlite3.connect(BASE / "banco" / "estudos.db")
pid = {c: (i, a) for i, c, a in con.execute("select id, codigo, assunto_id from pontos")}
ass_cod = {i: c for i, c in con.execute("select id, codigo from assuntos")}
agora = datetime.datetime.now().isoformat(timespec="seconds")
dif = []
for r, c in zip(rows, cods):
    p1, _, p2 = c.partition("/")
    q = con.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (r["prova"], int(r["numero"]))).fetchone()
    assert q, r
    if ass_cod[pid[p1][1]] != r["assunto"]:
        dif.append((r["prova"], r["numero"], r["assunto"], p1, r["detalhe"]))
    con.execute("update classificacao set ponto_id=?, ponto2_id=?, origem='IA etapa 3 (rascunho)', revisada=0, atualizado_em=? where questao_id=?",
                (pid[p1][0], pid[p2][0] if p2 else None, agora, q[0]))
con.execute("insert into log_alteracoes(quem,o_que) values('script 22', ?)", (f"159 questoes ligadas a pontos; {len(dif)} mudam de assunto",))
con.commit()
print("ligadas: 159; divergem do assunto provisorio:", len(dif))
for d in dif: print(d)
