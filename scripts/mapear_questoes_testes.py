#!/usr/bin/env python3
"""Testes do editor de questões (lib_questoes). Rodar: python -I scripts/mapear_questoes_testes.py
Usam banco e pasta de backup TEMPORÁRIOS, com o esquema real das tabelas; o banco real só é lido para copiar o esquema."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_questoes as Q  # noqa: E402

TABELAS = ("disciplinas", "assuntos", "pontos", "provas", "questoes", "classificacao", "comentarios", "log_alteracoes")


def criar_banco(caminho):
    real = sqlite3.connect(f"file:{Q.BANCO}?mode=ro", uri=True)
    ddl = {n: s for n, s in real.execute("select name,sql from sqlite_master where type='table'") if n in TABELAS}
    real.close()
    con = sqlite3.connect(caminho)
    for t in TABELAS:
        con.execute(ddl[t])
    c = con.execute
    c("insert into disciplinas(id,nome) values(1,'Disc A'),(2,'Disc B')")
    c("insert into assuntos(id,disciplina_id,codigo,nome) values(1,1,'AA01','Assunto A'),(2,2,'BB01','Assunto B')")
    c("insert into pontos(id,disciplina_id,assunto_id,codigo,texto,ativo) values(1,1,1,'AA01.01','Ponto 1',1),(2,1,1,'AA01.02','Ponto 2',1),"
      "(3,1,1,'AA01.03','Ponto inativo',0),(4,2,2,'BB01.01','Ponto de B',1)")
    c("insert into provas(id,nome,ano,banca,cargo) values(1,'2020 - Prova X',2020,'FCC','Cargo'),(2,'2021 - Prova Y',2021,'FCC','Cargo')")
    c("insert into questoes(id,prova_id,numero,disciplina_id,disciplina_original,enunciado,alt_a,alt_b,alt_c,alt_d,alt_e,gabarito,situacao,revisada) values"
      "(1,1,1,1,'Disc A','enunciado um','a1','b1','c1','d1','e1','A','valida',0),"
      "(2,1,2,1,'Disc A','enunciado dois','a2','b2','c2','d2','e2','B','revisar_texto',0),"
      "(3,2,1,2,'Disc B','outro texto tres','a3','b3','c3','d3','e3','C','valida',0),"
      "(4,2,2,1,'Disc A','sem classificacao','a4','b4','c4','d4','e4','D','valida',0)")
    c("insert into classificacao(questao_id,ponto_id,ponto2_id,detalhe,tipo_cobranca,origem,confianca,revisada,atualizado_em) values"
      "(1,1,NULL,'det1','lei_seca','IA (rascunho) | migrada v1 para v2','media',0,'2026-01-01'),"
      "(2,1,2,'det2','jurisprudencia','IA (rascunho)','alta',0,'2026-01-01'),"
      "(3,4,NULL,'det3','lei_seca','IA (rascunho)','baixa',0,'2026-01-01')")
    c("insert into comentarios(questao_id,texto,pegadinha,dispositivos,estado,pendente_confirmacao,autor,atualizado_em) values"
      "(1,'coment um','peg','art 1','rascunho',1,'IA (Claude)','2026-01-01'),(2,'coment dois','','','rascunho',0,'IA (Claude)','2026-01-01')")
    con.commit()
    con.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.banco = self.pasta / "t.db"
        self.bkp = self.pasta / "bkp"
        criar_banco(self.banco)

    def tearDown(self):
        shutil.rmtree(self.pasta, ignore_errors=True)

    def sql(self, q, *p):
        con = sqlite3.connect(self.banco)
        try:
            return con.execute(q, p).fetchall()
        finally:
            con.close()

    def salvar(self, qid, alt, motivo=""):
        return Q.salvar(self.banco, qid, alt, motivo, pasta_backup=self.bkp)

    def desfazer(self, qid):
        return Q.desfazer(self.banco, qid, pasta_backup=self.bkp)


class TestLeitura(Base):
    def test_listar_total_e_filtros(self):
        self.assertEqual(Q.listar(self.banco)["total"], 4)
        self.assertEqual(Q.listar(self.banco, {"disciplina_id": 2})["total"], 1)
        self.assertEqual([i["id"] for i in Q.listar(self.banco, {"migrada": True})["itens"]], [1])
        self.assertEqual([i["id"] for i in Q.listar(self.banco, {"sem_secundario": True})["itens"]], [1, 3])
        self.assertEqual([i["id"] for i in Q.listar(self.banco, {"sem_classificacao": True})["itens"]], [4])
        self.assertEqual([i["id"] for i in Q.listar(self.banco, {"comentario_confirmar": True})["itens"]], [1])
        self.assertEqual([i["id"] for i in Q.listar(self.banco, {"confianca": "baixa"})["itens"]], [3])
        self.assertEqual([i["id"] for i in Q.listar(self.banco, {"situacao": "revisar_texto"})["itens"]], [2])
        self.assertEqual([i["id"] for i in Q.listar(self.banco, {"busca": "tres"})["itens"]], [3])
        self.assertEqual(sorted(i["id"] for i in Q.listar(self.banco, {"ponto": "AA01.02"})["itens"]), [2])   # secundário também conta

    def test_listar_paginacao(self):
        r = Q.listar(self.banco, {}, limite=2, deslocamento=2)
        self.assertEqual((r["total"], len(r["itens"])), (4, 2))

    def test_obter(self):
        q = Q.obter(self.banco, 2)
        self.assertEqual((q["gabarito"], q["situacao"], q["classificacao"]["ponto"], q["classificacao"]["ponto2"]), ("B", "revisar_texto", "AA01.01", "AA01.02"))
        self.assertEqual(q["comentario"]["estado"], "rascunho")
        with self.assertRaises(Q.ErroQuestao):
            Q.obter(self.banco, 99)

    def test_topicos_so_ativos(self):
        cods = [p["codigo"] for d in Q.topicos(self.banco) for a in d["assuntos"] for p in a["pontos"]]
        self.assertEqual(sorted(cods), ["AA01.01", "AA01.02", "BB01.01"])


class TestClassificacao(Base):
    def test_editar_grava_origem_usuario_historico_e_log(self):
        r = self.salvar(1, {"classificacao": {"ponto": "AA01.02", "ponto2": "AA01.01"}})
        self.assertTrue(r["mudou"])
        c = r["questao"]["classificacao"]
        self.assertEqual((c["ponto"], c["ponto2"], c["origem"], c["revisada"]), ("AA01.02", "AA01.01", "usuario", 0))
        self.assertEqual(self.sql("select count(*) from historico_edicoes where questao_id=1")[0][0], 1)
        self.assertEqual(self.sql("select count(*) from log_alteracoes where quem='editor de questões'")[0][0], 1)

    def test_sem_mudanca_nao_grava(self):
        r = self.salvar(1, {"classificacao": {"ponto": "AA01.01"}})
        self.assertFalse(r["mudou"])
        self.assertEqual(self.sql("select count(*) from historico_edicoes")[0][0], 0)
        self.assertEqual(Q.obter(self.banco, 1)["classificacao"]["origem"], "IA (rascunho) | migrada v1 para v2")

    def test_classificar_questao_sem_classificacao(self):
        r = self.salvar(4, {"classificacao": {"ponto": "AA01.01", "tipo_cobranca": "lei_seca", "confianca": "alta"}})
        self.assertEqual(r["questao"]["classificacao"]["ponto"], "AA01.01")
        self.desfazer(4)
        self.assertIsNone(Q.obter(self.banco, 4)["classificacao"])

    def test_validacoes(self):
        for alt, msg in (({"classificacao": {"ponto": "AA01.01", "ponto2": "AA01.01"}}, "diferentes"),
                         ({"classificacao": {"ponto": "AA01.03"}}, "inativo"),
                         ({"classificacao": {"ponto": "XX99.99"}}, "não existe"),
                         ({"classificacao": {"ponto": ""}}, "obrigat"),
                         ({"classificacao": {"ponto": "AA01.01", "confianca": "enorme"}}, "confiança")):
            with self.assertRaises(Q.ErroQuestao) as e:
                self.salvar(1, alt)
            self.assertIn(msg, str(e.exception))
        self.assertEqual(self.sql("select count(*) from historico_edicoes")[0][0], 0)

    def test_tudo_ou_nada(self):
        with self.assertRaises(Q.ErroQuestao):
            self.salvar(1, {"texto": {"enunciado": "NOVO"}, "classificacao": {"ponto": "AA01.03"}})
        self.assertEqual(Q.obter(self.banco, 1)["enunciado"], "enunciado um")
        self.assertEqual(self.sql("select count(*) from historico_edicoes")[0][0], 0)


class TestTextoGabarito(Base):
    def test_editar_texto_e_desfazer(self):
        self.salvar(1, {"texto": {"enunciado": "ENUNCIADO NOVO", "alt_c": "c novo"}})
        q = Q.obter(self.banco, 1)
        self.assertEqual((q["enunciado"], q["alt_c"]), ("ENUNCIADO NOVO", "c novo"))
        self.desfazer(1)
        q = Q.obter(self.banco, 1)
        self.assertEqual((q["enunciado"], q["alt_c"]), ("enunciado um", "c1"))

    def test_campo_invalido(self):
        with self.assertRaises(Q.ErroQuestao):
            self.salvar(1, {"texto": {"gabarito": "X"}})

    def test_gabarito_exige_motivo_e_valor_valido(self):
        with self.assertRaises(Q.ErroQuestao):
            self.salvar(1, {"gabarito": "C"})
        with self.assertRaises(Q.ErroQuestao):
            self.salvar(1, {"gabarito": "Z"}, "motivo")
        self.assertEqual(Q.obter(self.banco, 1)["gabarito"], "A")
        r = self.salvar(1, {"gabarito": "C"}, "conferido na prova original")
        self.assertEqual(r["questao"]["gabarito"], "C")
        h = Q.historico(self.banco, 1)
        self.assertEqual((h[0]["campo"], h[0]["antes"], h[0]["depois"], h[0]["motivo"]), ("gabarito", "A", "C", "conferido na prova original"))

    def test_gabarito_nao_muda_situacao_da_prova(self):
        antes = self.sql("select count(*) from provas")[0][0]
        self.salvar(1, {"gabarito": "B"}, "x")
        self.assertEqual(self.sql("select count(*) from provas")[0][0], antes)


class TestComentario(Base):
    def test_editar_confere_e_zera_pendencia(self):
        self.salvar(1, {"comentario": {"texto": "comentário novo"}})
        c = Q.obter(self.banco, 1)["comentario"]
        self.assertEqual((c["texto"], c["estado"], c["pendente_confirmacao"], c["pegadinha"]), ("comentário novo", "conferido", 0, "peg"))
        self.desfazer(1)
        c = Q.obter(self.banco, 1)["comentario"]
        self.assertEqual((c["texto"], c["estado"], c["pendente_confirmacao"]), ("coment um", "rascunho", 1))

    def test_criar_comentario_e_desfazer_apaga(self):
        self.salvar(4, {"comentario": {"texto": "novo"}})
        self.assertEqual(Q.obter(self.banco, 4)["comentario"]["autor"], "usuario")
        self.desfazer(4)
        self.assertIsNone(Q.obter(self.banco, 4)["comentario"])

    def test_campo_invalido(self):
        with self.assertRaises(Q.ErroQuestao):
            self.salvar(1, {"comentario": {"estado": "ok"}})

    def test_sem_mudanca_nao_confere(self):
        r = self.salvar(1, {"comentario": {"texto": "coment um"}})
        self.assertFalse(r["mudou"])
        self.assertEqual(Q.obter(self.banco, 1)["comentario"]["estado"], "rascunho")


class TestRevisao(Base):
    def test_marcar_revisada(self):
        r = self.salvar(2, {"marcar_revisada": True})
        q = r["questao"]
        self.assertEqual((q["revisada"], q["situacao"], q["classificacao"]["revisada"], q["classificacao"]["origem"]), (True, "valida", 1, "usuario"))
        self.desfazer(2)
        q = Q.obter(self.banco, 2)
        self.assertEqual((q["revisada"], q["situacao"], q["classificacao"]["revisada"], q["classificacao"]["origem"]), (False, "revisar_texto", 0, "IA (rascunho)"))

    def test_editar_nao_marca_revisada_sozinho(self):
        q = self.salvar(2, {"texto": {"enunciado": "x"}})["questao"]
        self.assertEqual((q["revisada"], q["situacao"]), (False, "revisar_texto"))

    def test_marcar_questao_sem_classificacao(self):
        q = self.salvar(4, {"marcar_revisada": True})["questao"]
        self.assertTrue(q["revisada"])
        self.assertIsNone(q["classificacao"])


class TestDesfazer(Base):
    def test_desfaz_so_o_ultimo_lote(self):
        self.salvar(1, {"texto": {"enunciado": "um"}})
        self.salvar(1, {"texto": {"enunciado": "dois"}})
        self.desfazer(1)
        self.assertEqual(Q.obter(self.banco, 1)["enunciado"], "um")
        self.desfazer(1)
        self.assertEqual(Q.obter(self.banco, 1)["enunciado"], "enunciado um")
        with self.assertRaises(Q.ErroQuestao):
            self.desfazer(1)

    def test_recusa_se_mudou_por_fora(self):
        self.salvar(1, {"texto": {"enunciado": "um"}})
        self.sql("update questoes set enunciado='mexido por fora' where id=1")
        con = sqlite3.connect(self.banco); con.execute("update questoes set enunciado='mexido por fora' where id=1"); con.commit(); con.close()
        with self.assertRaises(Q.ErroQuestao):
            self.desfazer(1)
        self.assertEqual(Q.obter(self.banco, 1)["enunciado"], "mexido por fora")

    def test_desfazer_classificacao_restaura_tudo(self):
        self.salvar(1, {"classificacao": {"ponto": "AA01.02", "ponto2": "AA01.01", "confianca": "baixa", "detalhe": "novo"}})
        self.desfazer(1)
        c = Q.obter(self.banco, 1)["classificacao"]
        self.assertEqual((c["ponto"], c["ponto2"], c["confianca"], c["detalhe"], c["origem"], c["atualizado_em"]),
                         ("AA01.01", None, "media", "det1", "IA (rascunho) | migrada v1 para v2", "2026-01-01"))


class TestBackup(Base):
    def test_uma_copia_por_dia(self):
        p = Q.backup_do_dia(self.banco, self.bkp)
        self.assertTrue(p and p.exists())
        self.assertIsNone(Q.backup_do_dia(self.banco, self.bkp))
        self.salvar(1, {"texto": {"enunciado": "z"}})
        self.assertEqual(len(list(self.bkp.glob("*.db"))), 1)


class TestApi(Base):
    """As rotas /api/questoes do servidor do editor (servidor real em porta livre, banco temporário)."""

    def setUp(self):
        super().setUp()
        import http.client
        import json
        import threading
        import catalogar_editor as E
        self.http, self.json = http.client, json
        self.srv = E.criar_servidor(0, token="tok", banco=self.banco, backup=self.bkp)
        self.porta = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def req(self, metodo, caminho, corpo=None, token="tok", host=None):
        c = self.http.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        h = {"X-Editor-Token": token}
        if host:
            h["Host"] = host
        c.request(metodo, caminho, body=self.json.dumps(corpo) if corpo is not None else None, headers=h)
        r = c.getresponse()
        dados = r.read()
        c.close()
        try:
            return r.status, self.json.loads(dados)
        except ValueError:
            return r.status, dados

    def test_sem_token_ou_host_estranho_recusa(self):
        self.assertEqual(self.req("GET", "/api/questoes", token="errado")[0], 403)
        self.assertEqual(self.req("GET", "/api/questoes", host="outro.site")[0], 403)
        self.assertEqual(self.req("POST", "/api/questoes/1/salvar", {"alteracoes": {"gabarito": "B"}}, token="errado")[0], 403)
        self.assertEqual(Q.obter(self.banco, 1)["gabarito"], "A")

    def test_listar_obter_filtrar(self):
        st, r = self.req("GET", "/api/questoes?disciplina_id=2")
        self.assertEqual((st, r["total"]), (200, 1))
        st, r = self.req("GET", "/api/questoes?migrada=1")
        self.assertEqual([i["id"] for i in r["itens"]], [1])
        st, q = self.req("GET", "/api/questoes/2")
        self.assertEqual((st, q["classificacao"]["ponto2"]), (200, "AA01.02"))
        self.assertEqual(self.req("GET", "/api/questoes/99")[0], 400)
        self.assertEqual(self.req("GET", "/api/questoes/filtros")[1]["situacoes"][0], "valida")
        self.assertEqual(len(self.req("GET", "/api/questoes/topicos")[1]), 2)

    def test_salvar_historico_e_desfazer(self):
        st, r = self.req("POST", "/api/questoes/1/salvar", {"alteracoes": {"classificacao": {"ponto": "AA01.02"}, "marcar_revisada": True}})
        self.assertEqual((st, r["questao"]["classificacao"]["ponto"], r["questao"]["revisada"]), (200, "AA01.02", True))
        st, h = self.req("GET", "/api/questoes/1/historico")
        self.assertEqual(st, 200)
        self.assertTrue(h)
        st, r = self.req("POST", "/api/questoes/1/desfazer", {})
        self.assertEqual((st, r["questao"]["classificacao"]["ponto"], r["questao"]["revisada"]), (200, "AA01.01", False))

    def test_erro_de_validacao_vira_400_e_nada_grava(self):
        st, r = self.req("POST", "/api/questoes/1/salvar", {"alteracoes": {"gabarito": "B"}})
        self.assertEqual(st, 400)
        self.assertIn("motivo", r["erro"])
        self.assertEqual(Q.obter(self.banco, 1)["gabarito"], "A")

    def test_ensaio_usa_a_pasta_de_backup_do_ensaio(self):
        self.req("POST", "/api/questoes/1/salvar", {"alteracoes": {"texto": {"enunciado": "x"}}})
        self.assertEqual(len(list(self.bkp.glob("*.db"))), 1)

    def test_sincronizar_so_no_banco_real(self):
        self.assertEqual(self.req("POST", "/api/questoes/sincronizar", {})[0], 400)

    def test_pagina_questoes_recebe_o_token(self):
        c = self.http.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        c.request("GET", "/questoes")
        r = c.getresponse()
        corpo = r.read().decode("utf-8")
        c.close()
        self.assertEqual(r.status, 200)
        self.assertNotIn("__TOKEN__", corpo)
        self.assertIn("Editor de questões", corpo)
        self.assertIn('const TOKEN = "tok"', corpo)


if __name__ == "__main__":
    unittest.main(verbosity=1)
