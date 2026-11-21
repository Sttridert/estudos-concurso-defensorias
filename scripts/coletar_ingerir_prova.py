"""Ingestao de provas novas no banco permanente (estudos.db). Substitui o antigo 02/03 (que escrevia no banco antigo).
Uso:  python -I scripts/coletar_ingerir_prova.py dados/coleta/provas_novas_manifesto.json [--so NOME] [--simular]
Para cada prova do manifesto: extrai o texto do caderno (direto; OCR se nao houver texto), le o gabarito (txt da FCC ou PDF da
publicacao), separa as questoes (enunciado + alternativas A a E), atribui a disciplina pelo cabecalho do caderno e grava
provas/questoes. Nao classifica pontos nem escreve comentarios (isso e outra etapa). Idempotente: prova que ja existe e pulada.
Cabecalho combinado ("Direito Civil e Direito Processual Civil") vai para a primeira disciplina e a questao fica marcada
em `motivo_situacao` para separar na classificacao da disciplina.
Manifesto (JSON): lista de {nome, ano, instituicao, uf, banca, carreira, cargo, n_questoes, tipo_caderno, caderno, gabarito,
gabarito_formato ('txt'|'pdf'), gabarito_status, gabarito_origem, observacoes, grupo_legado} com caminhos relativos a raiz.
"""
import json, re, sqlite3, subprocess, sys, tempfile, shutil, unicodedata, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "banco" / "estudos.db"
TEXTO = RAIZ / "banco" / "fontes" / "texto-bruto"


