# Plano de melhorias e organização do projeto

> Nota de 16/11/2026: depois da Etapa 4, os documentos citados como `docs/00` a `05` e `metodo/` estão em `docs/arquivo/` (e as decisões em `docs/02-DECISOES-EM-VIGOR.md`).

Criado em 15/11/2026. Objetivo: arrumar o projeto depois que os produtos do concurso DPE-AM 2026 (Analista Jurídico) estiverem fechados, para que ele cresça com método e não por acúmulo. Este plano **não substitui** o `docs/05-PLANO-FECHAMENTO-DPEAM-2026.md`; ele começa onde o `05` termina.

## 0. Regra de porteiro
- **Só começa depois da Fase F do `05`** (critério de "DPE-AM 2026 fechado", seção 3, Fase F, item 4). **Situação em 16/11/2026: liberado.** A Fase E (conferência do edital pelo usuário) fica "em implementação" e **não bloqueia**, porque o critério aceita o edital declarado como rascunho.
- **Fase E em paralelo:** as Etapas 2 e 3 não mexem em `50` a `52` nem em `decisoes.txt`. Se o usuário alterar o edital no meio de uma etapa, a base de comparação é refeita (ver "Base de regressão" na Etapa 1).
- Até lá, nenhum produto ou documento novo fora do `05`. Os scripts atuais **não mudam** no meio do fechamento.
- **Única exceção:** a auditoria da Etapa 1, porque é só leitura e não altera nada.
- Cada etapa só começa depois que o usuário vê o resultado da anterior. Cópia do banco antes de qualquer mudança.

## 1. Diagnóstico (conversa de 15/11/2026; ainda não auditado em código)
1. **Um script por disciplina para a mesma tarefa.** Criar catálogo e classificar questões existe em versões separadas: DH (`21`, `22`), Penal (`30`, `31`), Língua Portuguesa (`58`, `59`), Princípios Institucionais (`60`, `61`), Execução Penal (`62`) e Idoso/PcD/Mulher (`63`). Ideal: um script só, lendo um arquivo de dados por disciplina.
2. **Dois caminhos para o mesmo fim.** Edital real: `28` (antigo) e `50` a `52` (artefato). Edital fictício: regra antiga e regra nova. O `42` só serve para DH e Penal.
3. **Documentação em camadas.** Planos `00`, `03`, `04`, `05`, pendências e 41 decisões. O `CLAUDE.md` lista a leitura fora de ordem (1 a 5, depois 7, depois 6) e diz que parte "é histórico".
4. **Disciplinas em estágios diferentes** (catálogo, classificação, comentários e conferência variam), cada uma feita de um jeito.
5. **Muitos arquivos gerados**, inclusive versões do mesmo produto, à espera de conferência.

O que já está certo e deve ser mantido: fluxo provas → banco único → perfil → motor → apostila; cópia do banco antes de gravar; `--simular`; perfil confirmado; pesos simples e declarados; "fora do edital" só com motivo.

## 2. Etapas

### Etapa 1. Auditoria só de leitura
Entrega: um relatório curto, sem alterar nada.
- Lista de scripts: o que faz, quem chama, o que é duplicado, o que está morto.
- Lista de documentos: o que vale, o que é histórico, o que se repete.
- **Matriz de situação por disciplina:** provas ingeridas, catálogo, questões classificadas, comentários, conferido ou rascunho, apostila gerada.
- Pontos onde um dado novo poderia "contaminar" os atuais (universo padrão "Todas as questões" em algum perfil; regravação do edital fictício).
- **Base de regressão:** contagens por perfil (2 a 11: questões, pontos, dispositivos, n efetivo) e lista dos documentos gerados, registradas antes de qualquer mudança. O teste das Etapas 2, 3 e 5 compara **código antigo contra código novo sobre o mesmo estado do banco**; se o usuário mudar o edital (Fase E), refaz-se a base. Sugestão: etiqueta no git (`base-regressao-AAAA-MM-DD`) no momento da base.
- **Candidatos a legado a verificar:** `produtos/modelos/` (modelos A e B, obsoletos), `docs/02-CONFERIR-MANUALMENTE.md`, scripts de entrada antiga (`01*` a `09`) e o `07_aplicar_tec` (a reescrever ou descartar).
- **Dados em aberto que a auditoria deve listar:** lote QConcursos (33 provas baixadas e não ingeridas; afeta "provas ingeridas" e o risco de contaminação) e a decisão sobre mover Idoso/PcD (disciplina 21) para DH (o usuário decide no momento da Etapa 2).
- O usuário decide o que cortar.

