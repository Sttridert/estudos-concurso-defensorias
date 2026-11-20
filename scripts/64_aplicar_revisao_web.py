#!/usr/bin/env python3
"""Aplica no banco o resultado da REVISÃO WEB de comentários marcados (plano 05, Fase B; decisão 41, item 6).

Uso:  python -I scripts/64_aplicar_revisao_web.py dados/revisao_web/<disciplina>.json [--simular]

Formato do arquivo (também é o REGISTRO da revisão: questão, afirmação, fonte, data e resultado):
  {"disciplina": "...", "consultado_em": "AAAA-MM-DD",
   "itens": [{"questao": "<prova>|<número>", "resultado": "confirmado" | "corrigido" | "sem_fonte",
              "afirmacao": "o que foi conferido", "fonte": ["URL ou documento"], "dispositivos": ["Norma|artigo", ...],
              "c": "novo comentário (obrigatório se corrigido)", "p": "nova pegadinha (opcional)"}]}
Efeito por resultado:
  confirmado -> tira a marca (pendente_confirmacao = 0); tira do comentário as frases "Não consegui conferir..." e "Confirmar ..."; grava os dispositivos, se vierem.
  corrigido  -> troca comentário (e pegadinha/dispositivos, se vierem) e tira a marca.
  sem_fonte  -> mantém a marca; se vier "c", troca o comentário (o texto deve dizer "confirmar no Planalto/tribunal").
Nada é citado sem ter sido lido na fonte. O comentário continua RASCUNHO da IA (estado 'rascunho'). Cópia do banco antes.
"""
import datetime, json, re, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
STALE = re.compile(r"^(N[ãa]o consegui conferir|Confirmar\b|Confirmar na)", re.I)


def limpa(texto):
    frases = re.split(r"(?<=[.!?])\s+", texto.strip())
    return " ".join(f for f in frases if not STALE.match(f)).strip()


def main():
    arq = Path(sys.argv[1])
    simular = "--simular" in sys.argv
    dados = json.loads(arq.read_text(encoding="utf-8"))
    con = sqlite3.connect(BANCO)
    if not simular:
        dst = RAIZ / "banco" / "backup" / f"estudos_antes_revisao_web_{arq.stem}_{datetime.date.today().isoformat()}.db"
        if not dst.exists():
            out = sqlite3.connect(dst); con.backup(out); out.close(); print("cópia de segurança:", dst.name)
    cont = {"confirmado": 0, "corrigido": 0, "sem_fonte": 0}
    hoje = datetime.date.today().isoformat()
    for it in dados["itens"]:
        prova, num = it["questao"].rsplit("|", 1)
        q = con.execute("select q.id from questoes q join provas p on p.id=q.prova_id where p.nome=? and q.numero=?", (prova, int(num))).fetchone()
        if not q:
            sys.exit("questão não encontrada: " + it["questao"])
        atual = con.execute("select texto,pegadinha,dispositivos,pendente_confirmacao from comentarios where questao_id=?", (q[0],)).fetchone()
        if not atual:
            sys.exit("a questão não tem comentário: " + it["questao"])
        texto, peg, disp, pend = atual
        r = it["resultado"]
        if r == "confirmado":
            texto, pend = limpa(texto), 0
        elif r == "corrigido":
            if not it.get("c"):
                sys.exit("corrigido sem texto novo: " + it["questao"])
            texto, pend = it["c"], 0
        elif r == "sem_fonte":
            if it.get("c"):
                texto = it["c"]
            pend = 1
        else:
            sys.exit("resultado inválido: " + r)
        if it.get("p"):
            peg = it["p"]
        if it.get("dispositivos") is not None:
            disp = json.dumps(it["dispositivos"], ensure_ascii=False)
        con.execute("update comentarios set texto=?, pegadinha=?, dispositivos=?, pendente_confirmacao=?, atualizado_em=? where questao_id=?",
                    (texto, peg, disp, pend, hoje, q[0]))
        cont[r] += 1
    con.execute("insert into log_alteracoes(quem,o_que) values('script 64', ?)",
                (f"revisão web {arq.name}: {cont['confirmado']} confirmados, {cont['corrigido']} corrigidos, {cont['sem_fonte']} sem fonte suficiente" + (" [simulação]" if simular else ""),))
    if simular:
        con.rollback(); print("(simulação: nada gravado)")
    else:
        con.commit()
    print(cont)


if __name__ == "__main__":
    main()
