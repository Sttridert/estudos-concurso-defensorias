#!/usr/bin/env python3
"""Perfil como arquivo (plano 06, Etapa 2b; decisões 46 e 47). Ver lib_perfil.py.
O perfil vive SÓ no `perfil.toml` da pasta do concurso (`produtos/apostilas/<concurso>/`). A tabela `perfis` do banco foi aposentada.

Uso:
  python -I scripts/72_perfil.py novo-concurso "<nome da pasta>" --banca FCC --carreira "Defensoria Pública" --cargo "Analista Jurídico"
        [--orgao DPE-AM] [--ano 2026] [--edital-id 4] [--edital-slug dpeam2026_analista_juridico] [--universo "Analista FCC"] [--meia-vida 8] [--pesos "1,0.5,0.25"]
        # cria a pasta e o perfil.toml (sem apostilas, nada confirmado). Universo: nome de um da tabela `universos` (cópia inline) ou omitido = todas
  python -I scripts/72_perfil.py nova-apostila "<pasta>" --disciplina "Direito Penal" [--bloco PENAL] [--nome "..."]
        # acrescenta uma apostila (id novo e único) ao concurso; NÃO confirmada
  python -I scripts/72_perfil.py mostrar "<pasta>"           # imprime o perfil para o usuário ler e confirmar (e o estado de cada apostila)
  python -I scripts/72_perfil.py confirmar "<pasta>" [--apostila ID ...]
        # SÓ depois de mostrar o perfil ao usuário e ter o "sim" dele no chat: grava a data de hoje e a impressão digital.
        # Sem opção, confirma só as apostilas que não estão em dia (nunca confirmadas, perfil alterado, base alterada ou confirmadas antes da
        # impressão da base); --apostila ID confirma essa(s); --todas renova a data de todas. Grava também a impressão da BASE (catálogo e edital).
  python -I scripts/72_perfil.py vincular-edital "<pasta>" <slug>
        # grava `edital_slug` (pasta em dados/editais_reais/) no perfil, depois de conferir que bate com o `edital_id`; não mexe na confirmação
"""
import datetime, importlib.util, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_perfil as LP

BANCO = LP.RAIZ / "banco" / "estudos.db"


def opt(a, nome, padrao=None):
    return a[a.index(nome) + 1] if nome in a and a.index(nome) + 1 < len(a) else padrao


def ler_pesos(txt):
    """'1,0.5,0.25' -> (A, B, C); recusa o que não serve (precisam ser 3 números, maiores que zero e nunca crescentes de A para C)"""
    try:
        v = [float(x) for x in txt.split(",")]
    except ValueError:
        sys.exit(f"--pesos '{txt}' inválido: use três números separados por vírgula, como 1,0.5,0.25.")
    if len(v) != 3 or any(x <= 0 for x in v) or not (v[0] >= v[1] >= v[2]):
        sys.exit(f"--pesos '{txt}' inválido: precisa de três números maiores que zero, do grupo A ao C, sem crescer (ex.: 1,0.5,0.25).")
    return v


def ler_meia_vida(txt):
    try:
        m = int(txt)
    except ValueError:
        sys.exit(f"--meia-vida '{txt}' inválida: use um número inteiro de anos, maior que zero.")
    if m <= 0:
        sys.exit(f"--meia-vida '{txt}' inválida: use um número inteiro de anos, maior que zero.")
    return m


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
    pesos = ler_pesos(opt(a, "--pesos", "1,0.5,0.25"))
    orgao = opt(a, "--orgao")
    c = {"nome": Path(nome).name, "banca": opt(a, "--banca"), "carreira": opt(a, "--carreira"), "cargo": opt(a, "--cargo"), "orgao": orgao,
         "ano_referencia": int(opt(a, "--ano")) if opt(a, "--ano") else None, "edital_id": int(opt(a, "--edital-id")) if opt(a, "--edital-id") else None,
         "meia_vida": ler_meia_vida(opt(a, "--meia-vida", 8)), "estudo_geral": not orgao,
         "pesos": {"A": pesos[0], "B": pesos[1], "C": pesos[2]}, "universo": universo, "apostila": []}
    if opt(a, "--edital-slug"):
        c["edital_slug"] = opt(a, "--edital-slug")
        if not c["edital_id"]:
            sys.exit("--edital-slug precisa de --edital-id.")
        problemas = LP.edital_problemas(con, c)
        if problemas:
            sys.exit("Edital de origem não confere: " + " ".join(problemas))
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


def amostra(con, c, disciplina):
    """(provas, questões válidas) da disciplina dentro do universo do concurso; ignora o recorte do bloco do edital (é só uma ordem de grandeza)"""
    spec = importlib.util.spec_from_file_location("m23", LP.RAIZ / "scripts" / "23_motor_analise.py")
    m23 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m23)
    filtro = (c.get("universo") or {}).get("filtro") or {}
    provas, n = set(), 0
    for prova, ano, banca, carr, cargo, inst in con.execute(
            """select distinct p.id,p.ano,p.banca,p.carreira,p.cargo,p.instituicao from provas p
               join questoes q on q.prova_id=p.id join disciplinas d on d.id=q.disciplina_id
               where d.nome=? and q.situacao in ('valida','revisar_texto')""", (disciplina,)):
        if m23.em_universo({"banca": banca or "", "carreira": carr or "", "cargo": cargo or "", "inst": inst or "", "ano": ano}, filtro):
            provas.add(prova)
    if provas:
        marc = ",".join("?" * len(provas))
        n = con.execute(f"""select count(*) from questoes q join disciplinas d on d.id=q.disciplina_id
                            where d.nome=? and q.situacao in ('valida','revisar_texto') and q.prova_id in ({marc})""", (disciplina, *provas)).fetchone()[0]
    return len(provas), n


