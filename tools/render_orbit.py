#!/usr/bin/env python3
"""Draw a session's orbit from its instrument document, as a static preview SVG.

Horizontal is price velocity, vertical is price acceleration. Points are joined
in time order within each contiguous run and never across a gap, and the last
point is never joined back to the first. Each segment takes the OKLCH hue of
the note its observation quantised to, at the fixed lightness and chroma the
document carries. Nothing is smoothed, closed or tidied here; an awkward
session draws an awkward orbit.

Scaling is the one presentation choice this preview makes: each axis is fitted
to the session's own largest magnitude so the shape fills the frame. The
document keeps the raw values, so a renderer that wants one fixed scale across
sessions has what it needs. The SVG says which scaling it used.

These previews are for Marcelo to look at. They are not in the public
allowlist and nothing here deploys. Usage:

    python -X utf8 tools/render_orbit.py --date 2026-09-04
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIZE = 1000
MARGIN = 80
STROKE = 1.4


def style(document):
    """One class per note: the sRGB fallback first, then the exact OKLCH where supported."""
    palette = document['method']['colour']['palette']
    fallback = ''.join(f'.n{p["landmark"]}{{stroke:{p["srgbFallback"]}}}' for p in palette)
    exact = ''.join(f'.n{p["landmark"]}{{stroke:{p["oklch"]}}}' for p in palette)
    return f'<style>{fallback}@supports (color: oklch(0.5 0.1 0)){{{exact}}}</style>'


def scale(document):
    """Map raw velocity and acceleration onto the frame using the session's own extremes."""
    bounds = document['bounds']
    half = SIZE / 2 - MARGIN
    vx = bounds['maxAbsVelocity'] or 1.0
    ay = bounds['maxAbsAcceleration'] or 1.0

    def point(p):
        # Positive acceleration goes up on the page, so y is flipped.
        return (round(SIZE / 2 + p['velocity'] / vx * half, 2), round(SIZE / 2 - p['acceleration'] / ay * half, 2))
    return point


def render(document):
    point = scale(document)
    segments, starts, ends, drawn = [], [], [], 0
    for run in document['runs']:
        points = run['points']
        if not points:
            continue
        starts.append(point(points[0]))
        ends.append(point(points[-1]))
        for a, b in zip(points, points[1:]):
            (x1, y1), (x2, y2) = point(a), point(b)
            segments.append(f'<line class="n{b["landmark"]}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')
            drawn += 1
    method = document['method']['smoothing']
    missing = document['source']['missingMinutes']
    gap_note = f" Missing minutes {', '.join(map(str, missing))} end a run; nothing is drawn across them." if missing else ''
    flat_note = ' The window is flat, so the orbit is a single stationary point.' if document['flat'] else ''
    desc = (f"Orbit of SPY on {document['date']}: horizontal is price velocity, vertical is price acceleration, "
            f"from a centred Savitzky-Golay fit of {method['window']} observations, degree {method['degree']}, "
            f"one-minute spacing, {method['edgeLossEachSide']} observations lost at each edge of each run. "
            f"{document['derivedObservations']} observations drawn in time order; the path is not closed. "
            f"Colour is the note each observation quantised to, thirty degrees of hue per semitone from A."
            f"{gap_note}{flat_note} Axes are scaled to this session's own extremes; this is a preview, not a fixed scale.")
    marks = ''.join(f'<circle cx="{x}" cy="{y}" r="4" fill="#f7f7f5"/>' for x, y in starts)
    marks += ''.join(f'<circle cx="{x}" cy="{y}" r="4" fill="none" stroke="#f7f7f5" stroke-width="1.5"/>' for x, y in ends)
    label = (f'<text x="{MARGIN}" y="{SIZE - MARGIN / 2}" fill="#8a8a92" font-family="Arial, Helvetica, sans-serif" '
             f'font-size="18" letter-spacing="1">SPY · {document["date"]} · velocity × acceleration · '
             f'{document["derivedObservations"]} observations · preview scaling</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" role="img" aria-labelledby="t d">'
            f'<title id="t">SPY {document["date"]} orbit</title><desc id="d">{desc}</desc>{style(document)}'
            f'<rect width="{SIZE}" height="{SIZE}" fill="#000"/>'
            f'<g fill="none" stroke-width="{STROKE}" stroke-linecap="round" opacity="0.92">{"".join(segments)}</g>'
            f'{marks}{label}</svg>\n'), drawn


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True)
    args = parser.parse_args(argv)
    source = ROOT / f'content/instrument/{args.date}.json'
    document = json.loads(source.read_text(encoding='utf-8'))
    svg, drawn = render(document)
    target = ROOT / f'assets/orbits/{args.date}-orbit.svg'
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(svg)
    print(f'{args.date}: {drawn} segments -> {target.relative_to(ROOT).as_posix()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
