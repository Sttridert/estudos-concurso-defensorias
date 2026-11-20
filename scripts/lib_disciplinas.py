"""Biblioteca do grupo B (Catalogar): fonte única das disciplinas do projeto.

Lê `dados/disciplinas.json`. Antes, o mapeamento sigla, nome e prefixo estava copiado em cinco lugares (43, 44,
coletar_programa_edital, lib_programa_edital e, em parte, 41). Disciplina nova: acrescentar uma entrada no arquivo.

  SIGLAS                  todas as siglas, na ordem do arquivo
  nome(sigla)             nome da disciplina no banco
  prefixo(sigla)          prefixo dos códigos do catálogo (ex.: PE de PE01.02)
  nomes(**filtro)         {sigla: nome}; filtro: extrair_edital_real=True/False
  prefixos()              {sigla: prefixo}
  padroes_titulo()        {sigla: [regex]} das disciplinas que se acham por título no PDF do edital
  ordem_extracao()        ordem padrão de `coletar_programa_edital.py extrair`
"""
import json
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "dados" / "disciplinas.json"
_dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
_por_sigla = {d["sigla"]: d for d in _dados["disciplinas"]}
SIGLAS = list(_por_sigla)


def nome(sigla):
    return _por_sigla[sigla]["nome"]


def prefixo(sigla):
    return _por_sigla[sigla]["prefixo"]


def nomes(**filtro):
    return {s: d["nome"] for s, d in _por_sigla.items() if all(d.get(k) == v for k, v in filtro.items())}


def prefixos():
    return {s: d["prefixo"] for s, d in _por_sigla.items()}


def padroes_titulo():
    return {s: d["padroes_titulo"] for s, d in _por_sigla.items() if d["padroes_titulo"]}


def ordem_extracao():
    return list(_dados["ordem_extracao"])
