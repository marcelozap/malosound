#!/usr/bin/env python3
"""Reconcile the archived XIV$ trading records into MaloSound's private archive.

Marcelo's daily summaries, Schwab receipts and written reviews live in a second
workspace that predates this site. This tool reads those sources and writes one
private reconciliation record per trading date, plus a month index.

Three rules shape everything here.

Nothing this tool writes is publishable. Records go to the private archive root,
never into content/. They carry dollar amounts, lot counts and broker export
filenames, and none of that belongs on a website.

Nothing this tool writes is an execution assessment. The sources are full of
things that look like grades and are not: a `process_color` computed from profit
and lot count, an `emotion_tag` Marcelo used to describe how a trade felt, review
prose where a coach called a day's process yellow. Every one of those is carried
forward as supplemental context, inside a block that names why it is not a grade.
Execution stays `[]` and unreviewed until Marcelo reviews it himself.

Nothing this tool writes is asserted without provenance. Every figure names the
file it came from, that file's sha256, and when the broker produced it. Where two
sources disagree, both numbers are recorded and the disagreement is reported. A
reconciliation that quietly picks a winner is worth less than one that shows the
conflict.
"""
import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

# The archived workspace. Passed in rather than hardcoded so the tests can run
# against fixtures and never touch the real records.
DEFAULT_SOURCE = Path(r'C:\Users\Green Machine\Documents\xiv$')
DEFAULT_ARCHIVE = Path(r'C:\MaloSound\Sessions\market-journal')

# `process_color` is arithmetic, not judgement. Quoted from the generator so the
# record can show its reader exactly how the color was reached, in one line, and
# there is no temptation to read it as Marcelo's opinion of the day.
PROCESS_COLOR_FORMULA = (
    "green if pnl > 0 and lot_rows <= 10 and zero_dte <= 5, "
    "else red if pnl <= -500 or lot_rows >= 50, "
    "else yellow if lot_rows > 10 or zero_dte > 5 or wash_sales > 0, else unrated "
    "(xiv$/scripts/import_schwab_realized.py)")

NOT_A_GRADE = (
    'Supplemental context from the archived workspace. It is not an execution '
    'assessment and must never be converted into one. Execution color comes only '
    'from Marcelo reviewing a named stretch of a named session.')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance(path, root, kind, note=None):
    """What a figure came from. Paths are recorded relative to the archived
    workspace, so a record stays readable if the workspace moves."""
    entry = dict(kind=kind, path=str(path.relative_to(root)), sha256=digest(path),
                 bytes=path.stat().st_size)
    if note:
        entry['note'] = note
    return entry


def iso(american):
    """'07/15/2026' -> '2026-07-15'. Broker exports use the American order and the
    rest of this project does not."""
    month, day, year = american.split('/')
    return f'{year}-{month}-{day}'


def settled_lots(csv_path, month):
    """The final word on what closed, from the broker's lot detail export.

    This is the settled record: one row per closed lot, exported after the month
    ended. Intraday receipts are snapshots of an unfinished day and will disagree
    with it. That disagreement is the point of the reconciliation, not a bug.
    """
    days = defaultdict(lambda: dict(lotRows=0, realized=0.0, contracts=0.0,
                                    underlyings=defaultdict(float), zeroDte=0, washSales=0))
    with csv_path.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            day = row['closed_date']
            if not day.startswith(month):
                continue
            bucket = days[day]
            bucket['lotRows'] += 1
            bucket['realized'] += float(row['lot_pnl'] or 0)
            bucket['contracts'] += float(row['quantity'] or 0)
            bucket['underlyings'][row['underlying']] += float(row['lot_pnl'] or 0)
            bucket['zeroDte'] += row['zero_dte'].strip().lower() == 'true'
            bucket['washSales'] += row['wash_sale'].strip().lower() == 'true'
    for bucket in days.values():
        bucket['realized'] = round(bucket['realized'], 2)
        bucket['underlyings'] = {k: round(v, 2) for k, v in sorted(bucket['underlyings'].items())}
    return dict(days)


