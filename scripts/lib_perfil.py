"""Perfil como ARQUIVO na pasta do concurso (plano 06, Etapa 2b; decisão 46).

Cada concurso tem uma pasta em `produtos/apostilas/<concurso>/` com um `perfil.toml` (dados comuns do concurso + uma entrada
`[[apostila]]` por apostila/bloco) e as apostilas ao lado. O ARQUIVO é a ÚNICA fonte do perfil: a tabela `perfis` do banco foi aposentada em 16/11/2026
(renomeada `perfis_aposentada_2026_11_16`, só histórico; decisão 47).

Confirmação: cada apostila guarda `confirmado_em` e `confirmado_hash` (impressão digital dos campos que definem o perfil). Se alguém
muda banca, cargo, órgão, edital, universo, pesos, meia-vida, disciplina ou bloco SEM reconfirmar (`72_perfil.py confirmar`), o hash
deixa de bater e o perfil conta como NÃO confirmado: o motor e o gerador recusam.

Segunda impressão digital, a da BASE (grupo D, 20/11/2026): além do perfil, a confirmação registra o hash do que a apostila usa de
fora do perfil, só conteúdo e sem datas: (a) o CATÁLOGO do escopo da apostila (assuntos e tópicos, com código e texto) e (b) o EDITAL
classificado do bloco (bloco, frases, destinos frase→tópico, tópicos fora do edital). Se a base mudou depois da confirmação, o perfil conta
como não confirmado e a mensagem diz qual das duas partes mudou. Confirmação anterior à base (sem os dois campos) continua valendo, com
AVISO no stderr, até ser refeita com `72_perfil.py confirmar`. Só a base DA APOSTILA entra: mexer em Civil não derruba Penal.
`edital_slug` (pasta em dados/editais_reais/) liga o perfil ao edital de origem; é conferido contra `edital_id`, mas fica fora do hash do perfil.
"""
import hashlib, json, sys, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_escopo as LE

RAIZ = Path(__file__).resolve().parent.parent
APOSTILAS = RAIZ / "produtos" / "apostilas"
_AVISADOS = set()
CAMPOS_COMUNS = ("banca", "carreira", "cargo", "orgao", "ano_referencia", "edital_id", "meia_vida", "estudo_geral")


def achar_arquivos():
    return sorted(APOSTILAS.glob("*/perfil.toml"))


def ler(arq):
    with open(arq, "rb") as f:
        c = tomllib.load(f)
    c.setdefault("apostila", [])      # concurso recém-criado, ainda sem apostilas
    return c


def impressao(c, a):
    """hash dos campos que definem o perfil efetivo (não inclui nome, observações nem datas)"""
    base = {k: c.get(k) for k in CAMPOS_COMUNS}
    base["pesos"] = c.get("pesos")
    base["universo"] = {"nome": (c.get("universo") or {}).get("nome"), "filtro": (c.get("universo") or {}).get("filtro")}
    base["disciplina"] = a.get("disciplina")
    base["bloco"] = a.get("bloco")
    return hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def edital_problemas(con, c):
    """Problemas na ligação perfil → edital de origem (lista de textos; vazia = ok). Sem `edital_slug` não há o que conferir."""
    slug = c.get("edital_slug")
    if not slug:
        return []
    pasta = RAIZ / "dados" / "editais_reais" / slug
    if not (pasta / "programa.json").exists():
        return [f"edital_slug «{slug}»: não existe dados/editais_reais/{slug}/programa.json."]
    prog = json.loads((pasta / "programa.json").read_text(encoding="utf-8")).get("edital", {})
    if prog.get("slug") != slug:
        return [f"edital_slug «{slug}»: o programa.json diz que o slug dele é «{prog.get('slug')}»."]
    r = con.execute("select nome from editais where id=?", (c.get("edital_id"),)).fetchone()
    if not r:
        return [f"edital_id {c.get('edital_id')} não existe na tabela editais."]
    if prog.get("pasta") and prog["pasta"] not in r[0]:
        return [f"edital_slug «{slug}» (pasta «{prog['pasta']}») não corresponde ao edital_id {c['edital_id']} («{r[0]}»)."]
    return []


