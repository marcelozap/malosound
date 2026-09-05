"""Build the source-backed line drawings and complete, no-JavaScript day pages."""
from datetime import date, datetime, timedelta
from html import escape as e
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')

def paragraphs(values):
    return ''.join('<p>'+e(p)+'</p>' for p in values)

def links(values):
    return ''.join('<a class="text-link" href="'+e(s['url'], quote=True)+'">'+e(s['label'])+' ↗</a>' for s in values)

def chapter(n, title, body):
    return f'<section class="journal-chapter chapter-{n}"><div class="chapter-label"><span class="chapter-number gold">{n}</span><h2 class="eyebrow gold">{title}</h2></div>{body}</section>'

def refresh():
    data = json.loads((ROOT/'content/editions.json').read_text(encoding='utf-8'))
    assets = set(json.loads((ROOT/'content/market-assets.json').read_text(encoding='utf-8')))
    for index, session in enumerate(sorted(data['sessions'], key=lambda s:s['date'])):
        song = session.get('originalSong') or session.get('closing')
        if not song or not song.get('audioUrl') or not song.get('chart'):
            continue
        day = session['date']; dt = date.fromisoformat(day)
        source_path = song['chart']['dataUrl']
        source = json.loads((ROOT/source_path.lstrip('/')).read_text(encoding='utf-8'))
        summary = source['summary']
        bounds = source.get('price_boundaries')
        if not bounds:
            bounds = [{'minute':0,'price':summary['open'],'source_kind':'first_minute_open'}]
            bounds += [{'minute':m['minute']+1,'price':m['close'],'source_kind':'minute_close'} for m in source['minutes'][:-1]]
            bounds.append({'minute':390,'price':summary['close'],'source_kind':'separate_closing_print'})
        gaps = source.get('missing_intervals', [])
        gap_ends = {g['end_minute'] for g in gaps}
        clock = lambda m:(datetime(2000,1,1,9,30)+timedelta(minutes=m)).strftime('%H:%M')
        sound = lambda m:f'{int(m*.5)//60}:{m*.5%60:04.1f}'
        gap_times = ', '.join(clock(g['start_minute'])+'–'+clock(g['end_minute'])+' ET' for g in gaps)
        lo, hi = summary['low'], summary['high']
        span = hi-lo or 1
        # Actual minute-close shape, without axes or curve smoothing.
        path = []
        for i, b in enumerate(bounds):
            if b['price'] is None:
                continue
            command = 'M' if i == 0 or b['minute'] in gap_ends else 'L'
            path.append(f"{command}{24+b['minute']/390*952:.2f},{30+(hi-b['price'])/span*280:.2f}")
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 340" role="img" aria-labelledby="title desc"><title id="title">The line SPY drew on {day}</title><desc id="desc">Observed minute closing prices, opening boundary and attributed terminal price, 09:30 to 16:00 ET. {'Breaks mark missing source intervals: '+gap_times+'.' if gaps else 'All 390 minute bars are present.'} No axes; vertical scale is relative to this session.</desc><defs><linearGradient id="ink" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#e5b657"/><stop offset=".48" stop-color="#efd497"/><stop offset="1" stop-color="#50b8f5"/></linearGradient></defs><path d="{' '.join(path)}" fill="none" stroke="url(#ink)" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/></svg>'''
        line_path = f'assets/charts/{day}-line.svg'
        notes = [source.get('price_convention','Minute closing prices are placed at their end-of-minute boundaries.'),
                 'The line joins observed boundaries without smoothing. It is not the exact intraminute tick path. Height is scaled to this session’s observed high and low; shapes across dates do not compare absolute price ranges.',
                 source.get('data_note','Source: Yahoo Finance. Retrospective interpretation.')]
        reconciliation = source.get('daily_reconciliation', {})
        daily = reconciliation.get('daily_ohlcv', {})
        if daily and reconciliation.get('ohlc_agreement_within_2_cents') is False:
            notes.append(f"Observed minute open: ${summary['open']:.2f}; vendor daily open: ${daily['open']:.2f}. Observed minute low: ${summary['low']:.2f}; daily low: ${daily['low']:.2f}. These source discrepancies remain unresolved.")
        if source.get('terminal_price', {}).get('source_kind') == 'vendor_daily_close':
            notes.append(f"The final anchor is the vendor daily close of ${summary['close']:.2f}, not a separate 16:00 intraday print; the last minute closes at ${summary['last_minute_bar_close']:.2f}.")
        chart = dict(url='/'+line_path, dataUrl=source_path,
                     alt=f'SPY’s {dt.strftime("%B")} {dt.day} price line from 09:30 to 16:00 ET'+('; breaks mark '+gap_times+'.' if gaps else '.'),
                     caption=f'SPY · Observed minute-close shape · {dt.strftime("%B")} {dt.day}, {dt.year}',
                     notes=notes)
        if gaps:
            rests = ', '.join(sound(g['start_minute'])+'–'+sound(g['end_minute']) for g in gaps)
            chart['gapNote']=f'Missing source data: {gap_times}. The line breaks there; the song leaves space at {rests}. No price or volume was filled in.'
        session['lineChart'] = chart
        write(line_path, svg)
        morning = session.get('preOpen') or session.get('morning')
        pre = '<h3>An open page.</h3><p>No before-open note was published for this date.</p>'
        if morning:
            pre = f'<p class="entry-status">{e(morning["label"])}</p><h3>{e(morning["title"])}</h3><p class="chapter-deck">{e(morning["summary"])}</p>'+paragraphs(morning.get('paragraphs',[]))
            pre += '<details class="journal-details"><summary>Sources & publication notes</summary>'+paragraphs(['Prepared / added: '+morning.get('preparedAt','Not recorded')])+links(morning.get('sources',[]))+'</details>'
        drawing = f'<h3>One session. One gesture.</h3><figure class="session-drawing"><img src="/{line_path}" width="1000" height="340" alt="{e(chart["alt"],quote=True)}"><figcaption class="drawing-times"><span>09:30 ET</span><span>16:00 ET</span></figcaption></figure><p class="drawing-caption">{e(chart["caption"])}</p>'
        if gaps: drawing += '<p class="data-gap">'+e(chart['gapNote'])+'</p>'
        drawing += '<details class="journal-details"><summary>Behind the line</summary>'+paragraphs(notes)+links([dict(url=source_path,label='View the source observations')])+'</details>'
        music = f'<h3 class="song-title">{e(song["title"])}</h3><p class="chapter-deck">SPY’s {dt.strftime("%B")} {dt.day}, 9:30 a.m.–4:00 p.m. ET session, compressed into a 3:15 instrumental.</p><div class="journal-player"><audio controls preload="metadata" aria-label="Listen to {e(song["title"],quote=True)}" src="{e(song["audioUrl"],quote=True)}"></audio></div><div class="song-specs"><span>03:15</span><span>80 BPM</span><span>SPY → SOUND</span></div>'+paragraphs([song.get('thesis',song['summary'])])
        music += '<details class="journal-details"><summary>How the day became music</summary>'+paragraphs(song.get('paragraphs',[]))
        music += '<div class="session-table-wrap"><table class="session-table"><thead><tr><th>Market time ET</th><th>Song time</th><th>Section</th></tr></thead><tbody>'
        for s in source.get('sections',[]):
            clock = lambda m:(datetime(2000,1,1,9,30)+timedelta(minutes=m)).strftime('%H:%M')
            sound = lambda m:f'{int(m*.5)//60}:{m*.5%60:04.1f}'
            music += f'<tr><td>{clock(s["start_minute"])}–{clock(s["end_minute"])}</td><td>{sound(s["start_minute"])}–{sound(s["end_minute"])}</td><td>{e(s["name"])}</td></tr>'
        music += '</tbody></table></div>'+links(song.get('sources',[]))
        if song.get('midiUrl'): music += links([dict(url=song['midiUrl'],label='Download editable MIDI')])
        music += '</details>'
        report = song['reportUrl'].lstrip('/')
        page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="MaloSound journal for {day}: the morning thought, SPY’s observed line, and an original 3:15 instrumental."><title>{dt.strftime('%B')} {dt.day} · {e(song['title'])} — MaloSound.ai</title><link rel="stylesheet" href="/journal.css"><link rel="canonical" href="https://malosound.ai/{report}"></head><body class="art-home"><a class="skip" href="#main">Skip to content</a><div class="wrap"><header class="topbar"><a class="wordmark" href="/">malosound<span>.ai</span></a><nav class="nav" aria-label="Main navigation"><a href="/#journal">Calendar</a><a href="/#xiv">XIV</a></nav></header><main id="main" class="standalone-journal"><div class="standalone-art" aria-hidden="true"></div><article class="day-entry"><header class="day-heading"><span class="eyebrow gold">Journal / {index+1:03d}</span><h1>{dt.strftime('%B')} {dt.day}</h1><p class="day-subtitle">{dt.strftime('%A, %Y')} · SPY · New York</p></header>{chapter('01','Before the open',pre)}{chapter('02','The line the day drew',drawing)}{chapter('03','The day, in another key',music)}</article><p><a class="text-link" href="/#journal">Back to the calendar ↗</a></p></main></div></body></html>'''
        write(report,page)
        assets.update([line_path,report,source_path.lstrip('/')])
    write('content/editions.json',json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    write('content/market-assets.json',json.dumps(sorted(assets),indent=2)+'\n')

if __name__ == '__main__': refresh()
