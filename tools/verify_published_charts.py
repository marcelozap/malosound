#!/usr/bin/env python3
"""Check that every published chart draws the right date from real supplied data.

Marcelo has reported wrong charts before, so this exists to make that claim
checkable rather than argued. It reads only what is published and asks four
questions of each day:

* Does the drawing belong to the date it is filed under? A day payload, its
  history file and its chart all carry the date independently, and a mismatch
  between any two of them is a chart showing the wrong session.
* Is there real supplied data behind it, with a hash naming where it came from?
* Is the resolution stated honestly? Seven hourly bars must not be described in
  language that implies a minute path.
* Is execution still unreviewed? Every published day should say so until Marcelo
  reviews one.

Two history schemas exist. The archive writes `sourceSha256` with `bars`; the two
song days were prepared earlier and write `source_sha256` with `minutes`. Both
carry provenance. A first version of this check knew only the first shape and
reported the song days as having no source hash at all, which was wrong and is
the reason the reader below is deliberately schema-agnostic: a verifier that
misreads a schema manufactures the very problem it was written to detect.

It also separates two absences that look alike from the outside. A date with a
journal entry and no chart data is a gap in the market sources. A date with chart
data and no entry is a publishing decision. Neither is an error, and reporting
them as one number hides which is which.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNREVIEWED = 'Execution not reviewed'


def series(history):
    """The observed points of a history file, whichever schema wrote it."""
    for key in ('bars', 'minutes', 'closes'):
        if isinstance(history.get(key), list):
            return key, history[key]
    return None, []


def source_hash(history):
    for key in ('sourceSha256', 'source_sha256'):
        if history.get(key):
            return history[key]
    return None


def resolution(history):
    interval = history.get('interval')
    if interval:
        return interval
    # The song-day schema names no interval; it is a minute session by
    # construction, and says so through its minute-indexed series.
    key, points = series(history)
    return '1m' if key == 'minutes' else None


def check_day(day, payload, root):
    """Everything wrong with one published day, as a list of plain sentences."""
    faults = []
    if payload.get('date') != day:
        faults.append(f'payload is dated {payload.get("date")}, not {day}')

    chart = payload.get('lineChart') or {}
    if not chart:
        faults.append('no chart data; the entry exists without a drawing')
        return faults

    drawing = root / (chart.get('url') or '').lstrip('/')
    if not chart.get('url') or not drawing.is_file():
        faults.append(f'chart image missing: {chart.get("url")}')

    data_url = chart.get('dataUrl') or ''
    data = root / data_url.lstrip('/')
    if not data_url or not data.is_file():
        faults.append(f'supplied data missing: {data_url or "(none declared)"}')
        return faults

    history = json.loads(data.read_text(encoding='utf-8'))
    if history.get('date') != day:
        faults.append(f'supplied data is dated {history.get("date")}, not {day}')
    if history.get('symbol') and history['symbol'] != 'SPY':
        faults.append(f'supplied data is {history["symbol"]}, not SPY')
    if not source_hash(history):
        faults.append('supplied data names no source hash')

    key, points = series(history)
    if not points:
        faults.append('supplied data carries no observations')
    interval = resolution(history)
    described = ' '.join(str(chart.get(k) or '') for k in ('caption', 'gapShort', 'gapNote', 'alt'))
    if interval == '1h':
        if 'ourly' not in described:
            faults.append('hourly bars are not described as hourly')
        if 'not a minute path' not in described:
            faults.append('hourly bars do not disclaim being a minute path')
    if interval == '1m' and points and len(points) < 380:
        faults.append(f'minute session carries only {len(points)} points')

    performance = payload.get('performance') or {}
    if performance.get('executionSections'):
        faults.append('carries execution sections that no owner review produced')
    if performance.get('executionAssessedAt'):
        faults.append('carries an execution assessment timestamp')
    if performance.get('setupRating') is not None:
        faults.append('carries a setup rating')
    label = (performance.get('execution') or {}).get('label')
    if label != UNREVIEWED:
        faults.append(f'execution label reads {label!r} rather than {UNREVIEWED!r}')
    return faults


def audit(root=ROOT, archive=None):
    index = json.loads((root / 'content/journal-index.json').read_text(encoding='utf-8'))
    published, faults = {}, {}
    for entry in index['days']:
        day = entry['date']
        path = root / f'content/days/{day}.json'
        if not path.is_file():
            faults[day] = ['listed in the index with no day payload']
            continue
        payload = json.loads(path.read_text(encoding='utf-8'))
        published[day] = payload
        problems = check_day(day, payload, root)
        if problems:
            faults[day] = problems

    # Dates the archive knows about that never reached the site, split by cause.
    known, drawable = {}, set()
    for summary in sorted((archive or Path('.')).glob('_reconciliation/*.json')) if archive else []:
        month = json.loads(summary.read_text(encoding='utf-8'))
        for day in month.get('tradingDates', []):
            known[day] = month['month']
        drawable.update(month.get('chartEligibleDates', []))

    unpublished = sorted(set(known) - set(published))
    return dict(
        publishedDays=sorted(published),
        publishedCount=len(published),
        faults=faults,
        months=index.get('months', []),
        tradingDatesKnownToArchive=len(known),
        unpublishedTradingDates=unpublished,
        unpublishedWithData=sorted(d for d in unpublished if d in drawable),
        unpublishedWithoutData=sorted(d for d in unpublished if d not in drawable),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--archive', type=Path, default=Path(r'C:\MaloSound\Sessions\market-journal'))
    args = parser.parse_args(argv)
    result = audit(args.root, args.archive)

    print(f'{result["publishedCount"]} published days across {len(result["months"])} months: '
          f'{", ".join(result["months"])}')
    print(f'{result["tradingDatesKnownToArchive"]} trading dates known to the private archive.')
    print(f'{len(result["unpublishedWithData"])} have chart data and are not published.')
    print(f'{len(result["unpublishedWithoutData"])} have no chart data, so nothing can be drawn.')
    if result['faults']:
        print(f'\n{len(result["faults"])} days with problems:')
        for day in sorted(result['faults']):
            for line in result['faults'][day]:
                print(f'  {day}: {line}')
        return 1
    print('\nEvery published day draws its own date from supplied data, states its '
          'resolution honestly, and reports execution as unreviewed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
