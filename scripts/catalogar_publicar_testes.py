#!/usr/bin/env python3
"""Testes de catalogar_publicar.py (publicação incremental) e da criação de disciplina do zero (lib_rascunho.ler_roteiro, criar_do_zero, tirar_ponto).

Rodar: python -I scripts/catalogar_publicar_testes.py
Cada teste monta um banco temporário com o ESQUEMA REAL do projeto (copiado de banco/estudos.db, sem dados) e pastas temporárias; nada toca nos dados reais.
"""
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalogar_publicar as P  # noqa: E402
import lib_rascunho as R  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BANCO_REAL = RAIZ / "banco" / "estudos.db"


def esquema_real():
    con = sqlite3.connect(f"file:{BANCO_REAL}?mode=ro", uri=True)
    try:
        return [r[0] for r in con.execute("select sql from sqlite_master where sql is not null and name not like 'sqlite_%' order by type desc, name")]
    finally:
        con.close()


ESQUEMA = esquema_real()


def criar_banco(caminho):
    con = sqlite3.connect(caminho)
    for sql in ESQUEMA:
        con.execute(sql)
    con.execute("insert into disciplinas(id,nome) values (1,'Disciplina Alfa'),(2,'Disciplina Delta')")
    con.execute("insert into assuntos(id,disciplina_id,codigo,nome) values (1,1,'AL01','Fundamentos'),(2,1,'AL02','Institutos'),(3,2,'DE01','Delta geral')")
    pontos = [(1, 1, 1, "AL01.01", "Conceito"), (2, 1, 1, "AL01.02", "Fontes"), (3, 1, 2, "AL02.01", "Contrato"), (4, 1, 2, "AL02.02", "Garantia"),
              (5, 2, 3, "DE01.01", "Ponto de Delta")]
    con.executemany("insert into pontos(id,disciplina_id,assunto_id,codigo,texto,ativo) values (?,?,?,?,?,1)", pontos)
    con.execute("insert into provas(id,nome,ano,banca,cargo) values (1,'Prova X',2025,'FCC','Analista')")
    for n in range(1, 6):
        con.execute("insert into questoes(id,prova_id,numero,disciplina_id,situacao) values (?,1,?,1,'valida')", (n, n))
    # q1 -> AL01.01 ; q2 -> AL01.02 ; q3 -> AL02.01 (+ AL02.02) ; q4 -> AL02.02 ; q5 -> AL01.02 (+ AL01.01)
    con.executemany("insert into classificacao(questao_id,ponto_id,ponto2_id,origem,revisada) values (?,?,?,?,0)",
                    [(1, 1, None, "IA"), (2, 2, None, "IA"), (3, 3, 4, "IA"), (4, 4, None, "IA"), (5, 2, 1, "IA")])
    con.execute("insert into edital_itens(id,disciplina_id,codigo,texto,versao) values (1,1,'I1','item um','v1'),(2,1,'I2','item dois','v1')")
    con.executemany("insert into edital_item_pontos(item_id,ponto_id) values (?,?)", [(1, 2), (1, 1), (2, 4)])
    con.commit()
    con.close()


def catalogo_v1_alfa(pasta):
    cat = {"disciplina": "Disciplina Alfa",
           "assuntos": [{"codigo": "AL01", "nome": "Fundamentos", "descricao": None}, {"codigo": "AL02", "nome": "Institutos", "descricao": None}],
           "pontos": [{"codigo": "AL01.01", "assunto": "AL01", "texto": "Conceito", "descricao": None, "origem": "t", "ativo": 1},
                      {"codigo": "AL01.02", "assunto": "AL01", "texto": "Fontes", "descricao": None, "origem": "t", "ativo": 1},
                      {"codigo": "AL02.01", "assunto": "AL02", "texto": "Contrato", "descricao": None, "origem": "t", "ativo": 1},
                      {"codigo": "AL02.02", "assunto": "AL02", "texto": "Garantia", "descricao": None, "origem": "t", "ativo": 1}]}
    (pasta / "alfa.json").write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")


