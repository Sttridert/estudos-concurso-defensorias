"""Lê do banco o ARTEFATO do edital (frases literais classificadas; scripts 50 a 52) e devolve, para o gerador de apostilas
(scripts/24), as mesmas estruturas que ele já usa com `edital_pontos` e `editais.programa`.

carregar(con, edital_id, disc_id, pts, bloco=None) -> dict com (bloco = sigla do bloco do perfil; sem ele vale a disciplina):
  programa   [{"item": rótulo, "topicos": [frases], "cods": [[(codigo, papel), ...] por frase]}]   só o bloco da própria disciplina
  edpts      {codigo: {ordem, texto_no_edital, marca_*, n_ed, trechos(JSON)}}                    pontos da disciplina que o edital cobre
  frase_de   {(rótulo, texto)}                                                                    frases inteiras (para o "…" dos trechos)
  outros     [(sigla do bloco, rótulo, frase, cods)]                                              frases de OUTROS blocos que caíram nesta disciplina
  n_frases, n_destinos
Rótulo de frase de outro bloco = "<SIGLA>.<item>" (sem espaço; o gerador separa o rótulo do texto pelo primeiro espaço).
Frase de bloco sem numeração (ex.: ECA do DPE-AM 2026) usa o rótulo "s/n". Propostas de tópicos novos (NP-...) não entram.
"""
import json


def carregar(con, edital_id, disc_id, pts, bloco=None):
    cod_de_id = {v["id"]: c for c, v in pts.items()}
    frases = con.execute("""select f.id, f.disciplina_edital, f.disciplina_id, f.item_ordem, f.item_rotulo, f.texto from edital_frases f
                            where f.edital_id=? order by f.id""", (edital_id,)).fetchall()
    if not frases:
        raise SystemExit(f"o edital {edital_id} não tem frases classificadas (rode os scripts 50, 51 e 52)")
    dest = {}
    for fid, pid, papel, trecho in con.execute("""select d.frase_id, d.ponto_id, d.papel, d.trecho from edital_frase_destinos d
                                                  join edital_frases f on f.id=d.frase_id where f.edital_id=? and d.ponto_id is not null order by d.id""", (edital_id,)):
        dest.setdefault(fid, []).append((pid, papel, trecho))
    todos_cod = {i: c for i, c in con.execute("select id, codigo from pontos")}
    programa, outros, frase_de = [], [], set()
    trechos, primeira = {}, {}
    itens = {}
    n_dest = 0
    for fid, sigla, fdisc, iord, irot, texto in frases:
        proprio = (sigla == bloco) if bloco else (fdisc == disc_id)      # perfil por bloco do edital (lib_escopo): o bloco manda
        rot = irot or "s/n"
        rotulo = rot if proprio else f"{sigla}.{rot}"
        frase_de.add((rotulo, texto))
        ds = dest.get(fid, [])
        # códigos para a coluna "Pontos": principais primeiro, depois secundários
        cods = []
        for pid, papel, tr in sorted(ds, key=lambda x: x[1] != "principal"):
            c = todos_cod[pid]
            if (c, papel) not in cods:
                cods.append((c, papel))
        for pid, papel, tr in ds:
            if pid in cod_de_id:
                pc = cod_de_id[pid]
                n_dest += 1
                # ordem: primeiro o que o bloco da própria disciplina diz, depois as frases de outros blocos
                primeira.setdefault(pc, fid + (0 if proprio else 10**6))
                t = {"i": rotulo, "t": tr or texto, "f": texto}
                lista = trechos.setdefault(pc, ([], []))[0 if proprio else 1]
                if t not in lista:
                    lista.append(t)
        if proprio:
            it = itens.setdefault(iord, {"item": rot, "topicos": [], "cods": []})
            it["topicos"].append(texto)
            it["cods"].append(cods)
        elif any(pid in cod_de_id for pid, _, _ in ds):
            outros.append((sigla, rotulo, texto, cods))
    programa = [itens[k] for k in sorted(itens)]
    # Regra do usuario (15/11/2026): tema que o edital escreve so em OUTRA disciplina nao entra na apostila desta.
    # O ponto so conta como "do edital" quando alguma frase do PROPRIO bloco da disciplina cai nele.
    so_outros = {pc: tr[1] for pc, tr in trechos.items() if not tr[0]}
    trechos = {pc: tr for pc, tr in trechos.items() if tr[0]}
    n_ed = {pc: con.execute("select count(*) from ponto_fontes where ponto_id=? and presente=1", (pts[pc]["id"],)).fetchone()[0] for pc in trechos}
    edpts = {pc: {"codigo": pc, "ordem": primeira[pc], "texto_no_edital": None, "marca_novo": 0, "marca_exclusivo": 0, "marca_detalhado": 0,
                  "n_ed": n_ed[pc], "trechos": json.dumps(tr[0] + tr[1], ensure_ascii=False)} for pc, tr in trechos.items()}
    try:
        fora = {c: m for c, m in con.execute("select p.codigo, f.motivo from edital_pontos_fora f join pontos p on p.id=f.ponto_id where f.edital_id=?", (edital_id,))}
    except Exception:
        fora = {}
    for pc, lst in so_outros.items():
        fora.setdefault(pc, "Só aparece em outro bloco do edital (" + ", ".join(sorted({t["i"] for t in lst})) + "): estude na apostila dessa disciplina.")
    return {"fora": fora, "programa": programa, "edpts": edpts, "frase_de": frase_de, "outros": outros, "n_frases": len(frases), "n_destinos": n_dest}
