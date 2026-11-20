# Plano: modelo novo da apostila (v2)

Pedido do usuário em 14/11/2026. Objetivo: estudo mais rápido, lendo de cima para baixo. O usuário responde a questão e, logo abaixo, confere resposta e comentário, sem ir ao fim do capítulo.
Regra de trabalho: **perguntar ao usuário antes de gerar qualquer apostila** (memória `perguntar-antes-de-gerar-apostila`). Uma etapa por vez; cada etapa termina com resultado que o usuário vê antes da próxima.

## O que o usuário pediu (decisões a registrar)
1. **Resposta e comentários na linha de baixo de cada questão**, dentro da mesma tabela do cartão, e não mais no fim do capítulo. A linha mantém a formatação atual do bloco de respostas (modelo: rótulo "O QUE FOI COBRADO" + tag, "Tópico exato", texto do comentário, "Pegadinha", "Dispositivos").
2. **Gabarito pequeno e cinza, no fim do texto do comentário** (mesma fonte que hoje tem na lista do início da tabela de respostas).
3. **Sem linha de cabeçalho** "RESPOSTAS E COMENTÁRIOS · Capítulo N". A lista de gabarito do capítulo deixa de existir.
4. **Tópico exato vai para a linha de resposta** e **sai do cartão**. A faixa "TÓPICO EXATO + tag (lei_seca, caso_concreto)" abaixo do cabeçalho do cartão é excluída (evita informação duplicada).
5. **Tópico exato com a frase inteira do edital**, com o trecho que motivou a classificação **grifado** (cor que combine com o tema azul/vinho). Hoje aparece só o trecho solto (ex.: "9. … espécies …"). Pode revelar a resposta: o risco é raro e fica mitigado porque o tópico agora só aparece na linha de resposta. **O guardrail que cortava o tópico para só o código sai.**
6. **Número da questão à esquerda** no cabeçalho do cartão (hoje "Questão 1.7" fica à direita).
7. **"Dispositivos, tratados e casos mais cobrados" organizado por fonte:** uma linha por lei/Constituição/código (tudo o que já caiu daquela norma), uma por súmula, uma por caso, uma por tratado etc., para o usuário abrir o material de estudo e ir por ordem.
8. **"O que mudou no edital e o que ficou de fora" em tabela.**

## Respostas do usuário (14/11/2026)
- **Número à esquerda:** é o "1.7" (capítulo.sequência) que vai para o começo do cabeçalho: `1.7 · 2026 · TJCE · Questão 55`. Confirmado.
- **Resumo do capítulo e linha de dispositivos de cada ponto:** **eliminar** (não ficam em lugar nenhum). Saem também as regras "Descrição do capítulo" do CLAUDE.md.
- **Tag (lei_seca, caso_concreto etc.):** fica no rótulo "O QUE FOI COBRADO [tag]" da linha de resposta. Confirmado.

## Achado: tags fora da legenda da capa (verificado em 14/11/2026)
**Não é erro de leitura (parsing); é vocabulário misturado.** A legenda da capa e o mapa `TAG` de `apostila_lib.py` só conhecem 5 valores: `lei/tratado` (Letra de lei), `sumula`, `jurisprudencia`, `doutrina` e `caso pratico`. Em `classificacao.tipo_cobranca` convivem dois vocabulários:
- **Direitos Humanos (antigo):** `lei/tratado` (112), `caso pratico` (26), `jurisprudencia` (23), `doutrina` (14), `sumula` (1), mais 10 `lei_seca`. Aparecem certo.
- **Todas as outras disciplinas (Penal, Constitucional, Administrativo, Civil, Proc. Civil, Proc. Penal, ECA):** `lei_seca` (819 questões) e `caso_concreto` (107), que não existem no `TAG`. Quando o valor não está no mapa, o gerador mostra o texto cru (`lei_seca`, `caso_concreto`) em cinza. No Penal: 105 `lei_seca` e 30 `caso_concreto` aparecem assim.
- **Súmula quase não é usada:** só 1 questão em todo o banco tem `sumula`; o resto das questões de súmula foi marcado `jurisprudencia` ou `lei_seca`. Na legenda, "Súmula" quase nunca aparece.

