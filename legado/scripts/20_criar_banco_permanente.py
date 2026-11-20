"""ETAPA 1 da migracao (decidida em 12/11/2026): cria o banco PERMANENTE (banco/estudos.db) e migra o que existe.
- Uma vez criado, o banco NUNCA e recriado do zero: este script se recusa a rodar se banco/estudos.db ja existir (use --refazer so com copia de seguranca e sabendo que apaga alteracoes feitas no banco novo).
- Fontes da migracao: banco/questoes.db (legado), dados/classificacao_dh.csv, dados/comentarios_dh_*.json, banco/ajustes_gabarito.json.
- Faz copia de seguranca do legado e dos dados em banco/backup/ antes de migrar.
Uso: python 20_criar_banco_permanente.py
"""
import sqlite3, json, csv, glob, re, shutil, pathlib, sys, datetime, hashlib

BASE = pathlib.Path(__file__).resolve().parent.parent
LEGADO = BASE / "banco" / "questoes.db"
NOVO = BASE / "banco" / "estudos.db"
BACKUP = BASE / "banco" / "backup"
HOJE = "2026-11-12"

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE provas (
  id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, ano INT NOT NULL, banca TEXT NOT NULL, carreira TEXT, instituicao TEXT, uf TEXT, cargo TEXT NOT NULL,
  n_questoes_esperado INT, tipo_caderno INT, gabarito_tipo INT, gabarito_status TEXT, gabarito_origem TEXT, caderno_lido_por_ocr INT DEFAULT 0,
  banca_escreve TEXT DEFAULT 'FCC (a confirmar)', grupo_legado TEXT, arquivo_edital TEXT, arquivo_caderno TEXT, arquivo_gabarito TEXT, observacoes TEXT);
CREATE TABLE disciplinas (id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL);
CREATE TABLE assuntos (id INTEGER PRIMARY KEY, disciplina_id INT NOT NULL REFERENCES disciplinas(id), codigo TEXT NOT NULL, nome TEXT NOT NULL, descricao TEXT, UNIQUE(disciplina_id, codigo));
-- catalogo mestre de pontos do conteudo (etapa 2); cada ponto pertence a UM assunto
CREATE TABLE pontos (id INTEGER PRIMARY KEY, disciplina_id INT NOT NULL REFERENCES disciplinas(id), assunto_id INT NOT NULL REFERENCES assuntos(id), codigo TEXT, texto TEXT NOT NULL, descricao TEXT, origem TEXT, ativo INT DEFAULT 1, criado_em TEXT, UNIQUE(disciplina_id, codigo));
-- editais (ficticios ou reais) = visoes do catalogo
CREATE TABLE editais (id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, tipo TEXT NOT NULL CHECK(tipo IN ('ficticio','real')), banca TEXT, carreira TEXT, cargo TEXT, ano INT, descricao TEXT, criado_em TEXT);
CREATE TABLE edital_pontos (edital_id INT NOT NULL REFERENCES editais(id), ponto_id INT NOT NULL REFERENCES pontos(id), ordem INT, texto_no_edital TEXT, marca_novo INT DEFAULT 0, marca_exclusivo INT DEFAULT 0, marca_detalhado INT DEFAULT 0, PRIMARY KEY(edital_id, ponto_id));
CREATE TABLE questoes (
  id INTEGER PRIMARY KEY, prova_id INT NOT NULL REFERENCES provas(id), numero INT NOT NULL, disciplina_id INT REFERENCES disciplinas(id), disciplina_original TEXT,
  enunciado TEXT, alt_a TEXT, alt_b TEXT, alt_c TEXT, alt_d TEXT, alt_e TEXT, gabarito TEXT, situacao TEXT DEFAULT 'valida', motivo_situacao TEXT,
  texto_bruto TEXT, texto_fonte TEXT, tec_id TEXT, tec_materia TEXT, tec_assunto TEXT, revisada INT DEFAULT 0, UNIQUE(prova_id, numero));
-- classificacao: ponto principal e secundario (cada um conta meio quando ha dois); assunto derivado do ponto (enquanto nao ha ponto, assunto_provisorio)
CREATE TABLE classificacao (
  questao_id INT PRIMARY KEY REFERENCES questoes(id), ponto_id INT REFERENCES pontos(id), ponto2_id INT REFERENCES pontos(id), assunto_provisorio_id INT REFERENCES assuntos(id),
  detalhe TEXT, tipo_cobranca TEXT, origem TEXT, confianca TEXT, revisada INT DEFAULT 0, atualizado_em TEXT);
CREATE TABLE comentarios (
  questao_id INT PRIMARY KEY REFERENCES questoes(id), texto TEXT, pegadinha TEXT, dispositivos TEXT, estado TEXT DEFAULT 'rascunho', pendente_confirmacao INT DEFAULT 0, autor TEXT, atualizado_em TEXT);
