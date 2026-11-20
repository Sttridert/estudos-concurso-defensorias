#!/usr/bin/env python3
"""Fase 5 (edital real), passo 3: grava no banco o artefato `edital_classificado.json` (saída do script 51).

Uso:  python -I scripts/52_gravar_edital_classificado.py <slug> [--simular]

O que faz (nada é recriado do zero; só se acrescentam tabelas e linhas):
 1. cópia de segurança em banco/backup/;
 2. cria, se não existirem, as tabelas edital_frases, edital_frase_destinos e pontos_propostos e a visão v_edital_frases;
 3. acha (ou cria) a linha do edital real em `editais` (nome "<pasta> [edital]", a mesma usada pelo script 43);
 4. grava as propostas de tópicos novos em `pontos_propostos` (status "proposto"; se já existir e já tiver sido decidida, não mexe);
 5. regrava as frases e os destinos desse edital (apaga as do mesmo edital e grava de novo);
 6. confere contagens com o arquivo e registra em log_alteracoes.
Não mexe em `pontos`, `edital_pontos`, `editais.programa` nem nas questões. Com --simular tudo roda numa cópia em memória do banco (o banco real não é tocado).

Uso futuro (apostilas): cada frase literal do edital tem um tópico principal (e secundários) por trecho. A apostila lê
`edital_frases` + `edital_frase_destinos` para montar o "edital verticalizado" e a coluna "Trechos do edital (literal)".
"""
import datetime, json, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"

DDL = """
CREATE TABLE IF NOT EXISTS pontos_propostos (
  id INTEGER PRIMARY KEY, codigo TEXT NOT NULL UNIQUE, edital_id INT REFERENCES editais(id), disciplina_id INT REFERENCES disciplinas(id),
  tema TEXT, nome TEXT NOT NULL, justificativa TEXT, parecidos TEXT,
  status TEXT NOT NULL DEFAULT 'proposto' CHECK(status IN ('proposto','homologado','rejeitado','duplicado')),
  ponto_id INT REFERENCES pontos(id),            -- preenchido quando a proposta vira (ou já é) um ponto do catálogo
  criado_em TEXT, decidido_em TEXT, observacao TEXT);
CREATE TABLE IF NOT EXISTS edital_frases (
  id INTEGER PRIMARY KEY, edital_id INT NOT NULL REFERENCES editais(id), disciplina_edital TEXT NOT NULL,
  disciplina_id INT REFERENCES disciplinas(id), item_ordem INT NOT NULL, item_rotulo TEXT, frase_ordem INT NOT NULL,
  codigo TEXT NOT NULL, texto TEXT NOT NULL, UNIQUE(edital_id, codigo));
CREATE TABLE IF NOT EXISTS edital_frase_destinos (
  id INTEGER PRIMARY KEY, frase_id INT NOT NULL REFERENCES edital_frases(id), ponto_id INT REFERENCES pontos(id),
  proposto_id INT REFERENCES pontos_propostos(id), papel TEXT NOT NULL CHECK(papel IN ('principal','secundario')),
  trecho TEXT, origem TEXT, confirmado INT NOT NULL DEFAULT 0,
  CHECK((ponto_id IS NULL) <> (proposto_id IS NULL)));
CREATE TABLE IF NOT EXISTS edital_pontos_fora (
  edital_id INT NOT NULL REFERENCES editais(id), ponto_id INT NOT NULL REFERENCES pontos(id), motivo TEXT NOT NULL,
  origem TEXT, confirmado INT NOT NULL DEFAULT 0, PRIMARY KEY(edital_id, ponto_id));
CREATE TABLE IF NOT EXISTS edital_blocos (
  edital_id INT NOT NULL REFERENCES editais(id), sigla TEXT NOT NULL, titulo_no_edital TEXT NOT NULL,
  disciplina_id INT REFERENCES disciplinas(id), ordem INT NOT NULL, PRIMARY KEY(edital_id, sigla));
CREATE INDEX IF NOT EXISTS ix_efd_frase ON edital_frase_destinos(frase_id);
CREATE INDEX IF NOT EXISTS ix_efd_ponto ON edital_frase_destinos(ponto_id);
CREATE INDEX IF NOT EXISTS ix_ef_edital ON edital_frases(edital_id, disciplina_edital);
CREATE VIEW IF NOT EXISTS v_edital_frases AS
  SELECT f.edital_id, f.disciplina_edital, f.item_rotulo, f.codigo AS frase_codigo, f.texto,
         d.papel, d.trecho, COALESCE(p.codigo, pp.codigo) AS ponto, COALESCE(p.texto, pp.nome) AS ponto_nome,
         CASE WHEN d.proposto_id IS NOT NULL THEN 'proposto' ELSE 'catalogo' END AS tipo_ponto, d.confirmado
  FROM edital_frases f JOIN edital_frase_destinos d ON d.frase_id = f.id
  LEFT JOIN pontos p ON p.id = d.ponto_id LEFT JOIN pontos_propostos pp ON pp.id = d.proposto_id;
"""


