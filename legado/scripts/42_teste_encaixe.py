#!/usr/bin/env python3
"""Etapa 5 do plano do edital fictício geral: teste de encaixe (só leitura; não altera o banco).

Uso:  python -I scripts/42_teste_encaixe.py

As questões já classificadas de DH e de Penal cabem no desenho novo (temas, tópicos e edital geral)?
 A. Estrutura: o tópico principal continua existindo depois das mudanças aprovadas (renomeações, novos, PE02 -> Criminologia).
 B. Edital: o tópico tem pelo menos um item literal nos editais coletados.
 C. Conteúdo: as palavras-chave de tópicos aplicadas ao enunciado, ao detalhe e à alternativa certa da questão
    apontam o mesmo tópico (consistente), outro (divergente) ou nenhum (inconclusivo).
 D. Candidatas a tópico novo: a questão casa com um tópico novo e não casa com o atual.
Meta do plano: 95% ou mais sem mexer em nada.
"""
import importlib.util, json, re, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("consol", RAIZ / "scripts" / "41_consolidar_itens.py")
consol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consol)

CRIMINOLOGIA = {"PE02.01", "PE02.02", "PE02.03", "PE02.04"}


def carregar(alvo):
    reg = consol.regex_catalogo(alvo)
    novos = consol.DH_NOVOS if alvo == "DH" else consol.PENAL_NOVOS
    extra = {}
    for cod, (_, rx) in novos.items():
        extra[cod] = re.compile(rx, re.I)
    itens = json.loads((RAIZ / "dados" / "edital_ficticio_geral" / f"{alvo}_itens.json").read_text(encoding="utf-8"))["itens"]
    com_item = {p.rstrip("*") for i in itens for p in i["pontos"]}
    return reg, extra, com_item


def main():
    con = sqlite3.connect(RAIZ / "banco" / "estudos.db")
    res = {}
    for alvo, pref in (("DH", "DH"), ("PENAL", "PE")):
        reg, extra, com_item = carregar(alvo)
        rows = con.execute(
            """select q.id, p.nome, q.numero, q.enunciado, q.alt_a, q.alt_b, q.alt_c, q.alt_d, q.alt_e, q.gabarito,
                      k.detalhe, pt.codigo, pt2.codigo
               from classificacao k
               join questoes q on q.id = k.questao_id
               join provas p on p.id = q.prova_id
               join pontos pt on pt.id = k.ponto_id
               left join pontos pt2 on pt2.id = k.ponto2_id
               where pt.codigo like ?""", (pref + "%",)).fetchall()
        tot = len(rows)
        a = b = cons = dive = inco = 0
        cand, divs = [], []
        for qid, prova, num, enun, *alts, gab, det, cod, cod2 in rows:
            a += 1      # o código continua existindo (renomear/criar não remove nenhum)
            if cod in com_item or cod in CRIMINOLOGIA:
                b += 1
            letra = (gab or "").strip().lower()[:1]
            alt_certa = {"a": alts[0], "b": alts[1], "c": alts[2], "d": alts[3], "e": alts[4]}.get(letra, "") or ""
            txt = " ".join([enun or "", det or "", alt_certa])
            hits = [k for k, rx in reg.items() if rx.search(txt)]
            hits += [k.rstrip("*") for k, rx in extra.items() if rx.search(txt) and not k.endswith("*")]
            if cod in hits or (cod2 and cod2 in hits):
                cons += 1
            elif hits:
                dive += 1
                divs.append((prova, num, cod, (det or "")[:60], hits[:3]))
            else:
                inco += 1
            novos_hit = [k for k, rx in extra.items() if k.endswith("*") and rx.search(txt)]
            if novos_hit and cod not in hits:
                cand.append((prova, num, cod, (det or "")[:60], novos_hit))
        res[alvo] = (tot, a, b, cons, dive, inco, cand, divs)
        print(f"\n===== {alvo}: {tot} questões classificadas (tópico principal)")
        print(f"A. estrutura: o tópico continua existindo ........ {a} de {tot} ({100*a/tot:.0f}%)")
        print(f"B. edital: o tópico tem item literal nos editais .. {b} de {tot} ({100*b/tot:.0f}%)")
        print(f"C. conteúdo (palavras-chave): consistente {cons} | divergente {dive} | inconclusivo {inco}")
        print(f"   consistente + inconclusivo (não contradiz) ..... {cons+inco} de {tot} ({100*(cons+inco)/tot:.0f}%)")
        print(f"D. candidatas a tópico novo (só olhar, não mexer) .. {len(cand)}")
        for x in cand[:8]:
            print("     ", x[0][:34], "Q", x[1], "|", x[2], "->", x[4], "|", x[3])
        print("   divergentes (até 12):")
        for x in divs[:20]:
            print("     ", x[0][:34], "Q", x[1], "|", x[2], "| detalhe:", x[3], "| palavras-chave apontam:", x[4])


if __name__ == "__main__":
    main()
