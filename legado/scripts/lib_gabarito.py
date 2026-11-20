"""Leitura de gabaritos FCC (varios formatos). Usado pela Fase 2."""
import re, pathlib, subprocess, os, tempfile

PT = r"C:\Users\paulo\AppData\Local\Programs\poppler-26.02.0\Library\bin\pdftotext.exe"


def pares(seg):
    """{num: letra} de um trecho; escolhe o formato que acha mais itens."""
    a = {}
    for m in re.finditer(r'(?<![\d/])([0-9DOl]{3})\s*-\s*([A-E])\b', seg):
        n = m.group(1).replace('D', '0').replace('O', '0').replace('l', '1')
        if n.isdigit():
            a.setdefault(int(n), m.group(2))
    b = {}
    for m in re.finditer(r'^\s*(\d{1,3})\s*([A-E])\b(?=\s|$)', seg, flags=re.M):
        b.setdefault(int(m.group(1)), m.group(2))
    return a if len(a) >= len(b) else b


def gabaritos_por_tipo_texto(texto):
    """{tipo: {num: letra}} a partir do texto (formatos de 1 tipo por arquivo)."""
    marcas = list(re.finditer(r'Tipo(?: de)? [Gg]abarito:?\s*(\d)', texto))
    if not marcas:
        m = re.search(r'Tipo\s*(\d)\s*Folha', texto)
        return {int(m.group(1)) if m else 0: pares(texto)}
    out = {}
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        d = pares(texto[m.end():fim])
        for k, v in d.items():
            out.setdefault(int(m.group(1)), {}).setdefault(k, v)
    return out


def gabaritos_bbox(pdf):
    """{tipo: {num: letra}} usando coordenadas (resolve varios tipos lado a lado)."""
    tmp = tempfile.mktemp(suffix=".html")
    subprocess.run([PT, "-bbox", str(pdf), tmp], check=True)
    t = open(tmp, encoding="utf-8").read()
    os.remove(tmp)
    hs, items = [], []
    for pi, p in enumerate(re.split(r'<page ', t)[1:]):
        words = [(float(x), float(y), w) for x, y, w in re.findall(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="[\d.]+">([^<]*)</word>', p)]
        for i, (x, y, w) in enumerate(words):
            if w == 'Tipo' and i + 2 < len(words) and words[i + 1][2].lower().startswith('gabarito') and words[i + 2][2].isdigit():
                hs.append((pi, y, int(words[i + 2][2])))
            m = re.fullmatch(r'(\d{3})-?([A-E])?', w)
            if m:
                letra = m.group(2)
                if not letra and i + 2 < len(words) and words[i + 1][2] == '-' and re.fullmatch('[A-E]', words[i + 2][2]):
                    letra = words[i + 2][2]
                if not letra and i + 1 < len(words) and re.fullmatch(r'-[A-E]', words[i + 1][2]):
                    letra = words[i + 1][2][1]
                if letra:
                    items.append((pi, y, int(m.group(1)), letra))
    hs.sort()
    res = {}
    for (pi, y, n, l) in items:
        cand = [h for h in hs if (h[0], h[1]) <= (pi, y + 1)]
        res.setdefault(cand[-1][2] if cand else 0, {}).setdefault(n, l)
    return res


def gabaritos(pdf, texto):
    """Escolhe o melhor metodo: bbox se houver >1 tipo no PDF, senao texto."""
    if len(re.findall(r'Tipo gabarito', texto)) > 1:
        return gabaritos_bbox(pdf)
    return gabaritos_por_tipo_texto(texto)


if __name__ == "__main__":
    base = pathlib.Path(__file__).resolve().parent.parent / "banco" / "texto-bruto"
    pr = pathlib.Path(__file__).resolve().parent.parent / "provas"
    for f in sorted(base.glob("*3. gabarito.txt")):
        t = f.read_text(encoding="utf-8")
        nome = f.name.replace(" - 3. gabarito.txt", "")
        g = gabaritos(pr / nome / "3. gabarito.pdf", t)
        cab = (base / f.name.replace("3. gabarito", "2. caderno de prova")).read_text(encoding="utf-8")
        tipo_cad = sorted(set(re.findall(r"Tipo\s*0*(\d)\b", cab[:6000])))
        print(nome[:46].ljust(46), {k: (len(v), min(v) if v else None, max(v) if v else None) for k, v in g.items()}, "cad:", tipo_cad)