def dump(con, tabelas):
    h = hashlib.sha256()
    for t in tabelas:
        for r in con.execute(f"select * from {t} order by 1,2"):
            h.update(repr(r).encode())
    return h.hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pub_test_"))
        self.banco = self.tmp / "t.db"
        criar_banco(self.banco)
        self.pasta = self.tmp / "cat"
        self.pasta.mkdir()
        self._pasta_r, self._cat_p = R.PASTA, P.CAT
        R.PASTA = self.pasta
        P.CAT = self.pasta
        catalogo_v1_alfa(self.pasta)

    def tearDown(self):
        R.PASTA, P.CAT = self._pasta_r, self._cat_p
        shutil.rmtree(self.tmp, ignore_errors=True)

    def con(self):
        c = sqlite3.connect(self.banco)
        c.isolation_level = None
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def publicar(self, slugs):
        c = self.con()
        try:
            c.execute("BEGIN IMMEDIATE")
            r = P._gravar(c, P.carregar_rascunhos(slugs))
            c.execute("COMMIT")
            return r
        except Exception:
            c.execute("ROLLBACK")
            raise
        finally:
            c.close()


class TestRoteiroEDoZero(Base):
    def test_ler_roteiro_basico(self):
        a = R.ler_roteiro("// c\n# Um | desc\n- A | d1\n- B\n# Dois\n- C | @Disciplina Alfa:AL01.01\n")
        self.assertEqual([x["nome"] for x in a], ["Um", "Dois"])
        self.assertEqual(a[0]["pontos"][0], {"texto": "A", "descricao": "d1", "adotar": None})
        self.assertEqual(a[1]["pontos"][0]["adotar"], {"disciplina": "Disciplina Alfa", "codigo": "AL01.01"})
        self.assertIsNone(a[1]["pontos"][0]["descricao"])

    def test_ler_roteiro_erros_com_numero_de_linha(self):
        for texto, trecho in [("- A\n", "linha 1"), ("# X\n", "sem tópico"), ("", "vazio"), ("# X\n- \n", "linha 2"), ("solto\n", "linha 1"),
                              ("# X\n- A\n- a\n", "repetido"), ("# X\n- A | @Sem formato\n", "@Disciplina:CÓDIGO")]:
            with self.assertRaises(R.ErroOp) as e:
                R.ler_roteiro(texto)
            self.assertIn(trecho, str(e.exception), texto)

    def test_criar_do_zero_valida_e_grava(self):
        a = R.ler_roteiro("# Um\n- A\n- B\n# Dois\n- C\n")
        with self.assertRaises(R.ErroOp):
            R.criar_do_zero("Bad Slug", "X", "XX", a)
        with self.assertRaises(R.ErroOp):
            R.criar_do_zero("beta", "Beta", "be", a)
        d = R.criar_do_zero("beta", "Disciplina Beta", "BE", a)
        self.assertTrue(d["do_zero"])
        self.assertEqual(d["base_v1"], {"assuntos": {}, "pontos": {}})
        cods = R.codigos(R.carregar("beta"))
        self.assertEqual(sorted(cods.values()), ["BE01", "BE01.01", "BE01.02", "BE02", "BE02.01"])
        with self.assertRaises(R.ErroOp):
            R.criar_do_zero("beta", "Disciplina Beta", "BE", a)                  # já existe

    def test_editor_funciona_com_rascunho_do_zero(self):
        R.criar_do_zero("beta", "Disciplina Beta", "BE", R.ler_roteiro("# Um\n- A\n- B\n# Dois\n- C\n- D\n"))
        d = R.carregar("beta")
        v = R.visao(d, banco=self.banco)
        self.assertEqual(len(v["assuntos"]), 2)
        self.assertTrue(all(p["novo"] for a in v["assuntos"] for p in a["pontos"]))
        R.comparacao(d, banco=self.banco)
        R.visao_v1(d, banco=self.banco)
        R.mapa(d)
        R.aplicar_op("beta", {"op": "editar_ponto", "uid": d["assuntos"][0]["pontos"][0]["uid"], "texto": "A renomeado"}, banco=self.banco)
        self.assertIn("beta", [c["slug"] for c in R.catalogos_disponiveis() if c["sem_v1"]])

    def test_tirar_ponto_exige_um_destino_so(self):
        R.criar_de_v1("alfa")
        with self.assertRaises(R.ErroOp):
            R.tirar_ponto("alfa", "AL01.02")
        with self.assertRaises(R.ErroOp):
            R.tirar_ponto("alfa", "AL01.02", destino_externo={"disciplina": "x", "codigo": "y"}, movido_para="z")
        with self.assertRaises(R.ErroOp):
            R.tirar_ponto("alfa", "ZZ99.99", movido_para="z")
        d = R.tirar_ponto("alfa", "AL01.02", movido_para="beta")
        self.assertEqual(d["lixeira"][0]["movido_para"], "beta")
        self.assertNotIn("AL01.02", [p.get("antigo") for a in d["assuntos"] for p in a["pontos"]])


