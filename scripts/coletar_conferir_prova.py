#!/usr/bin/env python3
"""Grupo A (Coletar): relatório de integridade das provas e migração do vocabulário do gabarito.

Uso (sempre com `python -I`):
  python -I scripts/coletar_conferir_prova.py relatorio [--prova "trecho do nome"] [--so-pendentes]
      Só leitura. Para cada prova diz "conferida" ou "pendente" e os motivos (ver scripts/lib_conferencia.py).
      "Conferida" é critério objetivo (contagem, alternativas, gabarito definitivo, nada em revisar_texto, vocabulário);
      a conferência do texto contra a imagem do caderno continua sendo sua (script `coletar_conferir_texto`).
  python -I scripts/coletar_conferir_prova.py migrar-situacao [--simular]
      Cria a coluna `provas.gabarito_situacao` (definitivo | preliminar | a_confirmar) e a preenche a partir do texto livre
      de `gabarito_status`, que não é alterado. Cópia do banco antes. Idempotente; recusa se a tag de "gabarito preliminar"
      mudaria para alguma prova.
"""
import argparse
import datetime
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_conferencia as C   # noqa: E402
import lib_escopo as LE       # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"


def relatorio(trecho=None, so_pendentes=False):
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    pd = C.provas_por_palavra(con)
    ids = [r["id"] for r in con.execute("select id from provas where nome like ? order by ano, nome", (f"%{trecho or ''}%",))]
    n_conf = 0
    for pid in ids:
        r = C.relatorio_prova(con, pid, pd)
        n_conf += r["estado"] == "conferida"
        if so_pendentes and r["estado"] == "conferida":
            continue
        marca = "CONFERIDA" if r["estado"] == "conferida" else "pendente "
        extra = " [OCR]" if r["ocr"] else ""
        print(f"{marca} {r['prova']}{extra}  ({r['questoes']} questões, {r['anuladas']} anuladas)")
        for m in r["motivos"]:
            print("     -", m)
        if r["atencao"]:
            print(f"     (atenção, não bloqueia) vocabulário incomum em {len(r['atencao'])} questões: {r['atencao']}")
    print(f"\n{n_conf} de {len(ids)} provas conferidas pelos critérios objetivos.")


def migrar_situacao(simular=False):
    con = sqlite3.connect(BANCO)
    con.row_factory = sqlite3.Row
    cols = [r["name"] for r in con.execute("pragma table_info(provas)")]
    provas = con.execute("select id, nome, gabarito_status from provas").fetchall()
    plano, falhas, mudaria_tag = [], [], []
    for p in provas:
        s = C.situacao_do_status(p["gabarito_status"])
        if s is None:
            falhas.append(p["nome"])
            continue
        # a tag antiga (lib_escopo.gabarito_preliminar) tem de continuar igual
        if LE.gabarito_preliminar(p["gabarito_status"]) != (s in ("preliminar", "a_confirmar")):
            mudaria_tag.append(p["nome"])
        plano.append((s, p["id"]))
    if falhas or mudaria_tag:
        sys.exit(f"Recusado. Status não reconhecido: {falhas}. Tag mudaria: {mudaria_tag}.")
    cont = {}
    for s, _ in plano:
        cont[s] = cont.get(s, 0) + 1
    print("situação por prova:", cont)
    if simular:
        print("(simulação: nada gravado)")
        return
    if "gabarito_situacao" not in cols:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_gabarito_situacao_{datetime.date.today().isoformat()}.db"
        if not dst.exists():
            out = sqlite3.connect(dst)
            con.backup(out)
            out.close()
            print("cópia de segurança:", dst.name)
        con.execute("alter table provas add column gabarito_situacao text")
    con.executemany("update provas set gabarito_situacao=? where id=?", plano)
    con.execute("insert into log_alteracoes(quem,o_que) values('coletar_conferir_prova migrar-situacao', ?)",
                (f"provas.gabarito_situacao preenchida: {cont}",))
    con.commit()
    print("gravado.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("relatorio")
    r.add_argument("--prova")
    r.add_argument("--so-pendentes", action="store_true")
    m = sub.add_parser("migrar-situacao")
    m.add_argument("--simular", action="store_true")
    x = ap.parse_args()
    if x.cmd == "relatorio":
        relatorio(x.prova, x.so_pendentes)
    else:
        migrar_situacao(x.simular)


if __name__ == "__main__":
    main()
