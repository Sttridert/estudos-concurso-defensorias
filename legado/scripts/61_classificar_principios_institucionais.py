#!/usr/bin/env python3
"""Classifica as questões de PRINCÍPIOS E ATRIBUIÇÕES INSTITUCIONAIS do universo Analista FCC (39) nos pontos PI01.01 a PI06.03 (rascunho da IA).

Uso:  python -I scripts/61_classificar_principios_institucionais.py [--simular]

Grava em `classificacao` com origem "IA (rascunho) 15/11/2026" e `revisada = 0`; substitui a classificação existente da questão.
Chave: prova + número. Cópia do banco antes. As questões da DPE-SP (LC 988/2006 e Lei 1.050/2008) entram pelo TEMA (ponto equivalente
do catálogo, que segue o edital da DPE-AM); o comentário avisa que a lei é paulista. As 7 questões do PI06 (Código Penal e
Improbidade; CF fora dos arts. 5º, 37 e 134) eram cobradas no mesmo bloco das provas de 2018 a 2023, mas o edital 2026 não as lista.
"""
import datetime, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
simular = "--simular" in sys.argv
L, CC, J = "lei_seca", "caso_concreto", "jurisprudencia"
P18, P19 = "2018 - DPE-AM - Analista Jurídico", "2019 - DPE-AM - Analista Jurídico"
P22, P22B = "2022 - DPE-AM - Analista Jurídico", "2022 - DPE-AM - Analista Jurídico (2)"
P23, PSP = "2023 - DPE-AM - Analista Jurídico", "2025 - DPE-SP - Analista de Defensoria"
# (prova, número): (principal, secundário ou None, tipo, detalhe, confiança)
C = {
 (P18, 17): ("PI03.02", None, L, "Membros natos do Conselho Superior", "media"),
 (P18, 18): ("PI01.03", None, L, "Exceções constitucionais expressas aos incisos do art. 5º", "media"),
 (P18, 19): ("PI06.01", None, L, "Forma culposa do peculato", "media"),
 (P18, 20): ("PI06.03", None, L, "Competência privativa da União (art. 22 da CF)", "media"),
 (P19, 13): ("PI03.02", None, L, "Critérios de substituição dos membros", "media"),
 (P19, 14): ("PI02.02", None, L, "Atribuições da Corregedoria-Geral", "media"),
 (P19, 15): ("PI06.02", None, L, "Ato de improbidade contra os princípios da Administração", "media"),
 (P19, 16): ("PI06.02", None, L, "Sanções do ato de improbidade (recebimento de vantagem)", "media"),
 (P19, 17): ("PI03.01", None, L, "Atribuições previstas na Constituição do Amazonas", "media"),
 (P19, 18): ("PI06.01", None, L, "Excesso de exação", "media"),
 (P19, 19): ("PI03.02", None, L, "Licença considerada de efetivo exercício", "media"),
 (P19, 20): ("PI03.04", None, L, "Vedação à evolução funcional do servidor", "baixa"),
 (P22, 15): ("PI01.01", "PI01.02", L, "EC 80/2014 e a defesa dos direitos coletivos", "media"),
 (P22, 16): ("PI04.01", "PI02.01", L, "Direito do assistido à revisão da recusa de atuação", "media"),
 (P22, 17): ("PI06.01", None, CC, "Prevaricação de servidor da Defensoria", "media"),
 (P22, 18): ("PI03.02", "PI01.02", L, "Convênios e autonomia administrativa", "media"),
 (P22, 19): ("PI02.01", None, L, "Objetivos da Defensoria (art. 3º-A da LC 80/1994)", "media"),
 (P22, 20): ("PI03.04", None, L, "Evolução funcional dos servidores auxiliares", "media"),
 (P22B, 15): ("PI01.03", None, L, "Rol exemplificativo do art. 5º", "media"),
 (P22B, 16): ("PI02.04", None, L, "Prova do exercício do cargo (carteira funcional)", "media"),
 (P22B, 17): ("PI03.04", None, L, "Estágio probatório dos servidores", "media"),
 (P22B, 18): ("PI01.03", "PI04.02", L, "Inafastabilidade da jurisdição e conciliação extrajudicial", "media"),
 (P22B, 19): ("PI03.02", "PI02.02", L, "Defensor Público-Geral como órgão da Administração Superior", "media"),
 (P22B, 20): ("PI06.01", None, CC, "Peculato por servidor da Defensoria", "media"),
 (P23, 15): ("PI03.04", None, L, "Duração e critérios do estágio probatório", "media"),
 (P23, 16): ("PI02.02", None, L, "Competência da Corregedoria-Geral", "media"),
 (P23, 17): ("PI01.02", None, L, "Autonomia da Defensoria e emendas constitucionais", "media"),
 (P23, 18): ("PI06.02", None, L, "Responsabilidade do sucessor ou herdeiro", "media"),
 (P23, 19): ("PI02.03", None, L, "Natureza dos Núcleos da Defensoria", "media"),
 (P23, 20): ("PI03.01", "PI02.04", L, "Garantia do Defensor na Constituição do Amazonas", "media"),
 (PSP, 80): ("PI02.02", "PI03.05", L, "Inspeção e fiscalização (lei paulista)", "baixa"),
 (PSP, 81): ("PI04.01", None, L, "Conferências e participação dos usuários (lei paulista)", "baixa"),
 (PSP, 82): ("PI02.03", None, L, "Núcleos Especializados (lei paulista)", "baixa"),
 (PSP, 83): ("PI03.04", None, L, "Avaliação do estágio probatório do servidor (lei paulista)", "baixa"),
 (PSP, 84): ("PI04.01", None, L, "Direitos dos usuários (lei paulista)", "baixa"),
 (PSP, 85): ("PI04.02", None, CC, "Poder de requisição do Defensor (lei paulista)", "baixa"),
 (PSP, 86): ("PI01.02", "PI01.01", J, "Decisões do STF sobre a Defensoria", "media"),
 (PSP, 87): ("PI04.01", None, L, "Acesso aos mecanismos internacionais e Defensor Público Interamericano", "baixa"),
 (PSP, 88): ("PI01.03", None, L, "Abrangência da gratuidade da justiça", "baixa"),
}
if not simular:
    dst = RAIZ / "banco" / "backup" / f"estudos_antes_classificar_pi_{datetime.date.today().isoformat()}.db"
    s = sqlite3.connect(BANCO); o = sqlite3.connect(dst); s.backup(o); o.close(); s.close()
    print("cópia de segurança:", dst.name)
con = sqlite3.connect(":memory:" if simular else BANCO)
if simular:
    real = sqlite3.connect(BANCO); real.backup(con); real.close()
pontos = {c: i for i, c in con.execute("select id,codigo from pontos where codigo like 'PI%'")}
n = 0
for (prova, num), (p1, p2, tipo, det, conf) in C.items():
    q = con.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=? and q.disciplina_id=15", (prova, num)).fetchone()
    assert q, (prova, num)
    con.execute("delete from classificacao where questao_id=?", (q[0],))
    con.execute("insert into classificacao(questao_id,ponto_id,ponto2_id,assunto_provisorio_id,detalhe,tipo_cobranca,origem,confianca,revisada,atualizado_em) values(?,?,?,?,?,?,?,?,0,datetime('now'))",
                (q[0], pontos[p1], pontos[p2] if p2 else None, None, det, tipo, "IA (rascunho) 15/11/2026", conf))
    n += 1
con.execute("insert into log_alteracoes(quem,o_que) values('script 61', ?)", (f"{n} questões de Princípios Institucionais classificadas (rascunho)" + (" [simulação]" if simular else ""),))
if not simular:
    con.commit()
print(n, "questões classificadas" + (" (simulação)" if simular else ""))
