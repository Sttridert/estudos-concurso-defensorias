"""Biblioteca do grupo A (Coletar), pista de editais: leitura do programa de um edital em PDF.

Núcleo que antes ficava dentro do script 40 e era importado pelo 50 por `importlib` (dependência cruzada entre grupos).
Agora o 40 (lote do edital fictício geral, grupo B) e `coletar_programa_edital.py` (edital real, grupo A) usam esta biblioteca.

  texto_pdf, secoes, e_titulo   acham os títulos de disciplina e cortam as seções do PDF
  juntar, dividir_itens, frases transformam o texto de uma seção em itens (pela numeração do edital) e frases literais
  dividir_itens_tolerante       aceita numeração irregular do edital (item repetido ou pulado)
  processar                     extrai uma disciplina-alvo (`ALVOS`) de um edital
  listar_disciplinas            lista TODOS os títulos de disciplina que o PDF traz (não só as `ALVOS`)
Regras (CLAUDE.md): texto literal; só se juntam quebras de linha e palavras hifenizadas no fim da linha. Hifenização duvidosa
fica em `avisos`. Nada aqui altera o banco.
"""
import csv, json, re, subprocess, sys, unicodedata, collections
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INVENTARIO = RAIZ / "dados" / "coleta" / "inventario_editais_edital_geral.csv"

# Quais títulos (em maiúsculas, sem acento) pertencem a cada disciplina: padrões em dados/disciplinas.json (fonte única).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_disciplinas as _LD  # noqa: E402
ALVOS = _LD.padroes_titulo()
# Qualquer título de disciplina (para saber onde a seção termina).
TITULO_GERAL = re.compile(
    r"^(DIREITO|DIREITOS|PRINCIPIOS|CRIMINOLOGIA|FILOSOFIA|SOCIOLOGIA|NOCOES|LINGUA|LEGISLACAO|EXECUCAO|TUTELA|ESTATUTO|"
    r"MEDICINA|ADMINISTRACAO|CIENCIA|PROCESSO|ETICA|HISTORIA|GEOGRAFIA|CONHECIMENTOS|RACIOCINIO|INFORMATICA|TEORIA|"
    r"SISTEMA|ECONOMIA|POLITICA|INTRODUCAO|ATRIBUICOES)\b")
PREFIXOS_COM_HIFEN = {"pos", "pre", "anti", "ex", "sem", "sub", "vice", "nao", "auto", "contra", "inter", "ultra", "extra",
                      "neo", "pan", "socio", "ibero", "afro", "luso", "arqui", "co", "semi", "pro", "pseudo", "todo", "infra"}
ABREV = {"art", "arts", "n", "no", "nº", "inc", "incs", "par", "dec", "p", "pp", "ex", "cf", "v", "vs", "ss", "al", "dr", "dra",
         "prof", "profa", "min", "rel", "obs", "ob", "cap", "caps", "sec", "tit", "ac", "adv", "ed", "resp", "reg", "jur", "etc", "ca"}


def norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").upper()


def texto_pdf(pdf: Path, layout: bool = True) -> list[str]:
    cmd = ["pdftotext"] + (["-layout"] if layout else []) + ["-enc", "UTF-8", str(pdf), "-"]
    r = subprocess.run(cmd, capture_output=True)
    linhas = r.stdout.decode("utf-8", "replace").splitlines()
    cont = collections.Counter(l.strip() for l in linhas if l.strip())
    ruido = re.compile(r"^(P[áa]gina\s+\d+\s*(de\s*\d+)?|\d{1,3})$", re.I)
    limpas = []
    for l in linhas:
        s = l.strip()
        if not s or ruido.match(s) or (cont[s] >= 6 and len(s) < 120):
            continue
        if re.search(r"\S {3,}\S.* {3,}\S", l.rstrip()) and not l.startswith(" " * 20):
            limpas.append("ΩTABELA")      # linha de tabela (várias colunas): encerra a seção
            continue
        limpas.append(s)
    # título de disciplina em maiúsculas no meio da linha ("... Partilha de bens. DIREITO PROCESSUAL CIVIL: 1. Código ..."): vira linha própria
    sep = re.compile(r"(?<=[\.;])\s+(?=[A-ZÀ-Ú][A-ZÀ-Ú ,]{8,80}:\s+\d)")
    saida = []
    for s in limpas:
        saida.extend(sep.split(s) if s != "ΩTABELA" else [s])
    return saida



