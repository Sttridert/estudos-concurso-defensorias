"""Biblioteca do grupo A (Coletar): conferência de integridade das provas e vocabulário do gabarito.

Vocabulário do gabarito (`provas.gabarito_situacao`; o texto livre `provas.gabarito_status` continua como nota com fonte e data):
  definitivo   gabarito oficial final conferido (relação geral da FCC, edital de resultado ou arquivo oficial)
  preliminar   só o gabarito preliminar foi localizado (a apostila marca a tag "gabarito preliminar")
  a_confirmar  situação ainda não confirmada (também recebe a tag)
`situacao_do_status` deriva o vocabulário do texto livre pela mesma regra que `lib_escopo.gabarito_preliminar` usa para a tag.

Relatório de integridade (`relatorio_prova`): estado "conferida" ou "pendente", com os motivos. O estado é CALCULADO a cada vez
(não é gravado), para nunca ficar desatualizado. Sinais:
  contagem        questões gravadas contra o número esperado da prova
  alternativas    questões válidas com alguma alternativa A a E vazia
  gabarito        questões não anuladas sem letra de gabarito
  situacao        gabarito diferente de "definitivo"
  texto_revisar   questões marcadas `revisar_texto` (extração incompleta, OCR ou alternativas faltando)
  ocr             caderno lido por OCR (informação; as questões entram em `texto_revisar` quando `coletar_ingerir_prova` as marcou)
  atencao         (informa, NÃO torna a prova pendente) questões com muitas palavras que não aparecem em nenhuma outra prova
                  do banco: sinal de erro de leitura, só um "onde olhar" (calibração com as 53 questões já marcadas: apontou 39%
                  delas e 6% das válidas). Questões de Língua Portuguesa ficam fora desse sinal, porque citam textos literários.
"""
import re
import unicodedata
from collections import defaultdict

SITUACOES = ("definitivo", "preliminar", "a_confirmar")
LIMIAR_VOCABULARIO = 0.15   # fração de palavras "só desta prova" que faz a questão entrar em atenção


def _sem_acento(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def situacao_do_status(status):
    """Deriva `definitivo | preliminar | a_confirmar` do texto livre de `gabarito_status`; None se não reconhecer."""
    t = _sem_acento(status).replace("_", " ").strip()
    if t.startswith("preliminar"):
        return "preliminar"
    if t.startswith("a confirmar"):
        return "a_confirmar"
    if t.startswith(("definitivo", "oficial", "conferido")):
        return "definitivo"
    return None


def _palavras(texto):
    return [w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{3,}", texto or "")]


def _texto_questao(q):
    return " ".join(str(q[k] or "") for k in ("enunciado", "alt_a", "alt_b", "alt_c", "alt_d", "alt_e"))


def provas_por_palavra(con):
    """Para cada palavra, o conjunto de provas em que aparece (base do sinal de vocabulário)."""
    pd = defaultdict(set)
    for pid, *campos in con.execute("select prova_id, enunciado, alt_a, alt_b, alt_c, alt_d, alt_e from questoes"):
        for w in set(_palavras(" ".join(str(c or "") for c in campos))):
            pd[w].add(pid)
    return pd


def fracao_fora_do_vocabulario(texto, prova_id, pd):
    """Fração das palavras do texto que não aparecem em nenhuma OUTRA prova do banco."""
    ws = _palavras(texto)
    if not ws:
        return 0.0
    return sum(1 for w in ws if not (pd.get(w, set()) - {prova_id})) / len(ws)


def relatorio_prova(con, prova_id, pd=None):
    """Devolve um dicionário com o estado e os motivos da prova. `con.row_factory` precisa ser sqlite3.Row."""
    p = con.execute("select * from provas where id=?", (prova_id,)).fetchone()
    qs = con.execute("""select q.*, d.nome as disc_nome from questoes q left join disciplinas d on d.id=q.disciplina_id
                        where q.prova_id=? order by q.numero""", (prova_id,)).fetchall()
    pd = pd if pd is not None else provas_por_palavra(con)
    motivos = []
    esperado = p["n_questoes_esperado"]
    if esperado is not None and len(qs) != esperado:
        motivos.append(f"contagem: {len(qs)} questões gravadas, {esperado} esperadas")
    validas = [q for q in qs if q["situacao"] != "anulada"]
    sem_alt = [q["numero"] for q in validas if not all(q[f"alt_{x}"] for x in "abcde")]
    if sem_alt:
        motivos.append(f"alternativas incompletas em {len(sem_alt)} questões: {sem_alt}")
    sem_gab = [q["numero"] for q in validas if not q["gabarito"]]
    if sem_gab:
        motivos.append(f"sem letra de gabarito em {len(sem_gab)} questões: {sem_gab}")
    situacao = p["gabarito_situacao"] if "gabarito_situacao" in p.keys() else situacao_do_status(p["gabarito_status"])
    if situacao != "definitivo":
        motivos.append(f"gabarito {situacao or 'sem situação definida'}")
    revisar = [q["numero"] for q in qs if q["situacao"] == "revisar_texto"]
    if revisar:
        motivos.append(f"{len(revisar)} questões em revisar_texto: {revisar}")
    atencao = [q["numero"] for q in validas
               if "portugu" not in _sem_acento(q["disc_nome"])
               and fracao_fora_do_vocabulario(_texto_questao(q), prova_id, pd) >= LIMIAR_VOCABULARIO and q["numero"] not in revisar]
    return {"prova": p["nome"], "estado": "pendente" if motivos else "conferida", "motivos": motivos,
            "atencao": atencao, "questoes": len(qs), "esperado": esperado, "ocr": bool(p["caderno_lido_por_ocr"]), "situacao_gabarito": situacao,
            "anuladas": sum(1 for q in qs if q["situacao"] == "anulada")}
