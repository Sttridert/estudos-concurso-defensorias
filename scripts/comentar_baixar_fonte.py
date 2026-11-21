#!/usr/bin/env python3
"""Grupo E: baixa uma página OFICIAL (ex.: planalto.gov.br) e grava o texto puro em dados/fontes/<nome>.txt, com URL e data na
primeira linha. Só copia o que o site entrega, sem resumir. Uso: python -I scripts/comentar_baixar_fonte.py URL NOME"""
import datetime, html, re, subprocess, sys
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


class T(HTMLParser):
    def __init__(self):
        super().__init__(); self.p = []; self.skip = 0
    def handle_starttag(self, t, a):
        if t in ("script", "style"): self.skip += 1
        if t in ("p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4"): self.p.append("\n")
    def handle_endtag(self, t):
        if t in ("script", "style"): self.skip -= 1
    def handle_data(self, d):
        if not self.skip: self.p.append(d)


def main():
    url, nome = sys.argv[1], sys.argv[2]
    if not re.match(r"^https://[\w.-]*(gov\.br|jus\.br|leg\.br)/", url):
        sys.exit("só aceito site oficial (gov.br, jus.br, leg.br)")
    raw = subprocess.run(["curl", "-sL", "-4", "--max-time", "90", "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36", url], capture_output=True, check=True).stdout
    try: txt = raw.decode("utf-8")
    except UnicodeDecodeError: txt = raw.decode("cp1252", "replace")
    t = T(); t.feed(txt)
    corpo = html.unescape("".join(t.p)).replace("\xa0", " ")
    corpo = "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in corpo.split("\n"))
    corpo = re.sub(r"\n{2,}", "\n", corpo).strip()
    saida = RAIZ / "dados" / "fontes" / f"{nome}.txt"
    saida.write_text(f"FONTE: {url} | consultado em {datetime.date.today().isoformat()} | texto copiado da página oficial\n{corpo}\n", encoding="utf-8")
    print(saida.name, len(corpo), "caracteres")


if __name__ == "__main__":
    main()
