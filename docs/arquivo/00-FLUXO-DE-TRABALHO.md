# Fluxo de trabalho: guias → insumos → produtos

> **Atualização 12/11/2026:** o fluxo novo (banco permanente, catálogo de pontos, perfil, motor `scripts/23`, apostila `scripts/24`) substituiu os scripts e planilhas descritos abaixo; leia `04-DECISOES-CONFIRMADAS.md` primeiro. As seções 3 a 5 ficam como histórico do método anterior (scripts agora em `scripts/legado/`).

Criado em 12/11/2026. **Ponto de entrada para quem retoma o trabalho** (agente ou usuário). Depois de ler este arquivo, leia `../00-PLANO-E-ROTEIRO.md` (registro do que foi feito) e `../01-PENDENCIAS.md` (o que falta).

## 1. A ideia em uma frase
Os **dois guias** são os pilares da análise. As **provas, os editais anteriores e as questões** (banco de dados) são os insumos. Aplicando os guias aos insumos, saem os **produtos**: primeiro as **planilhas** (análise e revisão), depois a **apostila**, montada a partir dos guias, dos insumos e das planilhas, com os **modelos** (`../modelos/`).

```
PILARES              INSUMOS                          PRODUTOS
Guia 1 (preditiva) ─┐  provas + gabaritos (PDF)       1º  Planilha de análise   (Guia 1)
                    ├─ editais (atual e anteriores)   1º  Planilha de revisão   (Guia 2)
Guia 2 (edital,    ─┘  banco de questões (SQLite)     2º  Apostila por disciplina (modelos A e B)
 examinadores,         relatórios de anulação
 revisão)              classificação e comentários
```

