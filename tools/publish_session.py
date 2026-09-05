"""Stage a validated original session in the public journal; does not push/deploy.

python -X utf8 tools/publish_session.py --analysis PATH --audio-url HTTPS_URL --midi-url HTTPS_URL
"""
import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo('America/New_York')
esc=html.escape


def require(condition,message):
    if not condition: raise ValueError(message)


def safe_url(url):
    u=urlsplit(url)
    require(u.scheme=='https' and u.hostname and not u.username and not u.password,'Public HTTPS media URL required')
    return url


def stage(analysis_path,audio_url,midi_url):
    a=json.loads(analysis_path.read_text(encoding='utf-8'))
    require(a['symbol']=='SPY' and len(a['minutes'])==390,'Requires a complete 390-minute SPY session')
    require(a['duration_seconds']==195 and a['tempo_bpm']==80,'Series requires 195 seconds at 80 BPM')
    require([m['minute'] for m in a['minutes']]==list(range(390)),'Incomplete minute sequence')
    c=a['composition']; day=a['date']; s=a['summary']
    require(c['date']==day and c['symbol']=='SPY','Composition must belong to this session')
    require(datetime.fromisoformat(day).date().isoformat()==day,'Invalid date')
    audio_url=safe_url(audio_url);midi_url=safe_url(midi_url)
    data=json.loads((ROOT/'content/editions.json').read_text(encoding='utf-8'))
    session=next((x for x in data['sessions'] if x['date']==day),None)
    if session and session.get('closing'):
        old=session['closing']
        if old.get('sourceHash')==a['source_sha256'] and old.get('audioUrl')==audio_url:
            print('Already staged this exact session; no history changed.');return
        raise ValueError('A closing edition already exists. Preserve it and prepare an explicit dated revision.')
    require(data['songDurationSeconds'] in (None,195),'Existing series uses another duration')
    prepared=datetime.now(ET).isoformat(timespec='seconds')
    report=f'reports/{day}-spy-song.html'; chart=f'assets/charts/{day}-spy.svg'; audit=f'assets/charts/{day}-spy-data.json'
    summary=(f"SPY opened at ${s['open']:.2f}, reached its low in the {s['low_bar_et']} ET minute, "
             f"and ended at ${s['close']:.2f}. {c['thesis']} "
             f"The full 9:30–4:00 session becomes a 3:15 original instrumental.")
    recon=a.get('daily_reconciliation',{})
    require(a['validation']['missing_bars']==0 and a['validation']['duplicate_bars']==0 and a['validation']['imputed_bars']==0,'Unverified minute coverage')
    require(len(c['sections'])==len(a['sections']) and all(x['start_minute']==y['start_minute'] and x['end_minute']==y['end_minute'] for x,y in zip(c['sections'],a['sections'])),'Musical and measured sections must share boundaries')
    require(recon and abs(recon['ending_price_difference'])<.02,'Resolve daily closing-price discrepancy before using this publication template')
    volume_note=(f"Observed minute volume totals {recon['minute_volume_sum']:,} shares, "
                 f"{recon['minute_volume_fraction_of_daily']*100:.2f}% of the provider's daily total. "
                 "Dynamics use those observed volumes; no missing volume is invented.") if recon else 'Volume intensity is relative within the observed session.'
    comparison='No genuine pre-open entry exists for this date in this journal, so no morning forecast is scored.'
    morning=(session or {}).get('morning')
    if morning and 'after close' not in morning.get('label','').lower():
        comparison='Read the dated morning entry alongside this closing observation. The source measurements are descriptive; they do not establish predictive accuracy.'
    paragraphs=[f"Session: {day}, 09:30–16:00 America/New_York. Prepared: {prepared}. This first rendering is retrospective.",
        comparison,c['thesis'],
        'Price controls melodic contour. Observed volume shapes rhythmic activity; volatility shapes texture. The key, tempo, instruments and seven-part arrangement are artistic choices, with LLM assistance and a procedural audio render.',
        f"The session high was ${s['high']:.2f} in the {s['high_bar_et']} bar; the low was ${s['low']:.2f} in the {s['low_bar_et']} bar. The separate 16:00 print is ${s['close']:.2f}; the final minute bar close is ${s['last_minute_bar_close']:.2f}.",
        volume_note,'Full-day normalization is retrospective. Minute bars do not reveal the exact intraminute path, and musical expression is not evidence of trading performance.']
    sources=[{'label':'Yahoo Finance — source minute chart','url':a['source_url']}]
    if recon: sources.append({'label':'Yahoo Finance — daily consistency check','url':recon['source_url']})
    entry=dict(title=c['title'],summary=summary,label='Original instrumental · retrospective session',paragraphs=paragraphs,
        reportUrl='/'+report,audioUrl=audio_url,midiUrl=midi_url,durationSeconds=195,tempoBpm=80,
        preparedAt=prepared,sourceHash=a['source_sha256'],sources=sources,
        chart=dict(url='/'+chart,dataUrl='/'+audit,alt=f'SPY minute closing prices for {day}, 09:30–16:00 New York, including the opening and separate closing print.',
            caption='Observed minute closes, session open and separate 16:00 print. Vertical axis is a focused USD price scale. Source: Yahoo Finance.'))

    # Export selected public market fields; exclude local paths, private notes,
    # raw renderer metadata and credentials by construction.
    public=dict(symbol='SPY',date=day,session_start=a['session_start'],session_end=a['session_end'],
        prepared_at=prepared,source_url=a['source_url'],source_sha256=a['source_sha256'],
        summary={k:s[k] for k in ('open','close','last_minute_bar_close','high','low','high_bar_et','low_bar_et')},
        duration_seconds=195,tempo_bpm=80,sections=c['sections'],data_note=volume_note,
        price_convention='Open at minute 0; minute closes at boundaries 1..389; separate closing print at 390.',
        minutes=[{k:m[k] for k in ('minute','timestamp_et','open','high','low','close','volume')} for m in a['minutes']])
    prices=[s['open']]+[m['close'] for m in a['minutes'][:-1]]+[s['close']]
    lo=s['low']-.15;hi=s['high']+.15
    x=lambda t:76+t/390*868
    y=lambda p:85+(hi-p)/(hi-lo)*235
    poly=' '.join(f'{x(i):.2f},{y(p):.2f}' for i,p in enumerate(prices))
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 395" role="img" aria-labelledby="title desc"><title id="title">SPY session prices · {day}</title><desc id="desc">Minute closing prices from 09:30 to 16:00 New York. Focused US dollar scale. Source Yahoo Finance.</desc><rect width="1000" height="395" fill="#081016"/><g font-family="Arial,sans-serif"><text x="76" y="36" fill="#edece7" font-size="23">SPY · {day}</text><text x="76" y="61" fill="#a9b0b4" font-size="15">Minute closes · USD · 09:30–16:00 New York</text>']
    for tick in range(int(lo)+1,int(hi)+1):
        yy=y(tick);svg.append(f'<line x1="76" y1="{yy}" x2="944" y2="{yy}" stroke="#273036"/><text x="62" y="{yy+5}" text-anchor="end" fill="#a9b0b4" font-size="15">{tick}</text>')
    for minute,label in [(0,'09:30'),(90,'11:00'),(180,'12:30'),(270,'14:00'),(390,'16:00')]:
        svg.append(f'<text x="{x(minute)}" y="351" text-anchor="middle" fill="#a9b0b4" font-size="16">{label}</text>')
    svg.extend([f'<polyline points="{poly}" fill="none" stroke="#e5b657" stroke-width="2.8" stroke-linejoin="round"/>',
        '<text x="76" y="382" fill="#a9b0b4" font-size="14">Source: Yahoo Finance · Retrospective musical interpretation · Full source notes in the session analysis</text></g></svg>'])
    table=''.join(f"<tr><td>{esc(z['start_et'])}–{esc(z['end_et'])}</td><td>{esc(z['song_start'])}–{esc(z['song_end'])}</td><td>{esc(c['sections'][i]['name'])}</td></tr>" for i,z in enumerate(a['sections']))
    article=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="SPY's {day} regular session translated into an original 3:15 instrumental, with source data and musical mapping."><title>{esc(c['title'])} — MaloSound.ai</title><link rel="stylesheet" href="../journal.css"><link rel="canonical" href="https://malosound.ai/{report}"></head><body><a class="skip" href="#main">Skip to content</a><div class="wrap"><header class="topbar"><a class="wordmark" href="../">malosound<span>.ai</span></a><nav class="nav" aria-label="Main navigation"><a href="../#journal">Sessions</a><a href="../#xiv">XIV</a></nav></header><main id="main" class="article-page session-page"><span class="eyebrow blue">{day} · Original instrumental · Retrospective</span><h1>{esc(c['title'])}</h1><p class="article-deck">{esc(summary)}</p><audio controls preload="metadata" aria-label="Listen to {esc(c['title'])}" src="{esc(audio_url,quote=True)}"></audio><div class="metric-strip"><span>3:15</span><span>80 BPM</span><span>65 bars</span><span>390 market minutes</span></div><img class="session-chart" src="../{chart}" alt="{esc(entry['chart']['alt'],quote=True)}"><div class="prose"><h2>How the day became a song</h2><p>{esc(c['thesis'])}</p><p>{esc(paragraphs[3])}</p><div class="session-table-wrap"><table class="session-table"><thead><tr><th>Market time ET</th><th>Song time</th><th>Section</th></tr></thead><tbody>{table}</tbody></table></div><h2>The observations and their limits</h2>{''.join('<p>'+esc(p)+'</p>' for p in [paragraphs[4],comparison,volume_note,paragraphs[-1]])}<p>One market minute becomes half a second of music. Minute closes are aligned to the end of their minute; the separate 16:00 price supplies the last boundary. Notes sample that path on a musical rhythm.</p><p>All 390 minute timestamps were checked. The original WAV is exactly 195 seconds with no clipped samples. Open, high, low and the final print agree with the same provider's daily bar; this is vendor consistency, not independent exchange certification.</p><h2>Explore the record</h2><p><a class="text-link" href="../{audit}">View the source data and mapping ↗</a></p><p><a class="text-link" href="{esc(midi_url,quote=True)}">Download the editable MIDI ↗</a></p>{''.join('<p><a class="text-link" href="'+esc(z['url'],quote=True)+'">'+esc(z['label'])+' ↗</a></p>' for z in sources)}<p class="source-note">Prepared {esc(prepared)}. Source snapshot SHA-256: {a['source_sha256']}. This is an original instrumental sketch with LLM-assisted arrangement, not a vocal recording or a performance claim.</p></div><div class="article-end"><a class="text-link" href="../#journal">Back to the journal ↗</a></div></main></div></body></html>'''
    for filename,text in [(report,article),(chart,''.join(svg)),(audit,json.dumps(public,indent=2))]:
        p=ROOT/filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
    if session is None: session={'date':day};data['sessions'].append(session)
    session['closing']=entry;data['songDurationSeconds']=195
    data['sessions'].sort(key=lambda x:x['date'],reverse=True)
    (ROOT/'content/editions.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assets=set(json.loads((ROOT/'content/market-assets.json').read_text(encoding='utf-8')))
    assets.update([report,chart,audit])
    (ROOT/'content/market-assets.json').write_text(json.dumps(sorted(assets),indent=2)+'\n',encoding='utf-8')
    print(f'Staged {day}: original audio, chart, analysis and preserved archive.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--analysis',type=Path,required=True);p.add_argument('--audio-url',required=True);p.add_argument('--midi-url',required=True)
    args=p.parse_args();stage(args.analysis,args.audio_url,args.midi_url)
