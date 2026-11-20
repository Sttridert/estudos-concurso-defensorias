# Plano: edital fictício geral de Defensorias e lista de temas por disciplina

Criado em 14/11/2026, depois de entrevista com o usuário. Estado: **plano aprovado nas escolhas abaixo; nenhuma etapa começou.** Cada etapa só começa depois que o usuário vê o resultado da anterior.

## 1. Objetivo e produto final
Montar um **edital fictício geral** de Defensorias (juntando os editais de várias Defensorias e da DPU) e, a partir dele, a **lista de temas por disciplina**. Essa lista é a classificação que o Guia 1 (seção 2) pede: uma lista fechada de assuntos, feita a partir do edital, antes de classificar a primeira questão. Ela servirá, mais tarde, para classificar questões e montar apostilas gerais (modelo A, sem edital).

**Produto final:** um documento por disciplina, no formato **Tema > Tópico > itens do edital fictício**. Cada item mostra a frase literal, a origem e em quantos editais aparece. O mesmo conteúdo fica gravado no banco.

## 2. Decisões confirmadas em 14/11/2026
1. **Cargos:** Defensor Público (Defensorias estaduais e DPU) e Analista Jurídico de Defensoria. Fora: cargos de apoio (Assistente Técnico).
2. **Editais:** todas as Defensorias e a DPU, de **todas as bancas** (não só FCC), cada item com **etiqueta de origem**. FCC-Defensoria 2020+ é o núcleo e vira uma visão própria do edital fictício. A visão "Geral" traz tudo.
3. **Ordem:** piloto com **Direitos Humanos e Direito Penal**; depois as disciplinas do concurso-alvo (DPE-AM 2026, prova em 07/03/2027: Constitucional, Administrativo, Civil, Processual Civil, Processual Penal e ECA/Idoso/Pessoa com Deficiência/Mulher); por último as demais.
4. **Conferência:** em lotes pequenos, no chat (cerca de 10 itens por vez, com a minha sugestão e a razão; o usuário responde "ok" ou corrige).
5. **Estrutura (decisão da IA, com base nos guias):** quatro níveis, descritos na seção 3.

Suposições que o usuário pode mudar: (a) editais de 2018 em diante; os mais antigos só se sobrar tempo; (b) a banca da DPU e os cargos da DPU (Defensor Público Federal; Analista só se tiver parte jurídica) serão confirmados na coleta.

## 3. Estrutura de quatro níveis

| Nível | O que é | Quantos | Nome no banco |
|---|---|---|---|
| 1. Disciplina | Direito Penal, DH etc. | 26 (18 fixadas na Etapa 1 + 8 na revisão da Etapa 3) | `disciplinas` |
| 2. **Tema** | grupo usado para contar quantas questões caíram | **8 a 15 por disciplina** (Guia 1, seção 2) | `assuntos` |
| 3. **Tópico** | unidade em que a questão será classificada | 40 a 60 por disciplina | `pontos` |
| 4. **Item do edital fictício** | frase literal copiada dos editais, com origem e contagem de editais | o que os editais trouxerem | `edital_pontos.trechos` (desenho final na Etapa 4) |

Por que não usar os itens do edital como tema direto: o Guia 1 diz que mais de 15 itens por disciplina dá tabela cheia de zeros e uns; cada edital escreve a mesma coisa de um jeito; e a questão teria de ser classificada entre 100 ou mais itens quase iguais. Por isso o tópico fica no meio, e os itens (muitos, variáveis) se ligam a ele. É o desenho que o banco e os modelos de apostila já usam (decisões 2, 3 e 4).

Termos: **frase** = linha copiada do edital sem alterar uma palavra; **item do edital fictício** = frase consolidada (frases iguais ou equivalentes de editais diferentes viram um item só); **etiqueta de origem** = marca que diz de que tipo de edital veio o item (FCC-Defensoria, outra banca de Defensoria, DPU; mais ano e órgão).

## 4. Etapas

