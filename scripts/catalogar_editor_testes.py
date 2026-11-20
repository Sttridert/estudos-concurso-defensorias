#!/usr/bin/env python3
"""Testes do editor visual do catálogo (marco M1): modelo, operações, mapa, diagnóstico e API. Biblioteca padrão (`unittest`).

Uso: python -I scripts/catalogar_editor_testes.py
Os testes usam uma pasta temporária e um banco sintético; só o teste de integração lê o banco real (somente leitura) e uma CÓPIA do catálogo
de Execução Penal. Nada em `dados/` nem em `banco/` é alterado.
"""
import csv
import json
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rascunho as R  # noqa: E402
import catalogar_editor as E  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

V1 = {"disciplina": "Disciplina de Teste", "assuntos": [
    {"codigo": "TP01", "nome": "Fundamentos", "descricao": None}, {"codigo": "TP02", "nome": "Sujeitos", "descricao": None},
    {"codigo": "TP03", "nome": "Pequeno", "descricao": None}],
    "pontos": [
    {"codigo": "TP01.01", "assunto": "TP01", "texto": "Natureza", "descricao": None, "origem": "t", "ativo": 1},
    {"codigo": "TP01.02", "assunto": "TP01", "texto": "Princípios", "descricao": None, "origem": "t", "ativo": 1},
    {"codigo": "TP02.01", "assunto": "TP02", "texto": "Órgãos", "descricao": None, "origem": "t", "ativo": 1},
    {"codigo": "TP02.02", "assunto": "TP02", "texto": "Condenado", "descricao": None, "origem": "t", "ativo": 1},
    {"codigo": "TP03.01", "assunto": "TP03", "texto": "Único", "descricao": None, "origem": "t", "ativo": 1},
    {"codigo": "TP03.02", "assunto": "TP03", "texto": "Inativo", "descricao": None, "origem": "t", "ativo": 0}]}
# contagens sintéticas: ponto -> (questões, itens)
CONT = {"TP01.01": (5, 6), "TP01.02": (0, 0), "TP02.01": (2, 1), "TP02.02": (3, 9), "TP03.01": (1, 2)}


V1_ORDEM = {"disciplina": "Disciplina de Ordem", "assuntos": [{"codigo": f"OR0{k}", "nome": f"Assunto {k}", "descricao": None} for k in range(1, 6)],
            "pontos": [{"codigo": f"OR0{k}.01", "assunto": f"OR0{k}", "texto": f"Ponto {k}", "descricao": None, "origem": "t", "ativo": 1} for k in range(1, 6)]}
# vocabulário distinto por classe (só letras: o classificador ignora dígitos): permite resultado de classificação calculável à mão
PALAVRAS = ["aurora zenite meridiano", "bussola farol enseada", "cantiga dueto serenata", "eclipse fresta penumbra", "galaxia horizonte nebulosa"]


def criar_banco(caminho):
    """Banco sintético. Disciplina 1 ('Disciplina de Teste'): contagens CONT, sem itens com posição. Disciplina 2 ('Disciplina de Ordem'): 5 assuntos
    de 1 ponto, 2 editais com 25 itens na ordem dos assuntos (posições conhecidas) e 8 questões por ponto com vocabulário próprio."""
    con = sqlite3.connect(caminho)
    con.executescript("""
        create table disciplinas(id integer primary key, nome text);
        create table pontos(id integer primary key, codigo text, disciplina_id integer);
        create table provas(id integer primary key, nome text, ano integer);
        create table questoes(id integer primary key, prova_id integer, numero integer, enunciado text, alt_a text, alt_b text, alt_c text, alt_d text,
                              alt_e text, situacao text default 'valida');
        create table classificacao(questao_id integer, ponto_id integer);
        create table edital_item_pontos(item_id integer, ponto_id integer);
        create table edital_itens(id integer primary key, disciplina_id integer);
        create table edital_item_ocorrencias(id integer primary key, item_id integer, edital_id integer);
    """)
    con.execute("insert into disciplinas values (1,'Disciplina de Teste'), (2,'Disciplina de Ordem')")
    con.execute("insert into provas values (1,'Prova X',2025)")
    qid = iid = 0
    for pid, (cod, (q, i)) in enumerate(CONT.items(), 1):
        con.execute("insert into pontos values (?,?,1)", (pid, cod))
        for _ in range(q):
            qid += 1
            con.execute("insert into questoes(id,prova_id,numero,enunciado) values (?,?,?,?)", (qid, 1, qid, f"Enunciado da questão {qid} sobre {cod}"))
            con.execute("insert into classificacao values (?,?)", (qid, pid))
        for _ in range(i):
            iid += 1
            con.execute("insert into edital_item_pontos values (?,?)", (iid, pid))
    base_ponto = 100
    for k in range(1, 6):                                     # disciplina 2: ponto ORk.01
        con.execute("insert into pontos values (?,?,2)", (base_ponto + k, f"OR0{k}.01"))
        for j in range(5):                                    # 5 itens por assunto, na ordem dos assuntos
            item = 200 + (k - 1) * 5 + j
            con.execute("insert into edital_itens values (?,2)", (item,))
            con.execute("insert into edital_item_pontos values (?,?)", (item, base_ponto + k))
        for j in range(8):                                    # 8 questões com o vocabulário da classe k
            qid += 1
            con.execute("insert into questoes(id,prova_id,numero,enunciado) values (?,?,?,?)", (qid, 1, qid, PALAVRAS[k - 1] + " questao"))
            con.execute("insert into classificacao values (?,?)", (qid, base_ponto + k))
    con.execute("insert into edital_item_pontos values (200, 102)")      # o item 200 liga a dois pontos de assuntos diferentes (OR01 e OR02)
    oid = 0
    for edital in (1, 2):
        for item in range(200, 225):
            oid += 1
            con.execute("insert into edital_item_ocorrencias values (?,?,?)", (oid, item, edital))
    con.commit()
    con.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._pasta = R.PASTA
        R.PASTA = self.tmp
        (self.tmp / "teste.json").write_text(json.dumps(V1, ensure_ascii=False), encoding="utf-8")
        self.banco = self.tmp / "banco.db"
        criar_banco(self.banco)
        self.d = R.criar_de_v1("teste")

    def tearDown(self):
        R.PASTA = self._pasta
        shutil.rmtree(self.tmp, ignore_errors=True)

    def op(self, **kw):
        self.d = R.aplicar_op("teste", kw, self.banco)
        return self.d

    def cods(self):
        return R.codigos(self.d)

    def uids(self, assunto_uid):
        return [p["uid"] for p in R.achar_assunto(self.d, assunto_uid)[1]["pontos"]]


