# Plano de fluxos e porteiro (RASCUNHO, não aprovado)

Criado em 16/11/2026 a partir de dois testes de lógica (hipóteses de pedidos do usuário e de insumos que faltam). **Status: rascunho para o usuário aprovar. Nada daqui começa antes da aprovação; cada etapa só começa depois que o usuário vê o resultado da anterior; nenhuma etapa gera nem regera apostila, a menos que o usuário peça.**

## 1. Objetivo
Fazer o método responder bem quando **falta alguma coisa**: catálogo, edital fictício, insumos de edital, questões, classificação, comentários ou conferência. Hoje o agente depende de lembrar as regras; o código quase não bloqueia nem avisa. O plano 06 organizou o projeto; este plano fecha as lacunas dos fluxos.

## 2. Diagnóstico (verificado no código em 16/11/2026, só leitura)

**O que o código já faz**
| Situação | Quem trata | Efeito |
|---|---|---|
| Perfil inexistente, incompleto, não confirmado ou alterado depois de confirmar | `23` e `24` | recusa |
| Edital real sem artefato | `24` e `70` | recusa |
| Disciplina fora do edital | `70` | recusa e lista as disciplinas |
| Universo sem questão válida da disciplina | `23` | recusa |
| Catálogo sem pontos; 0 classificadas no bloco; questões sem classificação ou sem comentário | `70` | só avisa; o `24` não impede |
| Texto a conferir, anulada, gabarito preliminar, comentário "confirmar" | `24` | gera e marca o cartão |
| Classificação `revisada`; comentário `estado`; artefato `confirmado` | ninguém lê | sem efeito |

**Lacunas (L)**
- **L1.** O porteiro não olha: estado do artefato (rascunho ou confirmado, por bloco), frases sem julgamento, propostas de tópico pendentes, gabarito preliminar, texto a conferir, amostra pequena. Ele disse "pode gerar" para o edital 4, que só tem 2 blocos confirmados.
- **L2.** Questão ingerida e não classificada some da apostila sem aviso na apostila (só o porteiro conta).
- **L3.** "Conferido pelo usuário" tem cinco vocabulários (`revisada`, `estado` do comentário, `pendente_confirmacao`, `confirmado` do artefato, status do gabarito) e quase nenhum efeito. Uma apostila toda em rascunho sai igual a uma conferida.
- **L4.** Disciplina nova com edital real: dois caminhos para criar o catálogo (ciclo do edital fictício geral, ou propostas `NOVO` do `51`), sem regra de qual usar nem de homologação das propostas.
- **L5.** Sem edital real, o método diz que o prefácio mostra o edital fictício geral, mas o `24` não lê `edital_itens`; só `edital_pontos`, que existe para DH e para os editais 2 e 3.
- **L6.** Não há número mínimo para "vale gerar" (editais para o fictício, questões, provas) nem regra de "gerar mesmo assim", exceto para comentários (decisão 40).
- **L7.** Apostila desatualizada em relação ao banco não é detectada (Civil, PI e ECA só apareceram regerando). A base de regressão não tem rotina de refazer depois que entra prova nova.
- **L8.** O universo é comum à pasta: não dá para um universo só para uma apostila; e há uma confirmação por apostila (10 por concurso) para dados comuns.
- **L9.** Resultados e notas do usuário ("acertei a 3 e a 5"): sem script nem fluxo; tabelas vazias.
- **L10.** Comentários só existem no banco (JSON em lotes), sem exportação como o catálogo.
- **L11.** Resíduos: dois caminhos de edital no `24` (artefato e `edital_pontos`, este só para o perfil 1) e a flag `--legado` do `23`.

## 3. Etapas propostas (ordem sugerida)
1. **Porteiro completo (só leitura).** Reescrever o relatório do `70` como "semáforo" por bloco: **bloqueia** (impede gerar), **avisa** (gera, mas o usuário precisa saber) e **informa**. Cobrir L1 e L2: catálogo, classificadas e não classificadas, comentários (sem e pendentes), `revisada`, artefato (por bloco, frases sem julgamento, propostas), gabaritos preliminares, texto a conferir, tamanho da amostra, perfil. Teste: rodar nos 10 blocos do edital 4 e no edital 8; nada muda em banco nem produtos.
2. **Bloqueios e "gerar mesmo assim".** Com o usuário, decidir o que bloqueia e o que só avisa (L6); definir o override com motivo registrado e escrito na capa da apostila ("gerada com pendências: ..."). Implementar nos `23`/`24`.
3. **Um só estado de conferência (L3).** Definir o vocabulário único (por exemplo: rascunho IA, conferido pelo usuário), o que aparece na apostila, e o comando para o usuário marcar o que conferiu (classificação, comentário, bloco do artefato).
4. **Catálogo de disciplina nova (L4).** Escolher um caminho (ou uma regra clara de quando usar cada um) e documentar no método; se for pelas propostas do `51`, definir a homologação.
5. **Prefácio sem edital real (L5).** Decidir: ligar o `24` ao edital fictício geral, ou mudar a regra escrita. Teste com uma disciplina sem edital fictício.
6. **Apostila desatualizada e base de regressão (L7).** Impressão digital dos insumos (banco, perfil) guardada na apostila; comando "o que está desatualizado?" (só leitura); rotina para refazer a base de regressão quando entra prova.
7. **Perfil: universo por apostila e confirmação por pasta (L8).** Só se o usuário quiser mudar; é decisão de modelo.
8. **Resultados e notas do usuário (L9).** Fluxo e script para gravar, e como a apostila mostra.
9. **Comentários como dados exportáveis (L10).** Mesmo padrão do `71`.
10. **Limpeza (L11).** Aposentar `--legado` e unificar o prefácio do perfil 1, se as etapas 4 e 5 permitirem.

## 4. Decisões que dependem do usuário
- Quais condições bloqueiam e quais só avisam (etapa 2); números mínimos de editais, questões e provas.
- Qual caminho para catálogo de disciplina nova (etapa 4).
- Se o prefácio sem edital deve usar o edital fictício geral (etapa 5).
- Se quer universo por apostila e confirmação por pasta (etapa 7).

## 5. Cenários de teste (aceite; repetir depois de cada etapa, em modo de leitura)
1. Disciplina fora do edital → recusa e lista as do edital.
2. Regerar uma apostila existente → só com pedido; perfil confirmado não é reconfirmado.
3. Mudar universo, pesos ou meia-vida → confirmação invalidada em todas as apostilas da pasta; mostrar e reconfirmar.
4. Prova nova ingerida → motor muda; apostilas e base marcadas como desatualizadas.
5. Edital novo com artefato em rascunho → o porteiro avisa que é rascunho e por bloco.
6. Disciplina nova sem catálogo → o porteiro diz o caminho a seguir e o que falta.
7. Estudo geral sem edital real → prefácio conforme a decisão da etapa 5.
8. Questões não classificadas → número dito antes de gerar; estado visível na apostila.
9. Comentários ausentes ou pendentes → pergunta "comento antes ou gero assim?".
10. Tudo em rascunho → a apostila diz isso na capa.
11. Banco sem questões ou universo vazio → recusa clara, sem erro técnico.
12. "Gerar mesmo assim" → registrado na capa, com o motivo.
13. Resultado ditado pelo usuário → gravado e mostrado (etapa 8).

## 6. Fora deste plano
A trilha de ensino médio continua bloqueada por falta de provas (ver `docs/03-PENDENCIAS.md`).