### INÍCIO: preparar
**Etapa 1. Regras e lista de disciplinas.**
Fixar a lista de cerca de 15 disciplinas e o mapa entre os 31 nomes de disciplina do banco e os nomes dos editais (Agrário com 2 questões, por exemplo, é ruído). Resolver a sobreposição entre DH e o bloco "Criança e Adolescente, Idoso, Pessoa com Deficiência e Mulher".
*Pronto quando:* o usuário aprovou a lista de disciplinas e o mapa de nomes.

**Resultado da Etapa 1 (14/11/2026, aguardando aprovação final):** 18 disciplinas na versão 1; mapa dos 31 nomes do banco em `dados/mapa_disciplinas_edital_geral.csv`.
- **Núcleo (13):** Constitucional, Administrativo, Civil, Processual Civil, Penal, Processual Penal, Execução Penal, Criminologia, Direitos Humanos, Criança e Adolescente, Consumidor, Difusos e Coletivos, Princípios e Atribuições Institucionais da Defensoria.
- **Segundo grupo (5):** Empresarial, Tributário, Seguridade Social, Ambiental e Urbanístico, Língua Portuguesa.
- **Decisões do usuário:** Criminologia e Execução Penal são disciplinas separadas; Idoso, Pessoa com Deficiência e Mulher entram dentro de DH; Criança e Adolescente é separada; as disciplinas raras ficam na caixa "Outras".
- **Caixa "Outras":** Filosofia e Sociologia Jurídica, Antidiscriminatório, Saúde, Agrário, Trabalho, História e Geografia regional, Raciocínio Lógico e Informática. **Revisão única da lista ao fim da Etapa 3**, com os editais de DPU e outras bancas: disciplina que aparecer em 3 ou mais editais entra. Só nesse ponto a lista de disciplinas pode crescer.
- **Fora do escopo:** conhecimentos gerais de cargos de apoio (120 questões).
- **Para tratar na geração de apostila:** o edital do DPE-AM 2026 põe Criminologia dentro de Penal e junta Criança, Idoso, Deficiência e Mulher numa disciplina só; a apostila desse concurso junta as disciplinas separadas do catálogo.
- **Para decidir na Etapa 4:** onde fica o tópico PE02 (Criminologia e política criminal) do catálogo de Penal, que hoje tem 0 questões.

**Etapa 2. Inventário de editais.**
Tabela com todos os editais (órgão, cargo, banca, ano, "já tenho" ou "falta", onde baixar). Já temos cerca de 21 editais jurídicos de Defensoria FCC de 2021 a 2026 (16 de Defensor, 5 de Analista) e os de 2018 e 2019 do DPE-AM, todos em `provas/<prova>/1. edital.pdf`.
*Pronto quando:* o usuário aprovou a lista.

**Resultado da Etapa 2 (14/11/2026, aguardando aprovação):** `dados/inventario_editais_edital_geral.csv`.
- **Já temos 22 editais jurídicos distintos** (correção: eram "cerca de 21"; o edital do DPE-AM 2022 está repetido em 3 pastas). São 16 de Defensor e 6 de Analista, de 2018 a 2026, todos FCC.
- **Falta, com fonte conhecida (10 editais):** DPE-SP 2026 (FCC), DPE-PB 2026 servidores (FCC), DPU 2017, DPE-RJ 2026 (FGV), DPE-SC 2026 e 2025 Analista (Fundatec), DPE-BA 2026 Analista Técnico (CEFETBAHIA), DPE-RO 2025 Analista (FGV), DPE-PA 2021 e DP-DF 2019 (Cebraspe); mais a Resolução 255/2026 da DPU (lista de disciplinas, não é edital).
- **Falta, a procurar (cerca de 10):** DPE-RO 2022, DPE-MG 2023, DPE-AC 2024, DPE-PR, DPE-MS, DPE-PE, DPE-PI, TO, SE, AL e concursos de servidores de outras Defensorias. Bancas e anos vêm de blogs e precisam de conferência.
- **Sem edital ainda:** DPU (VII Concurso), DPE-GO, DPE-RN, DPE-RO (VI), DP-DF (Defensor), DPE-AL.
- **Limite do levantamento:** o QConcursos só deixou listar 29 provas de Defensoria, quase todas de 2025 e 2026, e o filtro por instituição pediu plano pago. A lista completa do grupo C depende do TEC ou de pesquisa nos sites das bancas.

