#!/usr/bin/env python3
"""Grupo C (Mapear): biblioteca do EDITOR DE QUESTÕES (lista, edição e histórico), sem HTTP (decisão 57 do `02`).

Diferente do editor do catálogo, ESTE editor grava DIRETO NO BANCO (`banco/estudos.db`). Por isso:
- cópia do banco uma vez por dia em `banco/backup/estudos_editor_questoes_<data>.db` (`backup_do_dia`);
- toda edição é uma transação única, registrada em `historico_edicoes` (campo, valor antigo, valor novo, lote, motivo) e em `log_alteracoes`;
- `desfazer` devolve o último lote de edições da questão (se o valor ainda for o gravado; senão recusa);
- nada é apagado do banco e os PDFs de `provas/` não são tocados (edita-se só o texto extraído).

Regras (decisão 57):
- Principal e secundário: o principal é obrigatório e deve ser um tópico ATIVO; o secundário é opcional, ativo e diferente do principal.
  Editar a classificação grava `origem = usuario`; a revisão só vale com `marcar_revisada`.
- `marcar_revisada` (só o usuário aciona): `questoes.revisada = 1`, `classificacao.revisada = 1` e, se a questão estava em `revisar_texto`,
  passa a `valida`.
- Gabarito: só A a E, e o MOTIVO é obrigatório (muda a análise). Só a questão é registrada; a situação do gabarito da prova não muda.
- Comentário: salvar uma edição de comentário o põe em `estado = conferido` e zera `pendente_confirmacao`.
"""
import datetime
import json
import shutil
import sqlite3
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
PASTA_BACKUP = RAIZ / "banco" / "backup"

CAMPOS_TEXTO = ("enunciado", "alt_a", "alt_b", "alt_c", "alt_d", "alt_e")
GABARITOS = ("A", "B", "C", "D", "E")
SITUACOES = ("valida", "revisar_texto", "anulada", "desatualizada")
CONFIANCAS = ("alta", "media", "baixa")
TIPOS_COBRANCA = ("lei_seca", "jurisprudencia", "lei/tratado", "caso_concreto", "doutrina", "gramatica", "interpretacao", "sumula")
CAMPOS_COMENTARIO = ("texto", "pegadinha", "dispositivos")
LIMITE_TEXTO = 20000

DDL_HISTORICO = """
CREATE TABLE IF NOT EXISTS historico_edicoes (
  id INTEGER PRIMARY KEY, questao_id INT NOT NULL, campo TEXT NOT NULL, antes TEXT, depois TEXT,
  lote TEXT NOT NULL, motivo TEXT, quando TEXT NOT NULL, desfeita INT NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_hist_questao ON historico_edicoes(questao_id, desfeita);
"""


class ErroQuestao(Exception):
    """Pedido inválido (mensagem em português)."""


def _con(banco):
    con = sqlite3.connect(banco or BANCO)
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(DDL_HISTORICO)
    return con


def agora():
    return datetime.datetime.now().isoformat(timespec="seconds")


def backup_do_dia(banco=None, pasta=None):
    """Cópia do banco, uma por dia. Devolve o caminho se criou agora, ou None se já existia."""
    banco = Path(banco or BANCO)
    pasta = Path(pasta or PASTA_BACKUP)
    pasta.mkdir(parents=True, exist_ok=True)
    dst = pasta / f"estudos_editor_questoes_{datetime.date.today():%Y-%m-%d}.db"
    if dst.exists():
        return None
    s = sqlite3.connect(banco)
    o = sqlite3.connect(dst)
    s.backup(o)
    o.close()
    s.close()
    return dst


# ---------------------------------------------------------------- leitura
def filtros_disponiveis(banco=None):
    con = _con(banco)
    try:
        return {
            "disciplinas": [{"id": i, "nome": n} for i, n in con.execute(
                "select id,nome from disciplinas where id in (select disciplina_id from questoes) order by nome")],
            "provas": [{"id": i, "nome": n} for i, n in con.execute("select id,nome from provas order by ano desc, nome")],
            "situacoes": list(SITUACOES), "confiancas": list(CONFIANCAS), "tipos_cobranca": list(TIPOS_COBRANCA),
        }
    finally:
        con.close()


