#!/usr/bin/env python3
"""Grupo B (Catalogar): começar o catálogo de uma DISCIPLINA NOVA (sem catálogo v1) e apoiar o esqueleto com a evidência dos editais.

Uso (sempre com `python -I`):
  python -I scripts/catalogar_novo.py evidencia "palavra ..." [--provavel "Direito Tributário"] [--limite 40]
  python -I scripts/catalogar_novo.py criar SIGLA "Nome da disciplina" --prefixo XX --roteiro ARQUIVO.txt [--slug nome-sem-acento] [--padrao REGEX ...] [--simular]
  python -I scripts/catalogar_novo.py destino SLUG CODIGO_ANTIGO "Disciplina de destino" CODIGO_DESTINO     # funde um ponto do rascunho SLUG num ponto de outra disciplina

evidencia   só leitura. Lista os itens de edital (base `edital_itens`) que citam todas as palavras, ou cuja disciplina provável é a dada, com o número de
            editais que os trazem. Serve para escrever o roteiro: o esqueleto vem da estrutura da norma e da doutrina, e os itens dizem o que os editais cobram.
criar       escreve o rascunho v2 de uma disciplina NOVA a partir de um roteiro em texto (formato em lib_rascunho.ler_roteiro: `# assunto`, `- tópico | descrição`,
            e, opcionalmente, `| @Disciplina:CÓDIGO` para ADOTAR um ponto que já existe no banco), registra a disciplina em dados/disciplinas.json
            e, se o roteiro adota pontos, tira esses pontos do rascunho da disciplina de origem (que precisa existir). Não grava no banco: o banco só muda
            na publicação (scripts/catalogar_publicar.py). Depois: abrir no editor, diagnosticar (catalogar_coerencia), mostrar ao usuário.
destino     para um ponto que sai de uma disciplina e deve ser fundido em outra (o editor só aceita destino dentro do mesmo rascunho).
"""
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rascunho as R  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
DISCIPLINAS = RAIZ / "dados" / "disciplinas.json"