### Etapa 2. Unificar catálogo e classificação
Um script guiado por arquivos de dados em `dados/`; `21`, `22`, `30`, `31`, `58` a `63` passam a ser dados e configuração. **Teste de regressão:** motor e apostilas dos perfis existentes saem idênticos (mesmas contagens e mesmos documentos, salvo marcas novas), como na Fase A do `05`.

**Feita em 16/11/2026 (aguarda o usuário ver o resultado).** `scripts/71_catalogo_e_classificacao.py` (`exportar`, `aplicar`, `conferir`) e os dados em `dados/catalogo/*.json` (11 disciplinas, 403 pontos, 120 assuntos) e `dados/classificacao/*.csv` (1.436 classificações). Os arquivos foram **exportados do banco** (e não dos scripts antigos), porque os scripts `22` e `31` estavam defasados: desfariam reclassificações feitas depois, e cerca de 1.050 classificações (14/11/2026) só existiam no banco, sem arquivo. Regressão: `conferir` = 0 mudanças; teste com 6 alterações propositais numa cópia do banco, todas desfeitas, tabelas idênticas ao original; motor dos 11 perfis idêntico à base; hash do banco inalterado (as apostilas, que leem só o banco, ficam idênticas por construção). Scripts `21`, `22`, `31`, `58` a `63` movidos para `legado/scripts/`. **Decisões do usuário em 16/11/2026, já aplicadas:** (1) o `43` não cria mais pontos: confere que a taxonomia cabe no catálogo (`dados/catalogo/`) e, para disciplina nova, o `71 semear SIGLA "Disciplina"` gera o catálogo inicial a partir da taxonomia (conferência do `43 --simular` OK nas 7 disciplinas); (2) as 22 questões da disciplina 21 (Idoso/PcD) foram movidas para Direitos Humanos. **Efeito da mudança 2 na regressão (esperado, não é erro):** o motor dos perfis 3 a 11 segue idêntico à base; os perfis 1 e 2 (DH) mudam um pouco, porque a regra de escopo trata a questão da própria disciplina do perfil de forma diferente da questão de outra disciplina (a de outra só conta os pontos tocados pelo bloco). A nova base de DH deve ser a atual. A disciplina 29 (3 questões do TJCE) segue à parte.

