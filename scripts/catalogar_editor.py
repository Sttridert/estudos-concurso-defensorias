#!/usr/bin/env python3
"""Grupo B (Catalogar): servidor local do EDITOR VISUAL do catálogo (API + página). A lógica está em `lib_rascunho.py`.

Uso (sempre com `python -I`):
  python -I scripts/catalogar_editor.py [--porta 8765] [--abrir] [--pasta PASTA_DE_ENSAIO] [--referencia PASTA_DE_ENSAIO]
      Sobe o servidor SÓ em 127.0.0.1 e imprime o endereço (com o token da sessão). `--abrir` também abre o navegador.
      Ctrl+C encerra. O editor mexe só em RASCUNHOS (arquivos `dados/catalogo/_rascunho_*_v2.json`); o banco é lido (só leitura) para
      mostrar quantas questões e itens cada ponto tem. Publicar o v2 é outra etapa.

Segurança: só escuta em 127.0.0.1; toda chamada da API exige o cabeçalho `X-Editor-Token` (gerado a cada execução e embutido na página) e o
cabeçalho `Host` tem de ser 127.0.0.1 ou localhost (contra páginas de outros sites e contra DNS rebinding).

REVISÃO DO CONJUNTO DE REFERÊNCIA (marco M4): a página /revisao mostra uma questão por tela para o usuário arbitrar (teclas A, B, C...). As respostas
vão para `dados/referencia/referencia_ouro.csv` com origem "usuario" (nunca grave resposta no lugar do usuário). `--referencia DIR` usa outra pasta, para ensaio.

EDITOR DE QUESTÕES (grupo C, decisão 57): a página /questoes lista as questões e edita classificação, texto, gabarito e comentário GRAVANDO DIRETO NO BANCO
(cópia diária em banco/backup, histórico por edição e desfazer; ver lib_questoes.py). `--banco ARQ` aponta para outro banco, para ensaio.

API (JSON):
  GET  /api/questoes?...                      lista com filtros (disciplina_id, prova_id, situacao, confianca, ponto, busca, migrada, sem_secundario, ...)
  GET  /api/questoes/filtros | topicos | <id> | <id>/historico
  POST /api/questoes/<id>/salvar {alteracoes, motivo} | <id>/desfazer | sincronizar (roda o `71 exportar`)
  GET  /api/catalogos                         lista os catálogos v1 e se já têm rascunho
  POST /api/rascunho/<slug>/criar             cria o rascunho a partir do catálogo v1 (corpo opcional {"sobrescrever": true})
  GET  /api/rascunho/<slug>                   visão: códigos, contagens, diagnóstico do contrato, lixeira, desfazer e refazer
  POST /api/rascunho/<slug>/op                aplica uma operação (ver lib_rascunho.OPERACOES, mais "desfazer" e "refazer")
  GET  /api/rascunho/<slug>/mapa              mapa antigo→novo
  POST /api/rascunho/<slug>/mapa/exportar     grava o CSV do mapa e devolve o caminho
  GET  /api/rascunho/<slug>/questoes?uid=...  questões do ponto (e do que foi fundido nele)
  GET  /api/rascunho/<slug>/comparacao        métricas de estrutura do v1 e do v2 lado a lado, e o resumo das mudanças
  GET  /api/rascunho/<slug>/v1                o catálogo v1 de referência (somente leitura), no formato da visão
  GET  /api/rascunho/<slug>/metricas          classificador por código com rótulos v1 e v2 (validação cruzada; leva alguns segundos)
  GET  /api/referencia/fila                   a fila de revisão (não unânimes + amostra de controle), com o texto das questões e as respostas
  GET  /api/referencia/resumo                 progresso, posição do usuário e estimativa de acerto do rótulo atual
  POST /api/referencia/resposta               {chave, ponto_ouro (código ou "NENHUM"), nota}: grava a decisão do usuário
  POST /api/referencia/desfazer               {chave}: remove a resposta
"""
import json
import re
import secrets
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rascunho as R  # noqa: E402
import lib_revisao as V  # noqa: E402
import lib_questoes as Q  # noqa: E402

PAGINA = Path(__file__).resolve().parent / "catalogar_editor.html"
PAGINA_REVISAO = Path(__file__).resolve().parent / "catalogar_revisao.html"
PAGINA_QUESTOES = Path(__file__).resolve().parent / "mapear_questoes.html"
SLUG = re.compile(r"^[a-z0-9\-]+$")


