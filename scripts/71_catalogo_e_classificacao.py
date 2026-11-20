#!/usr/bin/env python3
"""Catálogo de pontos e classificação das questões, guiados por ARQUIVOS DE DADOS (plano 06, Etapa 2).

Substitui, para qualquer disciplina, os scripts por disciplina 21, 22, 31 e 58 a 63 (catálogo e classificação).

Uso:
  python -I scripts/71_catalogo_e_classificacao.py exportar [--saida PASTA]   # banco -> arquivos (uma vez; também serve para conferir)
  python -I scripts/71_catalogo_e_classificacao.py aplicar [disciplina ...] [--simular] [--banco ARQ]
  python -I scripts/71_catalogo_e_classificacao.py conferir [--banco ARQ]      # = aplicar --simular em todas
  python -I scripts/71_catalogo_e_classificacao.py estado [mostrar | definir <disciplina> provisorio|fechado --motivo "..." [--versao v2] [--editais "..."] [--risco "..."] [--sim-do-usuario]]
                                                                                       # catálogo FECHADO só aceita acréscimo (ver scripts/lib_catalogo.py)
  python -I scripts/71_catalogo_e_classificacao.py semear SIGLA "Nome da disciplina"   # SUPERADO (decisão 53; use scripts/catalogar_novo.py criar). Antes: disciplina NOVA, catálogo inicial a partir de
                                                                                       # dados/edital_ficticio_geral/taxonomia_SIGLA.json (depois conferir e `aplicar`)

Arquivos (um par por disciplina; o nome é o da disciplina sem acento, ex.: direito-penal):
  dados/catalogo/<disciplina>.json       assuntos e pontos (códigos, textos, descrições, origem)
  dados/classificacao/<disciplina>.csv   uma linha por questão: prova;numero;ponto;ponto2;tipo_cobranca;detalhe;confianca;
                                         origem;revisada;assunto_provisorio;atualizado_em
                                         (o arquivo é da disciplina do PONTO principal; a questão pode ser de outra disciplina)

Regras de segurança:
- O banco é a fonte única; `exportar` copia o que o banco TEM. Depois disso, editar o arquivo e rodar `aplicar` muda o banco.
- `aplicar` NUNCA apaga ponto, assunto ou classificação: só insere o que falta e atualiza o que difere do arquivo
  (classificação de questão que não está em arquivo nenhum fica como está). Pontos têm tabelas penduradas (edital, frases), por isso
  não há exclusão; para aposentar um ponto, `ativo = 0` no arquivo.
- Cópia do banco antes de gravar (banco/backup), registro em `log_alteracoes`, `--simular` não grava nada.
- Chave da questão: nome da prova + número (os ids mudam quando entra prova nova).
"""
import csv, datetime, json, re, sqlite3, sys, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_catalogo as LC   # noqa: E402  (estado do catálogo: provisório ou fechado)

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
CAT = RAIZ / "dados" / "catalogo"
CLS = RAIZ / "dados" / "classificacao"
CAMPOS = ["prova", "numero", "ponto", "ponto2", "tipo_cobranca", "detalhe", "confianca", "origem", "revisada", "assunto_provisorio", "atualizado_em"]


