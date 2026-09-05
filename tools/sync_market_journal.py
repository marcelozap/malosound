#!/usr/bin/env python3
"""Import approved market journal editions into MaloSound, preserving existing dates."""
from pathlib import Path
import json, shutil
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('/Users/a14/Documents/xiv/market-journal')
data=json.loads((ROOT/'content/editions.json').read_text())
sessions={s['date']:s for s in data['sessions']}
assets=[]
def copy(src,dest):
 p=ROOT/dest;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,p);assets.append(dest)
def put(day,kind,entry):
 session=sessions.setdefault(day,{'date':day})
 if kind in session and session[kind]!=entry:
  raise ValueError(f'{day} {kind} already differs; review before replacing published history')
 session[kind]=entry
entries=json.loads((SOURCE/'data/entries.json').read_text())
for e in entries:
 report=f"reports/{e['id']}.html"
 copy(SOURCE/'public'/e['reportUrl'].lstrip('/'),report)
 page=ROOT/report
 html=page.read_text()
 if 'name="description"' not in html:
  page.write_text(html.replace('</head>','<meta name="description" content="Dated market research published with the MaloSound journal."></head>'))
 put(e['id'],'morning',{'title':e['title'],'summary':e['summary'],'label':e['edition'],'paragraphs':[f"Snapshot: {e['cutoffLabel']}. {e['marketStatus']}"]+[f"{c['title']} — {c['body']}" for c in e['changes']], 'reportUrl':'/'+report,'mapUrl':'/market-map.html?date='+e['id']})
for e in json.loads((SOURCE/'data/closings.json').read_text()):
 chart=f"assets/charts/{e['id']}.png";audit=f"assets/charts/{e['id']}-data.json"
 copy(SOURCE/'public'/e['chart']['url'].lstrip('/'),chart)
 copy(SOURCE/'public/charts'/f"{e['id']}-data.json",audit)
 put(e['id'],'closing',{'title':e['title'],'summary':e['summary'],'label':e['session'],'paragraphs':[f"Session reference: {e['cutoff']}. Prepared: {e.get('generatedAt',e['cutoff'])}. Retrospective entries are not contemporaneous forecasts.",e['comparison']]+e['lessons']+['Next session — '+e['nextWatch']], 'chart':{'url':'/'+chart,'alt':e['chart']['alt'],'caption':e['chart']['caption'],'dataUrl':'/'+audit},'song':e['song'],'sources':e['sources']})
data['sessions']=sorted(sessions.values(),key=lambda e:e['date'],reverse=True)
(ROOT/'content/editions.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
(ROOT/'content/market-map.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
(ROOT/'content/market-assets.json').write_text(json.dumps(sorted(assets),indent=2)+'\n')
print(f'Imported {len(sessions)} session dates with {len(assets)} evidence files.')
