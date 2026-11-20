#!/usr/bin/env python3
"""Grupo A (Coletar), pista de questões: tudo sobre GABARITOS e metadados de fonte, em um só script.

Reúne os antigos 04, 05, 06 e 65 (decisão do usuário, A-2). Cada subcomando mantém o comportamento do script que substituiu.

Uso (sempre com `python -I`):
  python -I scripts/coletar_gabaritos.py baixar-fcc [--so CODIGO] [--saida PASTA]
      Baixa do site da FCC o gabarito oficial atual (relação geral, todos os tipos) de cada concurso.
      Saída: banco/gabaritos_fcc/<codigo>__<tabela>__<opcao>.html (bruto) e resumo.json.   (antigo 04)
  python -I scripts/coletar_gabaritos.py ajustes-fcc [--saida ARQUIVO.json]
      Lê os relatórios oficiais da FCC de "Alteração de gabarito e Atribuição de questões" (texto em
      banco/gabaritos_fcc/pdf/) e gera banco/ajustes_gabarito.json. Atribuição = questão atribuída a todos
      (na prática, anulada); alteração = a letra do gabarito mudou. Cada grupo entre linhas '-----' é UMA questão,
      numerada diferente em cada tipo de caderno.                                          (antigo 05)
  python -I scripts/coletar_gabaritos.py ler-tec NOME
      Lê o JSON baixado do TEC (banco/fonte_tec/recebidos/tec_NOME_questoes.json) e gera banco/fonte_tec/tec_NOME.json
      com campos limpos.                                                                   (antigo 06)
  python -I scripts/coletar_gabaritos.py aplicar ARQUIVO.json [--simular]
      Aplica no banco o resultado da pesquisa de anulações e alterações de gabarito.
      Formato: {"anulacoes": [{"prova", "numero", "tipo", "fonte"}], "status": [{"prova", "status", "fonte"}]}
        anulacoes: grava em `ajustes_gabarito` (ajuste 'atribuicao') e marca a questão como 'anulada';
        status:    troca `provas.gabarito_status` (a tag "gabarito preliminar" do cartão sai quando o status deixa de
                   começar por "preliminar" ou "a confirmar"; ver lib_escopo.gabarito_preliminar).
      Cópia do banco antes. Idempotente.                                                   (antigo 65)
"""
import argparse
import datetime
import json
import pathlib
import re
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lib_conferencia import situacao_do_status  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
BANCO_DIR = RAIZ / "banco"
BANCO = BANCO_DIR / "estudos.db"

# ---------------------------------------------------------------- baixar-fcc (antigo 04)
SITE_FCC = "https://www.concursosfcc.com.br/concursos"
CODIGOS_FCC = ["dpeam121", "dpeba120", "dpesc121", "dpeam122", "dpeap122", "dpece121", "dpemt221", "dpepb121", "dpeam123",
               "dpees121", "dpesp222", "dpeam224", "dpers124", "dpesp124", "dpeba125", "dpema125", "dpemt125", "dpego121",
               "dperr121", "dpeam124"]


def _curl(args, cj):
    r = subprocess.run(["curl", "-s", "-m", "60", "-c", cj, "-b", cj] + args, capture_output=True)
    return r.stdout.decode("latin-1", "replace")