**Resultado da Etapa 3 (14/11/2026, coleta feita; falta aprovar a revisão da lista de disciplinas):** 27 editais novos baixados, na convenção `provas/<ano> - <órgão> - <cargo> (edital, sem prova)/1. edital.pdf`. O repositório passa a ter **49 editais jurídicos** (22 que já tínhamos + 10 do grupo B + 17 do grupo C), todos com camada de texto (sem OCR). Situação de cada um em `dados/inventario_editais_edital_geral.csv`.
- **Fontes:** site oficial da FCC (DPE-SP 2026), site do Cebraspe (DPU 2017, DPE-PA, DP-DF, DPE-RO) e QConcursos (os demais, por links diretos de arquivo; sem baixar caderno nem gabarito).
- **Pendente:** Resolução 255/2026 da DPU (não é edital), edital do DP-DF 2026 (Analista; banca divergente nas fontes) e a retificação do conteúdo programático da DPE-MG 2023.
- **Conferir na Etapa 4:** DPE-RJ 2026 (o texto traz poucas linhas de programa; talvez o conteúdo esteja em anexo separado), DPE-SE 2021 (só 10 páginas) e os editais de Analista de RO, PR e BA (o programa usa outros títulos).
- **A regra de parada por saturação** acabou sem uso na coleta, porque todos os editais com link direto foram baixados. Ela passa a valer na Etapa 4: processo os editais em ordem (FCC-Defensoria, DPU, depois os demais por data) e paro quando os últimos 5 não trouxerem item novo em mais de 2% das frases.

**Revisão da lista de disciplinas (14/11/2026, decidida pelo usuário; lista v2 com 26 disciplinas).** Contagem aproximada em 48 editais lidos. Entram, além das 18:
- Pela regra de 3 ou mais editais: **Filosofia, Sociologia Jurídica e Ciência Política** (21 editais; o edital da DPU 2017 traz as três como títulos), **Direito Internacional** (11), **Direito à Saúde** (7), **Direito Agrário** (5), **Direito Antidiscriminatório e Étnico-Racial** (5).
- Por pedido do usuário, por causa da DPU (exceções à regra): **Direito do Trabalho e Processual do Trabalho**, **Direito Eleitoral** e **Direito Militar** (Penal Militar e Processual Penal Militar). Decisão da IA, a corrigir se o usuário quiser: Trabalho e Processo do Trabalho viram uma disciplina só, e Penal Militar e Processual Penal Militar também, para não multiplicar disciplinas pequenas; os itens do edital da DPU continuam identificáveis.
- **Ficam fora:** História e Geografia regional (conteúdo local, muda por Estado), Direito Digital/LGPD (a conferir; pode ser subitem de outras disciplinas), Raciocínio Lógico e Informática (só Analista, poucas questões). **Populações vulneráveis** (Resolução 255/2026 da DPU) fica dentro de DH. Reavaliar tudo isso quando o edital da DPU sair.
- **Proposta a confirmar quando chegarmos nelas:** disciplinas pequenas (Trabalho, Eleitoral, Militar, Agrário, Saúde, Internacional) têm poucas questões no banco, então terão de 3 a 8 temas e não de 8 a 15; a regra de 8 a 15 vale para disciplinas com cerca de 40 questões ou mais.
- Mapa atualizado em `dados/mapa_disciplinas_edital_geral.csv`. A lista de disciplinas fica **congelada** a partir daqui.

**Etapa 3. Coleta.**
Baixar os que faltam (TEC e QConcursos pelo Chrome; se falhar, site da banca ou da Defensoria; se falhar de novo, pedir o arquivo ao usuário). **Um edital por vez, no máximo 2 tentativas** em cada fonte. Salvar em `provas/<ano> - <órgão> - <cargo> (edital, sem prova)/1. edital.pdf` (mesma convenção do edital DPE-AM 2026). Não alterar PDFs já existentes.
**Regra de parada por saturação:** coletar nesta ordem: FCC-Defensoria (já temos), DPU, outras Defensorias da mais recente para a mais antiga. Parar quando os últimos 5 editais coletados não trouxerem item novo em mais de 2% das frases de cada disciplina do piloto.
*Pronto quando:* cada edital da lista está salvo ou marcado "não achei".

