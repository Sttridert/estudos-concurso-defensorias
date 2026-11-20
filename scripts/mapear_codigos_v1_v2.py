#!/usr/bin/env python3
"""Grupo C (Mapear): traduz os códigos de tópico do catálogo v1 para o v2 nos arquivos de decisão dos editais reais.

Por quê: a publicação do v2 (20/11/2026) manteve o id de cada tópico mas mudou o código. O banco foi remapeado pelo id,
mas `dados/editais_reais/<slug>/decisoes.txt` (e o artefato derivado) seguem com códigos do v1. Rodar `51` e `52` assim
gravaria destinos errados. Este script constrói o mapa v1 -> v2 pelo ID (cópia do banco de antes da publicação x banco atual).

Uso (só leitura; não grava nada em `dados/` nem no banco):
  python -I scripts/mapear_codigos_v1_v2.py mapa                       # mostra o mapa, com os casos sem destino automático
  python -I scripts/mapear_codigos_v1_v2.py traduzir <slug> [--saida ARQ]
        # lê decisoes.txt, traduz os códigos e grava ARQ (padrão: scripts temporário em decisoes_v2_proposta.txt na pasta do edital);
        # o decisoes.txt original NÃO é alterado. Lista o que ficou para decisão do usuário.

Regras do mapa:
- Tópico mantido (mesmo id): vale o código atual, mesmo que o sentido tenha mudado (o usuário confere no `53`).
- Tópico fundido (arquivado com sufixo #v1): vale o destino do rascunho v2 (campo `destino`), se estiver no mesmo rascunho.
- Os demais (migrados para outra disciplina etc.) ficam como "MANUAL": o script não adivinha.
"""
import json, re, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
ANTES = RAIZ / "banco" / "backup" / "estudos_antes_publicar_v2_2026-11-20.db"
COD = re.compile(r"\b([A-Z]{2}\d{2}(?:\.\d{2})?)\b")


def abrir(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def montar_mapa():
    """-> (mapa {codigo_v1: codigo_v2}, manual {codigo_v1: motivo}, tema {codigo_assunto_v1: [codigos v2 de tópicos do assunto]})"""
    v1 = abrir(ANTES); v2 = abrir(BANCO)
    atual = {i: (c, a) for i, c, a in v2.execute("select id,codigo,ativo from pontos")}
    antigo = {i: c for i, c in v1.execute("select id,codigo from pontos")}
    por_uid = {}
    for arq in RAIZ.glob("dados/catalogo/_rascunho_*_v2.json"):
        d = json.loads(arq.read_text(encoding="utf-8"))
        for x in d["lixeira"]:
            por_uid[x["uid"]] = x
    mapa, manual = {}, {}
    for i, c1 in antigo.items():
        if i not in atual:
            manual[c1] = "ponto não existe mais no banco"; continue
        c2, ativo = atual[i]
        if ativo:
            mapa[c1] = c2; continue
        x = por_uid.get("v1:" + c1)
        dest = x.get("destino") if x else None
        if dest and dest.startswith("v1:") and dest[3:] in antigo.values():
            alvo = {v: k for k, v in antigo.items()}[dest[3:]]
            if atual[alvo][1]:
                mapa[c1] = atual[alvo][0]; continue
        manual[c1] = (x.get("nota") if x else None) or "arquivado sem destino automático"
    # tema (assunto) v1 -> tópicos v2 dos pontos que estavam nele
    tema = {}
    for i, c1 in antigo.items():
        if c1 in mapa:
            tema.setdefault(c1.split(".")[0], []).append(mapa[c1])
    return mapa, manual, tema


def cmd_mapa():
    mapa, manual, _ = montar_mapa()
    mudou = {a: b for a, b in mapa.items() if a != b}
    print(f"{len(mapa)} códigos com destino automático ({len(mudou)} mudaram de código, {len(mapa) - len(mudou)} iguais); {len(manual)} sem destino automático:")
    for c, m in sorted(manual.items()):
        print(f"  MANUAL {c}: {m}")


def dedup(linha):
    """Fusões do v2 podem levar dois códigos de um mesmo grupo ao mesmo tópico: o principal fica, o repetido sai."""
    esq, dir_ = linha.split("=>", 1)
    grupos = []
    for g in re.split(r"\s\|\s", dir_):
        t = re.search(r'@"[^"]*"\s*$', g)
        trecho = t.group(0) if t else ""
        vistos, toks = set(), []
        for tok in (g[:t.start()] if t else g).split():
            base = tok.lstrip("+")
            if base in vistos:
                continue
            vistos.add(base); toks.append(tok)
        grupos.append(" ".join(toks) + (" " + trecho if trecho else ""))
    return esq + "=> " + " | ".join(x.strip() for x in grupos).strip()


def cmd_traduzir(slug, saida):
    pasta = RAIZ / "dados" / "editais_reais" / slug
    mapa, manual, tema = montar_mapa()
    linhas = (pasta / "decisoes.txt").read_text(encoding="utf-8").splitlines()
    novas, pend, trad, exp = [], [], 0, []
    for n, linha in enumerate(linhas, 1):
        corpo, _, coment = linha.partition("  #")
        if not corpo.strip() or corpo.lstrip().startswith("#") or corpo.startswith(("CONFIRMADO ", "NOVO ")):
            novas.append(linha); continue
        # trechos entre aspas são texto literal do edital: não traduzir
        partes = re.split(r'(@"[^"]*")', corpo)
        for k, p in enumerate(partes):
            if p.startswith('@"'):
                continue
            if corpo.startswith("COBRE ") or corpo.startswith("FORA "):
                pass
            def sub(m):
                nonlocal trad
                c = m.group(1)
                if "." in c:
                    if c in mapa:
                        trad += c != mapa[c]; return mapa[c]
                    if c in manual:
                        pend.append((n, c, manual[c])); return f"<<MANUAL:{c}>>"
                    return c            # não é código de tópico do catálogo (ex.: um sigla de frase)
                if c in tema and corpo.startswith("COBRE "):   # tema inteiro: vira os tópicos v2 dos tópicos que o tema tinha no v1
                    exp.append((n, c, len(tema[c]))); return " ".join(sorted(tema[c]))
                return c
            partes[k] = COD.sub(sub, p)
        texto = "".join(partes)
        if "=>" in texto and not texto.startswith(("COBRE ", "FORA ")):
            texto = dedup(texto)
        novas.append(texto + (("  #" + coment) if coment else ""))
    novas.insert(0, "VERSAO_CATALOGO v2")
    saida = Path(saida) if saida else pasta / "decisoes_v2_proposta.txt"
    saida.write_text("\n".join(novas) + "\n", encoding="utf-8")
    print(f"{trad} códigos traduzidos; {len(pend)} ocorrências para decisão do usuário; gravado em {saida} (o decisoes.txt original não foi tocado)")
    if exp:
        print(f"{len(exp)} temas do COBRE foram expandidos para os tópicos que já tinham no v1 (tópicos NOVOS do v2 dentro do tema NÃO entram; conferir):")
        for n, c, k in exp:
            print(f"  linha {n}: {c} -> {k} tópicos")
    for n, c, m in pend[:60]:
        print(f"  linha {n}: {c} — {m}")


def main():
    a = sys.argv[1:]
    if a[:1] == ["mapa"]:
        return cmd_mapa()
    if a[:1] == ["traduzir"] and len(a) >= 2:
        s = a[a.index("--saida") + 1] if "--saida" in a else None
        return cmd_traduzir(a[1], s)
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
