"""Depois de ingerir provas do manifesto, move os arquivos de provas/NOVAS/ para a pasta padrao provas/<nome da prova>/:
  1. edital.pdf (abertura), 2. caderno de prova.pdf, 3. gabarito.<ext>, e o resto em outros/.
Atualiza provas.arquivo_edital/caderno/gabarito no banco. So mexe em provas que ja estao no banco. Nao apaga nada:
o que sobrar em NOVAS (arquivos de concursos sem prova no banco, como o III Concurso ja existente) fica la.
Uso: python -I scripts/coletar_organizar_provas.py dados/provas_novas_manifesto.json [--simular]
"""
import json, shutil, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "banco" / "estudos.db"


def main():
    manifesto = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    simular = "--simular" in sys.argv
    con = sqlite3.connect(DB)
    for p in manifesto:
        r = con.execute("select id from provas where nome=?", (p["nome"],)).fetchone()
        if not r:
            print("fora do banco, pulei:", p["nome"])
            continue
        destino = RAIZ / "provas" / p["nome"]
        caderno = RAIZ / p["caderno"]
        gabarito = RAIZ / p["gabarito"]
        edital = RAIZ / p["arquivo_edital"] if p.get("arquivo_edital") else None
        if not caderno.exists():
            print("ja organizado ou ausente:", p["nome"])
            continue
        pasta_origem = caderno.parent.parent if caderno.parent.name == "Provas e Gabaritos" else caderno.parent
        print(f"[{p['nome']}] origem: {pasta_origem.name}")
        if simular:
            continue
        (destino / "outros").mkdir(parents=True, exist_ok=True)
        # arquivos principais
        usados = set()
        novos = {}
        for rotulo, src in (("1. edital", edital), ("2. caderno de prova", caderno), ("3. gabarito", gabarito)):
            if src and src.exists():
                dst = destino / f"{rotulo}{src.suffix}"
                shutil.move(str(src), str(dst))
                usados.add(src)
                novos[rotulo] = dst.relative_to(RAIZ).as_posix()
        # o resto da pasta da prova vai para outros/
        for f in sorted(pasta_origem.rglob("*")):
            if f.is_file():
                shutil.move(str(f), str(destino / "outros" / f.name))
        # remove pastas vazias da origem
        for d in sorted((x for x in pasta_origem.rglob("*") if x.is_dir()), reverse=True):
            try:
                d.rmdir()
            except OSError:
                pass
        try:
            pasta_origem.rmdir()
        except OSError:
            pass
        con.execute("update provas set arquivo_edital=coalesce(?,arquivo_edital), arquivo_caderno=?, arquivo_gabarito=? where id=?",
                    (novos.get("1. edital"), novos["2. caderno de prova"], novos["3. gabarito"], r[0]))
        con.commit()
        print("  organizado em", destino.relative_to(RAIZ))


if __name__ == "__main__":
    main()
