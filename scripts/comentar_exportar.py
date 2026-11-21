#!/usr/bin/env python3
"""Grupo E (Comentar): exporta os comentários do BANCO (fonte única) para dados/comentarios/comentarios.json (arquivo derivado,
como o `71 exportar`). Só lê o banco. `--conferir` só diz se o arquivo está igual ao banco (saída 1 se não).

Uso:  python -I scripts/comentar_exportar.py [--conferir] [--banco ARQ] [--saida ARQ]"""
import argparse, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_comentarios as LC


def montar(con):
    tem = con.execute("select 1 from sqlite_master where name='comentario_fontes'").fetchone()
    fontes = {}
    if tem:
        for qid, d, t, ar, u, dt in con.execute("select questao_id,dispositivo,trecho,arquivo,url,consultado_em from comentario_fontes order by id"):
            fontes.setdefault(qid, []).append({"dispositivo": d, "trecho": t, "arquivo": ar, "url": u, "consultado_em": dt})
    out = {}
    for qid, pr, n, t, p, d, e, pc, au, at in con.execute("""select c.questao_id,pv.nome,q.numero,c.texto,c.pegadinha,c.dispositivos,c.estado,
            coalesce(c.pendente_confirmacao,0),c.autor,c.atualizado_em from comentarios c join questoes q on q.id=c.questao_id
            join provas pv on pv.id=q.prova_id order by pv.nome,q.numero"""):
        out[f"{pr}|{n}"] = {"c": t, "p": p, "d": json.loads(d) if d else [], "estado": e, "pend": pc, "autor": au,
                            "atualizado_em": at, "fontes": fontes.get(qid, [])}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conferir", action="store_true")
    ap.add_argument("--banco", default=str(LC.RAIZ / "banco" / "estudos.db"))
    ap.add_argument("--saida", default=str(LC.RAIZ / "dados" / "comentarios" / "comentarios.json"))
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.banco}?mode=ro", uri=True)
    texto = json.dumps(montar(con), ensure_ascii=False, indent=1)
    arq = Path(a.saida)
    if a.conferir:
        igual = arq.exists() and arq.read_text(encoding="utf-8") == texto
        print("arquivo igual ao banco" if igual else "arquivo DIFERENTE do banco (rode sem --conferir)")
        sys.exit(0 if igual else 1)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(texto, encoding="utf-8")
    print(f"{len(json.loads(texto))} comentários exportados para {arq}")


if __name__ == "__main__":
    main()
