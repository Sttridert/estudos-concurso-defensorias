#!/usr/bin/env python3
"""Fase 5 (edital real), passo 2: classifica CADA FRASE do programa literal do edital em tema/tópico do banco.

Uso:  python -I scripts/51_classificar_edital.py <slug> [--pendencias]

Entradas (pasta dados/editais_reais/<slug>/):
  programa.json   saída do script 50 (frases literais por disciplina)
  decisoes.txt    decisões de classificação (escritas pela IA, conferidas pelo usuário); sintaxe abaixo
Saídas:
  edital_classificado.json   o ARTEFATO: cada frase literal com seus destinos (tópico principal + secundários)
  relatorio.md               resumo, pendências, propostas de tópicos novos e conferência de duplicatas
Não altera o banco (o script 52 grava).

Regras:
- Cada frase tem, por trecho, exatamente UM tópico principal e quantos secundários forem necessários. Se a frase mistura
  assuntos (ex.: lista de leis), cada assunto vira um grupo com o seu `trecho` literal (cópia exata de parte da frase).
- A frase pode cair em tópico de OUTRA disciplina (editais mudam assuntos de lugar); o relatório lista esses casos.
- Frase sem tópico no catálogo: vira PROPOSTA de tópico novo (linha NOVO). A proposta é conferida contra todos os
  tópicos de todas as disciplinas (duplicata?) e fica no banco para homologação futura; ela vale só para este edital.
- Base automática: se o banco (edital geral, `edital_item_ocorrencias`) liga a frase a UM só tópico e não há decisão
  escrita, esse tópico vira o principal (origem "herdado"). Com 0 ou 2+ tópicos, a decisão escrita é obrigatória.

Sintaxe de decisoes.txt (UTF-8; "#" começa comentário):
  PENAL-052 => PE10.01 +PE10.02                         principal PE10.01, secundário PE10.02 (frase inteira)
  PENAL-070 => PE14.04 @"Estatuto do Desarmamento (Lei nº 10.826/03 e Decreto n. 9.847/19)" | PE14.03 @"Crimes Hediondos (Lei nº 8.072/90)"
  NOVO NP-AM26-01 | Execução Penal | tema: Execução penal | Nome do tópico novo | justificativa
  COBRE ECA-002 => CA02 CA03 CA04                        a frase cobre TODOS os tópicos desses temas (ou códigos de tópico) como secundários
  FORA PE14.12 | motivo escrito                          tópico julgado FORA do edital (o motivo vai para o banco e para a apostila)

Segurança contra "fora do edital" por esquecimento (14/11/2026): um tópico que nenhuma frase cobre e que ninguém declarou FORA
fica "SEM JULGAMENTO"; o relatório o lista com o número de questões e a apostila o marca "a conferir no edital", nunca "fora".
Regra de dúvida: frase que cita o GÊNERO (ex.: "Extinção da punibilidade", "Estatuto da Criança e do Adolescente") cobre as
ESPÉCIES do catálogo (ex.: prescrição; capítulos do Estatuto), como secundárias.
"""
import json, re, sqlite3, sys, unicodedata, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
COD = re.compile(r"^(?:[A-Z]{2}\d{2}\.\d{2}|NP-[A-Z0-9\-]+)$")
VERSAO = "rascunho IA"
VERSAO_CATALOGO = "v2"   # versão do catálogo em que os códigos de decisoes.txt foram escritos (trava de 20/11/2026, grupo C)


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


PARADAS = set("de da do das dos e em a o as os para por com no na nos nas ao aos um uma que ou se sua seu sobre entre nao sem".split())


def radicais(s):
    return {w[:5] for w in re.findall(r"[a-z]{3,}", norm(s)) if w not in PARADAS}


