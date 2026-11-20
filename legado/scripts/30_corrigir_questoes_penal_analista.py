"""Corrige no banco permanente as questoes de Direito Penal das provas de Analista da FCC (13/11/2026).
1. DPE-AM 2023 Analista: o OCR jogou as questoes 41 a 47 dentro do texto bruto da Q40 (enunciado vazio).
   Texto reconstituido pela IA a partir do OCR do caderno (Tipo 005); gabarito ja estava no banco. Conferir no PDF.
2. DPE-AM 2018 Analista: cabecalho combinado "Direito Penal e Direito Processual Penal"; Q41 a Q43 sao de
   Processo Penal (apelacao, cautelares, competencia) e Q44 de Execucao Penal (saidas).
3. Limpeza de rodapes do caderno colados na alternativa E e de erros obvios de OCR nas questoes de Penal.
Idempotente."""
import sqlite3
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
con = sqlite3.connect(RAIZ / "banco" / "estudos.db")
PEN, PPEN, EXEC = 5, 6, 7
NOTA = "texto reconstituido pela IA a partir do OCR do caderno em 13/11/2026; conferir no PDF"

AM23 = {
 41: (PEN, "A lei penal posterior", ["retroagirá em qualquer hipótese.", "não retroagirá, salvo a pedido da vítima.", "não retroagirá, salvo para beneficiar o réu.", "não retroagirá, salvo para prejudicar o réu.", "não retroagirá em nenhuma hipótese."]),
 42: (PEN, "A anistia, a graça e o indulto são causas", ["excludentes da ilicitude.", "excludentes da culpabilidade.", "suspensivas da prescrição.", "interruptivas da prescrição.", "extintivas da punibilidade."]),
 43: (PEN, "A intervenção estatal consistente na repressão penal apenas se justifica se houver lesão ou perigo de lesão ao bem jurídico tutelado, de acordo com o princípio da", ["insignificância.", "humanidade.", "legalidade.", "ofensividade.", "adequação social."]),
 44: (PEN, "O uso moderado dos meios necessários para repelir injusta agressão, atual ou iminente, a direito próprio ou de terceira pessoa, configura", ["estado de necessidade.", "legítima defesa.", "coação irresistível.", "exercício regular de direito.", "estrito cumprimento do dever legal."]),
 45: (PEN, "A conduta do agente prevista e punida pela lei penal que tem como causa a imprudência, negligência ou imperícia configura o crime", ["culposo.", "doloso.", "preterdoloso.", "comissivo por omissão.", "omissivo."]),
 46: (PPEN, "O habeas corpus poderá ser impetrado", ["por qualquer pessoa, desde que exclusivamente em seu favor.", "por qualquer pessoa, em seu favor ou de outrem.", "pelo próprio paciente ou por procurador legalmente habilitado, apenas.", "pelo próprio paciente ou pelo cônjuge, ascendente, descendente ou irmão, apenas.", "por qualquer pessoa, exceto pelo próprio paciente."]),
 47: (PPEN, "Lançadas em 2015, [...] consistem na rápida apresentação da pessoa que foi presa a um juiz, em uma audiência onde também são ouvidos Ministério Público, Defensoria Pública ou advogado do preso. (Disponível em: www.cnj.jus.br)\nO texto acima trata das chamadas audiências", ["de custódia.", "de justificação.", "de mediação.", "preliminares.", "de instrução, debates e julgamento."]),
}
pid = lambda nome: con.execute("select id from provas where nome=?", (nome,)).fetchone()[0]
p23 = pid("2023 - DPE-AM - Analista Jurídico")
for n, (disc, enun, alts) in AM23.items():
    orig = "Direito Penal" if disc == PEN else "Direito Processual Penal"
    con.execute("""update questoes set disciplina_id=?, disciplina_original=?, enunciado=?, alt_a=?, alt_b=?, alt_c=?, alt_d=?, alt_e=?,
                   situacao='valida', motivo_situacao=?, texto_fonte='corrigido manualmente (OCR)' where prova_id=? and numero=?""",
                (disc, orig, enun, *alts, NOTA, p23, n))

p18 = pid("2018 - DPE-AM - Analista Jurídico")
for n, d in ((41, PPEN), (42, PPEN), (43, PPEN), (44, EXEC)):
    con.execute("update questoes set disciplina_id=?, motivo_situacao=coalesce(motivo_situacao||'; ','')||? where prova_id=? and numero=? and disciplina_id<>?",
                (d, "disciplina separada do cabecalho combinado Penal/Processo Penal em 13/11/2026", p18, n, d))

# rodapes colados e OCR obvio (so questoes de Penal das provas de Analista)
TROCAS = [(" DPEAM-An.Jur.Def.-Ciências Jurídicas-A01 9", ""), (" 12 DPESP-An.Defensoria Pública-AQ1-PF", ""),
          (" DPESP-An.Defensoria Pública-A01-PF 13", ""), ("intemação", "internação"), ("otratamento", "o tratamento"),
          ("cnamando", "chamando"), ("a vitima", "a vítima"), ("da vitima", "da vítima"), ("12anos", "12 anos"),
          ("IeII.", "I e II."), ("IIeIII.", "II e III."), ("IeIV.", "I e IV."), ("IIIe Iv.", "III e IV."), ("I,IIIeIv.", "I, III e IV."),
          ("Iv. Em se tratando", "IV. Em se tratando")]
rows = con.execute("""select q.id,q.enunciado,q.alt_a,q.alt_b,q.alt_c,q.alt_d,q.alt_e from questoes q join provas p on p.id=q.prova_id
                      where q.disciplina_id=? and p.banca='FCC' and p.cargo like 'Analista%'""", (PEN,)).fetchall()
mud = 0
for r in rows:
    novos = []
    for t in r[1:]:
        if t:
            for a, b in TROCAS:
                t = t.replace(a, b)
        novos.append(t)
    if novos != list(r[1:]):
        mud += 1
        con.execute("update questoes set enunciado=?,alt_a=?,alt_b=?,alt_c=?,alt_d=?,alt_e=? where id=?", (*novos, r[0]))
con.execute("insert into log_alteracoes(quem,o_que) values('script 30', ?)",
            (f"Penal Analista: AM2023 Q41-47 reconstituidas do OCR (41-45 Penal, 46-47 Proc. Penal); AM2018 Q41-43 -> Proc. Penal, Q44 -> Execucao; {mud} questoes com limpeza de OCR/rodape",))
con.commit()
print("ok; questoes limpas:", mud)
