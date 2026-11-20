#!/usr/bin/env python3
"""Grupo A (Coletar), pista de questões: corrigir ou confirmar o texto de questões marcadas `revisar_texto`.

Reúne os antigos 55 e 66. Chave da questão: prova + número (os IDs mudam). Cópia do banco antes de gravar (`banco/backup/`) e
registro em `log_alteracoes`. Só aplica o que o usuário pedir: o texto vem de transcrição conferida com a imagem do caderno
(`provas/` nunca é alterado).

Uso (sempre com `python -I`):
  python -I scripts/coletar_conferir_texto.py corrigir "<nome da prova>" <numero> [<numero> ...] [--simular]
      Lê `dados/correcoes_texto.json` ({prova: {numero: {disciplina, enunciado, alts[5], mover_para?}}}; `mover_para` troca a
      disciplina da questão) e, para cada número pedido, grava `enunciado` e `alt_a` a `alt_e` em `questoes` e passa `situacao`
      de `revisar_texto` para `valida`.                                                               (antigo 55)
  python -I scripts/coletar_conferir_texto.py confirmar "<nome da prova>" <numero> [<numero> ...] [--nota "texto"] [--simular]
      Passa `situacao` de `revisar_texto` para `valida` SEM mudar o texto (o texto já confere com o caderno). Para texto que
      precisa de correção use `corrigir`. `--simular` é novo (o 66 não tinha).                         (antigo 66)
Para saber quais provas e questões precisam disso: `scripts/coletar_conferir_prova.py relatorio`.
"""
import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"


def _abrir(simular, sufixo):
    """Em simulação trabalha numa cópia em memória; senão faz cópia de segurança do banco e abre o real."""
    if simular:
        con = sqlite3.connect(":memory:")
        real = sqlite3.connect(BANCO)
        real.backup(con)
        real.close()
        return con
    dst = RAIZ / "banco" / "backup" / f"estudos_antes_{sufixo}_{datetime.date.today().isoformat()}_{datetime.datetime.now().strftime('%H%M')}.db"
    s = sqlite3.connect(BANCO)
    o = sqlite3.connect(dst)
    s.backup(o)
    o.close()
    s.close()
    print("cópia de segurança:", dst.name)
    return sqlite3.connect(BANCO)


def corrigir(prova, numeros, simular=False):
    corr = json.loads((RAIZ / "dados" / "correcoes_texto.json").read_text(encoding="utf-8"))[prova]
    con = _abrir(simular, "correcao_texto")
    pid = con.execute("select id from provas where nome=?", (prova,)).fetchone()[0]
    marca = " [simulação]" if simular else ""
    for n in numeros:
        c = corr[n]
        assert len(c["alts"]) == 5, f"Q{n}: precisa de 5 alternativas"
        r = con.execute("select id,situacao from questoes where prova_id=? and numero=?", (pid, int(n))).fetchone()
        con.execute("update questoes set enunciado=?, alt_a=?, alt_b=?, alt_c=?, alt_d=?, alt_e=?, "
                    "situacao=case when situacao='revisar_texto' then 'valida' else situacao end where id=?",
                    (c["enunciado"], *c["alts"], r[0]))
        if c.get("mover_para"):
            dd = con.execute("select id from disciplinas where nome=?", (c["mover_para"],)).fetchone()
            assert dd, c["mover_para"]
            con.execute("update questoes set disciplina_id=?, motivo_situacao=? where id=?",
                        (dd[0], "disciplina e texto refeitos pela imagem do caderno em 15/11/2026", r[0]))
            con.execute("insert into log_alteracoes(quem,o_que) values('coletar_conferir_texto corrigir', ?)",
                        (f"{prova} Q{n} movida para {c['mover_para']}{marca}",))
        con.execute("insert into log_alteracoes(quem,o_que) values('coletar_conferir_texto corrigir', ?)",
                    (f"texto corrigido de {prova} Q{n} (era {r[1]}){marca}",))
        print(f"Q{n}: texto corrigido (situação era {r[1]})")
    if not simular:
        con.commit()
    else:
        print("(simulação: nada gravado)")


def confirmar(prova, numeros, nota="", simular=False):
    con = _abrir(simular, "confirmar_texto")
    pid = con.execute("select id from provas where nome=?", (prova,)).fetchone()[0]
    n = 0
    for num in numeros:
        r = con.execute("select id,situacao from questoes where prova_id=? and numero=?", (pid, num)).fetchone()
        if not r or r[1] != "revisar_texto":
            print(f"Q{num}: ignorada (situação {r[1] if r else 'inexistente'})")
            continue
        con.execute("update questoes set situacao='valida', motivo_situacao=? where id=?",
                    (f"texto conferido com a imagem do caderno em {datetime.date.today().isoformat()}" + (f"; {nota}" if nota else ""), r[0]))
        n += 1
    con.execute("insert into log_alteracoes(quem,o_que) values('coletar_conferir_texto confirmar', ?)",
                (f"{prova}: {n} questões com texto confirmado" + (" [simulação]" if simular else ""),))
    if not simular:
        con.commit()
    print(n, "questões confirmadas" + (" (simulação: nada gravado)" if simular else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("corrigir")
    c.add_argument("prova")
    c.add_argument("numeros", nargs="+")
    c.add_argument("--simular", action="store_true")
    f = sub.add_parser("confirmar")
    f.add_argument("prova")
    f.add_argument("numeros", nargs="+", type=int)
    f.add_argument("--nota", default="")
    f.add_argument("--simular", action="store_true")
    x = ap.parse_args()
    if x.cmd == "corrigir":
        corrigir(x.prova, x.numeros, x.simular)
    else:
        confirmar(x.prova, x.numeros, x.nota, x.simular)


if __name__ == "__main__":
    sys.exit(main())