def main():
    slug = sys.argv[1]
    simular = "--simular" in sys.argv
    pasta = RAIZ / "dados" / "editais_reais" / slug
    art = json.loads((pasta / "edital_classificado.json").read_text(encoding="utf-8"))
    hoje = datetime.date.today().isoformat()
    if not simular:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_edital_classificado_{slug}_{hoje}.db"
        if dst.exists():
            dst = RAIZ / "banco" / "backup" / f"estudos_antes_edital_classificado_{slug}_{hoje}_{datetime.datetime.now().strftime('%H%M')}.db"
        src = sqlite3.connect(BANCO); out = sqlite3.connect(dst); src.backup(out); out.close(); src.close()
        print("cópia de segurança:", dst.name)
    if simular:                      # trabalha numa cópia em memória: nada é gravado no banco real
        con = sqlite3.connect(":memory:"); real = sqlite3.connect(BANCO); real.backup(con); real.close()
    else:
        con = sqlite3.connect(BANCO)
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(DDL)
    ed = art["edital"]
    nome = f"{ed['pasta']} [edital]"
    r = con.execute("select id from editais where nome=?", (nome,)).fetchone()
    if r:
        eid = r[0]
    else:
        con.execute("insert into editais(nome,tipo,banca,carreira,cargo,ano,descricao,criado_em) values(?,?,?,?,?,?,?,?)",
                    (nome, "real", ed["banca"], "Defensoria Pública", ed["cargo"], ed["ano"], f"Edital real completo. Arquivo: {ed['arquivo']}", hoje))
        eid = con.execute("select id from editais where nome=?", (nome,)).fetchone()[0]
    disc = {n: i for i, n in con.execute("select id,nome from disciplinas")}
    pid = {c: i for i, c in con.execute("select id,codigo from pontos")}

    # propostas (não sobrescreve decisão já tomada)
    prop = {}
    for p in art["topicos_propostos"]:
        r = con.execute("select id,status from pontos_propostos where codigo=?", (p["id"],)).fetchone()
        did = disc.get(p["disciplina"])
        if r:
            prop[p["id"]] = r[0]
            if r[1] == "proposto":
                con.execute("update pontos_propostos set edital_id=?,disciplina_id=?,tema=?,nome=?,justificativa=?,parecidos=? where id=?",
                            (eid, did, p["tema"], p["nome"], p["justificativa"], json.dumps(p["parecidos_no_catalogo"], ensure_ascii=False), r[0]))
        else:
            con.execute("insert into pontos_propostos(codigo,edital_id,disciplina_id,tema,nome,justificativa,parecidos,criado_em) values(?,?,?,?,?,?,?,?)",
                        (p["id"], eid, did, p["tema"], p["nome"], p["justificativa"], json.dumps(p["parecidos_no_catalogo"], ensure_ascii=False), hoje))
            prop[p["id"]] = con.execute("select id from pontos_propostos where codigo=?", (p["id"],)).fetchone()[0]

    # frases e destinos do edital: regrava
    con.execute("delete from edital_frase_destinos where frase_id in (select id from edital_frases where edital_id=?)", (eid,))
    con.execute("delete from edital_frases where edital_id=?", (eid,))
    nf = nd = 0
    for d in art["disciplinas"]:
        for it in d["itens"]:
            for k, f in enumerate(it["frases"], 1):
                con.execute("insert into edital_frases(edital_id,disciplina_edital,disciplina_id,item_ordem,item_rotulo,frase_ordem,codigo,texto) values(?,?,?,?,?,?,?,?)",
                            (eid, d["codigo"], disc[d["disciplina_banco"]], it["ordem"], it["rotulo"], k, f["id"], f["texto"]))
                fid = con.execute("select id from edital_frases where edital_id=? and codigo=?", (eid, f["id"])).fetchone()[0]
                nf += 1
                for x in f["destinos"]:
                    novo = x["p"].startswith("NP-")
                    con.execute("insert into edital_frase_destinos(frase_id,ponto_id,proposto_id,papel,trecho,origem) values(?,?,?,?,?,?)",
                                (fid, None if novo else pid[x["p"]], prop[x["p"]] if novo else None, x["papel"], x["trecho"], x["origem"]))
                    nd += 1
    con.execute("delete from edital_blocos where edital_id=?", (eid,))
    for ordem, d in enumerate(art["disciplinas"], 1):
        con.execute("insert into edital_blocos(edital_id,sigla,titulo_no_edital,disciplina_id,ordem) values(?,?,?,?,?)",
                    (eid, d["codigo"], d.get("titulo_no_edital") or d["codigo"], disc[d["disciplina_banco"]], ordem))
    con.execute("delete from edital_pontos_fora where edital_id=?", (eid,))
    for x in art.get("fora_do_edital", []):
        con.execute("insert into edital_pontos_fora(edital_id,ponto_id,motivo,origem) values(?,?,?,?)", (eid, pid[x["p"]], x["motivo"], "decisao IA (rascunho)"))
    conf = art.get("blocos_confirmados", [])     # blocos que o usuário confirmou (diretiva CONFIRMADO em decisoes.txt)
    if conf:
        ph = ",".join("?" * len(conf))
        con.execute(f"""update edital_frase_destinos set confirmado=1 where frase_id in
                        (select id from edital_frases where edital_id=? and disciplina_edital in ({ph}))""", (eid, *conf))
        con.execute(f"""update edital_pontos_fora set confirmado=1 where edital_id=? and ponto_id in
                        (select p.id from pontos p where p.disciplina_id in (select distinct disciplina_id from edital_frases where edital_id=? and disciplina_edital in ({ph})))""", (eid, eid, *conf))
    # conferência
    esperado_f = sum(len(i["frases"]) for d in art["disciplinas"] for i in d["itens"])
    esperado_d = sum(len(f["destinos"]) for d in art["disciplinas"] for i in d["itens"] for f in i["frases"])
    bd_f = con.execute("select count(*) from edital_frases where edital_id=?", (eid,)).fetchone()[0]
    bd_d = con.execute("select count(*) from edital_frase_destinos d join edital_frases f on f.id=d.frase_id where f.edital_id=?", (eid,)).fetchone()[0]
    sem_principal = con.execute("""select count(*) from edital_frases f where edital_id=? and not exists
        (select 1 from edital_frase_destinos d where d.frase_id=f.id and d.papel='principal')""", (eid,)).fetchone()[0]
    assert (bd_f, bd_d, sem_principal) == (esperado_f, esperado_d, 0), (bd_f, esperado_f, bd_d, esperado_d, sem_principal)
    con.execute("insert into log_alteracoes(quem,o_que) values('script 52', ?)",
                (f"edital classificado {slug} (edital_id {eid}): {nf} frases, {nd} destinos, {len(prop)} propostas" + (" [simulação]" if simular else ""),))
    if simular:
        print("SIMULAÇÃO (cópia em memória; o banco real não foi tocado)")
    else:
        con.commit()
    print(f"edital_id {eid}: {nf} frases, {nd} destinos, {len(prop)} propostas de tópico; todas as frases têm tópico principal")


if __name__ == "__main__":
    main()
