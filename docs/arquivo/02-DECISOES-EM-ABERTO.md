# Decisões em aberto e pontos fracos do método

Criado em 12/11/2026, a pedido do usuário, para aprofundar e decidir. Complementa `00-FLUXO-DE-TRABALHO.md` (seção 5). Linguagem simples; cada item traz **o que é**, **por que importa**, **o que já sabemos**, **opções** e **minha recomendação**.

## Como ler este arquivo

- **Decisões suas** (D1 a D3): precisam de uma resposta sua para eu seguir.
- **Pontos fracos** (P1 a P6): riscos do método. Alguns têm solução técnica minha; outros dependem de você.
- Esforço é uma estimativa: **P** = menos de 30 minutos, **M** = algumas horas de trabalho, **G** = mais de um dia de trabalho.

---

## D1. A apostila deve ser uma "foto de uma data" ou acompanhar a planilha?

**O que é.** Você pediu que a apostila se baseie nas planilhas. Hoje o caminho é este: banco de questões → análise em Python (`11_analise_dh.py`) → apostila. A planilha de análise é feita em paralelo, com fórmulas, e serve para você mexer e para conferir o Python. A apostila **não lê** a planilha.

**Por que importa.** Se você mudar o peso de um grupo, o ano de referência ou marcar "Acertou/Errou" na planilha, os números dela mudam, mas os da apostila continuam os mesmos. Dois lugares mostrariam números diferentes.

**O que já sabemos.** Conferi a planilha recalculada contra o Python: batem (n efetivo 148,5; 25,5% e 18,2% nos dois maiores temas; teste retroativo de 56% e 52%). Então hoje não há contradição. O risco é futuro.

**Opções.**

| Opção                                | Como funciona                                                                          | Vantagem                                               | Desvantagem                                                                    | Esforço                                       |
| -------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------ | ---------------------------------------------- |
| A. Foto de uma data (como está)       | A apostila mostra a análise do dia em que foi gerada; a planilha é a ferramenta viva | Simples; a apostila é um documento fechado e estável | Pode divergir da planilha se você mudar parâmetros                           | P (só avisar na capa a data e os parâmetros) |
| B. Apostila lê a planilha recalculada | O script abre a planilha no LibreOffice, recalcula e lê os resultados                 | Uma só fonte de verdade para os números              | Depende do LibreOffice; mais lento; o Python de análise vira só conferência | M                                              |
| C. Parâmetros num arquivo único      | Pesos, meia-vida e ano de referência ficam num arquivo que a planilha e o Python leem | Consistência sem depender do LibreOffice              | A planilha deixaria de ser "livre" para mudar pesos                            | M                                              |

**Recomendação.** A (com a data e os parâmetros impressos na capa e uma regra de conferência de 3 números ao regerar). A opção B vale quando você começar a mudar os pesos com frequência. **Preciso de você:** dizer se você pretende mudar pesos ou parâmetros na planilha.


O que eu penso: as planilhas devem ser o registro dos dados estatísticos, pelo que entendi dos guias. com base neles é que a apostila vai ser criada. eu achava que a ia lia as planilhas e montava a apostila organizando as questões do banco de dados, apenas acrescentando os comentários das questões (o plus que a IA faria na apostila). inclusive, eu achava que o próprio banco de questões guardaria os temas sob os quais os assuntos dos editais foram organizados (orientação do guia preditivo), para facilitar essa organização.


acho que o fluxo então poderia ser assim:

1. com base nas provas anteriores, montamos o conteúdo programático (chamaremos de edital fictício), como você fez com o produto de direitos humanos para defensorias da fcc.
2. esse conteúdo programático vai ser agrupado dentro de assuntos (lista fixa de assuntos do guia 1, a "taxonomia"). a lista inclusive pode constar de um banco de dados. nela terá o assunto e, dentro dele, quais conteúdos do edital fictício estão abarcados nesse assunto (ou, como você chamou na apostila, "tema")
3. após, as questões do banco de dados vão ser classificadas tanto nos assuntos do edital fictício quanto no tema (em tese, algumas questões pdoem ser interdiciplinares, então podem ter mais de um assunto ou mais de um tema). dentro do banco de questões, devem constar os dados do item 2 "como montar a planilha de questões" (Concurso, ano, cargo e banca, Examinador, Disciplina, Assunto, Detalhe, Tipo de cobrança, Situação, resultado do candidato), além de constar qual o ponto específico do conteúdo programático. Essa parte mais pesada, que exige pensamento, deve ser feita pela IA.
4. quando o usuário pedir uma apostila, haverão dois casos, para fins de cálculo de peso:

4.1. com edital em vista:

4.1.1. deve haver um script que organize automaticamente as questões aplicando os pesos com as fórmulas do guia 1, dependendo dos dados do edital (banca, cargo, examinador) e aplicando as demais lentes disponíveis.

4.1.2. se uma lente não estiver disponível (em branco), em tese ela vale 1 (pois, se eu não estiver errado, mantém o resultado na fórmula final, que costuma multiplicar os valores da lente; corrija se eu estiver errado)

4.1.3. calcular a porcentagem do assunto, após a soma dos assuntos aplicadas as lentes.

4.1.4. Separe os assuntos em grupos (cai muito, cai às vezes, cai pouco), com base no guia 1.

4.1.5. Confira se a análise funciona com o teste retroativo, conforme o guia.

4.1.6. a apostila será montada ao final usando o modelo com edital.

4.2. sem edital: será semelhante. a diferença é que dependerá do que o usuário quer: qual o cargo e qual a banca.

valide para mim esse fluxo com base nos guias, para ver se faz sentido e se é uma boa adaptação do guia 1 para deixar mais geral o seu uso ou se destoa muito.

veja quais instrumentos serão necessários para isso funcionar, e já salve no claude.md para termos conhecimento.

a planilha de análise, nesse cenário, perderia o uso, já que o banco de questões e o banco de dados de assuntos supriria a necessidade. a planilha de resultado eu vi que é mais para casos que tenham algum edital em foco, confrontando esse edital com os dados para até mesmo ver o que entrou e saiu de novo. então devemos ver se mantemos ou adotamos outro instrumento futuramente.

---

## D2. Quero que eu gere rascunhos das fichas de revisão (Guia 2, capítulo 6)?

**O que é.** A ficha é uma meia página por assunto: "o erro que eu cometo", "a regra certa", "a pegadinha da banca". O material antigo (Penal e DH do DPE-AM) tinha rascunhos em `metodo/guias/exemplo - Fichas-Direitos Humanos.md`. Para o material novo, não gerei.

**Por que importa.** É o passo final do Guia 2 e o que você leria na véspera. Sem ele, a revisão final depende só das tabelas e dos comentários.

**O que já sabemos.** Os comentários que escrevi (159) já têm "o que foi cobrado", "pegadinha" e "dispositivos" por questão, que é o miolo de uma ficha. Falta reorganizar por **assunto** e deixar em branco "o erro que eu cometo", que só você pode preencher (o Guia 2 diz para escrever na hora do erro).

**Opções.**

| Opção                   | Conteúdo                                                                      | Esforço    |
| ------------------------- | ------------------------------------------------------------------------------ | ----------- |
| A. Fichas por tema (11)   | Uma ficha por capítulo, juntando as regras e as pegadinhas mais repetidas     | M           |
| B. Fichas por dispositivo | Uma ficha por tratado, artigo ou caso que caiu 2 vezes ou mais (hoje 40 itens) | M           |
| C. Só quando você errar | Você erra a questão e eu gero a ficha daquele item na hora                   | P por ficha |

**Recomendação.** B, porque é o formato que o Guia 2 descreve ("um assunto, meia página") e cruza com a planilha de revisão (itens com nota 2 e frequência alta). **Preciso de você:** confirmar se prefere por tema ou por dispositivo.

