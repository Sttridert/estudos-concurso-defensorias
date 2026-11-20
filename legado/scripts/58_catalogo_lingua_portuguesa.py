#!/usr/bin/env python3
"""Cria no banco o catálogo de LÍNGUA PORTUGUESA (assuntos LP01 a LP09 e 21 pontos), aprovado pelo usuário em 15/11/2026.

Uso:  python -I scripts/58_catalogo_lingua_portuguesa.py [--simular]

Segue as frases do bloco "LÍNGUA PORTUGUESA" do Anexo II do edital DPE-AM 2026 (Conhecimentos Gerais, todos os cargos).
Idempotente (não duplica assuntos nem pontos). Cópia do banco antes e registro em `log_alteracoes`. Rascunho da IA aprovado
pelo usuário; a classificação das questões é outro passo.
"""
import datetime, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
simular = "--simular" in sys.argv
CATALOGO = [
    ("LP01", "Compreensão e interpretação de textos", [
        ("LP01.01", "Compreensão e interpretação de textos de gêneros variados"),
        ("LP01.02", "Relação do texto com seu contexto histórico e intertextualidade"),
        ("LP01.03", "Denotação, conotação e sentido de palavras e expressões no contexto"),
        ("LP01.04", "Discurso direto, discurso indireto e discurso indireto livre"),
        ("LP01.05", "Sinonímia, antonímia e relações de sentido")]),
    ("LP02", "Figuras de linguagem", [("LP02.01", "Figuras de linguagem")]),
    ("LP03", "Ortografia, acentuação e crase", [
        ("LP03.01", "Ortografia e acentuação"),
        ("LP03.02", "Emprego do sinal indicativo de crase")]),
    ("LP04", "Morfologia e formação de palavras", [
        ("LP04.01", "Elementos estruturais e processos de formação de palavras"),
        ("LP04.02", "Pronomes"),
        ("LP04.03", "Flexão nominal e flexão verbal"),
        ("LP04.04", "Vozes do verbo"),
        ("LP04.05", "Correlação de tempos e modos verbais")]),
    ("LP05", "Sintaxe", [
        ("LP05.01", "Morfossintaxe e funções sintáticas"),
        ("LP05.02", "Coordenação e subordinação"),
        ("LP05.03", "Conectivos")]),
    ("LP06", "Concordância", [("LP06.01", "Concordância nominal e concordância verbal")]),
    ("LP07", "Regência", [("LP07.01", "Regência nominal e regência verbal")]),
    ("LP08", "Pontuação", [("LP08.01", "Pontuação")]),
    ("LP09", "Redação e reescrita", [
        ("LP09.01", "Reescrita, equivalência e transformação de estruturas"),
        ("LP09.02", "Reconhecimento de frases corretas e incorretas; clareza, coesão e substituição de repetições"),
        ("LP09.03", "Organização e reorganização de orações e períodos")]),
]
if not simular:
    dst = RAIZ / "banco" / "backup" / f"estudos_antes_catalogo_lp_{datetime.date.today().isoformat()}.db"
    s = sqlite3.connect(BANCO); o = sqlite3.connect(dst); s.backup(o); o.close(); s.close()
    print("cópia de segurança:", dst.name)
con = sqlite3.connect(":memory:" if simular else BANCO)
if simular:
    real = sqlite3.connect(BANCO); real.backup(con); real.close()
disc = con.execute("select id from disciplinas where nome='Língua Portuguesa'").fetchone()[0]
hoje = datetime.date.today().isoformat()
na = npt = 0
for cod, nome, pontos in CATALOGO:
    r = con.execute("select id from assuntos where disciplina_id=? and codigo=?", (disc, cod)).fetchone()
    if not r:
        con.execute("insert into assuntos(disciplina_id,codigo,nome) values(?,?,?)", (disc, cod, nome)); na += 1
        r = con.execute("select id from assuntos where disciplina_id=? and codigo=?", (disc, cod)).fetchone()
    for pc, texto in pontos:
        if not con.execute("select 1 from pontos where codigo=?", (pc,)).fetchone():
            con.execute("insert into pontos(disciplina_id,assunto_id,codigo,texto,descricao,origem,ativo,criado_em) values(?,?,?,?,?,?,1,?)",
                        (disc, r[0], pc, texto, None, "edital DPE-AM 2026, Anexo II (15/11/2026)", hoje)); npt += 1
con.execute("insert into log_alteracoes(quem,o_que) values('script 58', ?)", (f"catálogo de Língua Portuguesa: {na} assuntos e {npt} pontos novos" + (" [simulação]" if simular else ""),))
if not simular:
    con.commit()
print(f"{na} assuntos e {npt} pontos criados" + (" (simulação)" if simular else ""))
