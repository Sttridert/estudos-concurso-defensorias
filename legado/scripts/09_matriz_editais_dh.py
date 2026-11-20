"""Guia 2, cap. 2: matriz tema x edital para Direitos Humanos (marca onde cada tema aparece). Saida: banco/matriz_editais_dh.md"""
import re, pathlib
B = pathlib.Path(__file__).resolve().parent.parent / "banco"
TEMAS = [  # (codigo assunto, tema, regex)
 ("DH01","Fundamentos filosóficos e história dos DH", r"fundamentos filos|evolu[çc][ãa]o hist[óo]rica|origem, sentido"),
 ("DH01","Dignidade humana", r"dignidade humana|dignidade da pessoa"),
 ("DH01","Teoria crítica, decolonialidade, biopolítica", r"teoria cr[íi]tica|decolonial|biopol[íi]tica|necropol"),
 ("DH01","Gerações/dimensões e classificação", r"gera[çc][õo]es|dimens[õo]es"),
 ("DH02","Fontes e interpretação dos tratados de DH", r"interpreta[çc][ãa]o dos tratados|normas de interpreta"),
 ("DH02","Reservas e denúncias", r"reservas"),
 ("DH02","Soft law", r"soft law"),
 ("DH02","Responsabilidade internacional do Estado", r"responsabilidade internacional"),
 ("DH03","Sistema global ONU (órgãos, comitês, tratados)", r"Organiza[çc][ãa]o das Na[çc][õo]es Unidas|\(ONU\)"),
 ("DH03","Revisão Periódica Universal", r"revis[ãa]o peri[óo]dica"),
 ("DH03","Comentários gerais, relatórios, comitês temáticos", r"coment[áa]rios gerais|comit[êe]s? tem[áa]ticos|comit[êe]s"),
 ("DH04","Sistema interamericano (Comissão e Corte)", r"Corte Interamericana"),
 ("DH04","Convenção Americana e protocolos (San Salvador, pena de morte)", r"Convenção Americana|San Salvador"),
 ("DH04","Medidas cautelares e provisórias, petições", r"medidas cautelares|medidas provis[óo]rias"),
 ("DH04","Sistema africano e outros sistemas regionais", r"sistema africano|Carta Africana|sistema europeu"),
 ("DH05","Direito Internacional Humanitário", r"Internacional Humanit[áa]rio"),
 ("DH05","Tribunal Penal Internacional / Estatuto de Roma", r"Tribunal Penal Internacional|Estatuto de Roma"),
 ("DH05","Refugiados e migrantes", r"refugiad|migrantes|apatridia"),
 ("DH06","Incorporação e hierarquia dos tratados", r"hier[áa]rquica|incorpora[çc][ãa]o dos tratados|bloco de constitucionalidade"),
 ("DH06","Controle de convencionalidade", r"convencionalidade"),
 ("DH06","Federalização (IDC)", r"federaliza[çc][ãa]o|deslocamento de compet"),
 ("DH06","Execução de decisões internacionais no Brasil", r"execu[çc][ãa]o de decis[õo]es"),
 ("DH07","Políticas e programas nacionais (PNDH, planos)", r"PNDH|Programa Nacional de Direitos Humanos|Plano Nacional"),
 ("DH07","Comissão Nacional da Verdade / memória e justiça de transição", r"Comiss[ãa]o Nacional da Verdade|justi[çc]a de transi[çc][ãa]o|mem[óo]ria"),
 ("DH07","Acesso à justiça e 100 Regras de Brasília", r"100 Regras|Regras de Bras[íi]lia|acesso [àa] justi[çc]a"),
 ("DH07","Defensoria e sistema de proteção (amicus curiae, audiências públicas)", r"amicus curiae|audi[êe]ncias? p[úu]blicas"),
 ("DH07","Remédios constitucionais / mecanismos internos", r"habeas|mandado de|rem[ée]dios constitucionais|mecanismos de prote[çc][ãa]o"),
 ("DH08","Mulheres e violência de gênero (CEDAW, Belém do Pará)", r"discrimina[çc][ãa]o contra a mulher|Bel[ée]m do Par[áa]|igualdade de g[êe]nero|viol[êe]ncia contra a mulher"),
 ("DH08","Discriminação racial, povos indígenas, quilombolas", r"discrimina[çc][ãa]o racial|ind[íi]gena|quilombola|rela[çc][õo]es [ée]tnico"),
 ("DH08","Pessoas com deficiência", r"pessoas? com defici[êe]ncia"),
 ("DH08","LGBTQIA+ / diversidade", r"LGBT|orienta[çc][ãa]o sexual|identidade de g[êe]nero"),
 ("DH08","Pessoas idosas", r"pessoas? idosas?|idoso"),
 ("DH08","Crianças e adolescentes (Convenção)", r"direitos da crian[çc]a|Conven[çc][ãa]o sobre os direitos da crian"),
 ("DH08","Pessoas em situação de rua, moradia, despejos", r"situa[çc][ãa]o de rua|despejo|moradia"),
 ("DH09","Tortura e tratamentos cruéis (CAT, OPCAT)", r"tortura"),
 ("DH09","Privação de liberdade, Regras de Mandela/Bangkok", r"Mandela|Bangkok|privad[ao]s? de liberdade|sistema prisional|Tokyo|T[óo]quio"),
 ("DH10","Saúde, meio ambiente, clima, ODS/Agenda 2030", r"Agenda 2030|desenvolvimento sustent[áa]vel|direito [àa] sa[úu]de|mudan[çc]as clim[áa]ticas|meio ambiente"),
 ("DH10","Empresas e direitos humanos", r"empresas e direitos humanos|empresas transnacionais|Princ[íi]pios Orientadores"),
 ("DH10","Liberdade de expressão, mídia, tecnologias", r"liberdade de express[ãa]o|m[íi]dia|tecnologias|intelig[êe]ncia artificial"),
 ("DH10","Direito pandêmico / emergência", r"pand[êe]mic|emerg[êe]ncia"),
 ("DH11","Educação em direitos humanos", r"educa[çc][ãa]o em direitos humanos"),
]
progs = {}
for f in sorted((B / "programas_dh").glob("*.txt")):
    progs[f.stem] = re.sub(r"\s+", " ", f.read_text(encoding="utf-8"))
nomes = list(progs)
ab = [re.sub(r"^(\d{4}) - DPE-(\w+) - (\w+).*", r"\1 \2", n) + ("*" if "Analista" in n else "") for n in nomes]
out = ["# Matriz tema × edital: Direitos Humanos", "", "Gerada por `scripts/09_matriz_editais_dh.py`. ● = o tema aparece no programa de DH do edital (busca por palavras-chave no trecho extraído; confirmar quando a decisão depender de um item). \* = cargo de Analista. CE 2022: DH está dentro de Constitucional (item 5); AM 2022 e CE têm trecho curto.", "",
       "| Assunto | Tema | " + " | ".join(ab) + " | Nº de editais |", "|---|---|" + "---|" * (len(nomes) + 1)]
for cod, tema, rx in TEMAS:
    marcas = ["●" if re.search(rx, progs[n], re.I) else "" for n in nomes]
    out.append(f"| {cod} | {tema} | " + " | ".join(marcas) + f" | {sum(1 for m in marcas if m)} |")
(B / "matriz_editais_dh.md").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out[:4])); print(len(TEMAS), "temas;", len(nomes), "editais")
for cod, tema, rx in TEMAS:
    n = sum(1 for k in nomes if re.search(rx, progs[k], re.I)); print(f"{n:2d}/{len(nomes)}  {cod} {tema}")
