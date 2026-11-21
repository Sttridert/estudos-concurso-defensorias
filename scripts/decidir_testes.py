#!/usr/bin/env python3
"""Testes do grupo D (Decidir): lib_perfil (hash, leitura, escrita) e 72_perfil (validações, confirmar, mostrar).
Rodar: python -I scripts/decidir_testes.py
Usam pasta temporária no lugar de produtos/apostilas e só leem o banco real (somente leitura)."""
import contextlib
import gc
import importlib.util
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_perfil as LP  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
spec = importlib.util.spec_from_file_location("p72", RAIZ / "scripts" / "72_perfil.py")
P72 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P72)


def concurso():
    return {"nome": "Teste", "banca": "FCC", "carreira": "Defensoria Pública", "cargo": "Analista Jurídico", "orgao": "DPE-AM",
            "ano_referencia": 2026, "edital_id": 4, "meia_vida": 8, "estudo_geral": False, "pesos": {"A": 1, "B": 0.5, "C": 0.25},
            "universo": {"nome": "Analista FCC", "descricao": "d", "filtro": {"bancas": ["FCC"], "cargos_prefixo": ["Analista"]}},
            "apostila": [{"id": 901, "disciplina": "Direito Penal", "bloco": "PENAL", "nome": "A"},
                         {"id": 902, "disciplina": "Direito Civil", "bloco": "CIV", "nome": "B"}]}


