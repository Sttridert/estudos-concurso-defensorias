# legado/

Criado em 16/11/2026 (plano 06, auditoria da Etapa 1, cortes autorizados pelo usuario). Nada aqui e usado pelo motor nem pelo gerador. Nada foi apagado; para voltar, mover de volta.

- `scripts/`: 20 (criar banco; ja rodado), 25 (universos; ja rodado), 29 e 30 (correcoes pontuais ja aplicadas), cmp_gab, receptor_local. Os caminhos internos (`Path(__file__)`) apontam para `scripts/`; ao reutilizar, devolver o arquivo a `scripts/`.
- `produtos/apostilas/`: versoes antigas de Direito Penal e Direitos Humanos (sem sufixo e "[edital classificado]"; testes de 14/11/2026).
- `produtos/modelos/`: Modelo A e Modelo B (obsoletos desde 14/11/2026). `produtos/modelos/` mantem `base-estilos.docx`, que o gerador le, e o LEIA-ME.

Etapa 3 (16/11/2026): `scripts/28_importar_edital.py` e `scripts/42_teste_encaixe.py` tambem estao aqui; o ramo `--sem-artefato` do script 24 foi removido (o 24 recusa edital real sem artefato). Os editais 2 e 3 (DH e Penal do DPE-AM, importados pelo 28) continuam no banco, so como registro.
Documentos historicos: movidos em 16/11/2026 (Etapa 4) para `docs/arquivo/`, nao para esta pasta.

Etapa 2 (16/11/2026): scripts 21, 22, 31, 58, 59, 60, 61, 62 e 63 (catalogo e classificacao por disciplina) tambem estao em `scripts/` aqui. Seus dados foram exportados do banco para `dados/catalogo/` e `dados/classificacao/` e sao aplicados pelo `scripts/71_catalogo_e_classificacao.py`. NAO rodar os antigos: o 22 e o 31 desfariam reclassificacoes feitas depois deles.

Grupo A, etapa 2 (20/11/2026; decisão 49 do usuário): `scripts/01_extrair_texto.py`, `01b_reocr.py`, `01c_reocr_am23.py`, `01d_novas_provas.py` (extração de texto e OCR; o `26` e `scripts/lib_texto_prova.py` fazem o mesmo, e `refazer_ocr` guarda o texto embutido como `.embutido.txt`), `lib_gabarito.py` (nenhum script a importava) e `08_programa_dh.py` e `09_matriz_editais_dh.py` (só de Direitos Humanos, começo do projeto) estão aqui. As saídas antigas (`banco/texto-bruto/`, `banco/programas_dh/`, `banco/matriz_editais_dh.md`) continuam onde estavam.

Grupo A, etapa 3 (20/11/2026): `scripts/04_gabaritos_fcc.py`, `05_ajustes_gabarito.py`, `06_ler_tec.py` e `65_aplicar_gabaritos.py` foram reunidos em `scripts/coletar_gabaritos.py` (subcomandos `baixar-fcc`, `ajustes-fcc`, `ler-tec`, `aplicar`). Conferido: `ajustes-fcc` e `ler-tec` geram arquivos idênticos aos existentes; `aplicar --simular` e `baixar-fcc --so` rodam. Os originais ficam aqui só como histórico.

Grupo A, etapa 5 (20/11/2026): `scripts/50_programa_edital.py` e `56_acrescentar_bloco_ao_programa.py` foram reunidos em `scripts/coletar_programa_edital.py` (subcomandos `extrair`, `acrescentar-bloco` e o novo `disciplinas`). O núcleo de leitura de PDF que o `40` tinha (e o `50` importava por `importlib`) está agora em `scripts/lib_programa_edital.py`; o `40` ficou só com a rotina em lote. Conferido: as 8 disciplinas extraídas do edital 4 saem idênticas às do artefato existente; o bloco de Língua Portuguesa gerado pelo `acrescentar-bloco` é idêntico ao do artefato; o `40 DH --so` gera arquivo idêntico ao anterior.

Grupo A, etapa 7 (20/11/2026): `scripts/55_aplicar_correcoes_texto.py` e `66_confirmar_texto_questoes.py` foram reunidos em `scripts/coletar_conferir_texto.py` (subcomandos `corrigir` e `confirmar`; este agora tem `--simular`). Renomeados, sem mudar o código: `26_ingerir_prova.py` para `coletar_ingerir_prova.py`, `27_organizar_provas_novas.py` para `coletar_organizar_provas.py` e `57_gravar_textos_base.py` para `coletar_textos_base.py`.

Tabela antigo para novo (grupo A, 20/11/2026):
| Antigo | Novo |
|---|---|
| `01`, `01b`, `01c`, `01d` | `lib_texto_prova.py` (`extrair`, `refazer_ocr`) e `coletar_ingerir_prova.py` |
| `04`, `05`, `06`, `65` | `coletar_gabaritos.py` (`baixar-fcc`, `ajustes-fcc`, `ler-tec`, `aplicar`) |
| `26` | `coletar_ingerir_prova.py` |
| `27` | `coletar_organizar_provas.py` |
| `50`, `56` | `coletar_programa_edital.py` (`extrair`, `acrescentar-bloco`, `disciplinas`) e `lib_programa_edital.py` |
| `55`, `66` | `coletar_conferir_texto.py` (`corrigir`, `confirmar`) |
| `57` | `coletar_textos_base.py` |
| `lib_gabarito`, `08`, `09` | sem substituto (não eram usados) |
| (novo) | `coletar_conferir_prova.py` e `lib_conferencia.py` (relatório de integridade e vocabulário do gabarito) |
