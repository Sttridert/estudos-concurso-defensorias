#!/usr/bin/env python3
"""Passo 5 do ciclo por disciplina (Etapa 8 do plano do edital fictício geral): documento Word da disciplina.

Uso:  python -I scripts/44_gerar_documento_edital_geral.py DH|PENAL|CONST

Lê do banco (edital_itens, edital_item_pontos, edital_item_ocorrencias) e gera
produtos/edital-ficticio/Edital ficticio geral - <disciplina> (v1).docx com o desenho das apostilas:
Tema > Tópico > itens do edital fictício (texto literal, em quantos editais aparece, origem e marcas).
Não altera o banco.
"""
import csv, datetime, json, sqlite3, sys
from pathlib import Path
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import qn

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import apostila_lib as L

BANCO = RAIZ / "banco" / "estudos.db"
MODELO = RAIZ / "produtos" / "modelos" / "base-estilos.docx"
SAIDA = RAIZ / "produtos" / "edital-ficticio"
INVENTARIO = RAIZ / "dados" / "inventario_editais_edital_geral.csv"
import lib_disciplinas as LD   # fonte única: dados/disciplinas.json
DISCIPLINA = LD.nomes(edital_ficticio=True)
COR, TINTA = L.AZUL, L.AZUL_BG
C_FCC, C_DPU, C_OUT = "1f4e79", "8b1e3f", "57606a"


def inserir(doc, xml):
    sect = doc.element.body.find(qn("w:sectPr"))
    for el in parse_xml(f"<w:body {L.NS}>{xml}</w:body>"):
        sect.addprevious(el)


def origem_chips(fcc, dpu, out):
    x = ""
    if fcc: x += L.chip(f"FCC {fcc}", C_FCC)
    if dpu: x += L.chip(f"DPU {dpu}", C_DPU)
    if out: x += L.chip(f"Outras {out}", C_OUT)
    return x


def marcas(flags, provavel):
    m = []
    for f in flags:
        if f.startswith("novo"): m.append("novo (só 2025+)")
        elif f.startswith("exclusivo"): m.append("exclusivo")
        elif f.startswith("detalhado"): m.append("detalhado")
    if provavel: m.append(f"é de: {provavel}")
    return " · ".join(m) or "—"


