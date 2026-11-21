#!/usr/bin/env python3
"""Grava no banco os TEXTOS-BASE das provas (Língua Portuguesa e qualquer disciplina cujas questões dependam de um texto).

Uso:  python -I scripts/coletar_textos_base.py [--simular]

Fonte: `dados/coleta/textos_base.json` = {nome da prova: [{ordem, titulo, subtitulo?, autoria, q_ini, q_fim, texto, fonte, verso?}]}.
O texto usa `\\n\\n` entre parágrafos (ou estrofes, com `verso`), `\\n` para quebra de verso, e as marcas `<u>…</u>` (sublinhado)
e `<b>…</b>` (destaque) como nas questões. Cria a tabela `textos_base` se não existir (o banco nunca é recriado) e, a cada
execução, substitui as linhas das provas do JSON. Cópia do banco antes (em `banco/backup/`) e registro em `log_alteracoes`.
As questões se ligam ao texto por prova + número (q_ini a q_fim).
"""
import datetime, json, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
simular = "--simular" in sys.argv
dados = json.loads((RAIZ / "dados" / "coleta" / "textos_base.json").read_text(encoding="utf-8"))
if not simular:
    dst = RAIZ / "banco" / "backup" / f"estudos_antes_textos_base_{datetime.date.today().isoformat()}_{datetime.datetime.now().strftime('%H%M')}.db"
    s = sqlite3.connect(BANCO); o = sqlite3.connect(dst); s.backup(o); o.close(); s.close()
    print("cópia de segurança:", dst.name)
con = sqlite3.connect(":memory:" if simular else BANCO)
if simular:
    real = sqlite3.connect(BANCO); real.backup(con); real.close()
con.execute("""create table if not exists textos_base(
    id integer primary key autoincrement, prova_id integer not null references provas(id), ordem integer not null,
    titulo text, subtitulo text, autoria text, q_ini integer not null, q_fim integer not null, texto text not null,
    verso integer not null default 0, fonte text, atualizado_em text, unique(prova_id, ordem))""")
n = 0
for prova, blocos in dados.items():
    r = con.execute("select id from provas where nome=?", (prova,)).fetchone()
    if not r:
        sys.exit(f"prova não encontrada: {prova}")
    con.execute("delete from textos_base where prova_id=?", (r[0],))
    for b in blocos:
        con.execute("insert into textos_base(prova_id,ordem,titulo,subtitulo,autoria,q_ini,q_fim,texto,verso,fonte,atualizado_em) values(?,?,?,?,?,?,?,?,?,?,?)",
                    (r[0], b["ordem"], b.get("titulo"), b.get("subtitulo"), b.get("autoria"), b["q_ini"], b["q_fim"], b["texto"],
                     1 if b.get("verso") else 0, b.get("fonte"), datetime.date.today().isoformat()))
        n += 1
con.execute("insert into log_alteracoes(quem,o_que) values('coletar_textos_base', ?)", (f"{n} textos-base gravados de {len(dados)} provas" + (" [simulação]" if simular else ""),))
if not simular:
    con.commit()
print(n, "textos-base", "(simulação)" if simular else "gravados")
