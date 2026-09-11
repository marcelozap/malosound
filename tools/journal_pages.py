"""Build the source-backed line drawings and complete, no-JavaScript day pages."""
from datetime import date, datetime, timedelta
from html import escape as e
import json
from pathlib import Path
from trade_journal import (validate as validate_trades, presentation, strip as trade_strip,
                           notes as trade_notes, legend as trade_legend,
                           EXECUTION)
import session_chart
from trade_overlays import note as trade_overlay_note

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

def redraw_archive_charts(data, trades):
    """Redraw every saved archive session from its own bars and the current review.

    Hourly and minute archive days were drawn once, by the backfill tool that
    imported them, and never again. That meant an execution review could never
    reach them: Marcelo could assess a June session and its chart would stay
    neutral blue for ever, because nothing regenerated it. Song days were redrawn
    on every build and archive days were not, and the difference was invisible
    until someone actually reviewed a day.

    Drawing them here, from the saved bars plus the ledger, puts every published
    day on the same footing.
    """
    redrawn = []
    for session in data['sessions']:
        chart = session.get('lineChart') or {}
        url, data_url = chart.get('url', ''), chart.get('dataUrl', '')
        if not url or not data_url or url.endswith('-line.svg'):
            continue
        saved = ROOT / data_url.lstrip('/')
        if not saved.is_file():
            # Declared but not on disk. This is the unavailable-chart case, not a
            # reason to fail the build, and it must never be filled in with
            # another date's bars. verify_published_charts reports it by name.
            continue
        source = json.loads(saved.read_text(encoding='utf-8'))
        bars = session_chart.bars_from(source)
        if not bars:
            continue
        performance = presentation(trades.get(session['date']))
        hourly = source.get('interval') == '1h'
        detail = ('A thin line joins the session open and each hourly bar’s close — eight '
                  'points across the regular session, positioned by the clock. The last bar '
                  'covers 15:30 to 16:00 ET. Hourly bars, not a minute path.' if hourly else
                  'A thin line joins the session open and every observed minute close, '
                  '09:30 to 16:00 ET.')
        write(url.lstrip('/'), session_chart.document(
            session['date'], bars, performance['executionSections'],
            title=f'SPY {session["date"]} {"hourly" if hourly else "minute"} line',
            detail=detail, trade_sections=performance['tradeSections'],
            resolution='hourly' if hourly else 'minute'))
        chart['alt'] = (f'SPY {"hourly" if hourly else "minute"} line for {session["date"]}, '
                        f'09:30 to 16:00 ET. '
                        f'{trade_overlay_note(performance["tradeSections"], "hourly" if hourly else "minute")}')
        if hourly:
            chart['gapNote'] = ('The line joins the session open and each hourly bar’s close — '
                                'eight points in all. Bar timestamps mark interval starts; the '
                                'final interval ends at 16:00 ET. No interpolation between them '
                                'and no minute-level price path. Trade colors use only supplied times and outcomes.')
            chart['notes'] = ['A thin line connects the session open and each hourly bar’s '
                              'close, in the order they were observed. Height is scaled to '
                              'this session.']
        redrawn.append(session['date'])
    return redrawn


