# Modelos de apostila: como usar (para o agente)

> **AVISO (14/11/2026): os arquivos `Modelo A` e `Modelo B` estão OBSOLETOS e não são lidos por nenhum script.** O desenho real da apostila está no código: `scripts/apostila_lib.py` (cartão, tabelas, tags) e `scripts/24_gerar_apostila.py` (montagem). O único arquivo desta pasta que o gerador usa é `base-estilos.docx` (estilos, cabeçalho, rodapé; não editar). Para ver o modelo atual, gere uma apostila (o arquivo sai com o sufixo ` [modelo novo]`). O resto deste LEIA-ME descreve o desenho e os scripts ANTIGOS (cartão com faixa de tópico, respostas no fim do capítulo, scripts 03 a 15 que não existem mais); consulte `docs/04-PLANO-MODELO-APOSTILA-V2.md` e o `CLAUDE.md`.


Criado em 12/11/2026. Leia também `../../docs/00-PLANO-E-ROTEIRO.md` e `../../docs/01-PENDENCIAS.md`.

## Arquivos
| Arquivo | Para quê |
|---|---|
| `Modelo A - Apostila sem edital (por disciplina).docx` | Estudar **uma disciplina** com base só nas provas anteriores de um grupo de concursos (como a apostila de Direitos Humanos). |
| `Modelo B - Apostila com edital (por concurso).docx` | Estudar para **um concurso com edital publicado**, uma ou mais disciplinas, com o edital verticalizado no prefácio (desenho da "Apostila inicial - Penal e Direitos Humanos"). |
| `base-estilos.docx` | Cópia da apostila-modelo original; os geradores usam seus estilos, numeração, cabeçalho e rodapé. Não editar. |
| `../../scripts/apostila_lib.py` | Biblioteca do design (cartão, caixa, tabelas, chips, capa). Todo componente visual sai daqui. |
| `../../scripts/24_gerar_apostila.py` | Gerador genérico da apostila (modelo A, a partir do banco e do perfil). Exemplo de uso da biblioteca. |
| (removido) | O gerador antigo dos modelos lia o banco antigo e foi retirado do projeto; os `.docx` prontos continuam aqui. |

Os modelos têm **comentários do Word** (aba Revisão) explicando cada bloco. Para ver: abra o `.docx` no Word. Para entregar um documento final: Revisão > Excluir > Excluir todos os comentários.

## Design (não mudar sem pedido do usuário)
- Calibri; corpo 10,5 pt; cartões 10 pt; rótulos 8 a 8,5 pt; títulos 22/17/12 pt.
- Cores: tinta `1f2328`, cinza `5b6470`, borda `d0d7de`, fundo `f6f8fa`; disciplina em azul `1f4e79` (tinta `e8f0f8`) ou vinho `8b1e3f` (tinta `f8e9ee`); âmbar `9a6700` (tinta `fff4d6`) para "novo", "qualidade dos dados" e "o que mudou".
- Etiquetas de cobrança: lei `0b5cad`, súmula `b35900`, jurisprudência `6f42c1`, doutrina `1a7f37`, caso prático `57606a`.
- Questão = tabela de 2 colunas (cabeçalho colorido, faixa "tópico exato", enunciado e alternativas).
- **Regra do usuário (12/11/2026):** a resposta NUNCA aparece marcada no cartão. O gabarito vai no bloco "Respostas e comentários" no fim do capítulo, em letras pequenas e cinza claro, seguido dos comentários.

## Roteiro para uma nova disciplina (modelo A)
1. Banco atualizado: `03_criar_banco.py` → `07_aplicar_tec.py` (e `05_ajustes_gabarito.py` quando houver relatórios novos). Conferir gabarito (tipo do caderno = tipo do gabarito!), anuladas e texto das questões da disciplina.
2. Programa nos editais: `08_programa_dh.py` e `09_matriz_editais_dh.py` (copiar e trocar a disciplina e as palavras-chave).
3. Assuntos: definir 8 a 15 assuntos fixos (Guia 1, seção 2) e gravar em `assuntos` (ver `10_taxonomia_dh.py`).
4. Classificar as questões: `dados/classificacao_<disciplina>.csv` com `prova;numero;assunto;tipo;detalhe` (chave = prova + número; **não use IDs do banco**, eles mudam quando entra prova nova).
5. Comentar: `dados/comentarios_<disciplina>_<assunto>.json`, chave `"prova|número"`, campos `c` (o que foi cobrado), `p` (pegadinha), `d` (dispositivos `"Tratado|artigo"`). Só afirme o que puder; use "confirmar".
6. Analisar: `11_analise_dh.py` (copiar e trocar a disciplina): frequência com pesos e Wilson, grupos, teste retroativo, cobrança, concentração.
7. Gerar o Word: copiar `12_gerar_apostila_dh.py`, trocar as constantes e os textos específicos (capa, "Como ler"); rodar.
8. Planilhas: análise preditiva com fórmulas e lente 10 (`15_planilha_analise.py`, estrutura de `Analise-concurso - Penal e DH.xlsx`, preserva a coluna Resultado) e revisão (Guia 2, caps. 4 e 5: `13_planilha_revisao_dh.py`).
9. Conferir o resultado: converter para PDF (LibreOffice `soffice --headless --convert-to pdf`) e olhar os cartões, as tabelas e o fim de um capítulo.
10. Atualizar `00-PLANO-E-ROTEIRO.md` (seção de registro) e `01-PENDENCIAS.md`.

## Roteiro para estudo com edital (modelo B)
Os passos 1 a 9 acima valem, com estas diferenças: (a) o prefácio é o **edital verticalizado** do concurso-alvo (um subitem por linha, numeração do edital; marcar NOVO, exclusivo e detalhado demais comparando com o edital anterior e com editais de outros estados, Guia 2, cap. 2); (b) a tabela da lente 2 tem a coluna "Itens do edital"; (c) cada capítulo mostra os itens do edital que cobre; (d) o fim do título traz "Súmulas e artigos mais cobrados" e "Itens novos do edital". Para cargos com poucas provas próprias, misture provas parecidas da mesma banca (Guia 1, lente 3) e declare a amostra.

## Armadilhas já encontradas
- Gabarito de **outro tipo de caderno** (GO e RR 2021): sempre casar tipo do caderno com tipo do gabarito.
- Gabarito **preliminar**: procurar relatórios "Alteração de gabarito e Atribuição de questões" da FCC (atribuição = questão anulada).
- Texto de provas digitalizadas: OCR erra; corrigir à mão as questões da disciplina (`dados/correcoes_texto.json`).
- Pesos e teste retroativo: sempre declarar a amostra e comparar com o acaso; abaixo de 100 questões efetivas não ordene temas.
- Informação legal ou de jurisprudência sem fonte primária: marcar "confirmar".