def ler_decisoes(arq: Path):
    dec, novos, erros, fora, cobre = {}, {}, [], {}, {}
    global confirmados, declarada
    confirmados, declarada = [], []
    if not arq.exists():
        return dec, novos, fora, cobre, ["decisoes.txt não existe"]
    for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
        l = linha.split("  #")[0].strip() if "  #" in linha else linha.strip()
        if not l or l.startswith("#"):
            continue
        if l.startswith("VERSAO_CATALOGO "):     # declara em que catálogo os códigos abaixo foram escritos (ex.: VERSAO_CATALOGO v2)
            declarada.append(l.split()[1]); continue
        if l.startswith("CONFIRMADO "):          # o usuário confirmou as decisões deste bloco do edital (ex.: CONFIRMADO CONST 2026-11-14)
            confirmados.append(l.split()[1]); continue
        if l.startswith("FORA "):
            partes = [x.strip() for x in l[5:].split("|", 1)]
            if len(partes) != 2 or not partes[1]:
                erros.append(f"linha {n}: FORA precisa de motivo (FORA codigo | motivo)")
            else:
                fora[partes[0]] = partes[1]
            continue
        if l.startswith("COBRE "):
            mc = re.match(r"^COBRE\s+([A-Z]+-\d{3})\s*=>\s*(.+)$", l)
            if not mc:
                erros.append(f"linha {n}: COBRE inválido: {l[:80]}")
            else:
                cobre.setdefault(mc.group(1), []).extend(mc.group(2).split())
            continue
        if l.startswith("NOVO "):
            partes = [p.strip() for p in l[5:].split("|")]
            if len(partes) != 5:
                erros.append(f"linha {n}: NOVO precisa de 5 campos (id | disciplina | tema | nome | justificativa)"); continue
            novos[partes[0]] = {"id": partes[0], "disciplina": partes[1], "tema": partes[2].replace("tema:", "").strip(),
                                "nome": partes[3], "justificativa": partes[4]}
            continue
        m = re.match(r"^([A-Z]+-\d{3})\s*=>\s*(.+)$", l)
        if not m:
            erros.append(f"linha {n}: não entendi: {l[:80]}"); continue
        grupos = []
        for g in re.split(r"\s\|\s", m.group(2)):
            t = re.search(r'@"(.+)"\s*$', g)
            trecho = t.group(1) if t else None
            resto = g[:t.start()] if t else g
            cods = resto.split()
            if not cods or cods[0].startswith("+"):
                erros.append(f"linha {n}: grupo sem principal: {g[:60]}"); continue
            grupos.append({"principal": cods[0], "secundarios": [c.lstrip("+") for c in cods[1:]], "trecho": trecho})
        dec[m.group(1)] = grupos
    return dec, novos, fora, cobre, erros


