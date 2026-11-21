#!/usr/bin/env python3
"""Testes do grupo F (Produzir): comparação com a base de regressão (`produzir_regressao.py`), motor de análise (`23`),
escopo por bloco do edital (`lib_escopo`) e leitura do edital classificado (`lib_edital_classificado`), com bancos de brinquedo em memória.
Uso: python -I scripts/produzir_testes.py
"""
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import produzir_regressao as R  # noqa: E402
import lib_escopo as LE  # noqa: E402
import lib_edital_classificado as LA  # noqa: E402

_spec = importlib.util.spec_from_file_location("motor23", AQUI / "23_motor_analise.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

ESQUEMA = """
create table disciplinas(id integer primary key, nome text);
create table assuntos(id integer primary key, codigo text, nome text, disciplina_id integer);
create table pontos(id integer primary key, codigo text, texto text, assunto_id integer, disciplina_id integer, ativo integer default 1);
create table ponto_fontes(ponto_id integer, presente integer);
create table provas(id integer primary key, nome text, ano integer, banca text, carreira text, cargo text, instituicao text);
create table questoes(id integer primary key, prova_id integer, numero integer, situacao text, disciplina_id integer);
create table classificacao(questao_id integer, ponto_id integer, ponto2_id integer, assunto_provisorio_id integer, tipo_cobranca text);
create table edital_blocos(edital_id integer, sigla text, titulo_no_edital text, disciplina_id integer, ordem integer);
create table edital_frases(id integer primary key, edital_id integer, disciplina_edital text, disciplina_id integer, item_ordem integer, item_rotulo text, texto text);
create table edital_frase_destinos(id integer primary key, frase_id integer, ponto_id integer, papel text, trecho text);
create table edital_pontos_fora(edital_id integer, ponto_id integer, motivo text);
"""


def banco_brinquedo():
    """Duas disciplinas (1 Penal, 2 Processo); pontos 10 e 11 (Penal) e 20 e 21 (Processo); edital 7 com blocos PEN (disc 1) e PRO (disc 2).
    Frases: a 1 (bloco PEN) toca o ponto 10 (principal) e o 20 (secundário); a 2 (PRO) toca o 20; a 3 (PRO, sem número) toca o 21."""
    con = sqlite3.connect(":memory:")
    con.executescript(ESQUEMA)
    con.executemany("insert into disciplinas values(?,?)", [(1, "Direito Penal"), (2, "Direito Processual Penal")])
    con.executemany("insert into assuntos values(?,?,?,?)", [(1, "PE01", "Teoria do delito", 1), (2, "PR01", "Prisões", 2)])
    con.executemany("insert into pontos values(?,?,?,?,?,1)", [(10, "PE01.01", "Dolo e culpa", 1, 1), (11, "PE01.02", "Tentativa", 1, 1),
                                                           (20, "PR01.01", "Prisão preventiva", 2, 2), (21, "PR01.02", "Liberdade provisória", 2, 2)])
    con.executemany("insert into edital_blocos values(7,?,?,?,?)", [("PEN", "DIREITO PENAL", 1, 1), ("PRO", "DIREITO PROCESSUAL PENAL", 2, 2)])
    con.executemany("insert into edital_frases values(?,7,?,?,?,?,?)", [
        (1, "PEN", 1, 1, "1", "Dolo e culpa. Tentativa."), (2, "PRO", 2, 1, "1", "Prisão preventiva."), (3, "PRO", 2, 2, None, "Liberdade provisória.")])
    con.executemany("insert into edital_frase_destinos(frase_id,ponto_id,papel,trecho) values(?,?,?,?)", [
        (1, 10, "principal", "Dolo e culpa"), (1, 20, "secundario", "Tentativa"), (2, 20, "principal", None), (3, 21, "principal", None)])
    return con


# ------------------------------------------------------------------ comparação com a base de regressão
class Diferencas(unittest.TestCase):
    def test_iguais_nao_dao_diferenca(self):
        self.assertEqual(R.diferencas({"a": [1, 2, {"b": 3}], "c": "x"}, {"c": "x", "a": [1, 2, {"b": 3}]}), [])

    def test_valor_mudado_aparece_com_caminho(self):
        d = R.diferencas({"n": {"total": 10}}, {"n": {"total": 11}})
        self.assertEqual(len(d), 1)
        self.assertIn("/n/total", d[0])

    def test_chave_que_some_ou_aparece(self):
        d = R.diferencas({"a": 1}, {"b": 1})
        self.assertEqual(sorted(x.split(":")[0] for x in d), ["/a", "/b"])

    def test_lista_de_tamanho_diferente(self):
        self.assertEqual(len(R.diferencas({"l": [1, 2]}, {"l": [1, 2, 3]})), 1)

    def test_tipo_diferente_nao_passa_por_igual(self):
        self.assertEqual(len(R.diferencas({"a": 1}, {"a": "1"})), 1)

    def test_ordem_da_lista_importa(self):
        self.assertEqual(len(R.diferencas([1, 2], [2, 1])), 2)


class CompararPasta(unittest.TestCase):
    def _pasta(self, tmp, nome, arquivos):
        p = Path(tmp) / nome
        p.mkdir()
        for k, v in arquivos.items():
            (p / k).write_text(json.dumps(v), encoding="utf-8")
        return p

    def test_identicos_mudaram_faltando_sobrando(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._pasta(tmp, "b", {"x_perfil1.json": {"n": 1}, "y_perfil2.json": {"n": 1}, "z_perfil3.json": {"n": 1}})
            nova = self._pasta(tmp, "n", {"x_perfil1.json": {"n": 1}, "y_perfil2.json": {"n": 2}, "w_perfil4.json": {"n": 1}})
            ident, mud, falt, sobr = R.comparar_pasta(base, nova)
            self.assertEqual(ident, ["x_perfil1.json"])
            self.assertEqual(list(mud), ["y_perfil2.json"])
            self.assertEqual(falt, ["z_perfil3.json"])
            self.assertEqual(sobr, ["w_perfil4.json"])

    def test_filtro_por_perfil(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._pasta(tmp, "b", {"x_perfil1.json": {"n": 1}, "y_perfil10.json": {"n": 1}})
            nova = self._pasta(tmp, "n", {"x_perfil1.json": {"n": 1}, "y_perfil10.json": {"n": 2}})
            ident, mud, _, _ = R.comparar_pasta(base, nova, [1])       # perfil 1 não pode casar com perfil10
            self.assertEqual(ident, ["x_perfil1.json"])
            self.assertEqual(mud, {})


class BaseReal(unittest.TestCase):
    def test_ha_base_e_perfis(self):
        self.assertIsNotNone(R.base_padrao(), "nenhuma banco/base-regressao-* encontrada")
        self.assertTrue(R.ids_dos_perfis(R.RAIZ), "nenhum perfil.toml com apostila")


# ------------------------------------------------------------------ motor de análise (23)
class Wilson(unittest.TestCase):
    def test_sem_amostra_e_tudo(self):
        self.assertEqual(M.wilson(0.5, 0), (0.0, 1.0))

    def test_faixa_contem_o_p_e_estreita_com_n(self):
        lo1, hi1 = M.wilson(0.3, 20)
        lo2, hi2 = M.wilson(0.3, 200)
        self.assertTrue(lo1 < 0.3 < hi1 and lo2 < 0.3 < hi2)
        self.assertTrue(hi2 - lo2 < hi1 - lo1)

    def test_extremos_nao_saem_de_0_e_1(self):
        self.assertEqual(M.wilson(0, 10)[0], 0.0)
        self.assertEqual(M.wilson(1, 10)[1], 1.0)

    def test_valor_conhecido(self):
        lo, hi = M.wilson(0.5, 100)           # 0,5 com n = 100: cerca de 0,404 a 0,596
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)


class EmUniverso(unittest.TestCase):
    Q = {"banca": "FCC", "carreira": "Defensoria Pública", "cargo": "Analista Jurídico", "inst": "DPE-AM", "ano": 2022}

    def test_sem_filtro_tudo_entra(self):
        self.assertTrue(M.em_universo(self.Q, {}))

    def test_ou_dentro_da_lista_e_sem_diferenciar_caixa(self):
        self.assertTrue(M.em_universo(self.Q, {"bancas": ["cespe", "fcc"]}))
        self.assertFalse(M.em_universo(self.Q, {"bancas": ["cespe"]}))

    def test_e_entre_filtros(self):
        self.assertFalse(M.em_universo(self.Q, {"bancas": ["FCC"], "instituicoes": ["DPE-SP"]}))

    def test_prefixo_de_cargo(self):
        self.assertTrue(M.em_universo(self.Q, {"cargos_prefixo": ["Analista"]}))
        self.assertFalse(M.em_universo(self.Q, {"cargos_prefixo": ["Defensor"]}))

    def test_anos(self):
        self.assertFalse(M.em_universo(self.Q, {"ano_min": 2023}))
        self.assertFalse(M.em_universo(self.Q, {"ano_max": 2021}))
        self.assertTrue(M.em_universo(self.Q, {"ano_min": 2022, "ano_max": 2022}))


class GrupoDaProva(unittest.TestCase):
    PERFIL = {"carreira": "Defensoria", "banca": "FCC", "cargo": "Analista", "orgao": "DPE-AM", "orgao_ativo": False}

    def prova(self, **k):
        return {**{"carreira": "Defensoria", "banca": "FCC", "cargo": "Analista", "inst": "DPE-AM"}, **k}

    def test_estudo_geral(self):
        self.assertEqual(M.grupo_da_prova(self.PERFIL, self.prova(inst="DPE-SP")), "A")
        self.assertEqual(M.grupo_da_prova(self.PERFIL, self.prova(cargo="Defensor")), "B")
        self.assertEqual(M.grupo_da_prova(self.PERFIL, self.prova(banca="Cespe")), "C")

    def test_com_orgao(self):
        perfil = {**self.PERFIL, "orgao_ativo": True}
        self.assertEqual(M.grupo_da_prova(perfil, self.prova()), "A")
        self.assertEqual(M.grupo_da_prova(perfil, self.prova(inst="DPE-SP")), "B")
        self.assertEqual(M.grupo_da_prova(perfil, self.prova(carreira="Outra")), "C")


class FreqEGrupos(unittest.TestCase):
    def qs(self):
        return [{"w": 1.0, "itens": [("p1", "a1", 1.0)]}, {"w": 1.0, "itens": [("p1", "a1", 0.5), ("p2", "a2", 0.5)]}, {"w": 2.0, "itens": [("p3", "a2", 1.0)]}]

    def test_questao_com_dois_pontos_reparte_o_peso(self):
        f, tot, _ = M.freq(self.qs(), ["a1", "a2"], "a")
        self.assertAlmostEqual(tot, 4.0)
        self.assertAlmostEqual(f["a1"]["peso"], 1.5)
        self.assertAlmostEqual(f["a2"]["peso"], 2.5)
        self.assertAlmostEqual(f["a1"]["p"] + f["a2"]["p"], 1.0)

    def test_n_bruto_conta_a_fracao_e_nao_o_peso(self):
        f, _, _ = M.freq(self.qs(), ["p1", "p2", "p3"], "p")
        self.assertAlmostEqual(f["p1"]["n"], 1.5)
        self.assertAlmostEqual(f["p2"]["n"], 0.5)

    def test_n_efetivo_e_soma_ao_quadrado_sobre_soma_dos_quadrados(self):
        _, tot, neff = M.freq(self.qs(), ["a1", "a2"], "a")
        self.assertAlmostEqual(neff, tot * tot / (1 + 1 + 4))

    def test_item_sem_ponto_e_ignorado(self):
        f, tot, _ = M.freq([{"w": 1.0, "itens": [(None, None, 1.0)]}], ["a1"], "a")
        self.assertEqual(tot, 0)
        self.assertEqual(f["a1"]["p"], 0)

    def test_grupos_pelos_limites_da_faixa(self):
        f = {"x": {"lo": 0.30, "hi": 0.5}, "y": {"lo": 0.0, "hi": 0.2}, "z": {"lo": 0.1, "hi": 0.4}}
        self.assertEqual(M.grupos(f, 4), {"x": "Cai muito", "y": "Cai pouco", "z": "Cai às vezes"})   # uniforme = 0,25


class CarregarQuestoes(unittest.TestCase):
    def setUp(self):
        con = self.con = banco_brinquedo()
        con.executemany("insert into provas values(?,?,?,?,?,?,?)", [(1, "P2022", 2022, "FCC", "Defensoria", "Analista", "DPE-AM"), (2, "P2018", 2018, "FCC", "Defensoria", "Defensor", "DPE-SP")])
        con.executemany("insert into questoes values(?,?,?,?,?)", [(1, 1, 1, "valida", 1), (2, 1, 2, "valida", 1), (3, 2, 1, "valida", 2), (4, 2, 2, "valida", 2)])
        con.executemany("insert into classificacao values(?,?,?,?,?)", [(1, 10, 11, None, "lei_seca"), (2, 10, None, None, None), (3, 20, None, None, None), (4, 21, None, None, None)])
        self.perfil = {"disciplina_id": 1, "carreira": "Defensoria", "banca": "FCC", "cargo": "Analista", "orgao_ativo": False,
                       "ano_referencia": 2026, "meia_vida": 4, "pesos": {"A": 1.0, "B": 0.5, "C": 0.25}, "bloco_edital": "PEN", "edital_id": 7}

    def por_id(self, qs):
        return {q["id"]: q for q in qs}

    def test_peso_e_divisao_do_segundo_ponto(self):
        qs, _, _ = M.carregar_questoes(self.con, self.perfil, False)
        q = self.por_id(qs)
        self.assertEqual(q[1]["grupo"], "A")
        self.assertAlmostEqual(q[1]["w"], 1.0 * 0.5 ** (4 / 4))                 # 4 anos, meia-vida 4
        self.assertEqual([(p, f) for p, _, f in q[1]["itens"]], [(10, 0.5), (11, 0.5)])
        self.assertEqual([(p, f) for p, _, f in q[2]["itens"]], [(10, 1.0)])

    def test_questao_de_outra_disciplina_entra_pelo_ponto_tocado(self):
        qs, _, _ = M.carregar_questoes(self.con, self.perfil, False)
        q = self.por_id(qs)
        self.assertIn(3, q)                                      # Processo, mas no ponto 20, que o bloco PEN toca
        self.assertEqual(q[3]["grupo"], "B")                     # prova de Defensor: mesma carreira e banca, outro cargo
        self.assertAlmostEqual(q[3]["w"], 0.5 * 0.5 ** (8 / 4))
        self.assertNotIn(4, q)                                   # ponto 21 não é tocado pelo bloco PEN

    def test_legado_ignora_segundo_ponto(self):
        self.con.execute("update classificacao set assunto_provisorio_id=1 where questao_id=1")
        qs, _, _ = M.carregar_questoes(self.con, self.perfil, True)
        self.assertEqual(self.por_id(qs)[1]["itens"], [(None, 1, 1.0)])


# ------------------------------------------------------------------ escopo por bloco do edital (lib_escopo)
class Escopo(unittest.TestCase):
    def setUp(self):
        self.con = banco_brinquedo()

    def test_perfil_sem_bloco_e_por_disciplina(self):
        self.assertIsNone(LE.escopo(self.con, {"disciplina_id": 1}))
        self.assertEqual(LE.clausula(None, 1), ("q.disciplina_id=?", [1]))

    def test_bloco_toca_os_pontos_das_frases(self):
        e = LE.escopo(self.con, {"bloco_edital": "PEN", "edital_id": 7})
        self.assertEqual(e["toca"], {10, 20})                # principal e secundário da frase do bloco
        self.assertEqual(LE.escopo(self.con, {"bloco_edital": "PRO", "edital_id": 7})["toca"], {20, 21})

    def test_bloco_inexistente_para(self):
        with self.assertRaises(SystemExit):
            LE.escopo(self.con, {"bloco_edital": "XXX", "edital_id": 7})
        with self.assertRaises(SystemExit):
            LE.escopo(self.con, {"bloco_edital": "PEN", "edital_id": 99})

    def test_clausula_com_bloco_aceita_disciplina_ou_ponto_tocado(self):
        e = LE.escopo(self.con, {"bloco_edital": "PEN", "edital_id": 7})
        sql, par = LE.clausula(e, 1)
        self.assertIn("q.disciplina_id=?", sql)
        self.assertEqual(par, [1, 10, 20, 10, 20])
        self.assertEqual(LE.clausula({"toca": set()}, 1)[1], [1, -1, -1])     # bloco sem pontos: nunca vira "in ()"

    def test_efetivos_questao_da_disciplina_perde_ponto_fora_do_escopo(self):
        e = {"toca": {10}}
        self.assertEqual(LE.efetivos(e, 1, 1, 10, 99, {10, 11}), (10, None))
        self.assertEqual(LE.efetivos(e, 1, 1, 99, 11, {10, 11}), (None, 11))

    def test_efetivos_questao_de_outra_disciplina_so_com_ponto_tocado(self):
        e = {"toca": {20}}
        self.assertEqual(LE.efetivos(e, 1, 2, 21, 20, set()), (20, None))      # o tocado vira principal
        self.assertEqual(LE.efetivos(e, 1, 2, 21, 22, set()), (None, None))    # nenhum tocado: a questão não entra

    def test_efetivos_sem_escopo_filtra_pelos_validos(self):
        self.assertEqual(LE.efetivos(None, 1, 1, 10, 20, {10, 11}), (10, None))
        self.assertEqual(LE.efetivos(None, 1, 1, 99, 11, {10, 11}), (None, 11))

    def test_pontos_e_assuntos_do_escopo(self):
        e = LE.escopo(self.con, {"bloco_edital": "PEN", "edital_id": 7})
        pts = LE.pontos_do_escopo(self.con, {"disciplina_id": 1}, e)
        self.assertEqual(set(pts), {10, 11, 20})            # disciplina do perfil + ponto tocado de outra disciplina
        self.assertEqual(set(LE.pontos_do_escopo(self.con, {"disciplina_id": 1}, None)), {10, 11})
        self.assertEqual(set(LE.assuntos_do_escopo(self.con, pts)), {1, 2})

    def test_blocos_por_ponto_e_bloco_do_perfil(self):
        self.assertEqual(LE.blocos_por_ponto(self.con, 7), {10: {"PEN"}, 20: {"PEN", "PRO"}, 21: {"PRO"}})
        self.assertEqual(LE.bloco_do_perfil(self.con, {"edital_id": 7, "disciplina_id": 2}), "PRO")       # único bloco da disciplina
        self.assertEqual(LE.bloco_do_perfil(self.con, {"edital_id": 7, "disciplina_id": 2, "bloco_edital": "PEN"}), "PEN")
        self.assertIsNone(LE.bloco_do_perfil(self.con, {"edital_id": 8, "disciplina_id": 2}))

    def test_titulo_do_bloco_ganha_acento_e_caixa(self):
        self.con.execute("insert into assuntos values(3,'X','Execução e Legislação',1)")
        self.assertEqual(LE.titulo_legivel(self.con, "EXECUCAO E LEGISLACAO"), "Execução e Legislação")
        self.assertEqual(LE.titulo_legivel(self.con, "Direito Civil"), "Direito Civil")

    def test_gabarito_preliminar(self):
        for s in ("preliminar", "Preliminar", "a_confirmar", "A confirmar"):
            self.assertTrue(LE.gabarito_preliminar(s), s)
        for s in ("definitivo", "", None):
            self.assertFalse(LE.gabarito_preliminar(s), s)


# ------------------------------------------------------------------ edital classificado (lib_edital_classificado)
class EditalClassificado(unittest.TestCase):
    def setUp(self):
        self.con = banco_brinquedo()
        self.pts = {"PE01.01": {"id": 10}, "PE01.02": {"id": 11}, "PR01.01": {"id": 20}, "PR01.02": {"id": 21}}

    def test_sem_frases_para(self):
        with self.assertRaises(SystemExit):
            LA.carregar(self.con, 99, 1, self.pts, bloco="PEN")

    def test_programa_so_do_bloco_e_edpts_so_do_que_o_bloco_cobre(self):
        a = LA.carregar(self.con, 7, 1, self.pts, bloco="PEN")
        self.assertEqual(a["programa"], [{"item": "1", "topicos": ["Dolo e culpa. Tentativa."], "cods": [[("PE01.01", "principal"), ("PR01.01", "secundario")]]}])
        self.assertEqual(set(a["edpts"]), {"PE01.01", "PR01.01"})      # PR01.01 vem como secundário de uma frase do bloco PEN

    def test_ponto_com_trecho_do_proprio_bloco_antes_do_de_outro_bloco(self):
        a = LA.carregar(self.con, 7, 2, self.pts, bloco="PRO")
        self.assertEqual(set(a["edpts"]), {"PR01.01", "PR01.02"})
        trechos = json.loads(a["edpts"]["PR01.01"]["trechos"])
        self.assertEqual([t["i"] for t in trechos], ["1", "PEN.1"])       # o do próprio bloco primeiro, o de outro bloco depois (rótulo SIGLA.item)

    def test_frase_sem_numero_usa_s_n(self):
        a = LA.carregar(self.con, 7, 2, self.pts, bloco="PRO")
        self.assertIn("s/n", [it["item"] for it in a["programa"]])

    def test_tema_so_de_outro_bloco_vai_para_fora(self):
        a = LA.carregar(self.con, 7, 1, self.pts, bloco="PEN")
        self.assertNotIn("PE01.02", a["edpts"])
        self.con.execute("insert into edital_frase_destinos(frase_id,ponto_id,papel,trecho) values(2, 11, 'principal', null)")   # a frase do bloco PRO passa a tocar o ponto 11 (Penal)
        a = LA.carregar(self.con, 7, 1, self.pts, bloco="PEN")
        self.assertNotIn("PE01.02", a["edpts"])
        self.assertIn("PE01.02", a["fora"])
        self.assertIn("PRO.1", a["fora"]["PE01.02"])

    def test_motivo_gravado_de_ponto_fora_aparece(self):
        self.con.execute("insert into edital_pontos_fora values(7, 11, 'Lista fechada')")
        self.assertEqual(LA.carregar(self.con, 7, 1, self.pts, bloco="PEN")["fora"]["PE01.02"], "Lista fechada")


# ------------------------------------------------------------------ novidades do edital (lib_novidades_edital)
import lib_novidades_edital as NV  # noqa: E402


class NovidadesDoEdital(unittest.TestCase):
    def test_normalizar_ignora_acento_caixa_e_pontuacao(self):
        self.assertEqual(NV.normalizar("  Código  de Processo CIVIL (Lei n. 13.105)! "), NV.normalizar("codigo de processo civil lei n 13 105"))

    def test_frase_igual_nao_e_novidade(self):
        self.assertEqual(NV.comparar([("1", "Teorias da pena.")], [["teorias da PENA"]]), [])

    def test_frase_sem_parecida_e_nova(self):
        r = NV.comparar([("9", "Crimes em espécie.")], [["Teorias da pena.", "Extinção da punibilidade."]])
        self.assertEqual([(x["rotulo"], x["situacao"]) for x in r], [("9", NV.NOVA)])

    def test_frase_atualizada_e_reescrita(self):
        r = NV.comparar([("5", "Procedimentos do processo administrativo sancionatório previsto na Lei Federal 14.133/2021.")],
                        [["Procedimentos do processo administrativo sancionatório previsto na Lei Federal n. 8.666/93."]])
        self.assertEqual(r[0]["situacao"], NV.REESCRITA)

    def test_basta_existir_em_um_dos_editais_anteriores(self):
        r = NV.comparar([("1", "Sinase.")], [["Outra coisa."], ["sinase"]])
        self.assertEqual(r, [])

    def test_sem_edital_anterior_tudo_e_novo(self):
        self.assertEqual(len(NV.comparar([("1", "A."), ("2", "B.")], [])), 2)

    def test_frase_vazia_ou_so_pontuacao_e_ignorada(self):
        self.assertEqual(NV.comparar([("1", " . ")], [["x"]]), [])

    def test_rotulo_e_ordem_preservados(self):
        r = NV.comparar([("3", "alfa beta"), ("1", "gama delta epsilon")], [[]])
        self.assertEqual([x["rotulo"] for x in r], ["3", "1"])

    def test_programa_real_de_2026_nao_tem_novidade_contra_si_mesmo(self):
        p = NV.carregar_programa("dpeam2026_analista_juridico")
        atuais = p["blocos"]["PENAL"]
        self.assertTrue(atuais)
        self.assertEqual(NV.comparar(atuais, [[t for _, t in atuais]]), [])

    def test_programas_reais_penal_2026_traz_crimes_em_especie_a_mais_que_2023(self):
        a = NV.carregar_programa("dpeam2026_analista_juridico")["blocos"]["PENAL"]
        b = NV.carregar_programa("dpeam2023_analista_juridico")["blocos"]["PENAL"]
        textos = [x["texto"] for x in NV.comparar(a, [[t for _, t in b]])]
        self.assertIn("Crimes em espécie.", textos)


if __name__ == "__main__":
    unittest.main(verbosity=1)
