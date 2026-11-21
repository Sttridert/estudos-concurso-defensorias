# Auditoria da Etapa 1 (plano 06) — só leitura

> Nota de 16/11/2026: os nomes de documentos abaixo são os de antes da Etapa 4; os históricos agora estão em `docs/arquivo/` (ver `docs/01-METODO.md`).

Feita em 16/11/2026. Nada foi alterado nos scripts, no banco nem nos produtos; só este relatório foi criado. Fontes: lista de arquivos, primeira linha de cada script, consultas de leitura ao `banco/estudos.db`. **Não li o código de cada script por dentro**; os pontos marcados "(verificar)" pedem leitura na Etapa 2.

## 1. Scripts (5.718 linhas em 52 arquivos)

| Grupo                                                 | Scripts                                                                                                                                                                                                                       | Situação                                                                                                                                                                                                                |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Núcleo vivo                                          | `23` motor, `24` gerador, `apostila_lib`, `lib_escopo`, `lib_edital_classificado`, `70` porteiro                                                                                                                  | Em uso; é o que as 10 apostilas rodam                                                                                                                                                                                    |
| Entrada de provas                                     | `26`, `27`, `32`, `55`, `57`, `64`, `65`, `66`                                                                                                                                                                | Em uso, genéricos                                                                                                                                                                                                        |
| Edital real (artefato)                                | `50`, `51`, `52`, `53`, `56`                                                                                                                                                                                        | Em uso; a Fase E depende deles (não mexer)                                                                                                                                                                               |
| Edital fictício                                      | `40`, `41`, `43`, `44`                                                                                                                                                                                                | Em uso por disciplina; `42` só serve DH e Penal                                                                                                                                                                        |
| **Duplicados por disciplina (alvo da Etapa 2)** | catálogo: `21` (DH), `31` (Penal), `58` (LP), `60` (PI); classificação: `22` (DH), `31` (Penal), `59` (LP), `61` (PI), `62` (Execução Penal), `63` (Idoso/PcD/Mulher); `30` (correções de Penal) | Já rodados. O catálogo de Execução Penal veio dos `40` a `44`, não de um script próprio                                                                                                                         |
| Dois caminhos para o edital                           | `28` + `edital_pontos` (antigo) contra `50` a `52` (artefato)                                                                                                                                                         | `24` ainda tem o ramo antigo (`--sem-artefato`, e mensagem que manda rodar o `28`); `23` e `24` leem `edital_pontos` (verificar até onde)                                                                    |
| Provável morto / de uma vez só                      | `01`, `01b`, `01c`, `01d`, `04`, `05`, `06`, `08`, `09`, `20`, `25`, `29`, `cmp_gab`, `receptor_local`, `lib_gabarito`                                                                          | `20` e `25` já rodaram e se recusam a repetir; `29` e `30` são correções pontuais; `08`/`09` são só de DH. Candidatos a `legado/`, mas `04`/`05`/`01*` ainda servem para provas novas (decidir) |

Achado: só 4 scripts importam as bibliotecas (`23`, `24`, `44`, `70`). Quase tudo o mais é autônomo e repete a abertura do banco, o que reforça a unificação.

## 2. Documentos

- **Vivos:** `04-DECISOES-CONFIRMADAS`, `01-PENDENCIAS`, `05`, `06`, este `07`, `04-PLANO-MODELO-APOSTILA-V2` (modelo adotado, serve de referência), `03-PLANO-EDITAL-FICTICIO-GERAL` (ciclo por disciplina).
- **Histórico (arquivo morto na Etapa 4):** `00-PLANO-E-ROTEIRO`, `metodo/00-FLUXO` (seções 3 a 5 já são histórico), `metodo/02-DECISOES-EM-ABERTO`, `metodo/03-FLUXO-PROPOSTO-EM-VALIDACAO`, `PROMPT-REPRODUCAO`, `02-CONFERIR-MANUALMENTE` (foto de 12/11/2026, gerador aposentado).
- **Repetição:** o estado do projeto está em três lugares ao mesmo tempo (`CLAUDE.md` item 7, `05` seção 7, `01-PENDENCIAS`); a seção HISTÓRICO das pendências repete o `05`.
- `produtos/modelos/` (A e B): obsoletos pelo próprio aviso; nenhum script os lê.
- `produtos/apostilas/`: sobram **versões antigas** do mesmo produto em Penal (3 arquivos) e DH (4 arquivos: sem sufixo, `[edital classificado]`, `[modelo novo]` e a do Defensor Público). As oficiais são as `[modelo novo]` de 16/11/2026 (os de Penal e DH com outro sufixo são testes antigos). Candidatas a arquivo morto; o usuário decide.

