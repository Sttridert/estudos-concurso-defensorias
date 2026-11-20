#!/usr/bin/env python3
"""Grupo B (Catalogar): conjunto de referência (gold set) para medir a classificação de questões em um catálogo.

Ideia: uma amostra de questões é classificada às cegas (sem ver o rótulo atual) por três leitores independentes entre si, na medida do
possível: duas leituras da IA (com ordem e apresentação diferentes) e um classificador estatístico por código (sem LLM). Onde os leitores e o
rótulo atual divergem, o USUÁRIO arbitra. O resultado mede (a) a concordância entre leitores, (b) a taxa de erro dos rótulos atuais, que são
rascunho da IA, e (c) serve de régua para comparar o catálogo v1 com o v2.

Uso (sempre com `python -I`):
  python -I scripts/catalogar_referencia.py sortear [--n 110] [--semente 20261120]
      Sorteia a amostra estratificada (por disciplina; pontos em rodízio; anos e provas espalhados) e grava
      `dados/referencia/amostra_<data>.csv` (prova;numero;disciplina;ponto_atual;assunto_atual;ano). Reproduzível pela semente.
  python -I scripts/catalogar_referencia.py linha-de-base [--folds 5]
      Só leitura. Classificador por código (TF-IDF, centroide mais próximo), validação cruzada: mede quão bem o catálogo atual é
      "aprendível" dos próprios rótulos (acurácia e macro-F1 por disciplina, em ponto e em assunto) e grava as previsões fora da amostra.
  python -I scripts/catalogar_referencia.py leitura DISCIPLINA [--ordem normal|inversa]
      Só leitura. Imprime o catálogo da disciplina e as questões da amostra SEM o rótulo atual, para a leitura às cegas.
  python -I scripts/catalogar_referencia.py concordancia
      Só leitura. Lê as leituras (`dados/referencia/leitura_ia1.json`, `leitura_ia2.json`) e calcula concordância (kappa de Cohen).
  python -I scripts/catalogar_referencia.py arbitragem [--controles 30]
      Gera o pacote de arbitragem para o usuário (divergências + uma amostra de controle das concordâncias) em `dados/referencia/arbitragem_<data>.md`.
  python -I scripts/catalogar_referencia.py registrar ARQUIVO.json
      Grava as decisões do usuário em `dados/referencia/referencia_ouro.csv` (origem "usuario").
Os rótulos da referência ficam em ARQUIVOS (`dados/referencia/`); o banco não é alterado por este script.
"""
import collections
import csv
import datetime
import json
import math
import random
import re
import sqlite3
import statistics as st
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_disciplinas as LD  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
REF = RAIZ / "dados" / "referencia"

COTAS = {"DH": 12, "CONST": 12, "ADM": 12, "CIV": 12, "PCIV": 12, "PENAL": 12, "PPEN": 12, "ECA": 10, "LP": 8, "PI": 8}  # soma 110
STOP = set("de da do das dos a o as os e em no na nos nas que para por com um uma ao se ou sao ser como mais sua seu pela pelo ante sobre entre ate art lei "
           "alternativa assinale correta incorreta acordo conforme segundo seguintes seguinte afirmativa afirmativas".split())


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def tok(s):
    return [w for w in re.findall(r"[a-z]{3,}", norm(s)) if w not in STOP]


def abrir():
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def texto_questao(r):
    return " ".join(str(r[k] or "") for k in ("enunciado", "alt_a", "alt_b", "alt_c", "alt_d", "alt_e"))


def questoes_classificadas(con):
    """Questões válidas com ponto principal, com o texto e os dados do ponto e do assunto."""
    return con.execute("""
        select q.id as qid, p.nome as prova, p.ano, q.numero, q.enunciado, q.alt_a, q.alt_b, q.alt_c, q.alt_d, q.alt_e, q.gabarito,
               pt.id as ponto_id, pt.codigo as ponto, pt.texto as ponto_nome, pt.disciplina_id as disc_id,
               a.codigo as assunto, a.nome as assunto_nome
        from classificacao c
        join questoes q on q.id=c.questao_id and q.situacao='valida'
        join provas p on p.id=q.prova_id
        join pontos pt on pt.id=c.ponto_id
        join assuntos a on a.id=pt.assunto_id
        order by p.ano, p.nome, q.numero""").fetchall()