Não precisa.

---

## D3. Perfil dos examinadores (Guia 1, lente 5; Guia 2, capítulo 3): vale o esforço?

**O que é.** Em alguns concursos de Defensoria, uma comissão do próprio órgão escreve as questões. Quem são essas pessoas, o que publicaram e em que área atuam indica o que elas costumam cobrar. Os guias tratam isso como a lente mais forte quando os nomes são divulgados.

**O que já sabemos.** Pesquisei na web em 12/11/2026 e **não achei confirmação** de quem redige as questões objetivas: os blogs divergem, e o edital da DPE-SP só diz que a FCC aplica e divulga a prova. Os editais citam uma "Banca Examinadora" para as provas oral e discursiva, e a composição é publicada à parte (DPE-SP e DPE-RS).

**Por que importa.** Se a comissão escreve as questões, o histórico por assunto vale menos e o perfil dos examinadores vale mais. Hoje não sei qual caso se aplica a cada prova, então a análise trata todas como "FCC, a confirmar".

**Opções.**

| Opção                             | O que faz                                                                                                                                                                | Esforço       |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------- |
| A. Não aplicar a lente 5           | Seguir só com a estatística e declarar o limite                                                                                                                        | Nenhum         |
| B. Pesquisar uma prova de interesse | Achar a composição da banca de **um** concurso-alvo e levantar os examinadores de Direitos Humanos (currículo Lattes, área de atuação, teses institucionais) | M por concurso |
| C. Pesquisar todas as 19 provas     | Só faz sentido se você quiser comparar                                                                                                                                 | G              |

**Recomendação.** B, mas só depois que você definir o concurso-alvo. Sem alvo, o ganho é pequeno. **Preciso de você:** qual concurso é o alvo agora (ou se ainda não há).

A lente de examinadores só entra com valor se: 1) estiver disponível no banco de dados de questões e; 2) se o usuário indicar que são os mesmos examinadores. se não, o valor será 1 (novamente, corrija se eu estiver errado pois acho que esse valor é multiplicado no peso da questão)

---

## P1. Os scripts ainda são específicos de Direitos Humanos

**O que é.** Os scripts de análise (`10`, `11`, `13`, `15`) e de apostila (`12`) trazem Direitos Humanos escrito dentro deles: nome da disciplina, lista de assuntos, textos do "Como ler". Para outra disciplina, é preciso copiar e trocar.

**Por que importa.** É o maior obstáculo para "reproduzir em outras disciplinas". Cada disciplina nova custaria horas só de adaptação.

**O que já sabemos.** O `modelos/LEIA-ME.md` descreve a adaptação manual. A biblioteca de design (`apostila_lib.py`) já é genérica; o que não é genérico é a lógica ao redor.

**Solução proposta (esforço M a G).** Um arquivo de configuração por disciplina (nome, prefixo dos assuntos, lista de assuntos com descrição, arquivos de classificação e comentários, textos fixos) e um comando único, por exemplo `python pipeline.py --disciplina "Princípios Institucionais"`. Os textos que dependem da análise ("Como ler") passariam a ser gerados a partir do resultado, com regras fixas.

**Cuidado.** Generalizar cedo demais pode produzir um sistema complicado. Minha sugestão é fazer **a segunda disciplina à mão** (copiando e adaptando) e só depois extrair a configuração, porque aí sabemos o que realmente muda de uma disciplina para outra.

Eu ainda não entendi o que é esse script de análise. Pensei que a lista de assuntos fosse criada separado, na planilha de análise, e ela alimentasse depois outros pontos necessários.

---

## P2. Classificar e comentar é o gargalo e não tem segunda checagem

**O que é.** Para cada disciplina, o trabalho mais pesado é ler cada questão, escolher o assunto, o tipo de cobrança, escrever o comentário e a pegadinha. Em Direitos Humanos foram 159 questões feitas por mim, sem outra pessoa conferindo.