def e_titulo_simples(s: str) -> bool:
    return bool(re.fullmatch(r"[A-ZÀ-Ú][A-ZÀ-Ú ,\-/&]{7,90}", s)) or s in ("ΩTABELA",)


def anterior_ok_geral(anterior: str) -> bool:
    return (not anterior) or anterior[-1:] in ".;:?!)" or e_titulo_simples(anterior)


def e_titulo(s: str, anterior: str = ""):
    """Devolve (nome_normalizado, resto_na_mesma_linha) se a linha for título de disciplina."""
    if s == "ΩTABELA":
        return "TABELA", ""
    if re.match(r"^ANEXO\s+[IVX\d]+\b", s.upper()) and not re.match(r"^ANEXO\s+[IVX\d]+\s*[-–]\s*(DIREITO|DIREITOS)", norm(s)):
        return "ANEXO", ""   # fim de qualquer seção de disciplina
    s0 = re.sub(r"^(ANEXO [IVX]+\s*[-–]\s*)", "", s)
    s0 = re.sub(r"^(\(?[IVX]+\)?|\d{1,2})[\.\-–)]\s+(?=[A-ZÀ-Ú])", "", s0)
    m = re.match(r"^([A-ZÀ-Ú][A-ZÀ-Ú0-9 ,\-–/&\(\)ºª\.]{4,110}?)\s*:\s*(.*)$", s0)
    if m and m.group(1).strip().isupper():
        nome, resto = m.group(1).strip(), m.group(2)
        if re.match(r"^(DR|DRA|PROF)\b", norm(resto)):   # lista de examinadores, não programa
            return None
        if TITULO_GERAL.match(norm(nome)):
            return norm(nome), resto
        return None
    letras = re.sub(r"[^A-Za-zÀ-ú]", "", s0)
    if letras and s0.upper() == s0 and len(s0) <= 130 and TITULO_GERAL.match(norm(s0)):
        return norm(re.sub(r"\s+PONTO\s+[IVX]+$", "", s0)), ""
    if (s0.upper() == s0 and re.fullmatch(r"[A-ZÀ-Ú][A-ZÀ-Ú ,\-/&]{7,90}", s0) and len(s0.split()) >= 2
            and anterior_ok_geral(anterior)):
        return norm(s0), ""
    # prefixo em maiúsculas (3 ou mais palavras) seguido de ponto/dois-pontos e do texto na mesma linha
    m3 = re.match(r"^([A-ZÀ-Ú][A-ZÀ-Ú ,\-/&]{20,}?)\s*[\.:]\s+(\S.*)$", s0)
    if m3 and m3.group(1).isupper() and TITULO_GERAL.match(norm(m3.group(1))) and not re.match(r"^(DR|DRA|PROF)\b", norm(m3.group(2))):
        return norm(m3.group(1)), m3.group(2)
    # título em caixa mista seguido de dois-pontos e do item 1 na mesma linha (ex.: "Direitos Humanos: 1. Origem...")
    m2 = re.match(r"^(Direitos? [A-Za-zÀ-ú ,]{3,70}|Legisla[çc][ãa]o Penal Especial)\s*:\s*(\d.*)$", s0)
    if m2:
        return norm(m2.group(1)), m2.group(2)
    # título sozinho na linha, em qualquer caixa (ex.: "Direitos Humanos"), só palavras, sem ponto final
    n = norm(s0).rstrip(" :")
    anterior_ok = (not anterior) or anterior[-1:] in ".;:?!)" or anterior in ("ΩTABELA",) or bool(e_titulo_simples(anterior))
    if anterior_ok and len(n) <= 100 and not re.search(r"[\d\.;]", n) and (
            re.fullmatch(r"DIREITOS?( [A-Z,]+){1,14}", n)
            or re.fullmatch(r"(CRIMINOLOGIA|EXECUCAO PENAL|LEGISLACAO PENAL( ESPECIAL)?|FILOSOFIA( [A-Z,]+)*|SOCIOLOGIA( [A-Z,]+)*|"
                            r"NOCOES( [A-Z,]+)+|PRINCIPIOS( [A-Z,]+)+|LINGUA PORTUGUESA|CONHECIMENTOS( [A-Z,]+)+|TUTELA COLETIVA|"
                            r"MEDICINA LEGAL|TEORIA GERAL( [A-Z,]+)+|PROCESSO( [A-Z,]+)+|ATRIBUICOES( [A-Z,]+)+)", n)):
        return n, ""
    return None