def sigla_de_disc(con):
    nome_de = {r["id"]: r["nome"] for r in con.execute("select id,nome from disciplinas")}
    inv = {LD.nome(s): s for s in LD.SIGLAS}
    return {i: inv.get(n) for i, n in nome_de.items()}


# ---------------------------------------------------------------- sortear
def sortear(n_total, semente):
    con = abrir()
    sg = sigla_de_disc(con)
    rows = questoes_classificadas(con)
    por_disc = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        s = sg.get(r["disc_id"])
        if s in COTAS:
            por_disc[s][r["ponto"]].append(r)
    rnd = random.Random(semente)
    escolhidas = []
    escala = n_total / sum(COTAS.values())
    for s, cota in COTAS.items():
        cota = max(1, round(cota * escala))
        pontos = list(por_disc[s])
        rnd.shuffle(pontos)
        for p in pontos:
            rnd.shuffle(por_disc[s][p])
        usados_prova, usados_ano = collections.Counter(), collections.Counter()
        pegas = []
        while len(pegas) < cota and any(por_disc[s][p] for p in pontos):
            for p in pontos:
                if len(pegas) >= cota:
                    break
                cand = por_disc[s][p]
                if not cand:
                    continue
                # prefere a questão de prova e ano menos usados até agora
                cand.sort(key=lambda r: (usados_prova[r["prova"]], usados_ano[r["ano"]]))
                r = cand.pop(0)
                usados_prova[r["prova"]] += 1
                usados_ano[r["ano"]] += 1
                pegas.append(r)
        escolhidas += [(s, r) for r in pegas]
    REF.mkdir(parents=True, exist_ok=True)
    arq = REF / f"amostra_{datetime.date.today().isoformat()}.csv"
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["prova", "numero", "disciplina", "ponto_atual", "assunto_atual", "ano"])
        for s, r in escolhidas:
            w.writerow([r["prova"], r["numero"], s, r["ponto"], r["assunto"], r["ano"]])
    print(f"amostra de {len(escolhidas)} questões (semente {semente}) gravada em {arq.relative_to(RAIZ)}")
    cont = collections.Counter(s for s, _ in escolhidas)
    anos = collections.Counter(r["ano"] for _, r in escolhidas)
    print("por disciplina:", dict(cont))
    print("por ano:", dict(sorted(anos.items())))
    pts = {(s, r["ponto"]) for s, r in escolhidas}
    print(f"pontos distintos cobertos: {len(pts)}")


# ---------------------------------------------------------------- classificador por código
def vetor_tfidf(docs):
    df = collections.Counter(w for d in docs for w in set(d))
    n = len(docs)
    idf = {w: math.log((1 + n) / (1 + c)) + 1 for w, c in df.items()}

    def vec(d):
        tf = collections.Counter(d)
        v = {w: (1 + math.log(c)) * idf[w] for w, c in tf.items() if w in idf}
        nr = math.sqrt(sum(x * x for x in v.values())) or 1
        return {w: x / nr for w, x in v.items()}
    return vec


def cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0) for w, x in a.items())


def prever_centroide(treino, teste, rotulo):
    """Centroide mais próximo (TF-IDF). `treino`/`teste`: listas de (id, tokens, rotulo). Devolve {id: (rotulo_previsto, similaridade)}."""
    vec = vetor_tfidf([t[1] for t in treino])
    cent = collections.defaultdict(lambda: collections.defaultdict(float))
    for _, toks, r in treino:
        for w, x in vec(toks).items():
            cent[r][w] += x
    cents = {}
    for r, d in cent.items():
        nr = math.sqrt(sum(x * x for x in d.values())) or 1
        cents[r] = {w: x / nr for w, x in d.items()}
    out = {}
    for i, toks, _ in teste:
        v = vec(toks)
        melhor = max(((cos(v, c), r) for r, c in cents.items()), default=(0, None))
        out[i] = (melhor[1], melhor[0])
    return out


