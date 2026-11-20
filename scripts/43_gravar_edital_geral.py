#!/usr/bin/env python3
"""Passo 4 do ciclo por disciplina (Etapa 7 do plano do edital fictício geral): grava no banco.

Uso:  python -I scripts/43_gravar_edital_geral.py DH|PENAL [--simular]

O que faz (nada é recriado do zero; só se acrescentam tabelas e linhas):
 1. cópia de segurança em banco/backup/ (por disciplina e por dia);
 2. cria, se não existirem, as tabelas edital_itens, edital_item_pontos e edital_item_ocorrencias;
 3. grava cada edital coletado como linha de `editais` (tipo "real") e a linha do edital fictício geral;
 4. aplica os tópicos aprovados (criar e renomear) de dados/edital_ficticio_geral/topicos_aprovados_2026-11-14.csv;
 5. grava os itens da disciplina, a ligação de cada item aos tópicos e a frase literal de cada edital;
 6. confere as contagens com os arquivos e registra em log_alteracoes.
Com --simular tudo roda dentro de uma transação que é desfeita no fim.
É repetível: os itens da disciplina são apagados e regravados (as tabelas de itens são novas e só têm dados deste script).
"""
import csv, datetime, json, shutil, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
GER = RAIZ / "dados" / "edital_ficticio_geral"
INVENTARIO = RAIZ / "dados" / "inventario_editais_edital_geral.csv"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_disciplinas as LD   # noqa: E402  (fonte única: dados/disciplinas.json)
DISCIPLINA = LD.nomes(edital_ficticio=True)
PREFIXO = LD.prefixos()
VERSAO = "v1"
ORIGEM_PONTO = "edital geral v1 (14/11/2026)"

DDL = """
CREATE TABLE IF NOT EXISTS edital_itens (
  id INTEGER PRIMARY KEY, disciplina_id INT NOT NULL REFERENCES disciplinas(id), codigo TEXT NOT NULL, texto TEXT NOT NULL,
  n_editais INT, n_fcc INT, n_dpu INT, n_outras INT, ano_min INT, ano_max INT, flags TEXT, disciplina_provavel TEXT,
  versao TEXT NOT NULL, criado_em TEXT, UNIQUE(disciplina_id, codigo));
CREATE TABLE IF NOT EXISTS edital_item_pontos (
  item_id INT NOT NULL REFERENCES edital_itens(id), ponto_id INT NOT NULL REFERENCES pontos(id), PRIMARY KEY(item_id, ponto_id));
CREATE TABLE IF NOT EXISTS edital_item_ocorrencias (
  id INTEGER PRIMARY KEY, item_id INT NOT NULL REFERENCES edital_itens(id), edital_id INT NOT NULL REFERENCES editais(id),
  rotulo_no_edital TEXT, texto_literal TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_occ_item ON edital_item_ocorrencias(item_id);
CREATE INDEX IF NOT EXISTS ix_occ_edital ON edital_item_ocorrencias(edital_id);
CREATE INDEX IF NOT EXISTS ix_itpt_ponto ON edital_item_pontos(ponto_id);
"""


def nome_edital(pasta: str) -> str:
    return f"{pasta} [edital]"