class TestPublicarIncremental(Base):
    def rascunho_alfa_editado(self):
        d = R.criar_de_v1("alfa")
        u = {p["antigo"]: p["uid"] for a in d["assuntos"] for p in a["pontos"]}
        R.aplicar_op("alfa", {"op": "editar_ponto", "uid": u["AL01.01"], "texto": "Conceito geral"}, banco=self.banco)
        R.aplicar_op("alfa", {"op": "apagar_ponto", "uid": u["AL01.02"], "destino": u["AL01.01"]}, banco=self.banco)
        R.aplicar_op("alfa", {"op": "novo_ponto", "assunto": d["assuntos"][1]["uid"], "texto": "Ponto novo"}, banco=self.banco)
        R.aplicar_op("alfa", {"op": "novo_assunto", "nome": "Assunto novo"}, banco=self.banco)
        return u

    def test_mantidos_reaproveitam_o_id_e_fusao_reaponta(self):
        self.rascunho_alfa_editado()
        antes_delta = dump(self.con(), ["pontos"])
        r = self.publicar(["alfa"])
        c = self.con()
        self.assertEqual(c.execute("select texto from pontos where id=1").fetchone()[0], "Conceito geral")     # mesmo id, texto novo
        self.assertEqual(c.execute("select ativo,codigo from pontos where id=2").fetchone(), (0, "AL01.02#v1"))   # fundido e arquivado
        self.assertEqual(c.execute("select ponto_id from classificacao where questao_id=2").fetchone()[0], 1)    # q2 foi para o destino
        self.assertEqual(c.execute("select ponto_id,ponto2_id from classificacao where questao_id=5").fetchone(), (1, None))  # ponto2 igual ao principal some
        self.assertEqual(sorted(x[0] for x in c.execute("select ponto_id from edital_item_pontos where item_id=1")), [1])      # ligação duplicada mesclada
        self.assertEqual(c.execute("select count(*) from classificacao").fetchone()[0], 5)
        self.assertEqual(c.execute("select count(*) from pontos where disciplina_id=1 and ativo=1").fetchone()[0], 4)           # 3 mantidos + 1 novo
        self.assertEqual(r["pontos inseridos"], 1)
        self.assertEqual(r["assuntos inseridos"], 1)
        self.assertEqual(r["pontos fundidos e arquivados"], 1)
        self.assertEqual(c.execute("select codigo from pontos where texto='Ponto novo'").fetchone()[0], "AL02.03")
        # a disciplina que não foi publicada ficou intacta
        self.assertEqual(c.execute("select codigo,texto,ativo from pontos where id=5").fetchone(), ("DE01.01", "Ponto de Delta", 1))
        del antes_delta
        c.close()

    def test_marca_migrada_sem_apagar_origem_e_sem_revisar(self):
        self.rascunho_alfa_editado()
        self.publicar(["alfa"])
        c = self.con()
        origens = dict(c.execute("select questao_id,origem from classificacao"))
        self.assertTrue(origens[1].startswith("IA") and "migrada v1 para v2" in origens[1])     # renomeado
        self.assertIn("migrada", origens[2])                                                    # fundido
        self.assertNotIn("migrada", origens[4])                                                 # AL02.02 só foi renumerado ou mantido
        self.assertEqual(c.execute("select count(*) from classificacao where revisada=1").fetchone()[0], 0)
        c.close()

    def test_disciplina_do_zero_cria_e_nao_mexe_nas_outras(self):
        R.criar_do_zero("beta", "Disciplina Beta", "BE", R.ler_roteiro("# Um\n- A\n- B\n# Dois\n- C\n"))
        c = self.con()
        antes = dump(c, ["pontos", "assuntos", "classificacao", "edital_item_pontos"])
        c.close()
        r = self.publicar(["beta"])
        c = self.con()
        self.assertEqual(r["disciplinas criadas"], 1)
        self.assertEqual(c.execute("select count(*) from pontos p join disciplinas d on d.id=p.disciplina_id where d.nome='Disciplina Beta' and p.ativo=1").fetchone()[0], 3)
        self.assertEqual(c.execute("select count(*) from assuntos a join disciplinas d on d.id=a.disciplina_id where d.nome='Disciplina Beta'").fetchone()[0], 2)
        antigas = dump(c, ["classificacao", "edital_item_pontos"])
        self.assertEqual(antigas, dump(sqlite3.connect(self.banco), ["classificacao", "edital_item_pontos"]))
        self.assertEqual(c.execute("select count(*) from pontos where disciplina_id in (1,2)").fetchone()[0], 5)
        del antes
        c.close()

    def test_do_zero_recusa_disciplina_que_ja_tem_pontos(self):
        R.criar_do_zero("alfa2", "Disciplina Alfa", "AL", R.ler_roteiro("# Um\n- A\n"))
        with self.assertRaises(AssertionError) as e:
            self.publicar(["alfa2"])
        self.assertIn("já tem pontos", str(e.exception))

    def test_adocao_exige_publicar_junto_e_move_o_registro(self):
        R.criar_de_v1("alfa")
        R.criar_do_zero("gama", "Disciplina Gama", "GA", R.ler_roteiro("# Garantias\n- Garantia adotada | @Disciplina Alfa:AL02.02\n- Outro\n"),
                        textos_banco={("Disciplina Alfa", "AL02.02"): "Garantia"})
        R.tirar_ponto("alfa", "AL02.02", movido_para="gama")
        with self.assertRaises(AssertionError) as e:
            self.publicar(["gama"])                                   # a origem (alfa) não vai junto
        self.assertIn("publicada junto", str(e.exception))
        with self.assertRaises(AssertionError):
            self.publicar(["alfa"])                                   # o adotante (gama) não vai junto
        c = self.con()
        self.assertEqual(c.execute("select codigo from pontos where id=4").fetchone()[0], "AL02.02")    # nada mudou nas falhas
        c.close()
        r = self.publicar(["alfa", "gama"])
        c = self.con()
        self.assertEqual(c.execute("select d.nome from pontos p join disciplinas d on d.id=p.disciplina_id where p.id=4").fetchone()[0], "Disciplina Gama")   # mesmo id
        self.assertEqual(c.execute("select ponto_id from classificacao where questao_id=4").fetchone()[0], 4)
        self.assertEqual(r["mantidos: mudou de disciplina"], 1)
        self.assertIn("migrada", c.execute("select origem from classificacao where questao_id=4").fetchone()[0])
        c.close()

    def test_destino_externo_funde_em_outra_disciplina(self):
        R.criar_de_v1("alfa")
        R.tirar_ponto("alfa", "AL01.02", destino_externo={"disciplina": "Disciplina Delta", "codigo": "DE01.01"})
        self.publicar(["alfa"])
        c = self.con()
        self.assertEqual(c.execute("select ponto_id from classificacao where questao_id=2").fetchone()[0], 5)
        self.assertEqual(c.execute("select ativo from pontos where id=2").fetchone()[0], 0)
        self.assertEqual(c.execute("select codigo,ativo from pontos where id=5").fetchone(), ("DE01.01", 1))                        # destino não renumerado
        c.close()

    def test_falha_desfaz_tudo(self):
        d = R.criar_de_v1("alfa")
        R.aplicar_op("alfa", {"op": "editar_ponto", "uid": d["assuntos"][0]["pontos"][0]["uid"], "texto": "Mudado"}, banco=self.banco)
        arq = self.pasta / "_rascunho_alfa_v2.json"
        j = json.loads(arq.read_text(encoding="utf-8"))
        j["lixeira"].append({"uid": "v1:AL02.02", "antigo": "AL02.02", "texto": "Garantia", "descricao": None, "assunto_uid": "v1:AL02", "apagado_em": "x", "destino": None})
        j["assuntos"][1]["pontos"] = [p for p in j["assuntos"][1]["pontos"] if p["antigo"] != "AL02.02"]
        arq.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")                 # ponto apagado SEM destino: a gravação deve falhar
        c = self.con()
        antes = dump(c, ["pontos", "assuntos", "classificacao", "edital_item_pontos", "log_alteracoes"])
        c.close()
        with self.assertRaises(AssertionError):
            self.publicar(["alfa"])
        c = self.con()
        self.assertEqual(antes, dump(c, ["pontos", "assuntos", "classificacao", "edital_item_pontos", "log_alteracoes"]))
        c.close()

    def test_codigos_arquivados_nao_colidem_em_publicacoes_sucessivas(self):
        c = self.con()
        self.assertEqual(P._arquivar_codigo(c, "pontos", 1, "AL01.01"), "AL01.01#v1")
        c.execute("update pontos set codigo='AL01.01#v1' where id=1")
        self.assertEqual(P._arquivar_codigo(c, "pontos", 1, "AL01.01"), "AL01.01#v2")
        c.close()

    def test_simular_nao_toca_no_banco(self):
        self.rascunho_alfa_editado()
        antes = hashlib.sha256(self.banco.read_bytes()).hexdigest()
        rel = self.tmp / "rel.json"
        self.assertEqual(P.simular_cmd(["--simular", "--disciplina", "alfa", "--banco", str(self.banco), "--saida", str(rel)]), 0)
        self.assertEqual(antes, hashlib.sha256(self.banco.read_bytes()).hexdigest())
        self.assertEqual(json.loads(rel.read_text(encoding="utf-8"))["pontos fundidos e arquivados"], 1)

    def test_aplicar_no_banco_padrao_recusa_sem_a_palavra_do_usuario(self):
        self.assertEqual(P.aplicar_cmd(["--aplicar", "--disciplina", "alfa"]), 2)
        self.assertEqual(P.aplicar_cmd(["--aplicar", "--sim-do-usuario"]), 2)                  # sem dizer quais rascunhos
        self.assertEqual(P.simular_cmd(["--simular"]), 2)

    def test_aplicar_em_banco_de_teste_grava(self):
        self.rascunho_alfa_editado()
        self.assertEqual(P.aplicar_cmd(["--aplicar", "--disciplina", "alfa", "--banco", str(self.banco)]), 0)
        c = self.con()
        self.assertEqual(c.execute("select texto from pontos where id=1").fetchone()[0], "Conceito geral")
        self.assertEqual(c.execute("select count(*) from log_alteracoes").fetchone()[0], 1)
        c.close()

