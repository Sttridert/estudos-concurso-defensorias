#!/usr/bin/env python3
"""Perfil como arquivo (plano 06, Etapa 2b; decisões 46 e 47). Ver lib_perfil.py.
O perfil vive SÓ no `perfil.toml` da pasta do concurso (`produtos/apostilas/<concurso>/`). A tabela `perfis` do banco foi aposentada.

Uso:
  python -I scripts/72_perfil.py novo-concurso "<nome da pasta>" --banca FCC --carreira "Defensoria Pública" --cargo "Analista Jurídico"
        [--orgao DPE-AM] [--ano 2026] [--edital-id 4] [--universo "Analista FCC"] [--meia-vida 8] [--pesos "1,0.5,0.25"]
        # cria a pasta e o perfil.toml (sem apostilas, nada confirmado). Universo: nome de um da tabela `universos` (cópia inline) ou omitido = todas
  python -I scripts/72_perfil.py nova-apostila "<pasta>" --disciplina "Direito Penal" [--bloco PENAL] [--nome "..."]
        # acrescenta uma apostila (id novo e único) ao concurso; NÃO confirmada
  python -I scripts/72_perfil.py mostrar "<pasta>"           # imprime o perfil para o usuário ler e confirmar (e o estado de cada apostila)
  python -I scripts/72_perfil.py confirmar "<pasta>" [--apostila ID ...]
        # SÓ depois de mostrar o perfil ao usuário e ter o "sim" dele no chat: grava a data de hoje e a impressão digital
"""
import datetime, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_perfil as LP

BANCO = LP.RAIZ / "banco" / "estudos.db"


def opt(a, nome, padrao=None):
    return a[a.index(nome) + 1] if nome in a and a.index(nome) + 1 < len(a) else padrao


def pasta_de(txt):
    p = Path(txt)
    return p if p.is_absolute() else LP.APOSTILAS / p


def novo_concurso(a):
    nome = a[1]
    pasta = pasta_de(nome)
    arq = pasta / "perfil.toml"
    if arq.exists():
        sys.exit(f"Já existe: {arq}. Use nova-apostila para acrescentar apostilas.")
    for k in ("--banca", "--carreira", "--cargo"):
        if not opt(a, k):
            sys.exit(f"Falta {k}. Perfil mínimo: banca, carreira e cargo (e a disciplina, em nova-apostila).")
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    un = opt(a, "--universo")
    if un:
        r = con.execute("select nome,descricao,filtro from universos where nome=?", (un,)).fetchone()
        if not r:
            nomes = ", ".join(n for (n,) in con.execute("select nome from universos order by id"))
            sys.exit(f"Universo '{un}' não existe na tabela universos. Existentes: {nomes}")
        universo = {"nome": r[0], "descricao": r[1], "filtro": json.loads(r[2])}
    else:
        universo = {"nome": "Todas as questões", "descricao": "Sem filtro.", "filtro": {}}
    pesos = [float(x) for x in opt(a, "--pesos", "1,0.5,0.25").split(",")]
    orgao = opt(a, "--orgao")
    c = {"nome": Path(nome).name, "banca": opt(a, "--banca"), "carreira": opt(a, "--carreira"), "cargo": opt(a, "--cargo"), "orgao": orgao,
         "ano_referencia": int(opt(a, "--ano")) if opt(a, "--ano") else None, "edital_id": int(opt(a, "--edital-id")) if opt(a, "--edital-id") else None,
         "meia_vida": int(opt(a, "--meia-vida", 8)), "estudo_geral": not orgao,
         "pesos": {"A": pesos[0], "B": pesos[1], "C": pesos[2]}, "universo": universo, "apostila": []}
    pasta.mkdir(parents=True, exist_ok=True)
    LP.escrever(arq, c)
    print(f"criado: {arq}\nAgora: nova-apostila \"{pasta.name}\" --disciplina \"...\" [--bloco SIGLA]; depois mostrar e confirmar.")


