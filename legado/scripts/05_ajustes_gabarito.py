"""Le os relatorios oficiais da FCC de 'Alteracao de gabarito e Atribuicao de questoes' e gera banco/ajustes_gabarito.json.
- Atribuicao = questao atribuida a todos os candidatos (na pratica, anulada).
- Alteracao  = letra do gabarito mudou (a letra informada e a nova).
Cada grupo (entre linhas '-----') e UMA questao, numerada diferente em cada tipo de caderno. Pega-se a linha do tipo do caderno.
Uso: python 05_ajustes_gabarito.py
"""
import re, json, pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent / "banco"
PDF = BASE / "gabaritos_fcc" / "pdf"
RELATORIOS = {  # arquivo -> (prova, tipo do caderno)
    "dpeba120__atribuicoes_de_questoes": ("2021 - DPE-BA - Defensor Público", 2),
    "dpeap122__dpeap122_-_atribuicao": ("2022 - DPE-AP - Defensor Público", 1),
    "dpees121__dpees121_alteracao_atribuicao_de_gabarito": ("2023 - DPE-ES - Defensor Público", 3),
    "dpesp222__relatorio_alteracoes_gabaritos": ("2023 - DPE-SP - Defensor Público", 5),
    "dpeam224__6_dpeam224_alteracoes_de_gabarito": ("2025 - DPE-AM - Defensor Público", 1),
    "dpesp124__6_dpesp124_alteracoes_de_gabarito": ("2025 - DPE-SP - Analista de Defensoria", 1),
    "dpemt125__dpemt125_relatorio_atribuicao_de_gabaritos": ("2026 - DPE-MT - Defensor Público", 1),
    "dpego121__atribuicoes_de_gabarito": ("2021 - DPE-GO - Defensor Público", 4),
    "dperr119__alteracao_de_gabarito": ("2021 - DPE-RR - Defensor Público", 4),
}


def parse(txt):
    secao = None
    grupos = []  # (secao, [(num, tipo, letra)])
    atual = []
    for l in txt.splitlines():
        s = l.strip()
        if re.match(r'^Atribui', s): secao = "atribuicao"; continue
        if re.match(r'^Altera[cç][õo]es\s*$', s): secao = "alteracao"; continue
        m = re.match(r'^Quest[ãa]o\s+(\d+)\s+tipo\s+(\d)\s*([A-E])?\s*$', s)
        if m:
            t = int(m.group(2))
            if atual and t <= atual[-1][1]:  # tipo reiniciou: novo grupo (questao)
                grupos.append((secao, atual)); atual = []
            atual.append((int(m.group(1)), t, m.group(3)))
        elif s.startswith('-----') and atual:
            grupos.append((secao, atual)); atual = []
    if atual: grupos.append((secao, atual))
    return grupos


def main():
    ajustes = []
    for arq, (prova, tipo) in RELATORIOS.items():
        txt = (PDF / (arq + ".txt")).read_text(encoding="utf-8")
        for secao, g in parse(txt):
            linha = [x for x in g if x[1] == tipo]
            if not linha: continue
            n, _, letra = linha[0]
            secao = secao or ("alteracao" if letra else "atribuicao")
            ajustes.append({"prova": prova, "numero": n, "tipo": tipo, "ajuste": secao, "nova_letra": letra, "fonte": arq + ".pdf"})
    (BASE / "ajustes_gabarito.json").write_text(json.dumps(ajustes, ensure_ascii=False, indent=1), encoding="utf-8")
    for a in ajustes:
        print(a["prova"][:40].ljust(40), a["ajuste"], "Q", a["numero"], a["nova_letra"] or "")
    print(len(ajustes), "ajustes")


if __name__ == "__main__":
    main()
