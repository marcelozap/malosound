#!/usr/bin/env python3
"""Turn one session's regularly spaced closes into the instrument's fixed mapping.

Marcelo's instrument draws an orbit from price velocity (x) and price
acceleration (y), plays one of eight notes chosen by where the smoothed price
sits between the window's lowest and highest close, and colours the line by
that note's pitch. Everything here is fixed across sessions so that a tangled,
awkward session stays tangled and awkward: nothing is tuned per day.

Smoothing is a centred Savitzky-Golay fit: eleven observations, cubic
polynomial, one-minute spacing. The first and second derivatives come from the
fitted polynomial. Five observations are lost at each edge of every contiguous
run and are not extrapolated; a missing observation ends a run, so an overnight
gap or a source gap is never bridged as if the minutes were adjacent.

The mapping anchors are the window's lowest and highest close, frozen once. The
session open is not an anchor. Smoothed price is quantised to the nearest of
eight landmarks; an exact midpoint tie selects the higher landmark. A flat
window (high == low) produces the tonic everywhere and a stationary orbit.

Colour: A = 0 degrees, plus 30 degrees per semitone, modulo 360, so both A
octaves share a hue. Lightness and chroma are fixed OKLCH constants carried in
the output so a renderer never chooses them per session.

Nothing here reads broker records. Input is a public minute history file;
output names that file and its source hash. Usage:

    python -X utf8 tools/instrument_session.py --date 2026-09-04 [--write]
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_VERSION = 1
WINDOW = 11
DEGREE = 3
SPACING_MINUTES = 1
EDGE_LOSS = WINDOW // 2
LANDMARKS = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 0.886, 1.0)
NOTES = ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'A')
SEMITONES = (0, 2, 3, 5, 7, 8, 10, 12)
HUE_PER_SEMITONE = 30
OKLCH_LIGHTNESS = 0.80
OKLCH_CHROMA = 0.16
# Two landmark distances that differ by less than this are a tie.
TIE_TOLERANCE = 1e-12


def savitzky_golay_rows(window=WINDOW, degree=DEGREE):
    """Least-squares rows that turn one window of samples into polynomial coefficients.

    Row k gives the coefficient of t**k for the cubic fitted to the window, with
    t running -5..5 around the centre. The value at the centre is row 0, the
    slope is row 1 and the curvature term is row 2; the second derivative is
    twice that term.
    """
    half = window // 2
    t = np.arange(-half, half + 1, dtype=float)
    vandermonde = np.vander(t, degree + 1, increasing=True)
    return np.linalg.pinv(vandermonde)


def observations(history):
    """(minute, close) pairs in minute order from either history schema.

    The archive writes `bars`; the two recorded days write `minutes`. Both carry
    a minute index from 0 and a close. A minute that is absent, or whose close
    is missing or not finite, is simply not an observation.
    """
    series = history.get('bars') or history.get('minutes') or []
    found = {}
    for row in series:
        minute, close = row.get('minute'), row.get('close')
        if isinstance(minute, int) and isinstance(close, (int, float)) and np.isfinite(close):
            found[minute] = float(close)
    return sorted(found.items())


def contiguous_runs(pairs):
    """Split observations wherever a minute is missing. Runs are never bridged."""
    runs, current = [], []
    for minute, close in pairs:
        if current and minute != current[-1][0] + 1:
            runs.append(current)
            current = []
        current.append((minute, close))
    if current:
        runs.append(current)
    return runs


def normalise(smoothed, low, high):
    """Where a smoothed price sits between the frozen anchors, clamped to [0, 1].

    A least-squares fit can overshoot the raw closes slightly at a sharp turn;
    the clamp keeps that inside the mapping rather than inventing a ninth note.
    """
    if high == low:
        return 0.0
    return min(1.0, max(0.0, (smoothed - low) / (high - low)))


def quantize(position):
    """Index of the nearest landmark; an exact midpoint tie selects the higher one."""
    best, best_distance = 0, abs(position - LANDMARKS[0])
    for index in range(1, len(LANDMARKS)):
        distance = abs(position - LANDMARKS[index])
        if distance < best_distance - TIE_TOLERANCE or abs(distance - best_distance) <= TIE_TOLERANCE:
            best, best_distance = index, distance
    return best


def hue_of(index):
    return (SEMITONES[index] * HUE_PER_SEMITONE) % 360


def oklch_to_srgb_hex(lightness, chroma, hue):
    """An sRGB fallback for an OKLCH colour, gamut-clipped per channel.

    Browsers that understand oklch() use the exact colour; this hex exists so a
    renderer that does not is still visibly the right hue, and so the palette
    can be checked numerically. The clip is the one approximation, and it only
    matters where the fixed chroma leaves the sRGB gamut.
    """
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    linear = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
              -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
              -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)

    def encode(value):
        value = min(1.0, max(0.0, value))
        value = 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055
        return round(value * 255)
    return '#%02x%02x%02x' % tuple(encode(v) for v in linear)


def palette():
    """The eight notes as colours: exact OKLCH plus the sRGB fallback, fixed for every session."""
    return [dict(landmark=i, note=NOTES[i], semitone=SEMITONES[i], hue=hue_of(i),
                 oklch=f'oklch({OKLCH_LIGHTNESS} {OKLCH_CHROMA} {hue_of(i)})',
                 srgbFallback=oklch_to_srgb_hex(OKLCH_LIGHTNESS, OKLCH_CHROMA, hue_of(i)))
            for i in range(len(NOTES))]


def note_events(runs):
    """Run-length encode the landmark sequence: one event per held note, per run."""
    events = []
    for run in runs:
        current = None
        for point in run['points']:
            if current and current['landmark'] == point['landmark']:
                current['endMinute'] = point['minute']
                current['minutes'] += 1
                continue
            current = dict(startMinute=point['minute'], endMinute=point['minute'], minutes=1,
                           landmark=point['landmark'], note=point['note'],
                           semitone=point['semitone'], hue=point['hue'])
            events.append(current)
    return events


def analyse(history, source_path=None):
    pairs = observations(history)
    if not pairs:
        raise ValueError('No observations to analyse.')
    closes = [close for _, close in pairs]
    low, high = min(closes), max(closes)
    flat = high == low
    rows = savitzky_golay_rows()
    runs_out = []
    for run in contiguous_runs(pairs):
        if len(run) < WINDOW:
            runs_out.append(dict(startMinute=run[0][0], endMinute=run[-1][0], observations=len(run),
                                 points=[], note='shorter than the smoothing window; nothing derived'))
            continue
        values = np.array([close for _, close in run], dtype=float)
        points = []
        for centre in range(EDGE_LOSS, len(run) - EDGE_LOSS):
            coefficients = rows @ values[centre - EDGE_LOSS:centre + EDGE_LOSS + 1]
            smoothed = float(coefficients[0])
            if flat:
                velocity = acceleration = 0.0
            else:
                velocity = float(coefficients[1]) / SPACING_MINUTES
                acceleration = 2.0 * float(coefficients[2]) / SPACING_MINUTES ** 2
            position = normalise(smoothed, low, high)
            index = quantize(position)
            points.append(dict(minute=run[centre][0], close=run[centre][1],
                               smoothed=round(smoothed, 6), velocity=round(velocity, 6),
                               acceleration=round(acceleration, 6), position=round(position, 6),
                               landmark=index, note=NOTES[index], semitone=SEMITONES[index], hue=hue_of(index)))
        runs_out.append(dict(startMinute=run[0][0], endMinute=run[-1][0], observations=len(run),
                             derivedFrom=run[EDGE_LOSS][0], derivedTo=run[-1 - EDGE_LOSS][0], points=points))
    all_points = [p for run in runs_out for p in run['points']]
    present = {minute for minute, _ in pairs}
    missing = [m for m in range(pairs[0][0], pairs[-1][0] + 1) if m not in present]
    source = dict(path=source_path, sha256=history.get('sourceSha256') or history.get('source_sha256'),
                  observations=len(pairs), firstMinute=pairs[0][0], lastMinute=pairs[-1][0], missingMinutes=missing)
    return dict(
        schemaVersion=SCHEMA_VERSION,
        date=history.get('date'), symbol=history.get('symbol'),
        source=source,
        method=dict(
            smoothing=dict(kind='savitzky_golay', window=WINDOW, degree=DEGREE, spacingMinutes=SPACING_MINUTES,
                           edgeLossEachSide=EDGE_LOSS, derivatives='first and second derivatives of the fitted cubic',
                           gaps='a missing observation ends a run; runs are never bridged and edges are never extrapolated'),
            anchors=dict(low=low, high=high, frozen=True, sessionOpenIsAnchor=False),
            landmarks=list(LANDMARKS), notes=list(NOTES), semitones=list(SEMITONES),
            hueDegreesPerSemitone=HUE_PER_SEMITONE,
            colour=dict(model='oklch', lightness=OKLCH_LIGHTNESS, chroma=OKLCH_CHROMA,
                        note='fixed constants; a renderer never chooses these per session',
                        palette=palette()),
            tieRule='an exact midpoint selects the higher landmark',
            flatRule='high == low gives the tonic everywhere and a stationary orbit',
            orbit=dict(x='velocity, price units per minute', y='acceleration, price units per minute squared',
                       path='chronological polyline within each run; the last point is not joined to the first'),
        ),
        flat=flat,
        derivedObservations=len(all_points),
        bounds=dict(maxAbsVelocity=max((abs(p['velocity']) for p in all_points), default=0.0),
                    maxAbsAcceleration=max((abs(p['acceleration']) for p in all_points), default=0.0)),
        runs=runs_out,
        noteEvents=note_events(runs_out),
    )


def history_path(date):
    """The public minute file for a date, whichever pipeline wrote it."""
    for candidate in (ROOT / f'content/history/{date}-minute.json', ROOT / f'assets/charts/{date}-spy-data.json'):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f'No minute history for {date}; hourly days carry too few observations for this mapping.')


def render_json(document):
    return json.dumps(document, indent=2, ensure_ascii=False) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True)
    parser.add_argument('--history', type=Path, help='override the minute file')
    parser.add_argument('--write', action='store_true', help='write content/instrument/<date>.json')
    args = parser.parse_args(argv)
    path = args.history or history_path(args.date)
    history = json.loads(path.read_text(encoding='utf-8'))
    document = analyse(history, source_path='/' + path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path))
    text = render_json(document)
    print(f"{args.date}: {document['source']['observations']} observations, {document['derivedObservations']} derived, "
          f"{len(document['runs'])} run(s), {len(document['noteEvents'])} note events, "
          f"missing minutes {document['source']['missingMinutes'] or 'none'}, flat={document['flat']}")
    if args.write:
        target = ROOT / f'content/instrument/{args.date}.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        # Generated files match the repository's eol=lf attribute on every platform.
        with open(target, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
        print('wrote', target.relative_to(ROOT).as_posix(), hashlib.sha256(text.encode('utf-8')).hexdigest()[:12])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