def impressao_base(con, c, a):
    """{'catalogo': hash, 'edital': hash} do que a apostila usa de fora do perfil (só conteúdo, sem datas, sem estado de conferência)
    ou None se não der para calcular (disciplina ou bloco inexistente: o perfil_do_arquivo já reclama disso)."""
    d = con.execute("select id from disciplinas where nome=?", (a.get("disciplina"),)).fetchone()
    if not d:
        return None
    perfil = {"disciplina_id": d[0], "bloco_edital": a.get("bloco"), "edital_id": c.get("edital_id")}
    try:
        esc = LE.escopo(con, perfil)
    except SystemExit:
        return None
    pontos = LE.pontos_do_escopo(con, perfil, esc, so_ativos=True)
    assuntos = LE.assuntos_do_escopo(con, pontos)
    cat = sorted((codigo, texto, assuntos.get(ass, ("", ""))[0], assuntos.get(ass, ("", ""))[1]) for codigo, texto, ass in pontos.values())
    if esc is None:
        return {"catalogo": _h(cat), "edital": "-"}
    eid, bloco = esc["edital_id"], esc["bloco"]
    b = con.execute("select titulo_no_edital, disciplina_id, ordem from edital_blocos where edital_id=? and sigla=?", (eid, bloco)).fetchone()
    frases = []
    for fid, ordem, rot, fo, cod, txt in con.execute("""select id, item_ordem, item_rotulo, frase_ordem, codigo, texto from edital_frases
                                                        where edital_id=? and disciplina_edital=?""", (eid, bloco)):
        dest = sorted((pc or "", papel or "", trecho or "") for pc, papel, trecho in con.execute(
            """select p.codigo, d.papel, d.trecho from edital_frase_destinos d left join pontos p on p.id=d.ponto_id where d.frase_id=?""", (fid,)))
        frases.append((ordem or 0, rot or "", fo or 0, cod, txt, dest))
    ids = sorted(pontos) or [-1]
    fora = sorted(r[0] for r in con.execute(
        f"select p.codigo from edital_pontos_fora f join pontos p on p.id=f.ponto_id where f.edital_id=? and f.ponto_id in ({','.join('?' * len(ids))})", (eid, *ids)))
    return {"catalogo": _h(cat), "edital": _h({"bloco": list(b) if b else None, "frases": sorted(frases, key=lambda x: (x[0], x[2], x[3])), "fora": fora})}


def estado(con, c, a):
    """(código, detalhe) da confirmação de UMA apostila:
    'confirmada' | 'nunca' | 'perfil_alterado' | 'base_alterada' (detalhe = partes que mudaram) | 'sem_base' (confirmada antes da impressão da base)"""
    if not a.get("confirmado_em"):
        return "nunca", ""
    if a.get("confirmado_hash") != impressao(c, a):
        return "perfil_alterado", ""
    if a.get("confirmado_catalogo") is None and a.get("confirmado_edital") is None:
        return "sem_base", ""
    atual = impressao_base(con, c, a)
    if atual is None:
        return "base_alterada", "a base (não foi possível calculá-la: disciplina ou bloco do edital sumiu)"
    mudou = [rot for rot, k in (("o CATÁLOGO da disciplina", "catalogo"), ("o EDITAL classificado do bloco", "edital")) if a.get(f"confirmado_{k}") != atual[k]]
    return ("base_alterada", " e ".join(mudou)) if mudou else ("confirmada", "")


def procurar(pid):
    """(arquivo, concurso, apostila) do perfil com esse id, ou None"""
    for arq in achar_arquivos():
        c = ler(arq)
        for a in c.get("apostila", []):
            if a.get("id") == pid:
                return arq, c, a
    return None


def proximo_id(con):
    """id novo e único: maior id de qualquer perfil.toml (e da tabela aposentada, para não repetir nome de arquivo de saída) + 1"""
    ids = [a.get("id", 0) for arq in achar_arquivos() for a in ler(arq).get("apostila", [])]
    try:
        ids += [i for (i,) in con.execute("select id from perfis_aposentada_2026_11_16")]
    except Exception:
        pass
    return max(ids + [0]) + 1


