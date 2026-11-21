"""GRUPO F (Produzir): semáforo do porteiro e impressão digital das apostilas. Só leitura do banco; usado por `70`, `24` e `produzir_status.py`.

SEMÁFORO  verificar(con, perfil) -> lista de Achado(nivel, codigo, texto)
  BLOQUEIA  não se deve gerar (o `24` recusa; só gera com `--gerar-mesmo-assim "motivo"`, e a capa registra o motivo). Perfil não confirmado
            é recusado antes, pelo motor, e nem "mesmo assim" supera: só o usuário confirma
  AVISA     pode gerar, mas a apostila sai com a pendência declarada na capa
  INFORMA   só um número ou fato útil (não aparece na capa)

IMPRESSÃO DIGITAL  insumos(con, perfil) -> {parte: hash} de tudo o que muda o conteúdo da apostila (perfil, catálogo, edital do bloco,
  questões do universo, classificação, comentários e código gerador). `registrar`/`ler_registro` guardam em `impressoes.json`, na pasta do
  concurso (uma chave por perfil); `desatualizado(registro, atual)` diz quais partes mudaram desde que a apostila foi gerada.
"""
import collections
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import lib_escopo as LE  # noqa: E402
import lib_perfil as LP  # noqa: E402

BLOQUEIA, AVISA, INFORMA = "bloqueia", "avisa", "informa"
CODIGO_GERADOR = ("23_motor_analise.py", "24_gerar_apostila.py", "apostila_lib.py", "lib_escopo.py", "lib_edital_classificado.py", "lib_novidades_edital.py")
_motor = None


def motor():
    """o `23` (nome começa com número, então carrega por caminho)"""
    global _motor
    if _motor is None:
        spec = importlib.util.spec_from_file_location("motor23_sem", AQUI / "23_motor_analise.py")
        _motor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_motor)
    return _motor


class Achado(collections.namedtuple("Achado", "nivel codigo texto capa", defaults=(None,))):
    """`texto` é para o terminal; `capa`, quando existe, é a frase (para o leitor) que a capa da apostila declara como pendência"""



def carregar_perfil(con, pid):
    """como `23.carregar_perfil`, mas SEM recusar perfil não confirmado (o semáforo é que o declara); None se o perfil não existe"""
    p = LP.perfil_do_arquivo(con, pid)
    if p is None:
        return None
    p["pesos"] = json.loads(p["pesos_grupo"])
    p["orgao_ativo"] = bool(p.get("orgao") and con.execute(
        "select count(*) from provas where lower(instituicao)=lower(?) and lower(cargo)=lower(?) and lower(banca)=lower(?) and lower(carreira)=lower(?)",
        (p["orgao"], p["cargo"], p["banca"], p["carreira"])).fetchone()[0])
    p["universo"] = p["universo_arquivo"]
    return p


def questoes_do_universo(con, perfil):
    """questões que a apostila usa: as do escopo do perfil dentro do universo (mesma seleção do motor), qualquer situação"""
    M = motor()
    qs, _, _ = M.carregar_questoes(con, perfil, False)
    filtro = perfil["universo"]["filtro"]
    return [q for q in qs if M.em_universo({"banca": q["banca"], "carreira": q["carreira"], "cargo": q["cargo"], "inst": q["inst"], "ano": q["ano"]}, filtro)]


def _ph(ids):
    return ",".join("?" * len(ids)) or "NULL"