def main():
    slug = sys.argv[1]
    so_pendencias = "--pendencias" in sys.argv
    pasta = RAIZ / "dados" / "editais_reais" / slug
    prog = json.loads((pasta / "programa.json").read_text(encoding="utf-8"))
    dec, novos, fora_dec, cobre, erros = ler_decisoes(pasta / "decisoes.txt")
    if declarada != [VERSAO_CATALOGO]:
        sys.exit(f"RECUSADO: decisoes.txt não declara 'VERSAO_CATALOGO {VERSAO_CATALOGO}' (declarou: {declarada or 'nada'}). Os códigos podem ser do catálogo antigo "
                 "e apontariam para tópicos errados. Traduzir antes: python -I scripts/mapear_codigos_v1_v2.py traduzir <slug>.")
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    cat = {c: (d, t, a) for c, t, d, a in con.execute("select p.codigo,p.texto,d.nome,a.nome from pontos p join disciplinas d on d.id=p.disciplina_id join assuntos a on a.id=p.assunto_id where p.ativo=1")}
    # base do edital geral: frases do mesmo edital já ligadas a tópicos, na ordem
    nome_ed = f"{prog['edital']['pasta']} [edital]"
    base = {}
    for d, t, pts in con.execute("""select d.nome, o.texto_literal,
            (select group_concat(p.codigo,' ') from edital_item_pontos ip join pontos p on p.id=ip.ponto_id where ip.item_id=i.id)
            from edital_item_ocorrencias o join edital_itens i on i.id=o.item_id join disciplinas d on d.id=i.disciplina_id
            join editais e on e.id=o.edital_id where e.nome=? order by o.id""", (nome_ed,)):
        base.setdefault(d, []).append((t, (pts or "").split()))

    pend, usados = [], set()
    out_disc = []
    for d in prog["disciplinas"]:
        fila = list(base.get(d["disciplina_banco"], []))
        itens_out = []
        for it in d["itens"]:
            frases_out = []
            for f in it["frases"]:
                b = None
                for k, (t, pts) in enumerate(fila):
                    if t == f["texto"]:
                        b = pts; fila.pop(k); break
                g = dec.get(f["id"])
                origem = "decisao IA (rascunho)"
                if g is None:
                    if b is not None and len(b) == 1:
                        g = [{"principal": b[0], "secundarios": [], "trecho": None}]; origem = "herdado do edital geral v1"
                    else:
                        pend.append((f["id"], it["rotulo"], f["texto"], b)); g = []
                destinos = []
                for gr in g:
                    if gr["trecho"] and gr["trecho"] not in f["texto"]:
                        erros.append(f"{f['id']}: trecho não é literal da frase: {gr['trecho']!r}")
                    destinos.append({"p": gr["principal"], "papel": "principal", "trecho": gr["trecho"], "origem": origem})
                    for s in gr["secundarios"]:
                        destinos.append({"p": s, "papel": "secundario", "trecho": gr["trecho"], "origem": origem})
                    ps = [gr["principal"]] + gr["secundarios"]
                    if len(set(ps)) != len(ps):
                        erros.append(f"{f['id']}: tópico repetido no mesmo grupo")
                    for c in ps:
                        if not COD.match(c):
                            erros.append(f"{f['id']}: código inválido {c}")
                        elif c.startswith("NP-") and c not in novos:
                            erros.append(f"{f['id']}: proposta {c} não definida (linha NOVO)")
                        elif not c.startswith("NP-") and c not in cat:
                            erros.append(f"{f['id']}: tópico inexistente no banco: {c}")
                for c in cobre.get(f["id"], []):      # a frase cobre todos os tópicos do tema (ou o tópico) como secundários
                    alvo = [k for k in cat if k == c or k.startswith(c + ".")]
                    if not alvo:
                        erros.append(f"{f['id']}: COBRE {c} não existe no catálogo")
                    for k in alvo:
                        if all(x["p"] != k for x in destinos):
                            destinos.append({"p": k, "papel": "secundario", "trecho": None, "origem": "abrangência (decisão IA)"})
                frases_out.append({"id": f["id"], "texto": f["texto"], "destinos": destinos})
            itens_out.append({"ordem": it["ordem"], "rotulo": it["rotulo"], "frases": frases_out})
        out_disc.append({"codigo": d["codigo"], "disciplina_banco": d["disciplina_banco"], "titulo_no_edital": d["titulo_no_edital"], "itens": itens_out})
    for k in dec:
        if not any(f["id"] == k for d in prog["disciplinas"] for i in d["itens"] for f in i["frases"]):
            erros.append(f"decisão para frase que não existe: {k}")

    if so_pendencias or pend:
        print(f"PENDENTES (sem tópico ou com 2+ tópicos no edital geral, sem decisão escrita): {len(pend)}")
        for i, rot, t, b in pend:
            print(f"  {i} [{rot or '-'}] {t[:95]} => base: {' '.join(b) if b else ('-' if b == [] else 'sem base')}")
    if erros:
        print("ERROS:"); [print("  " + e) for e in erros]
    if pend or erros:
        sys.exit("artefato NÃO gerado" if not so_pendencias else None)

    # propostas: conferência de duplicata contra TODOS os tópicos de TODAS as disciplinas
    desc = {c: d or "" for c, d in con.execute("select codigo, descricao from pontos where ativo=1")}
    rad_cat = {c: radicais(f"{v[1]} {desc.get(c, '')}") for c, v in cat.items()}
    propostas = []
    usadas = {d["p"] for dd in out_disc for i in dd["itens"] for f in i["frases"] for d in f["destinos"]}
    for pid, n in novos.items():
        r = radicais(n["nome"])
        sim = sorted(((len(r & rc) / max(1, len(r | rc)), c) for c, rc in rad_cat.items()), reverse=True)[:3]
        propostas.append({**n, "status": "proposto", "usada_nas_frases": [f["id"] for dd in out_disc for i in dd["itens"] for f in i["frases"] if any(x["p"] == pid for x in f["destinos"])],
                          "parecidos_no_catalogo": [{"codigo": c, "nome": cat[c][1], "disciplina": cat[c][0], "similaridade": round(s, 2)} for s, c in sim if s >= 0.2]})
        if pid not in usadas:
            erros.append(f"proposta {pid} não é usada por nenhuma frase")
    if erros:
        print("ERROS:"); [print("  " + e) for e in erros]; sys.exit("artefato NÃO gerado")

    discs = {d["disciplina_banco"] for d in out_disc}
    for c, mot in fora_dec.items():
        if c not in cat:
            erros.append(f"FORA {c}: tópico não existe")
        elif c in usadas:
            erros.append(f"FORA {c}: o tópico é usado por frase do edital; ou tira o FORA ou tira a ligação")
    sem_jul = sorted(c for c, v in cat.items() if v[0] in discs and c not in usadas and c not in fora_dec)
    if erros:
        print("ERROS:"); [print("  " + e) for e in erros]; sys.exit("artefato NÃO gerado")
    art = {"edital": prog["edital"], "blocos_confirmados": confirmados, "fora_do_edital": [{"p": c, "motivo": m} for c, m in sorted(fora_dec.items())], "sem_julgamento": sem_jul, "estado": "rascunho da IA (a conferir pelo usuário)", "gerado_em": datetime.date.today().isoformat(),
           "gerado_por": "scripts/51_classificar_edital.py", "versao_catalogo": VERSAO_CATALOGO, "disciplinas": out_disc, "topicos_propostos": propostas}
    (pasta / "edital_classificado.json").write_text(json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")

    # relatório
    L = [f"# Relatório da classificação do edital — {slug}", "", f"Gerado em {art['gerado_em']} · estado: {art['estado']}", ""]
    L.append("## Resumo por disciplina do edital\n\n| Disciplina do edital | Frases | Com trecho | Com secundário | Tópico em outra disciplina | Em proposta |\n|---|---|---|---|---|---|")
    fora = []
    for d in out_disc:
        fr = [f for i in d["itens"] for f in i["frases"]]
        ct = sum(1 for f in fr if any(x["trecho"] for x in f["destinos"]))
        cs = sum(1 for f in fr if any(x["papel"] == "secundario" for x in f["destinos"]))
        outra = [(f, x) for f in fr for x in f["destinos"] if not x["p"].startswith("NP-") and cat[x["p"]][0] != d["disciplina_banco"]]
        np_ = sum(1 for f in fr if any(x["p"].startswith("NP-") for x in f["destinos"]))
        fora += [(d["codigo"], f, x) for f, x in outra]
        L.append(f"| {d['disciplina_banco']} | {len(fr)} | {ct} | {cs} | {len({f['id'] for f, _ in outra})} | {np_} |")
    L += ["", "## Frases cujo tópico principal está em OUTRA disciplina", ""]
    for cod, f, x in fora:
        if x["papel"] == "principal":
            L.append(f"- {f['id']} «{f['texto'][:90]}» → {x['p']} ({cat[x['p']][0]}: {cat[x['p']][1]})")
    L += ["", "## Propostas de tópicos novos (para homologação futura)", ""]
    if not propostas:
        L.append("Nenhuma.")
    for p in propostas:
        L.append(f"- **{p['id']}** · {p['disciplina']} · tema: {p['tema']} · {p['nome']} — {p['justificativa']} (frases: {', '.join(p['usada_nas_frases'])})")
        L.append("  - parecidos no catálogo: " + ("; ".join(f"{q['codigo']} {q['nome']} ({q['disciplina']}, {q['similaridade']})" for q in p["parecidos_no_catalogo"]) or "nenhum"))
    L += ["", "## Tópicos do catálogo que nenhuma frase do edital usa (candidatos a 'fora do edital')", ""]
    for d_nome in sorted({v[0] for v in cat.values()}):
        nao = [f"{c} {v[1]}" for c, v in sorted(cat.items()) if v[0] == d_nome and c not in usadas]
        L.append(f"- **{d_nome}** ({len(nao)}): " + "; ".join(nao))
    qn = dict(con.execute("select p.codigo,(select count(*) from classificacao cl where cl.ponto_id=p.id) from pontos p"))
    L += ["", f"## SEM JULGAMENTO ({len(sem_jul)} pontos): nenhuma frase os cobre e ninguém os declarou fora do edital. CONFERIR", "",
          "Cada um precisa de uma destas decisões em `decisoes.txt`: uma frase que o cobre (`=>` ou `COBRE`) ou `FORA codigo | motivo`. Até lá a apostila os marca \"a conferir no edital\".", ""]
    for d_nome in sorted({cat[c][0] for c in sem_jul}):
        L.append(f"- **{d_nome}**: " + "; ".join(f"{c} {cat[c][1]} ({qn.get(c, 0)} q.)" for c in sem_jul if cat[c][0] == d_nome))
    L += ["", f"## Declarados FORA do edital ({len(fora_dec)})", ""] + [f"- {c} {cat[c][1]} ({qn.get(c, 0)} q.): {m}" for c, m in sorted(fora_dec.items())]
    (pasta / "relatorio.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"sem julgamento: {len(sem_jul)} pontos; declarados fora: {len(fora_dec)}")
    print(f"gerado {pasta / 'edital_classificado.json'} e relatorio.md · {sum(len(i['frases']) for d in out_disc for i in d['itens'])} frases · {len(propostas)} propostas")


if __name__ == "__main__":
    main()
