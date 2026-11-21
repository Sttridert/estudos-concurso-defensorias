# CLAUDE.md

Orientação para o Claude Code neste repositório. Escrever sempre em português, em linguagem simples, e **presumir que o usuário precisa de contexto** em toda explicação ou pergunta.

## O que é o projeto
Apoio a estudos para concursos públicos de **Defensorias (banca FCC)**, por disciplina. Fluxo: provas e editais anteriores → banco único (`banco/estudos.db`) → perfil → motor de análise → **apostila** por disciplina (Word). Foco atual: o concurso **DPE-AM 2026 (Analista Jurídico)**, com 10 apostilas geradas, uma por bloco do edital (perfis 2 a 11), e a apostila de DH sem edital (perfil 1). Tudo que a IA produz é **rascunho** até o usuário conferir.

## Leia primeiro (nesta ordem)
1. `README.md`: mapa do repositório e como rodar.
2. `docs/01-METODO.md`: como o projeto funciona (banco, perfil, pesos, ciclo por disciplina, edital real, modelo da apostila, scripts).
3. `docs/02-DECISOES-EM-VIGOR.md`: decisões do usuário; **mandam sobre o resto**.
4. `docs/03-PENDENCIAS.md`: **única fonte do estado do projeto** (o que está feito, em curso, bloqueado e a decidir).
5. Planos: `docs/06-PLANO-MELHORIAS-E-ORGANIZACAO.md` (e `07-AUDITORIA-ETAPA-1.md`) e `docs/arquivo/08-PLANO-FLUXOS-E-PORTEIRO.md` (só histórico). O andamento de cada plano está no `03`, não aqui.
Histórico (só se precisar): `docs/arquivo/`. Guias da análise: `docs/guias/`. Scripts aposentados: `legado/`.

## Estrutura
```
banco/       estudos.db (fonte única, nunca recriado), fontes/ (texto-bruto, fonte_tec, gabaritos_fcc), analise/ (gerada), backup/ (só local), base-regressao-*/
dados/       catalogo/ e classificacao/ (por disciplina), comentarios/, fontes/ (normas oficiais), editais_reais/, referencia/, revisao_web/, coleta/ (insumos da coleta: manifesto de provas, listas da FCC, textos-base, correções de texto, inventário e universos de editais), disciplinas.json
docs/        01-METODO, 02-DECISOES-EM-VIGOR, 03-PENDENCIAS, planos em curso, guias/, arquivo/
produtos/    apostilas/<concurso>/ (perfil.toml + Word); modelos/ (só base-estilos.docx)
provas/      <ano - órgão - cargo>/ com edital, caderno, gabarito (PDF originais; não alterar; ficam só locais)
scripts/     código Python numerado (mapa em docs/01-METODO.md, seção 9); rodar com `python -I`
legado/      scripts, apostilas e modelos aposentados (ver legado/LEIA-ME.md)
requirements.txt   o que instalar para rodar do zero: pacote Python e programas externos (Tesseract com idioma `por`, Poppler, LibreOffice, curl)
```

