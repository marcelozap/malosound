#!/usr/bin/env python3
"""Draw one trading session as a thin price line, positioned by the clock.

Bars are placed by their time, not their index. Seven hourly bars spread evenly
across the width would put the last one at six sevenths, but a session is 390
minutes and the last bar covers only the 30 minutes from 15:30 — spreading them
by index leaves every bar off its true position and the drawing short of the
close. Here x comes from the clock: minute 0 is the 09:30 open at the left edge,
minute 390 is the 16:00 close at the right, and a bar's width is its actual
duration.

The line touches the session open and every observed bar's close, in the order
they happened, and nothing in between is invented. Hourly bars stay hourly —
seven wide steps, clearly not a minute path — because the line connects exactly
the boundaries that were actually observed and no others. A source gap breaks
the line rather than bridging it; the gap is real and stays visible.

One rule governs colour. **The line is never coloured by direction.** A falling
stretch and a rising stretch are the same colour, because green and red are
reserved for Marcelo's own review of how he played a stretch. Colouring the line
green because the price rose would be deriving execution quality from price
movement, which is the single thing this project refuses to do. Unreviewed time
is neutral blue, and stays that way no matter what the price did.

A candle renderer (`candles`, `classify`) is kept below, still correct and still
tested, in case a candle presentation is wanted again later. Nothing here calls
it; the published charts are lines.
"""
from trade_journal import EXECUTION, NEUTRAL_EXECUTION, session_minute

WIDTH, HEIGHT = 1000, 340
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 24, 30, 30
SESSION_MINUTES = 390          # 09:30 to 16:00 ET
PLOT_WIDTH = WIDTH - 2 * MARGIN_X
PLOT_HEIGHT = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM


def x_of(minute):
    """Minutes after the 09:30 open to a horizontal position.

    Minute 0 sits at the left edge and minute 390 at the right, so the drawing
    always spans the regular session exactly, whatever resolution it holds.
    """
    return MARGIN_X + minute / SESSION_MINUTES * PLOT_WIDTH


def y_of(price, low, high):
    span = (high - low) or 1
    return MARGIN_TOP + (high - price) / span * PLOT_HEIGHT


def classify(start, end, sections):
    """The execution class covering a bar, or neutral.

    A bar takes a class only when a reviewed span actually covers it. Partial
    overlap is not enough: a stretch Marcelo reviewed from 09:48 does not reach
    back and colour the hour that began at 09:30. Anything unreviewed stays
    neutral, which is what an absent assessment should look like.
    """
    for section in sections or []:
        opens = session_minute(section['startTime'])
        closes = session_minute(section['endTime'])
        if opens <= start and end <= closes:
            return section['execution']
    return NEUTRAL_EXECUTION


def candles(bars, sections=(), low=None, high=None):
    """SVG for one session's candles. `bars` carry startMinute, durationMinutes
    and open/high/low/close.

    Each candle is a body from open to close and a wick from high to low, both in
    the one colour its execution class gives it. A body that would vanish because
    open equals close is floored at a hairline so a flat bar is still visible and
    is not mistaken for missing data.
    """
    prices = [p for bar in bars for p in (bar['high'], bar['low'])]
    low = low if low is not None else min(prices)
    high = high if high is not None else max(prices)

    drawn = []
    for bar in bars:
        start = bar['startMinute']
        end = start + bar['durationMinutes']
        colour = EXECUTION[classify(start, end, sections)][1]
        left, right = x_of(start), x_of(end)
        # The gap is a proportion of the slot, not a fixed pixel. Capping it at one
        # pixel left an hourly body 144px wide, which reads as a stacked block
        # chart rather than candles; scaling it keeps the same shape legible at
        # both resolutions, where a slot is either 146 pixels or barely two.
        slot = right - left
        gap = max(0.15, slot * 0.2)
        left, right = left + gap, right - gap
        centre = (left + right) / 2
        wick = max(1.1, min(3.0, slot * 0.04))
        top = y_of(max(bar['open'], bar['close']), low, high)
        bottom = y_of(min(bar['open'], bar['close']), low, high)
        height = max(bottom - top, 1.1)
        drawn.append(
            f'<line x1="{centre:.2f}" y1="{y_of(bar["high"], low, high):.2f}" '
            f'x2="{centre:.2f}" y2="{y_of(bar["low"], low, high):.2f}" '
            f'stroke="{colour}" stroke-width="{wick:.2f}"/>'
            f'<rect x="{left:.2f}" y="{top:.2f}" width="{max(right - left, 0.8):.2f}" '
            f'height="{height:.2f}" fill="{colour}"/>')
    return ''.join(drawn)


OHLC = ('open', 'high', 'low', 'close')