## 3. Matriz de situação por disciplina (banco: 27 provas, 2.276 questões)

"Univ. Analista" = provas FCC de cargo Analista (o universo 7). Todos os comentários estão em `rascunho` (629); nenhuma classificação tem `revisada = 1`.

| Disciplina                                                                                                                                                                     | Questões no banco | Classificadas | Univ. Analista: questões / classif. / comentadas | Comentários marcados | Pontos | Apostila                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------ | ------------- | ------------------------------------------------- | --------------------- | ------ | ------------------------------- |
| Constitucional                                                                                                                                                                 | 211                | 211           | 50 / 50 / 50                                      | 0                     | 42     | sim (perfil 5)                  |
| Processual Civil                                                                                                                                                               | 194                | 194           | 47 / 47 / 47                                      | 1                     | 30     | sim (11)                        |
| Direitos Humanos                                                                                                                                                               | 186                | 186           | 45 / 45 / 45                                      | 11                    | 64     | sim (2; e perfil 1, sem edital) |
| Princípios Institucionais                                                                                                                                                     | 172                | 39            | 39 / 39 / 39                                      | 1                     | 21     | sim (7, junto com Legislação) |
| Penal                                                                                                                                                                          | 171                | 171           | 44 / 44 / 44                                      | 0                     | 55     | sim (3)                         |
| Língua Portuguesa                                                                                                                                                             | 151                | 99            | 99 / 99 / 99                                      | 2                     | 22     | sim (6)                         |
| Processual Penal                                                                                                                                                               | 146                | 146           | 40 / 40 / 40                                      | 3                     | 22     | sim (8, com Execução Penal)   |
| Administrativo                                                                                                                                                                 | 134                | 134           | 43 / 43 / 43                                      | 1                     | 36     | sim (10)                        |
| Civil                                                                                                                                                                          | 130                | 130           | 46 / 46 / 46                                      | 0                     | 50     | sim (4)                         |
| Criança e Adolescente                                                                                                                                                         | 110                | 110           | 20 / 20 / 20                                      | 3                     | 28     | sim (9, bloco ECA)              |
| Execução Penal                                                                                                                                                               | 99                 | 2             | 2 / 2 / 2                                         | 0                     | 33     | dentro de Proc. Penal           |
| Idoso/PcD (disc. 21) + Noções PcD (29)                                                                                                                                       | 25                 | 14            | 14 / 14 / 14                                      | 1                     | 0      | dentro do bloco ECA             |
| Consumidor, Difusos, Criminologia, Filosofia, Tributário, Empresarial, Ambiental, Previdenciário, Saúde, Antidiscriminatório, Agrário, Trabalho, Hist./Geografia Regional | 336                | 0             | 1 / 0 / 0 (Consumidor 1; Tributário 3)           | 0                     | 0      | não                            |
| Conhecimentos Gerais/Administrativos (apoio)                                                                                                                                   | 120                | 0             | 0                                                 | 0                     | 0      | não (outro cargo)              |
| Raciocínio Lógico, Informática, Legislação Institucional, Legislação                                                                                                    | 15                 | 0             | 15 / 0 / 0                                        | 0                     | 0      | fora do edital                  |

Total de comentários marcados "confirmar": 23. Situação das questões: 2.202 válidas, 53 `revisar_texto`, 19 anuladas, 2 desatualizadas.
Gabaritos: 8 conferidos com a FCC; 5 oficiais com conferência datada; **11 ainda preliminares ou "a confirmar"** (DPE-AM 2022 e 2023, MPPI 2025, TJCE 2026 e outras fora do universo).

## 4. Base de regressão (estado em 16/11/2026)

- Perfis 1 a 11, todos confirmados; perfis 2 a 11 por bloco do edital 4 (`DH, PENAL, CIV, CONST, LP, PINST, PPEN, ECA, ADM, PCIV`), universo 7, ano 2026, meia-vida 8, pesos 1/0,5/0,25.
- As contagens por disciplina da seção 3 são a base. Falta, na hora de começar a Etapa 2, **gravar a saída do motor de cada perfil** (por exemplo `23 --perfil N` em arquivo) e a lista dos documentos gerados; sugiro também a etiqueta no git (`base-regressao-2026-11-16`). Não fiz isso agora para não criar arquivos/etiquetas sem você pedir.

## 5. Pontos onde dado novo pode "contaminar" os atuais

