# Prompt para reproduzir o projeto

Copie o bloco abaixo e cole numa conversa nova com um agente que consiga ler arquivos, rodar Python e gravar arquivos (ex.: Claude Code numa pasta vazia). Preencha os campos entre `[colchetes]` antes. Junte à conversa os PDFs das provas, dos gabaritos e dos editais, e os dois guias do método (`docs/metodo/guias/`), se quiser que o agente os siga ao pé da letra.

---

```
Você vai montar comigo um sistema de apoio a estudos para concurso público. Ele pega as provas
anteriores, monta um banco de questões, descobre o que mais cai e gera uma APOSTILA em Word por
disciplina, com questões, gabarito e comentários. Escreva sempre em português, em linguagem simples,
e presuma que eu preciso de contexto em toda explicação ou pergunta.

## Meu caso
- Disciplina: [ex.: Direitos Humanos]
- Carreira / cargo: [ex.: Defensor Público]
- Banca: [ex.: FCC]
- Órgão (só se for concurso de um órgão específico): [ex.: DPE-AM, ou "estudo geral"]
- Edital do concurso-alvo: [anexado / ainda não saiu]
- Provas disponíveis: [lista ou pasta com os PDFs: caderno, gabarito definitivo e edital de cada concurso]

## Regra de trabalho
Divida o trabalho nas FASES abaixo. Ao fim de cada fase, mostre o resultado e PARE: a fase seguinte só
começa depois que eu vir e aprovar. Registre num arquivo docs/PLANO.md o que foi feito em cada fase e
num docs/PENDENCIAS.md o que ficou sem conferir. Decisões que eu tomar vão para docs/DECISOES.md; esse
arquivo manda sobre o resto.

## Estrutura de pastas
banco/ (estudos.db e textos extraídos; backup/ com cópias antes de qualquer mudança grande)
dados/ (catálogo, classificação, comentários, editais em JSON)
docs/ (plano, pendências, decisões, conferência manual)
produtos/apostilas/<disciplina>/ (Word)
provas/<ano - órgão - cargo>/ (1. edital, 2. caderno, 3. gabarito; PDFs originais, NUNCA alterar)
scripts/ (Python 3.12 numerado, caminhos relativos à raiz do projeto)

## FASE 1: Insumos e banco
1. Extraia o texto dos PDFs (pdftotext -layout -enc UTF-8; OCR com Tesseract nos digitalizados).
2. Crie o banco SQLite banco/estudos.db, que é a FONTE ÚNICA e nunca é recriado do zero (o script de
   criação deve se recusar a rodar de novo; antes de mudanças, copie para banco/backup/).
   Tabelas: provas (nome, ano, banca, carreira, instituição, cargo, caminhos dos PDFs), questoes
   (número, disciplina, enunciado, alternativas, gabarito, situação: válida/anulada/desatualizada),
   disciplinas, assuntos, pontos, editais, edital_pontos, classificacao (ponto principal, ponto
   secundário, tipo de cobrança, detalhe), comentarios (estado rascunho/conferido, marca
   pendente_confirmacao, autor), examinadores, resultados_usuario, autoavaliacao, perfis, universos,
   ajustes_gabarito, log_alteracoes.
   A chave estável de uma questão é prova + número (IDs internos mudam quando entra prova nova).
3. Ingestão de prova nova por manifesto JSON, idempotente (rodar duas vezes não duplica).
4. CONFIRA o gabarito: tipo do caderno = tipo do gabarito; use o definitivo; procure os relatórios de
   alteração/anulação da banca; PDFs com vários cargos ou texto escondido errado devem ser transcritos
   das imagens. Corrija à mão o texto de OCR das questões da disciplina. Liste dúvidas em
   docs/CONFERIR-MANUALMENTE.md.
Entregue: tabela com provas, nº de questões da disciplina, anuladas e pendências.

## FASE 2: Catálogo de pontos
1. Leia o programa da disciplina nos editais anteriores e as questões.
2. Proponha 8 a 15 ASSUNTOS fixos (taxonomia que não muda) e, dentro deles, PONTOS de conteúdo
   (códigos tipo DH04.06), cada um com nome e linha de dispositivos (lei, artigo, tratado).
3. Os nomes e descrições NUNCA podem conter a resposta de uma questão.
Entregue o catálogo para eu aprovar antes de classificar.

## FASE 3: Classificação e comentários (rascunho da IA)
1. Ligue cada questão a 1 ponto (ou 2, se tiver dois temas; aí cada um conta 0,5). O assunto sai do
   ponto. Registre o tipo de cobrança: lei/tratado, súmula, jurisprudência, doutrina, caso prático.
2. Comente cada questão: o que foi cobrado, a pegadinha, os dispositivos.
3. Nunca cite lei, súmula ou julgado sem certeza: escreva "confirmar". Informação de blog: "confirmar
   no Planalto/tribunal". Tudo entra como rascunho; marque pendente_confirmacao quando houver dúvida.
4. Confira por amostra (10% das questões) e registre o resultado.

## FASE 4: Perfil, universo e motor de análise
PERFIL mínimo: disciplina, carreira ou cargo, e banca (órgão opcional). Sem isso, não gere nada: diga
o que falta. Mostre o perfil e peça minha confirmação antes de rodar.

UNIVERSO = filtro de QUAIS questões entram (banca, carreira, cargo, instituição, prefixo de cargo, ano
mínimo e máximo). Padrão: todas as questões. Fica salvo no perfil. Universo e peso são coisas
diferentes.

PESOS (só dois, multiplicados):
- Recência: 0,5 ^ (idade ÷ 8), idade = ano de referência − ano da prova.
- Semelhança por grupo: A = 1 (mesma carreira, banca e cargo; com órgão no perfil, também o mesmo
  órgão), B = 0,5 (mesma carreira e banca, outro cargo ou órgão), C = 0,25 (o resto). Se o banco não
  tiver prova do órgão, volte à regra geral e avise.

CONTAS (para assuntos e para pontos):
- Frequência ponderada: soma dos pesos do item ÷ soma total dos pesos (questão com 2 pontos reparte).
- Número efetivo: (soma dos pesos)² ÷ soma dos pesos².
- Faixa de confiança de Wilson (95%) usando o número efetivo.
- Classificação: "Cai muito" se o limite inferior > 1/K; "Cai pouco" se o superior < 1/K; senão
  "Cai às vezes" (K = nº de assuntos ou de pontos com questão).
- Concentração: quantos assuntos somam 80%.
- Presença: em quantas provas o item apareceu.
- Tipo de cobrança ponderado (%).
- Good-Turing: pontos com 1 questão só ÷ total de questões (indício de pontos ainda não vistos);
  listar pontos sem questão.
- Teste retroativo, só nas provas do tipo do perfil (carreira, banca e cargo): (a) temporal: prevê
  cada prova com as anteriores (mínimo 30 questões antes); (b) uma prova escondida: prevê cada prova
  com todas as outras. Mede quanto da prova caiu no top 4 assuntos e no top 10 pontos. Compare
  SEMPRE com o acaso (k ÷ K).
- Comparador de universos: roda todos os universos no mesmo alvo. Não escolher universo só pelo maior
  número do teste.
AVISOS obrigatórios: menos de 5 provas do grupo A (teste é ruído); todas as provas no mesmo grupo;
número efetivo < 100 (faixas largas, não ordenar temas finamente).
Declare a amostra ao lado de todo número. Grave o relatório em banco/analise/<disciplina>_perfil<N>.md.
Lentes de diagnóstico (não são peso): tipo de cobrança, inéditos, concentração, presença. Examinador:
só sobe de grupo, se houver dado no banco e eu confirmar. Meu desempenho (acertos e notas 1 a 3, que
eu ditar no chat) multiplica no fim.

## FASE 5: Edital real (só se eu mandar um)
1. Copie o programa da disciplina IPSIS LITTERIS para dados/edital_<concurso>.json: itens e frases,
   uma frase por linha. Só é permitido juntar quebras de linha e palavras hifenizadas no fim da linha.
2. Ligue cada ponto aos trechos do edital ({"i": item, "t": trecho literal}). O script de importação
   deve RECUSAR o arquivo se algum trecho não existir exatamente dentro do item indicado.
3. Pontos que não estão no edital continuam, marcados "fora do edital". Compare com o edital anterior
   por frases (o que entrou e o que saiu).

## FASE 6: Apostila em Word (python-docx)
Capa e prefácio declaram perfil, universo e amostra. A apostila traz só as questões do universo.
Prefácio:
- Sem edital: tabela de assuntos/pontos com frequência, faixa, provas e grupo, e "como ler".
- Com edital: (1) edital verticalizado literal, uma frase por linha, agrupado pelos itens, com a
  coluna "Pontos"; (2) tabela de pontos com as colunas Ponto, Conteúdo, Trechos do edital (literal,
  com o número do item; "…" marca trecho de frase maior), Q. e Nota 1·2·3.
Capítulos por assunto, pontos ordenados pela análise. Cada questão é um CARTÃO (tabela de 2 colunas:
cabeçalho colorido com prova e número, faixa "tópico exato", enunciado, alternativas).
- O cartão NUNCA mostra a resposta.
- Tópico exato: com edital, código do ponto + o trecho do edital mais parecido com a questão
  (literal); sem edital, código + nome do ponto. Nunca o detalhe da questão. Descarte o trecho ou nome
  que tiver palavra que só aparece na alternativa correta; se nenhum servir, mostre só o código e
  avise no terminal.
- Campos de anotação: Meu resultado, Nota 1·2·3, "Anote aqui os erros".
Fim de cada capítulo, bloco "Respostas e comentários": gabarito em letra pequena e cinza claro; logo
abaixo, "O que foi cobrado neste capítulo" (descrição do capítulo e a linha de dispositivos de cada
ponto, uma por ponto); depois os comentários. A descrição só fica no início se o capítulo não tiver
questão.
Design: Calibri; corpo 10,5 pt; cartões 10 pt; rótulos 8 a 8,5 pt; títulos 22/17/12 pt. Cores: texto
1f2328, cinza 5b6470, borda d0d7de, fundo f6f8fa; disciplina em azul 1f4e79 (fundo e8f0f8) ou vinho
8b1e3f (fundo f8e9ee); âmbar 9a6700 (fundo fff4d6) para "novo" e avisos de qualidade dos dados.
Etiquetas de cobrança: lei 0b5cad, súmula b35900, jurisprudência 6f42c1, doutrina 1a7f37, caso
prático 57606a. Ponha todo o desenho numa biblioteca (apostila_lib.py) separada do gerador.
Qualidade: converta para PDF com LibreOffice e olhe os cartões, as tabelas e o fim de um capítulo;
confira os números da apostila contra o relatório da Fase 4.

## Regras que valem sempre
- Não altere os PDFs originais.
- Só abra arquivos e produtos para mim quando eu pedir.
- Não prometa previsão fina com pouca amostra: diga o tamanho da amostra e compare com o acaso.
- Se estiver em dúvida sobre uma decisão que é minha, pergunte; se for técnica, escolha e explique.

Comece pela Fase 1: liste o que recebeu, o que falta e como vai organizar as pastas.
```

---

## Observações
- O prompt cobre o método e as decisões até 13/11/2026. Se `docs/metodo/04-DECISOES-CONFIRMADAS.md` ou o `CLAUDE.md` mudarem, atualize o prompt.
- O que ele **não** reproduz sozinho: o seu julgamento ao aprovar o catálogo e conferir gabaritos e comentários. Isso continua sendo trabalho seu, e é o que dá qualidade ao resultado.
- A coleta pelo TEC Concursos ficou de fora, porque depende da sua conta e do navegador. Se quiser, dá para acrescentar uma fase opcional para ela.
