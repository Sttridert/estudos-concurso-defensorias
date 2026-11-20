#!/usr/bin/env python3
"""Grupo C (Mapear): aplica um RASCUNHO de classificação de questões ao banco, com validação (decisão 56 do `02`).

Uso:
  python -I scripts/mapear_aplicar_classificacao.py <rascunho.csv>                       # simulação (padrão): valida e mostra o que mudaria
  python -I scripts/mapear_aplicar_classificacao.py <rascunho.csv> --aplicar [--ajustar-disciplina]   # grava (cópia do banco antes)
  opções: --banco ARQ (outro banco, para teste)

Rascunho = CSV com ';' e as colunas do `dados/classificacao/<disciplina>.csv`:
  prova;numero;ponto;ponto2;tipo_cobranca;detalhe;confianca;origem;revisada;assunto_provisorio;atualizado_em
O rascunho pode misturar disciplinas (o principal de cada linha manda). Um rascunho serve a qualquer disciplina.

O que confere (ERRO impede de gravar; AVISO só informa):
 ERRO  questão não existe (prova + número); questão já classificada (este script só INSERE, nunca sobrescreve);
       ponto inexistente ou inativo; principal igual ao secundário; linha repetida; secundário sem principal.
 AVISO principal em disciplina que não é a da questão nem aparece no rótulo original da prova (marca "fora do bloco", decisão 56c);
       questão que não é 'valida'.
`--ajustar-disciplina`: a disciplina da questão passa a ser a do tópico principal (só quando difere); cada mudança é listada.
Depois de aplicar, rodar `python -I scripts/71_catalogo_e_classificacao.py exportar` para regenerar `dados/classificacao/` do banco.
Não toca em `revisada` (vem do arquivo; o padrão é 0).
"""
import csv, datetime, sqlite3, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
CAMPOS = ["prova", "numero", "ponto", "ponto2", "tipo_cobranca", "detalhe", "confianca", "origem", "revisada", "assunto_provisorio", "atualizado_em"]


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def palavra_chave(nome):
    n = norm(nome)
    for pre in ("direitos ", "direito da ", "direito do ", "direito de ", "direito "):
        if n.startswith(pre):
            n = n[len(pre):]
            break
    return "execu" if n.startswith("execu") else n