**Decisões do usuário (14/11/2026):**
1. **O código interpreta na hora de gerar a apostila.** O banco **não** é padronizado agora (nada de `UPDATE` em `classificacao.tipo_cobranca`).
2. **Súmula continua na legenda.** A reclassificação das questões que cobram súmula fica **para o futuro**. Obs. do usuário: algumas questões cobram mais de uma coisa ao mesmo tempo (ex.: lei e súmula); isso também fica para quando a reclassificação for feita (hoje só cabe um tipo por questão).

**Correção (Etapa 1), só no código (`apostila_lib.py`):** mapa de equivalência `lei_seca` → Letra de lei; `caso_concreto` → Caso prático; `lei/tratado`, `sumula`, `jurisprudencia`, `doutrina` e `caso pratico` continuam valendo. Valor desconhecido: o gerador avisa no terminal e usa "Sem tipo" (nunca mostra o texto cru).

## Etapas

**Etapa 0. Registro (curta).**
Acrescentar a decisão 36 em `docs/metodo/04-DECISOES-CONFIRMADAS.md` e trocar, em `CLAUDE.md`, as regras "Regras do usuário para as apostilas", "Tópico exato do cartão" e "Descrição do capítulo" (a resposta passa para a linha de baixo; guardrail removido; frase inteira com grifo).

**Etapa 1. Cartão novo, sem resposta ainda (`apostila_lib.cartao`, `24_gerar_apostila.py` por volta das linhas 380-395).**
Número à esquerda; excluir a faixa de tópico exato e tag; corrigir as tags (mapa de equivalência, aviso de valor desconhecido; migração do banco só com o OK do usuário). Resultado visível: só o cartão da questão e a legenda da capa.

**Etapa 2. Linha de resposta dentro da tabela do cartão (`apostila_lib.bloco_respostas` vira linha do cartão).**
- Nova função de linha (mesma largura da tabela, fundo claro) com: rótulo "O QUE FOI COBRADO" + tag, "Tópico exato", comentário, "Pegadinha", "Dispositivos" e, ao fim do comentário, "Gabarito: X" pequeno e cinza.
- Linha pode quebrar entre páginas (hoje `nao_quebrar=True` em `tr`; comentário longo não pode empurrar a linha toda para a página seguinte).
- Remover o bloco de respostas do fim do capítulo, o cabeçalho "RESPOSTAS E COMENTÁRIOS", o resumo "O que foi cobrado neste capítulo" e a linha de dispositivos de cada ponto (decisão do usuário: eliminar).
- A tag usa o rótulo "O QUE FOI COBRADO [tag]", com o nome e a cor da legenda da capa.
- Questão anulada: aviso ANULADA continua; sem gabarito.
- Questão sem comentário: linha só com tópico exato e gabarito.

**Etapa 3. Tópico exato com frase inteira e grifo (`topico_edital` e `lib_edital_classificado.py`).**
- O loader passa a entregar, em cada trecho, também a **frase inteira** (`f`) além do trecho (`t`). Para o fluxo antigo (`edital_pontos`), a frase vem do `programa`.
- `topico_edital` escolhe o melhor trecho como hoje (semelhança com a questão), mas devolve `código · item. FRASE INTEIRA` com o trecho grifado (cor de realce do tema). Se o trecho já é a frase toda, sem grifo.
- Sem edital real: nome do ponto (como hoje).
- Retirar o descarte por "palavra da resposta" (`palavras_da_resposta`/`topico_seguro`), mantendo só o que for usado pelo fluxo sem edital, se o usuário quiser.