### MEIO: construir
**Etapa 4. Piloto com DH e Penal.**
1. Extrair o programa de cada edital (texto direto; OCR só se preciso, e marcado "texto a conferir"), frase por frase, literal.
2. Juntar frases equivalentes e fazer a tabela de sinônimos. Marcar a origem e contar em quantos editais cada item aparece (núcleo, comum, raro).
3. Marcar o que é **novo**, **exclusivo** ou **detalhado demais** (Guia 2, capítulo 2).
4. Propor temas e tópicos **ampliando os que já existem** (DH: 11 temas e 59 tópicos; Penal: 14 temas e 53 tópicos). Os códigos atuais não mudam; só entram tópicos novos para os buracos.
5. Antes de criar tabelas no banco, mostrar o desenho ao usuário. O banco nunca é recriado; só se acrescentam tabelas, com cópia em `banco/backup/` antes.
*Parada:* o usuário confere, em lotes de cerca de 10 itens, os itens incertos e as decisões de junção, e aprova o método.

**Andamento da Etapa 4 (14/11/2026, aguardando decisões do usuário):**
- **Scripts novos:** `scripts/40_extrair_programas.py` (acha o programa de DH ou de Penal em cada edital e o divide em itens e frases, sem alterar o banco) e `scripts/41_consolidar_itens.py` (junta frases iguais ou quase iguais, marca origem, conta itens novos por edital e liga cada item aos tópicos). Saídas em `dados/programas_editais/<DH|PENAL>/` e `dados/edital_ficticio_geral/<DH|PENAL>_itens.json`.
- **Teste de acerto do extrator:** no DPE-AM 2026, as 76 frases de DH e as 70 de Penal que tínhamos copiado à mão saíram idênticas (76 de 76 e 70 de 70).
- **Resultado:** DH = 41 editais com programa, 4.766 frases, **1.291 itens distintos**. Penal = 43 editais, 3.980 frases, **870 itens distintos**.
- **Editais sem extração (ficam em quarentena, fora das contas):** DH: DPE-SE 2021 (duas colunas), DPE-CE 2022 (DH é o item 5 dentro de Direito Constitucional), DPE-PR 2024 (não traz DH como disciplina), DPE-RJ 2018 e 2026, e os de Analista de PR, RO e SC (não têm DH). Penal: DPE-SE 2021, DPE-MT 2022, DPE-PR 2024, DPE-RJ 2026 e os de Analista de PR e RO.
- **Regra de parada por saturação:** não parou. Os últimos editais ainda trazem 5% a 50% de itens "novos", mas isso é diferença de redação (Cebraspe e FGV escrevem por item, não por frase), não matéria nova. Por isso a saturação passa a ser medida por **tópico** e não por frase; todos os editais foram aproveitados.
- **Ligação aos tópicos existentes (por palavras-chave, rascunho):** DH 1.146 itens em tópicos atuais, 48 em tópicos novos propostos, 97 sem tópico; Penal 570 em tópicos atuais, 36 em novos, 50 de outras disciplinas (Execução Penal 46, Direito Militar 3, Processo Penal 1) e 214 sem tópico.
- **Tópicos propostos:** DH02.06, DH03.05, DH07.05, DH08.12, DH09.04, DH10.11; Penal PE03.04, PE08.07, PE14.12. Os temas (11 em DH e 14 em Penal) não mudam.
- **Tópicos do catálogo sem item literal em edital:** DH10.09 (Bioética). Os demais tópicos de DH e Penal têm apoio nos editais.
- **Decisões do usuário em 14/11/2026 (lote 1):** (a) DH: criar DH02.06, DH07.05, DH08.12, DH09.04 e DH10.11 e fundir os tratados avulsos no DH03.02 (renomeado "Declaração Universal, pactos da ONU e outros tratados"); (b) Penal: criar PE08.07 e PE14.12 e fundir imunidades e extradição no PE03.02 (renomeado "Lei penal no espaço, tempo e lugar do crime, imunidades e extradição"); (c) o tema PE02 (Criminologia e política criminal) vai para a disciplina Criminologia, e os 120 itens de edital dele ficam marcados "Criminologia (PE02)"; (d) desenho do banco aprovado: cada edital vira uma linha de `editais` (tipo "real") e entram 3 tabelas novas (itens do edital fictício; ligação item-tópico; ocorrência literal de cada frase em cada edital), com cópia em `banco/backup/` antes. **Nada foi gravado no banco ainda**; a gravação é a Etapa 7. Lista das mudanças: `dados/edital_ficticio_geral/topicos_aprovados_2026-11-14.csv`.
- **Números depois das correções (14/11/2026):** DH = 4.879 frases, 1.252 itens; 1.146 ligados a tópicos, 106 sem tópico. Penal = 4.035 frases, 860 itens; 561 ligados a tópicos, 103 de outras disciplinas (Execução Penal, Processo Penal, Direito Militar, Criminologia fica nos tópicos PE02), 196 sem tópico.
- **Qualidade da ligação (rascunho da máquina):** em amostra de 10 itens sorteados, 7 saíram totalmente certos e 3 trouxeram um tópico a mais por palavra-chave larga; as regras foram apertadas e uma nova amostra vai ao usuário.