def macro_f1(reais, previstos):
    rotulos = set(reais) | set(previstos)
    f1s = []
    for r in rotulos:
        tp = sum(1 for a, b in zip(reais, previstos) if a == r and b == r)
        fp = sum(1 for a, b in zip(reais, previstos) if a != r and b == r)
        fn = sum(1 for a, b in zip(reais, previstos) if a == r and b != r)
        if tp + fn == 0:
            continue   # rótulo que só aparece nas previsões não entra na média (sem exemplo real)
        p = tp / (tp + fp) if tp + fp else 0
        rc = tp / (tp + fn)
        f1s.append(2 * p * rc / (p + rc) if p + rc else 0)
    return st.mean(f1s) if f1s else 0


def validacao_cruzada(rows, folds, nivel):
    """Previsões fora da amostra por disciplina do ponto. `nivel`: 'ponto' ou 'assunto'."""
    sg_rows = collections.defaultdict(list)
    for r in rows:
        sg_rows[r["disc_id"]].append(r)
    prev = {}
    for d, lst in sg_rows.items():
        dados = [(r["qid"], tok(texto_questao(r)), r[nivel]) for r in lst]
        rnd = random.Random(7)
        idx = list(range(len(dados)))
        rnd.shuffle(idx)
        for f in range(folds):
            teste = [dados[i] for k, i in enumerate(idx) if k % folds == f]
            treino = [dados[i] for k, i in enumerate(idx) if k % folds != f]
            if not treino or not teste:
                continue
            prev.update(prever_centroide(treino, teste, None))
    return prev