def sem_acento(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


# ---------- extracao de texto (biblioteca do grupo A) ----------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_texto_prova import texto_direto, ocr, extrair  # noqa: E402,F401
from lib_conferencia import situacao_do_status  # noqa: E402


# ---------- gabarito ----------
def gabarito_txt(t, tipo):
    """O txt da FCC traz um bloco por 'Tipo gabarito N' (um por tipo de caderno). Pega so o bloco do tipo do caderno da prova.
    Sem marcador de tipo, usa o texto todo."""
    partes = re.split(r"Tipo gabarito\s*(\d+)", t)
    if len(partes) > 1:
        blocos = {int(partes[i]): partes[i + 1] for i in range(1, len(partes) - 1, 2)}
        if tipo not in blocos:
            sys.exit(f"Gabarito sem bloco do tipo {tipo} (tem {sorted(blocos)}).")
        t = blocos[tipo]
    return {int(n): l for n, l in re.findall(r"(\d{3})-([A-E*])", t)}


def gabarito_pdf(pdf):
    t = texto_direto(pdf)
    g = {}
    anuladas = set()
    for m in re.finditer(r"^\s*(\d{1,3})\s+([A-E]|ANULAD\w*|\*)\b[ \t]*(.*)$", t, re.M):
        n = int(m.group(1))
        g[n] = m.group(2)[0] if m.group(2) in "ABCDE" else "*"
        if "anulad" in m.group(3).lower() or g[n] == "*":
            anuladas.add(n)
    return g, anuladas


# ---------- cabecalhos de disciplina ----------
PREFIXOS = ("direito", "direitos", "lingua", "legislacao", "nocoes", "conhecimentos juridicos", "raciocinio", "matematica", "informatica",
            "administracao", "contabilidade", "atualidades", "principios", "etica", "portugues", "ingles", "geografia", "historia", "arquivologia",
            "gestao", "economia", "estatistica", "pedagogia", "conhecimentos de", "conhecimentos sobre", "politicas")
PADRAO_MAP = [  # (regex sobre texto normalizado, disciplina)
    (r"^lingua portuguesa", "Língua Portuguesa"),
    (r"^conhecimentos juridicos e institucionais", "Princípios e Atribuições Institucionais da Defensoria"),
    (r"^principios e atribuicoes institucionais", "Princípios e Atribuições Institucionais da Defensoria"),
    (r"^direitos dos idosos", "Direito do Idoso e da Pessoa com Deficiência"),
    (r"^direito da crianca", "Direito da Criança e do Adolescente"),
    (r"^direitos humanos", "Direitos Humanos"),
    (r"^direito civil e direito processual civil", "Direito Civil"),
    (r"^direito penal e direito processual penal", "Direito Penal"),
    (r"^direito constitucional", "Direito Constitucional"),
    (r"^direito administrativo", "Direito Administrativo"),
    (r"^direito processual civil", "Direito Processual Civil"),
    (r"^direito processual penal", "Direito Processual Penal"),
    (r"^direito civil", "Direito Civil"),
    (r"^direito penal", "Direito Penal"),
    (r"^direito tributario", "Direito Tributário"),
    (r"^legislacao institucional", "Legislação Institucional"),
    (r"^nocoes de informatica", "Noções de Informática"),
]


def cabecalho(linha, ocr=False):
    """Se a linha e um cabecalho de disciplina (centralizado, curto), devolve (texto_limpo, disciplina, combinado)."""
    if not ocr and not linha.startswith(" " * 8):
        return None  # no texto direto o cabecalho e centralizado; no OCR a indentacao se perde
    s = re.split(r"\s{3,}", linha.strip())[0].strip()
    if ocr and not (re.match(r"^[A-ZÀ-Ú]", s) and len(s) <= 80):
        return None
    if not (4 <= len(s) <= 110) or re.search(r"[.:;(]$|\d", s) or s.endswith(","):
        return None
    n = sem_acento(s)
    if not n.startswith(PREFIXOS):
        return None
    for rx, disc in PADRAO_MAP:
        if re.search(rx, n):
            combinado = bool(re.search(r"\be\b|,", n.replace("direitos humanos", "dh"))) and disc not in ("Direitos Humanos", "Língua Portuguesa") and \
                not n.startswith(("conhecimentos juridicos e institucionais", "direitos dos idosos", "direito da crianca"))
            return s, disc, combinado
    return s, s, False  # disciplina nova: usa o proprio nome do cabecalho


RUIDO = re.compile(r"^\s*(Caderno de Prova|Funda[cç][aã]o Carlos Chagas|\d{6}-PG\d+|Direitos Reservados|CONHECIMENTOS (GERAIS|ESPEC)|(DPEAM|MPPI|TJCE)\S*)", re.I)
RODAPE = re.compile(r"\s{2,}(DPEAM|MPPI|TJCE)\S.*$|\s+(DPEAM|MPPI|TJCE)-\S.*$")


def limpa_linha(l):
    return RODAPE.sub("", l).rstrip()


def limpar_linhas(linhas):
    return [limpa_linha(l) for l in linhas if not RUIDO.search(l)]


# ---------- parser de questoes ----------
def separar(texto, n_esperado):
    """Devolve lista de dicts {numero, disciplina, combinado, bloco(str)} e avisos."""
    linhas = texto.splitlines()
    fim = len(linhas)
    for i, l in enumerate(linhas):
        if re.match(r"^\s*(PROVA\s+)?DISCURSIVA", l):
            fim = i
            break
    linhas = linhas[:fim]
    ocr = texto.lstrip().startswith("=====OCR=====")
    disc, comb = None, False
    marcadas = []  # (linha, disciplina, combinado)
    for l in linhas:
        if RUIDO.search(l):
            continue
        l = limpa_linha(l)
        h = cabecalho(l, ocr)
        if h:
            disc, comb = h[1], h[2]
            continue  # cabecalho nao entra no texto
        marcadas.append((l, disc, comb))
    esperado = 1
    blocos = []
    for l, d, c in marcadas:
        m = re.match(r"^\s{0,14}(\d{1,3})\s*[.)](?:\s+(\S.*))?$", l)
        if m and int(m.group(1)) == esperado:
            blocos.append({"numero": esperado, "disciplina": d, "combinado": c, "linhas": [m.group(2) or ""], "discs": [(d, c)]})
            esperado += 1
        elif blocos:
            blocos[-1]["linhas"].append(l)
            blocos[-1]["discs"].append((d, c))
    avisos = []
    if blocos and len(blocos) < n_esperado:
        # numeros perdidos (comum em OCR de paginas em duas colunas): divide o ultimo bloco pela estrutura (A) a (E)
        ult = blocos[-1]
        novos = dividir_por_estrutura(ult["linhas"], ult["discs"])
        if novos and len(blocos) - 1 + len(novos) == n_esperado:
            blocos = blocos[:-1]
            for k, (ls, dc) in enumerate(novos):
                blocos.append({"numero": ult["numero"] + k, "disciplina": dc[0], "combinado": dc[1], "linhas": ls, "discs": []})
            esperado = n_esperado + 1
            avisos.append(f"a partir da questao {ult['numero']} os numeros foram atribuidos pela ordem das alternativas (numeros perdidos no OCR); conferir")
    if esperado - 1 != n_esperado:
        avisos.append(f"achei {esperado - 1} questoes, esperado {n_esperado}")
    return blocos, avisos


def dividir_por_estrutura(linhas, discs):
    """Divide um bloco com varias questoes procurando as sequencias (A) a (E). Devolve [(linhas_da_questao, (disciplina, combinado))]."""
    n = len(linhas)
    achadas, pos = [], 0
    while True:
        ia = next((k for k in range(pos, n) if re.match(r"^\s*\(A\)\s", linhas[k])), None)
        if ia is None:
            break
        marcas, k = [ia], ia
        for letra in "BCDE":
            kk = next((j for j in range(k + 1, n) if re.match(r"^\s*\(" + letra + r"\)\s", linhas[j])), None)
            if kk is None:
                return None
            marcas.append(kk)
            k = kk
        fim, j = marcas[4], marcas[4] + 1
        while j < n and linhas[j].strip():
            fim, j = j, j + 1
        achadas.append((ia, fim))
        pos = fim + 1
    saida, inicio = [], 0
    for ia, fim in achadas:
        enunc = [l for l in linhas[inicio:ia] if l.strip() and not re.match(r"^\s*\d{1,3}\s*[.)]?\s*$", l)]
        ls = enunc + linhas[ia:fim + 1]
        dc = discs[ia] if ia < len(discs) else (None, False)
        saida.append((ls, dc))
        inicio = fim + 1
    return saida


def partir_alternativas(linhas):
    """Separa enunciado e alternativas A a E. Devolve (enunciado, [a..e], ok, texto_antes_do_cabecalho_proxima)."""
    limpas = limpar_linhas(linhas)
    texto = "\n".join(limpas)
    texto = re.sub(r"([a-zà-ú])-[ \t]*\n\s*([a-zà-ú])", r"\1\2", texto)  # palavra hifenizada na quebra de linha
    pos, ini = {}, 0
    for letra in "ABCDE":
        m = re.compile(r"(?:(?<=\s)|^)\(" + letra + r"\)\s").search(texto, ini)
        if not m:
            break
        pos[letra] = (m.start(), m.end())
        ini = m.end()
    if len(pos) < 5:
        return re.sub(r"\s+", " ", texto).strip(), ["", "", "", "", ""], False
    enun = texto[:pos["A"][0]]
    alts = []
    for i, letra in enumerate("ABCDE"):
        fim = pos["ABCDE"[i + 1]][0] if i < 4 else len(texto)
        alt = texto[pos[letra][1]:fim]
        if letra == "E":  # corta o que sobrou depois da E (texto de apoio da proxima questao)
            partes = re.split(r"\n[ \t]*\n", alt)
            alt = partes[0]
            for extra in partes[1:]:
                if re.match(r"\s*[a-zà-ú]", extra):  # continuacao de frase apos quebra de pagina
                    alt += " " + extra
                else:
                    break
        alts.append(re.sub(r"\s+", " ", alt).strip())
    return re.sub(r"\s+", " ", enun).strip(), alts, True


# ---------- banco ----------
def id_disciplina(con, nome):
    r = con.execute("select id from disciplinas where nome=?", (nome,)).fetchone()
    if r:
        return r[0]
    con.execute("insert into disciplinas(nome) values(?)", (nome,))
    print("  disciplina nova criada:", nome)
    return con.execute("select id from disciplinas where nome=?", (nome,)).fetchone()[0]


def ingerir(con, p, simular=False):
    nome = p["nome"]
    if con.execute("select 1 from provas where nome=?", (nome,)).fetchone():
        print(f"[{nome}] ja existe no banco; pulei.")
        return
    caderno = RAIZ / p["caderno"]
    texto, por_ocr = extrair(caderno, TEXTO / f"{nome} - 2. caderno de prova.txt", p.get("forcar_ocr", False))
    if p.get("gabarito_manual"):  # transcricao manual (quando a camada de texto do PDF do gabarito e falha)
        gab, anul = {i + 1: l for i, l in enumerate(p["gabarito_manual"])}, set()
    elif p["gabarito_formato"] == "txt":
        gab = gabarito_txt((RAIZ / p["gabarito"]).read_text(encoding="utf-8", errors="replace"), p.get("tipo_caderno") or 1)
        anul = {n for n, l in gab.items() if l == "*"}
    else:
        gab, anul = gabarito_pdf(RAIZ / p["gabarito"])
    blocos, avisos = separar(texto, p["n_questoes"])
    print(f"[{nome}] questoes lidas: {len(blocos)} | gabarito: {len(gab)} respostas | OCR: {por_ocr}")
    for a in avisos:
        print("  AVISO:", a)
    por_disc, problemas = {}, []
    linhas_q = []
    for b in blocos:
        enun, alts, ok = partir_alternativas(b["linhas"])
        n = b["numero"]
        sit, motivo = "valida", None
        if n in anul:
            sit, motivo = "anulada", "gabarito da fonte marca anulada"
        elif not ok or not all(alts):
            sit, motivo = "revisar_texto", "alternativas incompletas na extracao"
            problemas.append(n)
        elif por_ocr:
            sit, motivo = "revisar_texto", "texto lido por OCR; conferir"
        if b["combinado"] and not motivo:
            motivo = f"cabecalho combinado: separar a disciplina na classificacao (atribuida a {b['disciplina']})"
        elif b["combinado"]:
            motivo += f"; cabecalho combinado (atribuida a {b['disciplina']})"
        if n not in gab:
            problemas.append(n)
        por_disc[b["disciplina"]] = por_disc.get(b["disciplina"], 0) + 1
        linhas_q.append((n, b["disciplina"], enun, alts, gab.get(n), sit, motivo, "\n".join(b["linhas"])))
    print("  por disciplina:", por_disc)
    if problemas:
        print("  questoes com problema (numero):", sorted(set(problemas)))
    if simular:
        return
    cur = con.execute("""insert into provas(nome,ano,banca,carreira,instituicao,uf,cargo,n_questoes_esperado,tipo_caderno,gabarito_tipo,gabarito_status,gabarito_origem,
        caderno_lido_por_ocr,banca_escreve,grupo_legado,arquivo_edital,arquivo_caderno,arquivo_gabarito,observacoes,gabarito_situacao) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (nome, p["ano"], p["banca"], p["carreira"], p["instituicao"], p["uf"], p["cargo"], p["n_questoes"], p.get("tipo_caderno"), p.get("tipo_caderno"),
                       p["gabarito_status"], p["gabarito_origem"], int(por_ocr), p.get("banca_escreve", "FCC (a confirmar)"), p.get("grupo_legado", "B"),
                       p.get("arquivo_edital", ""), p["caderno"], p["gabarito"], p.get("observacoes", ""),
                       p.get("gabarito_situacao") or situacao_do_status(p["gabarito_status"])))
    pid = cur.lastrowid
    for n, d, enun, alts, g, sit, motivo, bruto in linhas_q:
        con.execute("""insert into questoes(prova_id,numero,disciplina_id,disciplina_original,enunciado,alt_a,alt_b,alt_c,alt_d,alt_e,gabarito,situacao,motivo_situacao,texto_bruto,texto_fonte)
            values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (pid, n, id_disciplina(con, d), d, enun, *alts, g, sit, motivo, bruto, "pdftotext/OCR do caderno oficial"))
    con.execute("insert into log_alteracoes(quem,o_que) values('coletar_ingerir_prova', ?)", (f"prova {nome}: {len(linhas_q)} questoes",))
    con.commit()
    print(f"  gravada: prova id {pid}, {len(linhas_q)} questoes")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    manifesto = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    so = sys.argv[sys.argv.index("--so") + 1] if "--so" in sys.argv else None
    con = sqlite3.connect(DB)
    for p in manifesto:
        if so and so not in p["nome"]:
            continue
        ingerir(con, p, simular="--simular" in sys.argv)


if __name__ == "__main__":
    main()
