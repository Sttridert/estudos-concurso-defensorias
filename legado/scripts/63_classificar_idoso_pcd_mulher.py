#!/usr/bin/env python3
"""Classifica as 14 questões de Idoso, Pessoa com Deficiência e Mulher do universo Analista FCC que estavam sem classificação
(plano 05, item A4): 11 da DPE-AM 2018 (disciplina "Direito do Idoso e da Pessoa com Deficiência") e 3 do TJCE 2026
("Noções sobre Direitos das Pessoas com Deficiência"). Rascunho da IA: `revisada = 0`.

Uso:  python -I scripts/63_classificar_idoso_pcd_mulher.py [--simular]

Os pontos são os do catálogo de DH (DH08.01 mulheres, DH08.04 pessoas com deficiência, DH08.05 saúde mental, DH08.06 pessoas idosas).
A disciplina de origem da questão NÃO muda; o bloco do edital as pega pelos pontos tocados (decisão 41). Cópia do banco antes.
Chave: prova + número. Substitui a classificação existente da questão.
"""
import datetime, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
simular = "--simular" in sys.argv
L = "lei_seca"
P18, PTJ = "2018 - DPE-AM - Analista Jurídico", "2026 - TJCE - Analista Judiciário"
# (prova, número): (principal, secundário ou None, tipo, detalhe, confiança)
C = {
    (P18, 50): ("DH08.06", None, L, "Estatuto da Pessoa Idosa (Lei 10.741/2003): direito ao respeito (art. 10 e 17 a 18)", "alta"),
    (P18, 51): ("DH08.06", None, L, "Política Nacional do Idoso (Lei 8.842/1994): competências dos órgãos da área da saúde", "alta"),
    (P18, 52): ("DH08.06", None, L, "Lei estadual do Amazonas 4.463/2017: gratuidade e desconto do idoso nas passagens (norma estadual; confirmar)", "media"),
    (P18, 53): ("DH08.04", None, L, "Lei Brasileira de Inclusão (Lei 13.146/2015): direitos fundamentais", "alta"),
    (P18, 54): ("DH08.04", None, L, "Convenção sobre os Direitos das Pessoas com Deficiência e Protocolo Facultativo: obrigações do Estado", "alta"),
    (P18, 55): ("DH08.04", None, L, "Lei 7.853/1989: crimes contra a pessoa com deficiência", "alta"),
    (P18, 56): ("DH08.05", "DH08.04", L, "Lei 10.216/2001: direitos da pessoa com transtorno mental e internação voluntária", "alta"),
    (P18, 57): ("DH08.01", None, L, "Lei 12.845/2013: atendimento obrigatório e integral a vítimas de violência sexual", "alta"),
    (P18, 58): ("DH08.01", None, L, "Lei Maria da Penha: conceito de violência doméstica e familiar (âmbito da unidade doméstica)", "alta"),
    (P18, 59): ("DH08.01", None, L, "Lei Maria da Penha: medidas protetivas de urgência", "alta"),
    (P18, 60): ("DH08.01", None, L, "Diretrizes Nacionais de Abrigamento de Mulheres em Situação de Risco e Violência: casas-abrigo", "media"),
    (PTJ, 16): ("DH08.04", None, "caso_concreto", "Lei 13.146/2015: acessibilidade em espaços de lazer (quantidade de equipamentos acessíveis; texto a conferir)", "media"),
    (PTJ, 17): ("DH08.04", None, "caso_concreto", "Lei 13.146/2015: reserva de veículos acessíveis em frota de táxi (texto a conferir)", "media"),
    (PTJ, 18): ("DH08.04", None, "caso_concreto", "Lei 13.146/2015: crime de apropriação de bens ou rendimentos da pessoa com deficiência (texto a conferir)", "media"),
}


def main():
    con = sqlite3.connect(BANCO); cur = con.cursor()
    if not simular:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_classificar_idoso_pcd_{datetime.date.today().isoformat()}.db"
        if not dst.exists():
            out = sqlite3.connect(dst); con.backup(out); out.close(); print("cópia de segurança:", dst.name)
    pid = {c: (i, a) for c, i, a in cur.execute("select codigo,id,assunto_id from pontos")}
    agora = datetime.datetime.now().isoformat(timespec="seconds"); n = 0
    for (prova, num), (p1, p2, tipo, det, conf) in C.items():
        q = cur.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (prova, num)).fetchone()
        assert q, (prova, num)
        cur.execute("delete from classificacao where questao_id=?", (q[0],))
        cur.execute("""insert into classificacao(questao_id,ponto_id,ponto2_id,assunto_provisorio_id,detalhe,tipo_cobranca,origem,confianca,revisada,atualizado_em)
                       values (?,?,?,?,?,?,?,?,0,?)""", (q[0], pid[p1][0], pid[p2][0] if p2 else None, pid[p1][1], det, tipo, "IA (rascunho) 15/11/2026", conf, agora)); n += 1
    print(f"{n} questões classificadas")
    if simular:
        con.rollback(); print("(simulação: nada gravado)")
    else:
        cur.execute("insert into log_alteracoes(quem,o_que) values (?,?)", ("script 63", f"classificação de {n} questões de Idoso/PcD/Mulher (universo Analista FCC)"))
        con.commit()
    con.close()


if __name__ == "__main__":
    main()
