"""Minimal public day results; private fills, amounts and accounts never belong here.

Two separate judgements live here and must never be derived from each other:

* `outcome` is the day's net realized result. It is a text label only. It no
  longer colors the price line, because a profitable day can be badly played
  and a losing day can be played well.
* `executionSections` are Marcelo's own reviewed judgements about how he played
  named stretches of the session. Only he supplies them, with the timestamp of
  the assessment. Anything he has not reviewed stays neutral.

`setupRating` (1-14) is a third, independent axis: how good the opportunity was,
not how it was played and not what it paid.
"""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
import re

RESULTS = {
    'profit': ('Profit', '+', '#58dfa4'),
    'loss': ('Loss', '−', '#ff7188'),
    'flat': ('Flat', '=', '#b8c5d0'),
    'no_trade': ('No trade', '○', '#81929e'),
    'unrecorded': ('Unrecorded', '—', '#81929e'),
}
# Execution classes and the colors that carry them on the price line.
# Blue is the resting brand color for "not reviewed"; gold marks a stretch he
# deliberately sat out. Green and red are reviewed judgements, never inferred.
EXECUTION = {
    'good': ('Played well', '#58dfa4'),
    'misplayed': ('Misplayed', '#ff7188'),
    'sat_out': ('Sat out', '#e5b657'),
    'unreviewed': ('Not reviewed', '#50b8f5'),
}
NEUTRAL_EXECUTION = 'unreviewed'
FIELDS = {'date', 'outcome', 'setupRating', 'recordedAt', 'ratingAsOf', 'sourceKind',
          'executionSections', 'executionAssessedAt'}
SECTION_FIELDS = {'startTime', 'endTime', 'execution'}
# `publicNote` is the ONLY text that may be published, and only when Marcelo
# explicitly designates it. A plain note stays in the private record and never
# reaches this schema; `note` is refused here so it cannot arrive by habit.
SECTION_OPTIONAL = {'publicNote'}
SESSION_OPEN, SESSION_CLOSE = 570, 960          # 09:30 and 16:00, minutes from midnight ET
CLOCK = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
# Public text is kept deliberately small, and this guard is the last line rather
# than the first. The first line is that nothing is published unless Marcelo
# designates it; a pattern can never prove a sentence is safe to publish. What it
# can do is refuse the shapes that carry money, identity or position size, so a
# slip does not quietly become a publication. Clock times and small counts still
# pass, which is all a short execution remark needs.
PUBLIC_NOTE_MAX = 140
UNSAFE_PUBLIC = re.compile(
    r'[$€£¥@]'                                           # currency marks and '@'
    r'|\d{3,}'                                           # amounts, account and order ids
    r'|\d+\.\d'                                          # 1.46: a price or an amount
    r'|\d+(\.\d+)?\s*[km]\b'                             # 3k, 1.2m: money in shorthand
    r'|\b(dollars?|usd|eur|gbp|account|acct|order\s*id'  # named money and identifiers
    r'|contracts?|shares?|calls?|puts?|strikes?)\b',     # position detail stays private
    re.IGNORECASE)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('A timestamp with a timezone is required.')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() is None:
        raise ValueError('A timestamp with a timezone is required.')
    return parsed


def minute_of_day(value):
    """'09:48' -> 588. Raises unless it is a real clock time inside the session."""
    match = CLOCK.match(value) if isinstance(value, str) else None
    if not match:
        raise ValueError('Execution section times must be 24-hour HH:MM in New York time.')
    total = int(match.group(1)) * 60 + int(match.group(2))
    if not SESSION_OPEN <= total <= SESSION_CLOSE:
        raise ValueError('Execution section times must fall inside the 09:30-16:00 session.')
    return total


def session_minute(value):
    """Clock time -> minutes after the 09:30 open, which is the chart's x axis."""
    return minute_of_day(value) - SESSION_OPEN


