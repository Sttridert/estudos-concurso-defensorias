"""Grupo E (Comentar): regras comuns de gravação de comentários (usadas por comentar_gravar, comentar_pendentes, comentar_exportar e 64).

Regras (decisões 40 e 59 do `02`):
  - comentário existente NUNCA é sobrescrito sem pedido (`substituir`), e um comentário `conferido` pelo usuário nunca é sobrescrito;
  - só questão `valida` recebe comentário;
  - dispositivo citado só conta como conferido se vier com TRECHO LITERAL que exista no arquivo-fonte (dados/fontes/);
    dispositivo sem trecho conferido faz o comentário entrar com `pendente_confirmacao = 1`.
"""
import importlib.util, json, re, sqlite3, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_FONTES = RAIZ / "dados" / "fontes"

TABELA_FONTES = """create table if not exists comentario_fontes (
  id integer primary key, questao_id int not null references questoes(id), dispositivo text, trecho text,
  arquivo text, url text, consultado_em text)"""


def garantir_tabela(con):
    con.execute(TABELA_FONTES)


def normalizar(t):
    """Texto sem acento, minúsculo e com espaços simples: a conferência do trecho ignora só forma, nunca palavras."""
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    return re.sub(r"\s+", " ", t).strip()


def trecho_existe(trecho, arquivo, raiz=RAIZ):
    """True se o trecho (mínimo 15 caracteres) aparece, normalizado, no arquivo-fonte dentro de dados/fontes/."""
    caminho = (raiz / arquivo).resolve()
    base = (raiz / "dados" / "fontes").resolve()
    if base not in caminho.parents or not caminho.is_file():
        return False
    n = normalizar(trecho)
    return len(n) >= 15 and n in normalizar(caminho.read_text(encoding="utf-8", errors="replace"))


def validar_entrada(chave, v, raiz=RAIZ):
    """Devolve (erros, dispositivos_sem_fonte). Formato: {"c","p","d":["Norma|dispositivo"],"pend":0/1,
    "fontes":[{"dispositivo","trecho","arquivo","url","consultado_em"}]}."""
    erros = []
    if "|" not in chave or not chave.rsplit("|", 1)[1].isdigit():
        erros.append("chave deve ser '<prova>|<número>'")
    if not isinstance(v, dict):
        return erros + ["entrada não é objeto"], []
    if not isinstance(v.get("c"), str) or not v["c"].strip():
        erros.append("falta o comentário (c)")
    if not isinstance(v.get("p", ""), str):
        erros.append("pegadinha (p) deve ser texto")
    d = v.get("d", [])
    if not isinstance(d, list) or any((not isinstance(x, str)) or "|" not in x for x in d):
        erros.append("d deve ser lista de 'Norma|dispositivo'")
        d = []
    if v.get("pend", 0) not in (0, 1):
        erros.append("pend deve ser 0 ou 1")
    conferidos = set()
    for f in v.get("fontes", []) or []:
        if not isinstance(f, dict) or not f.get("dispositivo") or not f.get("trecho") or not f.get("arquivo"):
            erros.append("cada fonte precisa de dispositivo, trecho e arquivo")
            continue
        if not f.get("consultado_em"):
            erros.append(f"fonte de {f['dispositivo']} sem consultado_em")
        if not trecho_existe(f["trecho"], f["arquivo"], raiz):
            erros.append(f"trecho de {f['dispositivo']} NÃO existe em {f['arquivo']} (ou o arquivo não está em dados/fontes/)")
        else:
            conferidos.add(normalizar(f["dispositivo"]))
    sem_fonte = [x for x in d if normalizar(x) not in conferidos]
    return erros, sem_fonte


def gravar_fontes(con, qid, fontes):
    con.execute("delete from comentario_fontes where questao_id=?", (qid,))
    for f in fontes or []:
        con.execute("insert into comentario_fontes(questao_id,dispositivo,trecho,arquivo,url,consultado_em) values(?,?,?,?,?,?)",
                    (qid, f.get("dispositivo"), f.get("trecho"), f.get("arquivo"), f.get("url"), f.get("consultado_em")))


def classificar(con, qid, substituir):
    """'novo', 'substituir', 'existe' (pular) ou 'conferido' (recusar sempre)."""
    r = con.execute("select estado from comentarios where questao_id=?", (qid,)).fetchone()
    if not r:
        return "novo"
    if r[0] == "conferido":
        return "conferido"
    return "substituir" if substituir else "existe"


def _motor():
    spec = importlib.util.spec_from_file_location("motor23", RAIZ / "scripts" / "23_motor_analise.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def universo_do_perfil(con, pid):
    """Questões válidas do universo do perfil (mesma regra do motor), como lista de dicts {id,prova,numero}."""
    m = _motor()
    p = m.carregar_perfil(con, pid)
    qs, _, _ = m.carregar_questoes(con, p, False)
    return [q for q in qs if m.em_universo(q, p["universo"]["filtro"]) and q["situacao"] in m.VALIDAS]