def vincular_edital(a):
    if len(a) < 3:
        sys.exit(__doc__)
    arq = pasta_de(a[1]) / "perfil.toml"
    if not arq.exists():
        sys.exit(f"Não achei {arq}.")
    c = LP.ler(arq)
    if not c.get("edital_id"):
        sys.exit("O perfil não tem edital_id: não há edital de origem para ligar.")
    c["edital_slug"] = a[2]
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    problemas = LP.edital_problemas(con, c)
    if problemas:
        sys.exit("Edital de origem não confere (nada foi gravado): " + " ".join(problemas))
    LP.escrever(arq, c)
    print(f"edital_slug = {a[2]} gravado em {arq.parent.name} (a confirmação das apostilas não muda).")


def sem_destino(con, c, ap):
    """frases do bloco do edital sem nenhum tópico de destino (o que o 51 chama de sem julgamento; só conta, não decide)"""
    if not (ap.get("bloco") and c.get("edital_id")):
        return None
    return con.execute("""select count(*) from edital_frases f where f.edital_id=? and f.disciplina_edital=?
                          and not exists (select 1 from edital_frase_destinos d where d.frase_id=f.id and d.ponto_id is not null)""",
                       (c["edital_id"], ap["bloco"])).fetchone()[0]


ROTULO = {"confirmada": "confirmada em {em}", "nunca": "NÃO confirmada", "perfil_alterado": "PERFIL ALTERADO depois da confirmação de {em}",
          "base_alterada": "BASE ALTERADA depois da confirmação de {em}: mudou {det}",
          "sem_base": "confirmada em {em}, ANTES da impressão da base (vale, mas refaça ao gerar)"}


def mostrar(a):
    arq = pasta_de(a[1]) / "perfil.toml"
    c = LP.ler(arq)
    u = c.get("universo") or {}
    print(f"CONCURSO: {c.get('nome')}\n  banca={c.get('banca')} · carreira={c.get('carreira')} · cargo={c.get('cargo')} · órgão={c.get('orgao')} · ano={c.get('ano_referencia')}"
          f"\n  edital_id={c.get('edital_id')} · meia-vida={c.get('meia_vida')} · pesos={c.get('pesos')} · estudo geral={c.get('estudo_geral')}"
          f"\n  universo: {u.get('nome')}  filtro={json.dumps(u.get('filtro'), ensure_ascii=False)}")
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    print(f"  edital de origem: edital_id={c.get('edital_id')} · slug={c.get('edital_slug') or '(não informado)'}")
    for prob in LP.edital_problemas(con, c):
        print("  PROBLEMA NA LIGAÇÃO COM O EDITAL: " + prob)
    for ap in c.get("apostila", []):
        cod, det = LP.estado(con, c, ap)
        est = ROTULO[cod].format(em=ap.get("confirmado_em"), det=det)
        print(f"  apostila id {ap['id']}: {ap['disciplina']}" + (f" (bloco {ap['bloco']})" if ap.get("bloco") else "") + f" — {est}")
        np_, nq = amostra(con, c, ap["disciplina"])
        print(f"      amostra no universo: {nq} questões válidas em {np_} provas" + ("  (POUCA: menos de 5 provas é ruído)" if np_ < 5 else ""))
        sd = sem_destino(con, c, ap)
        if sd is not None:
            print(f"      edital: {sd} frases do bloco sem tópico de destino")


def confirmar(a):
    arq = pasta_de(a[1]) / "perfil.toml"
    if not arq.exists():
        sys.exit(f"Não achei {arq}.")
    ids = [int(a[i + 1]) for i, x in enumerate(a) if x == "--apostila" and i + 1 < len(a)]
    c = LP.ler(arq)
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    problemas = LP.edital_problemas(con, c)
    if problemas:
        sys.exit("Edital de origem não confere (nada foi confirmado): " + " ".join(problemas))
    hoje = datetime.date.today().isoformat()
    n = 0
    for ap in c["apostila"]:
        if ids and ap["id"] not in ids:
            continue
        if LP.estado(con, c, ap)[0] == "confirmada" and not ids and "--todas" not in a:
            continue            # já em dia (perfil e base): não renova a data sem pedido
        print(f"  confirmando apostila {ap['id']}: {ap['disciplina']}")
        ap["confirmado_em"] = hoje
        ap["confirmado_hash"] = LP.impressao(c, ap)
        base = LP.impressao_base(con, c, ap)
        if base is None:
            sys.exit(f"Apostila {ap['id']}: não consegui calcular a base (disciplina ou bloco inexistente no banco). Nada foi gravado.")
        ap["confirmado_catalogo"], ap["confirmado_edital"] = base["catalogo"], base["edital"]
        n += 1
    LP.escrever(arq, c)
    print(f"{n} apostila(s) confirmada(s) em {hoje}." + ("" if n else " (nada pendente; use --todas para renovar a data de todas)"))


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("novo-concurso", "nova-apostila", "mostrar", "confirmar", "vincular-edital"):
        sys.exit(__doc__)
    {"novo-concurso": novo_concurso, "nova-apostila": nova_apostila, "mostrar": mostrar, "confirmar": confirmar, "vincular-edital": vincular_edital}[a[0]](a)


if __name__ == "__main__":
    main()