def secoes(linhas: list[str]):
    """Lista de (nome_norm, linhas_da_seção) para cada título encontrado."""
    marcas = []
    for i, l in enumerate(linhas):
        t = e_titulo(l, linhas[i - 1] if i else "")
        if t:
            marcas.append((i, t[0], t[1]))
    out = []
    for k, (i, nome, resto) in enumerate(marcas):
        fim = marcas[k + 1][0] if k + 1 < len(marcas) else len(linhas)
        corpo = ([resto] if resto else []) + linhas[i + 1:fim]
        out.append((nome, corpo))
    return out


def juntar(linhas: list[str], avisos: list[str]) -> str:
    out = ""
    for l in linhas:
        esq_sigla = re.findall(r"[A-Za-zÀ-ú]+", out)[-1:]
        if out.endswith("-") and esq_sigla and esq_sigla[0].isupper() and len(esq_sigla[0]) >= 2 and l[:1].isupper():
            out = out + l            # sigla ou nome composto ("DPE-" + "AM"): o hifen e do proprio nome e fica
        elif out.endswith("-") and l[:1].islower():
            esq = re.findall(r"[A-Za-zÀ-ú]+", out)[-1] if re.findall(r"[A-Za-zÀ-ú]+", out) else ""
            if norm(esq).lower() in PREFIXOS_COM_HIFEN:
                out = out + l
            else:
                out = out[:-1] + l
                avisos.append(f"hifen removido: ...{esq}-|{l.split()[0]}")
        else:
            out = (out + " " + l) if out else l
    return re.sub(r"\s+", " ", out).strip()


def sucessores(p: list):
    s = [p[:-1] + [p[-1] + 1], p + [1]]
    for i in range(len(p) - 1):
        s.append(p[:i] + [p[i] + 1])
    return [tuple(x) for x in s]


def dividir_itens(txt: str):
    """Divide o texto em [(rotulo, texto)] pela numeração sequencial do edital."""
    # numeração tipo 1, 1.1, 1.1.1 (com ou sem ponto final)
    tokens = [(m.start(), m.group(1), m.end()) for m in re.finditer(r"(?<![\w/\.,ºª°\-])(\d{1,3}(?:\.\d{1,3})*)(?:[\.\)]\s*|\s+)(?=[A-ZÀ-Ú“\"(‘'])", txt)]
    aceitos, atual = [], None
    for pos, lab, fim in tokens:
        try:
            p = [int(x) for x in lab.split(".")]
        except ValueError:
            continue
        if atual is None:
            if p == [1]:
                aceitos.append((pos, lab, fim)); atual = p
        elif tuple(p) in sucessores(atual):
            aceitos.append((pos, lab, fim)); atual = p
    if len(aceitos) >= 3:
        itens = []
        for k, (pos, lab, fim) in enumerate(aceitos):
            ate = aceitos[k + 1][0] if k + 1 < len(aceitos) else len(txt)
            itens.append((lab, txt[fim:ate].strip()))
        return itens
    # letras a) b) c)
    toks = [(m.start(), m.group(1), m.end()) for m in re.finditer(r"(?<![\w])([a-z])\)\s+(?=[A-ZÀ-Ú“\"(])", txt)]
    ac, esp = [], "a"
    for pos, lab, fim in toks:
        if lab == esp:
            ac.append((pos, lab, fim)); esp = chr(ord(esp) + 1)
    if len(ac) >= 3:
        return [(lab, txt[fim:(ac[k + 1][0] if k + 1 < len(ac) else len(txt))].strip()) for k, (pos, lab, fim) in enumerate(ac)]
    return [("", txt)]


def frases(txt: str):
    partes, ini = [], 0
    for m in re.finditer(r"[\.\?!]\s+(?:[a-z]\)\s+)?(?=[A-ZÀ-Ú“\"(0-9‘'])", txt):
        antes = txt[ini:m.start() + 1]
        ult = re.findall(r"[A-Za-zÀ-ú§ºª]+\.?$", antes)
        palavra = norm(ult[-1]).lower().rstrip(".") if ult else ""
        if palavra in ABREV or re.search(r"\d\.$", antes) and re.match(r"\d", txt[m.end():m.end() + 1]):
            continue
        partes.append(re.sub(r"^[a-z]\)\s+", "", antes.strip())); ini = m.end()
    resto = re.sub(r"^[a-z]\)\s+", "", txt[ini:].strip())
    if resto:
        partes.append(resto)
    return [p for p in partes if p]


