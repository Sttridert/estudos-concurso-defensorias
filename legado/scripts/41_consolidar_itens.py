#!/usr/bin/env python3
"""Etapa 4 do plano do edital fictício geral: junta as frases dos editais em itens do edital fictício.

Uso:  python -I scripts/41_consolidar_itens.py DH|PENAL|EXEC

Entrada: dados/programas_editais/<disciplina>/*.json (saída do script 40).
Saída:   dados/edital_ficticio_geral/<disciplina>_itens.json e um resumo no terminal.
Não altera o banco. Passos:
 1. junta frases iguais (sem acento, caixa e pontuação) e quase iguais (semelhança >= 0,93);
 2. marca a origem de cada item (FCC-Defensoria, DPU, outra banca) e em quantos editais aparece;
 3. conta quantos itens novos cada edital trouxe, na ordem FCC, DPU, outros (regra de parada por saturação);
 4. liga cada item aos tópicos que já existem no catálogo (por palavras-chave); o que não casa fica "sem tópico".
"""
import csv, difflib, json, re, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "dados" / "programas_editais"
SAIDA = RAIZ / "dados" / "edital_ficticio_geral"

PENAL_REGEX = {
    "PE01.01": r"conceito, fontes|fontes, objetivos|escolas penais|evolu[çc][ãa]o hist[óo]rica do direito penal|genealogia|hist[óo]ria do processo de criminaliza|direito penal: conceito",
    "PE01.02": r"princ[íi]pios penais|princ[íi]pios constitucionais|legalidade|lesividade|insignific|interven[çc][ãa]o m[íi]nima|fragmentari|proporcionalidade",
    "PE01.03": r"constitui[çc][ãa]o e direito penal|estado democr[áa]tico de direito|direito penal e direitos humanos|direitos humanos e processo de criminaliza|poder punitivo",
    "PE02.01": r"escolas criminol|tend[êe]ncias do pensamento criminol|criminologia cr[íi]tica|pensamento criminol",
    "PE02.02": r"sistema penal|controle social|processo de criminaliza|m[íi]dia e sistema penal|pol[íi]cia e sistema penal|criminaliza[çc][ãa]o",
    "PE02.03": r"vitimolog|vitimiza",
    "PE02.04": r"pol[íi]tica criminal|penitenci[áa]ri|encarceramento|prisoniza",
    "PE03.01": r"lei penal no tempo|retroatividade|abolitio|novatio|extra-?atividade|lei penal e sua aplica|aplica[çc][ãa]o da lei penal",
    "PE03.02": r"tempo e lugar do crime|territorialidade|extraterritorialidade|lei penal no espa[çc]o|lugar do crime",
    "PE03.03": r"interpreta[çc][ãa]o da lei penal|analogia|conflito aparente|interpreta[çc][ãa]o (e|da) ",
    "PE04.01": r"teoria do delito|elementos do crime|bem jur[íi]dico|conceito (anal[íi]tico )?de crime|tipicidade|tipo penal",
    "PE04.02": r"conduta|nexo (de )?causal|resultado|imputa[çc][ãa]o objetiva|omiss[ãa]o",
    "PE04.03": r"\bdolo\b|\bculpa\b|culposo|doloso",
    "PE04.04": r"iter criminis|tentativa|consuma[çc][ãa]o",
    "PE04.05": r"desist[êe]ncia|arrependimento eficaz",
    "PE05.01": r"ilicitude|injusto penal",
    "PE05.02": r"excludentes da ilicitude|leg[íi]tima defesa|estado de necessidade|estrito cumprimento|exerc[íi]cio regular",
    "PE06.01": r"culpabilidade",
    "PE06.02": r"imputabilidade|medida de seguran[çc]a|inimputab|periculosidade",
    "PE06.03": r"inexigibilidade|excludentes da culpabilidade|coa[çc][ãa]o moral|obedi[êe]ncia hier[áa]rquica",
    "PE06.04": r"\berro (de tipo|de proibi|no direito penal|sobre)|descriminantes putativas",
    "PE07.01": r"arrependimento posterior",
    "PE07.02": r"crime imposs[íi]vel",
    "PE07.03": r"concurso de (agentes|pessoas)|participa[çc][ãa]o|coautoria|autoria",
    "PE07.04": r"concurso de crimes|crime continuado|concurso material|concurso formal",
    "PE08.01": r"teorias? (da|das) pena|finalidades da pena|fun[çc][ãa]o da pena|teorias da pena",
    "PE08.02": r"esp[ée]cies de pena|regimes?|progress[ãa]o|privativas de liberdade|pena: evolu[çc][ãa]o",
    "PE08.03": r"dosimetria|c[áa]lculo da pena|circunst[âa]ncias judiciais|agravantes|atenuantes|causas de aumento|diminui[çc][ãa]o|trif[áa]sico|aplica[çc][ãa]o da pena",
    "PE08.04": r"reincid[êe]ncia|antecedentes",
    "PE08.05": r"restritivas de direitos|\bmulta\b|penas alternativas",
    "PE08.06": r"suspens[ãa]o condicional|sursis|livramento condicional|reabilita[çc][ãa]o",
    "PE09.01": r"extin[çc][ãa]o da punibilidade|punibilidade|perd[ãa]o|decad[êe]ncia|perempção|anistia|indulto",
    "PE09.02": r"prescri[çc][ãa]o",
    "PE10.01": r"homic[íi]dio|feminic[íi]dio|crimes contra a vida|infantic[íi]dio|aborto|suic[íi]dio",
    "PE10.02": r"les[ãa]o corporal|crimes contra a pessoa|rixa|periclita|constrangimento ilegal|amea[çc]a|sequestro|crimes contra a honra|liberdade individual",
    "PE11.01": r"\bfurto\b|\broubo\b",
    "PE11.02": r"extors[ãa]o|estelionato|recepta[çc][ãa]o|crimes contra o patrim[ôo]nio|apropria[çc][ãa]o ind[ée]bita|\bdano\b",
    "PE12.01": r"estupro",
    "PE12.02": r"dignidade sexual|importuna[çc][ãa]o|ass[ée]dio",
    "PE13.01": r"administra[çc][ãa]o p[úu]blica|peculato|corrup[çc][ãa]o|concuss[ãa]o|prevarica",
    "PE13.02": r"contra o estado democr[áa]tico de direito|crimes contra o estado",
    "PE13.03": r"f[ée] p[úu]blica|crimes em esp[ée]cie|outros crimes",
    "PE14.01": r"drogas|11\.343|15\.343",
    "PE14.02": r"viol[êe]ncia dom[ée]stica|maria da penha|11\.340",
    "PE14.03": r"hediondos|8\.072",
    "PE14.04": r"desarmamento|10\.826",
    "PE14.05": r"crime organizado|organiza[çc][ãa]o criminosa|12\.850",
    "PE14.06": r"tr[âa]nsito|9\.503",
    "PE14.07": r"\btortura\b|9\.455",
    "PE14.08": r"ambientais|9\.605",
    "PE14.09": r"preconceito|7\.716|ra[çc]a ou de cor",
    "PE14.10": r"abuso de autoridade|13\.869|16\.869",
    "PE14.11": r"contraven[çc][õo]es",
}


