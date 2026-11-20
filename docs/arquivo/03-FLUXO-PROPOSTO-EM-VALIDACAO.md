# Fluxo proposto pelo usuário: validação contra os guias e instrumentos necessários

Criado em 12/11/2026. **Rascunho em validação**: nada daqui foi implementado ainda; falta o usuário confirmar as decisões da seção 6. Ver também `02-DECISOES-EM-ABERTO.md` (onde o usuário escreveu a proposta).

## 1. Veredito
O fluxo proposto **faz sentido e é uma boa adaptação do Guia 1** para uso geral. Ele muda duas coisas importantes: (1) o **banco de dados** vira a fonte única da verdade (taxonomia, conteúdo programático, classificação, comentários), e as planilhas viram **visões** dele; (2) os **pesos** passam a depender de um **perfil-alvo** (banca, carreira, cargo, órgão, examinadores) informado pelo usuário, em vez de serem fixos. Isso é compatível com o Guia 1 e resolve a limitação atual (scripts presos a Direitos Humanos). Três ajustes são necessários: ver seções 2 e 3.

## 2. Correção importante: nem toda lente é um "peso que se multiplica"
O usuário supôs que cada lente é um peso multiplicado ao valor da questão, valendo 1 quando faltar. Isso é **verdade só para duas lentes**. As outras têm outra natureza (conferido no Guia 1):

| Lente | Natureza no Guia 1 | Quando falta | Entra como |
|---|---|---|---|
| 1. Estrutura do edital | Parâmetros (nº de questões por disciplina, valor, nota mínima) | Usar a média histórica por prova | Parâmetro, não peso |
| 2. Frequência | Conta o peso das questões por assunto, em % com faixa de Wilson | — | Resultado |
| 3. Mistura com provas parecidas | **Fórmula de mistura**: (vezes no cargo + m × % da banca) ÷ (questões do cargo + m), com m entre 10 e 20 | Sem grupo parecido, não há o que misturar | Fórmula no nível do assunto, não peso |
| 4. Tipo de cobrança | Diagnóstico (lei, súmula, jurisprudência, doutrina, caso) | — | Resultado descritivo |
| 5. Examinador | **Não gera número**: sobe de grupo os assuntos ligados ao examinador (Guia 1: "não invente números") | Sem examinador conhecido, **nenhum ajuste** | Ajuste de grupo, não peso |
| 6. Recência | **Peso** 0,5^(idade ÷ meia-vida) | Idade desconhecida: peso 1 | Peso da questão (multiplica) |
| Semelhança (grupos A, B, C) | **Peso** 1, 0,5, 0,25 (Guia 1, seção 4.4 e passo 5): "multiplique os dois pesos" | Sem classificação: tratar como grupo A (peso 1) | Peso da questão (multiplica) |
| 7. Assuntos inéditos (Good-Turing) | Diagnóstico | — | Resultado descritivo |
| 8. Concentração (80%) | Diagnóstico | — | Resultado descritivo |
| 9. Presença em todas as provas | Diagnóstico | — | Resultado descritivo |
| 10. Seu desempenho | Multiplica no fim: questões esperadas × % do assunto × taxa de erro | Sem resolvidas: constante igual para todos (a planilha antiga usa 0,5), o que não altera a ordem | Prioridade final |

**Regra de ouro:** "valer 1" é correto para **pesos** (recência e semelhança). Para a lente 5 o neutro é "nenhum ajuste"; para a lente 10 é uma constante igual em todos os assuntos; as demais são sempre calculadas.

## 3. Ajustes que o Guia 1 exige no fluxo
1. **Semelhança = categorias, não vários multiplicadores independentes.** O guia define grupos A (mesmo cargo, mesmo órgão), B (mesma banca, cargos parecidos, últimos 8 a 10 anos) e C (mesma carreira, outras bancas), com pesos 1, 0,5 e 0,25. Multiplicar fatores separados (banca × cargo × órgão × examinador) encolhe demais o número efetivo de questões (0,5 × 0,5 × 0,5 = 0,125). Proposta: o perfil-alvo **decide o grupo** (A, B ou C) de cada prova comparando banca, cargo, órgão e carreira; o grupo dá o peso. Os pesos continuam editáveis.
2. **Questão com dois assuntos:** o Guia 1 manda contar meio ponto para cada (seção 2). O banco já tem o campo, mas ele não é usado.
3. **Lente 3 (mistura)** é uma fórmula à parte e continua opcional; hoje foi substituída pelos pesos de grupo, o que é uma simplificação aceitável, desde que declarada.
4. **Teste retroativo** precisa de pelo menos cerca de 5 provas; abaixo disso o resultado é ruído (Guia 1, seção 8).
5. **"Edital fictício"**: o Guia 1 diz para montar a lista de assuntos a partir do edital atual. Sem edital, usar a **união dos programas dos editais anteriores** é uma adaptação coerente (foi o que se fez em Direitos Humanos). Com edital real, o edital real passa a ser a fonte, mas **a taxonomia continua a mesma** (fixa e reaproveitada).