def perfil_do_arquivo(con, pid):
    """dict do perfil (chaves da antiga tabela `perfis`, mais `pasta` e `universo_arquivo`), montado do arquivo; None se não houver arquivo"""
    achou = procurar(pid)
    if not achou:
        return None
    arq, c, a = achou
    d = con.execute("select id from disciplinas where nome=?", (a["disciplina"],)).fetchone()
    if not d:
        sys.exit(f"{arq}: disciplina '{a['disciplina']}' não existe no banco.")
    u = c.get("universo") or {}
    uid = None
    if u.get("nome"):
        r = con.execute("select id,filtro from universos where nome=?", (u["nome"],)).fetchone()
        if r:
            uid = r[0]
            if json.loads(r[1]) != (u.get("filtro") or {}):
                if u["nome"] not in _AVISADOS:
                    _AVISADOS.add(u["nome"])
                    print(f"AVISO: o universo «{u['nome']}» do arquivo difere do da tabela `universos`; vale o do ARQUIVO.", file=sys.stderr)
    st, det = estado(con, c, a)
    if st == "sem_base" and pid not in _AVISADOS:
        _AVISADOS.add(pid)
        print(f"AVISO: a confirmação do perfil {pid} é anterior à impressão da base (catálogo e edital); vale, mas refaça com `72_perfil.py confirmar` "
              "quando for gerar a apostila.", file=sys.stderr)
    p = {"id": pid, "nome": a.get("nome") or c.get("nome"), "disciplina_id": d[0], "banca": c.get("banca"), "carreira": c.get("carreira"),
         "cargo": c.get("cargo"), "orgao": c.get("orgao") or None, "ano_referencia": c.get("ano_referencia"), "edital_id": c.get("edital_id"),
         "pesos_grupo": json.dumps(c.get("pesos") or {"A": 1, "B": 0.5, "C": 0.25}), "meia_vida": c.get("meia_vida", 8),
         "estudo_geral": int(bool(c.get("estudo_geral"))), "confirmado_pelo_usuario": int(st in ("confirmada", "sem_base")),
         "confirmado_em": a.get("confirmado_em"), "observacoes": a.get("observacoes"), "universo_id": uid, "bloco_edital": a.get("bloco"),
         "pasta": arq.parent, "arquivo_perfil": arq, "edital_slug": c.get("edital_slug"), "editais_anteriores": c.get("editais_anteriores") or [],
         "universo_arquivo": {"id": uid, "nome": u.get("nome") or "Todas as questões", "descricao": u.get("descricao") or "", "filtro": u.get("filtro") or {}}}
    if st == "base_alterada":
        p["motivo_nao_confirmado"] = (f"Depois da confirmação de {a['confirmado_em']} mudou {det} usado pelo perfil {pid}. Mostre o perfil ao usuário "
                                      "(`72_perfil.py mostrar`) e, com a confirmação dele, rode `72_perfil.py confirmar`.")
    if st == "perfil_alterado":
        p["motivo_nao_confirmado"] = (f"O perfil {pid} foi ALTERADO depois da confirmação de {a['confirmado_em']} (o arquivo {arq.parent.name}/perfil.toml "
                                      "não bate com a impressão digital). Mostre o perfil ao usuário e, com a confirmação dele, rode `72_perfil.py confirmar`.")
    return p


# ------------------------------------------------------------------ escrita (TOML simples)
def _v(x):
    if x is None:
        return None
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (int, float)):
        return repr(x) if isinstance(x, float) else str(x)
    if isinstance(x, str):
        return json.dumps(x, ensure_ascii=False)
    if isinstance(x, list):
        return "[" + ", ".join(_v(i) for i in x) + "]"
    if isinstance(x, dict):
        return "{ " + ", ".join(f"{k} = {_v(v)}" for k, v in x.items()) + " }"
    raise TypeError(type(x))


def escrever(arq, c):
    L = ["# perfil.toml: perfil do concurso (ÚNICA fonte do perfil; a tabela `perfis` do banco foi aposentada). Plano 06, Etapa 2b.",
         "# ATENÇÃO: mudar banca, cargo, órgão, edital, universo, pesos, meia-vida, disciplina ou bloco invalida a confirmação",
         "# (o motor e o gerador recusam). Depois de mostrar ao usuário e ter o \"sim\" dele: scripts/72_perfil.py confirmar.", ""]
    for k in ("nome", "banca", "carreira", "cargo", "orgao", "ano_referencia", "edital_id", "edital_slug", "editais_anteriores", "meia_vida", "estudo_geral"):
        if c.get(k) is not None:
            L.append(f"{k} = {_v(c[k])}")
    L.append(f"pesos = {_v(c['pesos'])}")
    L += ["", "[universo]"]
    for k in ("nome", "descricao", "filtro"):
        if c["universo"].get(k) is not None:
            L.append(f"{k} = {_v(c['universo'][k])}")
    for a in c["apostila"]:
        L += ["", "[[apostila]]"]
        for k in ("id", "disciplina", "bloco", "nome", "confirmado_em", "confirmado_hash", "confirmado_catalogo", "confirmado_edital", "observacoes"):
            if a.get(k) not in (None, ""):
                L.append(f"{k} = {_v(a[k])}")
    arq.write_text("\n".join(L) + "\n", encoding="utf-8")