def bars_from(source):
    """Candles from any of the saved history shapes.

    Three generators wrote three shapes for the same idea: hourly bars keyed by an
    ISO `startTime`, archive minute bars keyed by a `minute` index, and the song
    days' richer minute records that also carry volume and a `missing` flag. All
    three have carried full OHLC all along; only the drawing code ever threw it
    away. One reader over all three keeps a future chart from depending on which
    tool happened to write its source.
    """
    raw = source.get('bars') or source.get('minutes') or []
    if raw and 'startTime' in raw[0]:
        starts = [session_minute(bar['startTime'][11:16]) for bar in raw]
        ends = starts[1:] + [SESSION_MINUTES]
        return [dict(startMinute=start, durationMinutes=end - start,
                     **{k: bar[k] for k in OHLC})
                for bar, start, end in zip(raw, starts, ends)]
    return [dict(startMinute=bar['minute'], durationMinutes=1,
                 **{k: bar[k] for k in OHLC})
            for bar in raw
            if not bar.get('missing') and all(bar.get(k) is not None for k in OHLC)]


def line_paths(runs):
    """SVG `<path>` elements, one per coloured run of a thin price line."""
    drawn = []
    for run in runs:
        colour = EXECUTION[run['execution']][1]
        path = ' '.join(f'{"M" if i == 0 else "L"}{p["x"]:.2f},{p["y"]:.2f}'
                        for i, p in enumerate(run['points']))
        drawn.append(f'<path d="{path}" fill="none" stroke="{colour}" '
                     f'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>')
    return ''.join(drawn)


def lines(bars, sections=(), low=None, high=None):
    """The thin price line for one session, built from saved bars.

    Positions come from the clock (`x_of`), exactly as `candles` used: one
    point at the first bar's open, then one point at the end of every bar (its
    close). A segment between two consecutive points takes its bar's execution
    colour only when a reviewed span covers that bar's ENTIRE span — the same
    full-containment rule `classify` already gives candles. This matters most
    for hourly bars: colouring the whole 09:30-10:30 step because a review
    started at 09:48 would claim the review covers 09:30-09:48 too, which it
    does not. For a one-minute bar, full containment and point coverage are
    the same thing, so this behaves exactly as before at minute resolution. A
    source gap starts a new, disconnected run rather than bridging one.
    """
    if not bars:
        return ''
    prices = [p for bar in bars for p in (bar['open'], bar['close'])]
    low = low if low is not None else min(prices)
    high = high if high is not None else max(prices)

    def point(minute, price):
        return dict(x=x_of(minute), y=y_of(price, low, high))

    runs, previous_end, previous_point = [], None, None
    for bar in bars:
        start, end = bar['startMinute'], bar['startMinute'] + bar['durationMinutes']
        entry, exit_ = point(start, bar['open']), point(end, bar['close'])
        colour_class = classify(start, end, sections)
        gap = previous_end is not None and start > previous_end
        if gap or not runs:
            runs.append(dict(execution=colour_class, points=[entry, exit_]))
        elif runs[-1]['execution'] == colour_class:
            runs[-1]['points'].append(exit_)
        else:
            runs.append(dict(execution=colour_class, points=[previous_point, exit_]))
        previous_end, previous_point = end, exit_
    return line_paths(runs)


def colour_note(sections):
    if sections:
        marks = '; '.join(f'{s["startTime"]}–{s["endTime"]} ET {EXECUTION[s["execution"]][0].lower()}'
                          for s in sections)
        return (f'The line’s colour marks Marcelo’s own review of how he played each stretch ({marks}); '
                'unreviewed stretches stay neutral. The line is never coloured by whether '
                'the price rose or fell.')
    return ('No stretch of this session has been reviewed for execution, so the whole line is '
            'neutral. The line is never coloured by whether the price rose or fell.')


def trade_lines(bars, trade_sections=(), low=None, high=None):
    """Clip the existing market path at trade times without inventing price points."""
    from trade_overlays import COLORS, intervals
    base = lines(bars, (), low, high).replace(EXECUTION[NEUTRAL_EXECUTION][1], COLORS['unrecorded'])
    pieces = [base]
    for index, (start, end, outcome) in enumerate(intervals(trade_sections)):
        if outcome not in ('profit', 'loss'):
            continue
        clip = f'trade-window-{index}'
        pieces.append(f'<defs><clipPath id="{clip}"><rect x="{x_of(start):.4f}" y="0" '
                      f'width="{x_of(end)-x_of(start):.4f}" height="{HEIGHT}"/></clipPath></defs>'
                      f'<g clip-path="url(#{clip})">{base.replace(COLORS["unrecorded"], COLORS[outcome])}</g>')
    return ''.join(pieces)


def document(day, bars, sections=(), title='', detail='', low=None, high=None, trade_sections=(),
             resolution=None, coverage=None):
    from trade_overlays import note
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
            f'aria-labelledby="t d"><title id="t">{title or f"SPY {day}"}</title>'
            f'<desc id="d">{detail} {note(trade_sections, resolution, coverage)}</desc>'
            f'{trade_lines(bars, trade_sections, low, high)}</svg>')