class TestComandoNovo(Base):
    """catalogar_novo.py: criar (do zero e com adoção), destino e evidência, sobre banco e arquivos temporários."""

    def setUp(self):
        super().setUp()
        import catalogar_novo as N
        self.N = N
        self._n = (N.DISCIPLINAS, N.BANCO)
        self.disc = self.tmp / "disciplinas.json"
        self.disc.write_text(json.dumps({"ordem_extracao": [], "disciplinas": [{"sigla": "AL", "nome": "Disciplina Alfa", "prefixo": "AL", "padroes_titulo": [],
                                                                               "edital_ficticio": False, "extrair_edital_real": False}]}, ensure_ascii=False), encoding="utf-8")
        N.DISCIPLINAS, N.BANCO = self.disc, self.banco
        self.roteiro = self.tmp / "roteiro.txt"

    def tearDown(self):
        self.N.DISCIPLINAS, self.N.BANCO = self._n
        super().tearDown()

    def test_criar_do_zero_registra_disciplina_e_rascunho(self):
        self.roteiro.write_text("# Um\n- A\n- B | descricao\n# Dois\n- C\n", encoding="utf-8")
        self.N.criar(["BE", "Disciplina Beta", "--prefixo", "BE", "--roteiro", str(self.roteiro)])
        self.assertTrue(R.existe("disciplina-beta"))
        d = R.carregar("disciplina-beta")
        self.assertEqual(sum(len(a["pontos"]) for a in d["assuntos"]), 3)
        registro = json.loads(self.disc.read_text(encoding="utf-8"))["disciplinas"]
        self.assertEqual([x["sigla"] for x in registro], ["AL", "BE"])
        self.assertEqual(registro[1]["prefixo"], "BE")

    def test_criar_simular_nao_grava_nada(self):
        self.roteiro.write_text("# Um\n- A\n", encoding="utf-8")
        antes = self.disc.read_text(encoding="utf-8")
        self.N.criar(["BE", "Disciplina Beta", "--prefixo", "BE", "--roteiro", str(self.roteiro), "--simular"])
        self.assertEqual(antes, self.disc.read_text(encoding="utf-8"))
        self.assertFalse(R.existe("disciplina-beta"))

    def test_criar_recusa_sigla_prefixo_e_nome_repetidos_e_disciplina_com_pontos(self):
        self.roteiro.write_text("# Um\n- A\n", encoding="utf-8")
        for args in (["AL", "Outra", "--prefixo", "XX"], ["XX", "Outra", "--prefixo", "AL"], ["XX", "Disciplina Alfa", "--prefixo", "XX"]):
            with self.assertRaises(SystemExit):
                self.N.criar(args + ["--roteiro", str(self.roteiro)])
        self.disc.write_text(json.dumps({"ordem_extracao": [], "disciplinas": []}), encoding="utf-8")
        with self.assertRaises(SystemExit):                              # 'Disciplina Alfa' já tem pontos no banco
            self.N.criar(["AL", "Disciplina Alfa", "--prefixo", "AL", "--roteiro", str(self.roteiro)])
        self.assertFalse(R.existe("disciplina-alfa"))

    def test_criar_com_adocao_exige_rascunho_da_origem_e_registra_a_saida(self):
        self.roteiro.write_text("# Garantias\n- Garantia adotada | @Disciplina Alfa:AL02.02\n- Outro\n", encoding="utf-8")
        with self.assertRaises(SystemExit):                              # a origem ainda não tem rascunho
            self.N.criar(["GA", "Disciplina Gama", "--prefixo", "GA", "--roteiro", str(self.roteiro)])
        self.assertFalse(R.existe("disciplina-gama"))
        shutil.copy(self.pasta / "alfa.json", self.pasta / "disciplina-alfa.json")
        R.criar_de_v1("disciplina-alfa")
        self.N.criar(["GA", "Disciplina Gama", "--prefixo", "GA", "--roteiro", str(self.roteiro)])
        d = R.carregar("disciplina-gama")
        self.assertEqual([p["antigo"] for a in d["assuntos"] for p in a["pontos"]], ["AL02.02", None])
        self.assertEqual(d["base_v1"]["pontos"]["v1:AL02.02"]["banco"], {"disciplina": "Disciplina Alfa", "codigo": "AL02.02"})
        self.assertEqual(d["base_v1"]["pontos"]["v1:AL02.02"]["texto"], "Garantia")                  # texto atual do banco, para o mapa
        origem = R.carregar("disciplina-alfa")
        self.assertEqual(origem["lixeira"][0]["movido_para"], "disciplina-gama")
        self.roteiro.write_text("# X\n- Y | @Disciplina Alfa:AL09.09\n", encoding="utf-8")
        with self.assertRaises(SystemExit):                              # ponto que não existe no banco
            self.N.criar(["ZZ", "Disciplina Zeta", "--prefixo", "ZZ", "--roteiro", str(self.roteiro)])

    def test_destino_funde_em_outra_disciplina(self):
        R.criar_de_v1("alfa")
        self.N.destino(["alfa", "AL01.02", "Disciplina Delta", "DE01.01"])
        self.assertEqual(R.carregar("alfa")["lixeira"][0]["destino_externo"], {"disciplina": "Disciplina Delta", "codigo": "DE01.01"})
        with self.assertRaises(SystemExit):
            self.N.destino(["alfa", "AL02.01", "Disciplina Delta", "DE09.09"])

    def test_evidencia_so_le(self):
        c = sqlite3.connect(self.banco)
        c.execute("update edital_itens set n_editais=7 where id=1")
        c.commit()
        c.close()
        antes = hashlib.sha256(self.banco.read_bytes()).hexdigest()
        self.N.evidencia(["item um"])
        self.assertEqual(antes, hashlib.sha256(self.banco.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=1)