# Regras de ligação extras para DH (somam-se às palavras-chave do catálogo; servem só para sugerir o tópico)
DH_EXTRA = {
    "DH01.01": r"afirma[çc][ãa]o hist[óo]rica|origem e sentidos?|evolu[çc][ãa]o hist[óo]rica|hist[óo]ria dos direitos|documentos hist[óo]ricos|direitos humanos e contextos",
    "DH01.02": r"dignidade|fundamentos? filos[óo]ficos|teoria geral dos direitos humanos|conceito, terminologia|jusnaturalismo|juspositivismo|direitos naturais|sacralidade|humano e o inumano",
    "DH01.03": r"universalismo|relativismo|hermen[êe]utica diat[óo]pica|interculturalidade|direitos culturais",
    "DH01.04": r"zona de contato|globaliza[çc][õo]es rivais|descoloni|emancipa|domina[çc][ãa]o|contra-hegem|movimentos sociais|bandeiras de lutas|encantos e desencantos|encantat[óo]rio|usos pol[íi]ticos|imperialismo|branquitude|racismo estrutural|feminismo|teoria cr[íi]tica|ideologia|modernidade|capitalis|colonial|amefricanidade|di[áa]spora",
    "DH01.05": r"biopol[íi]tica|necropol|estado de exce[çc][ãa]o|guerra ao terror|fundamentalis|autorit|crises e rupturas|democracia",
    "DH02.01": r"fontes|classifica[çc][ãa]o|gera[çc][õo]es|soft law|n[úu]cleo de direito internacional dos direitos humanos|caracter[íi]sticas dos direitos humanos|direito internacional dos direitos humanos",
    "DH02.02": r"interpreta[çc][ãa]o|colis[ãa]o|conflitos entre direitos|pro homine",
    "DH02.03": r"suspens[ãa]o|restri[çc][õo]es|limites dos direitos humanos|limita[çc][õo]es|emerg[êe]ncia",
    "DH02.04": r"reservas|den[úu]ncias?|vig[êe]ncia|efic[áa]cia",
    "DH02.05": r"responsabilidade (internacional|do estado)|repara[çc][ãa]o|san[çc][õo]es|esgotamento dos recursos internos|obriga[çc][õo]es (assumidas|estatais)|subsidiariedade|justiciabilidade",
    "DH03.01": r"organiza[çc][ãa]o das na[çc][õo]es unidas|\bonu\b|carta das na[çc][õo]es unidas|assembleia geral|conselho de seguran[çc]a|conselho econ[ôo]mico|conselho de direitos humanos|\boit\b|organiza[çc][ãa]o internacional do trabalho|liga das na[çc][õo]es|sistema global|sistema internacional de prote[çc][ãa]o|ag[êe]ncias especializadas|unesco",
    "DH03.02": r"declara[çc][ãa]o universal|pacto internacional (dos|de|sobre)|pidcp|pidesc|direitos civis e pol[íi]ticos|direitos econ[ôo]micos, sociais",
    "DH03.03": r"comit[êe]s?|coment[áa]rios gerais|comunica[çc][õo]es individuais|protocolos? facultativos?|[óo]rg[ãa]os convencionais|extraconvencionais|mecanismos convencionais",
    "DH03.04": r"revis[ãa]o peri[óo]dica|exame peri[óo]dico|monitoramento|relat[óo]rios|procedimentos especiais|mecanismos de (prote[çc][ãa]o|apura[çc][ãa]o)|supervis[ãa]o|fiscaliza[çc][ãa]o",
    "DH04.01": r"sistema (regional )?interamericano|\boea\b|corte interamericana|comiss[ãa]o interamericana|organiza[çc][ãa]o dos estados americanos|jurisdi[çc][ãa]o contenciosa",
    "DH04.02": r"peti[çc][ãa]o|admissibilidade|procedimentos?|acesso|legitimidade",
    "DH04.03": r"medidas cautelares|medidas provis[óo]rias|medidas urgentes",
    "DH04.04": r"conven[çc][ãa]o americana|pacto de s[ãa]o jos[ée]|declara[çc][ãa]o americana",
    "DH04.05": r"san salvador|abo[lç][ií][çc][ãa]o da pena de morte|pena de morte",
    "DH04.06": r"casos? brasileiros|ximenes|gomes lund|brasil verde|garibaldi|vs\.? brasil|contra o brasil",
    "DH04.07": r"opini[õo]es consultivas|consultiva|casos contenciosos|jurisprud[êe]ncia",
    "DH04.08": r"desaparecimento for[çc]ado|conven[çc][ãa]o interamericana|resolu[çc][õo]es da oea",
    "DH04.09": r"africano|carta africana|europeu|regional",
    "DH05.01": r"humanit[áa]rio",
    "DH05.02": r"tribunal penal internacional|estatuto de roma|genoc[íi]dio|crimes internacionais",
    "DH05.03": r"refugiad|ap[áa]trid|asilo",
    "DH06.01": r"incorpora[çc][ãa]o|posi[çc][ãa]o hier[áa]rquica|hierarquia|status|reflexos do direito internacional|ordenamento jur[íi]dico brasileiro|interliga[çc][ãa]o entre o direito internacional e o direito interno|direito interno|direito brasileiro|implementa[çc][ãa]o dos direitos humanos no brasil",
    "DH06.02": r"convencionalidade|di[áa]logo (das|entre) cortes",
    "DH06.03": r"federaliza[çc][ãa]o|deslocamento de compet",
    "DH06.04": r"execu[çc][ãa]o de decis[õo]es|implementa[çc][ãa]o das decis[õo]es|cumprimento de decis[õo]es|decis[õo]es (oriundas|de) (tribunais|[óo]rg[ãa]os) internacionais",
    "DH07.01": r"programas?.{0,20}(nacionais?|estaduais?) de direitos humanos|pol[íi]ticas (nacionais|p[úu]blicas)|pndh|conselhos?|participa[çc][ãa]o social|programa estadual",
    "DH07.02": r"comiss[ãa]o (nacional|estadual) da verdade|justi[çc]a de transi[çc][ãa]o|mem[óo]ria|anistia",
    "DH07.03": r"acesso [àa] justi[çc]a|100 regras|regras de bras[íi]lia|defensoria",
    "DH07.04": r"rem[ée]dios constitucionais|habeas|mandado de|lit[íi]gio estrutural|amicus|audi[êe]ncias p[úu]blicas|mecanismos de prote[çc][ãa]o aos direitos humanos na constitui",
    "DH08.01": r"mulher|g[êe]nero|bel[ée]m do par[áa]|cedaw|viol[êe]ncia dom[ée]stica|maria da penha|obst[ée]trica",
    "DH08.02": r"racial|racism|[ée]tnico|a[çc][õo]es afirmativas|cotas|antirracis|negr[oa]s?",
    "DH08.03": r"ind[íi]gena|quilombola|povos e comunidades tradicionais|conven[çc][ãa]o 169|povos origin[áa]rios|territori",
    "DH08.04": r"defici[êe]ncia|cdpd|acessibilidade|capacitismo",
    "DH08.05": r"sa[úu]de mental|transtornos? mentais?|antimanicomial|psicossocia",
    "DH08.06": r"idoso|envelhecimento",
    "DH08.07": r"crian[çc]a|adolescente|infanto",
    "DH08.08": r"lgbt|orienta[çc][ãa]o sexual|identidade de g[êe]nero|yogyakarta|queer|travesti|transexual",
    "DH08.09": r"migrante|migra[çc][ãa]o|imigrante|trabalhadores migrantes",
    "DH08.10": r"situa[çc][ãa]o de rua|popula[çc][ãa]o de rua|sem-teto|sem-terra|favela|pobreza",
    "DH08.11": r"antidiscrimin|discrimina[çc][ãa]o|igualdade|interseccional|categorias suspeit|grupos vulner|vulnerabiliza|vulner[áa]veis",
    "DH09.01": r"tortura",
    "DH09.02": r"opcat|subcomit[êe] de preven|mecanismo nacional de preven",
    "DH09.03": r"mandela|bangkok|privad[ao]s? de liberdade|sistema prisional|regras m[íi]nimas|t[óo]quio|pris[ãa]o|encarceramento",
    "DH10.01": r"direito [àa] sa[úu]de|organiza[çc][ãa]o mundial da sa[úu]de|\boms\b|sa[úu]de",
    "DH10.02": r"moradia|despejos|conflitos fundi[áa]rios|direito [àa] cidade|terra",
    "DH10.03": r"alimenta[çc][ãa]o|padr[ãa]o de vida|trabalho|previd[êe]nci|seguridade",
    "DH10.04": r"educa[çc][ãa]o|retrocesso|progressividade|direitos econ[ôo]micos|judicializa[çc][ãa]o",
    "DH10.05": r"meio ambiente|ambiental|clima|agenda 2030|desenvolvimento sustent|diversidade biol[óo]gica|patrim[ôo]nio mundial|socioambiental|estocolmo",
    "DH10.06": r"empresas|investimentos internacionais|corporat|transnacionais",
    "DH10.07": r"liberdade de express|m[íi]dia|tecnologia|intelig[êe]ncia artificial|vigil[âa]ncia|internet|comunica[çc][ãa]o",
    "DH10.08": r"direito [àa] vida|for[çc]a letal|seguran[çc]a p[úu]blica|viol[êe]ncia (institucional|de estado)|policiamento",
    "DH10.09": r"bio[ée]tica|gen[ée]tic",
    "DH10.10": r"pand[êe]mi|covid",
    "DH11.01": r"educa[çc][ãa]o em direitos|educa[çc][ãa]o emancipat[óo]ria",
}


