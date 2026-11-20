"""Biblioteca do grupo A (Coletar): texto de PDFs de provas, com OCR.

Um só lugar para ler texto de PDF (direto ou por OCR). Antes havia a mesma função de OCR copiada em cinco scripts
(01, 01b, 01c, 01d e 26, hoje em legado/ exceto o 26, que usa esta biblioteca).

Funções:
  texto_direto(pdf)           texto embutido no PDF (pdftotext -layout)
  ocr(pdf, ...)               OCR página a página (pdftoppm 300 dpi + Tesseract em português)
  extrair(pdf, destino, ...)  reaproveita o texto já extraído; senão tenta o texto direto e cai no OCR
  refazer_ocr(pdf, destino)   refaz o OCR sobre um texto já gravado, guardando o original como `.embutido.txt`
  sinais_texto(texto)         sinais baratos de qualidade do texto (usados pelo relatório de integridade)

O texto lido por OCR começa com a linha `=====OCR=====`; é assim que o restante do projeto sabe que o caderno veio de OCR.
"""
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

MARCA_OCR = "=====OCR====="
MINIMO_TEXTO_DIRETO = 500   # abaixo disso o PDF é tratado como digitalizado (sem camada de texto)


def texto_direto(pdf):
    r = subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(pdf), "-"], capture_output=True)
    return r.stdout.decode("utf-8", "replace")


def ocr(pdf, dpi=300, lingua="por", psm="4", tessdata=None):
    """OCR com Tesseract. Devolve o texto das páginas separado por quebra de linha.
    `tessdata`: pasta de modelos alternativa (ex.: tessdata_best). Teste de 20/11/2026 (DPE-ES 2023, contra o texto limpo do TEC):
    o modelo `best` acertou só 0,3 a 1,1% mais palavras e levou 2,4 vezes mais tempo; `psm` 4 e 6 deram o mesmo resultado."""
    tmp = Path(tempfile.mkdtemp())
    try:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(tmp / "p")], check=True)
        partes = []
        for img in sorted(tmp.glob("p-*.png")):
            cmd = ["tesseract", str(img), "-", "-l", lingua, "--psm", psm] + (["--tessdata-dir", str(tessdata)] if tessdata else [])
            r = subprocess.run(cmd, capture_output=True)
            partes.append(r.stdout.decode("utf-8", "replace"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "\n".join(partes)


def veio_de_ocr(texto):
    return texto.lstrip().startswith(MARCA_OCR)


def extrair(pdf, destino, forcar_ocr=False):
    """Reaproveita o texto já extraído (destino) quando existir. Retorna (texto, lido_por_ocr).
    Sem texto gravado: tenta o texto direto; se vier pouco (ou `forcar_ocr`), usa OCR. Grava em `destino`."""
    destino = Path(destino)
    if destino.exists() and destino.stat().st_size > MINIMO_TEXTO_DIRETO:
        t = destino.read_text(encoding="utf-8")
        return t, bool(re.search(MARCA_OCR, t[:20]))
    t = texto_direto(pdf)
    por_ocr = False
    if forcar_ocr or len(t.strip()) < MINIMO_TEXTO_DIRETO:
        print("  OCR (sem texto no PDF):", Path(pdf).name, flush=True)
        t = MARCA_OCR + "\n" + ocr(pdf)
        por_ocr = True
    destino.write_text(t, encoding="utf-8")
    return t, por_ocr


def refazer_ocr(pdf, destino):
    """Refaz o OCR de um caderno cujo texto embutido é ruim. Guarda o original como `<destino>.embutido.txt` (uma vez só)."""
    destino = Path(destino)
    bak = destino.with_suffix(".embutido.txt")
    if destino.exists() and not bak.exists():
        shutil.copy(destino, bak)
    t = MARCA_OCR + "\n" + ocr(pdf)
    destino.write_text(t, encoding="utf-8")
    return t


# ---------- sinais de qualidade do texto (sem dicionário externo) ----------
def _sem_acento(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


# palavras funcionais muito frequentes em português: proporção alta indica texto legível
_FUNCIONAIS = {"de", "da", "do", "das", "dos", "a", "o", "as", "os", "e", "em", "no", "na", "nos", "nas", "que", "para", "por",
               "com", "um", "uma", "ao", "se", "ou", "nao", "sao", "foi", "ser", "como", "mais", "sua", "seu", "pela", "pelo"}


def sinais_texto(texto):
    """Sinais baratos de qualidade, para apontar onde olhar (não provam que o texto está certo):
    proporção de palavras funcionais do português, proporção de caracteres estranhos e de palavras de uma letra."""
    palavras = re.findall(r"[A-Za-zÀ-ÿ]+", texto)
    n = len(palavras)
    if n == 0:
        return {"palavras": 0, "funcionais": 0.0, "estranhos": 1.0, "uma_letra": 0.0}
    funcionais = sum(1 for p in palavras if _sem_acento(p) in _FUNCIONAIS) / n
    uma_letra = sum(1 for p in palavras if len(p) == 1 and p.lower() not in "aeo") / n
    total = max(len(texto), 1)
    estranhos = sum(1 for c in texto if c in "|¢§¬£¥©®™�") / total
    return {"palavras": n, "funcionais": round(funcionais, 3), "estranhos": round(estranhos, 4), "uma_letra": round(uma_letra, 3)}
