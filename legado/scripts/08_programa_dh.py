"""Fase 4: recorta o programa de Direitos Humanos de cada edital (texto bruto) para banco/programas_dh/<prova>.txt
Inicio: linha do cabecalho (achada a mao quando o formato foge do padrao). Fim: proximo titulo de disciplina.
"""
import re, pathlib
B = pathlib.Path(__file__).resolve().parent.parent / "banco"
OUT = B / "programas_dh"; OUT.mkdir(exist_ok=True)
INICIO = {  # linha (1-based) do cabecalho de DH no texto do edital
    "2021 - DPE-AM - Defensor Público": 1628, "2021 - DPE-GO - Defensor Público": 1667, "2021 - DPE-RR - Defensor Público": 2219,
    "2021 - DPE-SC - Defensor Público": 1465, "2022 - DPE-AP - Defensor Público": 2153, "2022 - DPE-MT - Defensor Público": 2306,
    "2025 - DPE-RS - Defensor Público": 2126, "2026 - DPE-MT - Defensor Público": 2308, "2026 - DPE-MA - Defensor Público": 2652,
}
FIXOS = {  # (inicio, fim) fixos
    "2022 - DPE-AM - Analista Jurídico": (1696, 1700), "2022 - DPE-CE - Defensor Público": (1559, 1565),
}
TITULO = re.compile(r"^\s*(?:[IVX]+\.\s*)?(Direito|Direitos|DIREITO|DIREITOS|Princ[íi]pios|PRINC[ÍI]PIOS|Filosofia|FILOSOFIA|Sociologia|SOCIOLOGIA|Criminologia|CRIMINOLOGIA|Execu[çc][ãa]o|Legisla[çc][ãa]o|LEGISLA|Hist[óo]ria|DEFENSORIA|Defensoria)\b[^.:;]{0,80}$")
def main():
    for f in sorted((B / "texto-bruto").glob("* - 1. edital.txt")):
        nome = f.name.replace(" - 1. edital.txt", "")
        if "Assistente" in nome: continue
        linhas = f.read_text(encoding="utf-8").splitlines()
        if nome in FIXOS:
            a, b = FIXOS[nome]; i, j = a - 1, b
        else:
            if nome in INICIO: i = INICIO[nome] - 1
            else:
                ini = [k for k, l in enumerate(linhas) if re.match(r"^\s*DIREITOS? HUMANOS\b[^a-z]{0,80}$", l.strip())]
                if not ini: print("SEM INICIO:", nome); continue
                cands = []
                for k in ini:
                    j = k + 1
                    while j < len(linhas) and j - k < 140 and not (j - k > 3 and TITULO.match(linhas[j]) and not re.match(r"^\s*DIREITOS? HUMANOS", linhas[j].strip())): j += 1
                    cands.append((j - k, k, j))
                _, i, j = max(cands)
            if nome not in FIXOS and nome in INICIO:
                j = i + 1
                while j < len(linhas) and j - i < 140 and not (j - i > 40 and TITULO.match(linhas[j]) and not re.match(r"^\s*(Direitos? Humanos|DIREITOS? HUMANOS)", linhas[j].strip())): j += 1
        txt = "\n".join(l.rstrip() for l in linhas[i:j] if l.strip())
        (OUT / f"{nome}.txt").write_text(txt, encoding="utf-8")
        print(f"{nome[:46]:46} linhas {i+1}-{j} ({j-i}) {len(txt)}c")
main()