**Por que importa.** A estatística inteira depende dessa classificação, e o conteúdo jurídico dos comentários depende da minha memória. Já houve erros: em 5 das 20 questões de GO e RR 2021, minha análise do conteúdo divergiu do gabarito oficial e tive de reescrever os comentários.

**O que já sabemos.** Comentários com dúvida levam "confirmar". Gabaritos oficiais ajudam a flagrar erros de conteúdo. Não há ainda uma conferência sistemática.

**Opções.**

| Opção                                     | O que faz                                                                                          | Esforço |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------- | -------- |
| A. Amostra de 10%                           | Você (ou um professor) confere 16 questões sorteadas por disciplina e registramos a taxa de erro | P a M    |
| B. Conferir só o que tem "confirmar"       | Eu listo todos os itens marcados e você valida na fonte oficial                                   | M        |
| C. Conferir o gabarito contra o comentário | Já fiz: o comentário que cita "Gabarito oficial: X" bate com o banco (0 divergências)           | Feito    |

**Recomendação.** A + B juntas para Direitos Humanos, antes de usar a apostila para decidir o que estudar. Posso preparar a lista das questões sorteadas e dos itens "confirmar" em uma planilha para você ou outra pessoa conferir. **Preciso de você:** dizer se quer isso e quem confere.

Eu achava que dava para automatizar essa parte de classificar e efetuar a contagem. Seria basicamente pegar as questões já com as informações das lentes e com os temas e assuntos, ver os mais recorrentes, aplicar as fórmulas, e devolver para a IA um esqueleto separado por temas, com as questões, e só para a IA comentar (inclusive, acho que os comentários podem ir para a própria base de dados, para evitar ter que refazer futuramente).

inclusive, as próprias lentes podem ser adaptáveis para qual tipo de apostila você quer: se o usuário responder que quer Defensoria FCC, o script já poderia ver quais questões são da FCC e aplicar sobre elas um peso maior, e nas restantes um peso menor.

---

## P3. Dois motores para a mesma conta (planilha e Python)

**O que é.** A análise existe duas vezes: em fórmulas na planilha e em Python. Isso serve de conferência, mas é duplicação.

**Por que importa.** Se eu alterar uma regra (por exemplo, o critério de "cai muito") em um lugar e esquecer o outro, os números divergem sem ninguém notar.

**Mitigação já definida.** Após qualquer mudança, regerar a planilha e conferir 3 números contra o Python (n efetivo, % do maior tema, média do teste retroativo). Posso transformar isso em um script de teste que roda sozinho (`python conferir_analise.py`). Esforço P.

**Recomendação.** Fazer o script de conferência agora; é barato e evita um erro silencioso.

Com o fluxo que imaginei acima, podemos rever a necessidade das planilhas.

---

## P4. Coleta de dados frágil

**O que é.** Obter as provas, os gabaritos e o texto limpo depende de: PDFs de imagem (OCR com erros), gabaritos em imagem, o site da FCC (só tem relação geral para concursos antigos), o TEC Concursos pelo navegador (a extensão do Claude desconectou e downloads falharam) e arquivos que você me envia.

**Por que importa.** Cada prova nova custa tempo e pode trazer erro de texto ou de gabarito. Em Direitos Humanos, uma só prova (DPE-ES 2023) exigiu cinco fontes.

**O que já sabemos.** As armadilhas estão no `modelos/LEIA-ME.md`. O mais sério foi o gabarito de outro tipo de caderno (GO e RR 2021), que só descobrimos por acaso.

**Opções para reduzir o custo.**

- Lista de verificação por prova (tipo de caderno, tipo do gabarito, relatório de alteração, texto das questões da disciplina) antes de entrar no banco. Esforço P.
- Pedir a você os PDFs de provas novas (você já tem acesso a gabaritos que eu não consigo). Custo zero para mim, algum para você.

**Recomendação.** Adotar a lista de verificação e usar sempre o TEC como segunda fonte do gabarito.


