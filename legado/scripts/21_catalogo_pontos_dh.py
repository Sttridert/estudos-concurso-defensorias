"""Etapa 2: grava o catalogo mestre de pontos de Direitos Humanos no banco permanente.
Fonte: dados/catalogo_pontos_direitos_humanos.csv (assunto;codigo;texto;descricao;regex_presenca).
Presenca por edital: procura as expressoes em banco/programas_dh/*.txt (so indicativo; conferir).
Idempotente: pode rodar de novo (atualiza textos; nao apaga classificacao). Gera banco/catalogo_pontos_dh.md.
"""
import csv, re, sqlite3, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "banco" / "estudos.db"
CSV = BASE / "dados" / "catalogo_pontos_direitos_humanos.csv"
PROG = BASE / "banco" / "programas_dh"
RELATORIO = BASE / "banco" / "catalogo_pontos_dh.md"
NOME_EDITAL = "Defensoria FCC · Direitos Humanos"
HOJE = datetime.date.today().isoformat()

con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys=ON")
con.execute("CREATE TABLE IF NOT EXISTS ponto_fontes (ponto_id INT NOT NULL REFERENCES pontos(id), edital_origem TEXT NOT NULL, presente INT NOT NULL, PRIMARY KEY(ponto_id, edital_origem))")

disc = con.execute("select id from disciplinas where nome like 'Direitos Humanos%'").fetchone()[0]
ass = {c: i for i, c in con.execute("select id, codigo from assuntos where disciplina_id=?", (disc,))}
nomes_ass = {c: n for c, n in con.execute("select codigo, nome from assuntos where disciplina_id=?", (disc,))}

progs = {p.stem: p.read_text(encoding="utf-8", errors="ignore") for p in sorted(PROG.glob("*.txt"))}
linhas = list(csv.DictReader(open(CSV, encoding="utf-8"), delimiter=";"))

for l in linhas:
    a = ass[l["assunto"]]
    row = con.execute("select id from pontos where disciplina_id=? and codigo=?", (disc, l["codigo"])).fetchone()
    if row:
        con.execute("update pontos set assunto_id=?, texto=?, descricao=? where id=?", (a, l["texto"], l["descricao"], row[0]))
    else:
        con.execute("insert into pontos(disciplina_id,assunto_id,codigo,texto,descricao,origem,criado_em) values(?,?,?,?,?,?,?)",
                    (disc, a, l["codigo"], l["texto"], l["descricao"], "editais e provas FCC de Defensorias (IA, rascunho)", HOJE))
pid = {c: i for i, c in con.execute("select id, codigo from pontos where disciplina_id=?", (disc,))}

# presenca por edital
pres = {}
for l in linhas:
    rx = re.compile(l["regex_presenca"], re.I)
    pres[l["codigo"]] = {n: bool(rx.search(t)) for n, t in progs.items()}
    for n, v in pres[l["codigo"]].items():
        con.execute("insert or replace into ponto_fontes values(?,?,?)", (pid[l["codigo"]], n, int(v)))

con.execute("insert or ignore into editais(nome,tipo,banca,carreira,cargo,descricao,criado_em) values(?,?,?,?,?,?,?)",
            (NOME_EDITAL, "ficticio", "FCC", "Defensoria", "Defensor Público",
             "Edital ficticio: uniao dos pontos de Direitos Humanos dos editais de Defensorias (FCC) de 2021 a 2026", HOJE))
eid = con.execute("select id from editais where nome=?", (NOME_EDITAL,)).fetchone()[0]
recentes = [n for n in progs if n[:4] in ("2025", "2026")]
for ordem, l in enumerate(linhas, 1):
    p = pres[l["codigo"]]
    com = [n for n, v in p.items() if v]
    novo = int(bool(com) and all(n in recentes for n in com))
    excl = int(len(com) == 1)
    con.execute("insert or replace into edital_pontos values(?,?,?,?,?,?,0)", (eid, pid[l["codigo"]], ordem, l["texto"], novo, excl))
con.execute("insert into log_alteracoes(quem,o_que) values('script 21', ?)", (f"catalogo DH: {len(linhas)} pontos; edital {NOME_EDITAL}",))
con.commit()

# relatorio
out = [f"# Catálogo de pontos — Direitos Humanos (rascunho da IA)\n", f"Gerado em {HOJE} por `scripts/21_catalogo_pontos_dh.py`. **{len(linhas)} pontos** em {len(ass)} assuntos; edital fictício «{NOME_EDITAL}».\n",
       f"Presença = a expressão-chave aparece no trecho de Direitos Humanos de cada um dos {len(progs)} programas ({', '.join(sorted(progs)[:1])} … {sorted(progs)[-1]}). É indicativo (busca por palavras); conferir.\n",
       "Marcas: **novo** = só aparece nos editais de 2025/2026; **exclusivo** = aparece em um único edital; **sem presença** = não achado em nenhum programa (ponto vindo das questões).\n"]
atual = None
for l in linhas:
    if l["assunto"] != atual:
        atual = l["assunto"]; out.append(f"\n## {atual} — {nomes_ass.get(atual, '')}\n")
        out.append("| Código | Ponto | Editais (de %d) | Marcas |\n|---|---|---|---|" % len(progs))
    com = sum(pres[l["codigo"]].values())
    marcas = []
    e = con.execute("select marca_novo, marca_exclusivo from edital_pontos where edital_id=? and ponto_id=?", (eid, pid[l["codigo"]])).fetchone()
    if e[0]: marcas.append("novo")
    if e[1]: marcas.append("exclusivo")
    if com == 0: marcas.append("sem presença")
    out.append(f"| {l['codigo']} | {l['texto']} | {com} | {', '.join(marcas)} |")
RELATORIO.write_text("\n".join(out) + "\n", encoding="utf-8")
print(len(linhas), "pontos gravados;", "relatorio:", RELATORIO)