def baixar_fcc(so=None, saida=None):
    out = pathlib.Path(saida) if saida else BANCO_DIR / "gabaritos_fcc"
    out.mkdir(exist_ok=True, parents=True)
    resumo = {}
    cj = tempfile.mktemp()
    for cod in ([so] if so else CODIGOS_FCC):
        resumo[cod] = []
        vistos = set()
        for pag in ["gabaritos/todos.html", "gabaritos/todos2.html", "gabaritos/todos3.html"]:
            t = _curl([f"{SITE_FCC}/{cod}/{pag}"], cj)
            m = re.search(r'name\s*=\s*"tabela"[^>]*value\s*=\s*"([^"]+)"', t)
            if not m or m.group(1) in vistos:
                continue
            tab = m.group(1)
            vistos.add(tab)
            inst = (re.search(r'name\s*=\s*"instituicao"[^>]*value\s*=\s*"([^"]*)"', t) or [None, ""])[1]
            conc = (re.search(r'name\s*=\s*"concurso"[^>]*value\s*=\s*"([^"]*)"', t) or [None, ""])[1]
            cargos = _curl(["-X", "POST", f"{SITE_FCC}/gabarito/gabaritoCargos.carregarCargos.mtw", "-d", f"tabela={tab}"], cj)
            ops = re.findall(r'"key":"([^"]+)","value":"([^"]*)"', cargos)
            for k, v in ops:
                if k == "0":
                    continue
                corpo = _curl(["-e", f"{SITE_FCC}/{cod}/{pag}", "-X", "POST", f"{SITE_FCC}/DivulgacaoGabaritoFull.fcc",
                               "--data-urlencode", f"spi={cod}", "--data-urlencode", "tpDivulgacao=0", "--data-urlencode", f"tabela={tab}",
                               "--data-urlencode", f"instituicao={inst}", "--data-urlencode", f"concurso={conc}",
                               "--data-urlencode", "textoApresentacaoRelacaoGeral=", "--data-urlencode", f"codOpcao={k}",
                               "--data-urlencode", "consultar=Consultar"], cj)
                nome = f"{cod}__{tab}__{k}.html"
                (out / nome).write_text(corpo, encoding="latin-1")
                tipos = len(re.findall(r"Tipo gabarito", corpo))
                resumo[cod].append({"pagina": pag, "tabela": tab, "opcao": k, "cargo": v, "arquivo": nome, "tipos": tipos})
                print(cod, tab, k, v[:50], "tipos:", tipos, flush=True)
        if not resumo[cod]:
            print(cod, "SEM GABARITO NO SITE", flush=True)
    (out / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- ajustes-fcc (antigo 05)
RELATORIOS_FCC = {  # arquivo -> (prova, tipo do caderno)
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


def _parse_ajustes(txt):
    secao = None
    grupos = []  # (secao, [(num, tipo, letra)])
    atual = []
    for linha in txt.splitlines():
        s = linha.strip()
        if re.match(r'^Atribui', s):
            secao = "atribuicao"
            continue
        if re.match(r'^Altera[cç][õo]es\s*$', s):
            secao = "alteracao"
            continue
        m = re.match(r'^Quest[ãa]o\s+(\d+)\s+tipo\s+(\d)\s*([A-E])?\s*$', s)
        if m:
            t = int(m.group(2))
            if atual and t <= atual[-1][1]:  # tipo reiniciou: novo grupo (questão)
                grupos.append((secao, atual))
                atual = []
            atual.append((int(m.group(1)), t, m.group(3)))
        elif s.startswith('-----') and atual:
            grupos.append((secao, atual))
            atual = []
    if atual:
        grupos.append((secao, atual))
    return grupos


def ajustes_fcc(saida=None):
    pdf = BANCO_DIR / "gabaritos_fcc" / "pdf"
    ajustes = []
    for arq, (prova, tipo) in RELATORIOS_FCC.items():
        txt = (pdf / (arq + ".txt")).read_text(encoding="utf-8")
        for secao, g in _parse_ajustes(txt):
            linha = [x for x in g if x[1] == tipo]
            if not linha:
                continue
            n, _, letra = linha[0]
            secao = secao or ("alteracao" if letra else "atribuicao")
            ajustes.append({"prova": prova, "numero": n, "tipo": tipo, "ajuste": secao, "nova_letra": letra, "fonte": arq + ".pdf"})
    destino = pathlib.Path(saida) if saida else BANCO_DIR / "ajustes_gabarito.json"
    destino.write_text(json.dumps(ajustes, ensure_ascii=False, indent=1), encoding="utf-8")
    for a in ajustes:
        print(a["prova"][:40].ljust(40), a["ajuste"], "Q", a["numero"], a["nova_letra"] or "")
    print(len(ajustes), "ajustes")


# ---------------------------------------------------------------- ler-tec (antigo 06)
def _parse_tec(txt):
    n = int(re.match(r"Quest[ãa]o (\d+)", txt).group(1))
    mat = (re.search(r"Mat[ée]ria:\s*(.*)", txt) or [None, ""])[1].strip()
    ass = (re.search(r"Assunto:\s*\n?(.*)", txt) or [None, ""])[1].strip()
    tid = (re.search(r"#(\d{4,})", txt) or [None, None])[1]
    corpo = txt.split("\n", 1)[1]  # corpo: depois da linha do #id
    i = re.search(r"#\d{4,}[^\n]*\n", corpo)
    corpo = corpo[i.end():] if i else corpo
    partes = re.split(r"\n\s*\n\s*([A-E])\n\t", "\n\n" + corpo.strip("\n"), flags=re.S)  # alternativas: linhas "A\n\t texto"
    enun = partes[0].strip()
    alts = {}
    for k in range(1, len(partes) - 1, 2):
        alts[partes[k]] = re.sub(r"\s+", " ", partes[k + 1]).strip()
    return n, {"tec_id": tid, "materia": mat, "assunto": ass, "enunciado": re.sub(r"[ \t]+\n", "\n", enun).strip(), "alternativas": alts}


def ler_tec(nome):
    pasta = BANCO_DIR / "fonte_tec"
    d = json.loads((pasta / "recebidos" / f"tec_{nome}_questoes.json").read_text(encoding="utf-8"))
    out = {}
    for _, v in d.items():
        n, r = _parse_tec(v)
        out[n] = r
    (pasta / f"tec_{nome}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ruins = [n for n, r in out.items() if len(r["alternativas"]) != 5]
    print(nome, len(out), "questoes; sem 5 alternativas:", ruins)


# ---------------------------------------------------------------- aplicar (antigo 65)
def aplicar(arquivo, simular=False):
    arq = pathlib.Path(arquivo)
    dados = json.loads(arq.read_text(encoding="utf-8"))
    con = sqlite3.connect(BANCO)
    if not simular:
        dst = BANCO_DIR / "backup" / f"estudos_antes_gabaritos_{datetime.date.today().isoformat()}.db"
        if not dst.exists():
            out = sqlite3.connect(dst)
            con.backup(out)
            out.close()
            print("cópia de segurança:", dst.name)
    n_an = n_st = 0
    for a in dados.get("anulacoes", []):
        p = con.execute("select id from provas where nome=?", (a["prova"],)).fetchone()
        q = con.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?",
                        (a["prova"], a["numero"])).fetchone()
        if not p or not q:
            sys.exit("prova ou questão não encontrada: " + json.dumps(a, ensure_ascii=False))
        if not con.execute("select 1 from ajustes_gabarito where prova_id=? and numero=? and tipo_caderno=?",
                           (p[0], a["numero"], a["tipo"])).fetchone():
            con.execute("insert into ajustes_gabarito(prova_id,numero,tipo_caderno,ajuste,nova_letra,fonte) values (?,?,?,?,?,?)",
                        (p[0], a["numero"], a["tipo"], "atribuicao", None, a["fonte"]))
        con.execute("update questoes set situacao='anulada', motivo_situacao=? where id=?",
                    ("atribuída a todos os candidatos (anulada) - relatório oficial da FCC: " + a["fonte"], q[0]))
        n_an += 1
    for s in dados.get("status", []):
        r = con.execute("select id from provas where nome=?", (s["prova"],)).fetchone()
        if not r:
            sys.exit("prova não encontrada: " + s["prova"])
        con.execute("update provas set gabarito_status=?, gabarito_situacao=? where id=?",
                    (s["status"], s.get("situacao") or situacao_do_status(s["status"]), r[0]))
        n_st += 1
    con.execute("insert into log_alteracoes(quem,o_que) values('coletar_gabaritos aplicar', ?)",
                (f"gabaritos de {arq.name}: {n_an} anulações, {n_st} status" + (" [simulação]" if simular else ""),))
    if simular:
        con.rollback()
        print("(simulação: nada gravado)")
    else:
        con.commit()
    print(f"{n_an} anulações, {n_st} status")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baixar-fcc")
    b.add_argument("--so", help="só este código de concurso (ex.: dpeam121)")
    b.add_argument("--saida", help="pasta de saída (padrão: banco/gabaritos_fcc)")
    a = sub.add_parser("ajustes-fcc")
    a.add_argument("--saida", help="arquivo de saída (padrão: banco/ajustes_gabarito.json)")
    t = sub.add_parser("ler-tec")
    t.add_argument("nome")
    p = sub.add_parser("aplicar")
    p.add_argument("arquivo")
    p.add_argument("--simular", action="store_true")
    x = ap.parse_args()
    if x.cmd == "baixar-fcc":
        baixar_fcc(x.so, x.saida)
    elif x.cmd == "ajustes-fcc":
        ajustes_fcc(x.saida)
    elif x.cmd == "ler-tec":
        ler_tec(x.nome)
    else:
        aplicar(x.arquivo, x.simular)


if __name__ == "__main__":
    main()
