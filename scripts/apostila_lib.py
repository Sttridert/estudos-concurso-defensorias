"""Biblioteca de design da apostila (reproduz o visual de 'Apostila inicial - Penal e Direitos Humanos.docx').
Sistema de design (tirado do modelo):
- Tipografia: Calibri; corpo 10,5 pt (sz 21); cartoes 10 pt; rotulos 8 a 8,5 pt em negrito; H1 22 pt, H2 17 pt, H3 12 pt; entrelinha 1,15 (276).
- Cores: tinta 1f2328, cinza 5b6470, cinza medio 57606a, cinza claro 8c959f, borda d0d7de, fundo f6f8fa,
  destaque da disciplina (azul 1f4e79 com tinta e8f0f8; vinho 8b1e3f com tinta f8e9ee), ambar 9a6700 (tinta fff4d6), verde 1a7f37.
- Etiquetas de cobranca: lei 0b5cad, sumula b35900, jurisprudencia 6f42c1, doutrina 1a7f37, caso pratico 57606a.
- Componentes: capa; caixa de destaque (tabela de 1 celula com barra grossa a esquerda); cartao de questao (tabela de 2 colunas);
  tabelas de dados (cabecalho na cor da disciplina, linhas com borda d0d7de, linhas que nao quebram); barras de grupo; etiquetas ("chips").
Todas as funcoes devolvem strings XML (WordprocessingML) para serem inseridas no corpo do documento.
"""
import re
from xml.sax.saxutils import escape

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
INK, GREY, MID, LIGHT, BORDER, BG = "1f2328", "5b6470", "57606a", "8c959f", "d0d7de", "f6f8fa"
AMBER, AMBER_BG, GREEN, RED = "9a6700", "fff4d6", "1a7f37", "b42318"
AZUL, AZUL_BG, VINHO, VINHO_BG = "1f4e79", "e8f0f8", "8b1e3f", "f8e9ee"
TAG = {"lei/tratado": ("Letra de lei", "0b5cad"), "sumula": ("Súmula", "b35900"), "jurisprudencia": ("Jurisprudência", "6f42c1"),
       "doutrina": ("Doutrina", "1a7f37"), "caso pratico": ("Caso prático", "57606a")}
LARGURA = 9638  # largura util em dxa (A4, margens de 2 cm)
_bm = [100]


def esc(t):
    return escape(t or "", {'"': "&quot;"})


def r(texto, b=False, i=False, color=INK, sz=21, shd=None, hl=None, caps=False, u=False):
    pr = '<w:rFonts w:ascii="Calibri" w:cs="Calibri" w:eastAsia="Calibri" w:hAnsi="Calibri"/>'
    if b: pr += '<w:b w:val="1"/><w:bCs w:val="1"/>'
    if i: pr += '<w:i w:val="1"/><w:iCs w:val="1"/>'
    if caps: pr += '<w:caps w:val="1"/>'
    pr += f'<w:color w:val="{color}"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    if u: pr += '<w:u w:val="single"/>'
    if hl: pr += f'<w:highlight w:val="{hl}"/>'
    if shd: pr += f'<w:shd w:fill="{shd}" w:val="clear"/>'
    return f'<w:r><w:rPr>{pr}</w:rPr><w:t xml:space="preserve">{esc(texto)}</w:t></w:r>'


_MARCA = re.compile(r"(</?[ub]>)")


def rt(texto, **kw):
    """como r(), mas entende as marcas <u>…</u> (sublinhado) e <b>…</b> (destaque) e a quebra de linha (\\n) do texto do banco.
    Usado nas questoes de Lingua Portuguesa (sublinhados e destaques da prova). Marca desconhecida fica como texto."""
    sub = bold = False
    runs = ""
    for linha_n, linha in enumerate((texto or "").split("\n")):
        if linha_n:
            runs += "<w:r><w:br/></w:r>"
        for parte in _MARCA.split(linha):
            if parte == "<u>": sub = True
            elif parte == "</u>": sub = False
            elif parte == "<b>": bold = True
            elif parte == "</b>": bold = False
            elif parte:
                k = dict(kw)
                if sub: k["u"] = True
                if bold: k["b"] = True
                runs += r(parte, **k)
    return runs


