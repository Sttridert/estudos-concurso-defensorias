"""Perfil como ARQUIVO na pasta do concurso (plano 06, Etapa 2b; decisão 46).

Cada concurso tem uma pasta em `produtos/apostilas/<concurso>/` com um `perfil.toml` (dados comuns do concurso + uma entrada
`[[apostila]]` por apostila/bloco) e as apostilas ao lado. O ARQUIVO é a ÚNICA fonte do perfil: a tabela `perfis` do banco foi aposentada em 16/11/2026
(renomeada `perfis_aposentada_2026_11_16`, só histórico; decisão 47).

Confirmação: cada apostila guarda `confirmado_em` e `confirmado_hash` (impressão digital dos campos que definem o perfil). Se alguém
muda banca, cargo, órgão, edital, universo, pesos, meia-vida, disciplina ou bloco SEM reconfirmar (`72_perfil.py confirmar`), o hash
deixa de bater e o perfil conta como NÃO confirmado: o motor e o gerador recusam.
"""
import hashlib, json, sys, tomllib
from pathlib import Path

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
    bate = a.get("confirmado_hash") == impressao(c, a)
    p = {"id": pid, "nome": a.get("nome") or c.get("nome"), "disciplina_id": d[0], "banca": c.get("banca"), "carreira": c.get("carreira"),
         "cargo": c.get("cargo"), "orgao": c.get("orgao") or None, "ano_referencia": c.get("ano_referencia"), "edital_id": c.get("edital_id"),
         "pesos_grupo": json.dumps(c.get("pesos") or {"A": 1, "B": 0.5, "C": 0.25}), "meia_vida": c.get("meia_vida", 8),
         "estudo_geral": int(bool(c.get("estudo_geral"))), "confirmado_pelo_usuario": int(bate and bool(a.get("confirmado_em"))),
         "confirmado_em": a.get("confirmado_em"), "observacoes": a.get("observacoes"), "universo_id": uid, "bloco_edital": a.get("bloco"),
         "pasta": arq.parent, "arquivo_perfil": arq,
         "universo_arquivo": {"id": uid, "nome": u.get("nome") or "Todas as questões", "descricao": u.get("descricao") or "", "filtro": u.get("filtro") or {}}}
    if a.get("confirmado_em") and not bate:
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
    for k in ("nome", "banca", "carreira", "cargo", "orgao", "ano_referencia", "edital_id", "meia_vida", "estudo_geral"):
        if c.get(k) is not None:
            L.append(f"{k} = {_v(c[k])}")
    L.append(f"pesos = {_v(c['pesos'])}")
    L += ["", "[universo]"]
    for k in ("nome", "descricao", "filtro"):
        if c["universo"].get(k) is not None:
            L.append(f"{k} = {_v(c['universo'][k])}")
    for a in c["apostila"]:
        L += ["", "[[apostila]]"]
        for k in ("id", "disciplina", "bloco", "nome", "confirmado_em", "confirmado_hash", "observacoes"):
            if a.get(k) not in (None, ""):
                L.append(f"{k} = {_v(a[k])}")
    arq.write_text("\n".join(L) + "\n", encoding="utf-8")
