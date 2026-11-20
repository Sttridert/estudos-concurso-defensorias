#!/usr/bin/env python3
"""Aplica no banco o resultado da pesquisa de anulações e alterações de gabarito (plano 05, Fase C, item 1).

Uso:  python -I scripts/65_aplicar_gabaritos.py dados/revisao_web/gabaritos.json [--simular]

Formato: {"anulacoes": [{"prova", "numero", "tipo", "fonte"}], "status": [{"prova", "status", "fonte"}]}
  anulacoes: grava em `ajustes_gabarito` (ajuste 'atribuicao') e marca a questão como 'anulada' (como o script 05 faz);
  status:    troca `provas.gabarito_status` (a tag "gabarito preliminar" do cartão sai quando o status deixa de começar por
             "preliminar" ou "a confirmar"; ver lib_escopo.gabarito_preliminar).
Cópia do banco antes. Idempotente.
"""
import datetime, json, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"


def main():
    arq = Path(sys.argv[1])
    simular = "--simular" in sys.argv
    dados = json.loads(arq.read_text(encoding="utf-8"))
    con = sqlite3.connect(BANCO)
    if not simular:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_gabaritos_{datetime.date.today().isoformat()}.db"
        if not dst.exists():
            out = sqlite3.connect(dst); con.backup(out); out.close(); print("cópia de segurança:", dst.name)
    n_an = n_st = 0
    for a in dados.get("anulacoes", []):
        p = con.execute("select id from provas where nome=?", (a["prova"],)).fetchone()
        q = con.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (a["prova"], a["numero"])).fetchone()
        if not p or not q:
            sys.exit("prova ou questão não encontrada: " + json.dumps(a, ensure_ascii=False))
        if not con.execute("select 1 from ajustes_gabarito where prova_id=? and numero=? and tipo_caderno=?", (p[0], a["numero"], a["tipo"])).fetchone():
            con.execute("insert into ajustes_gabarito(prova_id,numero,tipo_caderno,ajuste,nova_letra,fonte) values (?,?,?,?,?,?)",
                        (p[0], a["numero"], a["tipo"], "atribuicao", None, a["fonte"]))
        con.execute("update questoes set situacao='anulada', motivo_situacao=? where id=?",
                    ("atribuída a todos os candidatos (anulada) - relatório oficial da FCC: " + a["fonte"], q[0]))
        n_an += 1
    for s in dados.get("status", []):
        r = con.execute("select id from provas where nome=?", (s["prova"],)).fetchone()
        if not r:
            sys.exit("prova não encontrada: " + s["prova"])
        con.execute("update provas set gabarito_status=? where id=?", (s["status"], r[0]))
        n_st += 1
    con.execute("insert into log_alteracoes(quem,o_que) values('script 65', ?)",
                (f"gabaritos de {arq.name}: {n_an} anulações, {n_st} status" + (" [simulação]" if simular else ""),))
    if simular:
        con.rollback(); print("(simulação: nada gravado)")
    else:
        con.commit()
    print(f"{n_an} anulações, {n_st} status")


if __name__ == "__main__":
    main()
