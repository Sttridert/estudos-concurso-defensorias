#!/usr/bin/env python3
"""Testes do grupo F (Produzir): semáforo do porteiro e impressão digital das apostilas (`lib_semaforo`), com banco de brinquedo em memória.
Os bancos de brinquedo vêm de `produzir_testes.py`. Uso: python -I scripts/produzir_testes_semaforo.py
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import lib_semaforo as S  # noqa: E402
from produzir_testes import banco_brinquedo  # noqa: E402


def banco_semaforo():
    """banco de brinquedo com 5 provas e 5 questões de Penal (ponto 10), todas comentadas; edital 7 real com artefato"""
    con = banco_brinquedo()
    con.execute("alter table provas add column gabarito_status text")
    con.execute("alter table classificacao add column revisada integer")
    con.execute("alter table classificacao add column detalhe text")
    for col in ("enunciado", "alt_a", "alt_b", "alt_c", "alt_d", "alt_e", "gabarito"):
        con.execute(f"alter table questoes add column {col} text")
    con.executescript("create table editais(id integer primary key, tipo text);"
                      "create table comentarios(questao_id integer, texto text, pegadinha text, dispositivos text, estado text, pendente_confirmacao integer);")
    con.execute("insert into editais values(7,'real')")
    for i in range(1, 6):
        con.execute("insert into provas values(?,?,?,?,?,?,?,'definitivo')", (i, f"P{i}", 2020 + i, "FCC", "Defensoria", "Analista", "DPE-AM"))
        con.execute("insert into questoes(id,prova_id,numero,situacao,disciplina_id) values(?,?,1,'valida',1)", (i, i))
        con.execute("insert into classificacao(questao_id,ponto_id,tipo_cobranca,revisada) values(?,10,'lei_seca',0)", (i,))
        con.execute("insert into comentarios values(?,'texto','peg','[]','rascunho',0)", (i,))
    return con


PERFIL_SEM = {"id": 5, "disciplina_id": 1, "carreira": "Defensoria", "banca": "FCC", "cargo": "Analista", "orgao_ativo": False, "ano_referencia": 2026,
              "meia_vida": 8, "pesos": {"A": 1.0, "B": 0.5, "C": 0.25}, "bloco_edital": "PEN", "edital_id": 7, "universo": {"filtro": {}},
              "confirmado_pelo_usuario": 1}


class Semaforo(unittest.TestCase):
    def setUp(self):
        self.con = banco_semaforo()
        for alvo, ret in (("procurar", (None, {}, {})), ("estado", ("confirmada", "")), ("edital_problemas", [])):
            m = mock.patch.object(S.LP, alvo, return_value=ret)
            m.start()
            self.addCleanup(m.stop)

    def codigos(self, nivel, perfil=None):
        return {a.codigo for a in S.verificar(self.con, perfil or PERFIL_SEM) if a.nivel == nivel}

    def test_tudo_certo_nao_bloqueia_nem_avisa(self):
        self.assertEqual(self.codigos(S.BLOQUEIA), set())
        self.assertEqual(self.codigos(S.AVISA), set())
        self.assertIn("amostra", self.codigos(S.INFORMA))

    def test_perfil_nao_confirmado_bloqueia(self):
        self.assertIn("perfil_nao_confirmado", self.codigos(S.BLOQUEIA, {**PERFIL_SEM, "confirmado_pelo_usuario": 0}))

    def test_confirmacao_anterior_a_base_avisa(self):
        with mock.patch.object(S.LP, "estado", return_value=("sem_base", "")):
            self.assertIn("confirmacao_antiga", self.codigos(S.AVISA))

    def test_edital_real_sem_artefato_bloqueia(self):
        self.con.execute("insert into editais values(9,'real')")
        self.assertIn("edital_sem_artefato", self.codigos(S.BLOQUEIA, {**PERFIL_SEM, "edital_id": 9, "bloco_edital": None}))

    def test_sem_questoes_bloqueia_e_para(self):
        self.con.execute("delete from classificacao")
        self.assertEqual(self.codigos(S.BLOQUEIA), {"sem_questoes"})

    def test_questao_sem_comentario_bloqueia(self):
        self.con.execute("delete from comentarios where questao_id=3")
        achados = [a for a in S.verificar(self.con, PERFIL_SEM) if a.codigo == "sem_comentario"]
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].nivel, S.BLOQUEIA)
        self.assertIn("1 questões", achados[0].texto)

    def test_comentario_confirmar_avisa_e_vai_para_a_capa(self):
        self.con.execute("update comentarios set pendente_confirmacao=1 where questao_id in (1,2)")
        a = [x for x in S.verificar(self.con, PERFIL_SEM) if x.codigo == "comentario_confirmar"][0]
        self.assertEqual(a.nivel, S.AVISA)
        self.assertIn("2 comentários", a.capa)

    def test_gabarito_preliminar_avisa(self):
        self.con.execute("update provas set gabarito_status='preliminar' where id in (1,2,3)")
        a = [x for x in S.verificar(self.con, PERFIL_SEM) if x.codigo == "gabarito_preliminar"][0]
        self.assertIn("3 questões", a.texto)

    def test_amostra_pequena_avisa(self):
        self.con.execute("update questoes set situacao='anulada' where id>2")          # sobram 2 provas válidas
        self.assertIn("amostra_pequena", self.codigos(S.AVISA))

    def test_universo_limita_as_questoes(self):
        com_filtro = {**PERFIL_SEM, "universo": {"filtro": {"ano_min": 2024}}}        # só as provas de 2024 e 2025 (ids 4 e 5)
        self.assertIn("amostra_pequena", self.codigos(S.AVISA, com_filtro))
        self.con.execute("delete from comentarios where questao_id=1")                # comentário que falta, mas de questão fora do universo
        self.assertNotIn("sem_comentario", self.codigos(S.BLOQUEIA, com_filtro))
        self.assertIn("sem_comentario", self.codigos(S.BLOQUEIA))

    def test_anulada_nao_conta_como_sem_comentario(self):
        self.con.execute("update questoes set situacao='anulada' where id=3")
        self.con.execute("delete from comentarios where questao_id=3")
        self.assertNotIn("sem_comentario", self.codigos(S.BLOQUEIA))

    def test_pior_nivel(self):
        self.assertEqual(S.pior([S.Achado(S.INFORMA, "a", "x"), S.Achado(S.AVISA, "b", "y")]), S.AVISA)
        self.assertEqual(S.pior([S.Achado(S.INFORMA, "a", "x"), S.Achado(S.BLOQUEIA, "b", "y")]), S.BLOQUEIA)
        self.assertIsNone(S.pior([]))


class ImpressaoDigital(unittest.TestCase):
    def setUp(self):
        self.con = banco_semaforo()
        for alvo, ret in (("procurar", (None, {}, {})), ("impressao", "hperfil"), ("impressao_base", {"catalogo": "hcat", "edital": "hed"})):
            m = mock.patch.object(S.LP, alvo, return_value=ret)
            m.start()
            self.addCleanup(m.stop)

    def mudou(self, antes):
        dep = S.insumos(self.con, PERFIL_SEM)
        return {k for k in antes if antes[k] != dep[k]}, dep

    def test_estavel_sem_mudanca(self):
        self.assertEqual(S.insumos(self.con, PERFIL_SEM), S.insumos(self.con, PERFIL_SEM))

    def test_cada_parte_reage_so_ao_que_e_dela(self):
        antes = S.insumos(self.con, PERFIL_SEM)
        self.con.execute("update comentarios set pegadinha='nova' where questao_id=2")
        m, antes = self.mudou(antes)
        self.assertEqual(m, {"comentarios"})
        self.con.execute("update classificacao set tipo_cobranca='jurisprudencia' where questao_id=1")
        m, antes = self.mudou(antes)
        self.assertEqual(m, {"classificacao"})
        self.con.execute("update questoes set gabarito='C' where id=1")
        m, antes = self.mudou(antes)
        self.assertEqual(m, {"questoes"})

    def test_questao_fora_do_universo_nao_muda_a_impressao(self):
        self.con.execute("insert into questoes(id,prova_id,numero,situacao,disciplina_id) values(99,1,9,'valida',2)")            # Processo, ponto sem relação com o bloco PEN
        self.con.execute("insert into classificacao(questao_id,ponto_id,revisada) values(99,21,0)")
        self.con.execute("insert into comentarios values(99,'x','y','[]','rascunho',0)")
        antes = S.insumos(self.con, PERFIL_SEM)
        self.con.execute("update comentarios set texto='mudou' where questao_id=99")
        self.assertEqual(S.insumos(self.con, PERFIL_SEM), antes)

    def test_desatualizado_lista_so_o_que_mudou(self):
        reg = {"perfil": "a", "catalogo": "b", "edital": "c", "questoes": "d", "classificacao": "e", "comentarios": "f", "codigo": "g", "gerada_em": "x"}
        self.assertEqual(S.desatualizado(reg, dict(reg)), [])
        atual = {**reg, "catalogo": "outro", "codigo": "outro"}
        self.assertEqual(S.desatualizado(reg, atual), [S.ROTULOS["catalogo"], S.ROTULOS["codigo"]])

    def test_registro_ida_e_volta_e_varios_perfis(self):
        with tempfile.TemporaryDirectory() as tmp:
            p5, p6 = {"id": 5, "pasta": tmp}, {"id": 6, "pasta": tmp}
            self.assertEqual(S.ler_registro(p5), {})
            S.registrar(p5, {"perfil": "a"}, "x.docx", ["pend"], None, quando="2026-01-01 10:00")
            S.registrar(p6, {"perfil": "b"}, "y.docx", [], "motivo", quando="2026-01-02 10:00")
            r = S.ler_registro(p5)
            self.assertEqual((r["perfil"], r["arquivo"], r["pendencias"], r["gerada_mesmo_assim"]), ("a", "x.docx", ["pend"], None))
            self.assertEqual(S.ler_registro(p6)["gerada_mesmo_assim"], "motivo")

    def test_registro_corrompido_vale_como_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "impressoes.json").write_text("{quebrado", encoding="utf-8")
            self.assertEqual(S.ler_registro({"id": 5, "pasta": tmp}), {})


if __name__ == "__main__":
    unittest.main(verbosity=1)
