#!/usr/bin/env python3
"""Grupo B (Catalogar), Fase 4: coerência ENTRE disciplinas (só leitura; lê todos os `dados/catalogo/_rascunho_*_v2.json`; não usa banco nem questões).

Uso (sempre com `python -I`):
  python -I scripts/catalogar_entre_disciplinas.py

Confere, sobre os rascunhos v2 (decisão 55: tema interdisciplinar pode ter tópico em mais de uma disciplina, marcado "[Tema compartilhado com X]"):
  A. Marcas de tema compartilhado: quantas por par de disciplinas e quais ficam de UM LADO SÓ (A marca B, mas B não marca A).
  B. Marcas com nome de disciplina que o script não reconhece (erro de digitação ou nome fora do padrão).
  C. Possíveis temas compartilhados SEM marca: tópicos de disciplinas diferentes com nomes parecidos, sem marca entre as duas disciplinas.
  D. Forma: assuntos, tópicos e tópicos por assunto de cada disciplina (nível de detalhe parecido?).
  E. Nomes de assunto repetidos entre disciplinas.
  F. Destinos de "migra para X" que não existem como disciplina.
É triagem por palavras: o usuário decide; nada é alterado.
"""
import collections
import itertools
import json
import re
import statistics as st
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAT = RAIZ / "dados" / "catalogo"

# nome da marca -> disciplina canônica (slug do arquivo)
NOMES = {
    "direito penal": "direito-penal", "execucao penal": "execucao-penal", "direitos humanos": "direitos-humanos", "eca": "direito-da-crianca-e-do-adolescente",
    "direito da crianca e do adolescente": "direito-da-crianca-e-do-adolescente", "direito civil": "direito-civil",
    "direito constitucional": "direito-constitucional", "direito administrativo": "direito-administrativo",
    "direito processual civil": "direito-processual-civil", "direito processual penal": "direito-processual-penal",
    "principios e atribuicoes institucionais da defensoria": "principios-e-atribuicoes-institucionais-da-defensoria", "criminologia": "criminologia",
    "lingua portuguesa": "lingua-portuguesa",
}
CURTO = {v: k for k, v in reversed(list(NOMES.items()))}
MARCA = re.compile(r"\[Tema compartilhado com ([^\]]*)\]")
STOP = set("de da do das dos a o as os e em no na nos nas para por com sobre entre ao ou lei direito direitos penal processo processual".split())
LIM = 0.7


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def toks(s):
    return {w for w in re.findall(r"[a-z]{4,}", norm(s)) if w not in STOP}


def parceiros(texto):
    """Disciplinas citadas numa marca. Devolve (reconhecidas, desconhecidas)."""
    ok, ruim = set(), []
    longos = sorted(NOMES, key=len, reverse=True)
    for m in MARCA.finditer(texto or ""):
        resto = norm(re.sub(r"\([^)]*\)", "", m.group(1)))
        for nome in longos:                       # nomes completos primeiro (alguns têm " e " dentro)
            if nome in resto:
                ok.add(NOMES[nome])
                resto = resto.replace(nome, " ")
        for parte in re.split(r",| e ", resto):
            if parte.strip():
                ruim.append(parte.strip())
    return ok, ruim