# Ampliações das regras acima (leis, decretos, casos e variações de redação encontrados nos editais)
DH_MAIS = {
    "DH01.02": r"conceito, fundamentos|origem, ess[êe]ncia|concep[çc][ãa]o e conceitos|defini[çc][ãa]o e conceito|fundamentos dos direitos humanos|liberdades p[úu]blicas|direitos individuais, pol[íi]ticos",
    "DH01.04": r"seletividade|paradigma|epistemic[íi]dio|sujeitos dos direitos|subalternidade|corporalidades|lugar de fala|representatividade|imagens de controle|constitucionalismo haitiano|carta mandinga|produtos culturais|fascismo|instituintes|pluralismo|interculturalidade|diferen[çc]as e similaridades|microagress",
    "DH02.01": r"referenciais normativos|padr[õo]es internacionais de prote",
    "DH03.01": r"sistema geral de prote|organismos de prote[çc][ãa]o|vertentes da prote|tr[êe]s vertentes|prote[çc][ãa]o internacional dos direitos humanos|prote[çc][ãa]o internacional da pessoa|natureza objetiva",
    "DH04.07": r"\bcaso\b.{1,60}\bvs?\.|\bvs?\.\s",
    "DH04.09": r"mercosul|carta democr[áa]tica|comiss[ãa]o africana|corte africana|sistemas regionais|revis[ãa]o pelos pares",
    "DH05.01": r"conven[çc][õo]es de genebra|conflito armado|conven[çc][ãa]o da haia|armas|minas antipessoal|terroris|tomada de ref|bombas",
    "DH06.01": r"constitucionaliza|internaliza|bloco de constitucionalidade|conflitos entre normas|direitos humanos na constitui|tratados internacionais de prote[çc][ãa]o dos direitos",
    "DH07.01": r"decreto n[º°o.]* ?7\.037|plano nacional|plano de a[çc][ãa]o|institui[çc][ãa]o nacional de direitos humanos|pol[íi]tica nacional de direitos humanos|mecanismos estaduais",
    "DH07.04": r"processos? estrutura|litigio estrutural|decis[õo]es estruturantes|estado de coisas|litig[âa]ncia|[ôo]nus da prova|prova estat|tutela coletiva|extrajudicial|a[çc][ãa]o civil p[úu]blica|lobby|controle social|accountability|resolu[çc][ãa]o dpge|decis[õo]es e senten[çc]as",
    "DH07.03": r"defensor(es)? p[úu]blicos? interamericano|defesa eficaz|atua[çc][ãa]o do defensor",
    "DH08.01": r"12\.845|viol[êe]ncia sexual|direitos reprodutivos|aborto",
    "DH08.02": r"7\.716|14\.532|12\.990|adpf 186|10\.932|ra[çc]a ou de cor|10\.639|11\.645|igualdade racial|resolu[çc][ãa]o.{0,20}cnj n[º°o.]* ?(425|123)",
    "DH08.03": r"6\.040|4\.887|6\.001|est?atuto do [íi]ndio|terreiro|matriz africana|protocolos comunit[áa]rios|consulta pr[ée]via|art\. 231",
    "DH08.04": r"13\.146|7\.853|12\.764|autis|deficiente|marraqueche|modelo m[ée]dico",
    "DH08.05": r"10\.216|resolu[çc][ãa]o.{0,20}(487|cnj n[º°o.]* ?487)|interna[çc][ãa]o (volunt|involunt|compuls)|487/2023|manic",
    "DH08.06": r"10\.741|pessoas? idosas?|intergeracional",
    "DH08.07": r"12\.594|sinase|tr[áa]fico de pessoas",
    "DH08.08": r"adi n[º°o.]* ?4\.?275|4275|provimento.{0,20}73|registro civil|sexo|atala|diversidade sexual",
    "DH08.09": r"13\.445|9\.474|migrar|refugi",
    "DH08.10": r"7\.053|catador|recicl|res[íi]duos|12305|popula[çc][ãa]o em situa|resolu[çc][ãa]o n[º°o.]* ?01/2014",
    "DH08.11": r"modalidades de controles|n[ãa]o submiss[ãa]o|crit[ée]rios de prote[çc][ãa]o especial|minorias",
    "DH09.01": r"9\.455|istambul|estambul|minnesota|execu[çc][õo]es sum[áa]rias|extrajudiciais",
    "DH09.02": r"12\.847|8\.154|mecanismo nacional",
    "DH09.03": r"cnpcp|resolu[çc][ãa]o.{0,20}348|recolhimento compuls[óo]rio|sistema prisional",
    "DH10.02": r"fundi[áa]ri|agr[áa]ri|posse|estatuto da cidade|10\.257|minha casa|11\.977|regulariza[çc][ãa]o|campo|reintegra[çc][ãa]o|despejo|solu[çc][õo]es fundi|cidade|baixada maranhense",
    "DH10.03": r"seguran[çc]a alimentar|susan|nutricional|8\.742|assist[êe]ncia social|loas|padr[ãa]o adequado|m[íi]nimo existencial",
    "DH10.05": r"metas d[oe]\w* mil[êe]nio|socioambient|ambientais|meio ambiente|campos alagados|montreal|camada de oz|sanit[áa]rio|saneamento",
    "DH10.07": r"privacidade|dados pessoais|informa[çc][ãa]o|imprensa|[óo]dio|esquecimento|opini[ãa]o|credo",
    "DH10.08": r"seguran[çc]a cidad|controle externo da atividade policial|uso progressivo|for[çc]a|viol[êe]ncia pol[íi]tica",
}

