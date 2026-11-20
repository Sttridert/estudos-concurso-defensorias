"""Le os JSON baixados do TEC (um por prova) e gera fonte_tec/tec_<slug>.json com campos limpos."""
import json, re, sys, pathlib
B = pathlib.Path(__file__).resolve().parent.parent / "banco" / "fonte_tec"
def parse(txt):
    m = re.match(r"Quest[ãa]o (\d+) de (\d+)\s*\nMat[ée]ria:\s*(.*?)\nAssunto:\s*\n?(.*?)\n(?:\s*\n)*\s*(?:\d+\s*\n\s*)?(?:#(\d+)\s+)?(.*?)\n", txt, flags=re.S)
    n = int(re.match(r"Quest[ãa]o (\d+)", txt).group(1))
    mat = (re.search(r"Mat[ée]ria:\s*(.*)", txt) or [None, ""])[1].strip()
    ass = (re.search(r"Assunto:\s*\n?(.*)", txt) or [None, ""])[1].strip()
    tid = (re.search(r"#(\d{4,})", txt) or [None, None])[1]
    # corpo: depois da linha do #id
    corpo = txt.split("\n", 1)[1]
    i = re.search(r"#\d{4,}[^\n]*\n", corpo)
    corpo = corpo[i.end():] if i else corpo
    # alternativas: linhas "A\n\t texto"
    partes = re.split(r"\n\s*\n\s*([A-E])\n\t", "\n\n" + corpo.strip("\n") , flags=re.S)
    # partes: [enunciado, 'A', textoA, 'B', textoB, ...]
    enun = partes[0].strip()
    alts = {}
    for k in range(1, len(partes) - 1, 2):
        alts[partes[k]] = re.sub(r"\s+", " ", partes[k + 1]).strip()
    return n, {"tec_id": tid, "materia": mat, "assunto": ass, "enunciado": re.sub(r"[ \t]+\n", "\n", enun).strip(), "alternativas": alts}
if __name__ == "__main__":
    nome = sys.argv[1]
    d = json.loads((B / "recebidos" / f"tec_{nome}_questoes.json").read_text(encoding="utf-8"))
    out = {}
    for k, v in d.items():
        n, r = parse(v)
        out[n] = r
    (B / f"tec_{nome}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ruins = [n for n, r in out.items() if len(r["alternativas"]) != 5]
    print(nome, len(out), "questoes; sem 5 alternativas:", ruins)