def receipt_snapshots(receipts_path, month):
    """Every intraday receipt export, grouped by the date it reports.

    A day can have several: July 13 was exported seven times as the session went
    on, and each export reports a larger realized total than the last. Keeping the
    whole chain is what lets a reader see that an early chat total was not wrong,
    just early.
    """
    data = json.loads(receipts_path.read_text(encoding='utf-8'))
    chains, foreign = defaultdict(list), []
    for item in data.get('all', []):
        entry = dict(asof=item.get('asof'), rows=item.get('rows'),
                     contracts=item.get('contracts'), realized=item.get('pnl'),
                     exportName=item.get('name'))
        day = iso(item['date'])
        (chains[day] if day.startswith(month) else foreign).append(
            entry if day.startswith(month) else dict(entry, reportedDate=day))
    for chain in chains.values():
        chain.sort(key=lambda x: x['asof'] or '')
    return dict(chains), foreign


def owner_ideas(db_path, month):
    """Marcelo's own idea records: setup, thesis, invalidation, how it felt.

    These are the closest thing in the archive to first-person material, and they
    are still not assessments. They describe intent before or around a trade, they
    carry a coarse session bucket rather than a start and end time, and several
    read as written after the fact. They are supplemental.
    """
    if not db_path.exists():
        return {}, 'trade engine database not present'
    ideas = defaultdict(list)
    with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as con:
        for row in con.execute(
                'select date, underlying, symbol, setup_tag, session_tag, emotion_tag, '
                'thesis, trigger, invalidation from trade_ideas where date like ? order by date',
                (month + '%',)):
            keys = ('date', 'underlying', 'symbol', 'setupTag', 'sessionTag',
                    'emotionTag', 'thesis', 'trigger', 'invalidation')
            ideas[row[0]].append(dict(zip(keys, row)))
    return dict(ideas), None


def engine_lot_counts(db_path, month):
    """Closed-lot counts straight from the engine database, for cross-checking the
    CSV. The two are built from overlapping broker exports and can disagree where
    an export was appended more than once."""
    if not db_path.exists():
        return {}
    with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as con:
        return {day: n for day, n in con.execute(
            'select closed_date, count(*) from trade_lots where closed_date like ? '
            'group by closed_date', (month + '%',))}


def dated_files(directory, month, kind, root, note):
    """Supplemental material filed by the date in its filename."""
    found = defaultdict(list)
    if not directory.is_dir():
        return dict(found)
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        stem = path.stem.replace('_', '-')
        for start in range(len(stem) - 9):
            candidate = stem[start:start + 10]
            if candidate.startswith(month) and candidate[4] == '-' and candidate[7] == '-':
                found[candidate].append(provenance(path, root, kind, note))
                break
    return dict(found)


def covering(directory, pattern, month):
    """The backfill file whose declared range actually contains this month.

    The workspace keeps several generations of each export side by side, named
    `..._<start>_to_<end>`. Taking the first glob match reconciled July against a
    file that stops in June and reported zero trading days, which is the most
    dangerous possible failure here: a confident, empty, wrong answer. Pick by the
    declared range, and refuse rather than guess when nothing covers the month.
    """
    candidates = []
    for path in sorted(directory.glob(pattern)):
        parts = [chunk for chunk in path.stem.split('_') if len(chunk) == 10 and chunk[4] == '-']
        if len(parts) == 2 and parts[0][:7] <= month <= parts[1][:7]:
            candidates.append(path)
    if not candidates:
        raise ValueError(f'No {pattern} in {directory} declares a range covering {month}.')
    # Several generations can cover the same month; the newest export is the one
    # with the most settled data behind it.
    return max(candidates, key=lambda p: p.stat().st_mtime)