def chip(texto, fill, sz=17):
    """etiqueta: texto branco em negrito sobre fundo colorido"""
    return r(f" {texto} ", b=True, color="ffffff", sz=sz, shd=fill) + r("  ", sz=sz)


def p(runs="", after=0, before=0, line=276, jc=None, ind=None, keep_next=False, top=None, bottom=None, bullet=False,
      style=None, bookmark=None, keep_lines=False, pagina_nova=False, tab_dir=None):
    ppr = ""
    if style: ppr += f'<w:pStyle w:val="{style}"/>'
    if keep_next: ppr += '<w:keepNext w:val="1"/>'
    if keep_lines: ppr += '<w:keepLines w:val="1"/>'
    if pagina_nova: ppr += '<w:pageBreakBefore w:val="1"/>'
    if bullet: ppr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
    if top or bottom:
        ppr += "<w:pBdr>"
        if top: ppr += f'<w:top w:color="{top[0]}" w:space="{top[2]}" w:sz="{top[1]}" w:val="single"/>'
        if bottom: ppr += f'<w:bottom w:color="{bottom[0]}" w:space="{bottom[2]}" w:sz="{bottom[1]}" w:val="single"/>'
        ppr += "</w:pBdr>"
    if tab_dir: ppr += f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{tab_dir}"/></w:tabs>'
    ppr += f'<w:spacing w:after="{after}" w:before="{before}" w:line="{line}" w:lineRule="auto"/>'
    if bullet: ppr += '<w:ind w:left="300" w:right="0" w:hanging="220"/>'
    elif ind: ppr += f'<w:ind w:left="{ind}" w:firstLine="0"/>'
    if jc: ppr += f'<w:jc w:val="{jc}"/>'
    bm_open = bm_close = ""
    if bookmark:
        _bm[0] += 1
        bm_open = f'<w:bookmarkStart w:id="{_bm[0]}" w:name="{bookmark}"/>'; bm_close = f'<w:bookmarkEnd w:id="{_bm[0]}"/>'
    return f"<w:p><w:pPr>{ppr}</w:pPr>{bm_open}{runs}{bm_close}</w:p>"


def tab():
    return '<w:r><w:tab/></w:r>'


def pageref(anchor, texto, b=False, sz=19, color=None):
    """campo PAGEREF (numero da pagina do marcador); o texto e o valor em cache, o Word atualiza com Ctrl+A e F9"""
    rpr = f'<w:rPr><w:rFonts w:ascii="Calibri" w:cs="Calibri" w:eastAsia="Calibri" w:hAnsi="Calibri"/>' + ('<w:b w:val="1"/>' if b else "") + (f'<w:color w:val="{color}"/>' if color else "") + f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
    return (f'<w:r>{rpr}<w:fldChar w:fldCharType="begin"/></w:r><w:r>{rpr}<w:instrText xml:space="preserve"> PAGEREF {anchor} \\h </w:instrText></w:r>'
            f'<w:r>{rpr}<w:fldChar w:fldCharType="separate"/></w:r><w:r>{rpr}<w:t>{texto}</w:t></w:r><w:r>{rpr}<w:fldChar w:fldCharType="end"/></w:r>')


def link(anchor, runs):
    return f'<w:hyperlink w:anchor="{anchor}">{runs}</w:hyperlink>'


def quebra():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def espaco(after=120):
    return p("", after=after)


def titulo(nivel, texto, cor, bookmark=None, pagina_nova=False):
    """nivel 3 (topicos) leva um espaco acima e um abaixo; pagina_nova comeca o titulo em pagina nova (sem paragrafo de quebra)"""
    esp = dict(before=360, after=300) if nivel == 3 else {}
    return p(r(texto, b=True, color=cor, sz={1: 44, 2: 34, 3: 24}[nivel]), style=f"Heading{nivel}", bookmark=bookmark, pagina_nova=pagina_nova, **esp)


# ---------------------------------------------------------------- tabelas
def _bd(cor, sz=4):
    return "".join(f'<w:{l} w:color="{cor}" w:space="0" w:sz="{sz}" w:val="single"/>' for l in ("top", "left", "bottom", "right"))