# Tópicos NOVOS aprovados em 14/11/2026 (código com * = tópico novo; sem * = fusão num tópico existente).
# Só recebem itens que não casaram com nenhum tópico existente.
DH_NOVOS = {
    "DH02.06*": ("Obrigações dos Estados e teorias de controle (margem de apreciação, quarta instância)",
                 r"obriga[çc][õo]es (de|dos estados|estatais)|margem de aprecia|quarta inst|respeito, prote[çc][ãa]o e realiza|proteger, respeitar|n[ãa]o submiss|controle externo|padr[õo]es internacionais"),
    "DH03.02": ("Outros tratados e convenções internacionais cobrados nos editais",
                 r"^conven[çc][ãa]o|^conv[êe]nio|^protocolo (de|sobre|facultativo)|^tratado|regulamento sanit|apartheid|escravatura|casamento|aliment|extradi|imunidades|rela[çc][õo]es (diplom|consulares|culturais)|direito dos tratados|propriedade intelectual|livre circula"),
    "DH07.05*": ("Participação política, manifestação, resistência e proteção de defensores de direitos humanos",
                 r"manifesta[çc][ãa]o|resist[êe]ncia|defensores de direitos humanos|participa[çc][ãa]o pol[íi]tica|democr[áa]tic|lobby|terrorismo|autodetermina|paz\b"),
    "DH08.12*": ("Direitos sexuais e reprodutivos, laicidade e liberdade religiosa",
                 r"reprodutiv|sexuais|laicidade|religi[ãa]o|religios|intoler[âa]ncia"),
    "DH09.04*": ("Garantias judiciais, direitos pré-processuais e proteção penal dos direitos humanos",
                 r"garantias judiciais|pr[ée]-?processuais|prote[çc][ãa]o penal|direito penal e processual penal|v[íi]timas|testemunhas|devido processo|processo internacional|graves viola[çc][õo]es|decis[õo]es e senten"),
    "DH10.11*": ("Direitos econômicos, sociais e culturais: reserva do possível, financiamento e judicialização",
                 r"reserva do poss[íi]vel|financiamento|or[çc]amento|separa[çc][ãa]o dos poderes|\bdescs?\b|direitos sociais|desenvolvimento|assimetrias|cultura:|desporto|sa[úu]de p[úu]blica|proporcionalidade"),
}


