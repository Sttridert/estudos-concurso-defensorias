"""Extrai texto de provas adicionadas depois (pasta em 'base de dados'): caderno por OCR (300 dpi, por), edital e gabarito por texto direto."""
import sys, pathlib, subprocess, tempfile, shutil
BASE = pathlib.Path(__file__).resolve().parent.parent
nome = sys.argv[1]
P = BASE / "provas" / nome
OUT = BASE / "banco" / "texto-bruto"
for arq in ("1. edital", "3. gabarito"):
    t = subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(P / (arq + ".pdf")), "-"], capture_output=True).stdout.decode("utf-8", "replace")
    (OUT / f"{nome} - {arq}.txt").write_text(t, encoding="utf-8")
tmp = pathlib.Path(tempfile.mkdtemp())
subprocess.run(["pdftoppm", "-r", "300", "-png", str(P / "2. caderno de prova.pdf"), str(tmp / "p")], check=True)
partes = []
for img in sorted(tmp.glob("p-*.png")):
    r = subprocess.run(["tesseract", str(img), "-", "-l", "por", "--psm", "4"], capture_output=True)
    partes.append(f"\n=====PAGINA {img.stem.split('-')[-1]}=====\n" + r.stdout.decode("utf-8", "replace"))
shutil.rmtree(tmp, ignore_errors=True)
(OUT / f"{nome} - 2. caderno de prova.txt").write_text("".join(partes), encoding="utf-8")
print("ok", nome)
