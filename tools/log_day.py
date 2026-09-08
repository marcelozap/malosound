"""Log one trading day after the close: one command, private by default.

    python tools/log_day.py --date 2026-09-04 --outcome profit --setup 9 \
        --sat-out   09:30 09:48 "Waited for the range to set." \
        --played    09:48 09:52 "Took the open cleanly." \
        --misplayed 12:38 12:48 "Chased the second push."

Each flag names one stretch: START END, both HH:MM in New York time, plus an
optional note in your own words. Repeat a flag for more stretches.

**Those notes are private.** They go in the private record and stop there. The
site shows the colored stretch and nothing else, unless you say otherwise for
one stretch at a time:

    --public-note 09:48 09:52 "Took the open cleanly."

The start and end must match a stretch you already named. Public text is capped
short and refused if it carries an amount, an identifier or position detail.

    python tools/log_day.py --date 2026-09-04 --show
    python tools/log_day.py --date 2026-09-04 --outcome loss --replace

What it writes, and where:

* A PRIVATE record under `C:\\MaloSound\\Sessions\\market-journal\\<date>\\`,
  outside Git. Amounts, counts, broker notes, your stretch notes and anything
  passed with `--private-note` live only here.
* A PUBLIC summary appended to `content/trading-journal.json` through the same
  allowlist `record_trading_day.py` uses: date, outcome, setup rating, the
  reviewed spans, their timestamps, and any text you explicitly published.

Rules this command will not bend:

* Nothing is written until both records validate. A refused command leaves the
  private file and the public ledger exactly as they were.
* Running the same command twice changes nothing, and keeps the original
  timestamps and private notes rather than restamping them with the second run.
* Execution is reviewed after the close. `--assessed` defaults to now and is
  refused if it lands before that day's 16:00 ET.
* Nothing is graded for you. A stretch you do not name stays neutral, and no
  grade is ever derived from whether the day made money.
* `--setup` is the 1-14 opportunity rating and is independent of both.

Run the website build afterwards to redraw the line.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from record_trading_day import commit, normalize, plan, published
from trade_journal import EXECUTION, execution_summary

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = Path(r'C:\MaloSound\Sessions\market-journal')
ET = ZoneInfo('America/New_York')


def now_et():
    return datetime.now(timezone.utc).astimezone(ET).isoformat(timespec='seconds')


def spans(args):
    """Every named stretch, ordered, each carrying its private note."""
    out = []
    for values, execution in ((args.played, 'good'), (args.misplayed, 'misplayed'), (args.sat_out, 'sat_out')):
        for item in values:
            if len(item) < 2:
                raise SystemExit(f'A stretch needs START and END: --{execution} 09:48 09:52 "your note"')
            start, end, *rest = item
            out.append(dict(startTime=start, endTime=end, execution=execution,
                            note=rest[0] if rest else None, publicNote=None))
    out.sort(key=lambda s: s['startTime'])
    for start, end, text in args.public_note:
        match = [s for s in out if s['startTime'] == start and s['endTime'] == end]
        if not match:
            raise SystemExit(f'--public-note {start} {end} matches no stretch you named. '
                             'Publish text only for a stretch that exists.')
        if len(match) > 1:
            raise SystemExit(f'--public-note {start} {end} is ambiguous; two stretches share those times.')
        match[0]['publicNote'] = text
    return out


def public_sections(sections):
    """Only explicitly published text crosses over. The private note does not."""
    return [dict(startTime=s['startTime'], endTime=s['endTime'], execution=s['execution'],
                 **({'publicNote': s['publicNote']} if s['publicNote'] else {}))
            for s in sections]


def build(args, sections, old_public, old_private):
    """The public row and the private record, carrying unchanged timestamps forward."""
    assessed = args.assessed
    if sections and not assessed:
        # An unchanged assessment keeps the time it was actually made, so re-running
        # the same command does not restamp a review that only happened once.
        same = bool(old_public) and old_public['executionSections'] == public_sections(sections)
        assessed = old_public['executionAssessedAt'] if same else now_et()
    if sections:
        close = datetime.combine(datetime.strptime(args.date, '%Y-%m-%d').date(), time(16, 0), ET)
        if datetime.fromisoformat(assessed.replace('Z', '+00:00')) < close:
            raise SystemExit(f'Review after the close. {args.date} closes at {close.isoformat()}.')
    rated_at = args.rated_at
    if args.setup and not rated_at:
        same = bool(old_public) and old_public['setupRating'] == args.setup
        rated_at = old_public['ratingAsOf'] if same else (assessed or now_et())
    record = dict(date=args.date, mode='live', final=True, feesIncluded=True,
                  outcome=args.outcome, sourceKind='user_reported',
                  setupRating=args.setup, ratingAsOf=rated_at if args.setup else None,
                  executionSections=public_sections(sections) or None,
                  executionAssessedAt=assessed if sections else None)
    notes = args.private_note
    if not notes and old_private:
        notes = old_private.get('privateNotes', [])
    private = dict(date=args.date, outcome=args.outcome, setupRating=args.setup,
                   ratingAsOf=rated_at if args.setup else None,
                   executionAssessedAt=assessed if sections else None,
                   sections=sections, privateNotes=notes,
                   note='Private. Amounts, accounts, raw exports and stretch notes belong '
                        'here, never in the public ledger.')
    return record, private


def read_private(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return None


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--date', required=True, help='the New York trading date, YYYY-MM-DD')
    p.add_argument('--outcome', choices=['profit', 'loss', 'flat', 'no_trade'],
                   help='your own net result after fees; a label only, it does not color the line')
    p.add_argument('--setup', type=int, help='opportunity quality 1-14, independent of result and execution')
    p.add_argument('--rated-at', help='when you assessed the setup; defaults to the execution review time')
    p.add_argument('--played', nargs='+', action='append', default=[], metavar=('START END', 'NOTE'),
                   help='a stretch you played well: START END [NOTE]; the note stays private')
    p.add_argument('--misplayed', nargs='+', action='append', default=[], metavar=('START END', 'NOTE'),
                   help='a stretch you misplayed: START END [NOTE]; the note stays private')
    p.add_argument('--sat-out', nargs='+', action='append', default=[], metavar=('START END', 'NOTE'),
                   help='a stretch you deliberately sat out: START END [NOTE]; the note stays private')
    p.add_argument('--public-note', nargs=3, action='append', default=[], metavar=('START', 'END', 'TEXT'),
                   help='publish this text for a stretch you named: START END TEXT')
    p.add_argument('--assessed', help='when you reviewed execution; defaults to now, must be after the close')
    p.add_argument('--private-note', action='append', default=[], help='stays in the private record only')
    p.add_argument('--replace', action='store_true', help='correct a day already published')
    p.add_argument('--show', action='store_true', help='print what is public and private for this date, change nothing')
    return p


def main(argv=None, root=None, private_root=None):
    p = parser()
    args = p.parse_args(argv)

    base = Path(root) if root else ROOT
    private_path = (Path(private_root) if private_root else PRIVATE_ROOT) / args.date / 'day-review.json'
    ledger = base / 'content/trading-journal.json'

    if args.show:
        row = published(ledger, args.date)
        print(f'PUBLIC  {ledger}')
        print(json.dumps(row, indent=2) if row else '  (nothing published for this date)')
        print(f'\nPRIVATE {private_path}')
        print('  exists' if private_path.exists() else '  (no private record yet)')
        return 0

    if not args.outcome:
        p.error('--outcome is required unless you are using --show')

    # Preflight. Everything that can refuse, refuses here, before a byte is written.
    old_private = read_private(private_path)
    record, private = build(args, spans(args), published(ledger, args.date), old_private)
    row = normalize(dict(record), None)
    changed, data = plan(row, ledger, args.replace)

    stored = dict(old_private or {})
    logged_at = stored.pop('loggedAt', None)
    kept = stored == private and logged_at is not None
    if not kept:
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_text(json.dumps(dict(private, loggedAt=datetime.now(timezone.utc).isoformat(timespec='seconds')),
                                           indent=2) + '\n', encoding='utf-8')
    if changed:
        commit(ledger, data)

    print(f'private  {private_path}  ({"unchanged, original time kept" if kept else "written"})')
    print(f'public   {ledger}  ({"updated" if changed else "unchanged, original timestamp kept"})')
    print(f'result   {row["outcome"]}   setup {row["setupRating"] if row["setupRating"] else "not rated"}   '
          f'{execution_summary(row["executionSections"] or [])["label"]}')
    for item in row['executionSections'] or []:
        print(f'         {item["startTime"]}-{item["endTime"]} {EXECUTION[item["execution"]][0]}'
              + (f' · published: {item["publicNote"]}' if item['publicNote'] else '  (no public text)'))
    print('\nNext: python -X utf8 tools/build_website.py')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