def verificar(con, perfil):
    """semáforo de UM perfil (dict de `lib_perfil.perfil_do_arquivo`). Não grava nada."""
    M = motor()
    out = []
    # --- confirmação do perfil
    if not perfil.get("confirmado_pelo_usuario"):
        out.append(Achado(BLOQUEIA, "perfil_nao_confirmado", perfil.get("motivo_nao_confirmado") or "perfil ainda não confirmado pelo usuário"))
    achou = LP.procurar(perfil["id"])
    if achou:
        _, c, a = achou
        st, det = LP.estado(con, c, a)
        if st == "sem_base":
            out.append(Achado(AVISA, "confirmacao_antiga", "a confirmação do perfil é anterior à impressão da base (catálogo e edital); refazer com `72 confirmar` quando o usuário aprovar"))
        for prob in LP.edital_problemas(con, c):
            out.append(Achado(BLOQUEIA, "edital_do_perfil", prob))
    # --- edital
    eid = perfil.get("edital_id")
    if eid:
        tipo = con.execute("select tipo from editais where id=?", (eid,)).fetchone()
        if tipo and tipo[0] == "real" and not LE.tem_blocos(con, eid):
            out.append(Achado(BLOQUEIA, "edital_sem_artefato", f"o edital {eid} é real e não tem artefato (frases e blocos): montar com os scripts 50, 51 e 52"))
    # --- catálogo
    if not con.execute("select count(*) from pontos where disciplina_id=? and ativo=1", (perfil["disciplina_id"],)).fetchone()[0]:
        out.append(Achado(BLOQUEIA, "catalogo_vazio", "o catálogo da disciplina não tem tópicos ativos"))
    # --- questões do universo
    qs = questoes_do_universo(con, perfil)
    validas = [q for q in qs if q["situacao"] in M.VALIDAS]
    ids = [q["id"] for q in qs]
    provas = {q["prova"] for q in validas}
    if not validas:
        out.append(Achado(BLOQUEIA, "sem_questoes", "nenhuma questão válida no universo do perfil nesta disciplina ou bloco"))
        return out
    out.append(Achado(INFORMA, "amostra", f"{len(validas)} questões válidas de {len(provas)} provas ({len(qs) - len(validas)} anuladas ou fora)"))
    if len(provas) < 5:
        out.append(Achado(AVISA, "amostra_pequena", f"só {len(provas)} provas no universo: teste retroativo com menos de 5 provas é ruído (regra do projeto)",
                          f"Amostra pequena: só {len(provas)} provas. Use o histórico para ordenar o estudo, não para cortar conteúdo."))
    sem_com = con.execute(f"select count(*) from questoes q where q.id in ({_ph(ids)}) and q.situacao in ('valida','revisar_texto') and not exists (select 1 from comentarios c where c.questao_id=q.id)", ids).fetchone()[0]
    if sem_com:
        out.append(Achado(BLOQUEIA, "sem_comentario", f"{sem_com} questões do universo sem comentário (decisão 40: comentar antes de gerar)"))
    pend = con.execute(f"select count(*) from comentarios where questao_id in ({_ph(ids)}) and pendente_confirmacao=1", ids).fetchone()[0]
    if pend:
        out.append(Achado(AVISA, "comentario_confirmar", f"{pend} comentários marcados \"confirmar\" (dúvida de fonte, lei ou jurisprudência)",
                          f"{pend} {'comentário marcado' if pend == 1 else 'comentários marcados'} \"confirmar\": confira a fonte antes de confiar."))
    n_rasc = con.execute(f"select count(*) from comentarios where questao_id in ({_ph(ids)}) and estado<>'conferido'", ids).fetchone()[0]
    if n_rasc:
        out.append(Achado(INFORMA, "comentario_rascunho", f"{n_rasc} comentários ainda são rascunho da IA (não conferidos pelo usuário)"))
    prelim = con.execute(f"""select count(*) from questoes q join provas p on p.id=q.prova_id where q.id in ({_ph(ids)})
                             and (lower(coalesce(p.gabarito_status,'')) like 'preliminar%' or lower(coalesce(p.gabarito_status,'')) like 'a confirmar%' or lower(coalesce(p.gabarito_status,'')) like 'a_confirmar%')""", ids).fetchone()[0]
    if prelim:
        out.append(Achado(AVISA, "gabarito_preliminar", f"{prelim} questões de provas com gabarito preliminar ou a confirmar",
                          f"{prelim} {'questão' if prelim == 1 else 'questões'} com gabarito preliminar (marcadas no cartão)."))
    n_sem_class = con.execute("select count(*) from questoes q left join classificacao c on c.questao_id=q.id where q.disciplina_id=? and q.situacao in ('valida','revisar_texto') and c.questao_id is null",
                              (perfil["disciplina_id"],)).fetchone()[0]
    if n_sem_class:
        out.append(Achado(AVISA, "sem_classificacao", f"{n_sem_class} questões da disciplina ainda sem classificação (no banco todo; as do universo que faltarem não entram na apostila)",
                          f"{n_sem_class} {'questão' if n_sem_class == 1 else 'questões'} da disciplina ainda sem classificação: não entram nesta apostila."))
    n_rev = con.execute(f"select count(*) from classificacao where questao_id in ({_ph(ids)}) and coalesce(revisada,0)=0", ids).fetchone()[0]
    if n_rev:
        out.append(Achado(INFORMA, "classificacao_rascunho", f"{n_rev} classificações ainda são rascunho da IA (não revisadas pelo usuário)"))
    return out