def topicos(banco=None):
    """Tópicos ativos, agrupados por disciplina e assunto (para o seletor de principal e secundário)."""
    con = _con(banco)
    try:
        out = {}
        for d, a_cod, a_nome, p_cod, p_txt in con.execute(
                """select d.nome, a.codigo, a.nome, p.codigo, p.texto from pontos p join assuntos a on a.id=p.assunto_id
                   join disciplinas d on d.id=p.disciplina_id where p.ativo=1 order by d.nome, a.codigo, p.codigo"""):
            out.setdefault(d, {}).setdefault((a_cod, a_nome), []).append({"codigo": p_cod, "texto": p_txt})
        return [{"disciplina": d, "assuntos": [{"codigo": c, "nome": n, "pontos": ps} for (c, n), ps in ass.items()]} for d, ass in out.items()]
    finally:
        con.close()


def listar(banco=None, filtros=None, limite=100, deslocamento=0):
    """Filtros (todos opcionais): disciplina_id, prova_id, situacao, confianca, ponto (código, principal ou secundário), busca (texto do enunciado),
    migrada, sem_secundario, sem_classificacao, comentario_confirmar, nao_revisadas (booleanos)."""
    f = filtros or {}
    cond, par = [], []

    def add(c, *p):
        cond.append(c)
        par.extend(p)
    if f.get("disciplina_id"):
        add("q.disciplina_id=?", int(f["disciplina_id"]))
    if f.get("prova_id"):
        add("q.prova_id=?", int(f["prova_id"]))
    if f.get("situacao"):
        add("q.situacao=?", f["situacao"])
    if f.get("confianca"):
        add("c.confianca=?", f["confianca"])
    if f.get("ponto"):
        add("(pt1.codigo=? or pt2.codigo=?)", f["ponto"], f["ponto"])
    if f.get("busca"):
        add("q.enunciado like ?", "%" + f["busca"] + "%")
    if f.get("migrada"):
        add("coalesce(c.origem,'') like '%migrada%'")
    if f.get("sem_secundario"):
        add("c.questao_id is not null and c.ponto2_id is null")
    if f.get("sem_classificacao"):
        add("c.questao_id is null")
    if f.get("comentario_confirmar"):
        add("coalesce(cm.pendente_confirmacao,0)=1")
    if f.get("nao_revisadas"):
        add("coalesce(q.revisada,0)=0")
    onde = (" where " + " and ".join(cond)) if cond else ""
    base = """from questoes q join provas p on p.id=q.prova_id join disciplinas d on d.id=q.disciplina_id
              left join classificacao c on c.questao_id=q.id left join pontos pt1 on pt1.id=c.ponto_id left join pontos pt2 on pt2.id=c.ponto2_id
              left join comentarios cm on cm.questao_id=q.id"""
    con = _con(banco)
    try:
        total = con.execute("select count(*) " + base + onde, par).fetchone()[0]
        linhas = con.execute(
            "select q.id,p.nome,q.numero,d.nome,q.situacao,pt1.codigo,pt2.codigo,c.confianca,c.origem,coalesce(q.revisada,0),cm.estado,coalesce(cm.pendente_confirmacao,0) "
            + base + onde + " order by p.ano, p.nome, q.numero limit ? offset ?", par + [int(limite), int(deslocamento)]).fetchall()
        itens = [{"id": i, "prova": pr, "numero": n, "disciplina": d, "situacao": s, "ponto": p1, "ponto2": p2, "confianca": cf, "origem": o,
                  "revisada": bool(rv), "comentario": ce, "comentario_confirmar": bool(pc)} for i, pr, n, d, s, p1, p2, cf, o, rv, ce, pc in linhas]
        return {"total": total, "itens": itens}
    finally:
        con.close()


def _classificacao(con, qid):
    r = con.execute("""select p1.codigo, p2.codigo, c.tipo_cobranca, c.detalhe, c.confianca, c.origem, coalesce(c.revisada,0), c.assunto_provisorio_id, c.atualizado_em
                       from classificacao c left join pontos p1 on p1.id=c.ponto_id left join pontos p2 on p2.id=c.ponto2_id where c.questao_id=?""", (qid,)).fetchone()
    if not r:
        return None
    return {"ponto": r[0], "ponto2": r[1], "tipo_cobranca": r[2], "detalhe": r[3], "confianca": r[4], "origem": r[5], "revisada": r[6],
            "assunto_provisorio_id": r[7], "atualizado_em": r[8]}


