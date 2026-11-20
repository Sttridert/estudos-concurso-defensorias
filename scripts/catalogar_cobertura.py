#!/usr/bin/env python3
"""Grupo B (Catalogar): cobertura do EDITAL pelo rascunho v2 (só leitura; não usa questões, não grava no banco).

Uso (sempre com `python -I`):
  python -I scripts/catalogar_cobertura.py DISCIPLINA        (ex.: direito-penal; precisa de dados/catalogo/_rascunho_<DISCIPLINA>_v2.json)

Pergunta: o v2 deixa algum item de edital sem lugar, e quais tópicos do v2 ainda não têm nenhum item de edital?
Como mede: cada item de edital já está ligado a pontos do v1 (tabela `edital_item_pontos`). O mapa antigo→novo do rascunho diz
para onde cada ponto do v1 foi (mantido, movido, fundido, apagado). Seguindo o mapa, cada item cai em tópico(s) do v2 ou fica sem destino.
  1. Itens que ficam SEM tópico no v2 (a ligação do v1 foi apagada sem destino): a lista é o que o usuário precisa olhar.
     Se o ponto foi para outra disciplina (nota "migra para ..."), o item é contado à parte.
  2. Tópicos do v2 SEM item herdado: tópico novo ou dividido. É esperado (o item ainda não foi religado ao tópico novo, o que é
     da Fase 3 "religar itens"); serve para você ver quais tópicos novos não têm apoio no edital e confirmar se são cobrados.
  3. Itens que já não tinham tópico no v1 (fragmentos genéricos): só contados.
É triagem: não decide nada e não religa nada.
"""
import collections
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rascunho as R  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"


def _norm(s):
    import unicodedata
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


_GEN = set("de da do das dos a o as os e em no na nos nas para por com sobre entre ao ou penal processo processual direito lei".split())


def _palavras(nome):
    import re
    return [w for w in re.findall(r"[a-z]{4,}", _norm(nome)) if w not in _GEN]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    slug = args[0]
    d = R.carregar(slug)
    con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    disc = con.execute("select id from disciplinas where nome=?", (d["disciplina"],)).fetchone()
    if not disc:
        print(f"A disciplina '{d['disciplina']}' ainda não existe no banco (ela só entra na publicação, M6): não há item de edital para conferir.")
        return 0
    disc_id = disc[0]
    linhas = [m for m in R.mapa(d) if m["tipo"] == "ponto"]
    nota = {p["antigo"]: p.get("nota") for p in d["lixeira"] if p.get("antigo")}
    destino = {}                                  # código v1 -> código v2 (ou None) e motivo
    for m in linhas:
        if not m["antigo"]:
            continue
        if m["acao"] in ("apagado",):
            destino[m["antigo"]] = (None, nota.get(m["antigo"]) or "apagado sem destino")
        elif m["acao"] == "fundido":
            destino[m["antigo"]] = (m["destino"] or None, "fundido")
        else:
            destino[m["antigo"]] = (m["novo"], m["acao"])
    ponto_cod = dict(con.execute("select id,codigo from pontos where disciplina_id=?", (disc_id,)).fetchall())
    itens = {i: t for i, t in con.execute("select id,texto from edital_itens where disciplina_id=?", (disc_id,)).fetchall()}
    liga = collections.defaultdict(set)
    for it, pid in con.execute("select item_id,ponto_id from edital_item_pontos"):
        if it in itens and pid in ponto_cod:
            liga[it].add(ponto_cod[pid])
    if not itens:
        print(f"A disciplina '{d['disciplina']}' não tem nenhum item de edital na base (os editais carregados só trazem as disciplinas de Direito): "
              "não há como conferir cobertura nem evidência por palavras. A evidência dela virá de mais editais de outros cargos (decisão 54) ou das questões (grupo C).")
        return 0
    sem_tema_v1 = [i for i in itens if i not in liga]
    herdado = collections.Counter()               # código v2 -> itens
    perdidos, outra = [], collections.defaultdict(list)
    for it, cods in liga.items():
        fica = set()
        motivo = None
        for c in cods:
            novo, mot = destino.get(c, (None, "ponto fora do rascunho"))
            if novo:
                fica.add(novo)
            else:
                motivo = mot
        if fica:
            for n in fica:
                herdado[n] += 1
        elif motivo and motivo.startswith("migra para"):
            outra[motivo].append(it)
        else:
            perdidos.append((it, motivo))
    print(f"== COBERTURA DO EDITAL: {d['disciplina']} (rascunho v2; {len(itens)} itens de edital da disciplina; sem usar questões)\n")
    print(f"-- 1. Itens SEM tópico no v2: {len(perdidos)}")
    for it, mot in perdidos[:15]:
        print(f"   [{mot}] {itens[it][:110]}")
    if len(perdidos) > 15:
        print(f"   ... e mais {len(perdidos) - 15}")
    for mot, lst in outra.items():
        print(f"   {len(lst)} itens ficam com a outra disciplina ({mot}); exemplos: " + " | ".join(itens[i][:60] for i in lst[:3]))
    print("\n-- 2. Tópicos do v2 sem item de edital herdado (novos ou divididos; esperado até religar os itens)")
    print("   'citam' = itens de edital da disciplina cujo texto contém todas as palavras do nome do tópico (só triagem, por palavras)")
    cods = R.codigos(d)
    textos = [_norm(x) for x in itens.values()]
    n2 = sem_evid = 0
    for a in d["assuntos"]:
        for p in a["pontos"]:
            c = cods[p["uid"]]
            if not herdado.get(c):
                n2 += 1
                ps = _palavras(p["texto"])
                cit = sum(1 for x in textos if ps and all(w in x for w in ps))
                if cit == 0:
                    sem_evid += 1
                print(f"   {c} {p['texto'][:58]:58} " + ("(novo)" if not p.get("antigo") else "(do v1)") + f"  citam: {cit}" + ("   <- SEM EVIDÊNCIA POR PALAVRAS" if cit == 0 else ""))
    print(f"   -> {n2} de {sum(len(a['pontos']) for a in d['assuntos'])} tópicos sem item herdado; {sem_evid} deles sem nenhum item que cite o nome")
    print(f"\n-- 3. Itens que já não tinham tópico no v1 (fragmentos genéricos etc.): {len(sem_tema_v1)} de {len(itens)}")
    print("\nTriagem: nada foi religado nem alterado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