def banco():
    return sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(gc.collect)          # solta conexões do banco abertas pelo 72 (o Windows não apaga arquivo aberto)
        self.original = LP.APOSTILAS
        LP.APOSTILAS = Path(self.tmp.name)       # o 72 usa LP.APOSTILAS, então as duas bibliotecas veem a pasta temporária
        self.addCleanup(lambda: setattr(LP, "APOSTILAS", self.original))
        pasta = LP.APOSTILAS / "Conc"
        pasta.mkdir()
        self.arq = pasta / "perfil.toml"
        LP.escrever(self.arq, concurso())

    def confirma(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            P72.confirmar(["confirmar", "Conc", *args])
        return out.getvalue()

    def edita(self, fn):
        c = LP.ler(self.arq)
        fn(c)
        LP.escrever(self.arq, c)


class TestLibPerfil(Base):
    def test_escrever_e_reler_sem_perder_campos(self):
        c = LP.ler(self.arq)
        self.assertEqual(c["banca"], "FCC")
        self.assertEqual(c["pesos"], {"A": 1, "B": 0.5, "C": 0.25})
        self.assertEqual(c["universo"]["filtro"], {"bancas": ["FCC"], "cargos_prefixo": ["Analista"]})
        self.assertEqual([a["id"] for a in c["apostila"]], [901, 902])

    def test_impressao_muda_com_cada_campo_que_define_o_perfil(self):
        base = LP.impressao(LP.ler(self.arq), LP.ler(self.arq)["apostila"][0])
        mudancas = {
            "banca": lambda c: c.update(banca="Cebraspe"),
            "meia_vida": lambda c: c.update(meia_vida=5),
            "pesos": lambda c: c.update(pesos={"A": 1, "B": 0.4, "C": 0.2}),
            "filtro do universo": lambda c: c["universo"].update(filtro={}),
            "bloco": lambda c: c["apostila"][0].update(bloco="OUTRO"),
            "disciplina": lambda c: c["apostila"][0].update(disciplina="Direito Civil"),
            "edital": lambda c: c.update(edital_id=8),
            "órgão": lambda c: c.update(orgao="DPE-SP"),
            "cargo": lambda c: c.update(cargo="X"),
        }
        for nome, fn in mudancas.items():
            c = LP.ler(self.arq)
            fn(c)
            self.assertNotEqual(LP.impressao(c, c["apostila"][0]), base, f"o hash devia mudar com {nome}")

    def test_impressao_nao_muda_com_nome_ou_observacao(self):
        c = LP.ler(self.arq)
        a = c["apostila"][0]
        base = LP.impressao(c, a)
        a["nome"] = "outro nome"
        a["observacoes"] = "texto"
        c["nome"] = "x"
        self.assertEqual(LP.impressao(c, a), base)

    def test_proximo_id_passa_do_maior(self):
        con = banco()
        aposentados = [i for (i,) in con.execute("select id from perfis_aposentada_2026_11_16")]
        self.assertEqual(LP.proximo_id(con), max([902] + aposentados) + 1)

    def test_perfil_alterado_depois_de_confirmar_conta_como_nao_confirmado(self):
        self.confirma()
        con = banco()
        self.assertEqual(LP.perfil_do_arquivo(con, 901)["confirmado_pelo_usuario"], 1)
        self.edita(lambda c: c.update(banca="Cebraspe"))
        p = LP.perfil_do_arquivo(con, 901)
        self.assertEqual(p["confirmado_pelo_usuario"], 0)
        self.assertIn("ALTERADO", p["motivo_nao_confirmado"])

    def test_nunca_confirmado_nao_vale(self):
        self.assertEqual(LP.perfil_do_arquivo(banco(), 901)["confirmado_pelo_usuario"], 0)

    def test_id_inexistente_devolve_none(self):
        self.assertIsNone(LP.perfil_do_arquivo(banco(), 99999))


class TestConfirmar(Base):
    def test_sem_opcao_confirma_so_as_pendentes_e_nao_renova_as_prontas(self):
        self.confirma("--apostila", "901")
        self.edita(lambda c: c["apostila"][0].update(confirmado_em="2020-01-01"))   # data antiga; o hash continua batendo
        self.confirma()
        c = LP.ler(self.arq)
        self.assertEqual(c["apostila"][0]["confirmado_em"], "2020-01-01", "a já confirmada não deve ter a data renovada")
        self.assertTrue(c["apostila"][1].get("confirmado_hash"), "a pendente deve ter sido confirmada")

    def test_todas_renova_a_data(self):
        self.confirma()
        self.edita(lambda c: c["apostila"][0].update(confirmado_em="2020-01-01"))
        self.confirma("--todas")
        self.assertNotEqual(LP.ler(self.arq)["apostila"][0]["confirmado_em"], "2020-01-01")

    def test_apostila_alterada_volta_a_ser_confirmada(self):
        self.confirma()
        self.edita(lambda c: c.update(meia_vida=5))
        saida = self.confirma()
        self.assertIn("confirmando apostila 901", saida)
        self.assertIn("confirmando apostila 902", saida)

    def test_so_a_apostila_pedida(self):
        self.confirma("--apostila", "902")
        c = LP.ler(self.arq)
        self.assertFalse(c["apostila"][0].get("confirmado_hash"))
        self.assertTrue(c["apostila"][1].get("confirmado_hash"))

    def test_nada_pendente_avisa(self):
        self.confirma()
        self.assertIn("nada pendente", self.confirma())


class TestValidacoes(unittest.TestCase):
    def test_pesos_validos(self):
        self.assertEqual(P72.ler_pesos("1,0.5,0.25"), [1.0, 0.5, 0.25])
        self.assertEqual(P72.ler_pesos("1,1,1"), [1.0, 1.0, 1.0])

    def test_pesos_invalidos_recusam(self):
        for ruim in ("1,0.5", "1,0.5,0.25,0.1", "a,b,c", "0.25,0.5,1", "1,0,0", "1,-1,0.5", ""):
            with self.assertRaises(SystemExit, msg=ruim):
                P72.ler_pesos(ruim)

    def test_meia_vida(self):
        self.assertEqual(P72.ler_meia_vida("8"), 8)
        self.assertEqual(P72.ler_meia_vida(5), 5)
        for ruim in ("0", "-3", "x", "2.5"):
            with self.assertRaises(SystemExit, msg=ruim):
                P72.ler_meia_vida(ruim)


class TestMostrar(Base):
    def test_amostra_conta_so_o_universo(self):
        con = banco()
        c = LP.ler(self.arq)
        p_fcc, n_fcc = P72.amostra(con, c, "Direito Penal")
        c["universo"]["filtro"] = {}
        p_todas, n_todas = P72.amostra(con, c, "Direito Penal")
        self.assertGreater(n_fcc, 0)
        self.assertLessEqual(n_fcc, n_todas)
        self.assertLess(p_fcc, p_todas, "'Todas as questões' deve ter mais provas que Analista FCC")
        c["universo"]["filtro"] = {"bancas": ["BancaQueNaoExiste"]}
        self.assertEqual(P72.amostra(con, c, "Direito Penal"), (0, 0))


class BaseComCopia(Base):
    """Base com uma CÓPIA gravável do banco real (o real nunca é tocado); o 72 passa a usar a cópia."""

    def setUp(self):
        super().setUp()
        self.copia = Path(self.tmp.name) / "copia.db"
        origem = banco()
        dest = sqlite3.connect(self.copia)
        origem.backup(dest)
        origem.close()
        self.con = dest
        self.bancoreal = P72.BANCO
        P72.BANCO = self.copia
        self.addCleanup(lambda: setattr(P72, "BANCO", self.bancoreal))
        self.addCleanup(self.con.close)

    def estado(self, pid=901):
        c = LP.ler(self.arq)
        a = next(x for x in c["apostila"] if x["id"] == pid)
        return LP.estado(self.con, c, a)

    def so_de(self, bloco, outro):
        """id de um tópico ativo que o bloco `bloco` usa (disciplina ou frases) e o bloco `outro` não usa"""
        c = LP.ler(self.arq)
        usados = {}
        for sigla in (bloco, outro):
            a = next(x for x in c["apostila"] if x["bloco"] == sigla)
            d = self.con.execute("select id from disciplinas where nome=?", (a["disciplina"],)).fetchone()[0]
            perfil = {"disciplina_id": d, "bloco_edital": sigla, "edital_id": 4}
            usados[sigla] = set(LP.LE.pontos_do_escopo(self.con, perfil, LP.LE.escopo(self.con, perfil), so_ativos=True))
        return min(usados[bloco] - usados[outro])

    def grava(self, sql, *par):
        self.con.execute(sql, par)
        self.con.commit()


class TestBase(BaseComCopia):
    def test_confirmar_grava_a_base_e_fica_em_dia(self):
        self.confirma()
        a = LP.ler(self.arq)["apostila"][0]
        self.assertTrue(a["confirmado_catalogo"])
        self.assertTrue(a["confirmado_edital"])
        self.assertEqual(self.estado(), ("confirmada", ""))

    def test_base_e_calculada_para_cada_apostila(self):
        c = LP.ler(self.arq)
        b1, b2 = (LP.impressao_base(self.con, c, a) for a in c["apostila"])
        self.assertNotEqual(b1["catalogo"], b2["catalogo"])
        self.assertNotEqual(b1["edital"], b2["edital"])

    def test_mudar_texto_de_topico_da_disciplina_muda_o_catalogo(self):
        self.confirma()
        self.grava("update pontos set texto=texto||' X' where id=(select min(p.id) from pontos p join disciplinas d on d.id=p.disciplina_id "
                   "where d.nome='Direito Penal' and p.ativo=1)")
        cod, det = self.estado()
        self.assertEqual(cod, "base_alterada")
        self.assertIn("CATÁLOGO", det)
        self.assertNotIn("EDITAL", det)

    def test_mudar_destino_de_frase_do_bloco_muda_o_edital(self):
        self.confirma()
        self.grava("delete from edital_frase_destinos where id=(select d.id from edital_frase_destinos d join edital_frases f on f.id=d.frase_id "
                   "where f.edital_id=4 and f.disciplina_edital='PENAL' limit 1)")
        cod, det = self.estado()
        self.assertEqual(cod, "base_alterada")
        self.assertIn("EDITAL", det)

    def test_mexer_em_outra_apostila_nao_derruba_esta(self):
        self.confirma()
        con = self.con
        penal = {r[0] for r in con.execute("select id from pontos where disciplina_id=(select id from disciplinas where nome='Direito Penal')")}
        penal |= {r[0] for r in con.execute("select distinct d.ponto_id from edital_frase_destinos d join edital_frases f on f.id=d.frase_id "
                                            "where f.edital_id=4 and f.disciplina_edital='PENAL' and d.ponto_id is not null")}
        civ = con.execute("select id from pontos where disciplina_id=(select id from disciplinas where nome='Direito Civil') and ativo=1").fetchall()
        alvo = next(i for (i,) in civ if i not in penal)
        self.grava("update pontos set texto=texto||' Y' where id=?", alvo)
        self.assertEqual(self.estado(901), ("confirmada", ""))
        self.assertEqual(self.estado(902)[0], "base_alterada")

    def test_ruido_nao_muda_a_base(self):
        """data de criação e o 'confirmado' da frase não são conteúdo (lição da pesquisa: o hash cobre só conteúdo)"""
        self.confirma()
        self.grava("update pontos set criado_em='2000-01-01'")
        self.grava("update edital_frase_destinos set confirmado=1-coalesce(confirmado,0)")
        self.assertEqual(self.estado(), ("confirmada", ""))

    def test_confirmacao_antiga_sem_base_vale_com_aviso(self):
        self.confirma()
        self.edita(lambda c: [c["apostila"][0].pop("confirmado_catalogo"), c["apostila"][0].pop("confirmado_edital")])
        self.assertEqual(self.estado()[0], "sem_base")
        p = LP.perfil_do_arquivo(self.con, 901)
        self.assertEqual(p["confirmado_pelo_usuario"], 1)

    def test_base_alterada_o_motor_recusa_com_motivo(self):
        self.confirma()
        self.grava("update pontos set texto=texto||' Z' where disciplina_id=(select id from disciplinas where nome='Direito Penal') and ativo=1")
        p = LP.perfil_do_arquivo(self.con, 901)
        self.assertEqual(p["confirmado_pelo_usuario"], 0)
        self.assertIn("mudou o CATÁLOGO", p["motivo_nao_confirmado"])

    def test_sem_opcao_o_confirmar_refaz_a_que_ficou_com_base_alterada(self):
        self.confirma()
        self.grava("update pontos set texto=texto||' W' where id=?", self.so_de("PENAL", "CIV"))
        saida = self.confirma()
        self.assertIn("confirmando apostila 901", saida)
        self.assertNotIn("confirmando apostila 902", saida)
        self.assertEqual(self.estado(), ("confirmada", ""))


class TestSlug(BaseComCopia):
    SLUG = "dpeam2026_analista_juridico"

    def test_slug_certo_confere(self):
        c = LP.ler(self.arq)
        c["edital_slug"] = self.SLUG
        self.assertEqual(LP.edital_problemas(self.con, c), [])

    def test_sem_slug_nao_ha_o_que_conferir(self):
        self.assertEqual(LP.edital_problemas(self.con, LP.ler(self.arq)), [])

    def test_slug_de_outro_edital_e_recusado(self):
        c = LP.ler(self.arq)
        c["edital_slug"] = "dpepb2026_analista"          # é o edital 8, e o perfil diz edital 4
        self.assertTrue(LP.edital_problemas(self.con, c))

    def test_slug_inexistente_e_recusado(self):
        c = LP.ler(self.arq)
        c["edital_slug"] = "nao_existe"
        self.assertTrue(LP.edital_problemas(self.con, c))

    def test_vincular_grava_sem_mexer_na_confirmacao(self):
        self.confirma()
        antes = LP.ler(self.arq)["apostila"][0]["confirmado_hash"]
        P72.vincular_edital(["vincular-edital", "Conc", self.SLUG])
        c = LP.ler(self.arq)
        self.assertEqual(c["edital_slug"], self.SLUG)
        self.assertEqual(c["apostila"][0]["confirmado_hash"], antes)
        self.assertEqual(self.estado(), ("confirmada", ""))

    def test_vincular_slug_errado_nao_grava(self):
        with self.assertRaises(SystemExit):
            P72.vincular_edital(["vincular-edital", "Conc", "dpepb2026_analista"])
        self.assertIsNone(LP.ler(self.arq).get("edital_slug"))

    def test_confirmar_recusa_perfil_com_slug_que_nao_bate(self):
        self.edita(lambda c: c.update(edital_slug="dpepb2026_analista"))
        with self.assertRaises(SystemExit):
            self.confirma()


if __name__ == "__main__":
    unittest.main(verbosity=1)