# Cortes manuais (edital continua com outro assunto depois do último item): (pasta, disciplina) -> regra
OVERRIDES = {
    ("2018 - DPE-AM - Analista Jurídico", "DH"): {"ultimo_item": "11", "frases_no_ultimo": 1,
                                                  "motivo": "depois do item 11 (Educação em direitos) o texto segue com outra disciplina"},
    ("2022 - DPE-MT - Defensor Público", "EXEC"): {"ultimo_item": "10", "frases_no_ultimo": 6,
                                                  "motivo": "depois da 6ª frase do item 10 (Regras de Mandela) o texto segue com Grupo III, Direito Constitucional"},
}


def metadados():
    d = {}
    if INVENTARIO.exists():
        with open(INVENTARIO, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter=";"):
                d[r["arquivo_local"].replace("\\", "/")] = r
    return d


def processar(pasta: Path, alvo: str, meta: dict, dividir=None):
    dividir = dividir or dividir_itens
    linhas = texto_pdf(pasta / "1. edital.pdf")
    todas = secoes(linhas)
    modo = "layout"
    pats = [re.compile(p) for p in ALVOS[alvo]]
    melhores = {}   # nome do título -> (tamanho, corpo)
    for nome, corpo in todas:
        if any(p.search(nome) for p in pats):
            tam = len(" ".join(corpo))
            if tam > melhores.get(nome, (0, None))[0]:
                melhores[nome] = (tam, corpo)
    if not any(v[0] >= 600 for v in melhores.values()):      # editais em duas colunas: tentar leitura sem layout
        linhas = texto_pdf(pasta / "1. edital.pdf", layout=False)
        melhores = {}
        for nome, corpo in secoes(linhas):
            if any(p.search(nome) for p in pats):
                tam = len(" ".join(corpo))
                if tam > melhores.get(nome, (0, None))[0]:
                    melhores[nome] = (tam, corpo)
        modo = "sem layout (duas colunas?)"
    res = []
    for nome, (tam, corpo) in melhores.items():
        if tam < 600:
            continue
        if alvo == "DH" and nome != "DIREITOS HUMANOS" and not re.search(r"VULNER|ANTIDISC|GRUPOS|ENFASE|HUMANISTICA|ACESSO A JUSTICA", nome):
            continue   # ex.: linha de tabela de títulos ("Direitos humanos, com duração mínima de um ano")
        avisos = []
        txt = juntar(corpo, avisos)
        itens = []
        for lab, t in dividir(txt):
            itens.append({"item": lab, "frases": [f for f in frases(t) if len(re.sub(r"[\d\.\s]", "", f)) >= 3]})
        corte = OVERRIDES.get((pasta.name, alvo))
        if corte:      # corte manual: o edital continua com outro assunto depois do último item do programa
            lim = []
            for it in itens:
                lim.append(it)
                if it["item"] == corte["ultimo_item"]:
                    it["frases"] = it["frases"][:corte["frases_no_ultimo"]]
                    break
            itens = lim
            avisos.append("corte manual: " + corte["motivo"])
        res.append({"titulo_no_edital": nome, "caracteres": len(txt), "avisos": avisos[:30], "itens": itens})
    rel = f"provas/{pasta.name}/1. edital.pdf"
    m = meta.get(rel, {})
    return {"pasta": pasta.name, "banca": m.get("banca", "?"), "disciplina": alvo, "modo_leitura": modo, "secoes": res}


# ---------------------------------------------------------------- vindo do antigo script 50
def dividir_itens_tolerante(txt: str):
    """Como `dividir_itens`, mas aceita também o mesmo número de novo (item repetido) e o salto de um número (item pulado)."""
    tokens = [(mt.start(), mt.group(1), mt.end()) for mt in re.finditer(
        r"(?<![\w/\.,ºª°\-])(\d{1,3}(?:\.\d{1,3})*)(?:[\.\)]\s*|\s+)(?=[A-ZÀ-Ú“\"(‘'])", txt)]
    aceitos, atual = [], None
    for pos, lab, fim in tokens:
        try:
            p = [int(x) for x in lab.split(".")]
        except ValueError:
            continue
        if atual is None:
            if p == [1]:
                aceitos.append((pos, lab, fim)); atual = p
        elif (tuple(p) in sucessores(atual) or p == atual
              or (len(p) == 1 and len(atual) == 1 and p[0] == atual[0] + 2)
              or (len(p) == 1 and len(atual) > 1 and p[0] in (atual[0] + 1, atual[0] + 2))):
            aceitos.append((pos, lab, fim)); atual = p
    if len(aceitos) >= 3:
        return [(lab, txt[fim:(aceitos[k + 1][0] if k + 1 < len(aceitos) else len(txt))].strip())
                for k, (pos, lab, fim) in enumerate(aceitos)]
    return dividir_itens(txt)       # sem numeração: letras a) b) c) ou bloco único