def main():
    drafts = {}
    for p in sorted(CAT.glob("_rascunho_*_v2.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        drafts[d["slug"]] = d
    print(f"== COERÊNCIA ENTRE DISCIPLINAS: {len(drafts)} rascunhos v2 (sem usar banco nem questões)\n")

    # A e B
    marcas = collections.defaultdict(list)       # (origem, destino) -> [(topico, assunto)]
    desconhecidos = []
    for s, d in drafts.items():
        for a in d["assuntos"]:
            for t in a["pontos"]:
                ok, ruim = parceiros(t.get("descricao"))
                for o in ok:
                    marcas[(s, o)].append(t["texto"])
                for r in ruim:
                    desconhecidos.append((s, t["texto"], r))
    print("-- A. Marcas de tema compartilhado por par (origem -> disciplina citada)")
    for (o, dst), lst in sorted(marcas.items()):
        volta = len(marcas.get((dst, o), []))
        flag = "" if volta else "   <- de UM LADO SÓ (a outra disciplina não marca esta)"
        print(f"   {CURTO.get(o, o)[:34]:34} -> {CURTO.get(dst, dst)[:34]:34} {len(lst):3d} tópico(s); volta: {volta}{flag}")
    sem_rascunho = {dst for (o, dst) in marcas if dst not in drafts}
    if sem_rascunho:
        print("   (citadas sem rascunho v2 próprio: " + ", ".join(sorted(CURTO.get(x, x) for x in sem_rascunho)) + ")")

    print("\n-- B. Marcas com nome de disciplina não reconhecido")
    for s, t, r in desconhecidos:
        print(f"   {CURTO.get(s, s)}: '{t[:50]}' cita '{r}'")
    if not desconhecidos:
        print("   nenhuma")

    # C
    print("\n-- C. Possíveis temas compartilhados SEM marca (nomes parecidos em disciplinas diferentes)")
    todos = [(s, a["nome"], t["texto"], toks(t["texto"])) for s, d in drafts.items() for a in d["assuntos"] for t in a["pontos"]]
    nC = 0
    for (s1, a1, t1, k1), (s2, a2, t2, k2) in itertools.combinations(todos, 2):
        if s1 == s2 or len(k1) < 1 or len(k2) < 1:
            continue
        if (s1, s2) in marcas or (s2, s1) in marcas:
            continue
        inter = len(k1 & k2)
        if not inter:
            continue
        j = max(inter / len(k1 | k2), inter / min(len(k1), len(k2)) if min(len(k1), len(k2)) >= 2 else 0)
        if j >= LIM:
            nC += 1
            if nC <= 40:
                print(f"   {CURTO.get(s1, s1)[:22]:22} '{t1[:44]}'  ~  {CURTO.get(s2, s2)[:22]:22} '{t2[:44]}' ({j:.2f})")
    print(f"   -> {nC} par(es)" + (" (mostrados os 40 primeiros)" if nC > 40 else ""))

    # D
    print("\n-- D. Forma de cada disciplina")
    print(f"   {'disciplina':36} {'assuntos':>8} {'tópicos':>8} {'tóp./assunto (mín, mediana, máx)':>34}")
    for s, d in drafts.items():
        ns = [len(a["pontos"]) for a in d["assuntos"]]
        print(f"   {CURTO.get(s, s)[:36]:36} {len(ns):8d} {sum(ns):8d} {min(ns):>12d}, {int(st.median(ns)):>3d}, {max(ns):>3d}")

    # E
    print("\n-- E. Nomes de assunto repetidos entre disciplinas")
    nomes = collections.defaultdict(list)
    for s, d in drafts.items():
        for a in d["assuntos"]:
            nomes[norm(a["nome"])].append((s, a["nome"]))
    rep = {k: v for k, v in nomes.items() if len({s for s, _ in v}) > 1}
    for k, v in rep.items():
        print(f"   '{v[0][1]}' em: " + ", ".join(CURTO.get(s, s) for s, _ in v))
    if not rep:
        print("   nenhum")

    # G
    print("\n-- G. Sugestão de marca de volta (compartilhamento de um lado só: qual tópico do outro lado trata do mesmo tema?)")
    por_slug = {s: [(a["nome"], t) for a in d["assuntos"] for t in a["pontos"]] for s, d in drafts.items()}
    nG = 0
    for (o, dst), lst in sorted(marcas.items()):
        if marcas.get((dst, o)) or dst not in drafts:
            continue
        for texto in lst:
            origem = next(t for _, t in por_slug[o] if t["texto"] == texto)
            ko = toks(origem["texto"] + " " + MARCA.sub("", origem.get("descricao") or ""))
            melhor = max(((len(ko & toks(tt["texto"] + " " + MARCA.sub("", tt.get("descricao") or ""))) / max(len(ko | toks(tt["texto"] + " " + MARCA.sub("", tt.get("descricao") or ""))), 1), tt["texto"])
                          for _, tt in por_slug[dst]), default=(0, ""))
            nG += 1
            ref = f"melhor correspondente: '{melhor[1][:50]}' ({melhor[0]:.2f})" if melhor[0] >= 0.12 else "sem tópico correspondente (não há o que marcar)"
            print(f"   {CURTO.get(o, o)[:20]:20} '{texto[:44]}' -> {CURTO.get(dst, dst)[:20]:20} {ref}")
    print(f"   -> {nG} tópico(s) sem marca de volta")

    # F
    print("\n-- F. Destinos 'migra para ...' nas lixeiras")
    for s, d in drafts.items():
        for x in d.get("lixeira", []) + d.get("lixeira_assuntos", []):
            n = x.get("nota") or ""
            if n.startswith("migra para"):
                alvo = norm(re.sub(r"\(.*", "", n[len("migra para"):]).replace("a disciplina", "").strip(" ;"))
                alvo = re.sub(r";.*", "", alvo).strip()
                achou = any(alvo.startswith(k) or k.startswith(alvo) for k in NOMES)
                print(f"   {CURTO.get(s, s)[:26]:26} '{(x.get('texto') or x.get('nome'))[:46]}' -> {n[:70]}" + ("" if achou else "   <- DESTINO NÃO RECONHECIDO"))
    print("\nTriagem: nada foi alterado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
