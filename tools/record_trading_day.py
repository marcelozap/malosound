"""Stage one owner-supplied final day result from a private normalized JSON file."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from trade_journal import validate

ROOT = Path(__file__).resolve().parents[1]


def normalize(raw, recorded_at=None):
    if raw.get('mode') != 'live' or raw.get('final') is not True:
        raise ValueError('Only an explicitly final live trading result can color the public journal.')
    source = raw.get('sourceKind', 'user_reported')
    outcome = raw.get('outcome')
    if raw.get('feesIncluded') is not True:
        raise ValueError('Confirm the final result is net of fees.')
    count = raw.get('tradeCount')
    if 'tradeCount' in raw and (type(count) is not int or count < 0):
        raise ValueError('Trade count must be a nonnegative integer.')
    if 'netRealizedPnl' in raw:
        if raw.get('feesIncluded') is not True:
            raise ValueError('Net realized P&L must include fees.')
        value = raw['netRealizedPnl']
        if isinstance(value, bool) or value is None:
            raise ValueError('Net realized P&L must be a finite decimal.')
        try:
            pnl = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError('Net realized P&L must be a finite decimal.') from exc
        if not pnl.is_finite():
            raise ValueError('Net realized P&L must be finite.')
        count = raw.get('tradeCount')
        if type(count) is not int or count < 0 or (count == 0 and pnl != 0):
            raise ValueError('Supply the completed trade count; no-trade days cannot carry realized P&L.')
        calculated = 'no_trade' if count == 0 else 'profit' if pnl > 0 else 'loss' if pnl < 0 else 'flat'
        if outcome is not None and outcome != calculated:
            raise ValueError('The stated outcome conflicts with net realized P&L.')
        outcome = calculated
    elif source != 'user_reported':
        raise ValueError('An imported result needs net realized P&L, fees confirmation and trade count.')
    elif count is not None and ((count == 0 and outcome != 'no_trade') or (count > 0 and outcome == 'no_trade')):
        raise ValueError('The reported outcome conflicts with the trade count.')
    # Allowlist deliberately discards amounts, fills, broker/account identifiers and source paths.
    # executionSections carry only clock times, a reviewed class and Marcelo's own words.
    row = dict(date=raw['date'], outcome=outcome, setupRating=raw.get('setupRating'),
               ratingAsOf=raw.get('ratingAsOf'), sourceKind=source,
               executionSections=raw.get('executionSections'),
               executionAssessedAt=raw.get('executionAssessedAt'),
               recordedAt=recorded_at or datetime.now(timezone.utc).isoformat(timespec='seconds'))
    if 'tradeSections' in raw:
        row['tradeSections'] = raw['tradeSections']
    # Sections are NOT filtered. A malformed or unexpected section is a mistake worth
    # seeing, and silently dropping one would publish a day whose colors are not the
    # ones that were supplied. validate() enforces the exact shape and rejects it.
    if row['executionSections'] is not None and not isinstance(row['executionSections'], list):
        raise ValueError('executionSections must be a list of reviewed spans, or absent.')
    validate({'schemaVersion': 2, 'days': [row]})
    return row


def published(ledger, day):
    """The row already published for one date, or None. Reads only; validates what it reads."""
    return validate(json.loads(ledger.read_text(encoding='utf-8'))).get(day)


def plan(row, ledger, replace=False):
    """Decide the whole ledger change without writing anything.

    Returns (changed, data). Every reason to refuse is raised here, so a caller
    can preflight a write that touches more than this one file and leave the
    disk untouched when the answer is no.
    """
    data = json.loads(ledger.read_text(encoding='utf-8'))
    days = validate(data)
    old = days.get(row['date'])
    if old:
        if all(old.get(k) == row[k] for k in row if k != 'recordedAt'):
            return False, data
        if not replace:
            raise ValueError('This day already has a different result. Review the correction before using --replace.')
    days[row['date']] = row
    data['days'] = sorted(days.values(), key=lambda x: x['date'])
    validate(data)
    return True, data


def commit(ledger, data):
    ledger.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def stage(source, ledger, replace=False):
    row = normalize(json.loads(source.read_text(encoding='utf-8')))
    changed, data = plan(row, ledger, replace)
    if changed:
        commit(ledger, data)
    return changed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--replace', action='store_true')
    args = p.parse_args()
    changed = stage(args.input, ROOT/'content/trading-journal.json', args.replace)
    print('Daily result staged; build and publish the journal.' if changed else 'Unchanged; original recording timestamp retained.')
