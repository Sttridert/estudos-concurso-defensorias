#!/usr/bin/env python3
"""Classifica as questões de EXECUÇÃO PENAL do universo Analista FCC (2 questões) nos pontos EX01.01 a EX09.05 (rascunho da IA).

Uso:  python -I scripts/62_classificar_execucao_penal.py [--simular]

Grava em `classificacao` com origem "IA (rascunho) 15/11/2026" e `revisada = 0`; substitui a classificação existente da questão.
Chave: prova + número. Cópia do banco antes. As outras questões de Execução Penal do banco (fora do universo Analista FCC) ficam
para o lote de classificação geral (não são necessárias para a apostila do DPE-AM 2026).
"""
import datetime, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
simular = "--simular" in sys.argv
L, J = "lei_seca", "jurisprudencia"
# (prova, número): (principal, secundário ou None, tipo, detalhe, confiança)
C = {
    ("2018 - DPE-AM - Analista Jurídico", 44): ("EX05.02", None, L, "Permissão de saída e saída temporária: requisitos e prazos (art. 120 a 125 da LEP)", "alta"),
    ("2019 - DPE-AM - Analista Jurídico", 45): ("EX05.07", "EX04.01", J, "Súmulas do STJ na execução penal; gabarito D: livramento condicional sem revogação extingue a pena (falta grave nas demais)", "media"),
}


def main():
    con = sqlite3.connect(BANCO); cur = con.cursor()
    if not simular:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_classificar_exec_{datetime.date.today().isoformat()}.db"
        if not dst.exists():
            out = sqlite3.connect(dst); con.backup(out); out.close(); print("cópia de segurança:", dst.name)
    pid = {c: i for c, i in cur.execute("select p.codigo,p.id from pontos p join disciplinas d on d.id=p.disciplina_id where d.nome like 'Exec%'")}
    agora = datetime.datetime.now().isoformat(timespec="seconds"); n = 0
    for (prova, num), (p1, p2, tipo, det, conf) in C.items():
        q = cur.execute("select q.id,q.disciplina_id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (prova, num)).fetchone()
        assert q, (prova, num)
        ass = cur.execute("select assunto_id from pontos where id=?", (pid[p1],)).fetchone()[0]
        cur.execute("delete from classificacao where questao_id=?", (q[0],))
        cur.execute("""insert into classificacao(questao_id,ponto_id,ponto2_id,assunto_provisorio_id,detalhe,tipo_cobranca,origem,confianca,revisada,atualizado_em)
                       values (?,?,?,?,?,?,?,?,0,?)""", (q[0], pid[p1], pid[p2] if p2 else None, ass, det, tipo, "IA (rascunho) 15/11/2026", conf, agora)); n += 1
    print(f"{n} questões classificadas")
    if simular:
        con.rollback(); print("(simulação: nada gravado)")
    else:
        cur.execute("insert into log_alteracoes(quem,o_que) values (?,?)", ("script 62", f"classificação de {n} questões de Execução Penal (universo Analista FCC)"))
        con.commit()
    con.close()


if __name__ == "__main__":
    main()