def pior(achados):
    """nível mais grave presente (bloqueia > avisa > informa), ou None"""
    for n in (BLOQUEIA, AVISA, INFORMA):
        if any(a.nivel == n for a in achados):
            return n
    return None


# ------------------------------------------------------------------ impressão digital
def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]


def insumos(con, perfil):
    """{parte: hash} do que muda o conteúdo da apostila; sem datas nem campos que mudam sozinhos"""
    achou = LP.procurar(perfil["id"])
    c, a = achou[1], achou[2]
    base = LP.impressao_base(con, c, a) or {}
    ids = sorted(q["id"] for q in questoes_do_universo(con, perfil))
    ph = _ph(ids)
    q_rows = con.execute(f"""select q.id,q.enunciado,q.alt_a,q.alt_b,q.alt_c,q.alt_d,q.alt_e,q.gabarito,q.situacao,p.gabarito_status
                             from questoes q join provas p on p.id=q.prova_id where q.id in ({ph}) order by q.id""", ids).fetchall()
    c_rows = con.execute(f"select questao_id,ponto_id,ponto2_id,detalhe,tipo_cobranca from classificacao where questao_id in ({ph}) order by questao_id", ids).fetchall()
    m_rows = con.execute(f"select questao_id,texto,pegadinha,dispositivos,estado,pendente_confirmacao from comentarios where questao_id in ({ph}) order by questao_id", ids).fetchall()
    codigo = {n: hashlib.sha256((AQUI / n).read_bytes()).hexdigest()[:16] for n in CODIGO_GERADOR}
    # programas dos editais usados na seção "O que há de novo neste edital" (o atual e os anteriores, por conteúdo do arquivo)
    comparacao = {}
    for slug in [perfil.get("edital_slug")] + list(perfil.get("editais_anteriores") or []):
        arq = AQUI.parent / "dados" / "editais_reais" / str(slug) / "programa.json"
        if slug and arq.exists():
            comparacao[slug] = hashlib.sha256(arq.read_bytes()).hexdigest()[:16]
    return {"perfil": LP.impressao(c, a), "catalogo": base.get("catalogo"), "edital": base.get("edital"),
            "comparacao": _h(comparacao), "questoes": _h([tuple(r) for r in q_rows]), "classificacao": _h([tuple(r) for r in c_rows]), "comentarios": _h([tuple(r) for r in m_rows]), "codigo": _h(codigo)}


ROTULOS = {"perfil": "o perfil", "catalogo": "o catálogo da disciplina", "edital": "o edital classificado do bloco", "comparacao": "os programas dos editais comparados (seção de novidades)", "questoes": "as questões ou gabaritos",
           "classificacao": "a classificação das questões", "comentarios": "os comentários", "codigo": "o código gerador (layout ou motor)"}


def desatualizado(registro, atual):
    """lista de rótulos das partes que mudaram desde o registro (vazia = a apostila está em dia)"""
    return [ROTULOS[k] for k in ROTULOS if registro.get(k) != atual.get(k)]


def arquivo_registro(perfil):
    return Path(perfil["pasta"]) / "impressoes.json"


def ler_registro(perfil):
    """registro da última geração do perfil ({} se não houver)"""
    arq = arquivo_registro(perfil)
    if not arq.exists():
        return {}
    try:
        return json.loads(arq.read_text(encoding="utf-8")).get(str(perfil["id"]), {})
    except ValueError:
        return {}


def registrar(perfil, atual, arquivo, pendencias, forcado_motivo=None, quando=None):
    """grava a impressão do que foi usado e a lista de pendências declaradas na capa"""
    import datetime
    arq = arquivo_registro(perfil)
    todos = {}
    if arq.exists():
        try:
            todos = json.loads(arq.read_text(encoding="utf-8"))
        except ValueError:
            todos = {}
    todos[str(perfil["id"])] = {**atual, "gerada_em": quando or datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "arquivo": Path(arquivo).name,
                                "pendencias": pendencias, "gerada_mesmo_assim": forcado_motivo}
    arq.write_text(json.dumps(todos, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
