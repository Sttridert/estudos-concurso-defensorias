import re, json, sqlite3, pathlib, html as H
B=pathlib.Path(__file__).resolve().parent.parent / "banco"
MAP={"2021 - DPE-AM - Defensor Público":("dpeam121","A01"),"2021 - DPE-BA - Defensor Público":("dpeba120","A01"),"2021 - DPE-SC - Defensor Público":("dpesc121","A01"),
"2022 - DPE-AM - Analista Jurídico":("dpeam122","A"),"2022 - DPE-AP - Defensor Público":("dpeap122","A01"),"2022 - DPE-CE - Defensor Público":("dpece121","A01"),
"2022 - DPE-MT - Defensor Público":("dpemt221","A01"),"2022 - DPE-PB - Defensor Público":("dpepb121","A01"),"2023 - DPE-SP - Defensor Público":("dpesp222","A01")}
def tipos(corpo):
    t=re.sub(r"<[^>]*>"," ",corpo); t=H.unescape(t).replace("\xa0"," ")
    out={}
    for m in re.finditer(r"Tipo gabarito\s*(\d)(.*?)(?=Tipo gabarito|Seu navegador|$)",t,flags=re.S):
        out[int(m.group(1))]=dict((int(a),b) for a,b in re.findall(r"(\d{3})\s*-\s*(\S+)",m.group(2)))
    return out
con=sqlite3.connect(B/"questoes.db")
resumo=json.load(open(B/"gabaritos_fcc/resumo.json",encoding="utf-8"))
for nome,(cod,op) in MAP.items():
    r=[x for x in resumo[cod] if x["opcao"]==op and "aplic1" in x["tabela"]][0]
    corpo=(B/"gabaritos_fcc"/r["arquivo"]).read_text(encoding="latin-1")
    g=tipos(corpo)
    tc,=con.execute("select gabarito_tipo from provas where nome=?",(nome,)).fetchone()
    db=dict(con.execute("select q.numero,q.gabarito from questoes q join provas p on p.id=q.prova_id where p.nome=?",(nome,)).fetchall())
    site=g.get(tc,{})
    dif=[(n,db.get(n),site.get(n)) for n in sorted(set(db)|set(site)) if db.get(n)!=site.get(n)]
    nao_letra=[(n,l) for n,l in site.items() if l not in "ABCDE" or len(l)!=1]
    print(nome[:40].ljust(40),"tipo",tc,"site",len(site),"diferencas",len(dif),dif[:8],"nao-letra",nao_letra[:5])