class TestCriacao(Base):
    def test_estrutura_e_uids(self):
        self.assertEqual([a["uid"] for a in self.d["assuntos"]], ["v1:TP01", "v1:TP02", "v1:TP03"])
        self.assertEqual(self.uids("v1:TP01"), ["v1:TP01.01", "v1:TP01.02"])
        self.assertEqual(self.d["prefixo"], "TP")

    def test_ponto_inativo_nao_entra(self):
        self.assertNotIn("v1:TP03.02", [p["uid"] for a in self.d["assuntos"] for p in a["pontos"]])

    def test_codigos_pela_posicao(self):
        c = self.cods()
        self.assertEqual((c["v1:TP01"], c["v1:TP01.02"], c["v1:TP02.01"], c["v1:TP03.01"]), ("TP01", "TP01.02", "TP02.01", "TP03.01"))

    def test_nao_sobrescreve_sem_pedir(self):
        with self.assertRaises(R.ErroOp):
            R.criar_de_v1("teste")
        R.criar_de_v1("teste", sobrescrever=True)

    def test_base_v1_guardada(self):
        self.assertEqual(self.d["base_v1"]["pontos"]["v1:TP02.01"]["texto"], "Órgãos")

    def test_catalogo_inexistente(self):
        with self.assertRaises(R.ErroOp):
            R.criar_de_v1("nao-existe")


class TestMovimentos(Base):
    def test_mover_ponto_entre_assuntos_renumera_e_mantem_identidade(self):
        self.op(op="mover_ponto", uid="v1:TP02.01", para_assunto="v1:TP01", indice=0)
        c = self.cods()
        self.assertEqual(self.uids("v1:TP01"), ["v1:TP02.01", "v1:TP01.01", "v1:TP01.02"])
        self.assertEqual(c["v1:TP02.01"], "TP01.01")
        self.assertEqual(c["v1:TP01.01"], "TP01.02")
        self.assertEqual(c["v1:TP02.02"], "TP02.01")
        p = R.achar_ponto(self.d, "v1:TP02.01")[2]
        self.assertEqual(p["antigo"], "TP02.01")            # o código antigo fica guardado

    def test_mover_no_mesmo_assunto(self):
        self.op(op="mover_ponto", uid="v1:TP01.01", para_assunto="v1:TP01", indice=1)
        self.assertEqual(self.uids("v1:TP01"), ["v1:TP01.02", "v1:TP01.01"])

    def test_indice_fora_da_faixa(self):
        self.op(op="mover_ponto", uid="v1:TP01.01", para_assunto="v1:TP03", indice=99)
        self.assertEqual(self.uids("v1:TP03"), ["v1:TP03.01", "v1:TP01.01"])

    def test_indice_negativo_vai_para_o_inicio(self):
        self.op(op="mover_ponto", uid="v1:TP03.01", para_assunto="v1:TP01", indice=-1)       # -1 não pode virar "antes do último"
        self.assertEqual(self.uids("v1:TP01"), ["v1:TP03.01", "v1:TP01.01", "v1:TP01.02"])

    def test_mover_assunto_renumera_filhos(self):
        self.op(op="mover_assunto", uid="v1:TP03", indice=0)
        c = self.cods()
        self.assertEqual(c["v1:TP03"], "TP01")
        self.assertEqual(c["v1:TP03.01"], "TP01.01")
        self.assertEqual(c["v1:TP01.01"], "TP02.01")

    def test_ponto_inexistente(self):
        with self.assertRaises(R.ErroOp):
            self.op(op="mover_ponto", uid="v1:XX", para_assunto="v1:TP01")

    def test_destino_inexistente(self):
        with self.assertRaises(R.ErroOp):
            self.op(op="mover_ponto", uid="v1:TP01.01", para_assunto="v1:XX")


class TestEdicao(Base):
    def test_editar_ponto(self):
        self.op(op="editar_ponto", uid="v1:TP01.01", texto="  Novo nome ", descricao="Uma linha")
        p = R.achar_ponto(self.d, "v1:TP01.01")[2]
        self.assertEqual((p["texto"], p["descricao"]), ("Novo nome", "Uma linha"))

    def test_nome_vazio_recusado(self):
        with self.assertRaises(R.ErroOp):
            self.op(op="editar_ponto", uid="v1:TP01.01", texto="   ")
        with self.assertRaises(R.ErroOp):
            self.op(op="editar_assunto", uid="v1:TP01", nome="")

    def test_pre_requisito(self):
        self.op(op="editar_assunto", uid="v1:TP02", pre_requisito="v1:TP01")
        self.assertEqual(R.achar_assunto(self.d, "v1:TP02")[1]["pre_requisito"], "v1:TP01")
        with self.assertRaises(R.ErroOp):
            self.op(op="editar_assunto", uid="v1:TP02", pre_requisito="v1:TP02")
        with self.assertRaises(R.ErroOp):
            self.op(op="editar_assunto", uid="v1:TP02", pre_requisito="v1:NAO")

    def test_novos(self):
        self.op(op="novo_ponto", assunto="v1:TP03", indice=0, texto="Criado")
        novo = R.achar_assunto(self.d, "v1:TP03")[1]["pontos"][0]
        self.assertTrue(novo["uid"].startswith("n:"))
        self.assertIsNone(novo["antigo"])
        self.op(op="novo_assunto", indice=1, nome="Assunto criado")
        self.assertEqual(self.d["assuntos"][1]["nome"], "Assunto criado")
        self.assertEqual(self.cods()[self.d["assuntos"][1]["uid"]], "TP02")

    def test_campo_faltando(self):
        with self.assertRaises(R.ErroOp):
            self.op(op="mover_ponto", uid="v1:TP01.01")


