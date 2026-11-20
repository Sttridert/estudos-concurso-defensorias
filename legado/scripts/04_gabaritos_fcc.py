"""Baixa do site da FCC o gabarito oficial atual (relacao geral, todos os tipos) de cada concurso.
Saida: banco/gabaritos_fcc/<codigo>__<n>.html (bruto) e banco/gabaritos_fcc/resumo.json
Uso: python 04_gabaritos_fcc.py
"""
import re, json, pathlib, subprocess, tempfile, os, html as H

BASE = pathlib.Path(__file__).resolve().parent.parent / "banco"
OUT = BASE / "gabaritos_fcc"
OUT.mkdir(exist_ok=True)
P = "https://www.concursosfcc.com.br/concursos"
CODIGOS = ["dpeam121", "dpeba120", "dpesc121", "dpeam122", "dpeap122", "dpece121", "dpemt221", "dpepb121", "dpeam123",
           "dpees121", "dpesp222", "dpeam224", "dpers124", "dpesp124", "dpeba125", "dpema125", "dpemt125", "dpego121", "dperr121", "dpeam124"]


def curl(args, cj):
    r = subprocess.run(["curl", "-s", "-m", "60", "-c", cj, "-b", cj] + args, capture_output=True)
    return r.stdout.decode("latin-1", "replace")


def main():
    resumo = {}
    cj = tempfile.mktemp()
    for cod in CODIGOS:
        resumo[cod] = []
        vistos = set()
        for pag in ["gabaritos/todos.html", "gabaritos/todos2.html", "gabaritos/todos3.html"]:
            t = curl([f"{P}/{cod}/{pag}"], cj)
            m = re.search(r'name\s*=\s*"tabela"[^>]*value\s*=\s*"([^"]+)"', t)
            if not m or m.group(1) in vistos:
                continue
            tab = m.group(1); vistos.add(tab)
            inst = (re.search(r'name\s*=\s*"instituicao"[^>]*value\s*=\s*"([^"]*)"', t) or [None, ""])[1]
            conc = (re.search(r'name\s*=\s*"concurso"[^>]*value\s*=\s*"([^"]*)"', t) or [None, ""])[1]
            cargos = curl(["-X", "POST", f"{P}/gabarito/gabaritoCargos.carregarCargos.mtw", "-d", f"tabela={tab}"], cj)
            ops = re.findall(r'"key":"([^"]+)","value":"([^"]*)"', cargos)
            for k, v in ops:
                if k == "0":
                    continue
                corpo = curl(["-e", f"{P}/{cod}/{pag}", "-X", "POST", f"{P}/DivulgacaoGabaritoFull.fcc",
                              "--data-urlencode", f"spi={cod}", "--data-urlencode", "tpDivulgacao=0", "--data-urlencode", f"tabela={tab}",
                              "--data-urlencode", f"instituicao={inst}", "--data-urlencode", f"concurso={conc}",
                              "--data-urlencode", "textoApresentacaoRelacaoGeral=", "--data-urlencode", f"codOpcao={k}",
                              "--data-urlencode", "consultar=Consultar"], cj)
                nome = f"{cod}__{tab}__{k}.html"
                (OUT / nome).write_text(corpo, encoding="latin-1")
                tipos = len(re.findall(r"Tipo gabarito", corpo))
                resumo[cod].append({"pagina": pag, "tabela": tab, "opcao": k, "cargo": v, "arquivo": nome, "tipos": tipos})
                print(cod, tab, k, v[:50], "tipos:", tipos, flush=True)
        if not resumo[cod]:
            print(cod, "SEM GABARITO NO SITE", flush=True)
    (OUT / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
