"""Escopo de um perfil por BLOCO DO EDITAL (decisão 41 do usuário, 15/11/2026; plano 05, item A1).

Regra (vale para QUALQUER edital; nada aqui depende de um edital, sigla de bloco ou órgão):
  Com edital real, a apostila segue as disciplinas do edital. O perfil guarda `bloco_edital` (a sigla do bloco no artefato do
  `edital_id` do perfil; tabela `edital_blocos`). As questões da apostila são todas as classificadas (ponto principal ou
  secundário) em pontos TOCADOS por frases desse bloco (`edital_frase_destinos`), qualquer que seja a disciplina de origem,
  mais as da disciplina do perfil (que continuam entrando, como hoje, mesmo nos pontos fora do edital).
  Sem `bloco_edital`, o perfil continua por disciplina do catálogo (organização padrão).

Funções:
  escopo(con, perfil)                       -> None (perfil por disciplina) ou {"bloco","edital_id","toca"(ids de pontos),"titulo"}
  clausula(esc, disc_id)                    -> (trecho SQL, parâmetros) para `where` sobre `questoes q` e `classificacao c`
  pontos_do_escopo(con, perfil, esc)        -> {id: (codigo, texto, assunto_id)} (disciplina do perfil + pontos tocados)
  assuntos_do_escopo(con, pontos)           -> {id: (codigo, nome)}
  efetivos(esc, disc_perfil, disc_q, p1, p2, validos) -> (p1, p2) que valem na apostila
  blocos_por_ponto(con, edital_id)          -> {ponto_id: {siglas dos blocos cujas frases tocam o ponto}}
  titulos_blocos(con, edital_id)            -> {sigla: título legível}
  bloco_do_perfil(con, perfil)              -> sigla do bloco do perfil (explícito ou o único bloco da disciplina do perfil)
"""
import re
import sqlite3
import sys
import unicodedata


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tem_blocos(con, edital_id):
    try:
        return con.execute("select count(*) from edital_blocos where edital_id=?", (edital_id,)).fetchone()[0] > 0
    except sqlite3.OperationalError:
        return False


def escopo(con, perfil):
    bloco = perfil.get("bloco_edital")
    if not bloco:
        return None
    eid = perfil.get("edital_id")
    if not eid or not tem_blocos(con, eid):
        sys.exit(f"O perfil pede o bloco «{bloco}», mas o edital {eid} não tem blocos gravados (rode os scripts 50, 51 e 52).")
    blocos = {s: t for s, t in con.execute("select sigla, titulo_no_edital from edital_blocos where edital_id=?", (eid,))}
    if bloco not in blocos:
        sys.exit(f"O bloco «{bloco}» não existe no edital {eid}. Blocos do edital: " + "; ".join(f"{s} ({t})" for s, t in blocos.items()))
    toca = {r[0] for r in con.execute("""select distinct d.ponto_id from edital_frase_destinos d join edital_frases f on f.id=d.frase_id
                                         where f.edital_id=? and f.disciplina_edital=? and d.ponto_id is not null""", (eid, bloco))}
    return {"bloco": bloco, "edital_id": eid, "toca": toca, "titulo": blocos[bloco]}


def clausula(esc, disc_id, c="c"):
    """Condição sobre `questoes q` e `classificacao c`: disciplina do perfil OU ponto (principal ou secundário) tocado pelo bloco."""
    if esc is None:
        return "q.disciplina_id=?", [disc_id]
    ids = sorted(esc["toca"]) or [-1]
    ph = ",".join("?" * len(ids))
    return f"(q.disciplina_id=? or {c}.ponto_id in ({ph}) or {c}.ponto2_id in ({ph}))", [disc_id, *ids, *ids]


def pontos_do_escopo(con, perfil, esc, so_ativos=False):
    extra = " and ativo=1" if so_ativos else ""
    if esc is None:
        return {i: (c, t, a) for i, c, t, a in con.execute(f"select id,codigo,texto,assunto_id from pontos where disciplina_id=?{extra}", (perfil["disciplina_id"],))}
    ids = sorted(esc["toca"]) or [-1]
    ph = ",".join("?" * len(ids))
    return {i: (c, t, a) for i, c, t, a in con.execute(
        f"select id,codigo,texto,assunto_id from pontos where (disciplina_id=? or id in ({ph})){extra}", (perfil["disciplina_id"], *ids))}