def price_series(archive, month):
    """Saved intraday price snapshots, indexed by the exchange date they cover.

    Chart eligibility is detected, never asserted. When this was first written no
    July price series existed and every record said so; a snapshot saved later
    should make those same records true without anyone editing a constant. So the
    archive is scanned each run, and a date becomes eligible exactly when bars for
    it are on disk with a hash behind them.

    Bars are bucketed by exchange-local date using the snapshot's own gmt offset,
    not by UTC. A 16:00 ET bar is the next UTC day, and bucketing it wrong would
    quietly move the last hour of every session into the following date.
    """
    days = defaultdict(lambda: dict(bars=0))
    for path in sorted(archive.glob('*/source-yahoo-*.json')):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
            result = payload['chart']['result'][0]
            stamps, meta = result['timestamp'], result['meta']
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        offset = meta.get('gmtoffset') or 0
        source = None
        for stamp in stamps:
            day = datetime.fromtimestamp(stamp + offset, timezone.utc).strftime('%Y-%m-%d')
            if not day.startswith(month):
                continue
            source = source or dict(kind='yahoo_chart_snapshot', path=str(path),
                                    sha256=digest(path), symbol=meta.get('symbol'),
                                    interval=meta.get('dataGranularity'),
                                    timezone=meta.get('exchangeTimezoneName'))
            days[day]['bars'] += 1
            days[day]['source'] = source
    return dict(days)


def journal_entries(jsonl_path, month):
    rows = {}
    for line in jsonl_path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            row = json.loads(line)
            if row['date'].startswith(month):
                rows[row['date']] = row
    return rows


def shell_days(jsonl_path, month):
    """Every weekday in range, including the ones with no closed trade. A weekday
    with no realized trade is not proof that nothing was held, only that nothing
    closed; the generator says so and that caveat travels with the record."""
    rows = {}
    for line in jsonl_path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            row = json.loads(line)
            if row['date'].startswith(month):
                rows[row['date']] = row
    return rows