**Etapa 5. Teste de encaixe.**
As questões já classificadas de DH e Penal cabem nos temas e tópicos novos? **Meta: 95% ou mais sem mexer em nada.** Se não bater, uma única rodada de ajuste; se continuar abaixo, parar e conversar.
*Pronto quando:* a meta foi atingida e o usuário viu o resultado.

**Resultado da Etapa 5 (14/11/2026, aguardando o usuário ver):** `scripts/42_teste_encaixe.py` (só leitura). Aprovações do usuário antes dela: método da Etapa 4 (lote 2 de 10 itens), estrutura do tema PE14 (um tópico por lei, mais o PE14.12 "Outras leis penais especiais") e desenho do banco.
- **Questões testadas:** 176 de DH e 42 de Penal, já classificadas (tópico principal).
- **A. Estrutura:** o tópico continua existindo depois das mudanças aprovadas: 176 de 176 (DH) e 42 de 42 (Penal) = 100%.
- **B. Edital:** o tópico tem item literal nos editais: 174 de 176 (DH, 99%; as duas exceções são do DH10.09, Bioética) e 42 de 42 (Penal, 100%).
- **C. Conteúdo, por palavras-chave:** 91% (DH) e 93% (Penal) "não contradizem". Li as 18 divergências uma a uma (15 de DH e 3 de Penal): **todas as classificações atuais estão corretas**; a divergência vem de palavra-chave larga demais (ex.: "tratado" ou "saúde pública" puxando outro tópico). Só **1 candidata a mudar**: DPE-BA 2026 Q100 ("Programa de proteção a defensores de direitos humanos"), hoje em DH07.01, que caberia melhor no novo DH07.05. Fica anotada para a reclassificação futura; nada foi mudado.
- **Conclusão:** 217 de 218 questões encaixam sem mexer em nada (99,5%), acima da meta de 95%. Não foi preciso nenhuma rodada de ajuste.
- **Correção feita no caminho:** a regra do PE14.12 pegava "crime de..." qualquer; foi apertada (Penal: 556 itens ligados a tópicos, 27 em tópicos novos, 103 de outras disciplinas, 201 sem tópico).

**Etapa 6. Escala, uma disciplina por vez.**
Ordem: as disciplinas do concurso-alvo (Constitucional, Administrativo, Civil, Processual Civil, Processual Penal, ECA/Idoso/Pessoa com Deficiência/Mulher) e, depois, as demais (Português e Legislação da Defensoria entram aqui, por causa do Analista). Cada disciplina repete a rotina da Etapa 4.
*Pronto por disciplina:* 8 a 15 temas; 100% das frases com tópico; nenhum tópico vazio; o usuário conferiu e aprovou.

### FIM: fechar
**Etapa 7. Edital fictício geral no banco.**
Gravar o edital geral e as visões (Geral, FCC-Defensoria 2020+, DPU, Analista). O edital fictício atual de DH (`editais.id = 1`, só de DH) passa a ser a visão FCC-Defensoria do novo.