**Etapa 4. Dispositivos por fonte (`24_gerar_apostila.py`, linhas ~400-410).**
- Inspecionar primeiro os textos de `comentarios.dispositivos` das disciplinas já comentadas (DH e Penal) para definir as famílias: Constituição, códigos (CP, CPP, CPC, CC), leis (nº e nome), súmulas (STF, STJ, vinculantes), temas de repercussão e IAC, casos (Corte IDH, STF, STJ), tratados e convenções, outros.
- Tabela por família: **Fonte** | **Artigos / itens que já caíram** (em ordem do texto da norma) | **Vezes** | **Onde** (prova e questão).
- Dispositivo que não encaixar em família vai para "Outros", visível, para o usuário ver e corrigirmos a regra.

**Etapa 5. "O que mudou no edital e o que ficou de fora" em tabela.**
Colunas sugeridas: Situação (fora do edital, no edital sem questão, novo) | Ponto | Questões | Observação.

**Etapa 6. Teste e conferência (perguntar antes de gerar).**
Gerar DH e Penal (DPE-AM 2026, `--edital-artefato 4`), converter com LibreOffice, renderizar páginas e conferir: cartão, linha de resposta, grifo, quebra de página em comentários longos, tabela de dispositivos. Mostrar ao usuário.

**Etapa 6B. CANCELADA (14/11/2026, decisão do usuário):** os `Modelo A` e `Modelo B` não são lidos por nenhum script (o gerador usa só `base-estilos.docx`); não vale o esforço de reconstruí-los. Feito no lugar: aviso de "obsoleto" no topo de `produtos/modelos/LEIA-ME.md`. O texto abaixo fica só como histórico.

**Etapa 6B. Atualizar `produtos/modelos/` (faltava no plano; apontado pelo usuário em 14/11/2026).**
Hoje a pasta tem `Modelo A - Apostila sem edital (por disciplina).docx` e `Modelo B - Apostila com edital (por concurso).docx` (exemplos fixos, com campos `[Disciplina]` e comentários do Word para o agente), `LEIA-ME.md` e `base-estilos.docx`. Tudo mostra o desenho antigo (faixa de tópico exato no cartão; respostas no fim do capítulo), e o gerador antigo dos modelos foi aposentado.
- Criar `scripts/54_gerar_modelos.py`, que monta os Modelos A e B com `apostila_lib` (a mesma biblioteca do `24`), já no modelo v2: cartão com número à esquerda, linha de resposta com tag, tópico exato com frase inteira e grifo, gabarito pequeno e cinza no fim, sem bloco de respostas no fim do capítulo; dispositivos por fonte e "o que mudou" em tabela (depois das Etapas 4 e 5).
- Modelo A = prefácio sem edital (edital fictício). Modelo B = prefácio com edital real (edital verticalizado com coluna Pontos, frases de outros blocos, trechos literais).
- Os comentários do Word do modelo antigo (explicações para o agente) viram uma caixa "Notas para o agente" no fim, ou um `LEIA-ME`, a combinar com o usuário (python-docx não cria comentários do Word de forma confiável).
- Reescrever `produtos/modelos/LEIA-ME.md`: desenho novo (cartão em 3 linhas), regra "a resposta só aparece na linha de baixo", fluxo da fase 5 (scripts 50 a 52 e 24 `--edital-artefato`), tags, e **retirar os scripts que não existem mais** (03, 07, 10 a 15 etc.).
- `base-estilos.docx` **não muda** (só estilos, cabeçalho e rodapé; o gerador `24` e o `44` o usam).
- Fazer **depois** de o usuário aprovar o Penal novo, para não refazer os modelos se o desenho ainda mudar. Atualizar `CLAUDE.md` (linha da estrutura) e `docs/01-PENDENCIAS.md` (item "Modelos de apostila (A e B)").

**Etapa 7. Fechamento.**
Atualizar README, `docs/01-PENDENCIAS.md` e CLAUDE.md; depois decidir com o usuário se o fluxo antigo (script 28 e `edital_pontos`) sai de vez. Commit só a pedido.

## Ordem sugerida e tamanho
0 (curta) e 1 juntas; 2 (a maior); 3; 4; 5; 6 e 7. Cada uma cabe numa sessão curta. Nada disso muda o banco nem o artefato do edital.

