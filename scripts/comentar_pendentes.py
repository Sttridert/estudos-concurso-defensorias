#!/usr/bin/env python3
"""Grupo E (Comentar), só leitura: lista as questões VÁLIDAS do universo de cada perfil que ainda não têm comentário
(e, com --pendentes, as marcadas "confirmar").

Uso:  python -I scripts/comentar_pendentes.py [--perfil ID ...] [--pendentes] [--saida PEDIDO.json] [--banco ARQ]
  Sem --perfil, olha os perfis de todos os perfil.toml. Com --saida, grava um pedido para a IA comentar, com enunciado,
  alternativas, gabarito e ponto de cada questão (chave "<prova>|<número>"). Nada é gravado no banco."""
import argparse, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_comentarios as LC


def ids_de_perfis():
    import lib_perfil as LP
    ids = []
    for arq in LP.achar_arquivos():
        c = LP.ler(arq)
        ids += [a["id"] for a in c.get("apostila", [])]
    return sorted(set(ids))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", type=int, action="append")
    ap.add_argument("--pendentes", action="store_true")
    ap.add_argument("--saida")
    ap.add_argument("--banco", default=str(LC.RAIZ / "banco" / "estudos.db"))
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.banco}?mode=ro", uri=True)
    com = {r[0]: r[1] or 0 for r in con.execute("select questao_id,pendente_confirmacao from comentarios")}
    pedido, vistos = {}, set()
    for pid in a.perfil or ids_de_perfis():
        try:
            qs = LC.universo_do_perfil(con, pid)
        except SystemExit as e:
            print(f"perfil {pid}: recusado pelo motor ({str(e)[:80]})"); continue
        sem = [q for q in qs if q["id"] not in com]
        pen = [q for q in qs if com.get(q["id"])]
        print(f"perfil {pid}: universo {len(qs)} válidas; sem comentário {len(sem)}; para confirmar {len(pen)}")
        for q in sem + (pen if a.pendentes else []):
            vistos.add(q["id"])
    if a.saida and vistos:
        for qid in sorted(vistos):
            r = con.execute("""select p.nome,q.numero,q.enunciado,q.alt_a,q.alt_b,q.alt_c,q.alt_d,q.alt_e,q.gabarito,po.codigo,po.texto
                from questoes q join provas p on p.id=q.prova_id left join classificacao c on c.questao_id=q.id left join pontos po on po.id=c.ponto_id
                where q.id=?""", (qid,)).fetchone()
            pedido[f"{r[0]}|{r[1]}"] = {"enunciado": r[2], "alternativas": dict(zip("ABCDE", r[3:8])), "gabarito": r[8],
                                        "ponto": f"{r[9]} {r[10]}" if r[9] else None, "ja_tem_comentario": qid in com}
        Path(a.saida).write_text(json.dumps(pedido, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"pedido com {len(pedido)} questões gravado em {a.saida}")


if __name__ == "__main__":
    main()