CREATE TABLE examinadores (id INTEGER PRIMARY KEY, prova_id INT REFERENCES provas(id), nome TEXT, disciplina_id INT REFERENCES disciplinas(id), area_atuacao TEXT, fonte TEXT);
CREATE TABLE resultados_usuario (questao_id INT PRIMARY KEY REFERENCES questoes(id), resultado TEXT CHECK(resultado IN ('acertou','errou')), data TEXT, apostila TEXT);
CREATE TABLE autoavaliacao (ponto_id INT NOT NULL REFERENCES pontos(id), nota INT CHECK(nota IN (1,2,3)), motivo TEXT, data TEXT, PRIMARY KEY(ponto_id, data));
CREATE TABLE perfis (
  id INTEGER PRIMARY KEY, nome TEXT, disciplina_id INT REFERENCES disciplinas(id), banca TEXT NOT NULL, carreira TEXT, cargo TEXT NOT NULL, orgao TEXT, ano_referencia INT, edital_id INT REFERENCES editais(id),
  pesos_grupo TEXT DEFAULT '{"A":1,"B":0.5,"C":0.25}', meia_vida INT DEFAULT 8, estudo_geral INT DEFAULT 1, confirmado_pelo_usuario INT DEFAULT 0, confirmado_em TEXT, observacoes TEXT);
