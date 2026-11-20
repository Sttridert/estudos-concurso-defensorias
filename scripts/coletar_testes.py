#!/usr/bin/env python3
"""Testes do grupo A (Coletar): arquivo de dados da FCC, leitura de gabaritos e do TEC, situação do gabarito.
Rodar: python -I scripts/coletar_testes.py
Só leem o banco real (somente leitura) e arquivos já existentes; não gravam nada fora de pastas temporárias."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletar_gabaritos as G  # noqa: E402
import lib_conferencia as C  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


class TestArquivoFcc(unittest.TestCase):
    def test_estrutura_do_arquivo_de_dados(self):
        d = json.loads((RAIZ / "dados" / "fcc_concursos.json").read_text(encoding="utf-8"))
        cods = d["concursos"]
        self.assertTrue(cods)
        self.assertEqual(len(cods), len(set(cods)), "código de concurso repetido")
        for c in cods:
            self.assertRegex(c, r"^[a-z]{3,6}\d{3}$")
        for arq, v in d["relatorios_alteracao"].items():
            self.assertIn("prova", v)
            self.assertIn(int(v["tipo_caderno"]), range(1, 10))

    def test_carregar_devolve_o_que_o_script_usa(self):
        cods, rels = G.carregar_fcc()
        self.assertEqual(cods, G.CODIGOS_FCC)
        self.assertEqual(rels, G.RELATORIOS_FCC)
        for arq, (prova, tipo) in rels.items():
            self.assertIsInstance(prova, str)
            self.assertIsInstance(tipo, int)

    def test_provas_dos_relatorios_existem_no_banco(self):
        con = sqlite3.connect(f"file:{G.BANCO}?mode=ro", uri=True)
        try:
            for arq, (prova, _) in G.RELATORIOS_FCC.items():
                self.assertTrue(con.execute("select 1 from provas where nome=?", (prova,)).fetchone(), f"{arq}: prova não está no banco: {prova}")
        finally:
            con.close()

    def test_arquivo_de_dados_alternativo_e_arquivo_ausente(self):
        with tempfile.TemporaryDirectory() as t:
            arq = Path(t) / "x.json"
            arq.write_text(json.dumps({"concursos": ["abc123"], "relatorios_alteracao": {"r": {"prova": "P", "tipo_caderno": 2}}}), encoding="utf-8")
            self.assertEqual(G.carregar_fcc(arq), (["abc123"], {"r": ("P", 2)}))
            with self.assertRaises(SystemExit):
                G.carregar_fcc(Path(t) / "nao_existe.json")

    def test_ajustes_fcc_reproduz_o_arquivo_gravado(self):
        """Regressão da mudança para arquivo de dados: regerar os ajustes dá exatamente o `banco/ajustes_gabarito.json` existente."""
        with tempfile.TemporaryDirectory() as t:
            saida = Path(t) / "ajustes.json"
            G.ajustes_fcc(str(saida))
            novo = json.loads(saida.read_text(encoding="utf-8"))
        atual = json.loads((RAIZ / "banco" / "ajustes_gabarito.json").read_text(encoding="utf-8"))
        self.assertEqual(novo, atual)


class TestLeituraDeGabaritos(unittest.TestCase):
    def test_parse_ajustes_atribuicao_e_alteracao(self):
        txt = """Atribuição
Questão 5 tipo 1
Questão 7 tipo 2
-----
Questão 9 tipo 1
Questão 3 tipo 2
-----
Alterações
Questão 11 tipo 1 B
Questão 2 tipo 2 C
-----
"""
        g = G._parse_ajustes(txt)
        self.assertEqual(g[0], ("atribuicao", [(5, 1, None), (7, 2, None)]))
        self.assertEqual(g[1], ("atribuicao", [(9, 1, None), (3, 2, None)]))
        self.assertEqual(g[2], ("alteracao", [(11, 1, "B"), (2, 2, "C")]))

    def test_parse_ajustes_tipo_reiniciado_abre_novo_grupo_sem_separador(self):
        g = G._parse_ajustes("Alterações\nQuestão 1 tipo 1 A\nQuestão 4 tipo 2 B\nQuestão 8 tipo 1 C\nQuestão 6 tipo 2 D\n")
        self.assertEqual([x[1] for x in g], [[(1, 1, "A"), (4, 2, "B")], [(8, 1, "C"), (6, 2, "D")]])

    def test_parse_tec(self):
        # formato real do TEC (conferido em banco/fonte_tec/recebidos): "Questão N de T", Matéria, Assunto, linha "#id banca - ano - cargo", enunciado e alternativas
        txt = ("Questão 12 de 100\nMatéria: Direito Penal\nAssunto:\nCrimes contra a pessoa\n   \n28\n    \n #123456 FCC - 2023 - Defensor Público\n  \n\n"
               "Enunciado da questão aqui\n\n\nA\n\tprimeira alternativa\n\n\nB\n\tsegunda alternativa\n")
        n, r = G._parse_tec(txt)
        self.assertEqual((n, r["tec_id"], r["materia"], r["assunto"]), (12, "123456", "Direito Penal", "Crimes contra a pessoa"))
        self.assertEqual(r["enunciado"], "Enunciado da questão aqui")
        self.assertEqual(r["alternativas"], {"A": "primeira alternativa", "B": "segunda alternativa"})


class TestSituacaoDoGabarito(unittest.TestCase):
    def test_situacao_do_status(self):
        for texto, esperado in (("preliminar (FCC)", "preliminar"), ("Preliminar", "preliminar"), ("a confirmar", "a_confirmar"), ("a_confirmar", "a_confirmar"),
                                ("definitivo", "definitivo"), ("oficial FCC", "definitivo"), ("conferido no site", "definitivo"), ("qualquer coisa", None), ("", None)):
            self.assertEqual(C.situacao_do_status(texto), esperado, texto)

    def test_situacao_das_provas_do_banco_bate_com_o_texto(self):
        con = sqlite3.connect(f"file:{G.BANCO}?mode=ro", uri=True)
        try:
            ruins = [(n, st, sit) for n, st, sit in con.execute("select nome,gabarito_status,gabarito_situacao from provas")
                     if C.situacao_do_status(st) not in (None, sit)]
        finally:
            con.close()
        self.assertEqual(ruins, [], "gabarito_situacao diverge do texto de gabarito_status")


if __name__ == "__main__":
    unittest.main(verbosity=1)