def validate_sections(raw, assessed_at):
    """Ordered, non-overlapping, reviewed-only. Returns [] when nothing was reviewed."""
    if raw is None:
        if assessed_at is not None:
            raise ValueError('An execution assessment time needs the reviewed sections it belongs to.')
        return []
    if not isinstance(raw, list) or not raw:
        raise ValueError('executionSections must be a non-empty list, or null when nothing was reviewed.')
    if assessed_at is None:
        raise ValueError('Reviewed execution needs the actual time Marcelo assessed it.')
    timestamp(assessed_at)
    out, previous_end = [], None
    for item in raw:
        if not isinstance(item, dict) or not SECTION_FIELDS <= set(item) or set(item) - SECTION_FIELDS - SECTION_OPTIONAL:
            raise ValueError('Each execution section needs exactly startTime, endTime and execution, plus an optional publicNote. A plain "note" is refused: ordinary remarks stay in the private record.')
        start, end = minute_of_day(item['startTime']), minute_of_day(item['endTime'])
        if start >= end:
            raise ValueError('An execution section must end after it starts.')
        if previous_end is not None and start < previous_end:
            raise ValueError('Execution sections must be ordered and must not overlap.')
        if item['execution'] not in EXECUTION or item['execution'] == NEUTRAL_EXECUTION:
            raise ValueError('Execution must be good, misplayed or sat_out; unreviewed is the default, not a choice.')
        note = item.get('publicNote')
        if note is not None:
            if not isinstance(note, str) or not note.strip():
                raise ValueError('A public note must be non-empty text, or absent.')
            if len(note) > PUBLIC_NOTE_MAX:
                raise ValueError(f'Keep a public note under {PUBLIC_NOTE_MAX} characters.')
            found = UNSAFE_PUBLIC.search(note)
            if found:
                raise ValueError(f'Public notes stay minimal; {found.group(0)!r} looks like an amount or identifier. Keep it in the private record.')
        previous_end = end
        out.append(dict(startTime=item['startTime'], endTime=item['endTime'],
                        execution=item['execution'], publicNote=note))
    return out


def validate(data):
    if set(data) != {'schemaVersion', 'days'} or type(data['schemaVersion']) is not int or data['schemaVersion'] != 2 or not isinstance(data['days'], list):
        raise ValueError('Invalid public trading journal.')
    days = {}
    for row in data['days']:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError('Publish only the approved daily summary fields; no private trade data.')
        day = row['date']
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day or day in days:
            raise ValueError('Invalid or duplicate trading date.')
        if row['outcome'] not in RESULTS or row['outcome'] == 'unrecorded':
            raise ValueError('A recorded day needs an explicit outcome.')
        recorded = timestamp(row['recordedAt'])
        if date.fromisoformat(day) > recorded.astimezone(ZoneInfo('America/New_York')).date():
            raise ValueError('A completed result cannot be dated after its recording date in New York.')
        if row['sourceKind'] not in ('user_reported', 'imported_result'):
            raise ValueError('Unknown result source.')
        rating = row['setupRating']
        if rating is not None and (type(rating) is not int or not 1 <= rating <= 14):
            raise ValueError('Setup rating must be an integer from 1 to 14, or null.')
        if (rating is None) != (row['ratingAsOf'] is None):
            raise ValueError('A rating needs its actual assessment timestamp.')
        if rating is not None and timestamp(row['ratingAsOf']) > timestamp(row['recordedAt']):
            raise ValueError('Rating assessment cannot follow its recording time.')
        sections = validate_sections(row['executionSections'], row['executionAssessedAt'])
        # Store the normalized shape so every reader sees the same keys, including
        # an explicit note=None. Idempotent: re-validating a stored row is a no-op.
        row['executionSections'] = sections or None
        if sections:
            assessed = timestamp(row['executionAssessedAt'])
            session_close = datetime.combine(date.fromisoformat(day), time(16, 0), ZoneInfo('America/New_York'))
            if assessed < session_close:
                raise ValueError('Execution is reviewed after the close, not during the session.')
            if assessed > recorded:
                raise ValueError('Execution cannot be assessed after the row was recorded.')
        days[day] = row
    return days