CREATE TABLE ajustes_gabarito (id INTEGER PRIMARY KEY, prova_id INT REFERENCES provas(id), numero INT, tipo_caderno INT, ajuste TEXT, nova_letra TEXT, fonte TEXT);
CREATE TABLE log_alteracoes (id INTEGER PRIMARY KEY, quando TEXT DEFAULT (datetime('now')), quem TEXT, o_que TEXT);
CREATE INDEX ix_q_prova ON questoes(prova_id, numero);
CREATE INDEX ix_cl_ponto ON classificacao(ponto_id);
"""


def main():
    if "--refazer" not in sys.argv and NOVO.exists():
        print("RECUSADO: banco/estudos.db ja existe. O banco permanente nunca e recriado do zero. (Use --refazer apenas com copia de seguranca.)"); return
    BACKUP.mkdir(exist_ok=True)
    shutil.copy2(LEGADO, BACKUP / f"questoes_{HOJE}.db")
    for pasta in ("dados",):
        destino = BACKUP / f"{pasta}_{HOJE}"
        if destino.exists(): shutil.rmtree(destino)
        shutil.copytree(BASE / pasta, destino)
    shutil.copy2(BASE / "banco" / "ajustes_gabarito.json", BACKUP / f"ajustes_gabarito_{HOJE}.json")
    if NOVO.exists(): NOVO.unlink()
    old = sqlite3.connect(LEGADO); old.row_factory = sqlite3.Row
    new = sqlite3.connect(NOVO); new.executescript(SCHEMA)
    log = []
    # ---- disciplinas e assuntos
    for r in old.execute("SELECT id,nome FROM disciplinas ORDER BY id"): new.execute("INSERT INTO disciplinas(id,nome) VALUES (?,?)", (r["id"], r["nome"]))
    for r in old.execute("SELECT * FROM assuntos"): new.execute("INSERT INTO assuntos(id,disciplina_id,codigo,nome,descricao) VALUES (?,?,?,?,?)", (r["id"], r["disciplina_id"], r["codigo"], r["nome"], r["descricao"]))
    # ---- provas
    for r in old.execute("SELECT * FROM provas ORDER BY id"):
        new.execute("""INSERT INTO provas(id,nome,ano,banca,carreira,instituicao,uf,cargo,n_questoes_esperado,tipo_caderno,gabarito_tipo,gabarito_status,gabarito_origem,caderno_lido_por_ocr,banca_escreve,grupo_legado,arquivo_edital,arquivo_caderno,arquivo_gabarito,observacoes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (r["id"], r["nome"], r["ano"], "FCC", "Defensoria Pública", r["orgao"], r["uf"], r["cargo"], r["n_questoes_esperado"], r["tipo_caderno"], r["gabarito_tipo"], r["gabarito_status"],
                     r["gabarito_origem"], r["caderno_lido_por_ocr"], r["banca_escreve"], r["grupo"], r["arquivo_edital"], r["arquivo_caderno"], r["arquivo_gabarito"], r["observacoes"]))
    # ---- questoes
    cols = "id,prova_id,numero,disciplina_id,disciplina_original,enunciado,alt_a,alt_b,alt_c,alt_d,alt_e,gabarito,situacao,motivo_situacao,texto_bruto,texto_fonte,tec_id,tec_materia,tec_assunto,revisada"
    for r in old.execute(f"SELECT {cols} FROM questoes ORDER BY id"):
        new.execute(f"INSERT INTO questoes({cols}) VALUES ({','.join('?' * 20)})", tuple(r))
    # ---- classificacao (assunto provisorio; ponto vem na etapa 3)
    n_cl = 0
    for r in old.execute("SELECT questao_id,assunto_id,detalhe,tipo_cobranca,origem,confianca FROM classificacao"):
        new.execute("INSERT INTO classificacao(questao_id,assunto_provisorio_id,detalhe,tipo_cobranca,origem,confianca,atualizado_em) VALUES (?,?,?,?,?,?,?)", (*tuple(r), HOJE)); n_cl += 1
    # ---- comentarios (JSON; chave prova|numero)
    chave = {(n, num): i for i, n, num in old.execute("SELECT q.id,p.nome,q.numero FROM questoes q JOIN provas p ON p.id=q.prova_id")}
    n_com = 0
    for f in sorted(glob.glob(str(BASE / "dados" / "comentarios_dh_DH*.json"))):
        for k, v in json.loads(open(f, encoding="utf-8").read()).items():
            prova, num = k.rsplit("|", 1)
            qid = chave[(prova, int(num))]
            pend = 1 if re.search(r"onfirmar|não consegui|Atenção:|discutível", v["c"]) else 0
            new.execute("INSERT INTO comentarios(questao_id,texto,pegadinha,dispositivos,estado,pendente_confirmacao,autor,atualizado_em) VALUES (?,?,?,?,?,?,?,?)",
                        (qid, v["c"], v.get("p"), json.dumps(v.get("d", []), ensure_ascii=False), "rascunho", pend, "IA (Claude)", HOJE)); n_com += 1
    # ---- ajustes de gabarito (historico)
    pid = {n: i for i, n in old.execute("SELECT id,nome FROM provas")}
    for a in json.loads((BASE / "banco" / "ajustes_gabarito.json").read_text(encoding="utf-8")):
        new.execute("INSERT INTO ajustes_gabarito(prova_id,numero,tipo_caderno,ajuste,nova_letra,fonte) VALUES (?,?,?,?,?,?)", (pid[a["prova"]], a["numero"], a["tipo"], a["ajuste"], a["nova_letra"], a["fonte"]))
    # ---- perfil piloto (informado pelo usuario em 12/11/2026)
    did = new.execute("SELECT id FROM disciplinas WHERE nome='Direitos Humanos'").fetchone()[0]
    new.execute("INSERT INTO perfis(nome,disciplina_id,banca,carreira,cargo,orgao,ano_referencia,estudo_geral,confirmado_pelo_usuario,confirmado_em,observacoes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("Direitos Humanos · Defensor Público · FCC (estudo geral)", did, "FCC", "Defensoria Pública", "Defensor Público", None, 2026, 1, 1, HOJE, "Piloto do fluxo novo; informado pelo usuário no chat em 12/11/2026."))
    new.execute("INSERT INTO meta VALUES ('versao_esquema','1')"); new.execute("INSERT INTO meta VALUES ('migrado_de','questoes.db legado + dados/*.csv|json em 2026-11-12')")
    new.execute("INSERT INTO log_alteracoes(quem,o_que) VALUES ('script 20','banco permanente criado e dados migrados')")
    new.commit()
    # ---- verificacao
    rel = []
    def conta(db, sql): return db.execute(sql).fetchone()[0]
    for nome, sql in [("provas", "SELECT count(*) FROM provas"), ("questoes", "SELECT count(*) FROM questoes"), ("questoes anuladas", "SELECT count(*) FROM questoes WHERE situacao='anulada'"),
                      ("questoes sem gabarito (nao anuladas)", "SELECT count(*) FROM questoes WHERE gabarito IS NULL AND situacao<>'anulada'"), ("classificacoes", "SELECT count(*) FROM classificacao"), ("assuntos", "SELECT count(*) FROM assuntos")]:
        a, b = conta(old, sql), conta(new, sql.replace("FROM classificacao", "FROM classificacao")); rel.append((nome, a, b, "ok" if a == b else "DIFERENTE"))
    rel.append(("comentarios (JSON -> banco)", n_com, conta(new, "SELECT count(*) FROM comentarios"), "ok" if n_com == conta(new, "SELECT count(*) FROM comentarios") else "DIFERENTE"))
    # conferencia por impressao digital do texto de cada questao
    def h(db): return hashlib.md5("".join(f"{r[0]}|{r[1]}|{r[2]}|{r[3]}|{r[4]}\n" for r in db.execute("SELECT prova_id,numero,enunciado,gabarito,situacao FROM questoes ORDER BY prova_id,numero")).encode()).hexdigest()
    rel.append(("impressao digital das questoes", h(old), h(new), "ok" if h(old) == h(new) else "DIFERENTE"))
    linhas = ["# Relatorio da migracao (etapa 1)", f"Data: {HOJE}", "", "| Item | Legado | Novo | Resultado |", "|---|---|---|---|"] + [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rel]
    (BASE / "banco" / "relatorio_migracao.md").write_text("\n".join(linhas), encoding="utf-8")
    print("\n".join(linhas)); print("\nbanco novo:", NOVO, round(NOVO.stat().st_size / 1024), "KB; backup em", BACKUP)


if __name__ == "__main__":
    main()
