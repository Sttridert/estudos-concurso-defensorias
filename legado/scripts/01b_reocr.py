# Refaz o OCR de cadernos cujo texto embutido e ruim. Guarda o original como .embutido.txt
import pathlib, shutil, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import importlib.util
spec = importlib.util.spec_from_file_location("ex", str(pathlib.Path(__file__).parent / "01_extrair_texto.py"))
BASE = pathlib.Path(__file__).resolve().parent.parent
import subprocess, tempfile
def ocr(pdf):
    tmp = pathlib.Path(tempfile.mkdtemp())
    subprocess.run(["pdftoppm","-r","300","-png",str(pdf),str(tmp/"p")],check=True)
    partes=[]
    for img in sorted(tmp.glob("p-*.png")):
        r = subprocess.run(["tesseract",str(img),"-","-l","por","--psm","4"],capture_output=True)
        partes.append(f"\n=====PAGINA {img.stem.split('-')[-1]}=====\n"+r.stdout.decode("utf-8","replace"))
    shutil.rmtree(tmp,ignore_errors=True)
    return "".join(partes)
for nome in ["2023 - DPE-ES - Defensor Público", "2025 - DPE-SP - Analista de Defensoria"]:
    dest = BASE/"banco"/"texto-bruto"/f"{nome} - 2. caderno de prova.txt"
    bak = dest.with_suffix(".embutido.txt")
    if not bak.exists(): shutil.copy(dest, bak)
    dest.write_text(ocr(BASE/"provas"/nome/"2. caderno de prova.pdf"), encoding="utf-8")
    print("ok", nome, flush=True)
print("FIM")