def criar_servidor(porta=8765, token=None, banco=None, referencia=None, backup=None):
    token = token or secrets.token_urlsafe(16)

    class Handler(BaseHTTPRequestHandler):
        server_version = "EditorCatalogo/1"

        def log_message(self, *args):          # sem log de acesso no terminal
            pass

        # ---------- utilitários
        def _enviar(self, codigo, corpo, tipo="application/json; charset=utf-8"):
            dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(dados)

        def _host_ok(self):
            h = (self.headers.get("Host") or "").split(":")[0].lower()
            return h in ("127.0.0.1", "localhost")

        def _autorizado(self):
            return self._host_ok() and secrets.compare_digest(self.headers.get("X-Editor-Token", ""), token)

        def _corpo(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 1_000_000:
                raise R.ErroOp("corpo grande demais.")
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

        def _slug(self, texto):
            if not SLUG.match(texto):
                raise R.ErroOp("nome de catálogo inválido.")
            return texto

        # ---------- editor de questões (grava direto no banco; ver lib_questoes)
        def _questoes_get(self, partes, q):
            um = lambda k: (q.get(k) or [""])[0]
            if len(partes) == 2:
                f = {k: um(k) for k in ("disciplina_id", "prova_id", "situacao", "confianca", "ponto", "busca") if um(k)}
                for k in ("migrada", "sem_secundario", "sem_classificacao", "comentario_confirmar", "nao_revisadas"):
                    if um(k) in ("1", "true"):
                        f[k] = True
                return self._enviar(200, Q.listar(banco, f, int(um("limite") or 100), int(um("deslocamento") or 0)))
            if partes[2] == "filtros":
                return self._enviar(200, Q.filtros_disponiveis(banco))
            if partes[2] == "topicos":
                return self._enviar(200, Q.topicos(banco))
            qid = int(partes[2]) if partes[2].isdigit() else 0
            if len(partes) == 3:
                return self._enviar(200, Q.obter(banco, qid))
            if len(partes) == 4 and partes[3] == "historico":
                return self._enviar(200, Q.historico(banco, qid))
            return self._enviar(404, {"erro": "não encontrado"})

        def _questoes_post(self, partes):
            if len(partes) == 3 and partes[2] == "sincronizar":
                if banco is not None:
                    raise Q.ErroQuestao("a sincronização só vale para o banco real.")
                r = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve().parent / "71_catalogo_e_classificacao.py"), "exportar"],
                                   capture_output=True, text=True, cwd=str(R.RAIZ))
                if r.returncode != 0:
                    raise Q.ErroQuestao("a exportação falhou: " + (r.stderr or r.stdout)[-300:])
                return self._enviar(200, {"saida": r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "ok"})
            if len(partes) == 4 and partes[2].isdigit():
                qid = int(partes[2])
                if partes[3] == "salvar":
                    c = self._corpo()
                    return self._enviar(200, Q.salvar(banco, qid, c.get("alteracoes") or {}, c.get("motivo", ""), pasta_backup=backup))
                if partes[3] == "desfazer":
                    self._corpo()
                    return self._enviar(200, Q.desfazer(banco, qid, pasta_backup=backup))
            return self._enviar(404, {"erro": "não encontrado"})

        # ---------- rotas
        def do_GET(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                if not self._host_ok():
                    return self._enviar(403, {"erro": "host não permitido"})
                html = PAGINA.read_text(encoding="utf-8").replace("__TOKEN__", token) if PAGINA.exists() else "<p>página do editor ainda não existe</p>"
                return self._enviar(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if u.path == "/revisao":
                if not self._host_ok():
                    return self._enviar(403, {"erro": "host não permitido"})
                html = PAGINA_REVISAO.read_text(encoding="utf-8").replace("__TOKEN__", token) if PAGINA_REVISAO.exists() else "<p>página de revisão ainda não existe</p>"
                return self._enviar(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if u.path == "/questoes":
                if not self._host_ok():
                    return self._enviar(403, {"erro": "host não permitido"})
                html = PAGINA_QUESTOES.read_text(encoding="utf-8").replace("__TOKEN__", token) if PAGINA_QUESTOES.exists() else "<p>página do editor de questões ainda não existe</p>"
                return self._enviar(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if not u.path.startswith("/api/"):
                return self._enviar(404, {"erro": "não encontrado"})
            if not self._autorizado():
                return self._enviar(403, {"erro": "acesso negado"})
            try:
                partes = u.path.strip("/").split("/")          # api, catalogos | api, rascunho, slug, [acao] | api, referencia, fila|resumo
                if partes[1] == "catalogos":
                    return self._enviar(200, R.catalogos_disponiveis())
                if partes[1] == "questoes":
                    return self._questoes_get(partes, parse_qs(u.query))
                if partes[1] == "referencia" and len(partes) == 3:
                    if partes[2] == "fila":
                        itens = V.montar_fila(referencia, banco)
                        return self._enviar(200, {"itens": itens, "progresso": V.progresso(itens)})
                    if partes[2] == "resumo":
                        return self._enviar(200, V.resumo(referencia, banco))
                if partes[1] == "rascunho" and len(partes) >= 3:
                    slug = self._slug(partes[2])
                    d = R.carregar(slug)
                    if len(partes) == 3:
                        return self._enviar(200, R.visao(d, banco))
                    if partes[3] == "mapa":
                        return self._enviar(200, R.mapa(d))
                    if partes[3] == "comparacao":
                        return self._enviar(200, R.comparacao(d, banco))
                    if partes[3] == "v1":
                        return self._enviar(200, R.visao_v1(d, banco))
                    if partes[3] == "metricas":
                        return self._enviar(200, R.metricas_classificacao(d, banco))
                    if partes[3] == "questoes":
                        uid = (parse_qs(u.query).get("uid") or [""])[0]
                        return self._enviar(200, R.questoes_do_ponto(d, uid, banco))
                return self._enviar(404, {"erro": "não encontrado"})
            except (R.ErroOp, V.ErroRevisao, Q.ErroQuestao) as e:
                return self._enviar(400, {"erro": str(e)})

        def do_POST(self):
            if not self.path.startswith("/api/"):
                return self._enviar(404, {"erro": "não encontrado"})
            if not self._autorizado():
                return self._enviar(403, {"erro": "acesso negado"})
            try:
                partes = urlparse(self.path).path.strip("/").split("/")
                if partes[1] == "questoes":
                    return self._questoes_post(partes)
                if partes[1] == "referencia" and len(partes) == 3:
                    corpo = self._corpo()
                    if partes[2] == "resposta":
                        r = V.registrar_resposta(corpo.get("chave", ""), corpo.get("ponto_ouro", ""), corpo.get("nota", ""), referencia, banco)
                        return self._enviar(200, {"resposta": r, "progresso": V.resumo(referencia, banco)["fila"]})
                    if partes[2] == "desfazer":
                        V.desfazer_resposta(corpo.get("chave", ""), referencia)
                        return self._enviar(200, {"progresso": V.resumo(referencia, banco)["fila"]})
                if partes[1] == "rascunho" and len(partes) >= 4:
                    slug = self._slug(partes[2])
                    if partes[3] == "criar":
                        d = R.criar_de_v1(slug, sobrescrever=bool(self._corpo().get("sobrescrever")))
                        return self._enviar(200, R.visao(d, banco))
                    if partes[3] == "op":
                        d = R.aplicar_op(slug, self._corpo(), banco)
                        return self._enviar(200, R.visao(d, banco))
                    if partes[3] == "mapa" and len(partes) == 5 and partes[4] == "exportar":
                        arq = R.exportar_mapa(R.carregar(slug))
                        return self._enviar(200, {"arquivo": str(arq.relative_to(R.RAIZ)) if str(arq).startswith(str(R.RAIZ)) else str(arq)})
                return self._enviar(404, {"erro": "não encontrado"})
            except (R.ErroOp, V.ErroRevisao, Q.ErroQuestao) as e:
                return self._enviar(400, {"erro": str(e)})
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._enviar(400, {"erro": "corpo inválido (JSON esperado)"})

    srv = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    srv.token = token
    return srv


def main():
    a = sys.argv[1:]
    porta = int(a[a.index("--porta") + 1]) if "--porta" in a else 8765
    if "--pasta" in a:                      # ensaio: lê os catálogos v1 e grava os rascunhos em outra pasta (os dados reais ficam intactos)
        R.PASTA = Path(a[a.index("--pasta") + 1]).resolve()
        print(f"ENSAIO: catálogos e rascunhos em {R.PASTA}")
    banco = Path(a[a.index("--banco") + 1]).resolve() if "--banco" in a else None
    if banco:
        print(f"ENSAIO: banco {banco}")
    referencia = Path(a[a.index("--referencia") + 1]).resolve() if "--referencia" in a else None
    if referencia:
        print(f"ENSAIO: respostas da revisão em {referencia}")
    if not banco:
        copia = Q.backup_do_dia()
        if copia:
            print(f"cópia do dia do banco: {copia.name}")
    srv = criar_servidor(porta, banco=banco, referencia=referencia, backup=(banco.parent / "backup_ensaio") if banco else None)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Editor do catálogo em {url}  (somente neste computador; Ctrl+C encerra)")
    print(f"Editor de questões em {url}questoes  (grava direto no banco)")
    if "--abrir" in a:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrado.")


if __name__ == "__main__":
    main()
