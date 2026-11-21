"""Grava no banco comentarios (rascunho da IA) a partir de um JSON. Generico para qualquer disciplina.
Uso: python scripts/32_gravar_comentarios.py dados/comentarios_<...>.json
Formato: {"prova|numero": {"c": comentario, "p": pegadinha, "d": ["Norma|dispositivo", ...], "pend": 0/1}}
Idempotente: substitui o comentario da questao. Estado 'rascunho'; nada aqui foi conferido por humano."""
import json, sqlite3, datetime, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
arq = Path(sys.argv[1])
dados = json.loads(arq.read_text(encoding="utf-8"))
con = sqlite3.connect(RAIZ / "banco" / "estudos.db")
hoje = datetime.date.today().isoformat()
for chave, v in dados.items():
    prova, num = chave.rsplit("|", 1)
    q = con.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (prova, int(num))).fetchone()
    if not q:
        raise SystemExit("questao nao encontrada: " + chave)
    con.execute("insert or replace into comentarios(questao_id,texto,pegadinha,dispositivos,estado,pendente_confirmacao,autor,atualizado_em) values(?,?,?,?,?,?,?,?)",
                (q[0], v["c"], v["p"], json.dumps(v["d"], ensure_ascii=False), "rascunho", int(v.get("pend", 0)), "IA (Claude)", hoje))
con.execute("insert into log_alteracoes(quem,o_que) values('script 32', ?)", (f"{len(dados)} comentarios de {arq.name} (rascunho)",))
con.commit()
print(len(dados), "comentarios gravados;", sum(int(v.get("pend", 0)) for v in dados.values()), "marcados para confirmar")