### Etapa 2b. Perfil como arquivo dentro da pasta do concurso (ideia do usuário, 16/11/2026)
Hoje o perfil é uma linha da tabela `perfis`; os perfis 2 a 11 repetem cargo, banca, órgão, edital, universo e pesos e só mudam o bloco. Proposta: **cada concurso tem uma pasta** (ex.: `produtos/apostilas/Analista Jurídico Defensoria - DPE-AM 2026/`) com um **`perfil.toml`** (cargo, carreira, banca, órgão, edital, universo definido ali dentro, pesos, meia-vida, ano, data da confirmação, lista de blocos/apostilas) e as apostilas ao lado. Perfil sem edital (hoje o perfil 1) vira uma pasta própria ("Defensor Público FCC - estudo geral") com o universo escrito no arquivo.
- **Uma só fonte da verdade:** o arquivo manda; `23`, `24` e `70` leem o arquivo (`--perfil <pasta>`); a tabela `perfis` vira cópia gerada ou é aposentada.
- **Confirmação:** vale para a pasta toda; mudar universo, edital ou pesos invalida a confirmação (reconfirmar e regerar). A capa da apostila cita o perfil e a data.
- **Migração:** script que exporta cada linha de `perfis` para arquivo; regressão = saída do motor idêntica antes e depois. `--perfil ID` segue funcionando durante a transição.
- **A verificar antes de aposentar a tabela:** se `resultados_usuario` e `autoavaliacao` apontam para o ID do perfil.
- Entra depois da Etapa 2 (catálogo) e antes das trilhas, para que a trilha nova já nasça com este modelo (`produtos/<trilha>/<concurso>/perfil.toml`).
- **Feita em 16/11/2026 (aguarda o usuário ver o resultado):** `scripts/lib_perfil.py` e `scripts/72_perfil.py` (`exportar`, `conferir`, `sincronizar`, `confirmar`); `23` lê o `perfil.toml` (o `24` e o `70` usam o mesmo carregador) e o `24` grava a apostila na pasta do concurso. Dois arquivos: `produtos/apostilas/Analista Jurídico Defensoria - DPE-AM 2026/perfil.toml` (perfis 2 a 11) e `.../Defensor Público Defensoria - estudo geral (FCC)/perfil.toml` (perfil 1, universo "Todas as questões" mantido). As 11 apostilas existentes foram movidas para as pastas novas. **Testes:** motor dos 11 perfis idêntico à base; apostilas dos perfis 3 e 11 geradas do arquivo com texto idêntico (0 diferenças); mudar o universo no arquivo sem reconfirmar faz o motor recusar as 10 apostilas da pasta; `confirmar --apostila 3` libera só a 3; `sincronizar` e `conferir` fecham. **Depois, a pedido do usuário (16/11/2026): a tabela `perfis` foi aposentada** (renomeada `perfis_aposentada_2026_11_16`; sem fallback em `23`, `70`; `52` não mexe mais nela; o `72` perde `exportar`, `conferir` e `sincronizar` e ganha `novo-concurso`, `nova-apostila` e `mostrar`). Testado numa cópia: perfil novo nasce não confirmado, recebe o id 12, o motor recusa até `confirmar`, e perfil inexistente dá mensagem clara. Motor dos 11 perfis idêntico à base depois da aposentadoria.

### Etapa 3. Aposentar o legado
**Já feito em 16/11/2026 (cortes autorizados pelo usuário, só mover):** scripts `20`, `25`, `29`, `30`, `cmp_gab`, `receptor_local`; apostilas antigas de Penal e DH; Modelo A e B, tudo em `legado/` (ver `legado/LEIA-ME.md`). **Etapa 3 feita em 16/11/2026 (aguarda o usuário ver o resultado):** `28` e `42` movidos para `legado/scripts/`; no `24`, removida a flag `--sem-artefato` e o ramo que lia o programa do `28`; edital real sem artefato agora é recusado com mensagem. **Mantido de propósito:** o caminho do edital fictício (`edital_pontos`, perfil 1, e `edital_itens`), porque o perfil 1 ainda depende dele; a flag `--legado` do `23` (conta antiga) também ficou, por não estar na lista da auditoria; as tabelas antigas continuam no banco (nada apagado). **Teste:** num projeto-cópia, as apostilas dos perfis 3 e 11 saíram com o texto idêntico (0 diferenças em ~1.000 parágrafos e células cada) às de 16/11; perfil 1 gera; edital real sem artefato é recusado. **Falta (Etapa 4):** os documentos históricos (`CLAUDE.md` e `README.md` ainda os citam).
Mover para `legado/` (ou apagar, se o usuário autorizar): `28`, regra antiga de edital, `42` e o que a auditoria apontar. Corrigir as referências nos outros scripts e documentos.