class TestLixeira(Base):
    def test_apagar_com_questoes_exige_destino(self):
        with self.assertRaises(R.ErroOp) as cm:
            self.op(op="apagar_ponto", uid="v1:TP01.01")
        self.assertIn("5 questões", str(cm.exception))
        self.assertEqual(len(self.uids("v1:TP01")), 2)         # nada mudou

    def test_apagar_sem_questoes_nao_exige(self):
        self.op(op="apagar_ponto", uid="v1:TP01.02")
        self.assertEqual(self.uids("v1:TP01"), ["v1:TP01.01"])
        self.assertEqual(self.d["lixeira"][0]["uid"], "v1:TP01.02")

    def test_fundir_com_destino_soma_contagens(self):
        self.op(op="apagar_ponto", uid="v1:TP01.01", destino="v1:TP02.01")
        ef = R.contagens_efetivas(self.d, self.banco)
        self.assertEqual(ef["v1:TP02.01"], (2 + 5, 1 + 6))

    def test_destino_invalido(self):
        with self.assertRaises(R.ErroOp):
            self.op(op="apagar_ponto", uid="v1:TP01.01", destino="v1:TP01.01")
        with self.assertRaises(R.ErroOp):
            self.op(op="apagar_ponto", uid="v1:TP01.01", destino="v1:NAO")

    def test_cadeia_de_destinos(self):
        self.op(op="apagar_ponto", uid="v1:TP01.01", destino="v1:TP02.01")      # 01.01 -> 02.01
        self.op(op="apagar_ponto", uid="v1:TP02.01", destino="v1:TP02.02")      # 02.01 -> 02.02 (e 01.01 passa junto)
        ef = R.contagens_efetivas(self.d, self.banco)
        self.assertEqual(ef["v1:TP02.02"], (3 + 2 + 5, 9 + 1 + 6))
        self.assertEqual(R._destino_final(self.d, "v1:TP01.01"), "v1:TP02.02")

    def test_restaurar(self):
        self.op(op="apagar_ponto", uid="v1:TP01.02")
        self.op(op="restaurar_ponto", uid="v1:TP01.02", assunto="v1:TP02", indice=0)
        self.assertEqual(self.uids("v1:TP02")[0], "v1:TP01.02")
        self.assertEqual(self.d["lixeira"], [])
        with self.assertRaises(R.ErroOp):
            self.op(op="restaurar_ponto", uid="v1:TP01.02", assunto="v1:TP02")

    def test_apagar_assunto_so_vazio(self):
        with self.assertRaises(R.ErroOp):
            self.op(op="apagar_assunto", uid="v1:TP03")
        self.op(op="apagar_ponto", uid="v1:TP03.01", destino="v1:TP01.01")
        self.op(op="apagar_assunto", uid="v1:TP03")
        self.assertEqual(len(self.d["assuntos"]), 2)
        self.op(op="restaurar_assunto", uid="v1:TP03", indice=0)
        self.assertEqual(self.d["assuntos"][0]["uid"], "v1:TP03")

    def test_rebaixar_assunto(self):
        self.op(op="rebaixar_assunto", uid="v1:TP03", para_assunto="v1:TP01", indice=2)
        novo = R.achar_assunto(self.d, "v1:TP01")[1]["pontos"][2]
        self.assertEqual(novo["texto"], "Pequeno")
        self.assertEqual(self.d["lixeira"][0]["destino"], novo["uid"])
        self.assertEqual(R.contagens_efetivas(self.d, self.banco)[novo["uid"]], (1, 2))
        with self.assertRaises(R.ErroOp):
            self.op(op="restaurar_assunto", uid="v1:TP03")
        with self.assertRaises(R.ErroOp):
            self.op(op="rebaixar_assunto", uid="v1:TP01", para_assunto="v1:TP01")


class TestHistorico(Base):
    def test_desfazer_e_refazer(self):
        antes = json.dumps(self.d["assuntos"], sort_keys=True)
        self.op(op="mover_ponto", uid="v1:TP02.01", para_assunto="v1:TP01", indice=0)
        depois = json.dumps(self.d["assuntos"], sort_keys=True)
        self.assertNotEqual(antes, depois)
        self.op(op="desfazer")
        self.assertEqual(json.dumps(self.d["assuntos"], sort_keys=True), antes)
        self.op(op="refazer")
        self.assertEqual(json.dumps(self.d["assuntos"], sort_keys=True), depois)

    def test_nada_para_desfazer_ou_refazer(self):
        with self.assertRaises(R.ErroOp):
            self.op(op="desfazer")
        with self.assertRaises(R.ErroOp):
            self.op(op="refazer")

    def test_nova_operacao_limpa_o_refazer(self):
        self.op(op="editar_ponto", uid="v1:TP01.01", texto="A")
        self.op(op="desfazer")
        self.op(op="editar_ponto", uid="v1:TP01.01", texto="B")
        with self.assertRaises(R.ErroOp):
            self.op(op="refazer")

    def test_operacao_invalida_nao_entra_no_historico(self):
        with self.assertRaises(R.ErroOp):
            self.op(op="mover_ponto", uid="v1:XX", para_assunto="v1:TP01")
        self.assertEqual(R.carregar("teste")["historico"]["passado"], [])

    def test_limite_do_historico(self):
        for k in range(R.LIMITE_HISTORICO + 5):
            self.op(op="editar_ponto", uid="v1:TP01.01", texto=f"n{k}")
        self.assertEqual(len(R.carregar("teste")["historico"]["passado"]), R.LIMITE_HISTORICO)

    def test_persistencia_e_backup(self):
        self.op(op="editar_ponto", uid="v1:TP01.01", texto="Persistido")
        self.assertTrue(R.arquivo("teste").with_suffix(".bak").exists())
        self.assertEqual(R.achar_ponto(R.carregar("teste"), "v1:TP01.01")[2]["texto"], "Persistido")
        self.assertEqual(list(self.tmp.glob("*.tmp")), [])


class TestMapa(Base):
    def acao(self, antigo, tipo="ponto"):
        return next(m for m in R.mapa(self.d) if m["tipo"] == tipo and m["antigo"] == antigo)

    def test_tudo_mantido_no_inicio(self):
        self.assertTrue(all(m["acao"] == "mantido" for m in R.mapa(self.d)))
        self.assertEqual(len(R.mapa(self.d)), 3 + 5)

    def test_acoes(self):
        self.op(op="mover_ponto", uid="v1:TP02.01", para_assunto="v1:TP01", indice=0)
        self.op(op="editar_ponto", uid="v1:TP02.02", texto="Condenado e internado")
        self.op(op="mover_ponto", uid="v1:TP03.01", para_assunto="v1:TP02", indice=0)
        self.op(op="editar_ponto", uid="v1:TP03.01", texto="Único renomeado")
        self.op(op="apagar_ponto", uid="v1:TP01.02")
        self.op(op="apagar_ponto", uid="v1:TP01.01", destino="v1:TP02.01")
        self.op(op="novo_ponto", assunto="v1:TP01", texto="Criado")
        m = self.acao("TP02.01")
        self.assertEqual((m["acao"], m["novo"]), ("movido", "TP01.01"))
        self.assertEqual(self.acao("TP02.02")["acao"], "renomeado")
        self.assertEqual(self.acao("TP03.01")["acao"], "movido e renomeado")
        self.assertEqual(self.acao("TP01.02")["acao"], "apagado")
        f = self.acao("TP01.01")
        self.assertEqual((f["acao"], f["destino"]), ("fundido", "TP01.01"))
        novos = [m for m in R.mapa(self.d) if m["acao"] == "novo"]
        self.assertEqual(len(novos), 1)

    def test_renumerado(self):
        self.op(op="mover_ponto", uid="v1:TP01.01", para_assunto="v1:TP01", indice=1)
        self.assertEqual(self.acao("TP01.01")["acao"], "renumerado")
        self.assertEqual(self.acao("TP01.02")["acao"], "renumerado")

    def test_assunto_rebaixado_e_apagado(self):
        self.op(op="rebaixar_assunto", uid="v1:TP03", para_assunto="v1:TP01", indice=0)
        m = self.acao("TP03", "assunto")
        self.assertEqual((m["acao"], m["destino"]), ("rebaixado a ponto", "TP01.01"))
        f = self.acao("TP03.01")
        self.assertEqual((f["acao"], f["destino"]), ("fundido", "TP01.01"))

    def test_exportar_csv(self):
        self.op(op="editar_ponto", uid="v1:TP01.01", texto="Natureza revista")
        arq = R.exportar_mapa(self.d)
        with open(arq, encoding="utf-8") as f:
            linhas = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(arq.name, "_mapa_teste_v1_v2.csv")
        self.assertIn(("TP01.01", "renomeado"), [(l["antigo"], l["acao"]) for l in linhas])