def main():
    alvo = sys.argv[1].upper()
    disc_nome = DISCIPLINA[alvo]
    con = sqlite3.connect(BANCO); con.row_factory = sqlite3.Row
    disc = con.execute("select id from disciplinas where nome=?", (disc_nome,)).fetchone()["id"]
    temas = con.execute("select id,codigo,nome from assuntos where disciplina_id=? order by codigo", (disc,)).fetchall()
    pontos = con.execute("select id,assunto_id,codigo,texto,origem from pontos where disciplina_id=? and ativo=1 order by codigo", (disc,)).fetchall()
    itens = {r["id"]: r for r in con.execute("select * from edital_itens where disciplina_id=?", (disc,))}
    liga = {}
    for r in con.execute("select item_id,ponto_id from edital_item_pontos where item_id in (select id from edital_itens where disciplina_id=?)", (disc,)):
        liga.setdefault(r["ponto_id"], []).append(r["item_id"])
    com_ponto = {i for v in liga.values() for i in v}
    n_oc = con.execute("select count(*) from edital_item_ocorrencias where item_id in (select id from edital_itens where disciplina_id=?)", (disc,)).fetchone()[0]
    eds = con.execute("""select e.nome,e.banca,e.ano,count(*) n from edital_item_ocorrencias o join editais e on e.id=o.edital_id
                         where o.item_id in (select id from edital_itens where disciplina_id=?) group by e.id order by e.ano desc, e.nome""", (disc,)).fetchall()
    usados = {e["nome"].replace(" [edital]", "") for e in eds}
    quarentena = []
    with open(INVENTARIO, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            arq = r["arquivo_local"].replace("\\", "/")
            if arq.startswith("provas/") and r["situacao"] in ("tenho", "baixado") and "Assistente" not in arq:
                pasta = arq.split("/")[1]
                if pasta not in usados and "Analista Jurídico (2)" not in pasta:
                    quarentena.append(pasta)

    doc = Document(str(MODELO))
    body = doc.element.body
    for el in list(body):
        if el.tag != qn("w:sectPr"):
            body.remove(el)
    hp = doc.sections[0].header.paragraphs[0]
    if hp.runs:
        hp.runs[0].text = f"{disc_nome} · Defensorias e DPU  |  Edital fictício geral (v1)"
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    X = []
    X.append(L.capa("EDITAL FICTÍCIO GERAL · VERSÃO 1", disc_nome, COR, "Defensorias estaduais e DPU", L.VINHO,
                    "Tema > Tópico > itens do edital, com a origem de cada item",
                    f"{len(itens)} itens · {len(eds)} editais lidos · gerado em {hoje}"))
    X.append(L.caixa("Como ler este documento", [
        "O edital fictício junta, para esta disciplina, os programas de todos os editais coletados (Defensorias estaduais, DPU, de todas as bancas), sem alterar o texto de nenhum item.",
        "Cada item aparece sob o tópico em que será classificado. Um item que fala de dois assuntos aparece nos dois tópicos. Os temas e tópicos são a lista fixa da disciplina (versão 1).",
        "Coluna \"Ed.\": em quantos editais o item aparece. Coluna \"Origem\": FCC = Defensorias com banca FCC; DPU = edital da DPU; Outras = Defensorias de outras bancas.",
        "Marcas: \"novo\" = só aparece em editais de 2025 em diante; \"exclusivo\" = aparece em um único edital; \"detalhado\" = cita lei, decreto ou caso pelo número. Itens muito frequentes são o núcleo do que as Defensorias cobram; itens exclusivos mostram o que só uma comissão pôs.",
        "Os itens vieram de leitura automática dos PDFs e foram ligados aos tópicos por palavras-chave (rascunho conferido por amostra). Itens citados em mais de uma redação foram juntados quando eram praticamente iguais.",
    ], COR, TINTA))

    # números e temas
    X.append(L.titulo(1, "Números desta disciplina", L.INK, "numeros"))
    eh_gen = lambda i: "fragmento genérico" in (i["flags"] or "")
    gener = [i for i in itens.values() if i["id"] not in com_ponto and not i["disciplina_provavel"] and eh_gen(i)]
    sem_ponto = [i for i in itens.values() if i["id"] not in com_ponto and not i["disciplina_provavel"] and not eh_gen(i)]
    outra = [i for i in itens.values() if i["disciplina_provavel"] and i["id"] not in com_ponto]
    g = [5200, 1800, 2638]
    lin = L.cabecalho_tabela(["Tema", "Tópicos", "Itens ligados"], g, COR, centro=(1, 2))
    for t in temas:
        pts = [p for p in pontos if p["assunto_id"] == t["id"]]
        n = len({i for p in pts for i in liga.get(p["id"], [])})
        lin += L.linha_dados([f"{t['codigo']} · {t['nome']}", len(pts), n], g, negrito=(0,), centro=(1, 2), sz=18)
    X.append(L.tbl(g, lin))
    X.append(L.nota(f"Itens: {len(itens)}. Ligados a algum tópico: {len(com_ponto)}. De outra disciplina (guardados para quando ela for feita): {len(outra)}. Fragmentos genéricos sem tópico próprio (como Conceito e Disposições gerais): {len(gener)}. Sem tópico: {len(sem_ponto)}. Ocorrências literais (item × edital): {n_oc}."))
    X.append(L.titulo(2, "Editais lidos para esta disciplina", COR))
    g = [5600, 2200, 700, 1138]
    lin = L.cabecalho_tabela(["Edital", "Banca", "Ano", "Frases"], g, COR, sz=17, centro=(2, 3))
    for e in eds:
        lin += L.linha_dados([e["nome"].replace(" [edital]", "").replace(" (edital, sem prova)", ""), e["banca"] or "—", e["ano"] or "—", e["n"]], g, centro=(2, 3), sz=16)
    X.append(L.tbl(g, lin))
    if quarentena:
        X.append(L.caixa("Editais coletados que não entraram nas contas desta disciplina", [
            "Não foi possível extrair o programa desta disciplina (o edital não traz a disciplina, traz em outro formato ou em duas colunas):",
            "; ".join(sorted(quarentena)) + "."], L.AMBER, L.AMBER_BG))

    # corpo: temas e tópicos
    for t in temas:
        X.append(L.titulo(1, f"{t['codigo']} · {t['nome']}", COR, t["codigo"]))
        for pt in [p for p in pontos if p["assunto_id"] == t["id"]]:
            ids = liga.get(pt["id"], [])
            ed_do_topico = len({o[0] for o in con.execute("select edital_id from edital_item_ocorrencias where item_id in (%s)" % ",".join(map(str, ids)))}) if ids else 0
            novo = "  [tópico novo desta versão]" if alvo in ("DH", "PENAL") and (pt["origem"] or "").startswith("edital geral v1") else ""
            X.append(L.titulo(3, f"{pt['codigo']} · {pt['texto']}{novo}", COR))
            if not ids:
                X.append(L.caixa("Nenhum item de edital neste tópico", ["O tópico veio das questões de provas anteriores e nenhum edital coletado o cita pelas palavras-chave usadas."], L.AMBER, L.AMBER_BG))
                continue
            X.append(L.nota(f"{len(ids)} itens · aparece em {ed_do_topico} editais."))
            g = [6100, 600, 1500, 1438]
            lin = L.cabecalho_tabela(["Item do edital (texto literal)", "Ed.", "Origem", "Marcas"], g, COR, sz=17, centro=(1,))
            for iid in sorted(ids, key=lambda i: (-itens[i]["n_editais"], itens[i]["texto"])):
                i = itens[iid]
                lin += L.linha_dados([i["texto"], i["n_editais"], origem_chips(i["n_fcc"], i["n_dpu"], i["n_outras"]),
                                      marcas(json.loads(i["flags"] or "[]"), i["disciplina_provavel"])], g, centro=(1,), sz=16)
            X.append(L.tbl(g, lin))

    # apêndices
    if outra:
        X.append(L.titulo(1, "Itens que pertencem a outra disciplina", COR, "outra"))
        X.append(L.nota("Apareceram no programa desta disciplina em alguns editais, mas são de outra disciplina da lista. Ficam guardados e entram no ciclo dela."))
        g = [6600, 700, 2338]
        lin = L.cabecalho_tabela(["Item", "Ed.", "Disciplina provável"], g, COR, sz=17, centro=(1,))
        for i in sorted(outra, key=lambda i: (i["disciplina_provavel"], -i["n_editais"], i["texto"])):
            lin += L.linha_dados([i["texto"], i["n_editais"], i["disciplina_provavel"]], g, centro=(1,), sz=16)
        X.append(L.tbl(g, lin))
    if gener:
        X.append(L.titulo(1, "Fragmentos genéricos (sem tópico próprio)", COR, "genericos"))
        X.append(L.nota("Títulos soltos que só têm sentido dentro do item em que aparecem; não são classificáveis sozinhos."))
        g = [7200, 700, 1738]
        lin = L.cabecalho_tabela(["Item", "Ed.", "Origem"], g, COR, sz=17, centro=(1,))
        for i in sorted(gener, key=lambda i: (-i["n_editais"], i["texto"])):
            lin += L.linha_dados([i["texto"], i["n_editais"], origem_chips(i["n_fcc"], i["n_dpu"], i["n_outras"])], g, centro=(1,), sz=16)
        X.append(L.tbl(g, lin))
    if sem_ponto:
        X.append(L.titulo(1, "Itens sem tópico", COR, "semtopico"))
        X.append(L.nota("Itens que as palavras-chave não ligaram a nenhum tópico (muitos são títulos genéricos, leis citadas pelo número ou itens de um só edital). Servem de lista de conferência."))
        g = [7200, 700, 1738]
        lin = L.cabecalho_tabela(["Item", "Ed.", "Origem"], g, COR, sz=17, centro=(1,))
        for i in sorted(sem_ponto, key=lambda i: (-i["n_editais"], i["texto"])):
            lin += L.linha_dados([i["texto"], i["n_editais"], origem_chips(i["n_fcc"], i["n_dpu"], i["n_outras"])], g, centro=(1,), sz=16)
        X.append(L.tbl(g, lin))

    # inserir em blocos (evita XML gigante numa só chamada)
    for k in range(0, len(X), 40):
        inserir(doc, "".join(X[k:k + 40]))
    SAIDA.mkdir(parents=True, exist_ok=True)
    arq = SAIDA / f"Edital ficticio geral - {disc_nome} (v1).docx"
    doc.save(str(arq))
    print("documento:", arq.relative_to(RAIZ), f"| {len(itens)} itens, {len(com_ponto)} ligados, {len(outra)} de outra disciplina, {len(sem_ponto)} sem tópico, {len(quarentena)} editais em quarentena")


if __name__ == "__main__":
    main()
