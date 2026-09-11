"""Public, time-bounded trade outcomes. Never infer timing or execution quality."""
import re
from trade_journal import session_minute

COLORS = {'profit': '#e5b657', 'loss': '#50b8f5', 'flat': '#81929e', 'unrecorded': '#81929e'}
LABELS = {'profit': 'Profitable trade', 'loss': 'Losing trade', 'flat': 'Breakeven trade', 'unrecorded': 'Outcome unknown'}
FIELDS = {'startTime', 'endTime', 'outcome', 'underlying', 'sourceKind'}


def minute(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{2}:\d{2}(?::[0-5]\d)?', value):
        raise ValueError('Trade times must be HH:MM or HH:MM:SS in New York time.')
    result = session_minute(value[:5]) + (int(value[6:]) / 60 if len(value) == 8 else 0)
    if not 0 <= result <= 390:
        raise ValueError('Trade overlay times must be within this regular session.')
    return result


def validate(raw):
    if raw is None:
        return []
    # A tuple is accepted because every renderer defaults to an empty one; a
    # string or mapping is still refused, which is what this guard is for.
    if not isinstance(raw, (list, tuple)):
        raise ValueError('tradeSections must be a list.')
    out = []
    for row in raw:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError('Trade sections accept only startTime, endTime, outcome, underlying, sourceKind.')
        if row['underlying'] != 'SPY':
            raise ValueError('Only SPY-underlying trades may color a SPY chart.')
        if row['outcome'] not in COLORS or row['sourceKind'] not in ('user_reported', 'imported_result'):
            raise ValueError('Supply an explicit trade outcome and source kind.')
        if minute(row['startTime']) >= minute(row['endTime']):
            raise ValueError('A trade must exit after entry; do not guess overnight or partial-fill spans.')
        out.append(dict(row))
    return sorted(out, key=lambda row: minute(row['startTime']))


COVERAGE_KEYS = {'timed', 'untimed'}
# A source is a broker name. Digits are refused so an account number cannot
# arrive here by habit or by a copied fixture; identifiers stay private.
SOURCE_NAME = re.compile(r'[A-Za-z][A-Za-z ]{1,19}')


def validate_coverage(raw):
    """Which sources supplied timed trades for a day, and which could not.

    This is one trading record drawn from more than one broker, so a source
    that cannot supply execution times leaves the record incomplete rather
    than making the day a different day.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict) or not raw or set(raw) - COVERAGE_KEYS:
        raise ValueError('tradeCoverage accepts only timed and untimed source lists.')
    out = {}
    for key in ('timed', 'untimed'):
        names = raw.get(key)
        if names is None:
            continue
        if not isinstance(names, (list, tuple)) or not names:
            raise ValueError(f'tradeCoverage {key} must be a non-empty list of source names.')
        for name in names:
            if not isinstance(name, str) or not SOURCE_NAME.fullmatch(name):
                raise ValueError('A trade source is a broker name without digits; '
                                 'account identifiers stay in the private record.')
        out[key] = list(names)
    if not out:
        raise ValueError('tradeCoverage must name at least one source.')
    return out


def coverage_note(coverage):
    """The sentence that keeps an uncoloured stretch from reading as idle."""
    if not coverage:
        return ''
    timed, untimed = coverage.get('timed') or [], coverage.get('untimed') or []
    if not untimed:
        return ''
    parts = []
    if timed:
        parts.append(', '.join(timed) + ' timed trades')
    parts.append(', '.join(untimed) + ' timing unavailable')
    return (' Partial coverage: ' + '; '.join(parts) + '. Uncoloured time means this record is '
            'incomplete there, not that no trading happened.')


def intervals(sections):
    spans = [(minute(s['startTime']), minute(s['endTime']), s['outcome']) for s in validate(sections)]
    edges = sorted({0, 390} | {t for a, b, _ in spans for t in (a, b)})
    result = []
    for a, b in zip(edges, edges[1:]):
        outcomes = {o for start, end, o in spans if start <= a and b <= end}
        outcome = next(iter(outcomes)) if len(outcomes) == 1 else 'unrecorded'
        result.append((a, b, outcome))
    return result


def note(sections, resolution=None, coverage=None):
    """One sentence explaining what the line's color does, or why it does nothing.

    The empty case says which piece of evidence is absent rather than repeating
    one flat sentence on every date. A colored span needs three things at once —
    an entry time, an exit time, and a settled outcome — and an hourly session
    has a fourth problem on top, so the two cases read differently.
    """
    if not sections:
        missing = ('No trade outcome is drawn on this line. Coloring a span needs all three of an entry '
                   'time, an exit time, and a settled outcome from the broker record; where any one is '
                   'missing, or where two sources disagree about the same trade, the span stays neutral. '
                   'Neutral never means no trades occurred.')
        if resolution == 'hourly':
            missing += (' This session is drawn from hourly observations only, so it carries no '
                        'minute-level path for a trade window to sit on.')
        return missing + coverage_note(coverage)
    return ('Gold marks profitable trades and blue losing trades, only between supplied entry and exit times. '
            'Color shows the completed trade outcome, not running profit, price direction, or execution quality. '
            'Breakeven, unknown outcomes, conflicting overlapping trades, and time outside supplied trades stay neutral. '
            'Boundaries clip the displayed line; they do not add price observations.'
            + coverage_note(coverage))
