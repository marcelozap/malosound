"""Publish sparse historical SPY bar studies from an existing Yahoo snapshot.

Run manually with --source PATH. Never infers minute prices or owner execution.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

def prepare(source, days):
    raw = source.read_bytes()
    result = json.loads(raw)['chart']['result'][0]
    assert result['meta']['symbol'] == 'SPY'
    assert result['meta']['dataGranularity'] == '1h'
    quotes = result['indicators']['quote'][0]
    stamps = result['timestamp']
    assert all(len(quotes[k]) == len(stamps) for k in ('open','high','low','close'))
    entries = []
    for day in days:
        bars = []
        for i, stamp in enumerate(stamps):
            local = datetime.fromtimestamp(stamp, ZoneInfo('America/New_York'))
            if local.date().isoformat() != day or not '09:30' <= local.strftime('%H:%M') < '16:00':
                continue
            bar = dict(startTime=local.isoformat(), **{k:quotes[k][i] for k in ('open','high','low','close')})
            assert all(type(bar[k]) in (int,float) and math.isfinite(bar[k]) for k in ('open','high','low','close'))
            assert bar['low'] <= min(bar['open'],bar['close']) <= max(bar['open'],bar['close']) <= bar['high']
            bars.append(bar)
        assert [b['startTime'][11:16] for b in bars] == ['09:30','10:30','11:30','12:30','13:30','14:30','15:30']
        entries.append((day,bars))
    return hashlib.sha256(raw).hexdigest(), entries

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--dates',nargs='+',required=True)
    args=parser.parse_args()
    if len(set(args.dates)) != len(args.dates):
        raise ValueError('Duplicate requested dates')
    digest, entries=prepare(args.source, args.dates)
    data=json.loads((ROOT/'content/editions.json').read_text(encoding='utf-8'))
    assets=set(json.loads((ROOT/'content/market-assets.json').read_text()))
    for day,bars in entries:
        if any(s['date']==day for s in data['sessions']):
            raise ValueError('Existing entry must be reviewed before replacing: '+day)
        low=min(b['low'] for b in bars); high=max(b['high'] for b in bars)
        y=lambda price:round(30+(high-price)/(high-low or 1)*260,2)
        marks=[]
        for i,b in enumerate(bars):
            # Equal-width bar marks, never a fabricated trajectory through bars.
            x=70+i*140
            marks.append(f'<path d="M{x},{y(b["high"])} V{y(b["low"])} M{x-12},{y(b["open"])} H{x} M{x},{y(b["close"])} H{x+12}"/>')
        name=f'assets/charts/{day}-hourly.svg'; source_name=f'content/history/{day}-hourly.json'
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 340" role="img" aria-labelledby="t d"><title id="t">SPY '+day+' hourly bars</title><desc id="d">Seven OHLC bars: high to low vertical range, open tick left, close tick right. Last bar covers 15:30 to 16:00 ET. Separate bars do not show a minute path. Blue is neutral, not trade performance.</desc><g stroke="#50b8f5" stroke-width="3" fill="none">'+''.join(marks)+'</g></svg>'
        public=dict(date=day,symbol='SPY',interval='1h',timestampMeaning='bar start; final bar is 30 minutes',source='Yahoo Finance saved chart snapshot',sourceSha256=digest,bars=bars)
        for path,text in [(name,svg),(source_name,json.dumps(public,indent=2)+'\n')]:
            target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf-8')
        summary=f'Open {bars[0]["open"]:.2f} · Last bar close {bars[-1]["close"]:.2f} · Range {low:.2f}–{high:.2f}'
        data['sessions'].append(dict(date=day,closing=dict(title='SPY · Hourly study',summary=summary,label='Historical session · hourly observations',paragraphs=[]),lineChart=dict(url='/'+name,dataUrl='/'+source_name,alt=f'Seven neutral SPY hourly OHLC bars for {day}.',caption=summary,startLabel='09:30 ET',endLabel='16:00 ET',gapShort='Hourly bars · not a minute path',gapNote='Seven separate OHLC bars. Bar timestamps mark interval starts; the final interval ends at 16:00 ET. No interpolation or execution assessment.',notes=['Left tick: open. Right tick: close. Vertical mark: high–low. Height is scaled to this session.'])))
        assets.update([name,source_name])
    data['sessions'].sort(key=lambda s:s['date'],reverse=True)
    (ROOT/'content/editions.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'content/market-assets.json').write_text(json.dumps(sorted(assets),indent=2)+'\n',encoding='utf-8')
    print(f'Added {len(entries)} historical hourly studies, without songs or execution grades.')

if __name__=='__main__': main()