**Etapa 8. Produto final.**
Um documento por disciplina (Tema > Tópico > itens do edital) e um resumo de uma página.
*Pronto quando:* 100% das frases têm tópico; nenhum tópico vazio; 8 a 15 temas por disciplina; o usuário aprovou; **a lista é congelada como versão 1**.

**Etapa 9. Registro.**
Atualizar `CLAUDE.md`, `docs/01-PENDENCIAS.md`, `docs/metodo/04-DECISOES-CONFIRMADAS.md` e a memória. Commit feito pela IA; push só se o usuário pedir.

### Ciclo por disciplina (decidido em 14/11/2026, a pedido do usuário)
As etapas 6 a 9 passam a rodar **uma disciplina de cada vez**, para que cada disciplina concluída já possa ser usada, mesmo que o plano seja interrompido. Uma disciplina só entra em "concluída" quando passa por todos os passos abaixo.

| Passo do ciclo | Corresponde a | O que acontece com a disciplina X | Pronto quando |
|---|---|---|---|
| 1. Extração e consolidação | Etapa 6 | Lê o programa de X em cada edital, junta as frases em itens e marca a origem | Itens gerados e editais em quarentena listados |
| 2. Temas e tópicos | Etapa 6 | Propõe de 8 a 15 temas e de 40 a 60 tópicos (ou de 3 a 8 temas, se for disciplina pequena) e liga os itens aos tópicos. Em DH e Penal já existiam; nas demais, são criados a partir dos editais | Cobertura de itens ligados e lista de temas e tópicos propostos |
| 3. Conferência | Etapa 6 | O usuário confere em lotes de cerca de 10 itens e aprova os temas e tópicos | Usuário aprovou; lista **congelada em versão 1** |
| 4. Gravação no banco | Etapa 7 | Cópia de `banco/backup/` antes; grava temas, tópicos, itens, ligações e frases literais de X | Contagens do banco batem com os arquivos |
| 5. Documento | Etapa 8 | Gera o documento de X (Tema > Tópico > itens do edital) | Cada frase tem tópico; nenhum tópico vazio; usuário viu |
| 6. Registro | Etapa 9 | Atualiza pendências e decisões e faz commit (push só se o usuário pedir) | Commit feito |
| 7. Concluída | | X vira "concluída v1". Se houver questões classificadas, roda o teste de encaixe (Etapa 5) | Marcada no quadro de andamento |

- **O que continua sendo único, feito uma só vez:** a linha do "edital fictício geral" em `editais`, a gravação dos 49 editais coletados como linhas `real` (feita junto com a primeira disciplina gravada), as visões Geral, FCC-Defensoria, DPU e Analista (são consultas ao banco, não cópias) e o resumo de uma página com todas as disciplinas (feito ao final, ou a qualquer momento só com as concluídas).
- **Teste de encaixe:** só vale para disciplinas com questões já classificadas (hoje DH e Penal). Nas outras, a classificação das questões é o plano seguinte.
- **DH e Penal já estão no passo 3 concluído** (método e tópicos aprovados, encaixe 99,5%). Faltam os passos 4 a 7 para elas.

**Reprocessamento de 14/11/2026 (melhoria de cobertura):** os editais DPE-SE 2021 (duas colunas embaralhadas) e DPE-RO Analista 2025 (seção de Civil com programa de outros cargos) foram excluídos das disciplinas que contaminavam; Constitucional, Administrativo, Processual Civil, Processual Penal e Civil foram regravadas (cópias `estudos_antes_regravar_*`). Os códigos de item mudaram; nada dependia deles. Itens sem tópico próprio podem ser resolvidos à mão em `dados/edital_ficticio_geral/ajustes_<disciplina>.json`.

