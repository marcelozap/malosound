"""Add selected chart-only sessions from a saved SPY minute snapshot.

Requires a complete regular session. Does not create songs or trade assessments.
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
    if result['meta']['symbol'] != 'SPY' or result['meta']['dataGranularity'] != '1m':
        raise ValueError('A SPY 1m snapshot is required')
    stamps = result['timestamp']
    quotes = result['indicators']['quote'][0]
    fields = ('open', 'high', 'low', 'close')
    if any(len(quotes[k]) != len(stamps) for k in fields):
        raise ValueError('Unequal timestamp and price array lengths')
    entries = []
    for day in days:
        bars = []
        for i, stamp in enumerate(stamps):
            local = datetime.fromtimestamp(stamp, ZoneInfo('America/New_York'))
            minute = local.hour * 60 + local.minute - 570
            if local.date().isoformat() != day or not 0 <= minute < 390:
                continue
            values = {k: quotes[k][i] for k in fields}
            if local.second or any(type(v) not in (int, float) or not math.isfinite(v) for v in values.values()):
                raise ValueError('Invalid minute or price: ' + day)
            if not values['low'] <= min(values['open'], values['close']) <= max(values['open'], values['close']) <= values['high']:
                raise ValueError('Invalid OHLC range: ' + day)
            bars.append(dict(minute=minute, **values))
        if [b['minute'] for b in bars] != list(range(390)):
            raise ValueError('Session must contain 390 ordered, unique minute bars: ' + day)
        entries.append((day, bars))
    return hashlib.sha256(raw).hexdigest(), entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--dates', nargs='+', required=True)
    args = parser.parse_args()
    if len(set(args.dates)) != len(args.dates):
        raise ValueError('Duplicate requested dates')
    digest, entries = prepare(args.source, args.dates)
    data = json.loads((ROOT / 'content/editions.json').read_text(encoding='utf-8'))
    existing = {s['date'] for s in data['sessions']}
    if existing.intersection(args.dates):
        raise ValueError('Existing entries require review before replacement')
    assets = set(json.loads((ROOT / 'content/market-assets.json').read_text()))
    outputs = {}
    for day, bars in entries:
        low = min(b['low'] for b in bars)
        high = max(b['high'] for b in bars)
        points = [(0, bars[0]['open'])] + [(b['minute'] + 1, b['close']) for b in bars]
        path = ' '.join(f'{"M" if i == 0 else "L"}{24 + m / 390 * 952:.2f},{30 + (high - p) / (high - low or 1) * 280:.2f}' for i, (m, p) in enumerate(points))
        chart = f'assets/charts/{day}-minute.svg'
        source_name = f'content/history/{day}-minute.json'
        note = 'Opening price followed by 390 minute closes at bar-end times. The 16:00 endpoint is the final minute close, not a separate closing print. Straight segments join observations; height is scaled to this session.'
        outputs[chart] = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 340" role="img" aria-labelledby="t d"><title id="t">SPY {day}</title><desc id="d">{note} Blue means execution has not been reviewed.</desc><path d="{path}" fill="none" stroke="#50b8f5" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        outputs[source_name] = json.dumps(dict(date=day, symbol='SPY', interval='1m', source='Yahoo Finance saved chart snapshot', sourceSha256=digest, priceConvention=note, bars=bars), indent=2) + '\n'
        summary = f'Open {bars[0]["open"]:.2f} · Last minute close {bars[-1]["close"]:.2f}'
        data['sessions'].append(dict(date=day, closing=dict(title='SPY · The day’s line', summary=summary, label='Historical session', paragraphs=[]), lineChart=dict(url='/' + chart, dataUrl='/' + source_name, alt=f'SPY {day}, opening price and 390 minute closes.', caption=summary, startLabel='09:30 ET', endLabel='16:00 ET', gapShort='390 minute bars', gapNote=note, notes=['Saved market observations. Execution unreviewed.'])))
        assets.update((chart, source_name))
    data['sessions'].sort(key=lambda s: s['date'], reverse=True)
    outputs['content/editions.json'] = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    outputs['content/market-assets.json'] = json.dumps(sorted(assets), indent=2) + '\n'
    for name, value in outputs.items():
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding='utf-8')
    print(f'Added {len(entries)} chart-only sessions.')


if __name__ == '__main__':
    main()
