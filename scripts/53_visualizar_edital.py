#!/usr/bin/env python3
"""Gera uma página HTML local para LER e CONFERIR o artefato do edital (frase literal -> tópicos).

Uso:  python -I scripts/53_visualizar_edital.py <slug>
Lê dados/editais_reais/<slug>/edital_classificado.json (+ nomes dos tópicos no banco, só leitura) e grava
dados/editais_reais/<slug>/rascunho.html (arquivo único, sem internet). Filtros por disciplina, busca, e botão
"revisar" por frase (fica salvo no navegador; "copiar marcadas" gera a lista para colar no chat).
"""
import json, sqlite3, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
slug = sys.argv[1]
pasta = RAIZ / "dados" / "editais_reais" / slug
art = json.loads((pasta / "edital_classificado.json").read_text(encoding="utf-8"))
con = sqlite3.connect(f"file:{RAIZ / 'banco' / 'estudos.db'}?mode=ro", uri=True)
cat = {c: {"nome": t, "disc": d, "tema": a} for c, t, d, a in con.execute(
    "select p.codigo,p.texto,d.nome,a.nome from pontos p join disciplinas d on d.id=p.disciplina_id join assuntos a on a.id=p.assunto_id")}
for p in art["topicos_propostos"]:
    cat[p["id"]] = {"nome": p["nome"], "disc": p["disciplina"] + " (proposta)", "tema": p["tema"]}
dados = {"titulo": f"{art['edital']['pasta']}", "estado": art["estado"], "disciplinas": art["disciplinas"], "cat": cat,
         "propostas": art["topicos_propostos"]}