### Etapa 4. Enxugar os documentos
**Feita em 16/11/2026 (aguarda o usuário ver o resultado):** `docs/01-METODO.md`, `docs/02-DECISOES-EM-VIGOR.md` (antes `metodo/04`, com as decisões 42 a 46 novas e a 19 marcada como atualizada), `docs/03-PENDENCIAS.md` (reescrito; o completo está em `docs/arquivo/PENDENCIAS-completo-2026-11-16.md`); históricos e planos 03, 04 e 05 em `docs/arquivo/`; guias em `docs/guias/`; `CLAUDE.md` reescrito (de 19 KB para cerca de 5 KB, com a lista "Leia primeiro" em ordem). Os documentos arquivados mantêm seus links antigos (não corrigidos de propósito).
- Reduzir a três: **método**, **decisões em vigor** e **pendências**. O restante vira arquivo morto.
- Reescrever o `CLAUDE.md` mais curto, com a lista "Leia primeiro" em ordem.
- Limpar o `docs/01-PENDENCIAS.md` (já previsto na Fase F do `05`, item 2).

### Etapa 5. Teste de regressão final
**Feita em 16/11/2026 (aguarda o usuário ver o resultado).** (1) Motor dos 11 perfis, lendo dos `perfil.toml` e com a tabela `perfis` aposentada: idêntico à base (perfis 1 e 2, de DH, comparados com a base já atualizada). (2) Apostilas: regeradas no lugar **só as de DH** (perfis 1 e 2), como o usuário havia pedido; a de DH do perfil 2 mudou em 36 blocos (contagens de questões por tópico variam em 1, efeito de mover Idoso/PcD para DH). As outras 9 foram regeradas **numa cópia fora do projeto, só para comparar**, e o texto foi confrontado com o do commit `70f8ac9`: Administrativo, Constitucional, Penal, Processual Penal e Língua Portuguesa **idênticos**; Processual Civil só no número de página do sumário; Civil, Princípios Institucionais e ECA **diferentes** por causas explicadas (comentários revistos na web depois da última geração; rótulo de origem). **Incidente:** por engano, uma rodada de regeração de todos os perfis foi disparada nos arquivos reais (fora do combinado, que era só DH); o usuário a interrompeu, e as 9 apostilas não-DH foram restauradas byte a byte do commit `70f8ac9` (conferido). **Regra reforçada:** nada fora do plano sem consultar o usuário.
Rodar o motor e gerar as apostilas de todos os perfis; comparar com a versão anterior. Só então dar a organização por concluída.

## 3. Fase posterior: trilhas (cargo de ensino médio)
**BLOQUEADA (16/11/2026, decisão do usuário):** ainda não existem provas de ensino médio para formar o banco de questões, os temas/tópicos e o edital fictício. Nada desta seção começa antes de haver insumos. O que segue é só a ideia discutida.
Depende das Etapas 2 a 4 prontas. Ideia discutida em 15/11/2026: **um banco por "trilha"**, com o mesmo código.
- Trilha jurídica = a atual, sem mover nada. Trilha nova (nome a definir, ex.: "medio" ou "nivel-medio") com `banco/<trilha>/estudos.db`, `dados/<trilha>/`, `provas/<trilha>/` e `produtos/<trilha>/`.
- Scripts gerais compartilhados (`23`, `24`, `26`, `27`, `50` a `52`, `apostila_lib.py`, `lib_escopo.py`) recebem a trilha por opção (`--trilha`); sem a opção, comportam-se como hoje.
- Criador de esquema vazio à parte (o `20` se recusa a rodar de novo, de propósito).
- Disciplinas novas (Matemática, Raciocínio Lógico, Informática) com catálogo próprio; formato de apostila para cálculo a definir.
- **A decidir pelo usuário:** nome da trilha; o que copiar das disciplinas comuns (Português, Constitucional, Administrativo), marcado "copiado, a conferir"; edital fictício próprio da trilha.
- Antes de começar: SWOT e análise do cargo já discutidos no chat; fazer plano próprio (como o `05`) e pedir aprovação.

## 4. Critério de pronto
- Matriz de situação por disciplina publicada e atualizada.
- Um único script de catálogo e classificação; legado separado.
- Três documentos de referência e `CLAUDE.md` curto.
- Regressão sem diferença nos perfis existentes.
- Só então: plano da trilha de ensino médio.