def nova_apostila(a):
    arq = pasta_de(a[1]) / "perfil.toml"
    if not arq.exists():
        sys.exit(f"Não achei {arq}. Crie o concurso antes (novo-concurso).")
    disc = opt(a, "--disciplina")
    if not disc:
        sys.exit("Falta --disciplina.")
    c = LP.ler(arq)
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    if not con.execute("select 1 from disciplinas where nome=?", (disc,)).fetchone():
        nomes = ", ".join(n for (n,) in con.execute("select nome from disciplinas order by id"))
        sys.exit(f"Disciplina '{disc}' não existe. Existentes: {nomes}")
    bloco = opt(a, "--bloco")
    if bloco and c.get("edital_id"):
        if not con.execute("select 1 from edital_blocos where edital_id=? and sigla=?", (c["edital_id"], bloco)).fetchone():
            sys.exit(f"O edital {c['edital_id']} não tem o bloco '{bloco}' (rode o porteiro: scripts/70_porteiro_edital.py).")
    novo = {"id": LP.proximo_id(con), "disciplina": disc, "bloco": bloco,
            "nome": opt(a, "--nome") or f"{disc} · {c.get('cargo')} · {c.get('banca')}" + (f" · {c.get('orgao')} {c.get('ano_referencia')}" if c.get("orgao") else "")}
    c["apostila"].append(novo)
    LP.escrever(arq, c)
    print(f"apostila id {novo['id']} acrescentada a {arq.parent.name} (NÃO confirmada). Mostre ao usuário: mostrar \"{arq.parent.name}\".")


def mostrar(a):
    arq = pasta_de(a[1]) / "perfil.toml"
    c = LP.ler(arq)
    u = c.get("universo") or {}
    print(f"CONCURSO: {c.get('nome')}\n  banca={c.get('banca')} · carreira={c.get('carreira')} · cargo={c.get('cargo')} · órgão={c.get('orgao')} · ano={c.get('ano_referencia')}"
          f"\n  edital_id={c.get('edital_id')} · meia-vida={c.get('meia_vida')} · pesos={c.get('pesos')} · estudo geral={c.get('estudo_geral')}"
          f"\n  universo: {u.get('nome')}  filtro={json.dumps(u.get('filtro'), ensure_ascii=False)}")
    for ap in c.get("apostila", []):
        ok = ap.get("confirmado_hash") == LP.impressao(c, ap)
        est = f"confirmada em {ap['confirmado_em']}" if ok and ap.get("confirmado_em") else ("ALTERADA depois da confirmação de " + str(ap.get("confirmado_em")) if ap.get("confirmado_em") else "NÃO confirmada")
        print(f"  apostila id {ap['id']}: {ap['disciplina']}" + (f" (bloco {ap['bloco']})" if ap.get("bloco") else "") + f" — {est}")


def confirmar(a):
    arq = pasta_de(a[1]) / "perfil.toml"
    if not arq.exists():
        sys.exit(f"Não achei {arq}.")
    ids = [int(a[i + 1]) for i, x in enumerate(a) if x == "--apostila" and i + 1 < len(a)]
    c = LP.ler(arq)
    hoje = datetime.date.today().isoformat()
    n = 0
    for ap in c["apostila"]:
        if ids and ap["id"] not in ids:
            continue
        ap["confirmado_em"] = hoje
        ap["confirmado_hash"] = LP.impressao(c, ap)
        n += 1
    LP.escrever(arq, c)
    print(f"{n} apostila(s) confirmada(s) em {hoje}.")


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("novo-concurso", "nova-apostila", "mostrar", "confirmar"):
        sys.exit(__doc__)
    {"novo-concurso": novo_concurso, "nova-apostila": nova_apostila, "mostrar": mostrar, "confirmar": confirmar}[a[0]](a)


if __name__ == "__main__":
    main()