# Ampliações das regras de Penal (variações de redação dos editais)
PENAL_MAIS = {
    "PE01.01": r"pensamento penal|evolu[çc][ãa]o epistemol|dogm[áa]tica|fontes do direito penal|caracter[íi]sticas e fontes|ci[êe]ncia penal|hist[óo]ria do pensamento|finalidades do direito penal",
    "PE01.02": r"princ[íi]pios de direito penal|minimalismo|garantismo|princ[íi]pios aplic[áa]veis|princ[íi]pios do direito penal",
    "PE01.03": r"disposi[çc][õo]es constitucionais|tratados internacionais de direitos humanos e direito penal|pena e constitui[çc][ãa]o|pena e direitos humanos|constitucionaliza|direitos humanos",
    "PE02.01": r"associa[çc][ãa]o diferencial|anomia|subcultura|rea[çc][ãa]o social|funcionalismo|marxismo|escola de chicago|realismo criminol|abolicionis|positivismo criminol|esquerda punitiva|lei e ordem|labeling|etiquetamento|criminologia|an[áa]lises criminol",
    "PE02.02": r"policiza[çc][ãa]o|militariza[çc][ãa]o|simb[óo]lico|privatiza[çc][ãa]o|expans[ãa]o do direito penal|direito penal m[íi]nimo|sociedade de risco|inimigo",
    "PE02.04": r"pris[ãa]o|pris[õo]es|capitalismo|economia pol[íi]tica da pena|foucault|hist[óo]ria das pris|encarcer",
    "PE03.03": r"classifica[çc][ãa]o das normas|norma penal em branco|conflito de normas",
    "PE04.01": r"classifica[çc][ãa]o dos crimes|estrutura do tipo|conceitos? de crime|processo de imputa[çc][ãa]o|sujeitos|elementos do tipo|modernas tend[êe]ncias da teoria do delito|fato t[íi]pico",
    "PE04.02": r"rela[çc][ãa]o de causalidade|aus[êe]ncia de a[çc][ãa]o|a[çc][ãa]o e omiss[ãa]o|processo de imputa",
    "PE04.03": r"elementos subjetivos|imputa[çc][ãa]o subjetiva|erro de tipo.{0,5}dolo|preterdolo",
    "PE05.01": r"direito penal e moral|causas legais e supralegais|antijuridicidade",
    "PE05.02": r"justifica[çc][ãa]o|consentimento do ofendido",
    "PE06.01": r"direito penal do fato|do autor|culpabilidade e liberdade|vulnerabilidade|exculpa[çc][ãa]o",
    "PE06.02": r"medidas? de seguran[çc]a|sa[úu]de mental|10\.216|13\.146|semi-?imput|paciente judici[áa]rio",
    "PE06.03": r"causas de exculpa[çc][ãa]o",
    "PE08.01": r"economia pol[íi]tica da pena|fun[çc][ãa]o da pena|finalidades",
    "PE08.02": r"cumprimento|regime",
    "PE13.03": r"crimes contra (a fam[íi]lia|a incolumidade|a paz p[úu]blica|a propriedade imaterial|o sentimento religioso|o respeito aos mortos|a organiza[çc][ãa]o do trabalho|a economia|o meio ambiente|a f[ée])",
}
PENAL_MAIS.update({
    # o edital cita o grupo de crimes de forma genérica: vale para todos os tópicos do tema
    "PE10.01": r"crimes contra a pessoa|crimes em esp[ée]cie",
    "PE11.01": r"crimes contra o patrim[ôo]nio|crimes em esp[ée]cie",
    "PE12.01": r"dignidade sexual|crimes em esp[ée]cie",
    "PE08.04": r"agravantes|atenuantes",
    "PE01.01": PENAL_MAIS["PE01.01"] + r"|escravid|ditadura|colonialismo|estado de exce[çc][ãa]o|poder de punir|pena em perspectiva|direito penal moderno|genealogia",
    "PE01.03": PENAL_MAIS["PE01.03"] + r"|direitos e garantias aplic[áa]veis",
    "PE03.01": r"concurso de normas|revoga[çc][ãa]o da lei|contagem de prazo|prerrogativas funcionais|lei penal e",
    "PE04.01": PENAL_MAIS["PE04.01"] + r"|pessoas jur[íi]dicas|responsabiliza[çc][ãa]o penal",
    "PE06.03": PENAL_MAIS["PE06.03"] + r"|isen[çc][ãa]o de pena",
    "PE06.04": r"estrutura jur[íi]dica do erro|erro",
    "PE08.02": PENAL_MAIS["PE08.02"] + r"|limite das penas|comina[çc][ãa]o|rep[ae]ra[çc][ãa]o dos danos|valor m[íi]nimo",
})
# Itens que pertencem a outra disciplina do plano (ficam marcados para quando chegarmos nela)
OUTRA_DISC_PENAL = {
    "Execução Penal": r"7\.210|execu[çc][ãa]o penal|estabelecimentos? penais|albergado|col[ôo]nia agr[ií]cola|remi[çc][ãa]o|detra[çc][ãa]o|monitora[çc][ãa]o eletr|direito de visita|revista [íi]ntima|revista vexat|faltas disciplinares|san[çc][õo]es e das recompensas|condenado e do internado|autoriza[çc][õo]es de sa[íi]da|transfer[êe]ncia de presos|regras de mandela|cadeia p[úu]blica|hospital de cust[óo]dia|centro de observa[çc][ãa]o|[óo]rg[ãa]os da execu[çc][ãa]o|soma e da unifica|execu[çc][ãa]o das penas em esp|falta de vaga|\bcnj\b|extin[çc][ãa]o de pena",
    "Direito Militar": r"penal militar|c[óo]digo penal militar",
    "Processo Penal": r"negocial|n[ãa]o persecu[çc][ãa]o|transa[çc][ãa]o penal",
}
PENAL_NOVOS = {
    "PE14.12*": ("Outras leis penais especiais (antiterrorismo, lavagem de dinheiro, ECA, Estatuto do Idoso, Torcedor)",
                 r"13\.260|antiterror|9\.613|lavagem|8\.069|estatuto da crian|10\.741|estatuto do idoso|10\.671|torcedor|legisla[çc][ãa]o penal (extravagante|especial)|leis? penais? (extravagante|especial)|13\.964|pacote anticrime|istambul|12\.847"),
    "PE03.02": ("Lei penal quanto às pessoas, imunidades, extradição e eficácia de sentença estrangeira",
                 r"em rela[çc][ãa]o [àa]s pessoas|imunidades|extradi[çc][ãa]o|senten[çc]a estrangeira|lei penal quanto"),
    "PE08.07*": ("Efeitos da condenação",
                 r"efeitos da condena[çc][ãa]o|efeitos (penais|extrapenais)|reincid[êe]ncia|confisco|perda de bens"),
}