Usar o TEC com tanta frequencia pode dar problema. Criar cadernos com IA eu acho que é válido, mas conferir texto de questão, gabarito, pode dar problema. Prefiro assumir o risco. Você pode criar um documento separado de quais provas (se forem inteiras) ou questões geram dúvida, e eu irei atrás de solucionar manualmente fornecendo confirmação ou documento que auxilie.

---

## P5. Poucos dados por disciplina: o método não promete previsão fina

**O que é.** Cada prova tem de 5 a 13 questões de Direitos Humanos. Com 148 questões efetivas, só dois temas se destacam; os outros oito não se ordenam entre si.

**Números para ter em mente.**

- Teste retroativo: 56% das questões das provas seguintes caíram nos 4 temas do topo, contra 40% ao acaso (ganho de 16 pontos percentuais).
- Resultado por prova varia de 38% a 83%.
- Em uma prova de 8 questões de Direitos Humanos, o ganho médio é de cerca de 1 questão.

**O que significa.** O histórico serve para **ordenar** o estudo, não para **cortar** assuntos. Isso já está dito na apostila. Para disciplinas com mais questões por prova (por exemplo Constitucional ou Administrativo, 8 a 16 por prova), a precisão deve ser maior.

**Sem decisão necessária.** É um limite do método, não um defeito. O que vale é continuar declarando a amostra e comparando com o acaso.

Sem problema. A ideia é manter um estudo pela ordem do que é mais cobrado e dando mais ênfase nele, sem largar o resto. A apostila, que será produto, é mais uma revisão final sobre a matéria, não a tábula de salvação que trará todo o conhecimento ao candidato. são APOSTAS, mas com método e não ao acaso.

---

## P6. Elementos dos guias ainda sem produto

| Elemento                               | Situação                                                       | Depende de                                                                            |
| -------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Lente 3 (mistura com provas parecidas) | Substituída por pesos por cargo e idade; é uma simplificação | Eu poderia implementar a mistura hierárquica; esforço M                             |
| Lente 5 e capítulo 3 (examinadores)   | Não feito                                                       | Decisão D3                                                                           |
| Capítulo 6 (fichas)                   | Não feito                                                       | Decisão D2                                                                           |
| Lente 10 e capítulos 4 e 5            | Planilhas prontas                                                | Você: resolver questões e dar as notas                                              |
| Grupo C (outras bancas)                | Não existe                                                      | Provas de outras bancas para Defensoria (ex.: Cebraspe, FGV); só vale se faltar dado |

A mistura  vai depender do que o usuário pedir para a ia. se ele vem com o edital pronto de um concurso, a análise vai usar todas as lentes disponíveis. se ele quer a carreira x da banca x, essas lentes vão pesar mais, deixando de lado as lentes que testam semelhança de instituição, de examinador, etc, que valerão 1 (novamente, me corrija se estiver errado, mas a lente é usada como um peso a ser multiplicado ao valor da questão)

---


## Resumo: o que eu faria primeiro (se você concordar)

1. **P3** (script de conferência dos números): 20 minutos, evita erro silencioso.
2. **P2** (amostra de conferência + lista dos itens "confirmar"): prepara a apostila de Direitos Humanos para uso real.
3. **D2** (fichas por dispositivo): fecha o Guia 2.
4. Fazer a **segunda disciplina à mão** (sugestão: Princípios e Atribuições Institucionais da Defensoria) e só então **P1** (generalizar os scripts).
5. **D3** só depois de você definir o concurso-alvo.

## Perguntas diretas para você decidir

OBS.: respondi muitas coisas acima mesmo. analise lá.

1. Você pretende mudar pesos ou parâmetros na planilha? (define D1)
2. Fichas: por tema ou por dispositivo? (define D2)
3. Qual é o concurso-alvo agora, se houver? (define D3)
4. Quem confere a amostra das questões e os itens "confirmar"? (define P2)
5. Qual disciplina vem depois de Direitos Humanos?