def compacto(s: str) -> str:
    return re.sub(r"[\s\-–]+", "", s)


def texto_bruto(pdf: Path) -> str:
    """Texto do PDF sem cabeçalho/rodapé repetido e sem espaços nem hífens (para conferir frase por frase)."""
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True).stdout.decode("utf-8", "replace")
    todas = out.splitlines()
    rep = {s for s, n in collections.Counter(l.strip() for l in todas if l.strip()).items() if n >= 6 and len(s) < 120}
    linhas = [l for l in todas if not re.fullmatch(r"\s*\d{1,3}\s*", l) and l.strip() not in rep
              and not re.fullmatch(r"\s*P[áa]gina\s+\d+\s*(de\s*\d+)?\s*", l, re.I)]
    return compacto(" ".join(linhas))


def listar_disciplinas(pdf: Path, minimo_caracteres: int = 300):
    """Todos os títulos de disciplina do PDF (A-5): [{titulo_no_edital, caracteres, codigo, no_programa}], do maior para o menor trecho.
    `codigo` é a sigla de `ALVOS` quando o título é de uma das disciplinas do catálogo; senão None (disciplina fora do catálogo,
    como Informática, Língua Portuguesa ou Raciocínio Lógico). `no_programa` diz se o título está na região do conteúdo programático:
    entre o último "CONTEÚDO PROGRAMÁTICO" antes da primeira disciplina do catálogo e o primeiro ANEXO depois dela (o restante é corpo
    do edital: inscrições, avisos, política de privacidade). Tenta a leitura com layout e, se achar pouco, sem layout (duas colunas)."""
    pats = {c: [re.compile(p) for p in ps] for c, ps in ALVOS.items()}

    def varrer(layout):
        linhas = texto_pdf(pdf, layout=layout)
        marcas = []
        for i, l in enumerate(linhas):
            t = e_titulo(l, linhas[i - 1] if i else "")
            if t:
                marcas.append((i, t[0], t[1]))
        return linhas, marcas

    def codigo_de(nome):
        return next((c for c, ps in pats.items() if any(p.search(nome) for p in ps)), None)

    linhas, marcas = varrer(True)
    if not any(len(" ".join(linhas[i + 1:(marcas[k + 1][0] if k + 1 < len(marcas) else len(linhas))])) >= 600
               for k, (i, n, r) in enumerate(marcas)):
        linhas, marcas = varrer(False)
    primeiro_alvo = next((i for i, n, r in marcas if codigo_de(n)), None)
    inicio, fim = 0, len(linhas)
    if primeiro_alvo is not None:
        cps = [i for i, l in enumerate(linhas) if "CONTEUDO PROGRAMATICO" in norm(l) and i <= primeiro_alvo]
        inicio = cps[-1] if cps else 0
        fim = next((i for i, n, r in marcas if n == "ANEXO" and i > primeiro_alvo), len(linhas))
    melhor, dentro = {}, {}
    for k, (i, nome, resto) in enumerate(marcas):
        if nome in ("TABELA", "ANEXO"):
            continue
        ate = marcas[k + 1][0] if k + 1 < len(marcas) else len(linhas)
        tam = len(" ".join(([resto] if resto else []) + linhas[i + 1:ate]))
        if tam > melhor.get(nome, 0):
            melhor[nome] = tam
        dentro[nome] = dentro.get(nome, False) or (inicio <= i < fim)
    out = []
    for nome, tam in melhor.items():
        if tam >= minimo_caracteres:
            out.append({"titulo_no_edital": nome, "caracteres": tam, "codigo": codigo_de(nome), "no_programa": dentro[nome]})
    return sorted(out, key=lambda d: -d["caracteres"])
