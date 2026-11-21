#!/usr/bin/env python3
"""Grupo E (Comentar): grava comentários da IA (rascunho) no banco, com as proteções da decisão 59. Substitui o antigo `32`.

Uso:  python -I scripts/comentar_gravar.py ARQUIVO.json [--perfil ID] [--substituir] [--aplicar] [--banco ARQ]
  Sem --aplicar só SIMULA (não grava, não faz cópia). Formato de cada entrada (chave "<prova>|<número>"):
    {"c": comentário, "p": pegadinha, "d": ["Norma|dispositivo"], "pend": 0/1,
     "fontes": [{"dispositivo": "Norma|dispositivo", "trecho": "texto literal", "arquivo": "dados/fontes/x.txt",
                 "url": "...", "consultado_em": "AAAA-MM-DD"}]}
  Regras: só questão válida; comentário existente é pulado (--substituir troca, nunca um `conferido`);
  --perfil ID recusa questão fora do universo do perfil; todo trecho citado tem de existir no arquivo de dados/fontes/;
  dispositivo em "d" sem trecho conferido faz o comentário entrar com pendente_confirmacao = 1."""
import argparse, datetime, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_comentarios as LC

RAIZ = LC.RAIZ


def processar(con, dados, perfil=None, substituir=False, aplicar=False, raiz=RAIZ):
    """Devolve (resumo, problemas). Se houver problema, nada é gravado."""
    permitidos = None
    if perfil is not None:
        permitidos = {q["id"] for q in LC.universo_do_perfil(con, perfil)}
    hoje = datetime.date.today().isoformat()
    plano, problemas = [], []
    for chave, v in dados.items():
        erros, sem_fonte = LC.validar_entrada(chave, v, raiz)
        if erros:
            problemas += [f"{chave}: {e}" for e in erros]
            continue
        prova, num = chave.rsplit("|", 1)
        q = con.execute("select q.id,q.situacao from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (prova, int(num))).fetchone()
        if not q:
            problemas.append(f"{chave}: questão não encontrada")
            continue
        if q[1] != "valida":
            problemas.append(f"{chave}: questão não está válida ({q[1]})")
            continue
        if permitidos is not None and q[0] not in permitidos:
            problemas.append(f"{chave}: fora do universo do perfil {perfil}")
            continue
        acao = LC.classificar(con, q[0], substituir)
        if acao == "conferido":
            problemas.append(f"{chave}: comentário já CONFERIDO pelo usuário; não é sobrescrito")
            continue
        plano.append((chave, q[0], acao, v, bool(sem_fonte)))
    resumo = {"novo": 0, "substituir": 0, "existe": 0, "forcado_pendente": 0}
    for chave, qid, acao, v, forca in plano:
        resumo[acao] += 1
        if acao == "existe":
            continue
        pend = 1 if (int(v.get("pend", 0)) or forca) else 0
        resumo["forcado_pendente"] += 1 if (forca and not int(v.get("pend", 0))) else 0
        if aplicar and not problemas:
            con.execute("insert or replace into comentarios(questao_id,texto,pegadinha,dispositivos,estado,pendente_confirmacao,autor,atualizado_em) values(?,?,?,?,?,?,?,?)",
                        (qid, v["c"], v.get("p", ""), json.dumps(v.get("d", []), ensure_ascii=False), "rascunho", pend, "IA (Claude)", hoje))
            LC.gravar_fontes(con, qid, v.get("fontes"))
    return resumo, problemas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo")
    ap.add_argument("--perfil", type=int)
    ap.add_argument("--substituir", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--banco", default=str(RAIZ / "banco" / "estudos.db"))
    a = ap.parse_args()
    dados = json.loads(Path(a.arquivo).read_text(encoding="utf-8"))
    con = sqlite3.connect(a.banco)
    if a.aplicar:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_comentar_{datetime.datetime.now():%Y-%m-%d_%H%M}.db"
        out = sqlite3.connect(dst); con.backup(out); out.close(); print("cópia de segurança:", dst.name)
    LC.garantir_tabela(con)
    resumo, problemas = processar(con, dados, a.perfil, a.substituir, a.aplicar)
    if problemas:
        con.rollback()
        print("NADA GRAVADO. Problemas:"); [print(" -", p) for p in problemas]
        sys.exit(1)
    if a.aplicar:
        con.execute("insert into log_alteracoes(quem,o_que) values('comentar_gravar', ?)", (f"{Path(a.arquivo).name}: {resumo} (rascunho)",))
        con.commit()
    else:
        con.rollback()
    print(("GRAVADO: " if a.aplicar else "SIMULAÇÃO (nada gravado; use --aplicar): "), resumo)


if __name__ == "__main__":
    main()
