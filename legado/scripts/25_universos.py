"""Cria a tabela `universos` (filtros de quais questoes entram na analise) e liga o perfil a um universo.
Aditivo e idempotente: nao apaga nada. Filtro (JSON): bancas, carreiras, cargos, cargos_prefixo, instituicoes (listas), ano_min, ano_max. Vazio = todas as questoes.
Uso: python scripts/25_universos.py
"""
import sqlite3, json, datetime
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "banco" / "estudos.db"
HOJE = datetime.date.today().isoformat()
SEMENTES = [
    ("Todas as questões", "Todas as provas do banco, de qualquer banca, carreira e cargo.", {}),
    ("Só FCC", "Todas as provas da banca FCC, de qualquer carreira.", {"bancas": ["FCC"]}),
    ("Defensoria, todas as bancas", "Provas de Defensoria Pública, de qualquer banca e cargo.", {"carreiras": ["Defensoria Pública"]}),
    ("Defensoria FCC", "Provas de Defensoria Pública da banca FCC, de qualquer cargo.", {"bancas": ["FCC"], "carreiras": ["Defensoria Pública"]}),
    ("Defensor Público, todas as bancas", "Só o cargo de Defensor Público, de qualquer banca.", {"carreiras": ["Defensoria Pública"], "cargos": ["Defensor Público"]}),
    ("Analista FCC", "Provas da FCC de qualquer cargo de Analista (Analista Jurídico, Analista de Defensoria, Analista Ministerial, Analista Judiciário...), de qualquer carreira.", {"bancas": ["FCC"], "cargos_prefixo": ["Analista"]}),
    ("Defensor Público FCC", "Só Defensor Público da FCC.", {"bancas": ["FCC"], "carreiras": ["Defensoria Pública"], "cargos": ["Defensor Público"]}),
]

con = sqlite3.connect(DB)
con.execute("CREATE TABLE IF NOT EXISTS universos (id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, descricao TEXT, filtro TEXT NOT NULL DEFAULT '{}', criado_em TEXT)")
if "universo_id" not in [r[1] for r in con.execute("pragma table_info(perfis)")]:
    con.execute("ALTER TABLE perfis ADD COLUMN universo_id INT REFERENCES universos(id)")
for nome, desc, filtro in SEMENTES:
    con.execute("insert or ignore into universos(nome,descricao,filtro,criado_em) values(?,?,?,?)", (nome, desc, json.dumps(filtro, ensure_ascii=False), HOJE))
todas = con.execute("select id from universos where nome='Todas as questões'").fetchone()[0]
con.execute("update perfis set universo_id=? where universo_id is null", (todas,))
con.execute("insert into log_alteracoes(quem,o_que) values('script 25','tabela universos e perfis.universo_id')")
con.commit()
for r in con.execute("select id,nome,filtro from universos"):
    print(r)
