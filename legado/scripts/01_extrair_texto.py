# Fase 1: extrai texto dos PDFs (direto; OCR se nao houver texto). Uso: python 01_extrair_texto.py
import subprocess, pathlib, sys, tempfile, shutil, json
BASE = pathlib.Path(__file__).resolve().parent.parent
PROVAS = BASE / "provas"
OUT = BASE / "banco" / "texto-bruto"
OUT.mkdir(parents=True, exist_ok=True)
controle = []
def texto_direto(pdf):
    r = subprocess.run(["pdftotext","-enc","UTF-8","-layout",str(pdf),"-"],capture_output=True)
    return r.stdout.decode("utf-8","replace")
def ocr(pdf):
    tmp = pathlib.Path(tempfile.mkdtemp())
    subprocess.run(["pdftoppm","-r","300","-png",str(pdf),str(tmp/"p")],check=True)
    partes=[]
    for img in sorted(tmp.glob("p-*.png")):
        r = subprocess.run(["tesseract",str(img),"-","-l","por","--psm","4"],capture_output=True)
        partes.append(f"\n=====PAGINA {img.stem.split('-')[-1]}=====\n"+r.stdout.decode("utf-8","replace"))
    shutil.rmtree(tmp,ignore_errors=True)
    return "".join(partes)
for d in sorted(p for p in PROVAS.iterdir() if p.is_dir()):
    for pdf in sorted(d.glob("*.pdf")):
        dest = OUT / f"{d.name} - {pdf.stem}.txt"
        if dest.exists() and dest.stat().st_size > 200: continue
        t = texto_direto(pdf); modo="direto"
        if len(t.strip()) < 300:
            print("OCR:", d.name, pdf.name, flush=True); t = ocr(pdf); modo="ocr"
        dest.write_text(t, encoding="utf-8")
        controle.append({"prova":d.name,"arquivo":pdf.name,"modo":modo,"caracteres":len(t)})
        print(modo, len(t), d.name, pdf.name, flush=True)
(OUT.parent/"controle_extracao.json").write_text(json.dumps(controle,ensure_ascii=False,indent=1),encoding="utf-8")
print("FIM")