class TestDiagnostico(Base):
    def test_faixas_e_avisos(self):
        dg = R.diagnostico(self.d, self.banco)
        self.assertEqual(dg["assuntos"], 3)
        self.assertTrue(any("assuntos" in a for a in dg["avisos"]))           # 3 assuntos: abaixo do mínimo de 8
        tp03 = next(x for x in dg["por_assunto"] if x["codigo"] == "TP03")
        self.assertIn("pequeno", tp03["flags"])

    def test_sem_evidencia(self):
        dg = R.diagnostico(self.d, self.banco)
        self.assertIn("v1:TP01.02", dg["pontos_sem_evidencia"])               # 0 questões e 0 itens
        self.assertNotIn("v1:TP01.01", dg["pontos_sem_evidencia"])            # 5 questões

    def test_fundir_muda_o_diagnostico(self):
        self.op(op="apagar_ponto", uid="v1:TP01.01", destino="v1:TP02.01")
        v = R.visao(self.d, self.banco)
        p = next(p for a in v["assuntos"] for p in a["pontos"] if p["uid"] == "v1:TP02.01")
        self.assertEqual(p["questoes"], 7)

    def test_visao(self):
        v = R.visao(self.d, self.banco)
        self.assertFalse(v["pode_desfazer"])
        self.op(op="editar_ponto", uid="v1:TP01.01", texto="X")
        self.assertTrue(R.visao(self.d, self.banco)["pode_desfazer"])
        self.assertEqual(v["assuntos"][0]["pontos"][0]["questoes"], 5)

    def test_visao_da_lixeira_traz_o_assunto_de_origem(self):
        self.op(op="apagar_ponto", uid="v1:TP01.02")
        item = R.visao(self.d, self.banco)["lixeira"][0]
        self.assertEqual((item["uid"], item["assunto_uid"]), ("v1:TP01.02", "v1:TP01"))

    def test_questoes_do_ponto(self):
        self.op(op="apagar_ponto", uid="v1:TP01.01", destino="v1:TP02.01")
        qs = R.questoes_do_ponto(self.d, "v1:TP02.01", self.banco)
        self.assertEqual(len(qs), 7)
        self.assertIn("Enunciado", qs[0]["trecho"])


class BaseOrdem(Base):
    """Acrescenta o catálogo 'ordem' (5 assuntos de 1 ponto; editais na ordem dos assuntos; questões com vocabulário próprio)."""

    def setUp(self):
        super().setUp()
        (self.tmp / "ordem.json").write_text(json.dumps(V1_ORDEM, ensure_ascii=False), encoding="utf-8")
        self.do = R.criar_de_v1("ordem")

    def oop(self, **kw):
        self.do = R.aplicar_op("ordem", kw, self.banco)
        return self.do


class TestOrdemDidatica(BaseOrdem):
    def test_ordem_igual_a_dos_editais_da_rho_um(self):
        o = R.ordem_didatica(self.do, self.banco)
        self.assertEqual((o["rho"], o["assuntos_com_dados"]), (1.0, 5))
        self.assertEqual(o["por_assunto"]["v1:OR01"]["pos_atual"], 1)

    def test_medianas_das_posicoes(self):
        o = R.ordem_didatica(self.do, self.banco)["por_assunto"]
        self.assertAlmostEqual(o["v1:OR01"]["mediana"], 2 / 24, places=2)       # itens 0 a 4 de 25
        self.assertAlmostEqual(o["v1:OR05"]["mediana"], 22 / 24, places=2)      # itens 20 a 24 de 25
        self.assertEqual(o["v1:OR01"]["n"], 10)                                  # 5 itens em 2 editais

    def test_assunto_levado_ao_inicio_zera_a_correlacao(self):
        self.oop(op="mover_assunto", uid="v1:OR05", indice=0)
        o = R.ordem_didatica(self.do, self.banco)
        self.assertEqual(o["rho"], 0.0)
        self.assertEqual((o["por_assunto"]["v1:OR05"]["pos_atual"], o["por_assunto"]["v1:OR05"]["pos_editais"]), (1, 5))

    def test_ordem_invertida_da_rho_menos_um(self):
        for uid, i in (("v1:OR05", 0), ("v1:OR04", 1), ("v1:OR03", 2), ("v1:OR02", 3)):
            self.oop(op="mover_assunto", uid=uid, indice=i)
        self.assertEqual(R.ordem_didatica(self.do, self.banco)["rho"], -1.0)

    def test_sem_itens_com_posicao_nao_ha_correlacao(self):
        o = R.ordem_didatica(self.d, self.banco)                                # disciplina de teste: sem itens com posição
        self.assertIsNone(o["rho"])
        self.assertEqual(o["por_assunto"], {})

    def test_fusao_leva_as_posicoes_junto(self):
        self.oop(op="apagar_ponto", uid="v1:OR01.01", destino="v1:OR02.01")
        o = R.ordem_didatica(self.do, self.banco)["por_assunto"]
        self.assertNotIn("v1:OR01", o)                                           # o assunto ficou sem pontos
        self.assertEqual(o["v1:OR02"]["n"], 20)
        self.assertAlmostEqual(o["v1:OR02"]["mediana"], 4.5 / 24, places=2)

    def test_item_ligado_a_dois_pontos_do_mesmo_assunto_conta_uma_vez(self):
        # o item 200 já está em OR01 e em OR02; ao fundir OR01.01 em OR02.01 ele passa a ser candidato duas vezes ao mesmo assunto
        self.oop(op="apagar_ponto", uid="v1:OR01.01", destino="v1:OR02.01")
        self.assertEqual(R.ordem_didatica(self.do, self.banco)["por_assunto"]["v1:OR02"]["n"], 20)   # 10 itens x 2 editais, não 22

    def test_visao_traz_rho_e_dados_do_assunto(self):
        v = R.visao(self.do, self.banco)
        self.assertEqual(v["ordem"]["rho"], 1.0)
        self.assertEqual(v["assuntos"][0]["ordem"]["pos_editais"], 1)

    def test_banco_sem_tabelas_de_edital(self):
        vazio = self.tmp / "vazio.db"
        sqlite3.connect(vazio).close()
        self.assertIsNone(R.ordem_didatica(self.do, vazio)["rho"])


