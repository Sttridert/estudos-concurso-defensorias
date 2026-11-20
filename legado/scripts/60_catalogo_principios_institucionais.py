#!/usr/bin/env python3
"""Cria no banco o catálogo de PRINCÍPIOS E ATRIBUIÇÕES INSTITUCIONAIS DA DEFENSORIA (assuntos PI01 a PI06, 20 pontos), aprovado pelo usuário em 15/11/2026.
PI06 guarda temas que as provas de 2018 a 2023 cobravam no mesmo bloco e o edital 2026 não lista (ficam "fora do edital").

Uso:  python -I scripts/60_catalogo_principios_institucionais.py [--simular]

Segue as frases dos blocos "Legislação da Defensoria" e "Conhecimentos Jurídicos e Institucionais" do Anexo II do edital DPE-AM 2026 (Conhecimentos Gerais, todos os cargos).
Idempotente (não duplica assuntos nem pontos). Cópia do banco antes e registro em `log_alteracoes`. Rascunho da IA aprovado
pelo usuário; a classificação das questões é outro passo.
"""
import datetime, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
simular = "--simular" in sys.argv
CATALOGO = [
    ("PI01", "Fundamentos constitucionais", [
        ("PI01.01", "CF art. 134: função essencial à Justiça, missão e necessitados"),
        ("PI01.02", "Autonomia funcional, administrativa e orçamentária (EC 45/2004, EC 80/2014 e outras)"),
        ("PI01.03", "Direitos e garantias fundamentais (CF art. 5º), inclusive assistência jurídica gratuita"),
        ("PI01.04", "Administração Pública (CF art. 37)")]),
    ("PI02", "Lei Orgânica Nacional (LC 80/1994)", [
        ("PI02.01", "Princípios, funções e objetivos institucionais"),
        ("PI02.02", "Organização: Administração Superior, Conselho Superior, Corregedoria e Defensor Público-Geral"),
        ("PI02.03", "Órgãos de atuação e de execução; núcleos"),
        ("PI02.04", "Carreira: garantias, prerrogativas, deveres e vedações dos membros")]),
    ("PI03", "Organização da DPE-AM e normas estaduais", [
        ("PI03.01", "Constituição do Estado do Amazonas (Defensoria Pública)"),
        ("PI03.02", "Lei Complementar estadual 01/1990 (Lei Orgânica da DPE-AM)"),
        ("PI03.03", "Lei estadual 1.762/1986"),
        ("PI03.04", "Lei estadual 4.077/2014 (servidores: estágio probatório e evolução funcional)"),
        ("PI03.05", "Demais normas estaduais da organização da DPE-AM")]),
    ("PI04", "Atuação institucional, extrajudicial e ética", [
        ("PI04.01", "Atuação institucional e direitos dos usuários"),
        ("PI04.02", "Atuação extrajudicial"),
        ("PI04.03", "Ética institucional")]),
    ("PI05", "Antidiscriminatório e justiça social", [
        ("PI05.01", "Igualdade e proibição de discriminação; ações afirmativas"),
        ("PI05.02", "Justiça social, inclusão e participação (raça, gênero, LGBTQIAPN+ e pessoas com deficiência)")]),
    ("PI06", "Cobrado em provas anteriores, fora do edital 2026", [
        ("PI06.01", "Crimes praticados por funcionário público contra a Administração (CP, arts. 312 a 327)"),
        ("PI06.02", "Improbidade administrativa (Lei 8.429/1992, arts. 1º a 12)"),
        ("PI06.03", "Outros temas da Constituição Federal fora dos arts. 5º, 37 e 134")]),
]
if not simular:
    dst = RAIZ / "banco" / "backup" / f"estudos_antes_catalogo_pi_{datetime.date.today().isoformat()}.db"
    s = sqlite3.connect(BANCO); o = sqlite3.connect(dst); s.backup(o); o.close(); s.close()
    print("cópia de segurança:", dst.name)
con = sqlite3.connect(":memory:" if simular else BANCO)
if simular:
    real = sqlite3.connect(BANCO); real.backup(con); real.close()
disc = con.execute("select id from disciplinas where nome='Princípios e Atribuições Institucionais da Defensoria'").fetchone()[0]
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
con.execute("insert into log_alteracoes(quem,o_que) values('script 60', ?)", (f"catálogo de Princípios Institucionais: {na} assuntos e {npt} pontos novos" + (" [simulação]" if simular else ""),))
if not simular:
    con.commit()
print(f"{na} assuntos e {npt} pontos criados" + (" (simulação)" if simular else ""))