## Regras que valem sempre
- **Ambiente (clonar do zero):** instalar o que está em `requirements.txt` (pacotes Python por `pip` e, no cabeçalho do arquivo, os programas externos e o idioma `por` do Tesseract) antes de rodar qualquer script. Se um script novo precisar de pacote ou programa novo, acrescentar ali na mesma hora.
- **Banco:** nunca recriar; cópia em `banco/backup/` antes de qualquer gravação; `--simular` quando existir. Chave da questão: prova + número.
- **Perfil:** mora em `produtos/apostilas/<concurso>/perfil.toml` (única fonte; a tabela `perfis` do banco foi aposentada; criar com `scripts/72_perfil.py novo-concurso` e `nova-apostila`). Mínimo = disciplina, carreira ou cargo, e banca. Mostrar ao usuário e **pedir confirmação** antes de gerar (`72 confirmar` só depois do "sim"; mudar o perfil, ou o catálogo e o edital classificado que a apostila usa, sem reconfirmar faz o motor recusar). **Não regerar apostilas existentes sem o usuário pedir.**
- **Pedido de apostila com edital:** rodar primeiro `scripts/70_porteiro_edital.py --edital ID --disciplina "..."` (só leitura); se a disciplina não consta no edital, recusar e listar as que constam (decisão 41). Para gerar, o `24` já aplica o semáforo (`lib_semaforo`): se algo bloqueia, só gera com `--gerar-mesmo-assim "motivo"` (o motivo vai para a capa); `scripts/produzir_status.py` diz quais apostilas estão desatualizadas. Edital real sem artefato: montar com `coletar_programa_edital.py extrair`, `51` e `52`. **Atenção:** o `51` e o `52` recusam `decisoes.txt` sem `VERSAO_CATALOGO v2`; os dois editais existentes (DPE-AM e DPE-PB) ainda estão em códigos do v1, então use antes `scripts/mapear_codigos_v1_v2.py traduzir <slug>` (gera uma proposta, não altera o original) e confira com o usuário.
- **Disciplina nova (grupo B):** o catálogo nasce no **rascunho v2**, (o antigo `71 semear` foi aposentado) (decisões 53 a 55; roteiro completo em `docs/01-METODO.md`, seção 10): `scripts/catalogar_novo.py evidencia` (o que os editais trazem) e `criar` (rascunho do zero a partir de um roteiro); editor visual, `catalogar_coerencia` e `catalogar_cobertura`; o usuário aprova cada rascunho; só então `scripts/catalogar_publicar.py --simular` e, quando o usuário mandar, `--aplicar --sim-do-usuario`. Depois: comentar as questões do universo do perfil (decisão 40), confirmar o perfil, rodar `23` e `24`. **Não rodar scripts de `legado/`.**
- **Comentários (grupo E):** seguir a skill `.claude/skills/comentar-questao` (decisão 59): gravar só por `scripts/comentar_gravar.py` (simula por padrão), citar dispositivo só com trecho literal de `dados/fontes/`, nunca sobrescrever comentário `conferido`.
- **Conteúdo:** nunca citar lei, súmula ou julgado sem certeza (usar "confirmar"; blog: "confirmar no Planalto/tribunal"); dúvida de comentário, pesquisar a fonte oficial na web; declarar a amostra ao lado de qualquer número; teste retroativo com menos de 5 provas é ruído.
- **Processo:** só abrir arquivos e produtos quando o usuário pedir; cada etapa grande só começa depois que o usuário vê o resultado da anterior; commit local só quando pedido e push só a pedido; não alterar os PDFs de `provas/`.
- **Regressão:** antes de mudar código ou dados que afetem as apostilas, comparar a saída do motor dos 11 perfis com `banco/base-regressao-2026-11-20/` (e a etiqueta git `base-regressao-2026-11-20`); o motor lê o banco por caminho fixo; `python -I scripts/produzir_regressao.py` faz tudo isso numa cópia temporária (ver também o `LEIA-ME.txt` da base). A base de 2026-11-16 é anterior ao catálogo v2 e não compara direto. Ao gravar classificações em lote com o `mapear_aplicar_classificacao.py`, faça essa conferência antes (o script só valida e simula; não roda o motor): A/B nos 11 perfis, e se vier diferença não esperada, parar e consultar.

## Regra de documentação (evita contradição entre documentos)
- **O estado mora em um só lugar:** `docs/03-PENDENCIAS.md`. `CLAUDE.md`, `README.md`, `01` e `02` não dizem "etapa X feita", "falta Y" nem "em andamento"; só apontam para o `03`. Os planos (`06`, `08`...) descrevem o que fazer e o que foi feito *naquele plano*; o andamento atual fica no `03`.
- **Ao terminar qualquer tarefa que mude o estado:** atualizar o `03` (marcar `[x]` com data, ou abrir item novo) e **mais nenhum lugar** para o estado. Item resolvido sai de `[ ]` na mesma hora.
- **Documento novo em `docs/`:** citar no `CLAUDE.md` (lista "Leia primeiro") ou já criá-lo em `docs/arquivo/`.
- **Antes de dar a tarefa por terminada (e antes de commitar documentos):** rodar `python -I scripts/73_conferir_docs.py`; corrigir todo ERRO. O script só lê; confere docs citados, itens `[ ]` já resolvidos, estado repetido fora do `03` e caminhos citados que não existem.
- A memória do Claude (`MEMORY.md`) não guarda estado do projeto: só preferências e ponteiros para o `03`.
