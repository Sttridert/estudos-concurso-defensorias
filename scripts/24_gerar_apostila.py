"""Etapa 5: gera a apostila de uma disciplina a partir do banco permanente (estudos.db), do perfil e do motor (scripts/23).
Uso: python scripts/24_gerar_apostila.py [--perfil ID] [--edital-artefato EDITAL_ID] [--sem-artefato] [--titulo "..."]
Artefato do edital real (frases literais classificadas; scripts 50 a 52): e o caminho PADRAO quando o edital do perfil tem artefato (decisao 41);
--edital-artefato ID escolhe outro edital. Edital REAL sem artefato e recusado (monte o artefato com 50, 51 e 52); o caminho antigo (script 28) foi aposentado em 16/11/2026 (plano 06, Etapa 3). Perfil sem edital real usa o edital ficticio (edital_pontos).
Perfil por bloco do edital (`bloco` da apostila no perfil.toml): ver lib_escopo.py; o titulo e o do proprio edital, salvo --titulo.
Generico: nada aqui e especifico de Direitos Humanos. Capitulos = assuntos (ordem pela frequencia do motor);
dentro do capitulo as questoes ficam agrupadas por PONTO do catalogo. Prefacio = pontos do edital (ficticio ou real) do perfil.
Regra do usuario: cartao sem a resposta; gabarito discreto e comentarios no fim do capitulo; mesmo design da apostila-modelo.
"""
import json, re, sqlite3, sys, collections, importlib.util, pathlib
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import qn

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import apostila_lib as L
import lib_edital_classificado as LA
import lib_escopo as LE

spec = importlib.util.spec_from_file_location("motor", AQUI / "23_motor_analise.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

PROJ = AQUI.parent
MODELO = PROJ / "produtos" / "modelos" / "base-estilos.docx"
COR, TINTA = L.AZUL, L.AZUL_BG
RUIDO = re.compile(r"\s*(?:\d{1,3}\s*)?DPE[A-Z]{2}[-A-Za-zÀ-ú.()º0-9 ]*$")


def limpa(t):
    return RUIDO.sub("", (t or "").strip()).strip()


# ---------------------------------------------------------------- guardrail do "topico exato" (regra do usuario, 13/11/2026)
# O topico exato do cartao NUNCA traz o detalhe da questao (ele pode entregar a resposta, ex.: "status supralegal da CADH").
# Ele mostra so o ponto do catalogo (codigo e nome, como na tabela do prefacio). O detalhe vai para a area de respostas.
# Checagem extra: se o topico tiver palavra que so existe na alternativa correta (nao aparece no enunciado nem nas
# outras alternativas), o topico e reduzido ao codigo do ponto e o gerador avisa no terminal.
_PARADAS = set("a o e de da do das dos em no na nos nas um uma para por com sem que se ao aos as os ou sua seu suas seus "
               "pela pelo pelas pelos como mais nao sao foi ser ter contra sobre entre meio convencao direitos humanos".split())


def _raizes(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return {w[:6] for w in re.findall(r"[a-z0-9]+", t) if len(w) >= 4 and w not in _PARADAS}


def palavras_da_resposta(q):
    """raizes de palavras exclusivas da alternativa correta (as que, no topico, entregariam a resposta)"""
    g = (q.get("gabarito") or "").strip().upper()
    if q.get("situacao") == "anulada" or g not in "ABCDE" or len(g) != 1:
        return set()
    outras = _raizes(q.get("enunciado"))
    for x in "abcde":
        if x != g.lower():
            outras |= _raizes(q.get(f"alt_{x}"))
    return _raizes(q.get(f"alt_{g.lower()}")) - outras


def topico_seguro(q, pc, conteudo, pc2=None):
    """topico exato do cartao = ponto do catalogo; corta para o codigo se ainda assim vazar a resposta"""
    base = f"{pc} · {conteudo}"
    extra = f"  (+ {pc2})" if pc2 else ""
    vaza = palavras_da_resposta(q) & _raizes(base)
    if vaza:
        print(f"  aviso: topico de {q['prova']} Q{q['numero']} continha palavra da resposta ({', '.join(sorted(vaza))}); mostrado so o codigo {pc}")
        return pc + extra
    return base + extra


def inserir(doc, xml):
    sect = doc.element.body.find(qn("w:sectPr"))
    for el in parse_xml(f"<w:body {L.NS}>{xml}</w:body>"):
        sect.addprevious(el)


PAG = {}          # numero de pagina de cada ancora do sumario (preenchido pela 1a passada)
ANCORAS = {}      # ancora -> regex da linha que a marca no PDF


def paginas_do_pdf(docx):
    """converte o Word em PDF (LibreOffice) e acha a pagina de cada ancora do sumario; {} se nao der"""
    import subprocess, tempfile
    from pathlib import Path
    soffice = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
    if not soffice.exists():
        print("aviso: LibreOffice nao encontrado; sumario sem numeros de pagina")
        return {}
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([str(soffice), "--headless", "--convert-to", "pdf", "--outdir", tmp, str(docx)], capture_output=True, timeout=300)
        pdf = Path(tmp) / (Path(docx).stem + ".pdf")
        if not pdf.exists():
            print("aviso: nao consegui gerar o PDF; sumario sem numeros de pagina")
            return {}
        n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout).group(1))
        txt = {i: subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), "-layout", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout for i in range(1, n + 1)}
    out = {}
    for anc, rx in ANCORAS.items():
        for i in range(2, n + 1):          # a pagina 1 e a do sumario
            if re.search(rx, txt[i], re.M):
                out[anc] = i
                break
    return out


