"""Confere a coerência da documentação (só leitura; não altera nada).

Uso: python -I scripts/73_conferir_docs.py

Regras que verifica (ver "Regra de documentação" no CLAUDE.md):
 1. Todo docs/*.md de primeiro nível aparece citado no CLAUDE.md.
 2. Nenhum docs/*.md está fora do git (não rastreado) sem aviso.
 3. Em docs/03-PENDENCIAS.md, item aberto "[ ]" não pode dizer que já foi resolvido/feito.
 4. O estado (etapa feita, "falta a ...") mora só no 03: CLAUDE.md e README não podem repeti-lo.
 5. Caminhos entre crases nos documentos vivos existem de fato.
Saída: ERRO (corrigir) ou AVISO (olhar). Código de saída 1 se houver ERRO.
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
VIVOS = ["CLAUDE.md", "README.md", "docs/01-METODO.md", "docs/02-DECISOES-EM-VIGOR.md",
         "docs/03-PENDENCIAS.md"]
# documentos onde caminho inexistente é só aviso (guardam histórico e decisões antigas)
SO_AVISO = {"docs/02-DECISOES-EM-VIGOR.md"}

erros, avisos = [], []


def ler(rel):
    return (RAIZ / rel).read_text(encoding="utf-8")


# 1. docs citados no CLAUDE.md
claude = ler("CLAUDE.md")
for p in sorted(DOCS.glob("*.md")):
    if p.name not in claude:
        erros.append(f"docs/{p.name} não é citado no CLAUDE.md (incluir na lista, ou mover para docs/arquivo/).")

# 2. não rastreados no git
try:
    out = subprocess.run(["git", "status", "--porcelain", "--", "docs", "CLAUDE.md", "README.md"],
                         cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    for linha in out.splitlines():
        if linha.startswith("??"):
            avisos.append(f"{linha[3:]} ainda não está no git (rascunho fora do histórico).")
except Exception as e:  # git ausente
    avisos.append(f"git indisponível: {e}")

# 3. [ ] que diz estar resolvido
for n, linha in enumerate(ler("docs/03-PENDENCIAS.md").splitlines(), 1):
    if linha.startswith("- [ ]") and re.search(r"[Rr]esolvido|\bfeita?\b em \d", linha):
        erros.append(f"docs/03-PENDENCIAS.md:{n} item aberto [ ] cita que foi resolvido/feito; marcar [x] ou tirar o texto.")

# 4. estado repetido fora do 03
ESTADO = re.compile(r"Etapas? \d[^.\n]*(feitas?|em curso)|\bfalt(a|am) (a )?(\d|Etapa)|em andamento", re.I)
for rel in ("CLAUDE.md", "README.md"):
    for n, linha in enumerate(ler(rel).splitlines(), 1):
        if linha.startswith("## Regra de documentação"):
            break  # a própria regra cita as expressões proibidas
        if ESTADO.search(linha):
            erros.append(f"{rel}:{n} descreve estado de andamento; isso mora só em docs/03-PENDENCIAS.md (seção 1).")

# 5. caminhos entre crases
CAM = re.compile(r"`([^`\s]+)`")
for rel in VIVOS:
    alvo = erros if rel not in SO_AVISO else avisos
    for n, linha in enumerate(ler(rel).splitlines(), 1):
        for m in CAM.finditer(linha):
            c = m.group(1).rstrip(".,;:)")
            if not re.search(r"(/|\.py$)", c):
                continue
            if any(t in c for t in ("<", "*", "...", "AAAA", "NN", "{", "http", "=", "|")):
                continue
            c = c.replace("\\", "/")
            topo = c.split("/")[0]
            if "/" in c and topo not in ("banco", "dados", "docs", "produtos", "provas", "scripts", "legado"):
                continue  # caminho relativo a uma pasta (ex.: apostilas/, catalogo/)
            if "/" not in c and not re.match(r"\d\d", c):
                continue
            cand = [RAIZ / c, RAIZ / "scripts" / c, DOCS / c, RAIZ / "docs" / "arquivo" / c,
                    RAIZ / "legado" / "scripts" / c]
            if "/" not in c and not c.endswith(("/", )):
                cand.append(RAIZ / "legado" / c)
            if not any(x.exists() for x in cand):
                # tolera nomes de script abreviados ("scripts/72_perfil.py" já cobre; "72_perfil.py" cobre via scripts/)
                alvo.append(f"{rel}:{n} caminho inexistente: {c}")

for a in avisos:
    print("AVISO:", a)
for e in erros:
    print("ERRO: ", e)
print(f"\n{len(erros)} erro(s), {len(avisos)} aviso(s).")
sys.exit(1 if erros else 0)
