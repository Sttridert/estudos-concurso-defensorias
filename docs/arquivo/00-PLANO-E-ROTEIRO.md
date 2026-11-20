# Plano e roteiro: material geral de estudo para Defensorias (FCC)

Criado em 12/11/2026. **Leia este arquivo primeiro** ao retomar o trabalho (inclusive depois de perda de contexto). Ele diz o que já foi decidido, o que existe, o que falta e em que ordem fazer.

## 1. O que estamos construindo

Três produtos, nesta ordem de dependência:

1. **Banco de questões** (arquivo SQLite + exportações em CSV): todas as questões das 21 provas FCC de Defensoria de 2021 a 2026, com gabarito, disciplina, assunto e tipo de cobrança. Feito para crescer: novas provas entram sem refazer nada.
2. **Metodologia por disciplina**: os dois guias (análise preditiva; edital, examinadores e revisão) aplicados a um grupo de provas, em vez de um único cargo.
3. **Apostila por disciplina** (Word), no mesmo modelo da "Apostila inicial - Penal e Direitos Humanos". **Começa por Direitos Humanos.** Depois, uma disciplina por vez, reaproveitando os scripts.

## 2. Onde está cada coisa

| O quê | Onde (a partir de `C:\Users\paulo\Downloads\Auxílio Estudos Concurso\`) |
|---|---|
| 21 provas (PDF: 1. edital, 2. caderno, 3. gabarito) | `provas\<ano - órgão - cargo>\` |
| Guias de método (PDF) | `docs\metodo\guias\` |
| Este plano, banco, scripts, apostilas | raiz do repositório (`docs\`, `scripts\`, `produtos\`) |
| Banco de dados | `banco\estudos.db` (o `questoes.db` antigo foi retirado do projeto) |
| Scripts | `scripts\` (numerados na ordem de uso) |
| Texto bruto extraído dos PDFs | `banco\texto-bruto\` |
| Apostilas geradas | `produtos\apostilas\<disciplina>\` |
| Registro de decisões e pendências | final deste arquivo (seções 9 e 10) |

## 3. O que já sabemos sobre os dados (inventário de 12/11/2026)

- **21 provas.** 2021: AM, BA, GO, RR, SC (Defensor). 2022: AM (Analista Jurídico; Assistente 1 e 2), AP, CE, MT, PB (Defensor). 2023: ES, SP (Defensor); AM (Assistente). 2025: AM, RS (Defensor); SP (Analista de Defensoria). 2026: BA, MA, MT (Defensor). Não existe 2020 nem 2024 no QConcursos.
- **Dois jeitos de PDF.**
  - *Com texto* (16 cadernos): extração direta com `pdftotext -enc UTF-8`. Boa qualidade.
  - *Só imagem* (5 cadernos): DPE-AM 2025, DPE-RS 2025, DPE-BA 2026, DPE-MA 2026, DPE-MT 2026. Precisam de OCR (Tesseract com idioma `por` já instalado; Poppler também). Revisar o OCR por amostragem.
- **Gabaritos.** Os de texto são tabelas simples. Os de DPE-AP 2022, DPE-PB 2022, DPE-RS 2025 e DPE-BA 2026 são imagem (OCR). Alguns arquivos são só a "alteração de gabarito" (DPE-SP 2023), e vários são o gabarito **preliminar**. Cada prova pode ter vários **tipos de caderno** (001, 002...) com letras diferentes; é preciso casar o tipo do caderno com o tipo do gabarito.
- **Tamanho.** Provas de Defensor têm cerca de 100 questões. Provas de Analista têm 60 ou 88. Total estimado: 1.500 a 1.900 questões.
- **Quem escreve as questões.** Na maioria, a FCC. Em concursos de Defensor (DPE-SP em especial), uma comissão do próprio órgão. Isso muda a lente 5 (examinador). Registrar em cada prova.
- **Editais.** Há um edital de abertura em cada pasta (alguns vieram da FCC, não do QConcursos). Os editais antigos do DPE-AM (2017 a 2023) e a comparação com o de 2026 já existem em `analista jurídico\editais-anteriores\` e `analista jurídico\00-evolucao-dos-editais.md`.

## 4. Decisões tomadas (a menos que o usuário mude)

1. **Banco completo, classificação por etapas.** Todas as questões entram no banco com a *disciplina*. O *assunto* e o *tipo de cobrança* só são preenchidos para a disciplina em trabalho (começando por DH). Assim o banco já está completo e a classificação fina cresce por disciplina.
2. **Formato do banco: SQLite + CSV.** Um arquivo único, sem servidor, abre em qualquer ferramenta (DB Browser, Python, Excel via CSV). Cada mudança regera os CSV.
3. **Grupos de semelhança (Guia 1, seção 5, passo 2), adaptados ao material geral:**
   - **Grupo A** (peso 1): provas FCC de **Defensor Público** (a carreira-alvo do material).
   - **Grupo B** (peso 0,5): provas FCC de Defensoria para **outros cargos** (Analista, Assistente).
   - Não há grupo C (outras bancas) por ora.
   - Peso por idade: meia-vida de 8 anos, contada em relação a 2026 (Guia 1, lente 6). Os pesos são ponto de partida; o teste retroativo ajusta.
4. **Cada disciplina tem uma lista fixa de assuntos** (8 a 15), montada a partir da *união* dos programas dos editais de Defensor das 21 provas. Não muda depois de começar a classificar (se mudar, reclassificar tudo daquela disciplina).
5. **Questão anulada** fica no banco, marcada, fora das contas. **Questão desatualizada** (lei ou entendimento mudou) fica marcada, com peso 0 nas contas e um aviso na apostila.
6. **Comentário de cada questão** ("O que foi cobrado"): escrito por mim a partir do texto da questão e do gabarito. Toda informação de lei ou jurisprudência que eu não conseguir confirmar em fonte primária leva a marca "confirmar no Planalto/tribunal". Nunca inventar número de súmula, artigo ou julgado.
7. **Gabarito preliminar vs. definitivo.** Usar o definitivo quando existir. Quando só houver o preliminar, marcar a questão com `gabarito_status = preliminar`.
8. **Apostila:** mesma estrutura do modelo (capa, como usar, sumário, edital verticalizado, tabela de frequência, capítulos por tema com cartões de questão, tabela de súmulas e artigos, itens novos do edital). Detalhes na seção 7.

## 5. Esquema do banco (`questoes.db`)

Tabelas (nomes em português, sem acento):

- `provas` (id, ano, orgao, uf, cargo, grupo [A/B], banca_escreve [FCC/comissao_do_orgao/desconhecido], fase, n_questoes, tipos_caderno, fonte_edital, fonte_caderno, fonte_gabarito, gabarito_status [definitivo/preliminar/alterado], ocr [sim/nao], observacoes)
- `questoes` (id, prova_id, numero, disciplina_id, bloco_original, enunciado, alt_a..alt_e, gabarito, situacao [valida/anulada/desatualizada], motivo_situacao, tipo_caderno, texto_bruto, revisada [0/1])
- `disciplinas` (id, nome, nome_no_edital_atual) lista fechada: Constitucional, Administrativo, Tributário, Penal, Processual Penal, Civil, Processual Civil, Empresarial, Consumidor, Difusos e Coletivos, Criança e Adolescente, Direitos Humanos, Princípios e Atribuições da Defensoria, Filosofia e Sociologia do Direito, Língua Portuguesa, Outras.
- `assuntos` (id, disciplina_id, codigo, nome, descricao) a lista fixa de cada disciplina.
- `itens_edital` (id, prova_id, disciplina_id, numero, texto) o conteúdo programático verticalizado de cada edital.
- `item_assunto` (item_edital_id, assunto_id) liga item do edital ao assunto.
- `classificacao` (questao_id, assunto_id, assunto2_id, detalhe [artigo, súmula, caso], tipo_cobranca [lei/sumula/jurisprudencia/doutrina/caso], comentario, pegadinha, origem [manual/modelo], confianca)
- `dispositivos` (id, tipo [artigo/sumula/tratado/caso], referencia) e `questao_dispositivo` (questao_id, dispositivo_id, papel [resposta/distrator]) alimentam a tabela "súmulas e artigos mais cobrados".
- `revisoes_log` (quando, quem, o quê) para rastrear correções.
- Views: `v_frequencia_assunto` (com pesos e faixa de Wilson), `v_cobranca`, `v_presenca_por_prova`.

## 6. Roteiro de execução (fases, com o critério de "pronto")

**Fase 0. Preparação** *(feita em 12/11/2026)*: ler guias, relatório, fichas e apostila-modelo; inventariar PDFs; descobrir o que precisa de OCR. Este plano é o resultado.

**Fase 1. Extração do texto.**
- 1.1 Texto direto dos 16 cadernos e gabaritos de texto → `banco/texto-bruto/`.
- 1.2 OCR (Tesseract `-l por`, 300 dpi, via Poppler `pdftoppm`) dos 5 cadernos e dos 4 gabaritos em imagem.
- Pronto quando: existe um `.txt` por PDF, e uma planilha de controle com páginas e caracteres extraídos.

**Fase 2. Separar as questões e casar com o gabarito.**
- Script que corta o texto em questões (número, enunciado, alternativas A a E), registra o bloco/disciplina original quando a prova o informa, e junta com o gabarito do tipo certo.
- Conferências automáticas: nº de questões por prova bate com o edital; todas têm 5 alternativas; todas têm gabarito; nenhuma letra fora de A a E.
- Pronto quando: o banco tem todas as questões de todas as provas, com 0 pendências nas conferências ou com as exceções listadas na seção 10.

**Fase 3. Disciplina de cada questão.** Pelas faixas de número da prova (quando a prova divide por blocos) ou pela leitura da questão. Conferir por amostra: 10% de cada prova.

**Fase 4. Taxonomia de Direitos Humanos.**
- Verticalizar o programa de DH de cada edital (`itens_edital`), comparar entre editais (Guia 2, cap. 2: item novo, exclusivo, detalhado demais).
- Montar a lista fixa de 8 a 15 assuntos e ligar cada item do edital a um assunto. O relatório do modelo (DPE-AM) tinha 12 assuntos (D01 a D12): usar como ponto de partida e ajustar às provas de Defensor.
- Pronto quando: todos os itens de todos os editais têm assunto.

**Fase 5. Classificar e comentar as questões de DH.** Assunto, assunto 2, detalhe, tipo de cobrança, dispositivos (resposta e distratores), comentário e pegadinha. Em lotes por prova, registrando em `revisoes_log`.

**Fase 6. Análise (Guia 1 e Guia 2) para DH.** Lentes 1 a 9 (a 10, desempenho, fica para quando o usuário resolver questões), teste retroativo, número efetivo de questões, grupos "cai muito / às vezes / pouco". Lente 5 (examinador) só onde houver comissão do órgão. Itens novos do edital (Guia 2).

**Fase 7. Apostila de DH em Word.** Gerar a partir do banco (nada digitado à mão), seguindo a seção 7. Revisar o arquivo aberto no Word (sumário, tabelas, cartões).

**Fase 8. Próximas disciplinas.** Repetir as fases 4 a 7, na ordem a combinar com o usuário (sugestão: Princípios e Atribuições da Defensoria, Penal, Processual Penal, Constitucional...).

## 7. Modelo da apostila (extraído de "Apostila inicial - Penal e Direitos Humanos.docx")

Ordem das partes:
1. Capa: título, órgão/banca, data da prova, quantidade de questões comentadas e intervalo de anos.
2. "Como usar esta apostila" + legenda dos tipos de cobrança (letra de lei, súmula, jurisprudência, doutrina, caso prático) + fonte.
3. Sumário (Título 1, Título 2, Título 3 do Word).
4. Prefácio: **edital verticalizado** (itens numerados, para remeter da tabela de frequência).
5. Título da disciplina: número de questões classificadas e provas usadas.
6. **Tabela da lente 2**: colunas Itens do edital, Tema (capítulo), Qtd., % estimado, Faixa 95%, Grupo. Nota de rodapé sobre pesos e Wilson.
7. "Como ler a disciplina": teste retroativo, tipo de cobrança, mudanças do edital.
8. **Um capítulo por tema**, na ordem da tabela. Cabeçalho do capítulo traz os itens do edital. Dentro dele, **um cartão por questão**: ano/número, prova e tipo, gabarito; faixa "tópico exato"; enunciado; alternativas com a certa em verde; "O que foi cobrado" (base da resposta e por que os distratores erram).
9. Fecho: tabela de **súmulas e artigos mais cobrados** (dispositivo, vezes, onde, tema, distratores) e tabela de **itens novos do edital**.

Estilos do Word do modelo: Heading1 (partes e disciplinas), Heading2 (capítulos/temas), Heading3 (tabelas de apoio), tabelas com sombreamento, cabeçalho e rodapé próprios. Abrir o `.docx` modelo e copiar `styles.xml`, cabeçalho e rodapé para manter a aparência. Geração por script (biblioteca `docx` do Node ou Python); aplicar o skill `docx` do Claude.

Diferenças do material geral em relação ao modelo (DPE-AM Analista):
- A tabela de frequência traz também a coluna "Provas em que apareceu" (lente 9) e o peso do grupo A/B.
- Cada cartão mostra o órgão e o cargo da prova (o modelo só tinha um órgão).
- Um aviso visível em questões marcadas "preliminar" ou "desatualizada".
- Edital verticalizado: o do **concurso mais recente de Defensor** como base, com uma coluna "estava nos outros editais?" (Guia 2).

## 8. Regras de qualidade (valem em todas as fases)

- Nunca contar questão anulada. Nunca ordenar assuntos com menos de 100 questões efetivas: usar três grupos (Guia 1, seção 4.4).
- Declarar sempre a amostra (quantas questões, quantas provas, qual grupo) ao lado de qualquer número.
- Conteúdo legal e jurisprudencial: marcar "confirmar" quando não for de fonte primária.
- Não alterar os PDFs originais nem as pastas já existentes.
- Cada fase termina com um relatório curto no fim deste arquivo (seção 9) e a atualização da seção 10.
- Mensagens ao usuário: linguagem simples, com contexto (o que é, por que importa, o que preciso decidir).

## 9. Registro de execução

- **12/11/2026**: Fase 0 concluída. 21 provas baixadas. Plano criado.

## 10. Pendências e decisões em aberto

- [ ] Confirmar com o usuário: ordem das disciplinas depois de DH.
- [ ] Verificar, prova a prova, quem escreve as questões (FCC ou comissão do órgão), para a lente 5.
- [ ] Conferir se o gabarito de cada prova é definitivo ou preliminar.
- [ ] OCR: revisar por amostra o texto dos 5 cadernos e 4 gabaritos em imagem.

### Registro: Fases 1 e 2 (12/11/2026)
- **Fase 1 concluída.** Texto extraído de 63 PDFs em `banco/texto-bruto/` (OCR nos 5 cadernos-imagem e em 4 gabaritos). Re-OCR dos cadernos DPE-ES 2023 e DPE-SP 2025 (texto embutido ruim); no ES o original continua em uso (`.embutido.txt`) e há uma versão `.ocr300.txt`.
- **Fase 2 quase concluída.** `scripts/02_parse_questoes.py` separa as questões; `scripts/lib_gabarito.py` lê os gabaritos (usa coordenadas para PDFs com vários tipos lado a lado); `scripts/03_criar_banco.py` cria `banco/questoes.db`. Resultado: **1.910 questões em 21 provas**, todas com gabarito do tipo certo do caderno.
- **Gabaritos lidos por imagem (conferir):** DPE-RS 2025, DPE-PB 2022 (captura de tela de celular, baixa resolução) e DPE-AP 2022. Arquivos em `banco/gabaritos_manuais/`.
- **Direitos Humanos:** 143 questões em 17 provas (cabeçalho de cada prova). Disciplina vem do cabeçalho impresso no caderno; DPE-CE 2022 não tem cabeçalho nas questões 91 a 100 (corrigido à mão para "Princípios e Atribuições").
- **Texto incompleto (situacao = revisar_texto):** DPE-ES 2023 (56 questões, 5 de DH), DPE-AM Assistente 2023 (42), DPE-SP Analista 2025 (10, Português), DPE-AM Assistente 2022 (2) (5). Só as de DH importam agora; conferir no PDF.
- **Pendente na Fase 2:** terminar o re-OCR do caderno DPE-AM Assistente 2023 (`scripts/01c_reocr_am23.py`, em segundo plano) e rodar de novo `02` e `03`.

### Registro: verificação de gabaritos e anulações (12/11/2026)
- **Decisões do usuário (12/11/2026):** (1) em DPE-CE 2022 as questões de Direitos Humanos estão dentro do bloco de Constitucional: números 1, 3, 5, 7, 9, 11, 13, 14, 17, 19 e 20 (aplicado em `scripts/03_criar_banco.py`, `OVERRIDES_QUESTOES`); (2) pesquisar quem elabora as questões (regra: a própria FCC; algumas, como a DPE-SP, têm comissão própria); (3) manter o peso 0,5 para provas de Analista/Assistente (grupo B).
- **Site da FCC (relação geral dos gabaritos):** funciona só para concursos mais antigos (códigos dpeam121, dpeba120, dpesc121, dpeam122, dpeap122, dpece121, dpemt221, dpepb121, dpesp222). Script `scripts/04_gabaritos_fcc.py` (POST em `DivulgacaoGabaritoFull.fcc` com cookie e todos os campos do formulário). Conferência linha a linha com o banco: igual em AM21, SC21, AP22, CE22, MT22, SP23. Em PB22 corrigiu a questão 87 (D para C) e confirmou o resto da leitura visual. BA21: o gabarito do QConcursos era do tipo 1 e o caderno é tipo 2; trocado pelo tipo 2 do site. Para 2025 e 2026 o site novo não oferece a relação geral.
- **Anulações e alterações oficiais:** relatórios "Alteração de gabarito e Atribuição de questões" da FCC lidos por `scripts/05_ajustes_gabarito.py` → `banco/ajustes_gabarito.json` (15 ajustes, aplicados no banco). "Atribuição" = ponto dado a todos (tratada como anulada). Prova por prova: BA21 (Q8, Q52), AP22 (Q89, Q91, Q92), ES23 (Q38, Q75), SP23 (Q15 passou a C; Q41 anulada), AM25 (Q25, Q99), SP25 Analista (Q34), MT26 (Q11, Q13, Q63). Em DH: BA21 Q8 e SP25 Analista Q34 estão anuladas.
- **Sem relatório de anulação encontrado:** AM21, SC21, CE22, MT22, PB22, AM22, AM23, RS25, MA26, BA26, GO21, RR21. O gabarito dessas provas é o divulgado (em RS25, MA26 e BA26, o preliminar). Pode haver anulações não registradas. Tentativa de ler "questão anulada" no QConcursos ficou pendente (o navegador parou de responder).
- **Texto incompleto:** não encontrei outras versões utilizáveis dos cadernos (a FCC não publica os cadernos; QConcursos é a única fonte com PDF). Existe a "prova comentada" da Estratégia para DPE-ES (só serve para conferir gabarito, não para copiar texto).

### Regra de formato da apostila (12/11/2026, pedido do usuário)
- **As respostas NÃO ficam marcadas no cartão da questão** (o modelo usava alternativa certa em verde). O usuário quer resolver e depois consultar.
- **Gabarito em local discreto:** lista pequena, em cinza claro, no pé de cada capítulo (ou da página), em formato "Gabarito: 1-C · 2-A ...". O comentário "O que foi cobrado" (que revela a resposta) também vai para o fim do capítulo, depois do gabarito, em bloco separado "Comentários", nunca ao lado do enunciado.
- Questões anuladas: mostrar com aviso "anulada pela banca" e sem gabarito.

### Registro: Fases 4 a 7 para Direitos Humanos (12/11/2026)
- **Fase 4 (assuntos e editais):** 11 assuntos fixos de DH (DH01 a DH11) em `scripts/10_taxonomia_dh.py`. Programas de DH recortados dos 18 editais em `banco/programas_dh/` (`08_programa_dh.py`; extração imperfeita) e matriz tema × edital em `banco/matriz_editais_dh.md` (`09_matriz_editais_dh.py`, por palavra-chave).
- **Fase 5 (classificação e comentários):** 154 questões de DH classificadas (assunto, tipo de cobrança, tópico exato) em `dados/classificacao_dh.csv`; comentários, pegadinhas e dispositivos em `dados/comentarios_dh_DH01..DH10.json`. Origem: leitura das questões por Claude; **a conferir** (campo `origem = modelo (Claude), a conferir`). Itens que dependem de conferência estão marcados "confirmar" no texto.
- **Fase 6 (análise):** `scripts/11_analise_dh.py` → `banco/analise_dh.json`. 152 questões válidas, 18 provas, n efetivo 144,8, 10 temas com questões. Cai muito: igualdade e grupos vulnerabilizados (25,9%) e sistema interamericano (19,9%). Teste retroativo: 53,6% (temporal) e 55,4% (uma prova escondida por vez) contra 40% ao acaso: ganho moderado. 7 temas cobrem 80% das questões (pouca concentração).
- **Fase 7 (apostila):** `scripts/12_gerar_apostila_dh.py` → `apostilas/direitos-humanos/Apostila - Direitos Humanos (Defensorias FCC).docx` (90 páginas). Respostas **não** marcadas nos cartões; gabarito pequeno e cinza no fim de cada capítulo, seguido dos comentários (regra do usuário).
- **Achado importante (GO 2021 e RR 2021):** o gabarito disponível é do Tipo 1 e o caderno é Tipo 4; letras anuladas no banco e resposta dada por análise do conteúdo (marcada "não conferida"). Ver `01-PENDENCIAS.md`.
- **Pontos fracos conhecidos:** lente 5 (examinador) não aplicada; lente 10 (seu desempenho) depende de você resolver questões; classificação por assunto feita por uma só pessoa (sem segunda checagem); extração dos editais por palavra-chave.
- **Como regenerar tudo:** `03_criar_banco.py` → `07_aplicar_tec.py` → `10_taxonomia_dh.py` → `11_analise_dh.py` → `12_gerar_apostila_dh.py` (nessa ordem). Para a próxima disciplina, repetir 08 a 12 trocando a disciplina.

### Registro: ajustes de 12/11/2026 (noite)
- GO 2021 e RR 2021 corrigidos (gabarito do tipo 4 e relatórios). RS 2025, MA 2026 e BA 2026: preliminar presumido mantido (decisão do usuário).
- DPE-AM 2023 Analista Jurídico incluído (grupo B): 19 provas de DH, 159 questões de DH (157 válidas), n efetivo 148,5. Resultado da análise quase igual ao anterior (igualdade 25,5%; interamericano 18,2%).
- Classificação e comentários passaram a usar a chave `prova|número` (IDs mudam a cada nova prova).
- Planilha de revisão (Guia 2, caps. 4 e 5): `apostilas/direitos-humanos/Revisao - Direitos Humanos.xlsx` (`scripts/13_planilha_revisao_dh.py`).
- **Passos dos guias ainda não cumpridos para DH:** lente 5 (examinador, Guia 1) e cap. 3 do Guia 2 (sem informação confirmada sobre comissões); lente 3 (mistura hierárquica; usei pesos por cargo e idade em vez dela); lente 10 e caps. 4 a 6 do Guia 2 (dependem de você: notas 1 a 3, fichas, questões resolvidas).

### Registro: novo design e modelos (12/11/2026, noite)
- **Design:** a apostila de DH foi refeita no design da "Apostila inicial - Penal e Direitos Humanos" (mesmos estilos, tipografia, cores, cartão de questão em tabela, caixas de destaque, tabelas de dados). A biblioteca do design é `scripts/apostila_lib.py`; o gerador é `scripts/12_gerar_apostila_dh.py` (usa uma cópia do docx modelo, `modelos/base-estilos.docx`). A versão anterior do gerador ficou em `scripts/12_gerar_apostila_dh_v1_antigo.py.bak`.
- **Regra de respostas (mantida):** cartão sem resposta; bloco "Respostas e comentários" no fim do capítulo (gabarito pequeno e cinza claro + comentários).
- **Modelos com comentários do Word para o agente:** `modelos/Modelo A - Apostila sem edital (por disciplina).docx` e `modelos/Modelo B - Apostila com edital (por concurso).docx` (gerados por `scripts/14_gerar_modelos.py`) e `modelos/LEIA-ME.md` (roteiro completo, design, armadilhas).

### Registro: planilha de análise preditiva (12/11/2026, noite)
- O usuário apontou que faltava a planilha no formato de `Analise-concurso - Penal e DH.xlsx`. A análise estava só em Python (`11_analise_dh.py`), sem as fórmulas do anexo do Guia 1 nem a lente 10.
- Criada `apostilas/direitos-humanos/Analise-concurso - Direitos Humanos (Defensorias).xlsx` por `scripts/15_planilha_analise.py`: abas Leia-me, Parametros, Questoes (159 linhas, com colunas Resultado e pesos por fórmula), Assuntos, Direitos Humanos (lentes 2 e 10, Wilson, grupos, prioridade), Teste retroativo (temporal e uma prova escondida, por fórmula) e Calc retroativo. Conferida contra o Python (LibreOffice recalculou): n efetivo 148,5; 25,5% e 18,2%; retroativo temporal 56% e uma prova escondida 52%, contra 40% ao acaso.
- A planilha preserva a coluna Resultado se for regerada. Para testar uma prova nova: acrescentar as questões em Questoes (ou regerar pelo banco).

### Registro: organização para continuar (12/11/2026, noite)
- Criado `metodo/00-FLUXO-DE-TRABALHO.md` (guias → insumos → produtos; mapa passo a passo dos dois guias com situação de DH; receita para outra disciplina ou concurso; avaliação dos pontos fracos) e `metodo/guias/` (PDFs dos guias e exemplos antigos de produto).
- `CLAUDE.md` da raiz passou a apontar para o fluxo; memória do projeto atualizada.

### Registro: decisões fechadas e etapa 1 da migração (12/11/2026, noite)
- Decisões confirmadas: `metodo/04-DECISOES-CONFIRMADAS.md`. `CLAUDE.md` da raiz atualizado.
- Etapa 1 feita: `banco/estudos.db` (esquema permanente, migração do legado, backup em `banco/backup/`, relatório em `banco/relatorio_migracao.md`). Perfil piloto gravado em `perfis` (Direitos Humanos, Defensor Público, FCC, estudo geral; confirmado pelo usuário).
- Pedido do usuário (Q13): campos de anotação nos modelos de apostila (resultado por questão, nota por ponto, erros do capítulo).

## 12/11/2026 — Etapa 2 feita (catálogo de pontos de DH)
- `dados/catalogo_pontos_direitos_humanos.csv` (59 pontos, rascunho da IA) gravado em `banco/estudos.db` por `scripts/21_catalogo_pontos_dh.py` (tabelas `pontos`, `editais`, `edital_pontos`, nova `ponto_fontes`). Relatório: `banco/catalogo_pontos_dh.md`.
- Edital fictício «Defensoria FCC · Direitos Humanos» criado. Presença por edital é busca por palavras (indicativo). Aguarda o usuário ver o catálogo antes da etapa 3 (reclassificar as 159 questões).

## 12/11/2026 — Catálogo aprovado; etapa 3 feita (reclassificação)
- Usuário aprovou os 59 pontos (manter os 9 sem presença em editais, "pois caem").
- `scripts/22_classificar_pontos_dh.py` ligou as 159 questões a pontos (principal + 2º ponto quando há), rascunho da IA; 5 questões mudam de assunto em relação ao provisório. Relatório: `banco/questoes_por_ponto_dh.md`. Comentários mantidos.

## 12/11/2026 — Etapa 4 feita (motor genérico)
- `scripts/23_motor_analise.py [--perfil ID] [--legado]`: lê perfil, classifica provas em A/B/C (mesma carreira+banca+cargo = A; mesma carreira+banca, outro cargo = B; resto = C), pesos = grupo × recência, 2º ponto divide a questão, análise por assunto e por ponto (Wilson, grupos, concentração, cobrança, Good-Turing, teste retroativo). Recusa perfil incompleto ou não confirmado. Só lê o banco; grava `banco/analise/`.
- Conferência: `--legado` reproduz o script 11 (n efetivo 148,5; retroativo 55,7% / 51,8%).
- Resultado novo (pontos): assuntos 54,6% / 55,4% contra 40% ao acaso; pontos (top 10) 20,6% / 17,3% contra 17,2% = sem ganho (pontos são finos demais para prever).

## 12/11/2026 — Etapa 5 feita (apostila a partir dos pontos)
- `scripts/24_gerar_apostila.py [--perfil ID]` (genérico): capítulos = assuntos em ordem do motor; dentro, questões agrupadas por ponto; prefácio = pontos do edital fictício; comentários lidos do banco. Saída: `apostilas/direitos-humanos/Apostila - Direitos Humanos (Defensoria Pública FCC) - versao pontos.docx` (118 págs.; 159 questões; 156 dispositivos). A apostila antiga de 112 págs. foi mantida para comparar. Etapa 6 (aposentar legado) aguarda aprovação do usuário.

## 12/11/2026 — Etapa 6 feita (legado aposentado)
- Scripts 02, 03, 07, 10, 11, 12 (+.bak), 13, 15 movidos para `scripts/legado/` (com LEIA-ME). `banco/questoes.db` mantido como histórico. CLAUDE.md, `04-DECISOES-CONFIRMADAS.md` e `00-FLUXO-DE-TRABALHO.md` atualizados. Migração com Direitos Humanos concluída.

## 12/11/2026 — Universo de questões
- `scripts/25_universos.py` cria `universos` e `perfis.universo_id` (6 universos de partida; perfil 1 = Todas as questões). Motor `23` ganhou `--universo ID` e `--comparar`; `24` declara o universo e os avisos. Teste com DH: como todas as provas são de Defensoria FCC, os universos dão o mesmo resultado (assuntos 54,6% / 55,4%); "Defensor Público" tem 16 provas e n efetivo 134,8. Tabela: `banco/analise/direitos_humanos_perfil1_comparacao_universos.md`. Universo sem questão (ex.: Promotor, ainda sem provas) é recusado com mensagem clara.

## 12/11/2026 — Grupo A com órgão
- `23_motor_analise.py`: `perfis.orgao` passa a definir o grupo A (mesmo órgão, carreira, banca e cargo). Teste com DH: DPE-AM = 2 provas A; DPE-PB = 1 prova A (DPE-PB 2022); órgão sem prova no banco = aviso e regra geral. Sem órgão, os resultados não mudaram (n efetivo 148,5; 54,6% / 55,4%).

## 12/11/2026 — Ingestão de provas novas (pasta provas/NOVAS)
- Escritos `scripts/26_ingerir_prova.py` e `27_organizar_provas_novas.py` (ver CLAUDE.md). Manifesto: `dados/provas_novas_manifesto.json`.
- Ingeridas 5 provas (300 questões): DPE-AM Analista Jurídico 2018, 2019 e 2022 (2) (IV Concurso, ago/2022); MPPI 2025 Analista Ministerial (Ministério Público); TJCE 2026 Analista Judiciário (Judiciário).
- A prova de fev/2022 (III Concurso) já estava no banco (mesmo caderno, mesmo gabarito); seus arquivos extras foram para `provas/2022 - DPE-AM - Analista Jurídico/outros/`.
- Pastas vazias em NOVAS (aguardando arquivos): TJSC 2020 Analista, TJCE 2022 Oficial, TJBA 2023.
- Gabaritos: DPE-AM 2018, 2019 e 2022 (2) conferidos por duas fontes (txt por tipo de caderno e PDF); MPPI e TJCE são preliminares, transcritos das imagens dos PDFs (a camada de texto estava errada: 46 de 60 divergências no TJCE).
- 17 questões de Direitos Humanos (2018, 2019, 2022-2) foram ligadas a pontos (rascunho da IA); ainda sem comentário. As demais disciplinas ficam sem classificação até ganharem catálogo.

## 12/11/2026 — Teste com edital real: DPE-AM 2026, Analista Jurídico, Direitos Humanos
- Edital 01/2026 (VI Concurso, DPE-AM, FCC) copiado para `provas/2026 - DPE-AM - Analista Jurídico (edital, sem prova)/`. Programa de DH (itens 1 a 11) mapeado em `dados/edital_dpeam2026_analista_dh.json` e importado por `scripts/28_importar_edital.py`: 49 pontos no edital, 10 fora (DH02.03, DH05.01, DH08.05, DH09.03, DH10.01, DH10.03, DH10.04, DH10.06, DH10.08, DH10.10).
- Comparação por frases: o programa de DH de 2026 é igual ao de 2023 (de 2019 a 2023 não mudou; 2018 era maior). Única mudança de conteúdo: saiu o item "Programa Estadual de Direitos Humanos do Estado".
- Universo novo "Analista FCC" (banca FCC, cargo começando por "Analista"); perfil 2 criado (DH · Analista Jurídico · FCC · DPE-AM 2026), **aguardando confirmação do usuário**. Amostra de DH nesse universo: 36 questões em 6 provas (5 DPE-AM Analista Jurídico + DPE-SP 2025 Analista de Defensoria); n efetivo ≈ 34.
- `24_gerar_apostila.py` aprendeu a trabalhar com edital real (prefácio por itens do edital, pontos fora do edital, só questões do universo) e a imprimir "sem dados suficientes" quando o teste retroativo não roda.
- Correção: o `1. edital.pdf` da pasta `provas/2022 - DPE-AM - Analista Jurídico` é o do IV Concurso; o do III (da prova de fev/2022) está em `outros/`; o caminho no banco foi corrigido.

## 12/11/2026 — Apostila gerada: DH, Analista Jurídico, FCC, DPE-AM 2026 (universo Analista FCC)
- Perfil 2 confirmado pelo usuário no chat (universo só Analista FCC, estatística e questões). Apostila: `produtos/apostilas/direitos-humanos/Apostila - Direitos Humanos (Analista Jurídico FCC · DPE-AM 2026).docx` (36 questões de 6 provas; n efetivo 33,7; DH06 "cai muito" com 22%; assuntos sem questão no universo: DH01 e DH11, ambos no edital). Teste retroativo: temporal sem dados; uma prova escondida 50% contra 44% ao acaso (ruído).
- Escritos `scripts/29_comentarios_dh_provas_novas.py` e `dados/comentarios_dh_novas_provas.json`: comentários (rascunho da IA) das 17 questões de DH de 2018, 2019 e 2022-2; 6 marcados para confirmar (2018 Q49; 2019 Q50, Q53, Q55; 2022-2 Q52 e Q54). A apostila geral (perfil 1) foi regerada com as 17 questões.
- Comparação feita a pedido do usuário: ampliar o universo para todas as provas não piora a previsão das provas de Analista (50% em ambos), mas DH06 cai de 20% (Analista) para 8% (Defensor): risco de diluir esse assunto. Só Defensor Público prevê pior (37%, abaixo do acaso).

## 13/11/2026 — Apostila de Direito Penal: Analista Jurídico, FCC, DPE-AM 2026 (universo Analista FCC)
- Correções no banco (`scripts/30_corrigir_questoes_penal_analista.py`; backup `banco/backup/estudos_antes_penal_2026-11-13.db`): DPE-AM 2023 Q41 a Q47 reconstituídas do OCR (41 a 45 Penal, 46 e 47 Processo Penal); DPE-AM 2018 Q41 a 43 passaram a Processo Penal e Q44 a Execução Penal; limpeza de rodapés e OCR.
- Catálogo de Penal (rascunho da IA, aprovado pelo usuário): 14 assuntos (PE01 a PE14) e 53 pontos; 42 questões classificadas (`scripts/31_catalogo_e_classificacao_penal.py`; CSVs em `dados/`).
- Edital: `dados/edital_dpeam2026_analista_penal.json` (9 itens, 71 frases literais; todas ligadas a pontos; nenhum ponto fora do edital). Erros do próprio edital mantidos: "Lei nº 15.343/06" (Drogas) e "Lei nº 16.869/2019" (Abuso de Autoridade).
- Perfil 3 confirmado pelo usuário. Comentários das 42 questões (`dados/comentarios_penal_analista.json`, gravados por `scripts/32_gravar_comentarios.py`, genérico): 6 marcados para confirmar.
- Motor: 42 questões em 8 provas (A 5, B 1, C 2), n efetivo 37,4; PE08 Pena "cai muito" (20%); teste retroativo só "uma prova escondida": 43,8% contra 30,8% ao acaso (menos de 5 provas por rodada: ruído).
- Apostila: `produtos/apostilas/direito-penal/Apostila - Direito Penal (Analista Jurídico FCC · DPE-AM 2026).docx` (52 págs.). Cartões de PE09.01 (2023 Q42) e PE07.03 (2022-2 Q45) mostram só o código (guardrail: o trecho do edital entregaria a resposta).

## 15/11/2026: caderno de Direito Civil (piloto do modelo final)
- Perfil 4 criado e confirmado (Direito Civil, Analista Jurídico, FCC, DPE-AM 2026, universo Analista FCC, 46 questões). Caderno `[modelo novo]` gerado com `24_gerar_apostila.py --perfil 4 --edital-artefato 4`; o formato final está nas decisões 36, 38 e 39 de `docs/metodo/04-DECISOES-CONFIRMADAS.md`.
- Descoberto que Civil não tinha comentários no banco; escritos e gravados os 46 (rascunho da IA, 10 marcados para confirmar). Texto de 11 questões corrigido a partir da imagem do caderno (DPE-AM 2023 Q33 a Q35; MPPI 2025 Q45 a Q52).
- O script 24 agora gera o sumário com número de página (duas passadas, lendo as páginas do PDF via LibreOffice).
- Regerados no formato final: Penal (perfil 3, 39 páginas) e DH (perfil 2, 44 páginas). Pendente: 12 comentários que faltam (9 DH, 3 Penal), texto a conferir de 11 questões de Penal e comentários das demais disciplinas.
- 15/11/2026 (depois): escritos os 11 comentários que faltavam em DH (9) e Penal (2; o 12º era a Q40 de 2023, que estava com dados errados e foi corrigida). Penal e DH regerados (Penal 44 questões, 84 dispositivos; DH 45 questões, 51 dispositivos).
- 15/11/2026 (conferência de texto): 18 questões (11 de Penal e 7 de Civil do TJCE e MPPI) comparadas com a imagem do caderno e liberadas; Penal e Civil regerados sem nenhum aviso "TEXTO A CONFERIR".

## 15/11/2026: caderno de Direito Constitucional (Analista Jurídico, DPE-AM 2026, universo Analista FCC)
- Consulta ao banco: 41 questões de Constitucional no universo (DPE-AM 2018, 2019, 2022, 2022-2 e 2023; MPPI 2025; TJCE 2026), nenhuma com comentário, 16 em `revisar_texto`.
- Texto conferido com a imagem do caderno (ou a camada de texto do PDF) antes de qualquer correção; 11 questões corrigidas e as demais liberadas (`55_aplicar_correcoes_texto.py`).
- 41 comentários escritos e gravados com `32_gravar_comentarios.py` (rascunho da IA, 5 marcados para confirmar).
- Perfil 5 criado e confirmado pelo usuário; motor (`23`) e gerador (`24 --edital-artefato 4`) rodados: 41 questões, 98 dispositivos, nenhum aviso de texto, de tópico sem julgamento ou de tag desconhecida.

## 15/11/2026 (depois): correção da DPE-SP 2025 e início de Língua Portuguesa
- Achado: as Q1 a Q16 da DPE-SP 2025 Analista estavam mal montadas no banco (parágrafos do texto lidos como questões; Constitucional em Língua Portuguesa). Reconstruídas pela imagem do caderno, com gabarito conferido; Constitucional passou de 41 para 50 questões, comentadas (lote 3) e o caderno foi regerado.
- Língua Portuguesa: bloco LP acrescentado ao artefato do edital (script 56). Próximos passos: tabela de texto-base e sublinhados, catálogo, classificação, comentários, perfil e caderno.

## 15/11/2026: caderno de Língua Portuguesa (Analista Jurídico, DPE-AM 2026, universo Analista FCC)
- Texto das 99 questões de LP do universo conferido pela imagem (OCR corrigido à mão nas provas escaneadas; `dados/correcoes_texto.json`, script 55). Marcação `<u>…</u>` (sublinhado) e `<b>…</b>` (destaque) gravada no texto; lacunas saem como linha sublinhada.
- Tabela nova **`textos_base`** (17 textos de 8 provas; `dados/textos_base.json`, `57_gravar_textos_base.py`). O gerador mostra o texto no 1º cartão que o usa; os demais remetem a ele.
- Catálogo de LP (`58_catalogo_lingua_portuguesa.py`): 9 assuntos (LP01 a LP09) e 22 pontos. Edital: bloco LP acrescentado ao `programa.json` (`56_acrescentar_bloco_ao_programa.py`), decisões LP-001 a LP-021 em `decisoes.txt`, artefato com 550 frases, `52` rodado.
- Classificação das 99 questões (`59_classificar_lingua_portuguesa.py`, rascunho da IA) e 99 comentários (`dados/comentarios_lp_lote1.json` a `_lote3.json`, sem dispositivos); tags novas Interpretação de texto e Gramática (só na legenda quando usadas).
- Perfil 6 confirmado pelo usuário; motor: n efetivo 88,1; teste retroativo assuntos 82% contra 50% do acaso, pontos 86% contra 56%. Caderno gerado: 89 páginas, 99 questões, sem texto a conferir. Pendente: Princípios Institucionais (Legislação da Defensoria e Conhecimentos Jurídicos e Institucionais), ainda sem catálogo.

## 15/11/2026: caderno de Princípios e Atribuições Institucionais da Defensoria (perfil 7, mesmo perfil de Língua Portuguesa)
- Edital: bloco `PINST` acrescentado ao `programa.json` com dois itens (Legislação da Defensoria; Conhecimentos Jurídicos e Institucionais; 16 frases ipsis litteris; `56_acrescentar_bloco_ao_programa.py` ganhou `--item`/`--rotulo` e não divide frase em "n.º" nem em "1.762"). Decisões PINST-001 a 016 e FORA PI06.01 a 03 em `decisoes.txt`; artefato com 566 frases, 0 sem julgamento; `52` rodado.
- Catálogo (`60_catalogo_principios_institucionais.py`): 6 assuntos e 21 pontos (PI01 a PI05 = 18 pontos do edital; PI06 = 3 pontos cobrados em 2018 a 2023 e fora do edital 2026: crimes contra a Administração, improbidade e CF fora dos arts. 5º, 37 e 134).
- Texto das 39 questões do universo conferido (PDF e imagem; rodapés removidos, 2023 Q15 a Q20 refeitas pela imagem; lacunas em `<u>`). Classificação (`61_classificar_principios_institucionais.py`, rascunho da IA) e 39 comentários (`dados/comentarios_pi_lote1.json` e `_lote2.json`; 28 marcados `pendente_confirmacao`, porque o texto da LC 01/1990, da Lei 4.077/2014 e da Constituição do Amazonas não foi achado na web).
- Sete questões são de Código Penal ou Improbidade (2018 Q19; 2019 Q15, Q16, Q18; 2022 Q17; 2022-2 Q20; 2023 Q18) e uma de CF fora do art. 5º (2018 Q20): saem na seção "Temas cobrados anteriormente que não aparecem no edital atual". As 9 questões da DPE-SP (leis paulistas) entram pelo tema equivalente.
- Gerador: a coluna Nº do edital verticalizado alarga quando o rótulo é longo. Motor: n efetivo 37,5; teste retroativo temporal indisponível (poucas provas de Analista), leave-one-out 97% nos assuntos (acaso 80%). Caderno: 33 páginas, 39 questões, 26 dispositivos.
