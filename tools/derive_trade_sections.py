#!/usr/bin/env python3
"""Turn timed broker fills into the entry-to-exit windows a chart can colour.

This is one trading record drawn from more than one broker. A source that
records execution times can produce a window; a source that only records
closing dates cannot, and its trades stay uncoloured rather than being guessed
at or borrowed from the other source's clock.

Three rules shape the output.

A window is one completed position, not one fill and not one day. A contract
opens a trip when it goes from flat to held and closes it when it returns to
flat, so scaling out over three fills is a single window from the first entry
to the last exit. A position still open at the last fill has no exit time and
is reported rather than drawn.

An outcome is that position's own realised result, computed from its own fills.
It is never the day's total and never the other account's total. Premiums here
exclude fees, so a trip whose gross result is small enough that fees could
plausibly flip its sign is reported for review instead of being trusted.

Amounts, contract detail and account identifiers belong to the private record.
The public sections carry only a start time, an end time, an outcome, the
underlying, and the kind of source they came from.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

# One option contract controls this many shares, so a premium difference is
# multiplied by it to reach the realised dollar result.
CONTRACT_MULTIPLIER = 100
# Below this gross result, ordinary per-contract fees could flip the sign, so
# the trip is surfaced for a human rather than silently coloured.
FEE_UNCERTAINTY = 5.00

DEFAULT_WALKTHROUGH = Path(r'C:\MaloSound\Workspace\2026-trade-walkthrough\walkthrough-data.json')
DEFAULT_PRIVATE_ROOT = Path(r'C:\MaloSound\Sessions\market-journal')


def load_fills(walkthrough, day):
    """The timed fills recorded for one date, or an empty list."""
    data = json.loads(Path(walkthrough).read_text(encoding='utf-8'))
    for row in data.get('days', []):
        if row.get('date') == day:
            return row.get('fills') or [], row
    return [], {}


def underlying_of(contract):
    """'SPY 756 call - Jun 03' -> 'SPY'."""
    return contract.split()[0] if contract else ''


def round_trips(fills):
    """Completed positions, in the order they were opened.

    Grouping is per contract, because two strikes held at the same time are two
    positions, not one. Within a contract the running quantity decides the
    boundaries: flat to held opens a trip, held back to flat closes it.
    """
    by_contract = defaultdict(list)
    for fill in fills:
        by_contract[fill['contract']].append(fill)

    trips = []
    for contract, rows in by_contract.items():
        rows = sorted(rows, key=lambda r: r['time'])
        position, current = 0, None
        for row in rows:
            if position == 0:
                current = dict(contract=contract, underlying=underlying_of(contract),
                               startTime=row['time'], endTime=None, fills=[])
            current['fills'].append(row)
            position += row['quantity'] if row['side'] == 'Buy' else -row['quantity']
            if position == 0:
                current['endTime'] = row['time']
                trips.append(current)
                current = None
        if current is not None:
            # Still held when the record ends. No exit time exists, so no window
            # can be drawn; it is reported instead.
            trips.append(current)
    return sorted(trips, key=lambda t: t['startTime'])


def realised(trip):
    """The trip's own gross result, in dollars, from its own fills."""
    total = 0.0
    for fill in trip['fills']:
        signed = fill['quantity'] * fill['price']
        total += signed if fill['side'] == 'Sell' else -signed
    return round(total * CONTRACT_MULTIPLIER, 2)


def outcome_of(value):
    return 'profit' if value > 0 else 'loss' if value < 0 else 'flat'


def derive(fills, source_kind='imported_result', underlying='SPY'):
    """Public sections plus the private detail behind them."""
    public, private, skipped = [], [], []
    for trip in round_trips(fills):
        value = realised(trip)
        detail = dict(contract=trip['contract'], underlying=trip['underlying'],
                      startTime=trip['startTime'], endTime=trip['endTime'],
                      grossRealized=value, outcome=outcome_of(value),
                      fillCount=len(trip['fills']),
                      feeSensitive=abs(value) < FEE_UNCERTAINTY)
        private.append(detail)
        if trip['endTime'] is None:
            skipped.append(dict(detail, reason='position still open at the last recorded fill'))
            continue
        if trip['underlying'] != underlying:
            skipped.append(dict(detail, reason=f'not {underlying}; it may not colour a {underlying} chart'))
            continue
        if detail['outcome'] == 'flat':
            skipped.append(dict(detail, reason='breakeven takes no colour'))
            continue
        public.append(dict(startTime=trip['startTime'], endTime=trip['endTime'],
                           outcome=detail['outcome'], underlying=trip['underlying'],
                           sourceKind=source_kind))
    return public, private, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True, help='the New York trading date, YYYY-MM-DD')
    parser.add_argument('--walkthrough', type=Path, default=DEFAULT_WALKTHROUGH)
    parser.add_argument('--private-root', type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument('--underlying', default='SPY')
    parser.add_argument('--write-private', action='store_true',
                        help='save the detailed record beside the session, outside Git')
    args = parser.parse_args(argv)

    fills, row = load_fills(args.walkthrough, args.date)
    if not fills:
        print(f'{args.date}: no timed fills in this source. Nothing can be drawn.')
        return 0

    public, private, skipped = derive(fills, underlying=args.underlying)
    listed, counted = len(fills), row.get('allFillCount')
    print(f'{args.date}: {listed} timed fills listed'
          + (f' of {counted} recorded that day' if counted else '')
          + f'; {len(private)} positions, {len(public)} drawable {args.underlying} windows.')
    for item in private:
        flag = ' FEE-SENSITIVE' if item['feeSensitive'] else ''
        print(f"   {item['startTime']}-{item['endTime'] or 'open'}  {item['contract']:28s}"
              f"  {item['outcome']:7s}{flag}")
    for item in skipped:
        print(f"   skipped {item['contract']}: {item['reason']}")
    print(json.dumps(public, indent=2))

    if args.write_private:
        target = Path(args.private_root) / args.date / 'trade-derivation.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(dict(
            date=args.date, visibility='private',
            note='Gross premium results, fees excluded. Amounts stay out of the public journal.',
            listedFills=listed, recordedFillCount=counted,
            positions=private, skipped=skipped, publicSections=public), indent=2) + '\n',
            encoding='utf-8')
        print('private record:', target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
