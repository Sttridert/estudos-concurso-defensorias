#!/usr/bin/env python3
"""Confirma o texto de questões marcadas `revisar_texto` depois da conferência com a imagem do caderno (plano 05, Fase C, item 2).

Uso:  python -I scripts/66_confirmar_texto_questoes.py "<prova>" <numero> [<numero> ...] [--nota "texto"]

Passa `situacao` de `revisar_texto` para `valida` SEM mudar o texto (o texto já confere com o caderno). Para texto que precisa de
correção use `55_aplicar_correcoes_texto.py`. Cópia do banco antes; registro em `log_alteracoes`.
"""
import datetime, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
args = sys.argv[1:]
nota = ""
if "--nota" in args:
    i = args.index("--nota"); nota = args[i + 1]; args = args[:i] + args[i + 2:]
prova, numeros = args[0], [int(x) for x in args[1:]]
dst = RAIZ / "banco" / "backup" / f"estudos_antes_confirmar_texto_{datetime.date.today().isoformat()}_{datetime.datetime.now().strftime('%H%M')}.db"
s = sqlite3.connect(BANCO); o = sqlite3.connect(dst); s.backup(o); o.close(); s.close()
con = sqlite3.connect(BANCO)
pid = con.execute("select id from provas where nome=?", (prova,)).fetchone()[0]
n = 0
for num in numeros:
    r = con.execute("select id,situacao from questoes where prova_id=? and numero=?", (pid, num)).fetchone()
    if not r or r[1] != "revisar_texto":
        print(f"Q{num}: ignorada (situação {r[1] if r else 'inexistente'})"); continue
    con.execute("update questoes set situacao='valida', motivo_situacao=? where id=?", (f"texto conferido com a imagem do caderno em {datetime.date.today().isoformat()}" + (f"; {nota}" if nota else ""), r[0])); n += 1
con.execute("insert into log_alteracoes(quem,o_que) values('script 66', ?)", (f"{prova}: {n} questões com texto confirmado",))
con.commit(); print(n, "questões confirmadas; cópia:", dst.name)