def slug_de(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def sem_acento(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def opcao(args, nome, multi=False):
    vals = [args[i + 1] for i, x in enumerate(args) if x == nome and i + 1 < len(args)]
    return vals if multi else (vals[0] if vals else None)


def evidencia(args):
    palavras = [sem_acento(p) for p in (args[0].split() if args and not args[0].startswith("--") else [])]
    provavel = opcao(args, "--provavel")
    limite = int(opcao(args, "--limite") or 40)
    if not palavras and not provavel:
        sys.exit("informe palavras (ex.: evidencia \"tribut\") e/ou --provavel \"Disciplina\".")
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    rows = con.execute("select texto,n_editais,n_fcc,ano_min,ano_max,disciplina_provavel from edital_itens").fetchall()
    ach = []
    for t, ne, nf, a0, a1, dp in rows:
        if palavras and not all(p in sem_acento(t) for p in palavras):
            continue
        if provavel and sem_acento(provavel) not in sem_acento(dp or ""):
            continue
        ach.append((ne or 0, nf or 0, a0, a1, t, dp or ""))
    ach.sort(key=lambda x: (-x[0], x[4]))
    print(f"{len(ach)} itens de edital" + (f" que citam: {' '.join(palavras)}" if palavras else "") + (f" (disciplina provável: {provavel})" if provavel else ""))
    print("editais | FCC | anos      | disciplina provável | texto")
    for ne, nf, a0, a1, t, dp in ach[:limite]:
        print(f"{ne:7d} | {nf:3d} | {a0 or '?'}-{a1 or '?'} | {dp[:19]:19} | {t[:110]}")
    if len(ach) > limite:
        print(f"... e mais {len(ach) - limite} (use --limite)")


def criar(args):
    if len(args) < 2:
        sys.exit(__doc__)
    sigla, nome = args[0], args[1]
    prefixo, roteiro = opcao(args, "--prefixo"), opcao(args, "--roteiro")
    slug = opcao(args, "--slug") or slug_de(nome)
    padroes = opcao(args, "--padrao", multi=True)
    simular = "--simular" in args
    if not (prefixo and roteiro):
        sys.exit("faltam --prefixo e --roteiro.")
    dados = json.loads(DISCIPLINAS.read_text(encoding="utf-8"))
    for d in dados["disciplinas"]:
        if d["sigla"] == sigla:
            sys.exit(f"a sigla {sigla} já existe em dados/disciplinas.json.")
        if d["prefixo"] == prefixo:
            sys.exit(f"o prefixo {prefixo} já é de {d['nome']}.")
        if sem_acento(d["nome"]) == sem_acento(nome):
            sys.exit(f"a disciplina '{d['nome']}' já existe; para refazer o catálogo dela use o editor (criar a partir do catálogo atual).")
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    if con.execute("select count(*) from pontos p join disciplinas di on di.id=p.disciplina_id where di.nome=?", (nome,)).fetchone()[0]:
        sys.exit(f"a disciplina '{nome}' já tem pontos no banco; use o editor a partir do catálogo atual. "
                 "(Disciplina que existe no banco só como linha, sem pontos, pode receber catálogo novo.)")
    try:
        assuntos = R.ler_roteiro(Path(roteiro).read_text(encoding="utf-8"))
        textos, origens = {}, set()
        for a in assuntos:
            for p in a["pontos"]:
                if p["adotar"]:
                    d, c = p["adotar"]["disciplina"], p["adotar"]["codigo"]
                    r = con.execute("select p.texto from pontos p join disciplinas di on di.id=p.disciplina_id where di.nome=? and p.codigo=? and p.ativo=1", (d, c)).fetchone()
                    if not r:
                        raise R.ErroOp(f"o ponto {c} de '{d}' não existe (ou está arquivado) no banco.")
                    textos[(d, c)] = r[0]
                    origens.add(d)
        for d in origens:
            if not R.existe(slug_de(d)):
                raise R.ErroOp(f"para adotar pontos de '{d}', crie antes o rascunho dela no editor (a partir do catálogo atual): ele precisa registrar a saída dos pontos.")
        total = sum(len(a["pontos"]) for a in assuntos)
        print(f"disciplina nova: {nome} (sigla {sigla}, prefixo {prefixo}, slug {slug}); {len(assuntos)} assuntos e {total} tópicos; "
              f"{sum(1 for a in assuntos for p in a['pontos'] if p['adotar'])} adotados do banco")
        if simular:
            print("(simulação: nada foi gravado)")
            return
        d = R.criar_do_zero(slug, nome, prefixo, assuntos, textos_banco=textos)
        for a in assuntos:
            for p in a["pontos"]:
                if p["adotar"]:
                    R.tirar_ponto(slug_de(p["adotar"]["disciplina"]), p["adotar"]["codigo"], movido_para=slug)
    except R.ErroOp as e:
        sys.exit(f"ERRO: {e}")
    dados["disciplinas"].append({"sigla": sigla, "nome": nome, "prefixo": prefixo, "padroes_titulo": padroes, "edital_ficticio": False, "extrair_edital_real": False})
    DISCIPLINAS.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"rascunho criado: dados/catalogo/_rascunho_{slug}_v2.json; disciplina registrada em dados/disciplinas.json.")
    print("Próximos passos: abrir no editor (python -I scripts/catalogar_editor.py --abrir), rodar catalogar_coerencia e catalogar_cobertura, "
          "mostrar ao usuário; só depois publicar (catalogar_publicar.py --simular --disciplina " + slug + ").")


def destino(args):
    if len(args) != 4:
        sys.exit(__doc__)
    slug, antigo, disc, cod = args
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    if not con.execute("select 1 from pontos p join disciplinas di on di.id=p.disciplina_id where di.nome=? and p.codigo=? and p.ativo=1", (disc, cod)).fetchone():
        sys.exit(f"o ponto {cod} de '{disc}' não existe (ou está arquivado) no banco.")
    try:
        R.tirar_ponto(slug, antigo, destino_externo={"disciplina": disc, "codigo": cod})
    except R.ErroOp as e:
        sys.exit(f"ERRO: {e}")
    print(f"{antigo} sai do rascunho '{slug}' e será fundido em {cod} ({disc}) na publicação.")


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("evidencia", "criar", "destino"):
        print(__doc__)
        return 2
    {"evidencia": evidencia, "criar": criar, "destino": destino}[a[0]](a[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
