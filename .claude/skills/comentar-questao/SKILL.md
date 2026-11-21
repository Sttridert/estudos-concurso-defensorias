---
name: comentar-questao
description: Roteiro do grupo E para comentar questões do universo de um perfil (comentário, pegadinha, dispositivos) com fonte oficial e sem alucinação. Use quando o usuário pedir para comentar questões, completar comentários ou conferir comentários marcados "confirmar".
---

# Comentar questões (grupo E)

Escrever em português simples. Tudo que a IA produz aqui é **rascunho** até o usuário conferir. Decisão 59 do `docs/02-DECISOES-EM-VIGOR.md`.

1. **Listar o que falta** (só leitura): `python -I scripts/comentar_pendentes.py --perfil ID --saida <pedido.json>` (use a pasta temporária; `--pendentes` inclui os marcados "confirmar"). Só comentar o que o usuário pediu; não reescrever comentário existente.
2. **Texto-fonte primeiro.** Para cada dispositivo que o comentário vai citar, trazer o texto oficial (site do Planalto, tribunal) para `dados/fontes/<arquivo>.txt`, com URL e data na primeira linha. Dispositivo que não está em `dados/fontes/` **não pode ser citado como conferido**. Nunca citar lei, súmula ou julgado de memória: se não achar a fonte, não citar, ou marcar `pend: 1` e escrever "confirmar no Planalto/tribunal".
3. **Decidir a alternativa pelo dispositivo**, depois comparar com o gabarito do pedido. Se divergir, não forçar o comentário: registrar como alerta de gabarito e perguntar ao usuário.
4. **Escrever** o JSON (chave `"<prova>|<número>"`): `c` (por que a certa é certa e por que cada errada é errada), `p` (pegadinha), `d` (`"Norma|dispositivo"`), `pend`, e `fontes` com, para cada dispositivo, um **trecho literal** copiado do arquivo, `arquivo`, `url` e `consultado_em`. Cada dispositivo de `d` precisa do trecho que prova aquela alternativa (a fonte certa, mas fora do assunto, é o erro mais perigoso).
5. **Verificação separada só nas arriscadas** (súmula, tema do STF, lei recente, doutrina, gabarito preliminar): chamar um subagente que receba **só a pergunta e o arquivo-fonte, sem o comentário**; se divergir, `pend: 1`.
6. **Gravar** só por `python -I scripts/comentar_gravar.py arq.json --perfil ID` (simula); mostrar o resultado ao usuário; só com o "sim" `--aplicar`. Nunca escrever direto na tabela `comentarios`. Conferência web de comentário já marcado: `scripts/64_aplicar_revisao_web.py` (exige fonte).
7. **Depois:** `python -I scripts/comentar_exportar.py`, atualizar `docs/03-PENDENCIAS.md` e rodar `python -I scripts/73_conferir_docs.py`.