def validar(con, linhas):
    erros, avisos, plano, vistos = [], [], [], set()
    pontos = {}
    for i, c, d, a in con.execute("select id,codigo,disciplina_id,ativo from pontos"):
        pontos[c] = (i, d, a)
    disc = {i: n for i, n in con.execute("select id,nome from disciplinas")}
    for n, l in enumerate(linhas, 2):
        ref = f"linha {n} ({l['prova']} nº {l['numero']})"
        chave = (l["prova"], l["numero"])
        if chave in vistos:
            erros.append(f"{ref}: repetida"); continue
        vistos.add(chave)
        q = con.execute("""select q.id,q.situacao,q.disciplina_id,q.disciplina_original from questoes q join provas p on p.id=q.prova_id
                           where p.nome=? and q.numero=?""", (l["prova"], int(l["numero"]))).fetchone()
        if not q:
            erros.append(f"{ref}: questão não existe"); continue
        if con.execute("select 1 from classificacao where questao_id=?", (q[0],)).fetchone():
            erros.append(f"{ref}: já tem classificação (este script só insere)"); continue
        p1, p2 = l["ponto"], l["ponto2"]
        if not p1:
            erros.append(f"{ref}: sem ponto principal"); continue
        bad = False
        for c in (p1, p2):
            if c and (c not in pontos or not pontos[c][2]):
                erros.append(f"{ref}: ponto {c} não existe ou está inativo"); bad = True
        if bad:
            continue
        if p1 == p2:
            erros.append(f"{ref}: principal igual ao secundário"); continue
        d_princ = pontos[p1][1]
        if q[1] != "valida":
            avisos.append(f"{ref}: questão com situação '{q[1]}'")
        if d_princ != q[2] and palavra_chave(disc[d_princ]) not in norm(q[3]):
            avisos.append(f"{ref}: principal {p1} é de {disc[d_princ]}, que não é a disciplina da questão ({disc[q[2]]}) nem aparece em «{q[3]}» (fora do bloco?)")
        plano.append({"qid": q[0], "l": l, "p1": pontos[p1][0], "p2": pontos[p2][0] if p2 else None, "d_antes": q[2], "d_princ": d_princ})
    return erros, avisos, plano


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("--"):
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    arq = Path(a[0])
    banco = Path(a[a.index("--banco") + 1]) if "--banco" in a else BANCO
    aplicar, ajustar = "--aplicar" in a, "--ajustar-disciplina" in a
    with open(arq, encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    faltam = [c for c in CAMPOS if linhas and c not in linhas[0]]
    if faltam:
        sys.exit("faltam colunas no rascunho: " + ", ".join(faltam))
    if aplicar:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_classificacao_{datetime.datetime.now():%Y-%m-%d_%H%M}.db"
        s = sqlite3.connect(banco); o = sqlite3.connect(dst); s.backup(o); o.close(); s.close()
        print("cópia de segurança:", dst.name)
        con = sqlite3.connect(banco)
    else:
        con = sqlite3.connect(":memory:"); real = sqlite3.connect(f"file:{banco}?mode=ro", uri=True); real.backup(con); real.close()
    con.execute("PRAGMA foreign_keys=ON")
    erros, avisos, plano = validar(con, linhas)
    for e in erros:
        print("ERRO:", e)
    for v in avisos:
        print("AVISO:", v)
    if erros:
        con.close(); sys.exit(f"{len(erros)} erro(s); nada foi gravado.")
    agora = datetime.datetime.now().isoformat(timespec="seconds")
    mudam = [p for p in plano if p["d_antes"] != p["d_princ"]]
    for p in plano:
        l = p["l"]
        con.execute("""insert into classificacao(questao_id,ponto_id,ponto2_id,assunto_provisorio_id,detalhe,tipo_cobranca,origem,confianca,revisada,atualizado_em)
                       values(?,?,?,?,?,?,?,?,?,?)""", (p["qid"], p["p1"], p["p2"], None, l["detalhe"], l["tipo_cobranca"], l["origem"], l["confianca"], int(l["revisada"] or 0), agora))
        if ajustar and p["d_antes"] != p["d_princ"]:
            con.execute("update questoes set disciplina_id=? where id=?", (p["d_princ"], p["qid"]))
    nome = {i: n for i, n in con.execute("select id,nome from disciplinas")}
    resumo = {}
    for p in mudam:
        resumo[(nome[p["d_antes"]], nome[p["d_princ"]])] = resumo.get((nome[p["d_antes"]], nome[p["d_princ"]]), 0) + 1
    print(f"{len(plano)} classificações a inserir ({sum(1 for p in plano if p['p2'])} com secundário); {len(avisos)} aviso(s).")
    print(f"{len(mudam)} questões com disciplina diferente da do tópico principal" + (" (SERÃO AJUSTADAS)" if ajustar else " (use --ajustar-disciplina para ajustar)") + ":")
    for (de, para), k in sorted(resumo.items()):
        print(f"   {de} -> {para}: {k}")
    if aplicar:
        con.execute("insert into log_alteracoes(quem,o_que) values('mapear_aplicar_classificacao', ?)",
                    (f"{arq.name}: {len(plano)} classificações inseridas; disciplinas ajustadas: {len(mudam) if ajustar else 0}",))
        con.commit()
        print("GRAVADO. Agora rodar: python -I scripts/71_catalogo_e_classificacao.py exportar")
    else:
        print("(simulação: nada foi gravado)")
    con.close()


if __name__ == "__main__":
    main()