def tc(conteudo, w, fill=None, borda=BORDER, span=1, mar=(80, 140, 80, 140), valign="top", esquerda=None):
    """celula. esquerda=(cor, sz) cria barra grossa so a esquerda (caixa de destaque)"""
    pr = f'<w:tcW w:w="{w}" w:type="dxa"/>'
    if span > 1: pr += f'<w:gridSpan w:val="{span}"/>'
    if esquerda:
        pr += f'<w:tcBorders><w:top w:val="nil"/><w:left w:color="{esquerda[0]}" w:space="0" w:sz="{esquerda[1]}" w:val="single"/><w:bottom w:val="nil"/><w:right w:val="nil"/></w:tcBorders>'
    else:
        pr += f"<w:tcBorders>{_bd(borda)}</w:tcBorders>"
    if fill: pr += f'<w:shd w:fill="{fill}" w:val="clear"/>'
    pr += f'<w:tcMar><w:top w:w="{mar[0]}" w:type="dxa"/><w:left w:w="{mar[1]}" w:type="dxa"/><w:bottom w:w="{mar[2]}" w:type="dxa"/><w:right w:w="{mar[3]}" w:type="dxa"/></w:tcMar><w:vAlign w:val="{valign}"/>'
    return f"<w:tc><w:tcPr>{pr}</w:tcPr>{conteudo}</w:tc>"


def tr(celulas, cabecalho=False, nao_quebrar=True):
    pr = f'<w:cantSplit w:val="{1 if nao_quebrar else 0}"/>' + ('<w:tblHeader w:val="1"/>' if cabecalho else "")
    return f"<w:tr><w:trPr>{pr}</w:trPr>{celulas}</w:tr>"


def tbl(grade, linhas):
    g = "".join(f'<w:gridCol w:w="{w}"/>' for w in grade)
    return (f'<w:tbl><w:tblPr><w:tblW w:w="{sum(grade)}" w:type="dxa"/><w:jc w:val="left"/><w:tblLayout w:type="fixed"/><w:tblLook w:val="0000"/></w:tblPr>'
            f"<w:tblGrid>{g}</w:tblGrid>{linhas}</w:tbl>")


def caixa(titulo_txt, itens, cor, fundo, titulo_sz=21):
    """caixa de destaque: barra grossa a esquerda, fundo suave, titulo e marcadores"""
    corpo = p(r(titulo_txt, b=True, color=cor, sz=titulo_sz), after=60)
    for it in itens:
        corpo += p(it if it.startswith("<w:r") else r(it, sz=21), after=40, bullet=True)
    return tbl([LARGURA], tr(tc(corpo, LARGURA, fill=fundo, esquerda=(cor, 24)), nao_quebrar=False))


def cabecalho_tabela(rotulos, grade, cor, sz=19, centro=()):
    cs = ""
    for k, (rot, w) in enumerate(zip(rotulos, grade)):
        cs += tc(p(r(rot, b=True, color="ffffff", sz=sz), jc="center" if k in centro else None), w, fill=cor, borda=cor, mar=(70, 100, 70, 100))
    return tr(cs, cabecalho=True, nao_quebrar=False)


def linha_dados(valores, grade, sz=19, negrito=(), centro=(), fundo=None, nao_quebrar=True):
    """valores: texto, runs XML (comecam com '<w:r') ou lista (um paragrafo por elemento, para celulas com varias linhas)"""
    cs = ""
    for k, (v, w) in enumerate(zip(valores, grade)):
        jc = "center" if k in centro else None
        if isinstance(v, list):
            pars = [x if str(x).startswith("<w:r") else r(str(x), b=(k in negrito), sz=sz) for x in v] or [""]
            cont = "".join(p(x, jc=jc, after=(40 if n < len(pars) - 1 else 0)) for n, x in enumerate(pars))
        else:
            cont = p(v if str(v).startswith("<w:r") else r(str(v), b=(k in negrito), sz=sz), jc=jc)
        cs += tc(cont, w, fill=fundo, mar=(60, 100, 60, 100), valign="center")
    return tr(cs, nao_quebrar=nao_quebrar)


def barra_grupo(texto, grade, cor, fundo, sz=18):
    return tr(tc(p(r(texto, b=True, color=cor, sz=sz), keep_next=True), sum(grade), fill=fundo, span=len(grade), mar=(60, 100, 60, 100)))