**Melhoria de cobertura nas demais disciplinas (14/11/2026):** o mesmo método do Civil foi aplicado a DH, Penal, Constitucional, Administrativo, Processual Civil e Processual Penal: (1) regras de "outra disciplina" para o conteúdo que vaza (criminologia e execução penal em Processo Penal, consumidor em Processual Civil, administrativo em Constitucional etc.), (2) fragmentos genéricos separados, (3) exclusão do DPE-PR Analista 2023 do Administrativo, (4) classificação à mão da cauda longa em `ajustes_<disciplina>.json` (cerca de 1.100 itens lidos). Resultado: **nenhuma disciplina tem item sem destino** e a ligação a tópico ficou em DH 98%, Administrativo 92%, Processual Civil 89%, Constitucional 87%, Civil 86%, Processo Penal 79% e Penal 77% (o restante é conteúdo de outras disciplinas e fragmentos genéricos). Nenhum tópico novo foi preciso.

**Quadro de andamento por disciplina** (atualizar a cada passo):

| Disciplina | Passos concluídos | Situação |
|---|---|---|
| Direitos Humanos | 1 a 7 | **concluída v1 (14/11/2026)**: 1.252 itens gravados; documento de 84 páginas; encaixe 99,5% |
| Direito Penal | 1 a 7 | **concluída v1 (14/11/2026)**: 860 itens gravados; documento de 47 páginas; PE02 segue para Criminologia |
| Direito Constitucional | 1 a 7 | **concluída v1 (14/11/2026)**: taxonomia congelada com 15 temas e 42 tópicos; 1.470 itens gravados; documento de 77 páginas; sem teste de encaixe (as 202 questões ainda não foram classificadas) |
| Direito Administrativo | 1 a 7 | **concluída v1 (14/11/2026)**: taxonomia congelada com 15 temas e 36 tópicos (AD10.03 fundido no AD10.01 e AD06.03 no AD06.01); 1.777 itens gravados; documento de 79 páginas; sem teste de encaixe (as 146 questões ainda não foram classificadas) |
| Direito Processual Civil | 1 a 7 | **concluída v1 (14/11/2026)**: taxonomia congelada com 12 temas e 30 tópicos (PC11.02 fundido no PC11.01); 1.183 itens gravados; documento de 58 páginas; sem teste de encaixe (as 194 questões ainda não foram classificadas) |
| Direito Processual Penal | 1 a 7 | **concluída v1 (14/11/2026)**: taxonomia congelada com 9 temas e 22 tópicos; 888 itens gravados (66 itens de Execução Penal guardados para o ciclo dela); documento de 39 páginas; sem teste de encaixe (as 153 questões ainda não foram classificadas) |
| Direito Civil | 1 a 7 | **concluída v1.1 (14/11/2026)**: 12 temas e 50 tópicos (CV01.03 Teoria geral do direito privado criado); 1.699 itens gravados, 86% ligados a tópico, 214 de outras disciplinas, 24 fragmentos genéricos e nenhum sem destino (cauda longa classificada à mão em `ajustes_CIV.json`); sem teste de encaixe (as 128 questões ainda não foram classificadas) |
| Direito da Criança e do Adolescente | 1 a 7 | **concluída v1 (14/11/2026)**: 8 temas e 28 tópicos (crimes e infrações administrativas fundidos em CA08.01 a pedido do usuário); 775 itens gravados de 35 editais, 95% ligados a tópico, 40 de outras disciplinas (Direitos Humanos 21, texto de edital 10, conteúdo local 9), 1 fragmento genérico e nenhum sem destino (cauda longa classificada à mão em `ajustes_ECA.json`); 14 editais em quarentena (sem seção da disciplina); sem teste de encaixe (as questões ainda não foram classificadas) |
| Execução Penal | 1 a 7 | **concluída v1 (15/11/2026)**: 9 temas e 33 tópicos (EX01 a EX09; taxonomia congelada pelo usuário); 414 itens gravados (42 editais; Penal e Processual Penal entram como origem), 7 itens de Direito Penal marcados para esse ciclo e 8 fragmentos genéricos; documento em `produtos/edital-ficticio/`; cópia `banco/backup/estudos_antes_edital_geral_exec_2026-11-15.db`; só as 2 questões do universo Analista FCC foram classificadas (`scripts/62`); sem teste de encaixe (menos de 5 questões). As outras 97 questões de Execução Penal do banco seguem sem classificação |
| Demais disciplinas da lista v2 (menos Execução Penal) | | não iniciadas |