def _comentario(con, qid):
    r = con.execute("select texto,pegadinha,dispositivos,estado,coalesce(pendente_confirmacao,0),autor,atualizado_em from comentarios where questao_id=?", (qid,)).fetchone()
    if not r:
        return None
    return {"texto": r[0], "pegadinha": r[1], "dispositivos": r[2], "estado": r[3], "pendente_confirmacao": r[4], "autor": r[5], "atualizado_em": r[6]}


def obter(banco=None, qid=0):
    con = _con(banco)
    try:
        r = con.execute("""select q.id,p.nome,p.ano,p.banca,p.gabarito_situacao,q.numero,d.nome,q.disciplina_original,q.enunciado,q.alt_a,q.alt_b,q.alt_c,q.alt_d,q.alt_e,
                           q.gabarito,q.situacao,q.motivo_situacao,coalesce(q.revisada,0)
                           from questoes q join provas p on p.id=q.prova_id join disciplinas d on d.id=q.disciplina_id where q.id=?""", (int(qid),)).fetchone()
        if not r:
            raise ErroQuestao("questão não encontrada.")
        return {"id": r[0], "prova": r[1], "ano": r[2], "banca": r[3], "gabarito_situacao": r[4], "numero": r[5], "disciplina": r[6], "disciplina_original": r[7],
                "enunciado": r[8], "alt_a": r[9], "alt_b": r[10], "alt_c": r[11], "alt_d": r[12], "alt_e": r[13], "gabarito": r[14], "situacao": r[15],
                "motivo_situacao": r[16], "revisada": bool(r[17]), "classificacao": _classificacao(con, qid), "comentario": _comentario(con, qid)}
    finally:
        con.close()


def historico(banco=None, qid=0, limite=60):
    con = _con(banco)
    try:
        return [{"id": i, "campo": c, "antes": a, "depois": d, "lote": l, "motivo": m, "quando": q, "desfeita": bool(df)}
                for i, c, a, d, l, m, q, df in con.execute(
                    "select id,campo,antes,depois,lote,motivo,quando,desfeita from historico_edicoes where questao_id=? order by id desc limit ?", (int(qid), int(limite)))]
    finally:
        con.close()


# ---------------------------------------------------------------- escrita
def _ponto_id(con, codigo, obrigatorio=True):
    if not codigo:
        if obrigatorio:
            raise ErroQuestao("o tópico principal é obrigatório.")
        return None
    r = con.execute("select id,ativo from pontos where codigo=?", (codigo,)).fetchone()
    if not r:
        raise ErroQuestao(f"tópico {codigo} não existe.")
    if not r[1]:
        raise ErroQuestao(f"tópico {codigo} está inativo.")
    return r[0]


def _j(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True) if x is not None else None


