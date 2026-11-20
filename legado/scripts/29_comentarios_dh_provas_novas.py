"""Grava no banco os comentarios (rascunho da IA) das 17 questoes de Direitos Humanos das provas novas do DPE-AM (2018, 2019, 2022-2).
Fonte do texto: dados/comentarios_dh_novas_provas.json (chave 'prova|numero'; c = comentario, p = pegadinha, d = dispositivos, pend = 1 se precisa confirmar).
Idempotente: substitui o comentario da questao. Estado 'rascunho'; nada aqui foi conferido por humano."""
import json, sqlite3, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
dados = json.loads((RAIZ / "dados" / "comentarios_dh_novas_provas.json").read_text(encoding="utf-8"))
con = sqlite3.connect(RAIZ / "banco" / "estudos.db")
hoje = datetime.date.today().isoformat()
for chave, v in dados.items():
    prova, num = chave.rsplit("|", 1)
    q = con.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (prova, int(num))).fetchone()
    if not q:
        raise SystemExit("questao nao encontrada: " + chave)
    con.execute("insert or replace into comentarios(questao_id,texto,pegadinha,dispositivos,estado,pendente_confirmacao,autor,atualizado_em) values(?,?,?,?,?,?,?,?)",
                (q[0], v["c"], v["p"], json.dumps(v["d"], ensure_ascii=False), "rascunho", int(v.get("pend", 0)), "IA (Claude)", hoje))
con.execute("insert into log_alteracoes(quem,o_que) values('script 29', ?)", (f"{len(dados)} comentarios de DH das provas novas (rascunho)",))
con.commit()
print(len(dados), "comentarios gravados;", sum(int(v.get("pend", 0)) for v in dados.values()), "marcados para confirmar")