## 5. Fora deste plano (próximo plano)
Classificar as questões das outras disciplinas (milhares) e gerar as apostilas gerais. Só começa depois do produto final aprovado. Em 14/11/2026 já foram feitos: conferência dos tópicos renomeados, revisão de DH nos tópicos novos e classificação de Penal e das demais 6 disciplinas concluídas (1.219 questões classificadas, rascunho da IA). As 83 questões em disciplina errada também foram tratadas (81 movidas; 1.273 classificadas no total). Falta a amostra de conferência e as 29 questões movidas para disciplinas sem catálogo: ver `docs/01-PENDENCIAS.md`, seção "Ligar as questões aos tópicos novos".

## 6. Regra contra desvios
- Problema que **não trava** a etapa: vai para a lista "Depois" (`docs/01-PENDENCIAS.md`) e o plano segue.
- Problema que **trava**: usar a solução já escolhida na seção 7.
- Problema que **não está** na seção 7: parar e perguntar ao usuário, explicando o contexto em linguagem simples.
- Lista de disciplinas e de editais **congeladas** nas Etapas 1 e 2. Pedido novo vai para "Depois".
- A lista de temas de uma disciplina **não muda** depois de aprovada (Guia 1). Se for preciso dividir um tema, reclassificar todas as questões dele.

## 7. Riscos e soluções já decididas

### Fraquezas (internas)
| Risco | Solução |
|---|---|
| DH e Penal foram feitos antes do edital geral e podem pedir retrabalho | "Ampliar, não refazer": códigos atuais ficam; só entram tópicos novos para os buracos. A Etapa 5 mede o encaixe |
| Tema demais gera tabela de zeros (Guia 1) | Teto de 15 temas por disciplina; tópicos podem ser muitos, mas só os temas são contados |
| A IA junta frases equivalentes errado e ninguém percebe | O script 28 já recusa trecho que não exista literalmente no edital; o usuário confere itens incertos e decisões de junção em lotes |
| O banco tem 31 "disciplinas", muitas são ruído | A Etapa 1 fixa a lista e o mapa de nomes |
| Cansaço de decidir com termos técnicos | Lotes de cerca de 10 itens, com exemplo e recomendação; o usuário só diz "ok" ou corrige |
| O escopo cresce | Lista de editais e de disciplinas congelada; pedido novo vai para "Depois" |
| Mais editais do que dá para conferir | Regra de parada por saturação (Etapa 3) |

### Ameaças (externas)
| Risco | Solução |
|---|---|
| TEC ou QConcursos negam acesso, caem ou mudam; downloads em lote já falharam | Um edital por vez; 2 tentativas; depois site da banca ou da Defensoria; depois pedir o arquivo ao usuário; senão "não achei" |
| DPU e outras bancas têm estrutura diferente e inflam o edital | Etiqueta de origem e visões separadas; nada da DPU entra na contagem de questões da FCC |
| O mesmo tema com nomes diferentes vira duplicata | Tabela de sinônimos (Etapa 4) |
| Erro de lei no próprio edital (DPE-AM 2026 cita "Lei 15.343/06" para a Lei de Drogas) | Manter literal, com nota "erro do edital" |
| O edital geral vira um "mega-edital" que não prioriza nada | Cada item mostra em quantos editais aparece (núcleo, comum, raro) |
| A prova de 07/03/2027 se aproxima | Ordem das disciplinas segue o concurso-alvo; o edital real do DPE-AM sempre prevalece (decisão 19) |
| PDF digitalizado gera frase com erro de OCR | Preferir editais com camada de texto; os de OCR ficam "texto a conferir" |

## 8. O que já existe e será aproveitado
- `banco/estudos.db`: tabelas `editais`, `edital_pontos`, `pontos`, `assuntos`; scripts `21`, `28` e `31`.
- Editais FCC em `provas/`. O edital real do DPE-AM 2026 tem JSON próprio (`dados/edital_dpeam2026_analista_*.json`) e prevalece sobre o fictício.
- Os guias: Guia 1 (seção 2: lista fixa de 8 a 15 assuntos) e Guia 2 (capítulo 2: novo, exclusivo e detalhado demais).
