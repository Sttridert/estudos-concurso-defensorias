"""Testes do grupo E (comentar_gravar, lib_comentarios, comentar_exportar). Rodar: python -I scripts/comentar_testes.py"""
import json, sqlite3, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_comentarios as LC
import comentar_gravar as G
import comentar_exportar as X

FONTE = "Art. 5º, LXXIV: o Estado prestará assistência jurídica integral e gratuita aos que comprovarem insuficiência de recursos."


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        (self.raiz / "dados" / "fontes").mkdir(parents=True)
        (self.raiz / "dados" / "fontes" / "cf.txt").write_text(FONTE, encoding="utf-8")
        self.con = sqlite3.connect(":memory:")
        self.con.executescript("""create table provas(id integer primary key, nome text);
          create table questoes(id integer primary key, prova_id int, numero int, situacao text);
          create table comentarios(questao_id int primary key, texto text, pegadinha text, dispositivos text, estado text default 'rascunho',
                                   pendente_confirmacao int default 0, autor text, atualizado_em text);
          insert into provas values(1,'P');
          insert into questoes values(1,1,1,'valida'),(2,1,2,'valida'),(3,1,3,'anulada');""")
        LC.garantir_tabela(self.con)

    def tearDown(self):
        self.tmp.cleanup()

    def gravar(self, dados, **kw):
        return G.processar(self.con, dados, aplicar=kw.pop("aplicar", True), raiz=self.raiz, **kw)

    def entrada(self, **extra):
        e = {"c": "texto", "p": "peg", "d": ["CF|art. 5º, LXXIV"],
             "fontes": [{"dispositivo": "CF|art. 5º, LXXIV", "trecho": "assistência jurídica integral e gratuita",
                         "arquivo": "dados/fontes/cf.txt", "consultado_em": "2026-11-20"}]}
        e.update(extra)
        return e


class Testes(Base):
    def test_grava_novo_com_fonte_conferida(self):
        r, p = self.gravar({"P|1": self.entrada()})
        self.assertEqual((r["novo"], p), (1, []))
        self.assertEqual(self.con.execute("select pendente_confirmacao from comentarios").fetchone()[0], 0)
        self.assertEqual(self.con.execute("select count(*) from comentario_fontes").fetchone()[0], 1)

    def test_trecho_inexistente_barra_tudo(self):
        e = self.entrada(); e["fontes"][0]["trecho"] = "trecho que não existe na fonte nenhuma"
        r, p = self.gravar({"P|1": e, "P|2": self.entrada()})
        self.assertTrue(p)
        self.assertEqual(self.con.execute("select count(*) from comentarios").fetchone()[0], 0)

    def test_dispositivo_sem_trecho_vira_pendente(self):
        r, p = self.gravar({"P|1": self.entrada(fontes=[])})
        self.assertEqual((r["forcado_pendente"], p), (1, []))
        self.assertEqual(self.con.execute("select pendente_confirmacao from comentarios").fetchone()[0], 1)

    def test_arquivo_fora_de_dados_fontes_recusado(self):
        (self.raiz / "x.txt").write_text(FONTE, encoding="utf-8")
        e = self.entrada(); e["fontes"][0]["arquivo"] = "x.txt"
        self.assertTrue(self.gravar({"P|1": e})[1])

    def test_nao_sobrescreve_existente_sem_pedido(self):
        self.gravar({"P|1": self.entrada(c="primeiro")})
        r, p = self.gravar({"P|1": self.entrada(c="segundo")})
        self.assertEqual(r["existe"], 1)
        self.assertEqual(self.con.execute("select texto from comentarios").fetchone()[0], "primeiro")

    def test_substituir_troca_rascunho(self):
        self.gravar({"P|1": self.entrada(c="primeiro")})
        self.gravar({"P|1": self.entrada(c="segundo")}, substituir=True)
        self.assertEqual(self.con.execute("select texto from comentarios").fetchone()[0], "segundo")

    def test_conferido_nunca_e_sobrescrito(self):
        self.gravar({"P|1": self.entrada(c="primeiro")})
        self.con.execute("update comentarios set estado='conferido'")
        r, p = self.gravar({"P|1": self.entrada(c="segundo")}, substituir=True)
        self.assertTrue(p)
        self.assertEqual(self.con.execute("select texto from comentarios").fetchone()[0], "primeiro")

    def test_questao_nao_valida_recusada(self):
        self.assertTrue(self.gravar({"P|3": self.entrada()})[1])

    def test_formato_invalido(self):
        for ruim in ({"c": ""}, {"c": "x", "d": ["sem barra"]}, {"c": "x", "pend": 5}):
            self.assertTrue(self.gravar({"P|1": ruim})[1], ruim)

    def test_simulacao_nao_grava(self):
        self.gravar({"P|1": self.entrada()}, aplicar=False)
        self.assertEqual(self.con.execute("select count(*) from comentarios").fetchone()[0], 0)

    def test_exportar_traz_fontes(self):
        self.gravar({"P|1": self.entrada()})
        out = X.montar(self.con)
        self.assertEqual(out["P|1"]["fontes"][0]["arquivo"], "dados/fontes/cf.txt")
        self.assertEqual(out["P|1"]["estado"], "rascunho")


if __name__ == "__main__":
    unittest.main(verbosity=1)