1. **Perfil 1 (DH, Defensor Público) usa o universo 1, "Todas as questões".** Qualquer prova nova (inclusive as 33 do lote QConcursos, de Tribunal e MP) entra na conta dele e muda a apostila de DH sem edital. Os perfis 2 a 11 usam o universo 7 (só FCC, cargo Analista) e ficam protegidos de provas de outro tipo, mas **não de provas novas de Analista FCC**: elas mudam as contagens e fazem a regressão divergir de propósito. A regressão precisa distinguir "mudou porque entrou prova" de "mudou porque o código mudou" (por isso a base é código antigo contra código novo sobre o mesmo banco).
2. **Regravação do edital fictício:** o `43` faz cópia nova do banco a cada regravação e vale para todas as disciplinas; o `42` só conhece DH e Penal. Regravar um edital fictício muda `edital_itens` e pode mexer na apostila de quem usa o ramo sem artefato (perfil 1 usa o edital fictício 1).
3. **Scripts que regravam por disciplina** (`21`, `22`, `31`, `58` a `63`) são idempotentes pelo que consta nos cabeçalhos, mas não li cada um: rodá-los de novo pode sobrescrever classificação já revista (`revisada` está 0 em tudo, então a conferência humana ainda não protege nada). (verificar na Etapa 2)
4. **Artefato do edital 4 (Fase E):** mudança em `decisoes.txt` muda quais questões caem em cada bloco; não é contaminação, mas muda a base. Edital 8 (DPE-PB) é rascunho automático e não deve gerar apostila.
5. **Dados em aberto:** lote QConcursos (33 provas baixadas e não ingeridas); decisão sobre mover Idoso/PcD (disciplina 21) para DH (fica para a Etapa 2, a pedido).

## 6. O que cortar (para você decidir; nada foi cortado)

1. Mover para `legado/`: `28` (e o ramo `--sem-artefato` do `24`), `42`, `20`, `25`, `29`, `30`, `cmp_gab`, `receptor_local`; `08`/`09` se DH não voltar a usar. Dúvida: `01*`, `04`, `05`, `06` (servem para ingerir provas novas).
2. Arquivo morto de documentos: os seis "histórico" da seção 2.
3. Apostilas antigas de Penal (2) e DH (3): arquivo morto, mantendo as `[modelo novo]`.
4. `produtos/modelos/`: arquivo morto (mantendo `base-estilos.docx`, que o gerador lê).

Resposta. pode cortar o que você achar melhor.

### Andamento depois da resposta do usuário (16/11/2026)
- **Base de regressão gravada:** `legado/banco/base-regressao-2026-11-16/` (saída do motor dos 11 perfis, tamanhos das apostilas, hash do banco e dos scripts) e etiqueta git `base-regressao-2026-11-16` (aponta para o commit `70f8ac9`; o banco não mudou desde ele). Ao rodar o motor, só a saída do **perfil 1** diferia da versão commitada (a antiga era anterior às correções de dados), o que confirma o risco do universo "Todas as questões"; os perfis 2 a 11 saíram idênticos.
- **Cortes feitos (movidos para `legado/`, nada apagado):** scripts `20`, `25`, `29`, `30`, `cmp_gab`, `receptor_local`; apostilas antigas de Penal (2) e DH (2); Modelo A e B. A apostila de DH "Defensoria Pública FCC" **foi mantida**, porque é a do perfil 1 (ainda ativo). Motor e gerador conferidos depois dos cortes.
- **Cortes adiados:** os 6 documentos históricos ficam até a Etapa 4 (CLAUDE.md, README e `metodo/00` ainda os citam); `28`, `42` e o ramo antigo do `24` ficam para a Etapa 3, depois da Etapa 2.

## 7. Perguntas que ficam para as próximas etapas

- Perfil 1: deve trocar de universo (por exemplo 6, "Defensor Público FCC") antes de entrar prova nova? (Mudar isso muda a apostila dele; só com seu pedido.)
  Não. Na realidade, eu penso que podemos mudar para cara perfil ficar guardado na pasta onde vão ser criadas as apostilas. a pasta então é a materialização daquele perfil, que guarda também o universo escolhido, dentre outros. portanto, eu enxergo que cada perfil é uma escolha do candidato que pode até ser mudada para dentro daquela pasta de perfil. Ex.: Pasta: "Analista Jurídico Defensoria - DPE-AM 2026" → Perfil dentro da pasta: "Analistas FCC.py" ou ".md" ou qualquer outro formato que o app use. Analise e me retorne o que acha.
- Idoso/PcD para DH: no momento da Etapa 2.
- Pelo plano, a Etapa 2 só começa depois de você ver este relatório.