# ---------------------------------------------------------------- tags e cartao de questao (modelo v2, 14/11/2026)
# O banco mistura dois vocabularios de tipo de cobranca (DH: lei/tratado, caso pratico; demais disciplinas: lei_seca,
# caso_concreto). O codigo interpreta na hora de gerar a apostila (decisao do usuario); o banco nao e alterado.
TAG_EXTRA = {"interpretacao": ("Interpretação de texto", "0b7285"), "gramatica": ("Gramática", "5f3dc4")}   # Língua Portuguesa; só aparecem na legenda se usadas
TAG_ALIAS = {"lei_seca": "lei/tratado", "lei seca": "lei/tratado", "letra de lei": "lei/tratado", "lei": "lei/tratado",
             "caso_concreto": "caso pratico", "caso concreto": "caso pratico", "caso_pratico": "caso pratico"}
_tag_avisos = set()


def tag_de(tipo):
    """(nome, cor) da tag da legenda da capa; valor desconhecido avisa no terminal e vira 'Sem tipo' (nunca mostra o texto cru)"""
    k = (tipo or "").strip()
    k = TAG_ALIAS.get(k, k)
    if k in TAG:
        return TAG[k]
    if k in TAG_EXTRA:
        return TAG_EXTRA[k]
    if k not in _tag_avisos:
        _tag_avisos.add(k)
        print(f"  aviso: tipo de cobranca desconhecido {tipo!r}; mostrado como 'Sem tipo'")
    return ("Sem tipo", MID)


def caixa_texto_base(base):
    """conteudo do texto-base: base = {titulo, subtitulo, autoria, texto, verso, nota}. Se so houver `nota`, mostra a remissao
    ao texto ja impresso acima (mesmo capitulo)."""
    if base.get("nota"):
        return p(r(base["nota"], i=True, color=GREY, sz=17), after=0)
    c = p(r("TEXTO-BASE   ", b=True, color=LIGHT, sz=15) + (r(base.get("rotulo") or "", color=LIGHT, sz=15)), after=40, keep_next=True)
    if base.get("titulo"):
        c += p(r(base["titulo"], b=True, color=INK, sz=20), after=30, jc="center", keep_next=True)
    if base.get("subtitulo"):
        c += p(r(base["subtitulo"], i=True, color=GREY, sz=17), after=60, jc="center", keep_next=True)
    for par in (base.get("texto") or "").split("\n\n"):
        if base.get("verso"):
            c += p(rt(par, color="3d444d", sz=19, i=True), after=80, line=252, ind=2400)
        else:
            c += p(rt(par, color="3d444d", sz=19), after=60, line=252, jc="both")
    if base.get("autoria"):
        c += p(r(base["autoria"], color=GREY, sz=15), after=0, jc="right")
    return c