class TestComparacao(BaseOrdem):
    def test_visao_traz_acao_e_texto_antigo(self):
        self.op(op="editar_ponto", uid="v1:TP01.01", texto="Natureza revista")
        self.op(op="mover_ponto", uid="v1:TP02.01", para_assunto="v1:TP01", indice=0)
        pts = {p["uid"]: p for a in R.visao(self.d, self.banco)["assuntos"] for p in a["pontos"]}
        self.assertEqual((pts["v1:TP01.01"]["acao"], pts["v1:TP01.01"]["texto_antigo"]), ("renomeado", "Natureza"))
        self.assertEqual(pts["v1:TP02.01"]["acao"], "movido")
        self.assertIsNone(pts["v1:TP02.02"]["texto_antigo"])

    def test_v1_de_referencia_nao_muda_com_as_edicoes(self):
        self.op(op="mover_ponto", uid="v1:TP02.01", para_assunto="v1:TP01", indice=0)
        self.op(op="apagar_ponto", uid="v1:TP01.02")
        self.op(op="novo_assunto", nome="Outro")
        v1 = R.visao_v1(self.d, self.banco)
        self.assertEqual([a["codigo"] for a in v1["assuntos"]], ["TP01", "TP02", "TP03"])
        self.assertEqual([p["texto"] for p in v1["assuntos"][1]["pontos"]], ["Órgãos", "Condenado"])
        self.assertEqual(v1["assuntos"][0]["pontos"][0]["questoes"], 5)

    def test_comparacao_sem_mudancas_v1_igual_v2(self):
        c = R.comparacao(self.d, self.banco)
        self.assertEqual(c["v1"], c["v2"])
        self.assertEqual(set(c["mudancas"]), {"mantido"})

    def test_comparacao_depois_de_rebaixar(self):
        self.op(op="rebaixar_assunto", uid="v1:TP03", para_assunto="v1:TP01")
        c = R.comparacao(self.d, self.banco)
        self.assertEqual((c["v1"]["assuntos"], c["v2"]["assuntos"]), (3, 2))
        self.assertEqual(c["mudancas"].get("rebaixado a ponto"), 1)
        self.assertEqual(c["mudancas"].get("novo"), 1)


class TestMetricasClassificacao(BaseOrdem):
    def test_poucas_questoes_so_avisam(self):
        m = R.metricas_classificacao(self.d, self.banco)                        # disciplina de teste: 11 questões
        self.assertEqual(m["questoes"], 11)
        self.assertIn("aviso", m)
        self.assertNotIn("v1", m)

    def test_sem_mudancas_v1_e_v2_dao_o_mesmo(self):
        m = R.metricas_classificacao(self.do, self.banco)
        self.assertEqual(m["questoes"], 40)
        self.assertEqual(m["v1"], m["v2"])
        p = m["v1"]["ponto"]
        self.assertEqual((p["classes"], p["acuracia"], p["kappa"]), (5, 1.0, 1.0))      # vocabulário próprio por classe: acerta tudo
        self.assertEqual(p["acaso_maioria"], 0.2)

    def test_fundir_reduz_as_classes_e_mantem_as_questoes(self):
        self.oop(op="apagar_ponto", uid="v1:OR01.01", destino="v1:OR02.01")
        m = R.metricas_classificacao(self.do, self.banco)
        self.assertEqual(m["questoes"], 40)
        self.assertEqual((m["v1"]["ponto"]["classes"], m["v2"]["ponto"]["classes"]), (5, 4))
        self.assertEqual(m["v2"]["ponto"]["acaso_maioria"], 0.4)                 # a classe fundida tem 16 das 40
        self.assertIn("aviso", m)

    def test_movimento_de_ponto_nao_perde_questoes(self):
        self.oop(op="mover_ponto", uid="v1:OR05.01", para_assunto="v1:OR01", indice=1)
        m = R.metricas_classificacao(self.do, self.banco)
        self.assertEqual(m["questoes"], 40)
        self.assertEqual(m["v2"]["ponto"]["classes"], 5)                         # nenhum ponto foi fundido
        self.assertEqual(m["v1"]["assunto"]["classes"], 5)
        self.assertEqual(m["v2"]["assunto"]["classes"], 4)                       # o assunto OR05 ficou vazio: suas questões estão agora em OR01