## 2. Onde está cada coisa (a partir de `Auxílio Estudos Concurso\`)
| O quê | Onde |
|---|---|
| **Guias** (pilares) e exemplos antigos de produto | `docs\metodo\guias\` |
| Provas, editais e gabaritos em PDF (21 provas + DPE-AM 2023 Analista) | `provas\<ano - órgão - cargo>\` |
| Banco de questões (SQLite) e arquivos de apoio | `banco\` (`questoes.db`, `texto-bruto\`, `gabaritos_fcc\`, `fonte_tec\`, `programas_dh\`) |
| Dados de trabalho (classificação, comentários, correções) | `dados\` |
| Scripts numerados | `scripts\` |
| Modelos de apostila (A sem edital, B com edital) e roteiro de uso | `produtos\modelos\` |
| Produtos prontos | `produtos\apostilas\<disciplina>\` (apostila Word, planilha de análise, planilha de revisão) |
| Registro e pendências | `docs\00-PLANO-E-ROTEIRO.md` e `docs\01-PENDENCIAS.md` |

## 3. Mapa dos guias: o que cada passo exige, que produto gera e como está
Legenda: ✔ feito para Direitos Humanos · ◐ parcial · ✘ não feito · 👤 depende do usuário.

### Guia 1: análise preditiva
| Passo ou lente | Insumo | Produto / script | DH |
|---|---|---|---|
| Lente 1, estrutura do edital | edital do concurso-alvo | prefácio e parâmetros (nº de questões esperadas) | ◐ não há concurso-alvo; usou-se a média por prova |
| Passo 2, grupos A, B, C | provas | coluna Grupo em `Questoes` | ✔ A e B; C (outras bancas) não existe |
| Passo 3, lista fixa de assuntos (8 a 15) | programa dos editais | `scripts/10_taxonomia_dh.py` | ✔ |
| Passo 4, classificar as questões | banco | `dados/classificacao_dh.csv` | ✔ (uma só checagem) |
| Passo 5, pesos (idade, grupo) e nº efetivo | classificação | planilha de análise, colunas J a M | ✔ |
| Lente 2, frequência e faixa de Wilson | idem | planilha de análise, aba da disciplina | ✔ |
| Lente 3, mistura com provas parecidas | provas do grupo B | substituída por pesos de grupo | ◐ |
| Lente 4, tipo de cobrança | classificação | planilha e apostila | ✔ |
| Lente 5, examinador | composição das comissões | — | ✘ sem informação confirmada |
| Lente 6, recência | anos das provas | peso de idade | ✔ |
| Lente 7, assuntos inéditos (Good-Turing) | classificação | `scripts/11_analise_dh.py` | ✔ (nenhum assunto com 1 questão) |
| Lente 8, concentração (80%) | idem | idem | ✔ |
| Lente 9, presença em todas as provas | idem | coluna Provas | ✔ |
| Lente 10, seu desempenho | respostas do usuário | coluna Resultado da planilha | 👤 |
| Teste retroativo | provas | aba Teste retroativo | ✔ 56% contra 40% ao acaso |
| Passo 12, manter em dia | provas novas | regerar com os scripts | ✔ processo definido |

### Guia 2: edital, examinadores e revisão
| Capítulo | Insumo | Produto / script | DH |
|---|---|---|---|
| 2, comparar editais (novo, exclusivo, detalhado demais) | editais atual e anteriores | `scripts/08` e `09`, matriz tema × edital | ◐ por palavra-chave; sem edital de concurso-alvo |
| 3, perfil dos examinadores | nomes das comissões | — | ✘ |
| 4, autoavaliação 1 a 3 | itens do edital | `Revisao - Direitos Humanos.xlsx` (`scripts/13`) | 👤 notas |
| 5, cruzar nota × frequência | idem | fórmula da coluna Decisão | ✔ pronta |
| 6, fichas de revisão | erros do usuário + comentários | exemplo em `metodo/guias/exemplo - Fichas-...md` | ✘ ainda não gerei rascunhos |

## 4. Receita para repetir em outra disciplina ou outro concurso
1. **Insumos.** Baixar provas, editais e gabaritos (um arquivo por tipo de caderno!). Rodar `01`, `02`, `03` (banco), `05` (relatórios de alteração e anulação), `07` (texto limpo do TEC, quando preciso).
2. **Conferir os insumos** antes de analisar: tipo do caderno = tipo do gabarito; anuladas; texto das questões da disciplina; edital correto. Registrar em `01-PENDENCIAS.md` o que ficou sem conferir.
3. **Guia 2, cap. 2:** recortar o programa da disciplina de cada edital (`08`) e montar a matriz (`09`).
4. **Guia 1, passos 3 e 4:** fixar 8 a 15 assuntos; classificar cada questão (`dados/classificacao_<disciplina>.csv`, chave `prova;numero`).
5. **Planilhas (1º produto):** análise (`15`) e revisão (`13`). A análise em Python (`11`) existe para conferir a planilha.
6. **Comentários:** `dados/comentarios_<disciplina>_*.json` (chave `prova|número`).
7. **Apostila (2º produto):** `12` (modelo A) ou o modelo B; visual pela `apostila_lib.py`.
8. **Qualidade:** converter para PDF e olhar; conferir números da apostila contra a planilha; atualizar plano e pendências.

## 5. Avaliação honesta do método (12/11/2026)
**O que funciona bem**
- Separar insumo, método e produto: dá para refazer tudo quando entra prova nova.
- Banco com chave estável (`prova` + `número`) e scripts numerados: o caminho é rastreável.
- Guias como pilares: cada número da apostila aponta para uma lente do Guia 1.

**Pontos fracos conhecidos**
1. **Os scripts de análise e de apostila ainda são específicos de Direitos Humanos.** Para outra disciplina é preciso copiar e trocar constantes. Próximo passo de engenharia: um arquivo de configuração por disciplina e um comando único.
2. **Classificar e comentar é o gargalo** (a maior parte do esforço) e não tem segunda checagem. Sugestão: conferir por amostra (10% das questões por disciplina) e registrar o resultado.
3. **Dois motores para a mesma conta** (planilha com fórmulas e Python). Bom para conferir, ruim para manter. Regra: depois de qualquer mudança nos dados, regerar a planilha e conferir 3 números (nº efetivo, % do maior tema, média do teste retroativo) contra o Python.
4. **A apostila lê o Python, não a planilha.** Se o usuário mudar pesos na planilha, a apostila não muda. Decisão pendente: manter assim (apostila = foto de uma data) ou regerar a apostila a partir da planilha recalculada.
5. **Coleta de dados é frágil** (OCR, TEC/Chrome, gabaritos em imagem) e consome tempo; vale baixar uma prova por vez e conferir.
6. **Poucos dados por disciplina:** 5 a 13 questões de DH por prova; só dois temas se destacam. O método avisa isso; não prometa previsão fina.
7. **Fichas de revisão e lente 5** ainda não existem como produto.

## 6. Regras que valem sempre
- Declarar a amostra ao lado de qualquer número; comparar o teste retroativo com o acaso.
- Nunca citar lei, súmula ou julgado sem certeza; usar "confirmar".
- Nunca marcar a resposta no cartão da questão; gabarito discreto no fim do capítulo (regra do usuário).
- Mensagens ao usuário em linguagem simples e com contexto.
- Não alterar os PDFs originais.