HTML = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rascunho do edital classificado</title><style>
:root{--bg:#fafaf7;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--bd:#e2e0d8;--pri:#1f5f8b;--prib:#e3eff7;--sec:#6b6b66;--secb:#f1f0eb;--out:#a24a00;--outb:#fbeadb;--prop:#7a2e8f;--propb:#f3e6f7;--mark:#fff1a8;--flag:#c0392b}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17181a;--fg:#ececea;--mut:#a0a09a;--card:#1f2124;--bd:#33363a;--pri:#8ec1e8;--prib:#1f3445;--sec:#a0a09a;--secb:#2a2c2f;--out:#f0b27a;--outb:#46301c;--prop:#d9a6ec;--propb:#3a2644;--mark:#5c4f10;--flag:#ff7b6b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,Segoe UI,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--bd);padding:10px 16px}
h1{font-size:17px;margin:0 0 2px}.sub{color:var(--mut);font-size:13px;margin-bottom:8px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.tabs{display:flex;flex-wrap:wrap;gap:6px}button,input[type=search]{font:inherit;font-size:14px}
.tab{border:1px solid var(--bd);background:var(--card);color:var(--fg);border-radius:999px;padding:3px 11px;cursor:pointer}
.tab[aria-pressed=true]{background:var(--pri);color:#fff;border-color:var(--pri)}
input[type=search]{border:1px solid var(--bd);background:var(--card);color:var(--fg);border-radius:8px;padding:5px 10px;min-width:200px;flex:1}
label.f{font-size:13px;color:var(--mut);display:flex;gap:4px;align-items:center;cursor:pointer}
main{max-width:1000px;margin:0 auto;padding:12px 16px 80px}
.item{margin:18px 0 6px;font-weight:600;color:var(--mut);font-size:13px;text-transform:uppercase;letter-spacing:.04em}
.fr{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:9px 12px;margin:6px 0;display:grid;grid-template-columns:1fr auto;gap:6px 10px}
.fr.rev{border-color:var(--flag);box-shadow:inset 3px 0 0 var(--flag)}
.txt{font-size:15.5px}.id{font-size:11px;color:var(--mut);font-variant-numeric:tabular-nums}
mark{background:var(--mark);color:inherit;border-radius:3px;padding:0 1px}
.dest{grid-column:1/-1;display:flex;flex-direction:column;gap:4px}
.grp{display:flex;flex-wrap:wrap;gap:5px;align-items:baseline}.tr{font-size:12.5px;color:var(--mut);font-style:italic;flex-basis:100%}
.chip{font-size:13px;border-radius:6px;padding:2px 8px;border:1px solid transparent}
.chip b{font-weight:700}.p{background:var(--prib);color:var(--pri)}.s{background:var(--secb);color:var(--sec)}
.o{background:var(--outb);color:var(--out)}.n{background:var(--propb);color:var(--prop)}.sp{font-size:11px;opacity:.8}
.flag{border:1px solid var(--bd);background:transparent;color:var(--mut);border-radius:6px;cursor:pointer;padding:0 8px;height:26px}
.rev .flag{color:var(--flag);border-color:var(--flag)}
.note{width:100%;grid-column:1/-1;display:none;font:inherit;font-size:14px;border:1px solid var(--bd);border-radius:6px;padding:5px 8px;background:var(--bg);color:var(--fg)}
.rev .note{display:block}
.box{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:10px 14px;margin:10px 0;font-size:14px}
#cnt{font-size:13px;color:var(--mut)}@media(max-width:560px){.fr{grid-template-columns:1fr}}
</style></head><body>
<header><h1>Rascunho do edital classificado</h1><div class="sub" id="sub"></div>
<div class="bar"><div class="tabs" id="tabs"></div><input type="search" id="q" placeholder="Buscar frase, código ou tópico…">
<label class="f"><input type="checkbox" id="fOut">só tópico em outra disciplina</label>
<label class="f"><input type="checkbox" id="fMulti">só frases com trechos ou secundários</label>
<label class="f"><input type="checkbox" id="fRev">só marcadas</label>
<button class="tab" id="copiar">Copiar marcadas</button><span id="cnt"></span></div></header>
<main id="m"></main>
<script>
const D=__DADOS__;const KEY="rascunho-"+D.titulo;let rev={};try{rev=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(rev))}catch(e){}};
let disc="TODAS";const $=s=>document.getElementById(s);
const esc=s=>s.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
$("sub").textContent=D.titulo+" · "+D.estado;
const tabs=[["TODAS","Todas"]].concat(D.disciplinas.map(d=>[d.codigo,d.disciplina_banco.replace("Direito ","").replace("da Criança e do Adolescente","Criança/Adolesc.")]));
$("tabs").innerHTML=tabs.map(t=>`<button class="tab" data-d="${t[0]}" aria-pressed="${t[0]===disc}">${esc(t[1])}</button>`).join("");
$("tabs").onclick=e=>{const b=e.target.closest("[data-d]");if(!b)return;disc=b.dataset.d;[...$("tabs").children].forEach(x=>x.setAttribute("aria-pressed",x.dataset.d===disc));draw()};
["q","fOut","fMulti","fRev"].forEach(i=>$(i).oninput=draw);
function chip(x,bloco){const c=D.cat[x.p]||{nome:"?",disc:"?",tema:""};const nova=x.p.startsWith("NP-");
 const out=!nova&&c.disc!==bloco;const cls=nova?"n":out?"o":(x.papel==="principal"?"p":"s");
 return `<span class="chip ${cls}" title="${esc(c.tema)} — ${esc(c.disc)}">${x.papel==="principal"?"":"+ "}<b>${x.p}</b> ${esc(c.nome)}${out?` <span class="sp">· ${esc(c.disc)}</span>`:""}${nova?` <span class="sp">· proposta</span>`:""}</span>`}
function hl(t,trs){let h=esc(t);trs.forEach(s=>{const e=esc(s);h=h.replace(e,"<mark>"+e+"</mark>")});return h}
function draw(){const q=$("q").value.trim().toLowerCase(),fo=$("fOut").checked,fm=$("fMulti").checked,fr=$("fRev").checked;let n=0,h="";
 D.disciplinas.forEach(d=>{if(disc!=="TODAS"&&d.codigo!==disc)return;let hd="";
  d.itens.forEach(it=>{let hi="";it.frases.forEach(f=>{
   const grp=[];f.destinos.forEach(x=>{const k=x.trecho||"";let g=grp.find(g=>g.k===k);if(!g){g={k,l:[]};grp.push(g)}g.l.push(x)});
   const out=f.destinos.some(x=>!x.p.startsWith("NP-")&&(D.cat[x.p]||{}).disc!==d.disciplina_banco);
   const multi=f.destinos.some(x=>x.trecho||x.papel==="secundario");
   const alvo=(f.id+" "+f.texto+" "+f.destinos.map(x=>x.p+" "+((D.cat[x.p]||{}).nome||"")).join(" ")).toLowerCase();
   if(q&&!alvo.includes(q))return;if(fo&&!out)return;if(fm&&!multi)return;if(fr&&!rev[f.id])return;n++;
   const trs=f.destinos.map(x=>x.trecho).filter(Boolean);
   hi+=`<div class="fr ${rev[f.id]!==undefined?"rev":""}" data-id="${f.id}"><div class="txt"><span class="id">${f.id}</span><br>${hl(f.texto,trs)}</div>
   <button class="flag" data-f="${f.id}">${rev[f.id]!==undefined?"⚑ revisar":"⚐ revisar"}</button>
   <div class="dest">${grp.map(g=>`<div class="grp">${g.k?`<span class="tr">trecho: “${esc(g.k)}”</span>`:""}${g.l.map(x=>chip(x,d.disciplina_banco)).join(" ")}</div>`).join("")}</div>
   <input class="note" data-n="${f.id}" placeholder="O que está errado / o que você prefere?" value="${esc(rev[f.id]||"")}"></div>`});
   if(hi)hd+=`<div class="item">Item ${it.rotulo||"(sem número)"}</div>`+hi});
  if(hd)h+=`<h2 style="font-size:18px;margin:26px 0 0">${esc(d.disciplina_banco)} <small style="color:var(--mut);font-weight:400">(${esc(d.titulo_no_edital)})</small></h2>`+hd});
 if(disc==="TODAS"&&!q&&!fo&&!fm&&!fr&&D.propostas.length)h+=`<h2 style="font-size:18px;margin:26px 0 6px">Propostas de tópicos novos</h2>`+D.propostas.map(p=>`<div class="box"><b>${p.id}</b> · ${esc(p.disciplina)} · ${esc(p.nome)}<br><span style="color:var(--mut)">${esc(p.justificativa)}</span><br><span class="sp">Frases: ${p.usada_nas_frases.join(", ")}. Parecidos no catálogo: ${p.parecidos_no_catalogo.map(x=>x.codigo+" "+esc(x.nome)).join("; ")||"nenhum"}</span></div>`).join("");
 $("m").innerHTML=h||"<p>Nada com esses filtros.</p>";$("cnt").textContent=n+" frases · "+Object.keys(rev).length+" marcadas"}
$("m").onclick=e=>{const b=e.target.closest("[data-f]");if(!b)return;const id=b.dataset.f;if(rev[id]===undefined)rev[id]="";else delete rev[id];save();draw()};
$("m").oninput=e=>{const i=e.target.closest("[data-n]");if(i){rev[i.dataset.n]=i.value;save()}};
$("copiar").onclick=()=>{const t=Object.entries(rev).map(([k,v])=>k+(v?" — "+v:"")).join("\n")||"(nenhuma marcada)";
 const done=()=>{$("copiar").textContent="Copiado ✓";setTimeout(()=>$("copiar").textContent="Copiar marcadas",1500)};
 (navigator.clipboard?navigator.clipboard.writeText(t).then(done,()=>prompt("Copie:",t)):Promise.reject()).catch?.(()=>prompt("Copie:",t))};
draw();
</script></body></html>"""
saida = pasta / "rascunho.html"
saida.write_text(HTML.replace("__DADOS__", json.dumps(dados, ensure_ascii=False)), encoding="utf-8")
print("gerado", saida)