class TestAPI(Base):
    def setUp(self):
        super().setUp()
        self.srv = E.criar_servidor(0, token="tok-teste", banco=self.banco)
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def chamar(self, metodo, caminho, corpo=None, token="tok-teste", host=None, extra=None):
        req = urllib.request.Request(self.base + caminho, method=metodo, data=json.dumps(corpo).encode("utf-8") if corpo is not None else None)
        if token is not None:
            req.add_header("X-Editor-Token", token)
        if host:
            req.add_header("Host", host)
        for k, v in (extra or {}).items():
            req.add_header(k, v)
        if corpo is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read().decode("utf-8")) if "json" in r.headers.get("Content-Type", "") else r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_sem_token_ou_token_errado(self):
        self.assertEqual(self.chamar("GET", "/api/catalogos", token=None)[0], 403)
        self.assertEqual(self.chamar("GET", "/api/catalogos", token="errado")[0], 403)
        self.assertEqual(self.chamar("POST", "/api/rascunho/teste/op", {"op": "desfazer"}, token="errado")[0], 403)

    def test_host_estranho_recusado(self):
        self.assertEqual(self.chamar("GET", "/api/catalogos", host="exemplo.com")[0], 403)

    def test_origem_de_outro_site_sem_token(self):
        self.assertEqual(self.chamar("POST", "/api/rascunho/teste/op", {"op": "desfazer"}, token=None, extra={"Origin": "http://exemplo.com"})[0], 403)

    def test_catalogos_visao_e_operacao(self):
        s, lista = self.chamar("GET", "/api/catalogos")
        self.assertEqual(s, 200)
        self.assertIn("teste", [c["slug"] for c in lista])
        s, v = self.chamar("GET", "/api/rascunho/teste")
        self.assertEqual((s, v["disciplina"]), (200, "Disciplina de Teste"))
        s, v = self.chamar("POST", "/api/rascunho/teste/op", {"op": "mover_ponto", "uid": "v1:TP02.01", "para_assunto": "v1:TP01", "indice": 0})
        self.assertEqual(s, 200)
        self.assertEqual(v["assuntos"][0]["pontos"][0]["codigo"], "TP01.01")
        self.assertTrue(v["pode_desfazer"])

    def test_erros_viram_400(self):
        s, r = self.chamar("POST", "/api/rascunho/teste/op", {"op": "apagar_ponto", "uid": "v1:TP01.01"})
        self.assertEqual(s, 400)
        self.assertIn("questões", r["erro"])
        self.assertEqual(self.chamar("POST", "/api/rascunho/teste/op", {"op": "inexistente"})[0], 400)
        self.assertEqual(self.chamar("GET", "/api/rascunho/nao-existe")[0], 400)

    def test_slug_invalido(self):
        self.assertEqual(self.chamar("GET", "/api/rascunho/..%2Fsegredo")[0], 400)
        self.assertEqual(self.chamar("GET", "/api/rascunho/A_B")[0], 400)

    def test_criar_mapa_e_questoes(self):
        shutil.copy(self.tmp / "teste.json", self.tmp / "outro.json")
        s, v = self.chamar("POST", "/api/rascunho/outro/criar", {})
        self.assertEqual(s, 200)
        self.assertEqual(self.chamar("POST", "/api/rascunho/outro/criar", {})[0], 400)       # já existe
        s, m = self.chamar("GET", "/api/rascunho/teste/mapa")
        self.assertEqual((s, len(m)), (200, 8))
        s, r = self.chamar("POST", "/api/rascunho/teste/mapa/exportar", {})
        self.assertEqual(s, 200)
        s, qs = self.chamar("GET", "/api/rascunho/teste/questoes?uid=v1:TP01.01")
        self.assertEqual((s, len(qs)), (200, 5))

    def test_comparacao_v1_e_metricas(self):
        (self.tmp / "ordem.json").write_text(json.dumps(V1_ORDEM, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.chamar("POST", "/api/rascunho/ordem/criar", {})[0], 200)
        self.chamar("POST", "/api/rascunho/ordem/op", {"op": "apagar_ponto", "uid": "v1:OR01.01", "destino": "v1:OR02.01"})
        s, c = self.chamar("GET", "/api/rascunho/ordem/comparacao")
        self.assertEqual((s, c["v1"]["assuntos"], c["v2"]["assuntos"]), (200, 5, 5))
        self.assertEqual(c["mudancas"].get("fundido"), 1)
        s, v1 = self.chamar("GET", "/api/rascunho/ordem/v1")
        self.assertEqual((s, len(v1["assuntos"]), v1["assuntos"][0]["pontos"][0]["questoes"]), (200, 5, 8))
        s, m = self.chamar("GET", "/api/rascunho/ordem/metricas")
        self.assertEqual((s, m["questoes"], m["v2"]["ponto"]["classes"]), (200, 40, 4))
        s, v = self.chamar("GET", "/api/rascunho/ordem")
        self.assertEqual(v["ordem"]["assuntos_com_dados"], 4)                    # OR01 ficou sem pontos e sai da conta

    def test_endpoints_novos_exigem_token(self):
        for rota in ("comparacao", "v1", "metricas"):
            self.assertEqual(self.chamar("GET", f"/api/rascunho/teste/{rota}", token=None)[0], 403)

    def test_corpo_invalido(self):
        req = urllib.request.Request(self.base + "/api/rascunho/teste/op", method="POST", data=b"nao e json", headers={"X-Editor-Token": "tok-teste"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)

    def test_pagina_recebe_o_token(self):
        req = urllib.request.Request(self.base + "/")
        with urllib.request.urlopen(req) as r:
            html = r.read().decode("utf-8")
        self.assertIn("tok-teste", html)
        self.assertNotIn("__TOKEN__", html)


class TestIntegracaoDadosReais(unittest.TestCase):
    """Usa uma CÓPIA do catálogo real de Execução Penal e o banco real (só leitura); precisa reproduzir o diagnóstico do grupo B."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._pasta = R.PASTA
        R.PASTA = self.tmp
        shutil.copy(RAIZ / "dados" / "catalogo" / "execucao-penal.json", self.tmp / "execucao-penal.json")

    def tearDown(self):
        R.PASTA = self._pasta
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_execucao_penal_bate_com_o_catalogo_atual(self):
        """Depois da publicação do v2 (20/11/2026) o catálogo real de Execução Penal é o v2; o v1 só existe no backup do banco.
        O teste confere que a visão do editor concorda com o arquivo atual, sem fixar números de um catálogo antigo."""
        arq = json.loads((RAIZ / "dados" / "catalogo" / "execucao-penal.json").read_text(encoding="utf-8"))
        d = R.criar_de_v1("execucao-penal")
        v = R.visao(d)
        self.assertEqual(v["prefixo"], "EX")
        self.assertEqual(len(v["assuntos"]), len(arq["assuntos"]))
        self.assertEqual(sum(len(a["pontos"]) for a in v["assuntos"]), sum(1 for p in arq["pontos"] if p.get("ativo", 1)))
        self.assertTrue(all(isinstance(x["flags"], list) for x in v["diagnostico"]["por_assunto"]))

    def test_mapa_inicial_todo_mantido(self):
        d = R.criar_de_v1("execucao-penal")
        self.assertTrue(all(m["acao"] == "mantido" for m in R.mapa(d)))

    def test_arquivos_reais_intactos(self):
        real = RAIZ / "dados" / "catalogo" / "_rascunho_execucao-penal_v2.json"
        antes = (RAIZ / "dados" / "catalogo" / "execucao-penal.json").read_bytes()
        rascunho_antes = real.read_bytes() if real.exists() else None     # o rascunho real (aprovado pelo usuário) não pode mudar
        d = R.criar_de_v1("execucao-penal")
        R.aplicar_op("execucao-penal", {"op": "editar_ponto", "uid": d["assuntos"][0]["pontos"][0]["uid"], "texto": "Mudado no teste"})
        self.assertEqual((RAIZ / "dados" / "catalogo" / "execucao-penal.json").read_bytes(), antes)
        self.assertEqual(real.read_bytes() if real.exists() else None, rascunho_antes)     # o rascunho foi para a pasta temporária


# ---------------------------------------------------------------- revisão do conjunto de referência (M4)
import lib_revisao as V  # noqa: E402

CODS = {"A": "PE01.01", "B": "PE01.02", "C": "PE01.03", "D": "PE01.04", "E": "PE01.05"}
# (atual, ia1, ia2) por questão 1..10: 1 a 6 unânimes; 7 maioria com as IA contra o rótulo atual; 8 e 9 maioria com uma IA dissidente; 10 sem maioria
LEITURAS = {1: "AAA", 2: "AAA", 3: "AAA", 4: "BBB", 5: "BBB", 6: "CCC", 7: "ABB", 8: "CCD", 9: "DED", 10: "ABC"}


def criar_referencia(tmp):
    """Pasta de referência e banco sintéticos (disciplina 'Direito Penal', 5 pontos, 10 questões)."""
    ref = Path(tmp) / "ref"
    ref.mkdir()
    banco = Path(tmp) / "rev.db"
    con = sqlite3.connect(banco)
    con.executescript("""
        create table disciplinas(id integer primary key, nome text);
        create table assuntos(id integer primary key, disciplina_id integer, codigo text, nome text);
        create table pontos(id integer primary key, disciplina_id integer, assunto_id integer, codigo text, texto text, ativo integer);
        create table provas(id integer primary key, nome text, ano integer);
        create table questoes(id integer primary key, prova_id integer, numero integer, enunciado text, alt_a text, alt_b text, alt_c text, alt_d text,
                              alt_e text, gabarito text);
    """)
    con.execute("insert into disciplinas values (1,'Direito Penal')")
    con.execute("insert into assuntos values (1,1,'PE01','Fundamentos')")
    for i, cod in enumerate(CODS.values(), 1):
        con.execute("insert into pontos values (?,1,1,?,?,1)", (i, cod, f"Ponto {cod}"))
    con.execute("insert into pontos values (99,1,1,'PE01.99','Ponto inativo',0)")
    con.execute("insert into provas values (1,'Prova T',2025)")
    for n in range(1, 11):
        con.execute("insert into questoes values (?,1,?,?,?,?,?,?,?,?)", (n, n, f"Enunciado {n}", "a", "b", "c", "d", "e", "B"))
    con.commit()
    con.close()
    with open(ref / "amostra_2026-01-01.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["prova", "numero", "disciplina", "ponto_atual", "assunto_atual", "ano"])
        for n, tri in LEITURAS.items():
            w.writerow(["Prova T", n, "PENAL", CODS[tri[0]], "PE01", 2025])
    for k, nome in ((1, "ia1"), (2, "ia2")):
        (ref / f"leitura_{nome}.json").write_text(json.dumps({f"Prova T|{n}": CODS[tri[k]] for n, tri in LEITURAS.items()}), encoding="utf-8")
    return ref, banco


class BaseRevisao(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ref, self.banco = criar_referencia(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fila(self, n_controle=3):
        return V.montar_fila(self.ref, self.banco, n_controle=n_controle)

    def responder(self, n, letra_ou_codigo, nota="", n_controle=3):
        cod = CODS.get(letra_ou_codigo, letra_ou_codigo)
        return V.registrar_resposta(f"Prova T|{n}", cod, nota, self.ref, self.banco, n_controle=n_controle)


class TestClassificarLeitores(unittest.TestCase):
    def test_casos(self):
        self.assertEqual(V.classificar("A", "A", "A"), ("unanime", None, "A"))
        self.assertEqual(V.classificar("A", "B", "B"), ("maioria", "atual_diverge", "B"))
        self.assertEqual(V.classificar("C", "C", "D"), ("maioria", "ia_dissidente", "C"))
        self.assertEqual(V.classificar("D", "E", "D"), ("maioria", "ia_dissidente", "D"))
        self.assertEqual(V.classificar("A", "B", "C"), ("sem_maioria", None, None))


class TestFila(BaseRevisao):
    def test_composicao_e_ordem(self):
        f = self.fila()
        self.assertEqual([(i["numero"], i["tipo"], i["subtipo"]) for i in f][:4],
                         [(10, "sem_maioria", None), (7, "maioria", "atual_diverge"), (8, "maioria", "ia_dissidente"), (9, "maioria", "ia_dissidente")])
        self.assertEqual([i["tipo"] for i in f[4:]], ["controle"] * 3)
        self.assertTrue(all(i["numero"] <= 6 for i in f[4:]))                      # o controle vem só das unânimes (1 a 6)

    def test_controle_reproduzivel(self):
        self.assertEqual([i["chave"] for i in self.fila()], [i["chave"] for i in self.fila()])

    def test_controle_limitado_ao_que_existe(self):
        self.assertEqual(len([i for i in self.fila(n_controle=99) if i["tipo"] == "controle"]), 6)

    def test_opcoes_juntam_leitores_com_o_mesmo_codigo(self):
        i7 = next(i for i in self.fila() if i["numero"] == 7)                     # atual A; IA 1 e IA 2 B
        self.assertEqual([(o["letra"], o["codigo"], o["fontes"]) for o in i7["opcoes"]], [("A", CODS["A"], ["atual"]), ("B", CODS["B"], ["ia1", "ia2"])])
        i10 = next(i for i in self.fila() if i["numero"] == 10)
        self.assertEqual([o["codigo"] for o in i10["opcoes"]], [CODS["A"], CODS["B"], CODS["C"]])

    def test_controle_tem_uma_opcao_com_as_tres_fontes(self):
        c = next(i for i in self.fila() if i["tipo"] == "controle")
        self.assertEqual(len(c["opcoes"]), 1)
        self.assertEqual(c["opcoes"][0]["fontes"], ["atual", "ia1", "ia2"])

    def test_item_traz_texto_gabarito_e_catalogo_so_dos_ativos(self):
        i = self.fila()[0]
        self.assertEqual((i["enunciado"], i["gabarito"], len(i["alternativas"])), ("Enunciado 10", "B", 5))
        self.assertEqual([c["codigo"] for c in i["catalogo"]], list(CODS.values()))        # o inativo PE01.99 não aparece
        self.assertEqual(i["catalogo"][0]["assunto_nome"], "Fundamentos")

    def test_sem_leitura_da_ia_2_recusa(self):
        (self.ref / "leitura_ia2.json").unlink()
        with self.assertRaises(V.ErroRevisao):
            self.fila()


class TestRespostas(BaseRevisao):
    def test_grava_com_origem_usuario(self):
        r = self.responder(10, "A")
        self.assertEqual((r["origem"], r["ponto_ouro"], r["tipo"]), ("usuario", CODS["A"], "sem_maioria"))
        with open(self.ref / "referencia_ouro.csv", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual((len(linhas), linhas[0]["origem"]), (1, "usuario"))
        self.assertEqual(list(self.ref.glob("*.tmp")), [])

    def test_sobrescreve_e_aparece_na_fila(self):
        self.responder(10, "A")
        self.responder(10, "B")
        i = next(i for i in self.fila() if i["numero"] == 10)
        self.assertEqual(i["resposta"]["ponto_ouro"], CODS["B"])

    def test_codigo_invalido_ou_inativo_ou_de_outra_disciplina(self):
        for cod in ("XX99.99", "PE01.99", ""):
            with self.assertRaises(V.ErroRevisao):
                self.responder(10, cod)

    def test_nenhum_exige_nota(self):
        with self.assertRaises(V.ErroRevisao):
            self.responder(10, "NENHUM")
        r = self.responder(10, "NENHUM", "falta um ponto de erro de execução")
        self.assertEqual(r["ponto_ouro"], "NENHUM")

    def test_nota_longa_demais(self):
        with self.assertRaises(V.ErroRevisao):
            self.responder(10, "A", "x" * (V.LIMITE_NOTA + 1))

    def test_questao_fora_da_fila_e_recusada(self):
        controle = {i["numero"] for i in self.fila() if i["tipo"] == "controle"}
        fora = next(n for n in range(1, 7) if n not in controle)                   # unânime que não foi sorteada
        with self.assertRaises(V.ErroRevisao):
            self.responder(fora, "A")
        with self.assertRaises(V.ErroRevisao):
            V.registrar_resposta("Prova inexistente|1", CODS["A"], "", self.ref, self.banco, n_controle=3)

    def test_desfazer(self):
        self.responder(10, "A")
        V.desfazer_resposta("Prova T|10", self.ref)
        self.assertIsNone(next(i for i in self.fila() if i["numero"] == 10)["resposta"])
        with self.assertRaises(V.ErroRevisao):
            V.desfazer_resposta("Prova T|10", self.ref)


class TestResumo(BaseRevisao):
    def responder_nao_unanimes(self):
        self.responder(10, "A")      # concorda com o rótulo atual
        self.responder(7, "B")       # concorda com a dupla de IA (contra o rótulo atual)
        self.responder(8, "C")       # rótulo atual
        self.responder(9, "E")       # nem o rótulo atual nem a dupla de IA (só a IA 1 tinha E)

    def test_wilson(self):
        self.assertEqual(V.wilson(0, 0), (None, None))
        lo, hi = V.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.2366, places=2)
        self.assertAlmostEqual(hi, 0.7634, places=2)
        self.assertEqual(V.wilson(0, 10)[0], 0.0)
        self.assertEqual(V.wilson(10, 10)[1], 1.0)

    def test_sem_respostas(self):
        r = V.resumo(self.ref, self.banco, n_controle=3)
        self.assertEqual((r["fila"]["total"], r["fila"]["respondidas"]), (7, 0))
        self.assertIsNone(r["estimativa"])
        self.assertEqual(r["nao_unanimes"]["total"], 4)

    def test_posicao_do_usuario_nas_nao_unanimes(self):
        self.responder_nao_unanimes()
        nu = V.resumo(self.ref, self.banco, n_controle=3)["nao_unanimes"]
        self.assertEqual((nu["respondidas"], nu["com_atual"], nu["com_dupla_ia"], nu["outro"], nu["nenhum"]), (4, 2, 1, 1, 0))

    def test_estimativa_estratificada_completa(self):
        self.responder_nao_unanimes()
        ctrl = [i for i in self.fila() if i["tipo"] == "controle"]
        for k, i in enumerate(ctrl):                              # 2 confirmam a unanimidade; 1 discorda
            cod = i["opcoes"][0]["codigo"]
            self.responder(i["numero"], cod if k < 2 else next(c for c in CODS.values() if c != cod))
        r = V.resumo(self.ref, self.banco, n_controle=3)
        self.assertEqual(r["controle"]["discordou"], 1)
        e = r["estimativa"]
        self.assertTrue(e["completa"])
        self.assertAlmostEqual(e["acerto_rotulo_atual"], (6 * (2 / 3) + 2) / 10, places=6)           # 0,6
        self.assertAlmostEqual(e["ic95"][0], (6 * (1 - 0.7924) + 2) / 10, places=2)
        self.assertAlmostEqual(e["ic95"][1], (6 * (1 - 0.0615) + 2) / 10, places=2)
        self.assertIn("Amostra de controle pequena", e["aviso"])                 # 3 respostas de controle: abaixo do mínimo de 10
        self.assertNotIn("PARCIAL", e["aviso"])

    def test_sem_aviso_quando_completa_e_com_controle_suficiente(self):
        self.responder_nao_unanimes()
        for i in [i for i in self.fila() if i["tipo"] == "controle"]:
            self.responder(i["numero"], i["opcoes"][0]["codigo"])
        antes = V.MIN_CONTROLE
        V.MIN_CONTROLE = 3                                                          # o conjunto sintético só tem 3 de controle
        try:
            e = V.resumo(self.ref, self.banco, n_controle=3)["estimativa"]
        finally:
            V.MIN_CONTROLE = antes
        self.assertIsNone(e["aviso"])
        self.assertAlmostEqual(e["acerto_rotulo_atual"], (6 * 1.0 + 2) / 10, places=6)           # ninguém discordou: 0,8

    def test_estimativa_parcial_avisa(self):
        self.responder(10, "A")
        i = next(i for i in self.fila() if i["tipo"] == "controle")
        self.responder(i["numero"], i["opcoes"][0]["codigo"])
        e = V.resumo(self.ref, self.banco, n_controle=3)["estimativa"]
        self.assertFalse(e["completa"])
        self.assertIn("PARCIAL", e["aviso"])
        self.assertIn("Amostra de controle pequena", e["aviso"])                  # 1 resposta de controle

    def test_sem_amostra_de_controle_nao_ha_estimativa(self):
        self.responder_nao_unanimes()
        self.assertIsNone(V.resumo(self.ref, self.banco, n_controle=3)["estimativa"])

    def test_acordo_do_humano_com_cada_leitor(self):
        self.responder_nao_unanimes()
        a = V.resumo(self.ref, self.banco, n_controle=3)["acordo_humano"]
        self.assertEqual((a["atual"]["n"], a["atual"]["acordo"]), (4, 0.5))                # 10 e 8 concordam com o rótulo atual
        self.assertEqual(a["ia1"]["acordo"], 0.75)                                           # IA 1: 10 não (B), 7 sim, 8 sim, 9 sim


class TestAPIRevisao(BaseRevisao):
    def setUp(self):
        super().setUp()
        self.srv = E.criar_servidor(0, token="tok-rev", banco=self.banco, referencia=self.ref)
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def chamar(self, metodo, caminho, corpo=None, token="tok-rev"):
        req = urllib.request.Request(self.base + caminho, method=metodo, data=json.dumps(corpo).encode("utf-8") if corpo is not None else None)
        if token is not None:
            req.add_header("X-Editor-Token", token)
        if corpo is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_exige_token(self):
        for metodo, rota, corpo in (("GET", "/api/referencia/fila", None), ("GET", "/api/referencia/resumo", None),
                                    ("POST", "/api/referencia/resposta", {"chave": "Prova T|10", "ponto_ouro": CODS["A"]}),
                                    ("POST", "/api/referencia/desfazer", {"chave": "Prova T|10"})):
            self.assertEqual(self.chamar(metodo, rota, corpo, token=None)[0], 403)
        self.assertFalse((self.ref / "referencia_ouro.csv").exists())                        # nada foi gravado sem token

    def test_fila_resposta_desfazer_e_resumo(self):
        s, f = self.chamar("GET", "/api/referencia/fila")
        self.assertEqual((s, len(f["itens"]), f["progresso"]["respondidas"]), (200, 10, 0))      # 4 não unânimes + as 6 unânimes (o padrão pede até 15)
        s, r = self.chamar("POST", "/api/referencia/resposta", {"chave": "Prova T|10", "ponto_ouro": CODS["B"], "nota": ""})
        self.assertEqual((s, r["resposta"]["origem"], r["progresso"]["respondidas"]), (200, "usuario", 1))
        s, f = self.chamar("GET", "/api/referencia/fila")
        self.assertEqual(f["itens"][0]["resposta"]["ponto_ouro"], CODS["B"])
        s, r = self.chamar("POST", "/api/referencia/desfazer", {"chave": "Prova T|10"})
        self.assertEqual((s, r["progresso"]["respondidas"]), (200, 0))
        s, rs = self.chamar("GET", "/api/referencia/resumo")
        self.assertEqual((s, rs["nao_unanimes"]["total"]), (200, 4))

    def test_erros_viram_400(self):
        self.assertEqual(self.chamar("POST", "/api/referencia/resposta", {"chave": "Prova T|10", "ponto_ouro": "XX"})[0], 400)
        self.assertEqual(self.chamar("POST", "/api/referencia/resposta", {"chave": "Prova T|10", "ponto_ouro": "NENHUM"})[0], 400)
        self.assertEqual(self.chamar("POST", "/api/referencia/resposta", {"chave": "Outra|1", "ponto_ouro": CODS["A"]})[0], 400)
        self.assertEqual(self.chamar("POST", "/api/referencia/desfazer", {"chave": "Prova T|10"})[0], 400)

    def test_pagina_de_revisao_recebe_o_token(self):
        with urllib.request.urlopen(urllib.request.Request(self.base + "/revisao")) as r:
            html = r.read().decode("utf-8")
        self.assertIn("tok-rev", html)
        self.assertNotIn("__TOKEN__", html)


if __name__ == "__main__":
    unittest.main(verbosity=1)
