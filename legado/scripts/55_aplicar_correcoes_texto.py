#!/usr/bin/env python3
"""Aplica ao banco as correções de texto de questões digitadas à mão a partir da imagem do caderno (OCR ruim).

Uso:  python -I scripts/55_aplicar_correcoes_texto.py "<nome da prova>" <numero> [<numero> ...] [--simular]

Lê `dados/correcoes_texto.json` ({prova: {numero: {disciplina, enunciado, alts[5], mover_para?}}}; `mover_para` troca a disciplina da questão) e, para cada número pedido, grava
`enunciado` e `alt_a` a `alt_e` em `questoes` e passa `situacao` de `revisar_texto` para `valida`. Cópia do banco antes
(`banco/backup/`) e registro em `log_alteracoes`. Só aplica o que o usuário pedir: o texto vem de transcrição conferida
com a imagem do PDF original (provas/ não é alterado). Chave da questão: prova + número (os IDs mudam).
"""
import datetime, json, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco" / "estudos.db"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
simular = "--simular" in sys.argv
prova, numeros = args[0], args[1:]
corr = json.loads((RAIZ / "dados" / "correcoes_texto.json").read_text(encoding="utf-8"))[prova]
if not simular:
    dst = RAIZ / "banco" / "backup" / f"estudos_antes_correcao_texto_{datetime.date.today().isoformat()}_{datetime.datetime.now().strftime('%H%M')}.db"
    s = sqlite3.connect(BANCO); o = sqlite3.connect(dst); s.backup(o); o.close(); s.close()
    print("cópia de segurança:", dst.name)
con = sqlite3.connect(":memory:" if simular else BANCO)
if simular:
    real = sqlite3.connect(BANCO); real.backup(con); real.close()
pid = con.execute("select id from provas where nome=?", (prova,)).fetchone()[0]
for n in numeros:
    c = corr[n]
    assert len(c["alts"]) == 5, f"Q{n}: precisa de 5 alternativas"
    r = con.execute("select id,situacao from questoes where prova_id=? and numero=?", (pid, int(n))).fetchone()
    con.execute("update questoes set enunciado=?, alt_a=?, alt_b=?, alt_c=?, alt_d=?, alt_e=?, situacao=case when situacao='revisar_texto' then 'valida' else situacao end where id=?",
                (c["enunciado"], *c["alts"], r[0]))
    if c.get("mover_para"):
        dd = con.execute("select id from disciplinas where nome=?", (c["mover_para"],)).fetchone()
        assert dd, c["mover_para"]
        con.execute("update questoes set disciplina_id=?, motivo_situacao=? where id=?", (dd[0], "disciplina e texto refeitos pela imagem do caderno em 15/11/2026", r[0]))
        con.execute("insert into log_alteracoes(quem,o_que) values('script 55', ?)", (f"{prova} Q{n} movida para {c['mover_para']}" + (" [simulação]" if simular else ""),))
    con.execute("insert into log_alteracoes(quem,o_que) values('script 55', ?)", (f"texto corrigido de {prova} Q{n} (era {r[1]})" + (" [simulação]" if simular else ""),))
    print(f"Q{n}: texto corrigido (situação era {r[1]})")
if not simular:
    con.commit()