def slug(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def abrir(caminho):
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA foreign_keys=ON")
    return con


def vazio(v):
    return "" if v is None else str(v)


# ---------------------------------------------------------------- exportar
def exportar(con, saida_cat, saida_cls):
    saida_cat.mkdir(parents=True, exist_ok=True); saida_cls.mkdir(parents=True, exist_ok=True)
    discs = con.execute("select id,nome from disciplinas where id in (select disciplina_id from pontos) order by id").fetchall()
    total_p = total_c = 0
    for did, nome in discs:
        ass = con.execute("select codigo,nome,descricao from assuntos where disciplina_id=? order by codigo", (did,)).fetchall()
        pts = con.execute("""select p.codigo,a.codigo,p.texto,p.descricao,p.origem,p.ativo,p.criado_em from pontos p join assuntos a on a.id=p.assunto_id
                             where p.disciplina_id=? order by p.codigo""", (did,)).fetchall()
        dados = {"disciplina": nome,
                 "assuntos": [{"codigo": c, "nome": n, "descricao": d} for c, n, d in ass],
                 "pontos": [{"codigo": c, "assunto": a, "texto": t, "descricao": d, "origem": o, "ativo": at, "criado_em": cr} for c, a, t, d, o, at, cr in pts]}
        (saida_cat / f"{slug(nome)}.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        linhas = con.execute("""select pr.nome, q.numero, p1.codigo, p2.codigo, k.tipo_cobranca, k.detalhe, k.confianca, k.origem, k.revisada, a.codigo, k.atualizado_em
                                from classificacao k join questoes q on q.id=k.questao_id join provas pr on pr.id=q.prova_id
                                join pontos p1 on p1.id=k.ponto_id left join pontos p2 on p2.id=k.ponto2_id
                                left join assuntos a on a.id=k.assunto_provisorio_id
                                where p1.disciplina_id=? order by pr.nome, q.numero""", (did,)).fetchall()
        with open(saida_cls / f"{slug(nome)}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";", lineterminator="\n"); w.writerow(CAMPOS)
            for l in linhas:
                w.writerow([vazio(x) for x in l])
        total_p += len(pts); total_c += len(linhas)
        print(f"{nome}: {len(ass)} assuntos, {len(pts)} pontos, {len(linhas)} classificações")
    sem = con.execute("select count(*) from classificacao where ponto_id is null").fetchone()[0]
    print(f"TOTAL: {total_p} pontos, {total_c} classificações exportadas; classificações sem ponto principal (não exportadas): {sem}")


# ---------------------------------------------------------------- aplicar
def aplicar_catalogo(con, arq, rel, fechado=False):
    """`fechado`: catálogo fechado só aceita ACRÉSCIMO; mudança em linha existente vai para rel["bloqueado"] e não é feita."""
    d = json.loads(arq.read_text(encoding="utf-8"))
    did = con.execute("select id from disciplinas where nome=?", (d["disciplina"],)).fetchone()
    if not did:
        sys.exit(f"{arq.name}: disciplina '{d['disciplina']}' não existe no banco.")
    did = did[0]
    for a in d["assuntos"]:
        r = con.execute("select id,nome,descricao from assuntos where disciplina_id=? and codigo=?", (did, a["codigo"])).fetchone()
        if not r:
            con.execute("insert into assuntos(disciplina_id,codigo,nome,descricao) values(?,?,?,?)", (did, a["codigo"], a["nome"], a["descricao"]))
            rel["assuntos_novos"].append(a["codigo"])
        elif (r[1], r[2]) != (a["nome"], a["descricao"]):
            if fechado:
                rel["bloqueado"].append("assunto " + a["codigo"])
                continue
            con.execute("update assuntos set nome=?, descricao=? where id=?", (a["nome"], a["descricao"], r[0]))
            rel["assuntos_mudados"].append(a["codigo"])
    ass = {c: i for i, c in con.execute("select id,codigo from assuntos where disciplina_id=?", (did,))}
    for p in d["pontos"]:
        if p["assunto"] not in ass:
            sys.exit(f"{arq.name}: ponto {p['codigo']} aponta para assunto {p['assunto']} que não existe.")
        r = con.execute("select id,assunto_id,texto,descricao,ativo from pontos where disciplina_id=? and codigo=?", (did, p["codigo"])).fetchone()
        if not r:
            if con.execute("select 1 from pontos where codigo=?", (p["codigo"],)).fetchone():
                sys.exit(f"{arq.name}: o código {p['codigo']} já existe em outra disciplina.")
            con.execute("insert into pontos(disciplina_id,assunto_id,codigo,texto,descricao,origem,ativo,criado_em) values(?,?,?,?,?,?,?,?)",
                        (did, ass[p["assunto"]], p["codigo"], p["texto"], p["descricao"], p["origem"], p["ativo"], p["criado_em"]))
            rel["pontos_novos"].append(p["codigo"])
        elif (r[1], r[2], r[3], r[4]) != (ass[p["assunto"]], p["texto"], p["descricao"], p["ativo"]):
            if fechado:
                rel["bloqueado"].append("ponto " + p["codigo"])
                continue
            con.execute("update pontos set assunto_id=?, texto=?, descricao=?, ativo=? where id=?", (ass[p["assunto"]], p["texto"], p["descricao"], p["ativo"], r[0]))
            rel["pontos_mudados"].append(p["codigo"])
    nos_arquivos = {p["codigo"] for p in d["pontos"]}
    for (c,) in con.execute("select codigo from pontos where disciplina_id=?", (did,)):
        if c not in nos_arquivos:
            rel["pontos_so_no_banco"].append(c)


def aplicar_classificacao(con, arq, rel, agora):
    pontos = {c: i for i, c in con.execute("select id,codigo from pontos")}
    assuntos = {c: i for i, c in con.execute("select id,codigo from assuntos")}
    with open(arq, encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    for l in linhas:
        q = con.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (l["prova"], int(l["numero"]))).fetchone()
        if not q:
            sys.exit(f"{arq.name}: questão não achada: {l['prova']} nº {l['numero']}")
        for campo in ("ponto", "ponto2"):
            if l[campo] and l[campo] not in pontos:
                sys.exit(f"{arq.name}: {l['prova']} nº {l['numero']}: ponto {l[campo]} não existe no catálogo.")
        novo = (pontos[l["ponto"]], pontos[l["ponto2"]] if l["ponto2"] else None, assuntos[l["assunto_provisorio"]] if l["assunto_provisorio"] else None,
                l["detalhe"], l["tipo_cobranca"], l["origem"], l["confianca"], int(l["revisada"] or 0))
        r = con.execute("select ponto_id,ponto2_id,assunto_provisorio_id,detalhe,tipo_cobranca,origem,confianca,coalesce(revisada,0) from classificacao where questao_id=?", (q[0],)).fetchone()
        if r is None:
            con.execute("""insert into classificacao(questao_id,ponto_id,ponto2_id,assunto_provisorio_id,detalhe,tipo_cobranca,origem,confianca,revisada,atualizado_em)
                           values(?,?,?,?,?,?,?,?,?,?)""", (q[0],) + novo + (agora,))
            rel["classif_novas"].append((l["prova"], l["numero"]))
        elif tuple(r) != novo:
            con.execute("""update classificacao set ponto_id=?,ponto2_id=?,assunto_provisorio_id=?,detalhe=?,tipo_cobranca=?,origem=?,confianca=?,revisada=?,atualizado_em=?
                           where questao_id=?""", novo + (agora, q[0]))
            rel["classif_mudadas"].append((l["prova"], l["numero"]))


def aplicar(args, simular, banco):
    escolhidas = {slug(a) for a in args}
    cats = sorted(c for c in CAT.glob("*.json") if not c.name.startswith("_"))
    if escolhidas:
        cats = [c for c in cats if c.stem in escolhidas]
        faltam = escolhidas - {c.stem for c in cats}
        if faltam:
            sys.exit("Sem arquivo de catálogo para: " + ", ".join(sorted(faltam)) + ". Disponíveis: " + ", ".join(LC.catalogos()))
    if not simular:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_catalogo_classificacao_{datetime.datetime.now():%Y-%m-%d_%H%M}.db"
        s = sqlite3.connect(banco); o = sqlite3.connect(dst); s.backup(o); o.close(); s.close()
        print("cópia de segurança:", dst.name)
    con = abrir(":memory:" if simular else banco)
    if simular:
        real = sqlite3.connect(banco); real.backup(con); real.close()
    agora = datetime.datetime.now().isoformat(timespec="seconds")
    mexeu = 0
    for c in cats:
        rel = {k: [] for k in ("assuntos_novos", "assuntos_mudados", "pontos_novos", "pontos_mudados", "pontos_so_no_banco", "classif_novas", "classif_mudadas", "bloqueado")}
        aplicar_catalogo(con, c, rel, fechado=LC.esta_fechado(c.stem))
        if rel["bloqueado"]:
            msg = (f"{c.stem}: catálogo FECHADO; só aceita acréscimo. Mudanças em linhas existentes recusadas: {', '.join(rel['bloqueado'])}. "
                   "Para mudar o que já existe: reabrir (`estado definir ... provisorio --motivo ...`), com o mapa antigo→novo e o \"sim\" do usuário.")
            if not simular:
                con.rollback()
                sys.exit("RECUSADO, nada foi gravado. " + msg)
            print("BLOQUEADO (em simulação): " + msg)
        arq = CLS / f"{c.stem}.csv"
        if arq.exists():
            aplicar_classificacao(con, arq, rel, agora)
        muda = sum(len(rel[k]) for k in rel if k not in ("pontos_so_no_banco", "bloqueado"))
        mexeu += muda
        extra = f"; só no banco (não apagados): {', '.join(rel['pontos_so_no_banco'])}" if rel["pontos_so_no_banco"] else ""
        print(f"{c.stem}: " + (", ".join(f"{len(v)} {k.replace('_', ' ')}" for k, v in rel.items() if v and k != "pontos_so_no_banco") or "nada a mudar") + extra)
        if not simular and muda:
            con.execute("insert into log_alteracoes(quem,o_que) values('script 71', ?)", (f"{c.stem}: " + ", ".join(f"{len(v)} {k.replace('_', ' ')}" for k, v in rel.items() if v and k != "pontos_so_no_banco"),))
    if simular:
        print(f"(simulação: nada gravado; {mexeu} mudança(s) seriam feitas)")
    else:
        con.commit()
        print(f"gravado; {mexeu} mudança(s)")
    con.close()
    return mexeu


def semear(sigla, nome):
    tx = json.loads((RAIZ / "dados" / "edital_ficticio_geral" / f"taxonomia_{sigla.upper()}.json").read_text(encoding="utf-8"))
    destino = CAT / f"{slug(nome)}.json"
    if destino.exists():
        sys.exit(f"{destino.name} já existe; não sobrescrevo.")
    hoje = datetime.date.today().isoformat()
    dados = {"disciplina": nome,
             "assuntos": [{"codigo": t["codigo"], "nome": t["nome"], "descricao": None} for t in tx["temas"]],
             "pontos": [{"codigo": p["codigo"], "assunto": p["tema"], "texto": p["nome"], "descricao": None,
                         "origem": f"edital geral v1 ({hoje})", "ativo": 1, "criado_em": hoje} for p in tx["topicos"]]}
    CAT.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{destino.name}: {len(dados['assuntos'])} assuntos, {len(dados['pontos'])} pontos. Confira e rode `aplicar {slug(nome)}`.")


def estado(args):
    """`estado mostrar` | `estado definir <disciplina> provisorio|fechado --motivo "..." [--versao v2] [--editais "..."] [--risco "..." ...] [--sim-do-usuario]`"""
    if not args or args[0] == "mostrar":
        dados = LC.carregar()
        print(f"{'catálogo':58} {'estado':11} {'versão':6} {'data':10}  riscos")
        for s in LC.catalogos():
            d = dados.get(s)
            print(f"{s[:58]:58} {LC.estado_de(s, dados):11} {(d or {}).get('versao', '-'):6} {(d or {}).get('data', '-'):10}  "
                  + ("; ".join((d or {}).get("riscos", [])) or "(sem registro: conta como provisório)"))
        return
    if args[0] != "definir" or len(args) < 3:
        sys.exit(estado.__doc__)
    slug_, novo = args[1], args[2]
    resto = args[3:]

    def opcao(nome, multi=False):
        vals = [resto[i + 1] for i, x in enumerate(resto) if x == nome and i + 1 < len(resto)]
        return vals if multi else (vals[0] if vals else None)
    motivo = opcao("--motivo")
    if not motivo:
        sys.exit("--motivo é obrigatório.")
    d = LC.definir(slug_, novo, motivo, versao=opcao("--versao"), editais=opcao("--editais"), riscos=opcao("--risco", True) or None,
                   confirmado_pelo_usuario="--sim-do-usuario" in resto)
    print(f"{slug_}: {d['estado']} ({d['versao']}, {d['data']})")


def main():
    a = sys.argv[1:]
    if a and a[0] == "estado":
        return estado(a[1:])
    if a and a[0] == "semear" and len(a) == 3:
        return semear(a[1], a[2])
    if not a or a[0] not in ("exportar", "aplicar", "conferir"):
        sys.exit(__doc__)
    cmd, resto = a[0], a[1:]
    banco = BANCO
    if "--banco" in resto:
        i = resto.index("--banco"); banco = Path(resto[i + 1]); del resto[i:i + 2]
    simular = "--simular" in resto or cmd == "conferir"
    resto = [x for x in resto if x != "--simular"]
    if cmd == "exportar":
        saida = RAIZ
        if "--saida" in resto:
            i = resto.index("--saida"); saida = Path(resto[i + 1])
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        exportar(con, saida / "dados" / "catalogo" if saida != RAIZ else CAT, saida / "dados" / "classificacao" if saida != RAIZ else CLS)
    else:
        aplicar([] if cmd == "conferir" else resto, simular, banco)


if __name__ == "__main__":
    main()
