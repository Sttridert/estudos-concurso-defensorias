"""Biblioteca do grupo B (Catalogar): estado do catálogo de cada disciplina (provisório ou fechado).

O estado mora em `dados/catalogo/_estado.json` (o `_` no começo impede que o `71 aplicar` o trate como catálogo). Um registro por disciplina
(chave = nome do arquivo de catálogo sem extensão, ex.: `execucao-penal`):

  estado             "provisorio" ou "fechado"
  versao             "v1", "v2"... (muda quando o catálogo é refeito; ver o mapa antigo→novo em `_mapa_<disciplina>_<vA>_<vB>.csv`)
  data               data do último registro de estado
  editais_usados     universo de editais que fundamentou o catálogo (id em `dados/universos_editais.json` e quantos editais)
  riscos             lista de riscos conhecidos (o que pode estar errado ou incompleto)
  fechado_pelo_usuario_em   data em que o usuário disse "sim" (só para "fechado")
  historico          lista de {data, de, para, motivo}

Catálogo FECHADO: o `71 aplicar` só aceita ACRÉSCIMO (assunto ou ponto novo); qualquer mudança em linha existente (nome, descrição, assunto de um
ponto, `ativo`) é recusada. Para mudar o que já existe: reabrir o catálogo (`71 estado definir <disciplina> provisorio --motivo ...`), com o mapa
antigo→novo registrado e o "sim" do usuário.
"""
import json
import datetime
from pathlib import Path

CAT = Path(__file__).resolve().parent.parent / "dados" / "catalogo"
ARQUIVO = CAT / "_estado.json"
ESTADOS = ("provisorio", "fechado")


def catalogos():
    """Nomes (sem extensão) dos arquivos de catálogo, sem os de apoio (que começam com `_`)."""
    return sorted(p.stem for p in CAT.glob("*.json") if not p.name.startswith("_"))


def carregar():
    if ARQUIVO.exists():
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    return {}


def salvar(dados):
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def estado_de(slug, dados=None):
    """Estado de uma disciplina; sem registro conta como provisório."""
    d = (dados if dados is not None else carregar()).get(slug)
    return d["estado"] if d else "provisorio"


def esta_fechado(slug, dados=None):
    return estado_de(slug, dados) == "fechado"


def definir(slug, novo, motivo, versao=None, editais=None, riscos=None, confirmado_pelo_usuario=False):
    """Muda o estado de um catálogo. Fechar exige `confirmado_pelo_usuario` (só depois do "sim" do usuário no chat)."""
    if novo not in ESTADOS:
        raise SystemExit(f"estado deve ser um de {ESTADOS}")
    if slug not in catalogos():
        raise SystemExit(f"não há catálogo '{slug}'. Existem: {', '.join(catalogos())}")
    if novo == "fechado" and not confirmado_pelo_usuario:
        raise SystemExit("Fechar um catálogo só depois do \"sim\" do usuário: repita com --sim-do-usuario.")
    dados = carregar()
    hoje = datetime.date.today().isoformat()
    atual = dados.get(slug, {"estado": "provisorio", "versao": "v1", "editais_usados": None, "riscos": [], "historico": []})
    atual["historico"].append({"data": hoje, "de": atual["estado"], "para": novo, "motivo": motivo})
    atual["estado"] = novo
    atual["data"] = hoje
    if versao:
        atual["versao"] = versao
    if editais:
        atual["editais_usados"] = editais
    if riscos:
        atual["riscos"] = riscos
    if novo == "fechado":
        atual["fechado_pelo_usuario_em"] = hoje
    else:
        atual.pop("fechado_pelo_usuario_em", None)
    dados[slug] = atual
    salvar(dados)
    return atual