## Teste rápido pedido pelo usuário: refazer a apostila de Direito Penal no modelo novo (14/11/2026)
O usuário quer ver o Penal (perfil 3, DPE-AM 2026, `--edital-artefato 4`) no modelo novo **antes de terminar todas as etapas**, porque os tokens da sessão estão quase no fim. Ordem reduzida, para chegar a um Word que dê para avaliar:
1. **Etapas 0 e 1** (registro + cartão + tags).
2. **Etapa 2** (linha de resposta no cartão; remove o bloco do fim do capítulo).
3. **Etapa 3** (tópico exato com frase inteira e grifo).
4. **Gerar o Penal e conferir** (versão reduzida da Etapa 6: converter em PDF e olhar cartão, linha de resposta, grifo e quebra de página).
5. **Ficam para depois**, nesta ordem: Etapa 4 (dispositivos por fonte), Etapa 5 (tabela "o que mudou"), Etapa 7. Enquanto não forem feitas, a apostila de teste mantém essas duas seções como estão (marcar no terminal e na pendência).

**Cuidados do teste:**
- Há um arquivo de trava (`.~lock.Apostila - Direito Penal ... .docx#`): a apostila antiga do Penal está **aberta no Word ou no LibreOffice**. Para não falhar nem sobrescrever, a versão nova sai com **sufixo próprio** (`[modelo novo]`) e a antiga não é tocada.
- Se os tokens acabarem no meio, o plano acima diz onde parou: a próxima sessão retoma pela primeira etapa ainda não marcada como feita.

**Progresso (atualizar a cada etapa):** Etapa 0 [x] · Etapa 1 [x] · Etapa 2 [x] · Etapa 3 [x] · Teste Penal [x, gerado e conferido em PDF por amostra de 2 páginas em 14/11/2026: `produtos/apostilas/direito-penal/Apostila - Direito Penal (...) [modelo novo].docx`] · Etapa 4 [x, dispositivos por fonte, Penal gerado em 14/11/2026] · Etapa 5 [x, tabela] · Etapa 6B (cancelada; aviso de obsoleto no LEIA-ME) [x] · Etapa 7 [ ]

**Segurança da classificação (14/11/2026):** corrigido o "fora do edital" indevido no Penal; criados `FORA`, `COBRE` e "sem julgamento" (decisão 37; scripts 51 e 52, tabela `edital_pontos_fora`, loader e Parte 2 do prefácio no `24`). Penal gerado de novo.

**Feito além do plano:** cabeçalho do cartão preso ao enunciado (`keep_next`) para não ficar sozinho no fim da página; linha "Detalhe:" (o detalhe da questão, que o modelo antigo mostrava como "Tópico exato") mantida na linha de resposta; "Anote aqui os erros" mantido no fim do capítulo; o `24_gerar_apostila.py` agora salva sempre com o sufixo " [modelo novo]". Código novo: `apostila_lib.tag_de`, `apostila_lib.cartao` (com `resp`), `apostila_lib.anote_erros`, `24_gerar_apostila.topico_edital_xml`; `lib_edital_classificado` entrega a frase inteira (`f`) em cada trecho. **DH no modelo novo: gerado e conferido por amostra de 2 páginas em 14/11/2026** (`produtos/apostilas/direitos-humanos/Apostila - Direitos Humanos (...) [modelo novo].docx`, 58 páginas, 45 cartões); corrigido o resumo "Tipo de cobrança (ponderado)", que listava `lei/tratado` e `lei_seca` como tipos separados (agora soma em "Letra de lei"). Dados a limpar no futuro (`comentarios.dispositivos`): itens soltos como "Estatuto de Roma|1998" e "2º Protocolo...|1989, abolição da pena de morte", e "Súmulas sobre direito ambiental (conferir número)". **Não verificado:** capítulo muito longo/quebras de página além das 2 páginas vistas; sem edital real (`topico_seguro`) no modelo novo.

## Em aberto (não faz parte deste plano)
Conferência do rascunho do artefato (`rascunho.html`) e regra de homologação das propostas de tópicos (`NP-...`); ver `docs/01-PENDENCIAS.md`.
