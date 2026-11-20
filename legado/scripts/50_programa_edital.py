#!/usr/bin/env python3
"""Fase 5 (edital real), passo 1: extrai o PROGRAMA LITERAL do edital, dividido por disciplina.

Uso:  python -I scripts/50_programa_edital.py "<nome da pasta em provas/>" --slug <slug> [--alvos CONST,ADM,...]

Lê `provas/<pasta>/1. edital.pdf` e grava `dados/editais_reais/<slug>/programa.json`:
  edital      metadados (banca, carreira, cargo, órgão, ano, arquivo)
  disciplinas lista de {codigo, disciplina_banco, titulo_no_edital, itens:[{ordem, rotulo, frases:[{id, texto}]}]}
Regras (CLAUDE.md): texto ipsis litteris; só se juntam quebras de linha e palavras hifenizadas no fim da linha.
Guardrail: cada frase é conferida contra o texto bruto do PDF (sem espaços e sem hífens); se alguma não existir
igual, o script lista e NÃO grava. Reaproveita as funções do script 40, com uma divisão de itens que tolera a
numeração irregular do edital (item repetido ou pulado; ex.: DPE-AM 2026 repete o 6 e pula o 13 em Processo Civil).
Não altera o banco. Repetível.
"""
import argparse, csv, importlib.util, json, re, subprocess, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("extrator40", RAIZ / "scripts" / "40_extrair_programas.py")
m40 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m40)
DIVIDIR_ORIGINAL = m40.dividir_itens

DISCIPLINA_BANCO = {"DH": "Direitos Humanos", "PENAL": "Direito Penal", "CONST": "Direito Constitucional", "ADM": "Direito Administrativo",
                    "PCIV": "Direito Processual Civil", "PPEN": "Direito Processual Penal", "CIV": "Direito Civil",
                    "ECA": "Direito da Criança e do Adolescente"}
ORDEM_PADRAO = ["CONST", "ADM", "CIV", "PCIV", "PENAL", "PPEN", "DH", "ECA"]


def dividir_itens_tolerante(txt: str):
    """Como a do script 40, mas aceita também o mesmo número de novo (item repetido) e o salto de um número (item pulado)."""
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
        elif (tuple(p) in m40.sucessores(atual) or p == atual
              or (len(p) == 1 and len(atual) == 1 and p[0] == atual[0] + 2)
              or (len(p) == 1 and len(atual) > 1 and p[0] in (atual[0] + 1, atual[0] + 2))):
            aceitos.append((pos, lab, fim)); atual = p
    if len(aceitos) >= 3:
        return [(lab, txt[fim:(aceitos[k + 1][0] if k + 1 < len(aceitos) else len(txt))].strip())
                for k, (pos, lab, fim) in enumerate(aceitos)]
    return DIVIDIR_ORIGINAL(txt)       # sem numeração: letras a) b) c) ou bloco único (como no script 40)


def compacto(s: str) -> str:
    return re.sub(r"[\s\-–]+", "", s)


def texto_bruto(pdf: Path) -> str:
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True).stdout.decode("utf-8", "replace")
    todas = out.splitlines()
    # cabeçalho e rodapé que se repetem em cada página (ex.: "Página 49 de 67", "Publicação: ...") ficam no meio de frases que
    # cruzam a quebra de página: saem daqui, como já saem na extração (script 40, texto_pdf)
    rep = {s for s, n in __import__("collections").Counter(l.strip() for l in todas if l.strip()).items() if n >= 6 and len(s) < 120}
    linhas = [l for l in todas if not re.fullmatch(r"\s*\d{1,3}\s*", l) and l.strip() not in rep
              and not re.fullmatch(r"\s*P[áa]gina\s+\d+\s*(de\s*\d+)?\s*", l, re.I)]   # números de página
    return compacto(" ".join(linhas))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta"); ap.add_argument("--slug", required=True); ap.add_argument("--alvos", default=",".join(ORDEM_PADRAO))
    a = ap.parse_args()
    pasta = RAIZ / "provas" / a.pasta
    pdf = pasta / "1. edital.pdf"
    if not pdf.exists():
        sys.exit(f"não achei {pdf}")
    m40.dividir_itens = dividir_itens_tolerante          # só neste processo
    meta = m40.metadados()
    inv = {}
    rel = f"provas/{pasta.name}/1. edital.pdf"
    with open(RAIZ / "dados" / "inventario_editais_edital_geral.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["arquivo_local"].replace("\\", "/") == rel:
                inv = r
    bruto = texto_bruto(pdf)
    disciplinas, falhas = [], []
    for alvo in [x.strip().upper() for x in a.alvos.split(",") if x.strip()]:
        r = m40.processar(pasta, alvo, meta)
        if not r["secoes"]:
            print(f"{alvo}: nenhuma seção encontrada"); continue
        sec = max(r["secoes"], key=lambda s: s["caracteres"])
        itens, n = [], 0
        for k, it in enumerate(sec["itens"], 1):
            fr = []
            for f in it["frases"]:
                n += 1
                fr.append({"id": f"{alvo}-{n:03d}", "texto": f})
                if compacto(f) not in bruto:
                    falhas.append(f"{alvo}-{n:03d}: {f[:90]!r}")
            itens.append({"ordem": k, "rotulo": it["item"] or None, "frases": fr})
        disciplinas.append({"codigo": alvo, "disciplina_banco": DISCIPLINA_BANCO[alvo], "titulo_no_edital": sec["titulo_no_edital"],
                            "avisos": sec["avisos"], "itens": itens})
        print(f"{alvo:6} {len(itens):3d} itens {n:4d} frases  rótulos: {', '.join((i['rotulo'] or '-') for i in itens)[:150]}")
    if falhas:
        sys.exit("NÃO gravado: frases que não são cópia exata do PDF:\n  " + "\n  ".join(falhas))
    saida = RAIZ / "dados" / "editais_reais" / a.slug
    saida.mkdir(parents=True, exist_ok=True)
    edital = {"slug": a.slug, "pasta": pasta.name, "arquivo": rel, "banca": inv.get("banca", "?"), "orgao": inv.get("orgao"),
              "cargo": inv.get("cargo"), "ano": int(inv["ano_do_edital"]) if inv.get("ano_do_edital") else None}
    (saida / "programa.json").write_text(json.dumps({"edital": edital, "disciplinas": disciplinas}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"gravado {saida / 'programa.json'}: {len(disciplinas)} disciplinas, {sum(len(i['frases']) for d in disciplinas for i in d['itens'])} frases")


if __name__ == "__main__":
    main()
