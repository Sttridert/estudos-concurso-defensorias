"""Importa um edital (real ou ficticio) como visao do catalogo de pontos: tabelas editais e edital_pontos.
Uso: python scripts/28_importar_edital.py dados/edital_<...>.json
O JSON traz o edital (nome, tipo, banca, carreira, cargo, ano, descricao, arquivo), o PROGRAMA LITERAL da disciplina
("programa": [{"item": "1", "topicos": ["frase 1 do item, ipsis litteris", ...]}, ...]) e a lista de pontos que o edital
cobre, na ordem do programa: {"p": codigo do ponto, "texto": resumo do que o edital diz,
"trechos": [{"i": "item", "t": "trecho literal do edital"}, ...]}.
Regras (decisao do usuario de 13/11/2026):
- o programa e copiado do PDF do edital sem alterar uma palavra; a apostila o mostra como "edital verticalizado";
- cada trecho tem de existir, igual, dentro do item indicado; se nao existir, o script para (guardrail contra parafrase);
- os itens de cada ponto ("itens") sao calculados a partir dos trechos.
O mapeamento item do edital -> ponto e feito pela IA (rascunho) e deve ser conferido. Pontos do catalogo que nao constam
no edital ficam de fora de edital_pontos (a apostila os mostra como 'fora do edital'). Idempotente (substitui o mapeamento).
"""
import json, sqlite3, sys, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "banco" / "estudos.db"
d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
con = sqlite3.connect(DB)

# colunas novas (13/11/2026): programa literal do edital e trechos literais por ponto
if "programa" not in [c[1] for c in con.execute("pragma table_info(editais)")]:
    con.execute("alter table editais add column programa TEXT")          # JSON: [{item, topicos: [...]}]
if "trechos" not in [c[1] for c in con.execute("pragma table_info(edital_pontos)")]:
    con.execute("alter table edital_pontos add column trechos TEXT")     # JSON: [{i, t}]

disc = con.execute("select id from disciplinas where nome=?", (d["disciplina"],)).fetchone()[0]
pts = {c: i for i, c in con.execute("select id, codigo from pontos where disciplina_id=?", (disc,))}
programa = d.get("programa") or []
texto_item = {it["item"]: " ".join(it["topicos"]) for it in programa}
erros = []
for x in d["pontos"]:
    if x["p"] not in pts:
        erros.append(f"ponto inexistente no catalogo: {x['p']}")
    for t in x.get("trechos", []):
        if t["i"] not in texto_item:
            erros.append(f"{x['p']}: item {t['i']} nao existe no programa")
        elif t["t"] not in texto_item[t["i"]]:
            erros.append(f"{x['p']}: trecho nao e literal do item {t['i']}: {t['t']!r}")
    if programa and not x.get("trechos"):
        erros.append(f"{x['p']}: sem trechos literais do edital")
if erros:
    sys.exit("edital NAO importado:\n  " + "\n  ".join(erros))

desc = d["descricao"] + (" Arquivo: " + d["arquivo"] if d.get("arquivo") else "") + (" " + d["observacao_bloco"] if d.get("observacao_bloco") else "")
prog_json = json.dumps(programa, ensure_ascii=False) if programa else None
r = con.execute("select id from editais where nome=?", (d["nome"],)).fetchone()
if r:
    eid = r[0]
    con.execute("update editais set tipo=?,banca=?,carreira=?,cargo=?,ano=?,descricao=?,programa=? where id=?", (d["tipo"], d["banca"], d["carreira"], d["cargo"], d["ano"], desc, prog_json, eid))
    con.execute("delete from edital_pontos where edital_id=?", (eid,))
else:
    con.execute("insert into editais(nome,tipo,banca,carreira,cargo,ano,descricao,criado_em,programa) values(?,?,?,?,?,?,?,?,?)",
                (d["nome"], d["tipo"], d["banca"], d["carreira"], d["cargo"], d["ano"], desc, datetime.date.today().isoformat(), prog_json))
    eid = con.execute("select id from editais where nome=?", (d["nome"],)).fetchone()[0]
for ordem, x in enumerate(d["pontos"], 1):
    trechos = x.get("trechos", [])
    itens = ", ".join(sorted({t["i"] for t in trechos}, key=int)) if trechos else x.get("itens", "")
    con.execute("insert into edital_pontos(edital_id,ponto_id,ordem,texto_no_edital,marca_novo,marca_exclusivo,marca_detalhado,trechos) values(?,?,?,?,?,0,0,?)",
                (eid, pts[x["p"]], ordem, f"Itens {itens}: {x['texto']}", int(x.get("novo", 0)), json.dumps(trechos, ensure_ascii=False) if trechos else None))
fora = sorted(set(pts) - {x["p"] for x in d["pontos"]})
sem_ponto = [f"{it['item']}.{k}" for it in programa for k, f in enumerate(it["topicos"], 1)
             if not any(t["i"] == it["item"] and t["t"] in f for x in d["pontos"] for t in x.get("trechos", []))]
con.execute("insert into log_alteracoes(quem,o_que) values('script 28', ?)", (f"edital {d['nome']}: {len(d['pontos'])} pontos no edital, {len(fora)} fora; programa literal com {sum(len(it['topicos']) for it in programa)} frases",))
con.commit()
print(f"edital id {eid}: {len(d['pontos'])} pontos no edital; fora do edital ({len(fora)}): {', '.join(fora)}")
if programa:
    print(f"programa literal: {len(programa)} itens; frases sem ponto: {', '.join(sem_ponto) or 'nenhuma'}")
