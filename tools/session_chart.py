#!/usr/bin/env python3
"""Draw one trading session as candles, positioned by the clock.

Two things were wrong with the charts before this existed, and both were the kind
of wrong that a metadata check passes.

Bars were placed by their index rather than their time. Seven hourly bars were
spread evenly across the width, but a session is 390 minutes and the last bar
covers only the 30 minutes from 15:30, so every bar sat slightly off its true
position and the drawing stopped short of the close. Here x comes from the
clock: minute 0 is the 09:30 open at the left edge, minute 390 is the 16:00
close at the right, and a bar's width is its actual duration.

Minute sessions were drawn as a line of closing prices while the source carried
full OHLC for every minute. The high and low of each minute were on disk and
thrown away at drawing time. Where candle data exists, candles are drawn.

One rule governs colour, and it is the reason this module does not do what every
other candle chart does. **Candles are never coloured by direction.** An up
candle and a down candle are the same colour, because green and red are reserved
for Marcelo's own review of how he played a stretch. Colouring a candle green
because the price rose would be deriving execution quality from price movement,
which is the single thing this project refuses to do. Unreviewed time is neutral
blue, and stays that way no matter what the price did.
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


def colour_note(sections):
    if sections:
        marks = '; '.join(f'{s["startTime"]}–{s["endTime"]} ET {EXECUTION[s["execution"]][0].lower()}'
                          for s in sections)
        return (f'Colour marks Marcelo’s own review of how he played each stretch ({marks}); '
                'unreviewed stretches stay neutral. Candles are never coloured by whether '
                'the price rose or fell.')
    return ('No stretch of this session has been reviewed for execution, so every candle is '
            'neutral. Candles are never coloured by whether the price rose or fell.')


def document(day, bars, sections=(), title='', detail='', low=None, high=None):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
            f'aria-labelledby="t d"><title id="t">{title or f"SPY {day}"}</title>'
            f'<desc id="d">{detail} {colour_note(sections)}</desc>'
            f'{candles(bars, sections, low, high)}</svg>')