def segments(points, gap_end_minutes, sections):
    """Split the exact observed points into runs of one execution class each.

    The geometry is never changed: every input point appears in the output in
    order, and a point where the class changes appears in both neighbouring runs
    so the drawn line stays continuous. Section boundaries land on whole minutes,
    which are exactly where the observed boundaries already are, so nothing is
    interpolated or invented.
    """
    spans = [(session_minute(s['startTime']), session_minute(s['endTime']), s['execution']) for s in sections]

    def classify(minute):
        for start, end, execution in spans:
            if start <= minute < end:
                return execution
        return NEUTRAL_EXECUTION

    runs = []
    for index, point in enumerate(points):
        previous = points[index - 1] if index else None
        # A run ends at a source gap, and at a change of execution class.
        broken = previous is not None and point['minute'] in gap_end_minutes
        # The stretch entering this point carries the class of the minute before it.
        entering = classify(point['minute'] - 1) if index else classify(point['minute'])
        if not runs or broken or runs[-1]['execution'] != entering:
            if runs and not broken and previous is not None:
                runs.append(dict(execution=entering, points=[previous, point]))
            else:
                runs.append(dict(execution=entering, points=[point]))
        else:
            runs[-1]['points'].append(point)
    return [run for run in runs if len(run['points']) > 1]


def execution_summary(sections):
    """One short, honest line for the calendar and index."""
    if not sections:
        return dict(reviewed=False, counts={}, label='Execution not reviewed')
    counts = {}
    for item in sections:
        counts[item['execution']] = counts.get(item['execution'], 0) + 1
    parts = [f"{counts[k]} {EXECUTION[k][0].lower()}" for k in ('good', 'misplayed', 'sat_out') if k in counts]
    return dict(reviewed=True, counts=counts, label='Reviewed · ' + ', '.join(parts))


def presentation(row):
    outcome = row['outcome'] if row else 'unrecorded'
    label, glyph, color = RESULTS[outcome]
    rating = row['setupRating'] if row else None
    sections = (row.get('executionSections') or []) if row else []
    return dict(outcome=outcome, label=label, glyph=glyph, color=color,
                setupRating=rating, ratingAsOf=row['ratingAsOf'] if row else None,
                recordedAt=row['recordedAt'] if row else None,
                executionSections=sections,
                executionAssessedAt=row.get('executionAssessedAt') if row else None,
                execution=execution_summary(sections),
                neutralColor=EXECUTION[NEUTRAL_EXECUTION][1],
                sourceLabel=('Reported by Marcelo' if row['sourceKind'] == 'user_reported' else 'Imported daily result') if row else None)


def strip(view):
    return f'<div class="trade-strip"><span class="trade-result"><span aria-hidden="true">{view["glyph"]}</span> My day · {view["label"]}</span></div>'


def legend(view):
    """Only the classes actually present on this day's line."""
    present = ['unreviewed'] + [k for k in ('good', 'misplayed', 'sat_out')
                                if any(s['execution'] == k for s in view['executionSections'])]
    items = ''.join(f'<span class="exec-key"><i style="background:{EXECUTION[k][1]}"></i>{EXECUTION[k][0]}</span>' for k in present)
    return f'<div class="exec-legend" role="img" aria-label="Execution color key">{items}</div>'


def notes(view):
    result = ['Daily scalps. Small steps. My record in color and sound.']
    if view['executionSections']:
        for item in view['executionSections']:
            line = f'{item["startTime"]}–{item["endTime"]} ET · {EXECUTION[item["execution"]][0]}'
            if item['publicNote']:
                line += ' · ' + item['publicNote']
            result.append(line)
    if view['executionAssessedAt']:
        result.append('Execution reviewed at ' + view['executionAssessedAt'] + ', after the close.')
    if view['sourceLabel']:
        result.append(view['sourceLabel'] + ' · Net result recorded ' + view['recordedAt'] + '. The net result is a label here; it does not color the line.')
    return result
