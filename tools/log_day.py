"""Log one trading day after the close: one command, private by default.

    python tools/log_day.py --date 2026-09-04 --outcome profit --setup 9 \
        --sat-out   09:30 09:48 "Waited for the range to set." \
        --played    09:48 09:52 "Took the open cleanly." \
        --misplayed 12:38 12:48 "Chased the second push."

Each flag names one stretch: START END, both HH:MM in New York time, plus an
optional note in your own words. Repeat a flag for more stretches.

    python tools/log_day.py --date 2026-09-04 --show
    python tools/log_day.py --date 2026-09-04 --outcome loss --replace

What it writes, and where:

* A PRIVATE record under `C:\\MaloSound\\Sessions\\market-journal\\<date>\\`,
  outside Git. Amounts, counts, broker notes and anything you pass with
  `--private-note` live only here.
* A PUBLIC summary appended to `content/trading-journal.json` through the same
  allowlist `record_trading_day.py` uses: date, outcome, setup rating, the
  reviewed execution spans and their timestamps. Nothing else crosses over.

Rules this command will not bend:

* Execution is reviewed after the close. `--assessed` defaults to now and is
  refused if it lands before that day's 16:00 ET.
* Nothing is graded for you. A stretch you do not name stays neutral, and no
  grade is ever derived from whether the day made money.
* `--setup` is the 1-14 opportunity rating and is independent of both.
* Amounts stay out of public notes; the validator rejects them.

Run the website build afterwards to redraw the line.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from record_trading_day import normalize, stage
from trade_journal import EXECUTION, execution_summary

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = Path(r'C:\MaloSound\Sessions\market-journal')
ET = ZoneInfo('America/New_York')


def section(values, execution):
    start, end, *rest = values
    note = rest[0] if rest else None
    item = dict(startTime=start, endTime=end, execution=execution)
    if note:
        item['note'] = note
    return item


def build(args):
    sections = ([section(v, 'good') for v in args.played]
                + [section(v, 'misplayed') for v in args.misplayed]
                + [section(v, 'sat_out') for v in args.sat_out])
    sections.sort(key=lambda s: s['startTime'])
    assessed = args.assessed
    if sections and not assessed:
        assessed = datetime.now(timezone.utc).astimezone(ET).isoformat(timespec='seconds')
    if sections:
        close = datetime.combine(datetime.strptime(args.date, '%Y-%m-%d').date(), time(16, 0), ET)
        if datetime.fromisoformat(assessed.replace('Z', '+00:00')) < close:
            raise SystemExit(f'Review after the close. {args.date} closes at {close.isoformat()}.')
    record = dict(date=args.date, mode='live', final=True, feesIncluded=True,
                  outcome=args.outcome, sourceKind='user_reported',
                  setupRating=args.setup, ratingAsOf=args.rated_at if args.setup else None,
                  executionSections=sections or None,
                  executionAssessedAt=assessed if sections else None)
    if args.setup and not record['ratingAsOf']:
        record['ratingAsOf'] = assessed or datetime.now(timezone.utc).astimezone(ET).isoformat(timespec='seconds')
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--date', required=True, help='the New York trading date, YYYY-MM-DD')
    p.add_argument('--outcome', choices=['profit', 'loss', 'flat', 'no_trade'],
                   help='your own net result after fees; a label only, it does not color the line')
    p.add_argument('--setup', type=int, help='opportunity quality 1-14, independent of result and execution')
    p.add_argument('--rated-at', help='when you assessed the setup; defaults to the execution review time')
    p.add_argument('--played', nargs='+', action='append', default=[], metavar=('START END', 'NOTE'),
                   help='a stretch you played well: START END [NOTE], times HH:MM ET')
    p.add_argument('--misplayed', nargs='+', action='append', default=[], metavar=('START END', 'NOTE'),
                   help='a stretch you misplayed: START END [NOTE]')
    p.add_argument('--sat-out', nargs='+', action='append', default=[], metavar=('START END', 'NOTE'),
                   help='a stretch you deliberately sat out: START END [NOTE]')
    p.add_argument('--assessed', help='when you reviewed execution; defaults to now, must be after the close')
    p.add_argument('--private-note', action='append', default=[], help='stays in the private record only')
    p.add_argument('--replace', action='store_true', help='correct a day already published')
    p.add_argument('--show', action='store_true', help='print what is public and private for this date, change nothing')
    args = p.parse_args()

    private_dir = PRIVATE_ROOT / args.date
    private_path = private_dir / 'day-review.json'
    ledger = ROOT / 'content/trading-journal.json'

    if args.show:
        published = json.loads(ledger.read_text(encoding='utf-8'))
        row = next((d for d in published['days'] if d['date'] == args.date), None)
        print(f'PUBLIC  {ledger}')
        print(json.dumps(row, indent=2) if row else '  (nothing published for this date)')
        print(f'\nPRIVATE {private_path}')
        print('  exists' if private_path.exists() else '  (no private record yet)')
        return 0

    if not args.outcome:
        p.error('--outcome is required unless you are using --show')

    record = build(args)
    row = normalize(dict(record), None)          # validates before anything is written

    private_dir.mkdir(parents=True, exist_ok=True)
    private = dict(record, privateNotes=args.private_note,
                   loggedAt=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                   note='Private. Amounts, accounts and raw exports belong here, never in the public ledger.')
    private_path.write_text(json.dumps(private, indent=2) + '\n', encoding='utf-8')

    changed = stage_record(record, ledger, args.replace)
    summary = execution_summary(row['executionSections'] or [])
    print(f'private  {private_path}')
    print(f'public   {ledger}  ({"updated" if changed else "unchanged, original timestamp kept"})')
    print(f'result   {row["outcome"]}   setup {row["setupRating"] if row["setupRating"] else "not rated"}   {summary["label"]}')
    for item in row['executionSections'] or []:
        print(f'         {item["startTime"]}-{item["endTime"]} {EXECUTION[item["execution"]][0]}'
              + (f' · {item["note"]}' if item['note'] else ''))
    print('\nNext: python -X utf8 tools/build_website.py')
    return 0


def stage_record(record, ledger, replace):
    """Reuse the audited staging path by handing it a temporary private file."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / 'day.json'
        source.write_text(json.dumps(record), encoding='utf-8')
        return stage(source, ledger, replace)


if __name__ == '__main__':
    raise SystemExit(main())