def salvar(banco=None, qid=0, alteracoes=None, motivo="", pasta_backup=None):
    """Aplica as alterações (ver o módulo) numa transação. Devolve {"mudou": bool, "lote": str, "campos": [...], "questao": obter(...)}."""
    alt = alteracoes or {}
    motivo = (motivo or "").strip()
    backup_do_dia(banco, pasta_backup)
    con = _con(banco)
    lote, quando, feitos = uuid.uuid4().hex[:12], agora(), []

    def reg(campo, antes, depois):
        con.execute("insert into historico_edicoes(questao_id,campo,antes,depois,lote,motivo,quando) values(?,?,?,?,?,?,?)", (qid, campo, antes, depois, lote, motivo or None, quando))
        feitos.append(campo)
    try:
        q = con.execute("select enunciado,alt_a,alt_b,alt_c,alt_d,alt_e,gabarito,situacao,coalesce(revisada,0) from questoes where id=?", (int(qid),)).fetchone()
        if not q:
            raise ErroQuestao("questão não encontrada.")
        qid = int(qid)
        atual = dict(zip(CAMPOS_TEXTO + ("gabarito", "situacao", "revisada"), q))
        # texto
        for campo, valor in (alt.get("texto") or {}).items():
            if campo not in CAMPOS_TEXTO:
                raise ErroQuestao(f"campo de texto inválido: {campo}.")
            if not isinstance(valor, str) or len(valor) > LIMITE_TEXTO:
                raise ErroQuestao(f"texto inválido em {campo}.")
            if valor != (atual[campo] or ""):
                reg(campo, atual[campo], valor)
                con.execute(f"update questoes set {campo}=? where id=?", (valor, qid))
        # gabarito
        if "gabarito" in alt and alt["gabarito"] != atual["gabarito"]:
            if alt["gabarito"] not in GABARITOS:
                raise ErroQuestao("gabarito deve ser A, B, C, D ou E.")
            if not motivo:
                raise ErroQuestao("para mudar o gabarito, escreva o motivo.")
            reg("gabarito", atual["gabarito"], alt["gabarito"])
            con.execute("update questoes set gabarito=? where id=?", (alt["gabarito"], qid))
        # situação
        if "situacao" in alt and alt["situacao"] != atual["situacao"]:
            if alt["situacao"] not in SITUACOES:
                raise ErroQuestao("situação inválida.")
            reg("situacao", atual["situacao"], alt["situacao"])
            con.execute("update questoes set situacao=? where id=?", (alt["situacao"], qid))
            atual["situacao"] = alt["situacao"]
        # classificação
        antes_c = _classificacao(con, qid)
        c = alt.get("classificacao")
        if c is not None:
            p1 = _ponto_id(con, c.get("ponto"))
            p2 = _ponto_id(con, c.get("ponto2"), obrigatorio=False)
            if p2 is not None and p2 == p1:
                raise ErroQuestao("o tópico principal e o secundário devem ser diferentes.")
            conf = c.get("confianca") or (antes_c or {}).get("confianca") or "media"
            if conf not in CONFIANCAS:
                raise ErroQuestao("confiança inválida.")
            tipo = (c.get("tipo_cobranca") if c.get("tipo_cobranca") is not None else (antes_c or {}).get("tipo_cobranca")) or ""
            detalhe = c.get("detalhe") if c.get("detalhe") is not None else (antes_c or {}).get("detalhe")
            if detalhe is not None and len(detalhe) > 1000:
                raise ErroQuestao("detalhe longo demais (máximo de 1000 caracteres).")
            novo = {"ponto": c.get("ponto"), "ponto2": c.get("ponto2") or None, "tipo_cobranca": tipo, "detalhe": detalhe or "", "confianca": conf}
            velho = {k: (antes_c or {}).get(k) for k in novo}
            velho["ponto2"] = velho["ponto2"] or None
            velho["detalhe"] = velho["detalhe"] or ""
            if antes_c is None or novo != velho:
                if antes_c is None:
                    con.execute("""insert into classificacao(questao_id,ponto_id,ponto2_id,detalhe,tipo_cobranca,origem,confianca,revisada,atualizado_em)
                                   values(?,?,?,?,?,?,?,0,?)""", (qid, p1, p2, novo["detalhe"], tipo, "usuario", conf, quando))
                else:
                    con.execute("update classificacao set ponto_id=?,ponto2_id=?,detalhe=?,tipo_cobranca=?,origem='usuario',confianca=?,atualizado_em=? where questao_id=?",
                                (p1, p2, novo["detalhe"], tipo, conf, quando, qid))
                reg("classificacao", _j(antes_c), _j(_classificacao(con, qid)))
        # comentário
        cm = alt.get("comentario")
        if cm is not None:
            for k in cm:
                if k not in CAMPOS_COMENTARIO:
                    raise ErroQuestao(f"campo de comentário inválido: {k}.")
            antes_m = _comentario(con, qid)
            novo = {k: cm.get(k, (antes_m or {}).get(k)) for k in CAMPOS_COMENTARIO}
            if any(not isinstance(v, (str, type(None))) or len(v or "") > LIMITE_TEXTO for v in novo.values()):
                raise ErroQuestao("texto de comentário inválido.")
            if antes_m is None or any((novo[k] or "") != ((antes_m or {}).get(k) or "") for k in CAMPOS_COMENTARIO):
                if antes_m is None:
                    con.execute("insert into comentarios(questao_id,texto,pegadinha,dispositivos,estado,pendente_confirmacao,autor,atualizado_em) values(?,?,?,?,?,?,?,?)",
                                (qid, novo["texto"], novo["pegadinha"], novo["dispositivos"], "conferido", 0, "usuario", quando))
                else:
                    con.execute("update comentarios set texto=?,pegadinha=?,dispositivos=?,estado='conferido',pendente_confirmacao=0,atualizado_em=? where questao_id=?",
                                (novo["texto"], novo["pegadinha"], novo["dispositivos"], quando, qid))
                reg("comentario", _j(antes_m), _j(_comentario(con, qid)))
        # revisão
        if alt.get("marcar_revisada"):
            if not atual["revisada"]:
                reg("revisada", "0", "1")
                con.execute("update questoes set revisada=1 where id=?", (qid,))
            ant = _classificacao(con, qid)
            if ant is not None and not ant["revisada"]:
                con.execute("update classificacao set revisada=1, origem='usuario', atualizado_em=? where questao_id=?", (quando, qid))
                reg("classificacao", _j(ant), _j(_classificacao(con, qid)))
            if atual["situacao"] == "revisar_texto":
                reg("situacao", "revisar_texto", "valida")
                con.execute("update questoes set situacao='valida' where id=?", (qid,))
        if feitos:
            con.execute("insert into log_alteracoes(quem,o_que) values('editor de questões', ?)", (f"questão {qid}: {', '.join(sorted(set(feitos)))} (lote {lote})" + (f"; motivo: {motivo}" if motivo else ""),))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {"mudou": bool(feitos), "lote": lote, "campos": sorted(set(feitos)), "questao": obter(banco, qid)}