def assuntos_do_escopo(con, pontos):
    ids = sorted({a for _, _, a in pontos.values()}) or [-1]
    ph = ",".join("?" * len(ids))
    return {i: (c, n) for i, c, n in con.execute(f"select id,codigo,nome from assuntos where id in ({ph})", ids)}


def efetivos(esc, disc_perfil, disc_q, p1, p2, validos):
    """Pontos que valem na apostila para uma questão. Questão da disciplina do perfil: como está (secundário fora do escopo some).
    Questão de outra disciplina: só os pontos tocados pelo bloco (o tocado vira o principal se o principal não for tocado)."""
    if esc is None:
        return p1, p2
    if disc_q == disc_perfil:
        # principal ou secundário fora do escopo some (a questão da disciplina continua entrando; ex.: questão de Princípios da Defensoria
        # classificada num tópico de Penal depois da publicação do catálogo v2, decisão 54)
        return (p1 if p1 in validos else None), (p2 if p2 in validos else None)
    t = [p for p in (p1, p2) if p is not None and p in esc["toca"]]
    return (t[0] if t else None), (t[1] if len(t) > 1 else None)


def blocos_por_ponto(con, edital_id):
    out = {}
    for pid, sigla in con.execute("""select distinct d.ponto_id, f.disciplina_edital from edital_frase_destinos d join edital_frases f on f.id=d.frase_id
                                     where f.edital_id=? and d.ponto_id is not null""", (edital_id,)):
        out.setdefault(pid, set()).add(sigla)
    return out


def _acentuar(con):
    """palavra sem acento (minúscula) -> forma acentuada, aprendida dos nomes de disciplinas e assuntos do catálogo"""
    d = {}
    for (n,) in list(con.execute("select nome from disciplinas")) + list(con.execute("select nome from assuntos")):
        for w in re.findall(r"[A-Za-zÀ-ÿ]+", n):
            d.setdefault(_sem_acento(w).lower(), w.lower())
    return d


def titulo_legivel(con, titulo):
    """Título do bloco como está no edital (às vezes em maiúsculas e sem acento) em caixa de título, com acentos do catálogo."""
    if titulo != titulo.upper() and not titulo.isascii():
        return titulo
    ac = _acentuar(con)
    peq = {"de", "da", "do", "das", "dos", "e", "a", "o", "em", "para", "com"}
    saida = []
    for i, w in enumerate(re.findall(r"[A-Za-zÀ-ÿ]+|[^A-Za-zÀ-ÿ]+", titulo)):
        if re.match(r"[A-Za-zÀ-ÿ]", w):
            b = ac.get(_sem_acento(w).lower(), w.lower())
            w = b if (b in peq and i > 0) else b[:1].upper() + b[1:]
        saida.append(w)
    return "".join(saida)


def titulos_blocos(con, edital_id):
    if not edital_id or not tem_blocos(con, edital_id):
        return {}
    return {s: titulo_legivel(con, t) for s, t in con.execute("select sigla, titulo_no_edital from edital_blocos where edital_id=?", (edital_id,))}


def bloco_do_perfil(con, perfil):
    """Sigla do bloco do perfil: a explícita (`bloco_edital`) ou, se o edital tem um único bloco da disciplina do perfil, esse."""
    if perfil.get("bloco_edital"):
        return perfil["bloco_edital"]
    eid = perfil.get("edital_id")
    if not eid or not tem_blocos(con, eid):
        return None
    r = [s for (s,) in con.execute("select sigla from edital_blocos where edital_id=? and disciplina_id=?", (eid, perfil["disciplina_id"]))]
    return r[0] if len(r) == 1 else None


def gabarito_preliminar(status):
    """Tag "gabarito preliminar" (decisão 41, item 5): `provas.gabarito_status` preliminar ou a confirmar.
    Quando a pesquisa na web achar anulação ou gabarito definitivo, o status da prova é atualizado e a tag some."""
    t = _sem_acento(status or "").lower().replace("_", " ").strip()
    return t.startswith("preliminar") or t.startswith("a confirmar")