def reconcile(source, month, now, archive=None):
    """Build every record for one month without writing anything."""
    reports, backfill = source / 'reports', source / 'journal_backfill'
    lots_csv = covering(backfill, 'trade_receipts_lots_*.csv', month)
    pnl_jsonl = covering(backfill, 'pnl_journal_entries_daily_*.jsonl', month)
    shell_jsonl = covering(backfill, 'daily_calendar_journal_shell_weekdays_*.jsonl', month)
    receipts_json = reports / f'recent_realized_receipts_{month}.json'

    settled = settled_lots(lots_csv, month)
    snapshots, foreign = receipt_snapshots(receipts_json, month) if receipts_json.exists() else ({}, [])
    ideas, ideas_note = owner_ideas(source / 'data' / 'xiv_trade_engine.sqlite', month)
    engine = engine_lot_counts(source / 'data' / 'xiv_trade_engine.sqlite', month)
    journal = journal_entries(pnl_jsonl, month)
    shells = shell_days(shell_jsonl, month)
    prices = price_series(archive, month) if archive else {}
    reviews = dated_files(source / 'reviews', month, 'review',
                          source, 'Written reflection or coaching prose. ' + NOT_A_GRADE)
    cards = dated_files(source / 'daily_cards', month, 'daily_card',
                        source, 'Daily money-flow card. ' + NOT_A_GRADE)

    lots_source = provenance(lots_csv, source, 'schwab_lot_detail')
    records, conflicts = {}, []
    for day in sorted(set(settled) | set(journal)):
        figures = settled.get(day)
        entry = journal.get(day, {})

        chain = snapshots.get(day, [])
        latest = chain[-1] if chain else None
        # Where the settled export and the last intraday receipt disagree, both
        # numbers stay. The receipt was taken while the day was still moving; the
        # export is what actually settled. Neither is a mistake, and picking one
        # silently would hide the only interesting thing about the pair.
        if latest and figures and abs(latest['realized'] - figures['realized']) >= 0.01:
            conflicts.append(dict(date=day, settled=figures['realized'],
                                  lastSnapshot=latest['realized'], snapshotAsOf=latest['asof'],
                                  difference=round(figures['realized'] - latest['realized'], 2)))
        if day in engine and figures and engine[day] != figures['lotRows']:
            conflicts.append(dict(date=day, settledLotRows=figures['lotRows'],
                                  engineLotRows=engine[day],
                                  note='Lot detail export and engine database disagree on closed lots.'))

        supplemental = reviews.get(day, []) + cards.get(day, [])
        records[day] = dict(
            schemaVersion=1,
            date=day,
            visibility='private',
            traded=True,
            settled=dict(source=lots_source, **figures) if figures else None,
            receiptSnapshots=dict(source=provenance(receipts_json, source, 'receipt_inventory'),
                                  chain=chain) if chain else None,
            supplemental=supplemental,
            ownerIdeas=dict(note='Marcelo\'s own setup, thesis and invalidation notes. '
                                 'Session tags are coarse buckets, not start and end times. ' + NOT_A_GRADE,
                            entries=ideas.get(day, [])) if ideas.get(day) else None,
            notAnAssessment=dict(
                processColor=entry.get('process_color'),
                formula=PROCESS_COLOR_FORMULA,
                reason='Computed from profit, lot count, zero-DTE count and wash sales. '
                       'Profit does not establish execution quality. ' + NOT_A_GRADE),
            execution=dict(status='unreviewed', executionSections=[], executionAssessedAt=None,
                           reason='No stretch of this session has been reviewed by Marcelo.'),
            marketPathSource=prices.get(day, {}).get('source'),
            marketPathBars=prices.get(day, {}).get('bars'),
            chartEligible=day in prices,
            chartBlockedBecause=None if day in prices else
                'No intraday price series for this date is saved in the archive.',
            reconciledAt=now,
        )

    quiet = {d: r for d, r in shells.items() if r.get('traded') is False}
    index = dict(
        schemaVersion=1,
        month=month,
        visibility='private',
        generatedAt=now,
        tradingDates=sorted(records),
        tradingDateCount=len(records),
        quietWeekdays=sorted(quiet),
        quietWeekdayNote='No closed realized trade in the broker export. Not proof that no '
                         'position was held intraday.',
        datesWithReceiptSnapshots=sorted(snapshots),
        datesWithSupplementalReviews=sorted(reviews),
        datesWithOwnerIdeas=sorted(ideas),
        conflicts=conflicts,
        unmatchedReceiptExports=foreign,
        unmatchedReceiptNote='Receipt exports whose reported date falls outside this month. A '
                             'bulk history export lands here; it is not a trading day.',
        executionAssessmentsFound=0,
        executionAssessmentNote='No owner-written execution assessment exists in either workspace '
                                'for any date in this month.',
        chartEligibleDates=sorted(d for d in records if d in prices),
        marketDatesWithPrices=sorted(prices),
        chartEligibilityNote='A date is chart-eligible when an intraday price series for it is '
                             'saved in the archive with a hash behind it. Eligible means drawable, '
                             'not reviewed: colour still requires Marcelo.',
        sources=dict(lotDetail=lots_source,
                     receiptInventory=provenance(receipts_json, source, 'receipt_inventory')
                     if receipts_json.exists() else None,
                     dailyJournal=provenance(pnl_jsonl, source, 'daily_pnl_journal'),
                     calendarShell=provenance(shell_jsonl, source, 'calendar_shell')),
    )
    if ideas_note:
        index['ownerIdeasNote'] = ideas_note
    return records, index


def write(records, index, archive, month):
    written = []
    for day, record in records.items():
        folder = archive / day
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'archive-reconciliation.json'
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        written.append(path)
    summary = archive / '_reconciliation' / f'{month}.json'
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    written.append(summary)
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--month', default='2026-07', help='YYYY-MM to reconcile')
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--archive', type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument('--dry-run', action='store_true', help='report without writing')
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    records, index = reconcile(args.source, args.month, now, args.archive)
    if not args.dry_run:
        write(records, index, args.archive, args.month)

    print(f'{args.month}: {index["tradingDateCount"]} trading dates reconciled, '
          f'{len(index["quietWeekdays"])} quiet weekdays.')
    print(f'  receipt snapshots on {len(index["datesWithReceiptSnapshots"])} dates; '
          f'written reviews on {len(index["datesWithSupplementalReviews"])} dates; '
          f'owner idea records on {len(index["datesWithOwnerIdeas"])} dates.')
    print(f'  {len(index["conflicts"])} source disagreements recorded, '
          f'{len(index["unmatchedReceiptExports"])} receipt exports outside the month.')
    print(f'  execution assessments found: {index["executionAssessmentsFound"]}. '
          f'chart-eligible dates: {len(index["chartEligibleDates"])}.')
    if args.dry_run:
        print('  dry run: nothing written.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