def _restaurar_json(con, qid, tabela, antes, depois):
    atual = _classificacao(con, qid) if tabela == "classificacao" else _comentario(con, qid)
    esperado = json.loads(depois) if depois else None
    if (atual or None) != esperado:
        raise ErroQuestao(f"{tabela} foi alterada depois desta edição; não dá para desfazer sem perder a mudança mais nova.")
    ant = json.loads(antes) if antes else None
    if tabela == "classificacao":
        if ant is None:
            con.execute("delete from classificacao where questao_id=?", (qid,))
            return
        p1 = _ponto_id_qualquer(con, ant["ponto"])
        p2 = _ponto_id_qualquer(con, ant["ponto2"])
        con.execute("update classificacao set ponto_id=?,ponto2_id=?,tipo_cobranca=?,detalhe=?,confianca=?,origem=?,revisada=?,atualizado_em=? where questao_id=?",
                    (p1, p2, ant["tipo_cobranca"], ant["detalhe"], ant["confianca"], ant["origem"], ant["revisada"], ant["atualizado_em"], qid))
    else:
        if ant is None:
            con.execute("delete from comentarios where questao_id=?", (qid,))
            return
        con.execute("update comentarios set texto=?,pegadinha=?,dispositivos=?,estado=?,pendente_confirmacao=?,autor=?,atualizado_em=? where questao_id=?",
                    (ant["texto"], ant["pegadinha"], ant["dispositivos"], ant["estado"], ant["pendente_confirmacao"], ant["autor"], ant["atualizado_em"], qid))


def _ponto_id_qualquer(con, codigo):
    if not codigo:
        return None
    r = con.execute("select id from pontos where codigo=?", (codigo,)).fetchone()
    if not r:
        raise ErroQuestao(f"tópico {codigo} não existe mais; não dá para desfazer.")
    return r[0]


def desfazer(banco=None, qid=0, pasta_backup=None):
    """Desfaz o último lote de edições da questão (todos os campos dele, do mais novo para o mais antigo)."""
    backup_do_dia(banco, pasta_backup)
    con = _con(banco)
    try:
        qid = int(qid)
        r = con.execute("select lote from historico_edicoes where questao_id=? and desfeita=0 order by id desc limit 1", (qid,)).fetchone()
        if not r:
            raise ErroQuestao("não há edição para desfazer nesta questão.")
        lote = r[0]
        itens = con.execute("select id,campo,antes,depois from historico_edicoes where questao_id=? and lote=? and desfeita=0 order by id desc", (qid, lote)).fetchall()
        for hid, campo, antes, depois in itens:
            if campo in ("classificacao", "comentario"):
                _restaurar_json(con, qid, campo, antes, depois)
            else:
                atual = con.execute(f"select {campo} from questoes where id=?", (qid,)).fetchone()[0]
                if str(atual if atual is not None else "") != str(depois if depois is not None else ""):
                    raise ErroQuestao(f"{campo} foi alterado depois desta edição; não dá para desfazer.")
                con.execute(f"update questoes set {campo}=? where id=?", (int(antes) if campo == "revisada" else antes, qid))
            con.execute("update historico_edicoes set desfeita=1 where id=?", (hid,))
        con.execute("insert into log_alteracoes(quem,o_que) values('editor de questões', ?)", (f"questão {qid}: lote {lote} desfeito",))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {"desfeito": lote, "questao": obter(banco, qid)}