def main():
    alvo = sys.argv[1].upper()
    simular = "--simular" in sys.argv
    if alvo not in DISCIPLINA:
        sys.exit("Disciplinas aceitas: " + ", ".join(DISCIPLINA) + " (as novas leem a taxonomia aprovada em arquivo).")
    hoje = datetime.date.today().isoformat()
    if not simular:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_edital_geral_{alvo.lower()}_{hoje}.db"
        if dst.exists():      # já houve gravação hoje: nova cópia com a hora, para não sobrescrever o estado anterior
            dst = RAIZ / "banco" / "backup" / f"estudos_antes_regravar_{alvo.lower()}_{hoje}_{datetime.datetime.now().strftime('%H%M')}.db"
        if not dst.exists():
            src = sqlite3.connect(BANCO); out = sqlite3.connect(dst); src.backup(out); out.close(); src.close()
            print("cópia de segurança:", dst.name)
    con = sqlite3.connect(BANCO)
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(DDL) if not simular else [con.execute(s) for s in DDL.strip().split(";") if s.strip()]
    cur = con.cursor()

    # inventário -> metadados dos editais
    meta = {}
    with open(INVENTARIO, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            arq = r["arquivo_local"].replace("\\", "/")
            if arq.startswith("provas/"):
                meta[arq.split("/")[1]] = r
    dados = json.loads((GER / f"{alvo}_itens.json").read_text(encoding="utf-8"))
    pastas = [p for p, *_ in dados["ordem_de_processamento"]]

    # 3. editais reais e o fictício geral
    novos_ed = 0
    ed_id = {}
    for pasta in pastas:
        m = meta.get(pasta, {})
        nome = nome_edital(pasta)
        row = cur.execute("select id from editais where nome=?", (nome,)).fetchone()
        if not row:
            try:
                ano = int(pasta[:4])
            except ValueError:
                ano = None
            desc = f"Banca {m.get('banca', '?')}; fonte: {m.get('fonte', 'repositório')}; arquivo provas/{pasta}/1. edital.pdf. {m.get('observacao', '')}".strip()
            cur.execute("insert into editais(nome,tipo,banca,carreira,cargo,ano,descricao,criado_em) values (?,?,?,?,?,?,?,?)",
                        (nome, "real", m.get("banca"), "Defensoria Pública", m.get("cargo"), ano, desc, hoje))
            row = (cur.lastrowid,); novos_ed += 1
        ed_id[pasta] = row[0]
    nome_geral = "Defensorias — Geral (edital fictício)"
    if not cur.execute("select 1 from editais where nome=?", (nome_geral,)).fetchone():
        cur.execute("insert into editais(nome,tipo,banca,carreira,cargo,ano,descricao,criado_em) values (?,?,?,?,?,?,?,?)",
                    (nome_geral, "ficticio", None, "Defensoria Pública", None, None,
                     "Edital fictício geral: união dos programas de Defensorias e DPU coletados (todas as bancas), com origem por item. "
                     "Visões (FCC-Defensoria, DPU, Analista) são consultas por origem em edital_itens.", hoje))

    # disciplina
    disc = cur.execute("select id from disciplinas where nome=?", (DISCIPLINA[alvo],)).fetchone()[0]

    # 4. tópicos: os temas e tópicos (assuntos e pontos) agora vêm do CATÁLOGO (dados/catalogo/<disciplina>.json), aplicado pelo
    #    script 71 (plano 06, Etapa 2). Este script não cria nem renomeia mais pontos: só confere que a taxonomia cabe no catálogo.
    criados = renomeados = 0
    if alvo not in ("DH", "PENAL"):
        tx = json.loads((GER / f"taxonomia_{alvo}.json").read_text(encoding="utf-8"))
        existentes = {c for (c,) in cur.execute("select codigo from pontos where disciplina_id=?", (disc,))}
        faltam = sorted(tp["codigo"] for tp in tx["topicos"] if tp["codigo"] not in existentes)
        if faltam:
            sys.exit(f"Faltam no catálogo {len(faltam)} tópico(s) da taxonomia ({', '.join(faltam[:6])}...). Gere o catálogo com "
                     f"`python -I scripts/71_catalogo_e_classificacao.py semear {alvo} \"{DISCIPLINA[alvo]}\"`, confira e rode `... 71 aplicar`.")
    pid = {c: i for c, i in cur.execute("select codigo,id from pontos where disciplina_id=?", (disc,))}

    # 5. itens, ligações e ocorrências (regrava a disciplina)
    cur.execute("delete from edital_item_ocorrencias where item_id in (select id from edital_itens where disciplina_id=?)", (disc,))
    cur.execute("delete from edital_item_pontos where item_id in (select id from edital_itens where disciplina_id=?)", (disc,))
    cur.execute("delete from edital_itens where disciplina_id=?", (disc,))
    n_it = n_lig = n_occ = 0
    sem_ponto = set()
    for it in dados["itens"]:
        cur.execute("""insert into edital_itens(disciplina_id,codigo,texto,n_editais,n_fcc,n_dpu,n_outras,ano_min,ano_max,flags,disciplina_provavel,versao,criado_em)
                       values (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (disc, it["id"], it["texto"], it["n_editais"], it["n_fcc"], it["n_dpu"], it["n_outras"], min(it["anos"]), max(it["anos"]),
                     json.dumps(it["flags"], ensure_ascii=False), it.get("disciplina_provavel"), VERSAO, hoje))
        iid = cur.lastrowid; n_it += 1
        for cod in it["pontos"]:
            cod = cod.rstrip("*")
            if cod not in pid:
                sem_ponto.add(cod); continue
            cur.execute("insert or ignore into edital_item_pontos(item_id,ponto_id) values (?,?)", (iid, pid[cod])); n_lig += 1
        for o in it["ocorrencias"]:
            cur.execute("insert into edital_item_ocorrencias(item_id,edital_id,rotulo_no_edital,texto_literal) values (?,?,?,?)",
                        (iid, ed_id[o["edital"]], o["item"], o["texto"])); n_occ += 1

    # 6. conferência
    esp_it = len(dados["itens"]); esp_occ = sum(len(i["ocorrencias"]) for i in dados["itens"])
    esp_lig = sum(len({c.rstrip('*') for c in i["pontos"]}) for i in dados["itens"])
    c_it = cur.execute("select count(*) from edital_itens where disciplina_id=?", (disc,)).fetchone()[0]
    c_occ = cur.execute("select count(*) from edital_item_ocorrencias where item_id in (select id from edital_itens where disciplina_id=?)", (disc,)).fetchone()[0]
    c_lig = cur.execute("select count(*) from edital_item_pontos where item_id in (select id from edital_itens where disciplina_id=?)", (disc,)).fetchone()[0]
    ok = (c_it, c_occ, c_lig) == (esp_it, esp_occ, esp_lig) and not sem_ponto
    print(f"{alvo}: editais novos gravados {novos_ed} | tópicos criados {criados}, renomeados {renomeados}")
    print(f"itens {c_it}/{esp_it} | ocorrências literais {c_occ}/{esp_occ} | ligações item-tópico {c_lig}/{esp_lig} | códigos sem tópico no banco: {sorted(sem_ponto)}")
    print("CONFERÊNCIA:", "OK" if ok else "DIVERGE")
    if simular or not ok:
        con.rollback(); print("(simulação ou divergência: nada foi gravado)"); con.close(); return
    cur.execute("insert into log_alteracoes(quem,o_que) values (?,?)",
                ("script 43", f"edital geral v1 de {DISCIPLINA[alvo]}: {c_it} itens, {c_occ} ocorrências, {c_lig} ligações; tópicos criados {criados}, renomeados {renomeados}; editais novos {novos_ed}"))
    con.commit(); con.close()
    print("gravado.")


if __name__ == "__main__":
    main()
