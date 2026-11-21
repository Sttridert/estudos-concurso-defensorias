# Auxílio Estudos Concurso

Apoio a estudos para concursos públicos de **Defensorias (banca FCC)**. Pega as provas anteriores, monta um banco de questões, descobre o que mais cai e gera uma **apostila por disciplina** (Word) com questões, gabarito e comentários. Piloto pronto: **Direitos Humanos**.

## Como funciona
`guias (método)` → `provas e editais (insumos)` → `banco estudos.db` → `motor de análise` → `apostila`

1. As provas ficam em `provas/`; o texto vai para `banco/fontes/texto-bruto/`.
2. Cada questão é ligada a um **ponto** do catálogo da disciplina (e, portanto, a um **assunto**).
3. Um **universo** escolhe quais questões entram (todas, só FCC, só Defensoria, só Defensor Público FCC etc.). Um **perfil** (disciplina, carreira ou cargo, banca) define os pesos: semelhança (grupos A, B, C) e recência.
4. O motor calcula frequência com faixa de confiança, teste retroativo e diagnósticos.
5. O gerador monta a apostila.

## Estrutura
| Pasta | Conteúdo |
|---|---|
| `banco/` | `estudos.db` (fonte única, nunca recriado), `fontes/` (texto bruto das provas, dados do TEC, gabaritos da FCC), `analise/` (saída do motor), `base-regressao-*/` e `backup/` (cópias do banco, só locais) |
| `dados/` | `catalogo/` e `classificacao/` por disciplina, `comentarios/`, `fontes/` (normas oficiais), `editais_reais/` (programa de cada edital), `referencia/`, `revisao_web/`, `coleta/` (insumos da coleta de provas e editais) e `disciplinas.json` |
| `docs/` | método, decisões em vigor, pendências, planos em curso, `guias/` (PDF, só local) e `arquivo/` (histórico) |
| `produtos/` | apostilas prontas (`apostilas/`) e `modelos/base-estilos.docx` (estilos do gerador) |
| `legado/` | scripts, dados, apostilas e modelos aposentados (ver `legado/LEIA-ME.md`) |
| `provas/` | provas, editais e gabaritos oficiais em PDF, por concurso (só locais; o banco guarda esses caminhos, então a pasta não muda de lugar) |
| `scripts/` | código Python; o prefixo do nome diz o grupo (tabela abaixo) |

## Mapa dos grupos (A a F)
Os grupos descrevem as etapas do trabalho; os dados atravessam várias etapas, por isso as pastas são por tipo de conteúdo e não por grupo.

| Grupo | O que faz | Scripts | Onde ficam os dados |
|---|---|---|---|
| A. Coletar | provas, gabaritos e programas de edital | `coletar_*`, `lib_texto_prova`, `lib_programa_edital` | `provas/`, `banco/fontes/`, `dados/coleta/`, `dados/editais_reais/` |
| B. Catalogar | assuntos e tópicos de cada disciplina | `catalogar_*`, `lib_catalogo`, `lib_rascunho`, `71_*` | `dados/catalogo/`, `dados/disciplinas.json` |
| C. Mapear | liga questões e frases de edital aos tópicos | `mapear_*`, `lib_questoes`, `51`, `52`, `53` | `dados/classificacao/`, `dados/referencia/` |
| D. Decidir | perfil, universo e pesos | `72_perfil`, `lib_perfil`, `decidir_testes` | `produtos/apostilas/<concurso>/perfil.toml` |
| E. Comentar | comentários com fonte oficial | `comentar_*`, `64`, `lib_comentarios` | `dados/comentarios/`, `dados/fontes/`, `dados/revisao_web/` |
| F. Produzir | semáforo, motor, apostila Word, regressão | `70`, `23`, `24`, `apostila_lib`, `lib_escopo`, `lib_semaforo`, `produzir_*` | `produtos/apostilas/`, `banco/analise/`, `banco/base-regressao-*/` |

## Como rodar (Windows, Python 3.12)
Requisitos: ver `requirements.txt` (pacote Python `python-docx`; programas externos Tesseract com o idioma `por`, Poppler e LibreOffice, e o que mais for preciso para clonar do zero).
```
python scripts/23_motor_analise.py --perfil 1     # análise (grava em banco/analise/)
python scripts/23_motor_analise.py --perfil 1 --universo 6   # outro universo de questões
python scripts/23_motor_analise.py --perfil 1 --comparar    # compara universos no mesmo alvo
python scripts/24_gerar_apostila.py --perfil 1    # apostila (grava em produtos/apostilas/)
python -I scripts/coletar_ingerir_prova.py dados/coleta/provas_novas_manifesto.json   # entra prova nova no banco
python -I scripts/coletar_conferir_prova.py relatorio           # quais provas estão conferidas e quais pendentes
python -I scripts/71_catalogo_e_classificacao.py conferir        # catálogo e classificação: arquivos x banco
# edital real = artefato: coletar_programa_edital.py extrair, depois 51 e 52
```
O perfil mora em `produtos/apostilas/<concurso>/perfil.toml` (criar com `scripts/72_perfil.py novo-concurso` e `nova-apostila`; mostrar com `mostrar`; confirmar com `confirmar` só depois do "sim" do usuário). Precisa estar completo e confirmado. A tabela `perfis` do banco foi aposentada.

## Para quem retoma o trabalho
Leia `CLAUDE.md`, depois `docs/01-METODO.md`, `docs/02-DECISOES-EM-VIGOR.md` e `docs/03-PENDENCIAS.md`.

## Aviso
As provas em `provas/` são material oficial das bancas, guardado só para estudo pessoal. Classificação, pontos e comentários são rascunho feito por IA e precisam de conferência (ver `docs/03-PENDENCIAS.md`). Não publique o repositório em local público sem rever isso.
