"""Minimal public day results; private fills, amounts and accounts never belong here."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

RESULTS = {
    'profit': ('Profit', '+', '#58dfa4'),
    'loss': ('Loss', '−', '#ff7188'),
    'flat': ('Flat', '=', '#b8c5d0'),
    'no_trade': ('No trade', '○', '#81929e'),
    'unrecorded': ('Unrecorded', '—', '#81929e'),
}
FIELDS = {'date', 'outcome', 'setupRating', 'recordedAt', 'ratingAsOf', 'sourceKind'}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('A timestamp with a timezone is required.')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() is None:
        raise ValueError('A timestamp with a timezone is required.')
    return parsed


def validate(data):
    if set(data) != {'schemaVersion', 'days'} or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1 or not isinstance(data['days'], list):
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
        days[day] = row
    return days


def presentation(row):
    outcome = row['outcome'] if row else 'unrecorded'
    label, glyph, color = RESULTS[outcome]
    rating = row['setupRating'] if row else None
    return dict(outcome=outcome, label=label, glyph=glyph, color=color,
                setupRating=rating, ratingAsOf=row['ratingAsOf'] if row else None,
                recordedAt=row['recordedAt'] if row else None,
                sourceLabel=('Reported by Marcelo' if row['sourceKind'] == 'user_reported' else 'Imported daily result') if row else None)


def strip(view):
    rating = view['setupRating']
    label = f'Setup quality: {rating} of 14' if rating is not None else 'Setup quality not rated'
    bars = ''.join(f'<i class="{"is-lit" if rating is not None and n <= rating else ""}"></i>' for n in range(1, 15))
    score = str(rating) if rating is not None else '—'
    return f'<div class="trade-strip"><span class="trade-result"><span aria-hidden="true">{view["glyph"]}</span> My day · {view["label"]}</span><div class="setup-meter" role="img" aria-label="{label}" title="Setup quality · 14 is reserved for the rarest opportunities"><span class="setup-bars" aria-hidden="true">{bars}</span><span class="setup-score" aria-hidden="true">{score}<small>/14</small></span></div></div>'


def notes(view):
    result = ['SPY draws the shape. Color records Marcelo’s net realized trading result after fees for that New York date: green for profit, red for loss. This is a market price line, not an account equity curve. Gray means flat, no trade, or an unrecorded result; the label distinguishes them.',
              'The 1–14 rating is Marcelo’s setup-quality assessment, separate from profit or loss. 14 is the rarest tier, aiming for roughly 14 exceptional opportunities a year; it is not a guaranteed annual count or a quota. Ratings are never inferred from a winning day.']
    if view['sourceLabel']:
        result.append(view['sourceLabel'] + ' · Recorded ' + view['recordedAt'])
    if view['ratingAsOf']:
        result.append('Setup assessment time: ' + view['ratingAsOf'] + '. A later assessment is retrospective, not a pre-trade call.')
    return result