PROC_PENAL = re.compile(r"processual penal|processo penal|inqu[ée]rito policial|busca e apreens|a[çc][ãa]o penal|queixa-crime|liberdade provis|pris[ãa]o preventiva|nulidades|tribunal do j[úu]ri|meios de (prova|obten)|sistemas de investiga|investiga[çc][ãa]o preliminar|jurisdi[çc][ãa]o e compet|condi[çc][õo]es da a[çc][ãa]o|quebra de sigilo|autodefesa|defesa t[ée]cnica|[ôo]nus da prova|ind[íi]cios no processo", re.I)


def sem_acento(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn").lower()


# Editais que não valem para a disciplina (o texto extraído mistura programas de outros cargos)
EXCLUIR = {("2026 - DPE-BA - Analista Técnico Direito (edital, sem prova)", "ADM"),
           ("2025 - DPE-RO - Analista Jurídico (edital, sem prova)", "CIV"),     # seção de "Civil" traz programa de outros cargos (TI, engenharia, contabilidade)
           ("2021 - DPE-SE - Defensor Público (edital, sem prova)", "CIV"),       # duas colunas: leitura embaralha as colunas
           ("2021 - DPE-SE - Defensor Público (edital, sem prova)", "CONST"),
           ("2021 - DPE-SE - Defensor Público (edital, sem prova)", "ADM"),
           ("2021 - DPE-SE - Defensor Público (edital, sem prova)", "PCIV"),
           ("2021 - DPE-SE - Defensor Público (edital, sem prova)", "PPEN"),
           ("2021 - DPE-SE - Defensor Público (edital, sem prova)", "EXEC"),     # duas colunas: leitura embaralha com regras do concurso
           ("2023 - DPE-PR - Analista Direito (edital, sem prova)", "ADM")}      # seção de Administrativo avança por outras disciplinas (processo penal etc.)


def norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def origem(pasta: str, banca: str) -> str:
    if "DPU" in pasta:
        return "DPU"
    return "FCC" if banca.upper().startswith("FCC") else "Outra banca"


def ano_de(pasta: str) -> int:
    return int(pasta[:4])


def taxonomia(alvo: str):
    """Taxonomia (temas, tópicos e palavras-chave) de uma disciplina nova: dados/edital_ficticio_geral/taxonomia_<alvo>.json."""
    f = SAIDA / f"taxonomia_{alvo}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def regex_catalogo(alvo: str) -> dict:
    if alvo not in ("DH", "PENAL"):
        tx = taxonomia(alvo)
        return {tp["codigo"]: re.compile(tp["regex"], re.I) for tp in (tx or {}).get("topicos", []) if tp.get("regex")}
    if alvo == "PENAL":
        return {k: re.compile(v + ("|" + PENAL_MAIS[k] if k in PENAL_MAIS else ""), re.I) for k, v in PENAL_REGEX.items()}
    out = {}
    with open(RAIZ / "dados" / "catalogo_pontos_direitos_humanos.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            partes = [DH_EXTRA.get(r["codigo"], ""), DH_MAIS.get(r["codigo"], "")]
            if r.get("regex_presenca") and r["codigo"] not in ("DH01.03", "DH04.05", "DH06.01", "DH06.04"):
                partes.append(r["regex_presenca"])
            rx = "|".join(x for x in partes if x)
            if rx:
                out[r["codigo"]] = re.compile(rx, re.I)
    return out


def main():
    alvo = sys.argv[1].upper()
    arquivos = sorted((ENTRADA / alvo).glob("*.json"))
    eds = []
    por_pasta = {}
    for a in arquivos:
        d = json.loads(a.read_text(encoding="utf-8"))
        frases = [(i["item"], f) for s in d["secoes"] for i in s["itens"] for f in i["frases"]]
        if not frases or (d["pasta"], alvo) in EXCLUIR:
            continue
        por_pasta[d["pasta"]] = {"pasta": d["pasta"], "banca": d["banca"], "origem": origem(d["pasta"], d["banca"]), "ano": ano_de(d["pasta"]), "frases": frases}
    if alvo == "EXEC":
        # Execução Penal também aparece como parte de Penal e de Processual Penal; esses itens foram guardados
        # (disciplina_provavel) quando aquelas disciplinas foram consolidadas, e entram aqui com a origem de cada edital.
        for outra in ("PENAL", "PPEN"):
            f_out = SAIDA / f"{outra}_itens.json"
            if not f_out.exists():
                continue
            bancas = {}
            for g in (ENTRADA / outra).glob("*.json"):
                dj = json.loads(g.read_text(encoding="utf-8")); bancas[dj["pasta"]] = dj["banca"]
            for it in json.loads(f_out.read_text(encoding="utf-8"))["itens"]:
                if not (it.get("disciplina_provavel") or "").startswith("Execu"):
                    continue
                for oc in it["ocorrencias"]:
                    pasta = oc["edital"]
                    if (pasta, alvo) in EXCLUIR or pasta not in bancas:
                        continue
                    e = por_pasta.setdefault(pasta, {"pasta": pasta, "banca": bancas[pasta], "origem": origem(pasta, bancas[pasta]), "ano": ano_de(pasta), "frases": []})
                    if (oc["item"], oc["texto"]) not in e["frases"]:
                        e["frases"].append((oc["item"], oc["texto"]))
    eds = list(por_pasta.values())
    # ordem de processamento: FCC (mais recente primeiro), DPU, outras bancas (mais recente primeiro)
    rank = {"FCC": 0, "DPU": 1, "Outra banca": 2}
    eds.sort(key=lambda e: (rank[e["origem"]], -e["ano"], e["pasta"]))

    cl = []          # clusters
    por_chave = {}   # chave normalizada -> índice do cluster
    serie = []
    for e in eds:
        novos = 0
        primeira = {}          # rótulo do item -> primeira frase (o "cabeçalho" do item)
        for item, texto in e["frases"]:
            k = norm(texto)
            if len(k) < 4:
                continue
            idx = por_chave.get(k)
            if idx is None and len(k) >= 30:
                melhor, mr = None, 0.0
                for k2, i2 in por_chave.items():
                    if abs(len(k2) - len(k)) > 0.15 * max(len(k), len(k2)) or len(k2) < 30:
                        continue
                    sm = difflib.SequenceMatcher(None, k, k2)
                    if sm.real_quick_ratio() < 0.93 or sm.quick_ratio() < 0.93:
                        continue
                    r = sm.ratio()
                    if r > mr:
                        melhor, mr = i2, r
                if mr >= 0.93:
                    idx = melhor
                    por_chave[k] = idx
            if idx is None:
                idx = len(cl)
                cl.append({"texto": texto, "variantes": {}, "editais": {}})
                por_chave[k] = idx
                novos += 1
            c = cl[idx]
            if item not in primeira:
                primeira[item] = texto
                pai = None
            else:
                pai = primeira[item]
            if pai is None and "." in item:
                pai = primeira.get(item.split(".")[0])
            if pai and pai != texto:
                c.setdefault("pais", set()).add(pai)
            c["variantes"][texto] = c["variantes"].get(texto, 0) + 1
            c["editais"].setdefault(e["pasta"], {"origem": e["origem"], "ano": e["ano"], "item": item, "texto": texto})
        serie.append((e["pasta"], e["origem"], len(e["frases"]), novos))

    reg = regex_catalogo(alvo)
    fa = SAIDA / f"ajustes_{alvo}.json"
    AJUSTES = {sem_acento(k).strip(): v for k, v in json.loads(fa.read_text(encoding="utf-8")).items()} if fa.exists() else {}
    itens = []
    for n, c in enumerate(cl, 1):
        eds_c = c["editais"]
        n_fcc = sum(1 for v in eds_c.values() if v["origem"] == "FCC")
        n_dpu = sum(1 for v in eds_c.values() if v["origem"] == "DPU")
        n_out = len(eds_c) - n_fcc - n_dpu
        texto_busca = sem_acento(re.sub(r"^\d+(\.\d+)*\s+", "", c["texto"])) if alvo not in ("DH", "PENAL") else c["texto"]
        pontos = [cod for cod, rx in reg.items() if rx.search(texto_busca)]
        herdado = False
        if not pontos and alvo not in ("DH", "PENAL") and (taxonomia(alvo) or {}).get("herdar_do_pai"):
            e_de_outra = any(re.search(rx, texto_busca, re.I) for rx in ((taxonomia(alvo) or {}).get("outra_disciplina", {})).values())
            sem_rotulo = re.sub(r"^\d+(\.\d+)*\s+", "", c["texto"])
            amplo = (taxonomia(alvo) or {}).get("herdar_do_pai") == "amplo"   # "amplo" = regra original do Administrativo (sem limite de tamanho)
            fragmento = amplo or (len(sem_rotulo.split()) <= 4 and not re.search(r"\d", sem_rotulo))   # só fragmentos genéricos ("Conceito.", "Fases.") herdam
            if not e_de_outra and fragmento:       # item que é de outra disciplina não herda tópico do item-pai
                contagem, n_pais = {}, 0
                for pai in sorted(c.get("pais", ())):
                    if len(pai) > 70 and not amplo:       # cabeçalho longo (lista de assuntos) é ambíguo: não herda
                        continue
                    tb = sem_acento(pai)
                    hits_pai = [cod for cod, rx in reg.items() if rx.search(tb)]
                    if 0 < len(hits_pai) <= 2:     # pai ambíguo (muitos tópicos) não é herdado
                        n_pais += 1
                        for cod in hits_pai:
                            contagem[cod] = contagem.get(cod, 0) + 1
                for cod, qtd in contagem.items():    # só o tópico que a maioria dos pais indica
                    if 2 * qtd >= n_pais:
                        pontos.append(cod)
            herdado = bool(pontos)
        if not pontos and alvo == "DH":
            pontos = [cod for cod, (_, rx) in DH_NOVOS.items() if re.search(rx, c["texto"], re.I)][:1]
        if not pontos and alvo == "PENAL":
            pontos = [cod for cod, (_, rx) in PENAL_NOVOS.items() if re.search(rx, c["texto"], re.I)][:1]
        disc_prov = None
        if alvo == "PENAL" and PROC_PENAL.search(c["texto"]):
            pontos = []
            disc_prov = "Processo Penal"            # o programa de Penal de alguns editais vai até o Processo Penal
        if alvo == "PENAL" and pontos and all(p.startswith("PE02") for p in pontos):
            disc_prov = "Criminologia (PE02)"      # decisão de 14/11/2026: PE02 vai para a disciplina Criminologia
        if alvo not in ("DH", "PENAL") and not pontos:
            for dname, rx in ((taxonomia(alvo) or {}).get("outra_disciplina", {})).items():
                if re.search(rx, texto_busca, re.I):
                    disc_prov = dname
                    break
        if alvo == "PENAL" and not pontos:
            for dname, rx in OUTRA_DISC_PENAL.items():
                if re.search(rx, c["texto"], re.I):
                    disc_prov = dname
                    break
        flags = []
        ajuste = AJUSTES.get(sem_acento(c["texto"]).strip())
        if ajuste is not None:                       # classificação feita à mão (arquivo de ajustes da disciplina)
            pontos = list(ajuste.get("pontos", []))
            disc_prov = ajuste.get("disciplina") or None
            flags.append("classificado à mão")
            if alvo == "PENAL" and pontos and all(p.startswith("PE02") for p in pontos) and not disc_prov:
                disc_prov = "Criminologia (PE02)"      # PE02 vai para a disciplina Criminologia (decisão de 14/11/2026)
            if ajuste.get("generico"):
                flags.append("fragmento genérico (sem tópico próprio)")
        generico = False
        if alvo not in ("DH", "PENAL") and not pontos and not disc_prov and ajuste is None:
            gx = (taxonomia(alvo) or {}).get("fragmentos_genericos")
            if gx and re.search(gx, sem_acento(re.sub(r"^\d+(\.\d+)*\s+", "", c["texto"])).strip(), re.I):
                generico = True
                flags.append("fragmento genérico (sem tópico próprio)")
        if herdado:
            flags.append("tópico herdado do item pai")
        if re.search(r"\b(lei|decreto|resolu[çc][ãa]o|provimento|adpf|adi|recomenda[çc][ãa]o)\b.{0,25}\d|\bcaso\b.{1,60}\bvs?\.|\d{3,}/\d{2,4}", c["texto"], re.I):
            flags.append("detalhado (cita lei, decreto ou caso)")
        if min(v["ano"] for v in eds_c.values()) >= 2025:
            flags.append("novo (so de 2025 em diante)")
        if len(eds_c) == 1:
            flags.append("exclusivo (1 edital)")
        if n_fcc == 0:
            flags.append("sem FCC")
        if n_dpu and not n_fcc and not n_out:
            flags.append("so DPU")
        itens.append({"id": f"{alvo}-{n:04d}", "texto": c["texto"], "n_editais": len(eds_c), "n_fcc": n_fcc, "n_dpu": n_dpu, "n_outras": n_out,
                      "anos": sorted({v["ano"] for v in eds_c.values()}), "pontos": pontos, "disciplina_provavel": disc_prov, "flags": flags,
                      "variantes": list(c["variantes"].keys()) if len(c["variantes"]) > 1 else [],
                      "ocorrencias": [{"edital": k, "item": v["item"], "texto": v["texto"]} for k, v in sorted(eds_c.items())],
                      "editais": sorted(eds_c.keys())})
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / f"{alvo}_itens.json").write_text(json.dumps({"alvo": alvo, "ordem_de_processamento": serie, "itens": itens}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{alvo}: {len(eds)} editais com programa, {sum(len(e['frases']) for e in eds)} frases, {len(itens)} itens distintos")
    print("\nSaturação (ordem: FCC, DPU, outras bancas):  edital | origem | frases | itens novos | % novos")
    for p, o, nf, nn in serie:
        print(f"  {p[:58]:58} {o[:6]:6} {nf:4d} {nn:4d} {100*nn/max(nf,1):5.1f}%")
    outra = [i for i in itens if not i["pontos"] and i["disciplina_provavel"]]
    sem = [i for i in itens if not i["pontos"] and not i["disciplina_provavel"] and not any(f.startswith("fragmento genérico") for f in i["flags"])]
    n_gen = sum(1 for i in itens if any(f.startswith("fragmento genérico") for f in i["flags"]))
    novos = [i for i in itens if any(p.endswith("*") for p in i["pontos"])]
    print(f"\nItens ligados a algum tópico: {len(itens)-len(sem)-len(outra)} de {len(itens)} (dos quais {len(novos)} em tópico novo proposto)")
    print(f"Itens de outra disciplina (marcados para depois): {len(outra)}; fragmentos genéricos: {n_gen}; sem tópico: {len(sem)}")


if __name__ == "__main__":
    main()