def cartao(cor, tinta, rot, titulo_txt, sub_txt, enunciado, alternativas, aviso=None, resp=None, base=None):
    """cartao de questao em tabela: cabecalho colorido com o NUMERO a esquerda (rot = capitulo.sequencia), enunciado e
    alternativas; logo abaixo, a linha de RESPOSTA E COMENTARIOS (modelo v2: o usuario le de cima para baixo, responde e
    depois olha a linha de baixo) e a linha 'Meu resultado'. resp = {tipo, topico_xml, detalhe, comentario, pegadinha,
    dispositivos, gab} ou None. Nenhuma resposta aparece acima da linha de resposta."""
    cab = p(r(f" {rot} ", b=True, color=cor, sz=22, hl="white") + r("   " + titulo_txt, b=True, color="ffffff", sz=21) + r("   " + sub_txt, color="ffffff", sz=17)
            + (r("   " + aviso + " ", b=True, color=RED, sz=17, shd="ffffff") if aviso else ""), keep_next=True)   # cabeçalho não fica sozinho no fim da página
    linhas = tr(tc(cab, LARGURA, fill=cor, borda=cor, valign="center", span=2))
    if base:   # texto-base da questao (Lingua Portuguesa): linha propria, antes do enunciado
        linhas += tr(tc(caixa_texto_base(base), LARGURA, span=2, fill=BG, mar=(100, 140, 80, 140)), nao_quebrar=False)
    corpo = p(rt(enunciado, sz=21), after=100)
    for letra, txt in zip("ABCDE", alternativas):
        corpo += p(r(f"({letra})  ", b=True, color=GREY, sz=20) + rt(txt, color="3d444d", sz=20), after=50)
    linhas += tr(tc(corpo, LARGURA, span=2, mar=(120, 140, 100, 140)), nao_quebrar=False)
    if resp:
        nome_tag, cor_tag = tag_de(resp.get("tipo"))
        partes = [(r("O QUE FOI COBRADO   ", b=True, color=GREY, sz=16) + chip(nome_tag, cor_tag), 60)]
        if resp.get("topico_xml"):
            partes.append((r("Tópico exato: ", b=True, color=GREY, sz=17) + resp["topico_xml"], 40))
        if resp.get("marcas"):      # decisao 41: disciplina de origem e "tambem em <outra apostila>" (auditabilidade)
            partes.append((r("Origem: ", b=True, color=GREY, sz=17) + r("  ·  ".join(resp["marcas"]), color=GREY, sz=17), 40))
        if resp.get("detalhe"):
            partes.append((r("Detalhe: ", b=True, color=GREY, sz=17) + r(resp["detalhe"], color=GREY, sz=17), 40))
        if resp.get("comentario"):
            partes.append((r(resp["comentario"], sz=20), 50))
        if resp.get("pegadinha"):
            partes.append((r("Pegadinha: ", b=True, color=INK, sz=19) + r(resp["pegadinha"], color="3d444d", sz=19), 40))
        if resp.get("dispositivos"):
            partes.append((r("Dispositivos: ", b=True, color=GREY, sz=17) + r(resp["dispositivos"], color=GREY, sz=17), 40))
        # a linha pode quebrar entre paginas (sem espacos em branco), mas o ultimo paragrafo fica junto do gabarito
        c = "".join(p(x, after=a_, keep_next=(n == len(partes) - 1), keep_lines=(n == len(partes) - 1)) for n, (x, a_) in enumerate(partes))
        c += p(r("GABARITO  ", b=True, color=LIGHT, sz=14) + r(resp.get("gab") or "—", color=LIGHT, sz=15)
              + ("   " + chip("gabarito preliminar", AMBER) if resp.get("gab_prelim") else ""), before=40, after=0)
        linhas += tr(tc(c, LARGURA, fill=BG, span=2, mar=(90, 140, 90, 140)), nao_quebrar=False)
    linhas += tr(tc(p(r("MEU RESULTADO   ", b=True, color=GREY, sz=15) + r("☐ Acertei      ☐ Errei", color=GREY, sz=18), after=0), LARGURA, fill=BG, span=2, mar=(50, 140, 50, 140)))
    return tbl([6838, 2800], linhas)


def anote_erros(rotulo):
    """fim do capitulo: so o espaco para anotar os erros (as respostas agora ficam abaixo de cada questao)"""
    return tbl([LARGURA], tr(tc(p(r(f"ANOTE AQUI OS ERROS DO {rotulo.upper()}   ", b=True, color=GREY, sz=15) + r("(números das questões que errou; diga ao agente no chat)", i=True, color=LIGHT, sz=15), after=60)
                                + p(r("______________________________________________________________________________________", color=BORDER, sz=18), after=0), LARGURA, fill="ffffff", mar=(70, 140, 70, 140))))


# ---------------------------------------------------------------- capa, sumario, cabecalhos
def capa(rotulo, linha1, cor1, linha2, cor2, subtitulo, meta):
    return (p(r(rotulo, b=True, color=GREY, sz=22), after=60) + p(r(linha1, b=True, color=cor1, sz=60), after=0)
            + p(r(linha2, b=True, color=cor2, sz=60), after=240) + p(r(subtitulo, color=INK, sz=26), after=60, top=(INK, 12, 8))
            + p(r(meta, color=GREY, sz=22), after=1000))


def rotulo_secao(texto, cor=GREY, sz=20):
    return p(r(texto, b=True, color=cor, sz=sz), keep_next=True)


def legenda_cobranca(extras=()):
    cs = r("Legenda dos tipos de cobrança:  ", b=True, color=GREY, sz=18)
    for _, (nome, cor) in TAG.items(): cs += chip(nome, cor)
    for k in extras:
        if k in TAG_EXTRA: cs += chip(*TAG_EXTRA[k])
    return p(cs, after=80)


def fonte(texto):
    return p(r(texto, i=True, color=GREY, sz=16), after=80, before=120)


def nota(texto):
    return p(r(texto, i=True, color=GREY, sz=17), after=160, before=60)