def refresh():
    data = json.loads((ROOT/'content/editions.json').read_text(encoding='utf-8'))
    assets = set(json.loads((ROOT/'content/market-assets.json').read_text(encoding='utf-8')))
    trades = validate_trades(json.loads((ROOT/'content/trading-journal.json').read_text(encoding='utf-8')))
    for index, session in enumerate(sorted(data['sessions'], key=lambda s:s['date'])):
        performance = presentation(trades.get(session['date']))
        session['performance'] = performance
        song = session.get('originalSong') or session.get('closing')
        # A day earns a drawn line as soon as it has checked source data. Music is
        # optional: older archive days can be chart-only, and a standalone page is
        # written only where a song and its report URL actually exist.
        if not song or not song.get('chart') or not song['chart'].get('dataUrl'):
            continue
        has_song = bool(song.get('audioUrl'))
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
        points = []
        for i, b in enumerate(bounds):
            if b['price'] is None:
                continue
            x, y = round(24+b['minute']/390*952, 2), round(30+(hi-b['price'])/span*280, 2)
            points.append(dict(minute=b['minute'], x=x, y=y))
        # One <path> per reviewed stretch. The coordinates are the same observed
        # points in the same order; only the stroke color changes at a boundary,
        # and a boundary point is drawn in both runs so the line stays unbroken.
        drawn = session_chart.trade_lines(session_chart.bars_from(source),
                                          performance['tradeSections'], lo, hi)
        colour_note = trade_overlay_note(performance['tradeSections'])
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 340" role="img" aria-labelledby="title desc"><title id="title">SPY line for {day}, 09:30 to 16:00 ET</title><desc id="desc">A thin line joins the session open and every observed minute close, 09:30 to 16:00 ET, without smoothing. {'Breaks mark missing source intervals: '+gap_times+'.' if gaps else 'All 390 minute bars are present.'} No axes; vertical scale is relative to this session. {colour_note} Marcelo's net result that day: {performance['label']}.</desc>{drawn}</svg>'''
        line_path = f'assets/charts/{day}-line.svg'
        timeline_path = f'assets/charts/{day}-timeline.json'
        timeline = dict(marketStartMinutes=570,
                        marketDurationMinutes=390, width=1000, height=340, points=points,
                        tradeSections=performance['tradeSections'],
                        gaps=[dict(startMinute=g['start_minute'], endMinute=g['end_minute']) for g in gaps])
        if has_song:
            timeline = dict(durationSeconds=source['duration_seconds'], **timeline)
            write(timeline_path, json.dumps(timeline, separators=(',', ':'))+'\n')
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
                     alt=f'SPY minute line for {dt.strftime("%B")} {dt.day}, 09:30 to 16:00 ET'+('; breaks mark '+gap_times+'.' if gaps else '.')+' '+colour_note,
                     caption=f'SPY · Minute line · {dt.strftime("%B")} {dt.day}, {dt.year}',
                     notes=notes)
        if has_song:
            chart['playheadUrl'] = '/'+timeline_path
        if gaps and not has_song:
            chart['gapNote'] = f'Missing source data: {gap_times}. The line breaks there. No price or volume was filled in.'
            chart['gapShort'] = f'Source gap · {gap_times}'
        elif gaps:
            rests = ', '.join(sound(g['start_minute'])+'–'+sound(g['end_minute']) for g in gaps)
            chart['gapNote']=f'Missing source data: {gap_times}. The line breaks there; the song leaves space at {rests}. No price or volume was filled in.'
            chart['gapShort']=f'Source gap · {gap_times} · silence {rests}'
        session['lineChart'] = chart
        write(line_path, svg)
        morning = session.get('preOpen') or session.get('morning')
        pre = '<h3>An open page.</h3><p>No before-open note was published for this date.</p>'
        if morning:
            pre = f'<p class="entry-status">{e(morning["label"])}</p><h3>{e(morning["title"])}</h3>'
            pre += '<details class="journal-details"><summary>Notes + sources</summary>'+paragraphs([morning['summary']]+morning.get('paragraphs',[])+['Prepared / added: '+morning.get('preparedAt','Not recorded')])+links(morning.get('sources',[]))+'</details>'
        pre = '<details class="morning-fold"><summary>Morning notes</summary>'+pre+'</details>'
        drawing = f'<figure class="session-drawing" data-timeline-src="/{timeline_path}"><div class="drawing-stage"><img src="/{line_path}" width="1000" height="340" alt="{e(chart["alt"],quote=True)}"></div><figcaption class="drawing-times"><span>09:30 ET</span><span>16:00 ET</span></figcaption></figure>'
        drawing = trade_strip(performance) + drawing + trade_legend(performance)
        if gaps: drawing += '<p class="data-gap">'+e(chart['gapShort'])+'</p>'
        drawing += '<details class="journal-details"><summary>Behind the line</summary>'+paragraphs([chart['caption']]+([chart['gapNote']] if gaps else [])+notes)+links([dict(url=source_path,label='View the source observations')])+'</details>'
        drawing += '<details class="journal-details"><summary>My trading record</summary>'+paragraphs(trade_notes(performance))+'</details>'
        if not has_song or not song.get('reportUrl'):
            # Chart-only archive day. The line and provenance are already
            # written above; there is no music timeline or standalone page to
            # build. Music stays optional for older entries.
            assets.update([line_path, source_path.lstrip('/')])
            if has_song:
                assets.add(timeline_path)
            continue
        music = f'<p class="eyebrow blue">One song. One session.</p><div class="journal-player"><audio controls preload="metadata" aria-label="Listen to {e(song["title"],quote=True)}" src="{e(song["audioUrl"],quote=True)}"></audio></div><div class="song-specs"><span>03:15</span><span>80 BPM</span><span>SPY → SOUND</span></div>'
        music += '<details class="journal-details"><summary>About the song</summary>'+paragraphs([f'SPY’s {dt.strftime("%B")} {dt.day}, 9:30 a.m.–4:00 p.m. ET session, compressed into a 3:15 instrumental.',song.get('thesis',song['summary'])]+song.get('paragraphs',[]))
        music += '<div class="session-table-wrap"><table class="session-table"><thead><tr><th>Market time ET</th><th>Song time</th><th>Section</th></tr></thead><tbody>'
        for s in source.get('sections',[]):
            clock = lambda m:(datetime(2000,1,1,9,30)+timedelta(minutes=m)).strftime('%H:%M')
            sound = lambda m:f'{int(m*.5)//60}:{m*.5%60:04.1f}'
            music += f'<tr><td>{clock(s["start_minute"])}–{clock(s["end_minute"])}</td><td>{sound(s["start_minute"])}–{sound(s["end_minute"])}</td><td>{e(s["name"])}</td></tr>'
        music += '</tbody></table></div>'+links(song.get('sources',[]))
        if song.get('midiUrl'): music += links([dict(url=song['midiUrl'],label='Download editable MIDI')])
        music += '</details>'
        report = song['reportUrl'].lstrip('/')
        page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="MaloSound journal for {day}: the morning thought, SPY’s observed line, and an original 3:15 instrumental."><title>{dt.strftime('%B')} {dt.day} · {e(song['title'])} — MaloSound.ai</title><link rel="stylesheet" href="/journal.css"><link rel="canonical" href="https://malosound.ai/{report}"></head><body class="art-home"><a class="skip" href="#main">Skip to content</a><div class="wrap"><header class="topbar"><a class="wordmark" href="/">malosound<span>.ai</span></a><nav class="nav" aria-label="Main navigation"><a href="/#journal">Calendar</a></nav></header><main id="main" class="standalone-journal"><div class="standalone-art" aria-hidden="true"></div><article class="day-entry"><header class="day-heading session-cover"><div class="cover-aura" aria-hidden="true"></div><div class="cover-orbit" aria-hidden="true"></div><div class="cover-copy"><span class="eyebrow gold">{dt.strftime('%B')} {dt.day} · {dt.year}</span><h1>{e(song['title'])}</h1><p class="day-subtitle">SPY · SESSION REPLAY · 03:15</p></div></header>{chapter('01','Before the open',pre)}{chapter('02','The line the day drew',drawing)}{chapter('03','The day, in another key',music)}</article><p><a class="text-link" href="/#journal">Back to the calendar ↗</a></p></main></div></body></html>'''
        page = page.replace('<article class="day-entry">', f'<article class="day-entry" data-trade-result="{performance["outcome"]}">')
        page = page.replace('</body>', '<script src="/session-playhead.js" defer></script></body>')
        write(report,page)
        assets.update([line_path,timeline_path,report,source_path.lstrip('/')])
    redraw_archive_charts(data, trades)
    write('content/editions.json',json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    assets.update(write_archive(data, trades))
    write('content/market-assets.json',json.dumps(sorted(assets),indent=2)+'\n')


def archive(data, trades):
    """A small index the calendar can hold, plus one detail file per day.

    The browser loads the index once and fetches only the day it is showing, so
    a year of entries costs the same first paint as a week. Every field here is
    derived from editions.json; nothing new is asserted.

    Returns {path: text} rather than writing, so the same code that fills the
    checkout can fill the build directory from the staged copy of the data,
    after the audio URLs have been rewritten to local files.
    """
    sessions = sorted(data['sessions'], key=lambda s: s['date'])
    files = {}
    index_days = []
    for session in sessions:
        day = session['date']
        song = session.get('originalSong') or session.get('closing')
        chart = session.get('lineChart')
        view = presentation(trades.get(day))
        index_days.append(dict(
            date=day,
            title=(song or {}).get('title') or (session.get('morning') or session.get('preOpen') or {}).get('title') or '',
            hasSong=bool(song and song.get('audioUrl')),
            hasChart=bool(chart),
            chartUrl=(chart or {}).get('url'),
            marketClosed=bool((song or {}).get('marketClosed')),
            outcome=view['outcome'],
            outcomeLabel=view['label'],
            setupRating=view['setupRating'],
            executionReviewed=view['execution']['reviewed'],
            executionLabel=view['execution']['label'],
            detailUrl=f'/content/days/{day}.json'))
        files[f'content/days/{day}.json'] = json.dumps(session, ensure_ascii=False, separators=(',', ':')) + '\n'
    earliest = sessions[0]['date'] if sessions else None
    declared = data.get('seriesStartDate')
    index = dict(schemaVersion=1,
                 # An entry older than the declared start is still an entry. The
                 # calendar must be able to reach it, so the index reports the
                 # earlier of the two and never hides a day behind the boundary.
                 seriesStartDate=min(x for x in (declared, earliest) if x) if (declared or earliest) else None,
                 declaredStartDate=declared,
                 songDurationSeconds=data.get('songDurationSeconds'),
                 months=sorted({s['date'][:7] for s in sessions}),
                 days=index_days)
    files['content/journal-index.json'] = json.dumps(index, ensure_ascii=False, indent=2) + '\n'
    return files


def write_archive(data, trades):
    files = archive(data, trades)
    for path, text in files.items():
        write(path, text)
    return list(files)

if __name__ == '__main__': refresh()