## 4. O fluxo, passo a passo, contra o Guia 1
| Passo do usuário | Equivale no Guia 1 | Avaliação |
|---|---|---|
| 1. Montar o conteúdo programático ("edital fictício") a partir das provas e editais anteriores | Passo 3 (lista de assuntos a partir do edital) e Guia 2, cap. 2 (comparar editais) | Boa adaptação |
| 2. Agrupar o conteúdo em assuntos (taxonomia fixa de 8 a 15), guardada no banco | Passo 3 e seção 2 ("lista fixa") | Fiel ao guia; ganho: reutilizável |
| 3. Classificar cada questão em assunto e em ponto do conteúdo; permitir mais de um | Passo 4 e seção 2 (colunas da planilha de questões) | Fiel; o ponto do conteúdo é um acréscimo útil (dá o "tópico exato") |
| 4. Perfil: com edital ou sem edital | Seção 7 do Guia 1 (aplicação a outros concursos) | Boa generalização |
| 4.1.1 Script aplica pesos conforme banca, cargo, examinador | Passos 2, 5 e 6 | Fiel, com o ajuste 1 acima |
| 4.1.2 Lente em branco vale 1 | — | Correto para pesos; ver seção 2 |
| 4.1.3 Porcentagem após somar os pesos | Passo 6 (com faixa de Wilson) | Fiel |
| 4.1.4 Três grupos | Passo 7 e seção 4.4 | Fiel |
| 4.1.5 Teste retroativo | Passo 11 e seção 5 | Fiel |
| 4.1.6 Apostila pelo modelo com edital | — (produto) | Coerente |
| 4.2 Sem edital: depende de cargo e banca informados | Seção 7 do Guia 1 ("situação do concurso") | Coerente |

## 5. Instrumentos necessários
**Banco de dados (fonte única, nunca recriado do zero)**
- `provas`: ano, órgão, **banca, carreira, cargo**, grupo de comparação, tipo do caderno, status do gabarito, fonte.
- `questoes`: texto, alternativas, gabarito, situação (válida, anulada, desatualizada).
- `disciplinas` e `assuntos` (taxonomia fixa, 8 a 15 por disciplina, com descrição).
- `conteudos` (edital fictício ou real): disciplina, assunto, texto do item, origem (quais editais), marcas novo, exclusivo e detalhado demais.
- `classificacao`: questão → conteúdo principal (e, se houver, o secundário), assunto derivado, tipo de cobrança, tópico exato.
- `comentarios`: texto, pegadinha, dispositivos, estado de revisão (rascunho, conferido), data, autor (IA ou humano).
- `examinadores`: prova, nome, disciplina, área de atuação, fonte (só entra se houver dado; Guia 2, cap. 3).
- `resultados_usuario` e `autoavaliacao`: o estado pessoal do usuário (acertou ou errou; notas 1 a 3).
- `perfis`: perfis-alvo salvos (banca, carreira, cargo, órgão, ano de referência, pesos, parâmetros do edital).

**Motor genérico (substitui os scripts específicos de Direitos Humanos)**
1. Lê o perfil e classifica cada prova em A, B ou C.
2. Calcula o peso de cada questão (semelhança × recência) e o número efetivo.
3. Calcula, por assunto: porcentagem, faixa de Wilson, grupo, tipo de cobrança, inéditos, concentração, presença.
4. Roda o teste retroativo (temporal e uma prova escondida) e compara com o acaso.
5. Aplica a lente 5 (se houver examinador) como subida de grupo e a lente 10 (se houver resultados) como prioridade.
6. Gera o **esqueleto da apostila**: assuntos em ordem, questões do banco já separadas, sem comentário.

**Camada da IA (só o que exige pensamento)**: classificar as questões novas, escrever os comentários e a pegadinha (gravados no banco), conferir "confirmar".

**Saídas**: tabelas de análise (para consulta e auditoria), planilhas como **exportação** do banco, esqueleto e apostila final (modelo A ou B).

**Qualidade**: checklist por prova na entrada; documento de **dúvidas para conferência manual** (feito por pedido do usuário: `../02-CONFERIR-MANUALMENTE.md`); teste automático de consistência dos números.

## 6. O que as planilhas passam a ser
- **Planilha de análise:** deixa de ser a fonte; vira uma **visão exportada** do banco (útil para auditar a conta com fórmulas visíveis). Pode ser gerada sob demanda por perfil.
- **Planilha de revisão (Guia 2, capítulos 4 e 5):** continua útil mesmo sem edital real, porque o "edital fictício" também tem itens para dar nota de 1 a 3; é o único lugar do estado **pessoal** do usuário. O que entrou e o que saiu entre editais passa a ser uma coluna do `conteudos`. Sugestão: manter como exportação e importar as notas de volta para `autoavaliacao`.

## 7. Riscos
- **Migração:** o banco atual é recriado do zero a cada execução (`03_criar_banco.py`), e a classificação e os comentários vivem em CSV e JSON. Mudar para "banco permanente" exige reescrever os carregadores.
- **Reclassificar com itens de conteúdo:** as 159 questões de Direitos Humanos hoje têm assunto e um "tópico exato" em texto livre; ligar cada uma a um item do conteúdo é trabalho de IA (M).
- **Lentes sem dado** (examinador, grupo C) continuarão neutras por muito tempo.
- **Complexidade:** o perfil com muitos atributos pode virar um sistema difícil de manter; começar com poucos (banca, carreira, cargo, órgão).