def main():
    pid = int(sys.argv[sys.argv.index("--perfil") + 1]) if "--perfil" in sys.argv else 1
    con = sqlite3.connect(M.DB)
    con.row_factory = sqlite3.Row
    perfil = M.carregar_perfil(con, pid)          # recusa perfil incompleto ou nao confirmado
    disc_id = perfil["disciplina_id"]
    disc = con.execute("select nome from disciplinas where id=?", (disc_id,)).fetchone()[0]
    esc = LE.escopo(con, perfil)         # perfil por bloco do edital (decisao 41): o bloco manda; None = por disciplina do catalogo
    if esc:                              # titulo e divisao do proprio edital (um bloco = uma apostila)
        disc = LE.titulos_blocos(con, perfil["edital_id"])[esc["bloco"]]
    if "--titulo" in sys.argv:        # título da apostila diferente do nome da disciplina; ex.: apostila que une dois blocos do edital
        disc = sys.argv[sys.argv.index("--titulo") + 1]
    an = M.analisar(con, perfil)
    if esc is None:
        ass = {r["codigo"]: dict(r) for r in con.execute("select id,codigo,nome,descricao from assuntos where disciplina_id=?", (disc_id,))}
        pts = {r["codigo"]: dict(r) for r in con.execute("select id,codigo,texto,descricao,assunto_id from pontos where disciplina_id=? and ativo=1 order by codigo", (disc_id,))}
    else:       # disciplina do perfil + pontos tocados pelas frases do bloco (qualquer disciplina de origem)
        ids_pts = sorted(LE.pontos_do_escopo(con, perfil, esc, so_ativos=True))
        pts = {r["codigo"]: dict(r) for r in con.execute(f"select id,codigo,texto,descricao,assunto_id from pontos where id in ({','.join('?' * len(ids_pts))}) order by codigo", ids_pts)}
        ids_ass = sorted({v["assunto_id"] for v in pts.values()})
        ass = {r["codigo"]: dict(r) for r in con.execute(f"select id,codigo,nome,descricao from assuntos where id in ({','.join('?' * len(ids_ass))})", ids_ass)}
    cod_ass_de_id = {a["id"]: c for c, a in ass.items()}
    ed = con.execute("select * from editais where id=?", (perfil["edital_id"],)).fetchone() if perfil["edital_id"] else None
    if ed is None:
        ed = con.execute("select * from editais where nome like ? order by id limit 1", (f"%{disc}%",)).fetchone()
    tem_trechos = "trechos" in [c[1] for c in con.execute("pragma table_info(edital_pontos)")]
    edpts = {r["codigo"]: dict(r) for r in con.execute(
        "select p.codigo,ep.ordem,ep.texto_no_edital,ep.marca_novo,ep.marca_exclusivo,ep.marca_detalhado,(select count(*) from ponto_fontes f where f.ponto_id=p.id and f.presente=1) as n_ed, "
        + ("ep.trechos " if tem_trechos else "null as trechos ") +
        "from edital_pontos ep join pontos p on p.id=ep.ponto_id where ep.edital_id=?", (ed["id"],))} if ed else {}
    art = None
    eid_art = None
    if "--edital-artefato" in sys.argv:
        eid_art = int(sys.argv[sys.argv.index("--edital-artefato") + 1])
    elif perfil.get("edital_id") and LE.tem_blocos(con, perfil["edital_id"]):
        eid_art = perfil["edital_id"]      # decisao 41 (A3c): com edital real que tem artefato, o artefato e o caminho padrao
    if eid_art:        # fluxo novo da fase 5 (decisao 35): edital real = artefato frase a frase
        ed = con.execute("select * from editais where id=?", (eid_art,)).fetchone()
        art = LA.carregar(con, ed["id"], disc_id, pts, bloco=perfil.get("bloco_edital"))
        edpts = art["edpts"]
    if ed is not None and ed["tipo"] == "real" and art is None:
        sys.exit(f"O edital «{ed['nome']}» e real e ainda nao tem artefato (frases classificadas e blocos). Monte-o com os scripts 50, 51 e 52 "
                 "(decisao 35) e rode o porteiro (scripts/70_porteiro_edital.py). O caminho antigo (script 28 e edital_pontos) foi aposentado.")
    n_ed = con.execute("select count(distinct edital_origem) from ponto_fontes").fetchone()[0]
    real = bool(ed and ed["tipo"] == "real")  # edital real: o prefacio mostra o edital verticalizado e os pontos organizados
    programa = art["programa"] if art else []
    if art:     # ponto só é "fora do edital" se foi julgado; os demais ficam "a conferir" (segurança de 14/11/2026)
        fora_txt = lambda pc: "" if pc in edpts else (" (fora do edital)" if pc in art["fora"] else " (a conferir no edital)")
    else:
        fora_txt = lambda pc: "" if (not real or pc in edpts) else " (fora do edital)"

    def conteudo(pc):
        """nome do ponto como aparece na tabela do prefacio (com edital real: como o edital trata)"""
        m = re.match(r"Itens ([^:]+): (.*)", (edpts.get(pc) or {}).get("texto_no_edital") or "") if real else None
        return m.group(2) if m else pts[pc]["texto"]

    trechos_de = {pc: json.loads(e["trechos"]) if e.get("trechos") else [] for pc, e in edpts.items()}
    frase_de = art["frase_de"] if art else {(it["item"], f) for it in programa for f in it["topicos"]}

    def fmt_trecho(t):
        """trecho literal do edital: 'item. texto'; '…' quando e parte de uma frase maior"""
        return f"{t['i']}. " + (t["t"] if (t["i"], t["t"]) in frase_de else f"… {t['t']} …")

    def topico_edital(q, pc, pc2=None):
        """Regra do usuario (13/11/2026): com edital real, o topico exato e o texto do edital, ipsis litteris.
        Escolhe, entre os trechos do ponto, o mais parecido com a questao (detalhe pesa 2, enunciado e alternativas 1),
        pulando os que tem palavra exclusiva da alternativa correta. Sem trecho seguro: so o codigo do ponto.
        Sem edital real ou ponto fora do edital: o nome do ponto (topico_seguro)."""
        extra = f"  (+ {pc2})" if pc2 else ""
        trs = trechos_de.get(pc) or []
        if not trs:
            return topico_seguro(q, pc, conteudo(pc) + fora_txt(pc), pc2)
        det = _raizes(q.get("detalhe"))
        texto_q = _raizes(" ".join(q.get(k) or "" for k in ("enunciado", "alt_a", "alt_b", "alt_c", "alt_d", "alt_e")))
        resp = palavras_da_resposta(q)
        cand = []
        for n, t in enumerate(trs):
            rz = _raizes(t["t"])
            if rz & resp:
                continue
            cand.append((-(2 * len(rz & det) + len(rz & texto_q)), len(t["t"]), n, t))
        if not cand:
            print(f"  aviso: todos os trechos do edital de {pc} tem palavra da resposta de {q['prova']} Q{q['numero']}; mostrado so o codigo")
            return pc + extra
        return f"{pc} · {fmt_trecho(min(cand)[3])}" + extra

    def topico_edital_xml(q, pc, pc2=None):
        """Modelo v2 (14/11/2026): o topico exato vai para a linha de resposta e traz a FRASE INTEIRA do edital, com o trecho
        que motivou a classificacao grifado (vinho sobre fundo claro). Sem guardrail de palavra da resposta: o topico so
        aparece depois da questao. Escolhe, entre os trechos do ponto, o mais parecido com a questao."""
        cinza = dict(color=L.GREY, sz=17)
        extra = f"  (+ {pc2})" if pc2 else ""
        trs = trechos_de.get(pc) or []
        if not trs:
            return L.r(topico_seguro(q, pc, conteudo(pc) + fora_txt(pc), pc2), **cinza)
        det = _raizes(q.get("detalhe"))
        texto_q = _raizes(" ".join(q.get(k) or "" for k in ("enunciado", "alt_a", "alt_b", "alt_c", "alt_d", "alt_e")))
        cand = []
        for n, t in enumerate(trs):
            rz = _raizes(t["t"])
            cand.append((-(2 * len(rz & det) + len(rz & texto_q)), len(t["t"]), n, t))
        t = min(cand)[3]
        frase = t.get("f") or next((f for it in programa if it["item"] == t["i"] for f in it["topicos"] if t["t"] in f), t["t"])
        BLOCOS = tit_blocos       # titulos dos blocos do proprio edital (tabela edital_blocos), nada fixo no codigo
        mb = re.match(r"^([A-Z]+)\.(.+)$", t["i"])      # frase escrita em OUTRO bloco do edital (rótulo SIGLA.item): diz o bloco por extenso
        origem_bloco = f" (edital, bloco «{BLOCOS.get(mb.group(1), mb.group(1))}»" + ("" if mb.group(2) == "s/n" else f", item {mb.group(2)}") + ")" if mb else ""
        lab = "" if (mb or t["i"] == "s/n") else t["i"] + ". "
        runs = L.r(f"{pc} · {lab}", b=True, **cinza)
        k = frase.find(t["t"])
        if t["t"] == frase or k < 0:
            runs += L.r(frase, **cinza)
        else:
            runs += L.r(frase[:k], **cinza) + L.r(t["t"], b=True, color=L.VINHO, sz=17, shd="f4dde3") + L.r(frase[k + len(t["t"]):], **cinza)
        return runs + L.r(origem_bloco, **cinza) + L.r(extra, **cinza)

    rows = con.execute("""select q.id,q.numero,q.situacao,q.gabarito,q.enunciado,q.alt_a,q.alt_b,q.alt_c,q.alt_d,q.alt_e,
        p.nome as prova,p.ano,p.instituicao,p.cargo,p.tipo_caderno,p.banca,p.carreira,
        cl.ponto_id,cl.ponto2_id,cl.detalhe,cl.tipo_cobranca,q.disciplina_id as disc_origem,p.gabarito_status,
        co.texto as c_texto,co.pegadinha as c_peg,co.dispositivos as c_disp,co.pendente_confirmacao as c_pend
        from questoes q join provas p on p.id=q.prova_id join classificacao cl on cl.questao_id=q.id
        left join comentarios co on co.questao_id=q.id
        where cl.ponto_id is not null and """ + LE.clausula(esc, disc_id, "cl")[0] + " order by p.ano,p.instituicao,q.numero", LE.clausula(esc, disc_id, "cl")[1]).fetchall()
    cod_ponto = {v["id"]: c for c, v in pts.items()}
    nome_disc = {i: n for i, n in con.execute("select id,nome from disciplinas")}
    # marcas do cartao (decisao 41): "disciplina de origem" e "tambem em <outra apostila>" (so com artefato de edital real)
    own_bloco = LE.bloco_do_perfil(con, {**perfil, "edital_id": ed["id"]}) if art else None      # o artefato pode ser outro edital que o do perfil antigo
    blocos_pt = LE.blocos_por_ponto(con, ed["id"]) if art else {}
    tit_blocos = LE.titulos_blocos(con, ed["id"]) if art else {}
    por_ponto = collections.defaultdict(list)
    filtro_universo = perfil["universo"]["filtro"]
    for r_ in rows:
        r_ = dict(r_)
        r_["ponto_id"], r_["ponto2_id"] = LE.efetivos(esc, disc_id, r_["disc_origem"], r_["ponto_id"], r_["ponto2_id"], set(cod_ponto))
        if r_["ponto_id"] is None or r_["ponto_id"] not in cod_ponto:
            continue            # questao de outra disciplina que o bloco nao toca
        # so entram na apostila as questoes do universo escolhido (o mesmo filtro das contas)
        if not M.em_universo({"banca": r_["banca"] or "", "carreira": r_["carreira"] or "", "cargo": r_["cargo"] or "", "inst": r_["instituicao"] or "", "ano": r_["ano"]}, filtro_universo):
            continue
        por_ponto[cod_ponto[r_["ponto_id"]]].append(r_)

    ordem = sorted(an["assuntos"], key=lambda c: -an["assuntos"][c]["p"])
    ordem += [c for c in sorted(ass) if c not in ordem]
    # Pedido do usuario (15/11/2026): assunto sem nenhuma questao no universo nao vira capitulo vazio;
    # todos eles se unem num capitulo final "Assuntos do edital sem cobranca anterior".
    pts_de = lambda c: [pc for pc, pv in pts.items() if cod_ass_de_id[pv["assunto_id"]] == c]
    # Pedido do usuario (15/11/2026): ponto que ja caiu mas NAO consta do edital atual da disciplina sai dos capitulos
    # normais e vai para o capitulo final "Temas cobrados anteriormente que nao aparecem no edital atual".
    fora_ed = {pc for pc in pts if real and pc not in edpts}
    pts_ed = lambda c: [pc for pc in pts_de(c) if pc not in fora_ed]
    ordem_q = [c for c in ordem if sum(len(por_ponto[pc]) for pc in pts_ed(c)) > 0]
    vazios = [c for c in ordem if c not in ordem_q and pts_ed(c)]
    fora_q = [pc for c in ordem for pc in pts_de(c) if pc in fora_ed and por_ponto[pc]]
    cap_de = {c: i for i, c in enumerate(ordem_q, 1)}
    N_SEM = len(ordem_q) + 1                        # capitulo unificado dos assuntos sem questao (so existe se houver)
    N_FORA = len(ordem_q) + (1 if vazios else 0) + 1  # capitulo dos temas cobrados fora do edital (so existe se houver)
    for c in ordem:
        if c not in cap_de:
            cap_de[c] = N_SEM if c in vazios else N_FORA
    sig = lambda s: s.replace("DPE-", "")

    doc = Document(str(MODELO))
    body = doc.element.body
    for el in list(body):
        if el.tag != qn("w:sectPr"):
            body.remove(el)
    hp = doc.sections[0].header.paragraphs[0]
    if hp.runs:
        hp.runs[0].text = f"{disc} · {perfil['carreira']} ({perfil['banca']})  |  Apostila por disciplina"

    X = []
    n_val, n_prov = an["n_validas"], an["n_provas"]
    X.append(L.capa("APOSTILA POR DISCIPLINA", disc, L.VINHO, f"para {perfil['cargo']} · {perfil['banca']}", L.AZUL,
                    f"{perfil['carreira']} · Banca {perfil['banca']} · {perfil['nome']}",
                    f"Universo: {an['universo']['nome']}  ·  {n_val} questões comentadas de {n_prov} provas"))
    X.append(L.legenda_cobranca(extras=sorted({(r_["tipo_cobranca"] or "") for r_ in rows})))
    X.append(L.fonte("Fonte: cadernos e gabaritos oficiais da FCC e TEC Concursos. Pontos, classificação e comentários feitos neste trabalho e sujeitos a conferência."))

    # sumario (com numero de pagina: campo PAGEREF; os numeros vem da 1a passada, via PDF)
    TAB = 9638
    pg_ = lambda anc: PAG.get(anc, "–")
    X.append(L.p(L.r("SUMÁRIO", b=True, color=L.GREY, sz=20), after=40, top=(L.INK, 8, 6)))
    ent_parte = lambda t, anc, cor=L.INK: L.p(L.link(anc, L.r(t, b=True, color=cor, sz=23)) + L.tab() + L.pageref(anc, pg_(anc), b=True, sz=21, color=cor), after=50, before=160, tab_dir=TAB)
    ent_cap = lambda n, t, qtd, anc: L.p(L.r(f"{n}.  ", b=True, color=COR, sz=19) + L.link(anc, L.r(t, color=L.INK, sz=20)) + L.r(f"  ({qtd} {'questão' if qtd == 1 else 'questões'})", color=L.GREY, sz=17) + L.tab() + L.pageref(anc, pg_(anc), sz=19, color=L.GREY), after=30, ind=360, tab_dir=TAB)
    ent_sub = lambda t, anc: L.p(L.r("▸  ", b=True, color=L.GREY, sz=19) + L.link(anc, L.r(t, color=L.INK, sz=20)) + L.tab() + L.pageref(anc, pg_(anc), sz=19, color=L.GREY), after=30, ind=360, tab_dir=TAB)
    qtd_cap = {c: sum(len(por_ponto[pc]) for pc in pts_ed(c)) for c in ass}
    ANCORAS.clear()
    # titulo longo (ex.: bloco que une duas materias) quebra em 2 linhas no PDF: a ancora usa so o comeco do titulo
    ANCORAS["prefacio"] = rf"^\s*{re.escape('O edital e os pontos de ' if real else 'Os pontos de ')}"
    X.append(ent_parte(f"Prefácio · O edital e os pontos de {disc}" if real else f"Prefácio · Os pontos de {disc} nos editais", "prefacio"))
    if real:
        ANCORAS["edital-verticalizado"] = r"^\s*Edital verticalizado\s*$"
        X.append(ent_sub("Edital verticalizado", "edital-verticalizado"))
    ANCORAS["disciplina"] = r"^\s*DISCIPLINA\s*$"
    X.append(ent_parte(f"{disc}: frequência dos assuntos e capítulos", "disciplina", L.VINHO))
    for c in ordem_q:
        ANCORAS[f"cap{cap_de[c]}"] = rf"^\s*CAPÍTULO {cap_de[c]}\s+·"
        X.append(ent_cap(cap_de[c], ass[c]["nome"], qtd_cap[c], f"cap{cap_de[c]}"))
    X.append(L.p(L.r("Complementos", b=True, color=L.GREY, sz=19), after=30, before=120, ind=360))
    if vazios:
        ANCORAS[f"cap{N_SEM}"] = r"^\s*Assuntos do edital sem cobrança anterior\s*$"
        X.append(ent_sub("Assuntos do edital sem cobrança anterior", f"cap{N_SEM}"))
    if fora_q:
        ANCORAS[f"cap{N_FORA}"] = r"^\s*Temas cobrados anteriormente que não aparecem no edital atual\s*$"
        X.append(ent_sub("Temas cobrados anteriormente que não aparecem no edital atual", f"cap{N_FORA}"))
    ANCORAS["dispositivos"] = r"^\s*Dispositivos, tratados e casos mais cobrados\s*$"
    X.append(ent_sub("Dispositivos, tratados e casos mais cobrados", "dispositivos"))
    ANCORAS["novos"] = r"^\s*(O que mudou no edital e o que ficou de fora|Pontos novos dos editais)\s*$"
    X.append(ent_sub("O que mudou no edital e o que ficou de fora" if real else "Pontos novos dos editais", "novos"))
    X.append(L.quebra())

    # prefacio: pontos do edital
    if real:
        # Regra do usuario (13/11/2026): com edital real, o prefacio tem duas partes:
        #   Parte 1 - edital verticalizado: o programa do edital, ipsis litteris, uma frase por linha, com os pontos de cada frase;
        #   Parte 2 - pontos organizados: a tabela de pontos, com os trechos literais do edital classificados em cada ponto.
        X.append(L.rotulo_secao("PREFÁCIO"))
        X.append(L.titulo(1, f"O edital e os pontos de {disc}", L.INK, "prefacio"))
        X.append(L.p(L.r(f"Edital de referência: «{ed['nome']}». Abaixo está o edital verticalizado: o programa de {disc} exatamente como está no edital, uma frase por linha, com o ponto do catálogo em que cada frase foi classificada ({len(edpts)} pontos no edital). A classificação é rascunho da IA; confira com o edital.", color=L.INK, sz=21), after=200))

        # parte 1: edital verticalizado
        X.append(L.titulo(2, "Edital verticalizado", COR, "edital-verticalizado"))
        if programa:
            X.append(L.p(L.r(f"Texto literal do programa de {disc} do edital, sem nenhuma palavra alterada. A numeração é a do próprio edital: cada item ou subitem ocupa uma linha, com todas as suas frases. A coluna \"Pontos\" mostra os pontos do catálogo em que as frases do item foram classificadas (código e nome).", color=L.GREY, sz=19), after=160))
            g = [700, 5038, 3900] if all(len(str(i_["item"])) <= 8 for i_ in programa) else [1500, 4400, 3738]     # rótulo longo (ex.: nome de um trecho do edital) pede coluna mais larga
            nome_pt = {r_[0]: r_[1] for r_ in con.execute("select codigo,texto from pontos")}     # inclui pontos de outras disciplinas
            linhas = L.cabecalho_tabela(["Nº", "Programa do edital (texto literal)", "Pontos (código e nome)"], g, COR, sz=17, centro=(0,))
            sem_ponto = 0
            for it in programa:
                sn = it["item"] == "s/n"      # bloco sem numeração no edital
                # Pedido do usuario (15/11/2026): o item/subitem inteiro numa linha so (frases juntas, na ordem do edital);
                # os pontos de todas as frases do item entram na mesma celula (sem repetir; principal antes de secundario)
                cods_item = []
                for k, frase in enumerate(it["topicos"], 1):
                    if "cods" in it:          # artefato novo: tópicos de cada frase (principal primeiro; "+" = secundário; pode ser de outra disciplina)
                        cods = [c if papel == "principal" else "+" + c for c, papel in it["cods"][k - 1]]
                    else:
                        cods = [pc for pc in edpts if any(t["i"] == it["item"] and t["t"] in frase for t in trechos_de[pc])]
                        cods.sort(key=lambda pc: edpts[pc]["ordem"])
                    sem_ponto += 0 if cods else 1
                    for c_ in cods:
                        if c_ not in cods_item:
                            cods_item.append(c_)
                # um ponto que e principal numa frase e secundario em outra aparece so como principal
                principais = {c_ for c_ in cods_item if not c_.startswith("+")}
                cods_item = [c_ for c_ in cods_item if not (c_.startswith("+") and c_[1:] in principais)]
                cods_item.sort(key=lambda c_: c_.startswith("+"))
                cel = [L.r(c_, b=True, sz=16) + L.r("  " + nome_pt.get(c_.lstrip("+"), ""), sz=16, color=L.GREY) for c_ in cods_item] or ["—"]
                linhas += L.linha_dados([("" if sn else it["item"]), " ".join(it["topicos"]), cel], g, negrito=(0,), centro=(0,), sz=18)   # numeração do próprio edital
            X.append(L.tbl(g, linhas))
            X.append(L.nota(f"{sum(len(it['topicos']) for it in programa)} frases em {len(programa)} itens. \"—\": frase de título ou geral, sem ponto próprio ({sem_ponto})." + (" Na coluna Pontos, \"+\" marca ponto secundário; código de outra disciplina (ex.: PE14.02) é ponto que esta frase também toca fora desta apostila." if art else "")))
        else:
            X.append(L.caixa("Programa literal não cadastrado", ["O JSON deste edital não traz o campo \"programa\" (texto literal). Rode os scripts 50 a 52 para montar o artefato do edital."], L.AMBER, L.AMBER_BG))
        X.append(L.quebra())

        def trechos_txt(pc):
            out = []
            for t in trechos_de.get(pc, []):
                item, txt = fmt_trecho(t).split(" ", 1)
                out.append(L.r(item + " ", b=True, color=L.GREY, sz=17) + L.r(txt, sz=17))
            if not out:
                m = re.match(r"Itens ([^:]+):", (edpts.get(pc) or {}).get("texto_no_edital") or "")
                out = [L.r(f"Itens {m.group(1)}" if m else "—", color=L.GREY, sz=17)]
            return out

    else:
        X.append(L.rotulo_secao("PREFÁCIO"))
        X.append(L.titulo(1, f"Os pontos de {disc} nos editais", L.INK, "prefacio"))
        X.append(L.p(L.r(f"Catálogo de {len(pts)} pontos de {disc}, montado a partir de {n_ed} editais de Defensoria da FCC e das próprias questões" + (f" (edital de referência: «{ed['nome']}»)" if ed else "") +
                         ". A coluna \"Editais\" conta em quantos programas o ponto aparece (busca por palavras-chave; confirme no edital do seu concurso). Pontos com 0 vieram das questões e não foram achados nos programas.", color=L.INK, sz=21), after=120))
        X.append(L.p(L.r("Como ler as colunas:  ", b=True, color=L.GREY, sz=18) + L.chip("NOVO", L.AMBER) + L.r("só nos editais de 2025 e 2026.   ", color=L.GREY, sz=18)
                     + L.r("Cap.", b=True, color=L.INK, sz=18) + L.r(": capítulo.   ", color=L.GREY, sz=18) + L.r("Q.", b=True, color=L.INK, sz=18) + L.r(": questões já cobradas.   ", color=L.GREY, sz=18)
                     + L.r("☐ ☐ ☐", b=True, color=L.INK, sz=18) + L.r(": estudei, revisei, fiz questões.", color=L.GREY, sz=18), after=200))
        g = [850, 3350, 900, 600, 600, 1550, 1750]
        linhas = L.cabecalho_tabela(["Ponto", "Conteúdo", "Editais", "Cap.", "Q.", "Estudei · Revisei · Questões", "Nota 1 · 2 · 3"], g, COR, sz=17, centro=(2, 3, 4, 5, 6))
        n_novos = 0
        for c in ordem:
            linhas += L.barra_grupo(f"Capítulo {cap_de[c]} · {ass[c]['nome']}", g, COR, TINTA)
            for pc, pv in pts.items():
                if cod_ass_de_id[pv["assunto_id"]] != c:
                    continue
                e = edpts.get(pc, {})
                novo = bool(e.get("marca_novo"))
                n_novos += 1 if novo else 0
                ed_txt = L.r(f"{e.get('n_ed', 0)} de {n_ed}  ", sz=19) + (L.chip("NOVO", L.AMBER) if novo else "")
                linhas += L.linha_dados([pc, pv["texto"], ed_txt, str(cap_de[c]), str(len(por_ponto[pc])), "☐  ☐  ☐", "1 ☐   2 ☐   3 ☐"], g, negrito=(0,), centro=(2, 3, 4, 5, 6), sz=18)
        X.append(L.tbl(g, linhas))
        X.append(L.nota(f"{len(pts)} pontos, {n_novos} novos. A coluna Q. conta questões em que o ponto é o principal. A extração do texto dos editais tem falhas; use o quadro como mapa, não como lista oficial."))
        X.append(L.quebra())

    # disciplina
    X.append(L.rotulo_secao("DISCIPLINA", cor=L.VINHO))
    X.append(L.titulo(1, disc, L.VINHO, "disciplina"))
    pg = an["provas_por_grupo"]
    anos_ap = sorted({r_["ano"] for lst in por_ponto.values() for r_ in lst})
    periodo = f"{anos_ap[0]} a {anos_ap[-1]}" if anos_ap else "sem provas"
    zero_hi = round(100 * M.wilson(0, an["n_efetivo"])[1])  # limite superior da faixa para assunto sem questao
    X.append(L.p(L.r(f"Universo: {an['universo']['nome']}. {n_val} questões classificadas, de {n_prov} provas ({periodo}).", color=L.GREY, sz=21), after=160))
    X.append(L.titulo(3, "Frequência dos assuntos (ordem de estudo)", L.VINHO))
    g = [700, 3538, 800, 1000, 1500, 900, 1200]
    linhas = L.cabecalho_tabela(["Cap.", "Assunto (capítulo)", "Qtd.", "% est.", "Faixa 95%", "Provas", "Grupo"], g, COR, centro=(0, 2, 3, 4, 5))
    for c in ordem:
        a = an["assuntos"].get(c)
        if a:
            gr = L.r(a["grupo"], b=(a["grupo"] == "Cai muito"), color=(COR if a["grupo"] == "Cai muito" else L.INK), sz=18)
            linhas += L.linha_dados([cap_de[c] if c in ordem_q else "—", ass[c]["nome"], f"{a['n']:g}", f"{a['p']:.0f}%", f"{a['lo']:.0f}% a {a['hi']:.0f}%", a["provas"], gr], g, negrito=(0,), centro=(0, 2, 3, 4, 5))
        else:
            linhas += L.linha_dados([cap_de[c] if c in ordem_q else "—", ass[c]["nome"], 0, "0%", f"até {zero_hi}%", 0, L.r("Sem dados", sz=18)], g, negrito=(0,), centro=(0, 2, 3, 4, 5))
    X.append(L.tbl(g, linhas))
    for av in an["avisos"]:
        X.append(L.nota("Aviso: " + av))
    top2 = sorted(an["assuntos"].items(), key=lambda kv: -kv[1]["p"])[:2]
    top_ = top2
    ct_n = collections.Counter()      # junta os dois vocabulários do banco (lei/tratado + lei_seca = Letra de lei etc.)
    for k_, v_ in an["cobranca_pct"].items():
        ct_n[L.tag_de(k_)[0]] += v_
    cob_txt = ", ".join(f"{v:.0f}% {k}" for k, v in sorted(ct_n.items(), key=lambda kv: -kv[1]) if v >= 1)
    X.append(L.caixa(f"Como ler {disc}", [
        f"Os assuntos que mais caem: {top2[0][1]['nome']} ({top2[0][1]['p']:.0f}%) e {top2[1][1]['nome']} ({top2[1][1]['p']:.0f}%). Com {an['n_efetivo']} questões efetivas, os demais não se ordenam com segurança entre si.",
        f"Tipo de cobrança (ponderado): {cob_txt}.",
        "A amostra é pequena: estude o programa inteiro e use o histórico para decidir a ordem, não para cortar conteúdo."], COR, TINTA))

    # capitulos
    disp = collections.defaultdict(list)
    # textos-base (Lingua Portuguesa): o texto aparece no primeiro cartao de cada capitulo que o usa; os seguintes remetem a ele
    tbases = collections.defaultdict(list)
    try:
        for t_ in con.execute("select p.nome,t.id,t.q_ini,t.q_fim,t.titulo,t.subtitulo,t.autoria,t.texto,t.verso from textos_base t join provas p on p.id=t.prova_id"):
            tbases[t_[0]].append({"id": t_[1], "q_ini": t_[2], "q_fim": t_[3], "titulo": t_[4], "subtitulo": t_[5], "autoria": t_[6], "texto": t_[7], "verso": bool(t_[8])})
    except sqlite3.OperationalError:
        pass                                  # banco sem a tabela textos_base: nenhuma disciplina usa texto-base
    vistos_cap = collections.defaultdict(dict)
    def base_de(q, n_cap, rot):
        for t_ in tbases.get(q["prova"], []):
            if t_["q_ini"] <= q["numero"] <= t_["q_fim"]:
                vistos = vistos_cap[n_cap]
                if t_["id"] in vistos:
                    return {"nota": f"Texto-base: o mesmo da questão {vistos[t_['id']]} (acima, neste capítulo)."}
                vistos[t_["id"]] = rot
                return dict(t_, rotulo=f"{q['ano']} · {sig(q['instituicao'])} · questões {t_['q_ini']} a {t_['q_fim']}")
        return None
    def cartoes(n_cap, lista):
        k = 0
        for pc in lista:
            if not por_ponto[pc]:
                continue
            X.append(L.titulo(3, f"{pc} · {pts[pc]['texto']}{fora_txt(pc)}", COR))
            primeiro = True
            for q in por_ponto[pc]:
                if not primeiro:
                    X.append(L.espaco(160))   # espaco so ENTRE cartoes do mesmo topico (o titulo do topico ja tem seu espaco)
                primeiro = False
                k += 1
                rot = f"{n_cap}.{k}"
                sub = f"FCC {q['ano']} · {q['cargo']}" + (f" · Tipo {int(q['tipo_caderno']):03d}" if q["tipo_caderno"] else "")
                pc2 = cod_ponto[q["ponto2_id"]] if q["ponto2_id"] else None
                topico_xml = topico_edital_xml(q, pc, pc2) if real else L.r(topico_seguro(q, pc, conteudo(pc), pc2), color=L.GREY, sz=17)
                ds = json.loads(q["c_disp"]) if q["c_disp"] else []
                for d_ in ds:
                    disp[d_].append((q["ano"], sig(q["instituicao"]), q["numero"], pts[pc]["texto"]))
                gab = "anulada" if q["situacao"] == "anulada" else (q["gabarito"] or "—")
                marcas = []
                if q["disc_origem"] != disc_id:
                    marcas.append("disciplina de origem: " + nome_disc[q["disc_origem"]])
                if art:
                    outros_b = sorted({sg for pid_ in (q["ponto_id"], q["ponto2_id"]) if pid_ for sg in blocos_pt.get(pid_, ())} - {own_bloco})
                    if outros_b:
                        marcas.append("também em " + "; ".join(tit_blocos.get(sg, sg) for sg in outros_b))
                resp = {"marcas": marcas, "gab_prelim": LE.gabarito_preliminar(q["gabarito_status"]), "tipo": q["tipo_cobranca"], "topico_xml": topico_xml, "detalhe": q["detalhe"] or "", "comentario": q["c_texto"] or "",
                        "pegadinha": q["c_peg"] or "", "dispositivos": "; ".join(x.replace("|", ", ") for x in ds), "gab": gab}
                X.append(L.cartao(COR, TINTA, rot, f"{q['ano']}  ·  {sig(q['instituicao'])}  ·  Questão {q['numero']}", sub,
                                  limpa(q["enunciado"]), [limpa(q[f"alt_{x}"]) for x in "abcde"], aviso="ANULADA" if q["situacao"] == "anulada" else ("TEXTO A CONFERIR" if q["situacao"] == "revisar_texto" else None), resp=resp, base=base_de(q, n_cap, rot)))

    for c in ordem_q:
        n_cap = cap_de[c]
        a = an["assuntos"].get(c)
        pts_cap = pts_ed(c)
        qs_total = sum(len(por_ponto[pc]) for pc in pts_cap)
        # capitulo comeca em pagina nova so se for o primeiro ou tiver 4 questoes ou mais (evita paginas quase vazias)
        nova_pg = (c == ordem_q[0] or qs_total >= 4)
        if not nova_pg:
            X.append(L.espaco(300))
        X.append(L.p(L.r(f"CAPÍTULO {n_cap}   ·   Pontos: {pts_cap[0]} a {pts_cap[-1]}", b=True, color=COR, sz=18), keep_next=True, pagina_nova=nova_pg))
        X.append(L.titulo(2, ass[c]["nome"], COR, f"cap{n_cap}"))
        if a:
            X.append(L.p(L.chip(f"{qs_total} questões", COR) + L.chip(f"{a['p']:.0f}% da disciplina", L.MID) + L.chip(f"faixa {a['lo']:.0f}% a {a['hi']:.0f}%", L.LIGHT) + L.chip(a["grupo"], L.AMBER if a["grupo"] == "Cai muito" else L.MID), after=100))
        else:
            X.append(L.p(L.chip("0 questões", COR) + L.chip(f"faixa até {zero_hi}%", L.LIGHT), after=100))
        # a descricao do capitulo pode entregar respostas (ex.: "status supralegal"): ela vai para a tabela de respostas
        # (regra do usuario, 13/11/2026); so fica aqui quando o capitulo nao tem questao
        if qs_total == 0:
            X.append(L.p(L.r(ass[c]["descricao"] or "", i=True, color=L.GREY, sz=19), after=160))
        else:
            X.append(L.espaco(60))
        # mini mapa dos pontos do capitulo
        g = [1000, 5438, 1200, 1500]
        lin = L.cabecalho_tabela(["Ponto", "Conteúdo", "Questões", "Nota 1 · 2 · 3"], g, COR, centro=(2, 3))
        for pc in pts_cap:
            lin += L.linha_dados([pc, pts[pc]["texto"] + fora_txt(pc), len(por_ponto[pc]), "1 ☐  2 ☐  3 ☐"], g, negrito=(0,), centro=(2, 3), sz=18)
        X.append(L.tbl(g, lin))
        X.append(L.espaco(160))
        if qs_total == 0:
            X.append(L.caixa("Nenhuma questão nas provas estudadas", [f"Os pontos deste capítulo constam em programas de alguns editais, mas as provas do universo ({periodo}) não cobraram. Estude pelo edital e leia a norma uma vez."], L.AMBER, L.AMBER_BG))
            X.append(L.quebra())
            continue
        cartoes(n_cap, pts_cap)

    # capitulo unico dos assuntos sem questao no universo (pontos fora do edital ficam na tabela "O que mudou no edital")
    if vazios:
        X.append(L.titulo(2, "Assuntos do edital sem cobrança anterior", COR, f"cap{N_SEM}", pagina_nova=True))
        X.append(L.p(L.chip("0 questões", COR) + L.chip(f"faixa até {zero_hi}%", L.LIGHT), after=100))
        X.append(L.caixa("Sem cobrança no universo não quer dizer que não cai", [f"Estes assuntos constam do edital, mas as provas do universo ({an['universo']['nome']}; {n_val} questões, {periodo}) não cobraram nenhum deles. Com tão poucas questões, a ausência pode ser acaso, e a banca pode cobrar algo novo. Estude pelo edital e leia a norma uma vez; use o histórico para decidir a ordem, não para cortar conteúdo."], L.AMBER, L.AMBER_BG))
        X.append(L.espaco(120))
        g = [850, 2400, 4300, 1588]
        lin = L.cabecalho_tabela(["Ponto", "Conteúdo", "Trechos do edital (literal)" if real else "Descrição do assunto", "Nota 1 · 2 · 3"], g, COR, sz=17, centro=(3,))
        n_pts_sem = 0
        for c in vazios:
            lst = [pc for pc in pts_de(c) if (not real) or pc in edpts]
            if not lst:
                continue
            lin += L.barra_grupo(ass[c]["nome"], g, COR, TINTA)
            for pc in lst:
                n_pts_sem += 1
                n_sec = (an.get("pontos") or {}).get(pc, {}).get("n", 0)      # defeito 2 (A5): ponto so secundario de questoes de outros capitulos
                lin += L.linha_dados([pc, conteudo(pc) + (f"  (só como ponto secundário de questões de outros capítulos: {n_sec:g} no total, contadas pela metade)" if n_sec else ""), trechos_txt(pc) if real else (ass[c]["descricao"] or "—"), "1 ☐  2 ☐  3 ☐"], g, negrito=(0,), centro=(3,), sz=18)
        X.append(L.tbl(g, lin))
        X.append(L.nota(f"{n_pts_sem} pontos em {len(vazios)} assuntos. Quando um ponto aparece só como secundário de questões de outros capítulos, a tabela de frequência o conta (meia questão cada), mas ele não tem capítulo próprio. Pontos que não constam do edital não aparecem aqui; estão em \"O que mudou no edital e o que ficou de fora\"."))

    if fora_q:
        X.append(L.titulo(2, "Temas cobrados anteriormente que não aparecem no edital atual", COR, f"cap{N_FORA}", pagina_nova=True))
        nq_fora = sum(len(por_ponto[pc]) for pc in fora_q)
        X.append(L.p(L.chip(f"{nq_fora} questões", COR) + L.chip("fora do edital", L.AMBER), after=100))
        X.append(L.caixa("Por que estes temas estão aqui", [f"Estes pontos já foram cobrados nas provas do universo ({an['universo']['nome']}), mas não constam do programa de {disc} do edital atual. Em geral, ficam por último na ordem de estudo; leia o edital antes de decidir se vale estudá-los (alguns podem estar dentro de uma frase geral do edital). Os temas que o edital escreve em outra disciplina não entram nesta apostila."], L.AMBER, L.AMBER_BG))
        X.append(L.espaco(120))
        g = [1000, 5438, 1200, 1500]
        lin = L.cabecalho_tabela(["Ponto", "Conteúdo", "Questões", "Nota 1 · 2 · 3"], g, COR, centro=(2, 3))
        for pc in fora_q:
            lin += L.linha_dados([pc, pts[pc]["texto"], len(por_ponto[pc]), "1 ☐  2 ☐  3 ☐"], g, negrito=(0,), centro=(2, 3), sz=18)
        X.append(L.tbl(g, lin))
        X.append(L.espaco(160))
        cartoes(N_FORA, fora_q)

    # ---- Etapa 4 (modelo v2): dispositivos agrupados por FONTE, para o aluno abrir o material e estudar por ordem
    FAMILIAS = ["Constituição", "Códigos e leis", "Súmulas", "Jurisprudência nacional (ações e julgados)", "Casos e jurisprudência internacional",
                "Tratados e convenções", "Soft law, resoluções e órgãos", "Outros"]

    def familia(fonte, item):
        if re.match(r"S[úu]mula", item):
            return "Súmulas"
        if fonte in ("CF", "ADCT", "CRFB", "Constituição Federal"):
            return "Constituição"
        if fonte in ("STF", "STJ", "TST", "TSE", "TRF", "TJ") or re.match(r"(ADI|ADPF|ADC|ADO|HC|RE|REsp|RHC|MS|Tema|IAC|IRDR)\b", item):
            return "Jurisprudência nacional (ações e julgados)"
        if fonte in ("Corte IDH", "CIDH", "TEDH", "CorteIDH") or " vs. " in item:
            return "Casos e jurisprudência internacional"
        if fonte.startswith("Estatuto de Roma"):
            return "Tratados e convenções"
        if re.match(r"(CP|CPP|CPC|CC|CLT|CTN|LEP|CDC|CTB|ECA)$", fonte) or re.match(r"(Lei|Decreto|Lei Complementar|LC|Medida Provisória|MP|Estatuto)\b", fonte):
            return "Códigos e leis"
        if re.match(r"(Resolução|Regras|100 Regras|Agenda|Declaração|Comitê|CNJ|OIT|Princípios|Diretrizes|Comentário|Constituição da OMS|OMS|ONU)", fonte):
            return "Soft law, resoluções e órgãos"
        return "Tratados e convenções"

    def chave_nat(txt):
        nums = [int(x) for x in re.findall(r"\d+", txt)]
        return (nums or [10 ** 9], txt)

    por_fonte = collections.defaultdict(lambda: collections.defaultdict(list))
    for kd, v in disp.items():
        fonte, _, item = kd.partition("|")
        fonte, item = fonte.strip(), item.strip() or "(sem item)"
        por_fonte[(familia(fonte, item), fonte)][item] += v
    X.append(L.titulo(2, "Dispositivos, tratados e casos mais cobrados", COR, "dispositivos", pagina_nova=True))
    X.append(L.p(L.r("Tudo o que já caiu, agrupado por fonte (uma linha para cada Constituição, código, lei, súmula, tribunal ou tratado), para você abrir o material de estudo e ir por ordem. Dentro de cada linha os itens seguem a ordem do texto da norma; entre parênteses, quantas vezes caiu e onde. As fontes de cada grupo estão da mais cobrada para a menos cobrada.", color=L.GREY, sz=19), after=160))
    g = [2300, 6038, 1300]
    linhas = L.cabecalho_tabela(["Fonte", "O que já caiu (ordem do texto; entre parênteses, onde caiu)", "Vezes"], g, COR, centro=(2,))
    for fam in FAMILIAS:
        fontes = [(fo, its) for (fa, fo), its in por_fonte.items() if fa == fam]
        if not fontes:
            continue
        fontes.sort(key=lambda x: (-sum(len(r) for r in x[1].values()), x[0]))
        linhas += L.barra_grupo(f"{fam}  ·  {len(fontes)} fonte(s)", g, COR, TINTA)
        for fo, its in fontes:
            par = []
            for it in sorted(its, key=chave_nat):
                refs = its[it]
                onde = "; ".join(f"{a_} {o} Q{n}" for a_, o, n, _ in refs[:3]) + ("…" if len(refs) > 3 else "")
                par.append(L.r(it, b=True, sz=18) + L.r(f"   ({len(refs)}×: {onde})", color=L.GREY, sz=16))
            linhas += L.linha_dados([fo, par, sum(len(r) for r in its.values())], g, negrito=(0,), centro=(2,), sz=18, nao_quebrar=False)   # linha longa (ex.: CP) pode quebrar de página
    X.append(L.tbl(g, linhas))
    X.append(L.nota(f"{len(disp)} dispositivos distintos em {len(por_fonte)} fontes. A família de cada fonte é decidida pelo nome (ex.: \"STF\" com \"Súmula\" vai para Súmulas); o que não encaixa vai para Outros."))
    X.append(L.espaco(200))

    # ---- Etapa 5 (modelo v2): "o que mudou no edital e o que ficou de fora" em TABELA
    def tabela_mudou(grupos):
        gm = [1000, 3700, 800, 4138]
        lm = L.cabecalho_tabela(["Ponto", "Conteúdo", "Q.", "Observação"], gm, COR, centro=(2,))
        for tit, linhas_g in grupos:
            if not linhas_g:
                continue
            lm += L.barra_grupo(f"{tit}  ·  {len(linhas_g)}", gm, L.AMBER, L.AMBER_BG)
            for cod, nome, nq, obs in linhas_g:
                lm += L.linha_dados([cod, nome, str(nq), obs], gm, negrito=(0,), centro=(2,), sz=18)
        return L.tbl(gm, lm)

    if real:
        X.append(L.titulo(2, "O que mudou no edital e o que ficou de fora", COR, "novos", pagina_nova=True))
        fora = sorted(pc for pc in pts if pc not in edpts)
        fj = [pc for pc in fora if ((not art) or pc in art["fora"]) and not por_ponto[pc]]     # os que ja cairam estao no capitulo proprio
        sj = [pc for pc in fora if art and pc not in art["fora"] and not por_ponto[pc]]
        X.append(L.p(L.r((f"Edital de referência: «{ed['nome']}». A classificação das frases do edital em pontos é rascunho da IA; confira no edital." if art else ed["descricao"]) + " Pontos do edital sem questão aparecem na tabela de pontos de cada capítulo" + (" e na seção dos assuntos sem cobrança" if vazios else "") + ". Temas já cobrados fora do edital estão na seção própria.", color=L.GREY, sz=18), after=120))
        gm = [3800, 5338]
        lm = L.cabecalho_tabela(["Motivo (por que não está no edital)", "Pontos do catálogo que nunca caíram"], gm, COR)
        mot = collections.OrderedDict()
        for pc in fj:
            mot.setdefault(art["fora"][pc] if art else "Não consta do programa.", []).append(pc)
        if mot:
            lm += L.barra_grupo(f"Fora do edital  ·  {len(fj)} pontos", gm, L.AMBER, L.AMBER_BG)
            for m_, lst in mot.items():
                lm += L.linha_dados([m_, "; ".join(f"{pc} {pts[pc]['texto']}" for pc in lst)], gm, sz=17)
        if sj:
            lm += L.barra_grupo(f"A conferir no edital (sem julgamento)  ·  {len(sj)} pontos", gm, L.AMBER, L.AMBER_BG)
            lm += L.linha_dados(["Confira no edital antes de decidir se estuda.", "; ".join(f"{pc} {pts[pc]['texto']}" for pc in sj)], gm, sz=17)
        X.append(L.tbl(gm, lm))
    else:
        X.append(L.titulo(2, "Pontos novos dos editais", COR, "novos"))
        novos = [pc for c in ordem for pc, pv in pts.items() if cod_ass_de_id[pv["assunto_id"]] == c and edpts.get(pc, {}).get("marca_novo")]
        sem = [pc for pc in pts if not por_ponto[pc]]
        X.append(L.p(L.r("Como não há prova antiga que confirme os pontos novos, a prioridade vem do edital (Guia 2, capítulo 2): trate-os como \"cai muito\" até ver a próxima prova.", color=L.GREY, sz=18), after=120))
        X.append(tabela_mudou([
            ("Aparecem só nos editais de 2025 e 2026", [(pc, pts[pc]["texto"], len(por_ponto[pc]), f"Capítulo {cap_de[cod_ass_de_id[pts[pc]['assunto_id']]]}") for pc in novos]),
            ("Sem nenhuma questão nas provas estudadas", [(pc, pts[pc]["texto"], 0, "Leia o edital e a norma uma vez.") for pc in sem])]))
    inserir(doc, "".join(X))
    out = perfil["pasta"] if perfil.get("pasta") else PROJ / "produtos" / "apostilas" / disc.lower().replace(" ", "-")   # pasta do concurso (perfil.toml)
    out.mkdir(parents=True, exist_ok=True)
    sufixo = " [modelo novo]"     # modelo v2 (docs/arquivo/04-PLANO-MODELO-APOSTILA-V2.md): não sobrescreve a apostila do modelo antigo
    arq = out / (f"Apostila - {disc} ({perfil['cargo']} {perfil['banca']} · {perfil['orgao']} {ed['ano']}){sufixo}.docx" if real and perfil.get("orgao") else f"Apostila - {disc} ({perfil['carreira']} {perfil['banca']}){sufixo}.docx")
    doc.save(str(arq))
    main.arq = arq
    print("gerado:", arq, round(arq.stat().st_size / 1024), "KB; dispositivos:", len(disp), "; questoes:", sum(len(v) for v in por_ponto.values()))


if __name__ == "__main__":
    main()                                    # 1a passada: sem numeros de pagina no sumario
    PAG.update(paginas_do_pdf(main.arq))      # acha as paginas no PDF
    main()                                    # 2a passada: sumario com os numeros
