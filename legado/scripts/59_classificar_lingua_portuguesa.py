#!/usr/bin/env python3
"""Classifica as questões de LÍNGUA PORTUGUESA do universo Analista FCC (99) nos pontos LP01.01 a LP09.03 (rascunho da IA, confiança média).

Uso:  python -I scripts/59_classificar_lingua_portuguesa.py [--simular]

Grava em `classificacao` (ponto principal, secundário, detalhe, tipo de cobrança) com origem "IA (rascunho) 15/11/2026" e
`revisada = 0`. Substitui a classificação existente da questão. Chave: prova + número. Cópia do banco antes.
Tipos de cobrança: `interpretacao` (texto) e `gramatica` (norma); a apostila_lib interpreta os dois (não alteram o banco antigo).
"""
import datetime, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
simular = "--simular" in sys.argv
I, G = "interpretacao", "gramatica"
P18, P19 = "2018 - DPE-AM - Analista Jurídico", "2019 - DPE-AM - Analista Jurídico"
P22, P22B = "2022 - DPE-AM - Analista Jurídico", "2022 - DPE-AM - Analista Jurídico (2)"
P23, PSP = "2023 - DPE-AM - Analista Jurídico", "2025 - DPE-SP - Analista de Defensoria"
PMP, PTJ = "2025 - MPPI - Analista Ministerial", "2026 - TJCE - Analista Judiciário"
# (prova, número): (principal, secundário ou None, tipo, detalhe)
C = {
 (P18, 1): ("LP01.01", None, I, "Sentido de uma afirmação no contexto"),
 (P18, 2): ("LP01.01", "LP02.01", I, "Metáfora do fogo selvagem"),
 (P18, 3): ("LP01.01", None, I, "Referente de expressões qualificativas"),
 (P18, 4): ("LP01.03", None, I, "Sentido de expressão no contexto"),
 (P18, 5): ("LP09.02", None, G, "Clareza e correção de comentário sobre o texto"),
 (P18, 6): ("LP06.01", "LP04.05", G, "Concordância verbal e tempos e modos"),
 (P18, 7): ("LP09.01", None, G, "Reescrita que preserva o sentido (subordinação temporal)"),
 (P18, 8): ("LP04.04", None, G, "Voz ativa para voz passiva"),
 (P18, 9): ("LP01.01", None, I, "Argumento do autor"),
 (P18, 10): ("LP01.05", None, I, "Segmentos em oposição de sentido"),
 (P18, 11): ("LP04.02", "LP07.01", G, "Pronomes relativos e oblíquos (da qual, cujo, em que)"),
 (P18, 12): ("LP06.01", None, G, "Concordância verbal com o elemento sublinhado"),
 (P18, 13): ("LP08.01", None, G, "Pontuação da frase"),
 (P18, 14): ("LP01.01", None, I, "Distinção entre mediação e conciliação"),
 (P18, 15): ("LP05.01", None, G, "Função sintática dos termos sublinhados"),
 (P18, 16): ("LP09.01", None, G, "Nova redação de uma frase do texto"),
 (P19, 1): ("LP01.01", None, I, "Tese dos biólogos sobre o bem-estar"),
 (P19, 2): ("LP01.05", None, I, "Relação de causa e efeito entre segmentos"),
 (P19, 3): ("LP01.03", None, I, "Sentido de segmento do texto"),
 (P19, 4): ("LP09.02", None, G, "Clareza e correção de comentário sobre o texto"),
 (P19, 5): ("LP04.04", "LP06.01", G, "Voz passiva e concordância"),
 (P19, 6): ("LP09.01", "LP05.02", G, "Integração de orações em período único"),
 (P19, 7): ("LP01.01", None, I, "Conceito de acomodação social"),
 (P19, 8): ("LP01.03", None, I, "Sentido de “cooperação antagônica”"),
 (P19, 9): ("LP01.01", None, I, "Inferência do terceiro parágrafo"),
 (P19, 10): ("LP09.01", None, G, "Nova redação sem prejuízo do sentido"),
 (P19, 11): ("LP05.01", None, G, "Função sintática dos termos sublinhados"),
 (P19, 12): ("LP04.02", "LP09.01", G, "Substituição de repetições por pronomes"),
 (P22, 1): ("LP01.01", None, I, "Núcleo da crônica de Fernando Sabino"),
 (P22, 2): ("LP01.03", None, I, "Sentido de segmento do texto"),
 (P22, 3): ("LP06.01", None, G, "Concordância verbal"),
 (P22, 4): ("LP09.01", "LP05.03", G, "Substituição de segmento sem prejuízo do sentido"),
 (P22, 5): ("LP04.04", "LP04.05", G, "Voz passiva e correlação de tempos verbais"),
 (P22, 6): ("LP01.01", None, I, "Argumento central de Voltaire"),
 (P22, 7): ("LP01.05", None, I, "Segmentos que expressam contradição"),
 (P22, 8): ("LP04.03", None, G, "Flexão do imperativo e do presente na 2ª pessoa do singular"),
 (P22, 9): ("LP09.01", "LP05.03", G, "Nova redação com “porém”"),
 (P22, 10): ("LP04.02", "LP07.01", G, "Pronomes relativos (de que, de cuja, onde, cujos)"),
 (P22, 11): ("LP01.01", None, I, "Relação estabelecida no primeiro parágrafo"),
 (P22, 12): ("LP01.01", None, I, "Posicionamento do autor"),
 (P22, 13): ("LP05.03", None, G, "Sentido funcional de condicionalidade"),
 (P22, 14): ("LP08.01", None, G, "Pontuação do período"),
 (P22B, 1): ("LP01.03", None, I, "Sentido de “compulsão inefável”"),
 (P22B, 2): ("LP01.01", None, I, "Atitude do cronista"),
 (P22B, 3): ("LP01.01", None, I, "Atributos do texto que o cronista idealiza"),
 (P22B, 4): ("LP06.01", None, G, "Concordância verbal"),
 (P22B, 5): ("LP04.02", "LP07.01", G, "Pronomes relativos com preposição (em que, aonde, às quais)"),
 (P22B, 6): ("LP04.04", None, G, "Voz passiva do mais-que-perfeito"),
 (P22B, 7): ("LP09.01", None, G, "Nova redação preservando o sentido"),
 (P22B, 8): ("LP01.01", None, I, "Tese sobre a ordem civilizatória"),
 (P22B, 9): ("LP01.03", None, I, "Sentido de expressões do texto"),
 (P22B, 10): ("LP01.03", None, I, "Sentido de segmento do texto"),
 (P22B, 11): ("LP04.03", "LP04.05", G, "Flexão verbal"),
 (P22B, 12): ("LP08.01", None, G, "Vírgula e mudança de sentido"),
 (P22B, 13): ("LP09.01", "LP05.02", G, "Integração de orações em período único"),
 (P22B, 14): ("LP04.02", "LP09.01", G, "Substituição de repetições por pronomes oblíquos"),
 (P23, 1): ("LP01.01", None, I, "Relevância das experiências do cronista"),
 (P23, 2): ("LP01.01", None, I, "Estruturação do texto em parágrafos"),
 (P23, 3): ("LP04.02", "LP07.01", G, "Pronomes relativos (na qual, a que, das quais, cuja, aonde)"),
 (P23, 4): ("LP04.04", None, G, "Transposição para a voz passiva"),
 (P23, 5): ("LP01.03", None, I, "Sentido de segmento do texto"),
 (P23, 6): ("LP01.01", None, I, "Paradoxo nas crônicas de Rubem Braga"),
 (P23, 7): ("LP06.01", None, G, "Concordância verbal"),
 (P23, 8): ("LP01.01", None, I, "Ideia central do texto"),
 (P23, 9): ("LP01.03", None, I, "Paráfrase de passagem do texto"),
 (P23, 10): ("LP01.01", None, I, "Passagem que confirma uma ideia"),
 (P23, 11): ("LP09.01", "LP05.02", G, "Integração de orações em período único"),
 (P23, 12): ("LP04.05", None, G, "Correlação de tempos e modos verbais"),
 (P23, 13): ("LP04.02", "LP09.01", G, "Substituição de repetições por pronomes"),
 (P23, 14): ("LP08.01", None, G, "Pontuação da frase"),
 (PSP, 1): ("LP01.01", None, I, "Sentido da citação de Emerson no texto"),
 (PSP, 2): ("LP01.01", None, I, "Posição do autor sobre a IA"),
 (PSP, 3): ("LP01.01", None, I, "Crítica ao nome “inteligência artificial”"),
 (PSP, 4): ("LP04.02", None, G, "Referentes de pronomes"),
 (PSP, 5): ("LP05.01", None, G, "Funções do “se”"),
 (PSP, 6): ("LP06.01", None, G, "Concordância verbal com o elemento sublinhado"),
 (PSP, 7): ("LP09.02", "LP06.01", G, "Redação gramaticalmente correta"),
 (PMP, 1): ("LP01.01", None, I, "Trecho em que o cronista se dirige ao leitor"),
 (PMP, 2): ("LP02.01", None, I, "Hipérbole"),
 (PMP, 3): ("LP04.02", None, G, "Retomada de expressão por palavra sublinhada"),
 (PMP, 4): ("LP01.04", "LP04.03", G, "Transposição para o discurso direto"),
 (PMP, 5): ("LP04.05", None, G, "Fato anterior ao passado (mais-que-perfeito)"),
 (PMP, 6): ("LP04.01", None, G, "Prefixo de negação"),
 (PMP, 7): ("LP01.01", None, I, "Sentido do poema"),
 (PMP, 8): ("LP05.01", None, G, "Sujeito da forma verbal"),
 (PMP, 9): ("LP05.03", "LP01.05", G, "Valor de “só que”"),
 (PMP, 10): ("LP01.01", None, I, "Ideia enfatizada no trecho do romance"),
 (PMP, 11): ("LP05.01", None, G, "Pleonasmo do objeto indireto"),
 (PMP, 12): ("LP08.01", None, G, "Vírgula em enumeração"),
 (PTJ, 1): ("LP05.02", "LP05.03", G, "Valor da oração subordinada final"),
 (PTJ, 2): ("LP01.01", None, I, "Período sobre o qual a fortuna perdeu o direito"),
 (PTJ, 3): ("LP01.01", None, I, "Como Sêneca caracteriza o presente"),
 (PTJ, 4): ("LP04.03", None, G, "Verbo na segunda pessoa do singular"),
 (PTJ, 5): ("LP02.01", None, I, "Antítese"),
 (PTJ, 6): ("LP04.02", None, G, "Palavra sublinhada que retoma termo anterior"),
 (PTJ, 7): ("LP05.01", None, G, "Palavra usada como substantivo"),
 (PTJ, 8): ("LP05.01", None, G, "Objeto direto pleonástico"),
 (PTJ, 9): ("LP04.01", None, G, "Prefixo de negação"),
 (PTJ, 10): ("LP05.03", "LP05.01", G, "“Se” como conjunção condicional"),
}
if not simular:
    dst = RAIZ / "banco" / "backup" / f"estudos_antes_classificar_lp_{datetime.date.today().isoformat()}.db"
    s = sqlite3.connect(BANCO); o = sqlite3.connect(dst); s.backup(o); o.close(); s.close()
    print("cópia de segurança:", dst.name)
con = sqlite3.connect(":memory:" if simular else BANCO)
if simular:
    real = sqlite3.connect(BANCO); real.backup(con); real.close()
pontos = {c: i for i, c in con.execute("select id,codigo from pontos where codigo like 'LP%'")}
n = 0
for (prova, num), (p1, p2, tipo, det) in C.items():
    q = con.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=? and q.disciplina_id=17", (prova, num)).fetchone()
    assert q, (prova, num)
    con.execute("delete from classificacao where questao_id=?", (q[0],))
    con.execute("insert into classificacao(questao_id,ponto_id,ponto2_id,assunto_provisorio_id,detalhe,tipo_cobranca,origem,confianca,revisada,atualizado_em) values(?,?,?,?,?,?,?,?,0,datetime('now'))",
                (q[0], pontos[p1], pontos[p2] if p2 else None, None, det, tipo, "IA (rascunho) 15/11/2026", "media"))
    n += 1
con.execute("insert into log_alteracoes(quem,o_que) values('script 59', ?)", (f"{n} questões de Língua Portuguesa classificadas (rascunho)" + (" [simulação]" if simular else ""),))
if not simular:
    con.commit()
print(n, "questões classificadas" + (" (simulação)" if simular else ""))