def linha_de_base(folds):
    con = abrir()
    sg = sigla_de_disc(con)
    rows = questoes_classificadas(con)
    print(f"{len(rows)} questões classificadas; classificador por código (TF-IDF, centroide mais próximo), validação cruzada de {folds} partes.\n")
    print(f"{'disciplina':34} {'n':>4}  {'ponto: acur.':>12} {'macro-F1':>9}   {'assunto: acur.':>14} {'macro-F1':>9}   pontos com 1 questão só")
    resultado = {}
    previsoes = {}
    for nivel in ("ponto", "assunto"):
        prev = validacao_cruzada(rows, folds, nivel)
        for r in rows:
            previsoes.setdefault(r["qid"], {})[nivel] = prev.get(r["qid"], (None, 0))[0]
        resultado[nivel] = prev
    por_disc = collections.defaultdict(list)
    for r in rows:
        por_disc[sg.get(r["disc_id"])].append(r)
    todos = {"ponto": ([], []), "assunto": ([], [])}
    linhas = {}
    for s in LD.SIGLAS:
        lst = por_disc.get(s)
        if not lst:
            continue
        medidas = {}
        for nivel in ("ponto", "assunto"):
            reais = [r[nivel] for r in lst]
            prevs = [previsoes[r["qid"]][nivel] for r in lst]
            acc = sum(a == b for a, b in zip(reais, prevs)) / len(reais)
            medidas[nivel] = (acc, macro_f1(reais, prevs))
            todos[nivel][0].extend(reais)
            todos[nivel][1].extend(prevs)
        unicos = sum(1 for c in collections.Counter(r["ponto"] for r in lst).values() if c == 1)
        print(f"{LD.nome(s)[:34]:34} {len(lst):4d}  {medidas['ponto'][0]:12.2f} {medidas['ponto'][1]:9.2f}   {medidas['assunto'][0]:14.2f} {medidas['assunto'][1]:9.2f}   {unicos}")
        linhas[s] = {"n": len(lst), "ponto_acuracia": round(medidas["ponto"][0], 3), "ponto_macro_f1": round(medidas["ponto"][1], 3),
                     "assunto_acuracia": round(medidas["assunto"][0], 3), "assunto_macro_f1": round(medidas["assunto"][1], 3), "pontos_com_1_questao": unicos}
    for nivel in ("ponto", "assunto"):
        a, b = todos[nivel]
        print(f"TOTAL {nivel}: acurácia {sum(x == y for x, y in zip(a, b)) / len(a):.2f}; macro-F1 (média por rótulo) {macro_f1(a, b):.2f}")
    REF.mkdir(parents=True, exist_ok=True)
    arq = REF / "linha_de_base_classificador_v1.json"
    arq.write_text(json.dumps({"gerado_em": datetime.date.today().isoformat(), "folds": folds, "metodo": "TF-IDF + centroide mais próximo, validação cruzada por disciplina",
                               "por_disciplina": linhas, "previsoes": {str(r["prova"]) + "|" + str(r["numero"]): {"ponto": previsoes[r["qid"]]["ponto"], "assunto": previsoes[r["qid"]]["assunto"]} for r in rows}},
                              ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print("\nprevisões fora da amostra gravadas em", arq.relative_to(RAIZ))


# ---------------------------------------------------------------- leitura às cegas
def ler_amostra():
    arqs = sorted(REF.glob("amostra_*.csv"))
    if not arqs:
        sys.exit("não há amostra; rode `sortear` antes.")
    with open(arqs[-1], encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";")), arqs[-1]


def cortar(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n].rstrip() + " [...]"


def leitura(sigla, ordem):
    sigla = sigla.upper()
    amostra, _ = ler_amostra()
    linhas = [r for r in amostra if r["disciplina"] == sigla]
    if not linhas:
        sys.exit(f"nenhuma questão da amostra em {sigla}")
    con = abrir()
    did = con.execute("select id from disciplinas where nome=?", (LD.nome(sigla),)).fetchone()[0]
    pts = con.execute("select pt.codigo, pt.texto, a.codigo as ac, a.nome as an from pontos pt join assuntos a on a.id=pt.assunto_id "
                      "where pt.disciplina_id=? and pt.ativo=1 order by pt.codigo", (did,)).fetchall()
    print(f"=== CATÁLOGO DE {LD.nome(sigla).upper()} ({len(pts)} pontos) ===")
    if ordem == "normal":
        atual = None
        for p in pts:
            if p["ac"] != atual:
                atual = p["ac"]
                print(f"\n[{p['ac']}] {p['an']}")
            print(f"   {p['codigo']}  {p['texto']}")
    else:   # apresentação diferente: lista plana em ordem alfabética, sem agrupar por assunto
        for p in sorted(pts, key=lambda p: norm(p["texto"])):
            print(f"   {p['codigo']}  {p['texto']}")
    ordem_q = list(linhas) if ordem == "normal" else list(reversed(linhas))
    print(f"\n=== QUESTÕES ({len(ordem_q)}; rótulo atual OCULTO) ===")
    ids = {f"{x['prova']}|{x['numero']}": f"Q{k:03d}" for k, x in enumerate(amostra, 1)}   # id curto, estável: posição na amostra
    for i, r in enumerate(ordem_q, 1):
        q = con.execute("select q.* from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (r["prova"], int(r["numero"]))).fetchone()
        print(f"\n#{ids[r['prova'] + '|' + str(r['numero'])]}  (disciplina da questão: {con.execute('select nome from disciplinas where id=?', (q['disciplina_id'],)).fetchone()[0]})")
        print("  " + cortar(q["enunciado"], 750))
        for L in "abcde":
            print(f"  ({L.upper()}) " + cortar(q[f"alt_{L}"], 150))


# ---------------------------------------------------------------- concordância e arbitragem
def assunto_de(codigo):
    return codigo.split(".")[0] if codigo else None


def carregar_leitores():
    """Devolve (amostra, leitores): leitores = {nome: {chave: codigo_do_ponto}}. `atual` = rótulo no banco; `ia1`/`ia2` = leituras às cegas
    da IA (arquivos); `cod` = previsão fora da amostra do classificador por código."""
    amostra, _ = ler_amostra()
    chave = lambda r: f"{r['prova']}|{r['numero']}"  # noqa: E731
    leitores = {"atual": {chave(r): r["ponto_atual"] for r in amostra}}
    for nome, arq in (("ia1", "leitura_ia1.json"), ("ia2", "leitura_ia2.json")):
        p = REF / arq
        if p.exists():
            leitores[nome] = json.loads(p.read_text(encoding="utf-8"))
    p = REF / "linha_de_base_classificador_v1.json"
    if p.exists():
        prev = json.loads(p.read_text(encoding="utf-8"))["previsoes"]
        leitores["cod"] = {chave(r): prev[chave(r)]["ponto"] for r in amostra if chave(r) in prev and prev[chave(r)]["ponto"]}
    return amostra, leitores


def kappa(a, b):
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def concordancia():
    amostra, L = carregar_leitores()
    chaves = [f"{r['prova']}|{r['numero']}" for r in amostra]
    print(f"{len(chaves)} questões na amostra; leitores disponíveis: {', '.join(L)}\n")
    pares = [(x, y) for i, x in enumerate(L) for y in list(L)[i + 1:]]
    print(f"{'par':14} {'n':>4}  {'ponto: acordo':>13} {'kappa':>6}   {'assunto: acordo':>15} {'kappa':>6}")
    for x, y in pares:
        ks = [k for k in chaves if k in L[x] and k in L[y]]
        pa, pb = [L[x][k] for k in ks], [L[y][k] for k in ks]
        aa, ab = [assunto_de(v) for v in pa], [assunto_de(v) for v in pb]
        print(f"{x + ' x ' + y:14} {len(ks):4d}  {sum(i == j for i, j in zip(pa, pb)) / len(ks):13.2f} {kappa(pa, pb):6.2f}   "
              f"{sum(i == j for i, j in zip(aa, ab)) / len(ks):15.2f} {kappa(aa, ab):6.2f}")
    if "ia1" in L:
        print("\nPor disciplina (rótulo atual x leitura da IA 1):")
        por = collections.defaultdict(lambda: [0, 0, 0])
        disc = {f"{r['prova']}|{r['numero']}": r["disciplina"] for r in amostra}
        for k in chaves:
            d = por[disc[k]]
            d[0] += 1
            d[1] += L["atual"][k] == L["ia1"][k]
            d[2] += assunto_de(L["atual"][k]) == assunto_de(L["ia1"][k])
        for s, (n, p, a) in por.items():
            print(f"   {s:6} n={n:3d}  mesmo ponto {p:2d} ({100 * p / n:3.0f}%)  mesmo assunto {a:2d} ({100 * a / n:3.0f}%)")
        todos3 = sum(1 for k in chaves if k in L.get("cod", {}) and L["atual"][k] == L["ia1"][k] == L["cod"][k])
        print(f"\nos três leitores no mesmo ponto: {todos3} de {len(chaves)}")


def arbitragem(n_controle=30):
    amostra, L = carregar_leitores()
    if "ia1" not in L:
        sys.exit("falta `leitura_ia1.json`.")
    con = abrir()
    nomes = {r["codigo"]: r["texto"] for r in con.execute("select codigo,texto from pontos")}
    chaves = [f"{r['prova']}|{r['numero']}" for r in amostra]
    disc = {f"{r['prova']}|{r['numero']}": r["disciplina"] for r in amostra}
    divergem = [k for k in chaves if L["atual"][k] != L["ia1"][k]]
    iguais = [k for k in chaves if L["atual"][k] == L["ia1"][k]]
    rnd = random.Random(20261121)
    controle = sorted(rnd.sample(iguais, min(n_controle, len(iguais))), key=chaves.index)
    itens = [(k, "divergência") for k in divergem] + [(k, "controle") for k in controle]
    itens.sort(key=lambda t: (list(COTAS).index(disc[t[0]]), chaves.index(t[0])))
    indice, linhas = {}, []
    linhas.append(f"# Pacote de arbitragem: conjunto de referência ({datetime.date.today().isoformat()})\n")
    linhas.append("Para cada questão há opções com letras. **A** = rótulo atual do banco; **B** = leitura às cegas da IA; **C** = classificador por código (só aparece quando "
                  "difere de A e B). Responda com a letra, com um **código de ponto** do catálogo da disciplina, ou com `NENHUM` (se nenhum ponto serve; acrescente uma "
                  "nota curta). Nos itens de **controle** a IA e o rótulo atual concordam: responda `OK` se concorda ou o código correto.\n")
    linhas.append(f"{len(divergem)} divergências e {len(controle)} controles, de {len(chaves)} questões.\n")
    atual_disc = None
    for n, (k, tipo) in enumerate(itens, 1):
        s = disc[k]
        if s != atual_disc:
            atual_disc = s
            did = con.execute("select id from disciplinas where nome=?", (LD.nome(s),)).fetchone()[0]
            pts = con.execute("select codigo,texto from pontos where disciplina_id=? and ativo=1 order by codigo", (did,)).fetchall()
            linhas.append(f"\n---\n## {LD.nome(s)} ({s})\nCatálogo: " + "; ".join(f"{p['codigo']} {cortar(p['texto'], 60)}" for p in pts) + "\n")
        prova, numero = k.rsplit("|", 1)
        q = con.execute("select q.* from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (prova, int(numero))).fetchone()
        a, b = L["atual"][k], L["ia1"][k]
        c = L.get("cod", {}).get(k)
        opcoes = {"A": a, "B": b}
        if tipo == "divergência" and c and c not in (a, b):
            opcoes["C"] = c
        indice[str(n)] = {"chave": k, "tipo": tipo, "opcoes": opcoes}
        linhas.append(f"### {n}. [{tipo}] {k}")
        linhas.append(cortar(q["enunciado"], 1400))
        for Lt in "abcde":
            linhas.append(f"- ({Lt.upper()}) " + cortar(q[f"alt_{Lt}"], 260))
        linhas.append(f"Gabarito: {q['gabarito']}")
        if tipo == "divergência":
            for letra, cod in opcoes.items():
                linhas.append(f"- **{letra}** = {cod} {nomes.get(cod, '?')}")
        else:
            linhas.append(f"- IA e rótulo atual: **{a}** {nomes.get(a, '?')}  → responda `OK` ou o código correto")
        linhas.append("")
    arq_md = REF / f"arbitragem_{datetime.date.today().isoformat()}.md"
    arq_md.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    (REF / "arbitragem_indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(divergem)} divergências + {len(controle)} controles = {len(itens)} itens para o usuário; pacote em {arq_md.relative_to(RAIZ)}")


def registrar(arquivo):
    """Grava as decisões do usuário. ARQUIVO.json: {"<n>": "A"|"B"|"C"|"OK"|"<codigo>"|"NENHUM", ...} (n = número do item no pacote); nota opcional como
    {"<n>": ["NENHUM", "nota"]}."""
    resp = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    indice = json.loads((REF / "arbitragem_indice.json").read_text(encoding="utf-8"))
    nomes = {r["codigo"] for r in abrir().execute("select codigo from pontos")}
    saida = REF / "referencia_ouro.csv"
    antigos = {}
    if saida.exists():
        with open(saida, encoding="utf-8") as f:
            antigos = {r["chave"]: r for r in csv.DictReader(f, delimiter=";")}
    for n, v in resp.items():
        nota = ""
        if isinstance(v, list):
            v, nota = v[0], v[1]
        it = indice[n]
        v = v.strip()
        if v.upper() in it["opcoes"]:
            cod = it["opcoes"][v.upper()]
        elif v.upper() == "OK":
            cod = it["opcoes"]["A"]
        elif v.upper() == "NENHUM":
            cod = "NENHUM"
        elif v in nomes:
            cod = v
        else:
            sys.exit(f"item {n}: resposta '{v}' inválida")
        antigos[it["chave"]] = {"chave": it["chave"], "ponto_ouro": cod, "tipo": it["tipo"], "origem": "usuario", "nota": nota,
                                "data": datetime.date.today().isoformat()}
    with open(saida, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["chave", "ponto_ouro", "tipo", "origem", "nota", "data"], delimiter=";")
        w.writeheader()
        w.writerows(antigos.values())
    print(f"{len(resp)} decisões registradas; referência com {len(antigos)} itens em {saida.relative_to(RAIZ)}")


def maioria():
    """Arbitragem automática por MAIORIA entre três leituras (rótulo atual, IA 1, IA 2). Não é decisão do usuário: origem `ia_maioria`.
    Dois ou mais leitores no mesmo ponto = decisão; os três diferentes = `sem_maioria` (fica para o usuário). Grava `referencia_maioria.csv`."""
    amostra, L = carregar_leitores()
    for n in ("atual", "ia1", "ia2"):
        if n not in L:
            sys.exit(f"falta a leitura '{n}'.")
    con = abrir()
    nomes = {r["codigo"]: r["texto"] for r in con.execute("select codigo,texto from pontos")}
    linhas, cont = [], collections.Counter()
    atual_diverge_das_duas, ia_dissidente, sem_maioria = [], [], []
    por_disc = collections.defaultdict(lambda: collections.Counter())
    for r in amostra:
        k = f"{r['prova']}|{r['numero']}"
        a, b, c = L["atual"][k], L["ia1"][k], L["ia2"][k]
        votos = collections.Counter([a, b, c])
        cod, n = votos.most_common(1)[0]
        if n == 3:
            tipo = "unanime"
        elif n == 2:
            tipo = "maioria"
            if b == c != a:
                atual_diverge_das_duas.append((k, a, cod))
            else:
                ia_dissidente.append((k, "ia2" if a == b else "ia1", cod))
        else:
            tipo, cod = "sem_maioria", ""
            sem_maioria.append((k, a, b, c))
        cont[tipo] += 1
        por_disc[r["disciplina"]][tipo] += 1
        linhas.append({"chave": k, "disciplina": r["disciplina"], "ponto_maioria": cod, "tipo": tipo, "atual": a, "ia1": b, "ia2": c, "origem": "ia_maioria"})
    saida = REF / "referencia_maioria.csv"
    with open(saida, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    n = len(amostra)
    print(f"{n} questões: unânimes {cont['unanime']} ({100 * cont['unanime'] / n:.0f}%), maioria de 2 em 3: {cont['maioria']}, sem maioria: {cont['sem_maioria']}")
    print(f"o rótulo ATUAL diverge das duas leituras da IA (que concordam entre si) em {len(atual_diverge_das_duas)} ({100 * len(atual_diverge_das_duas) / n:.0f}%)")
    print(f"uma das leituras da IA é a dissidente (o rótulo atual concorda com a outra) em {len(ia_dissidente)}")
    print("\npor disciplina (unânime / maioria / sem maioria):")
    for s in COTAS:
        c = por_disc[s]
        print(f"   {s:6} {c['unanime']:2d} / {c['maioria']:2d} / {c['sem_maioria']:2d}")
    print("\nrótulo atual contra as duas leituras (provável erro do rótulo atual):")
    for k, a, cod in atual_diverge_das_duas:
        print(f"   {k}: atual {a} ({nomes.get(a, '?')[:38]}) -> maioria {cod} ({nomes.get(cod, '?')[:38]})")
    print("\nsem maioria (os três diferentes):")
    for k, a, b, c in sem_maioria:
        print(f"   {k}: atual {a}, ia1 {b}, ia2 {c}")
    print("\ngravado em", saida.relative_to(RAIZ))


def converter_ids(arquivo, destino):
    """Converte {"Q017": "PE08.03", ...} (ids curtos de `leitura`) em {"prova|numero": codigo} e grava em `destino` (na pasta de referência)."""
    amostra, _ = ler_amostra()
    por_id = {f"Q{k:03d}": f"{r['prova']}|{r['numero']}" for k, r in enumerate(amostra, 1)}
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    desconhecidos = [k for k in dados if k not in por_id]
    if desconhecidos:
        sys.exit(f"ids desconhecidos: {desconhecidos}")
    saida = {por_id[k]: v for k, v in dados.items()}
    (REF / destino).write_text(json.dumps(saida, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"{len(saida)} leituras convertidas em {destino}; faltam {len(por_id) - len(saida)} de {len(por_id)}")


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd, resto = a[0], a[1:]

    def opcao(nome, padrao):
        return resto[resto.index(nome) + 1] if nome in resto else padrao
    if cmd == "sortear":
        sortear(int(opcao("--n", 110)), int(opcao("--semente", 20261120)))
    elif cmd == "linha-de-base":
        linha_de_base(int(opcao("--folds", 5)))
    elif cmd == "leitura":
        leitura(resto[0], opcao("--ordem", "normal"))
    elif cmd == "maioria":
        maioria()
    elif cmd == "converter-ids":
        converter_ids(resto[0], resto[1])
    elif cmd == "concordancia":
        concordancia()
    elif cmd == "arbitragem":
        arbitragem(int(opcao("--controles", 30)))
    elif cmd == "registrar":
        registrar(resto[0])
    else:
        sys.exit(f"comando '{cmd}' ainda não implementado nesta versão\n" + __doc__)


if __name__ == "__main__":
    main()
