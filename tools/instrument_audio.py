#!/usr/bin/env python3
"""Play a session's instrument document as two synchronized stems.

The document (content/instrument/<date>.json) already decided every note.
This renderer only voices it, with fixed values a page cannot change:

* Clock: half a second per session minute, so a session is 195 seconds and a
  page can drive the orbit and both stems from one position.
* Stem 1, the session: one note per `noteEvents` entry, pitch A3 (220 Hz)
  plus the event's semitone, starting at startMinute * 0.5 s and stopping at
  (endMinute + 1) * 0.5 s. Consecutive events are contiguous; there is no
  overlap and no gap between them. Attack 0.02 s, release 0.08 s, both inside
  the note.
* Stem 2, the parent window: one note per `parent.sessionDay.noteEvents`
  entry, the same clock and the same start and stop rule, one octave below
  stem 1 (A2, 110 Hz, plus the semitone). Attack 0.15 s, release 0.40 s, so it
  sits under the session as the slow layer.
* Voice: the same additive tone for both, fundamental plus a second harmonic
  at 0.35 and a third at 0.15, sine-squared attack and cosine-squared release.
* Mix: one gain shared by both stems, chosen so their sum peaks at -1 dBFS.
  Each stem is written with that same gain, so playing both at unity
  reproduces the mix exactly and never clips.
* Silence wherever the mapping derived nothing: the edge loss at each end of
  every run and any missing observation. Nothing is voiced that was not
  derived, and nothing is random or chosen per day.

The voice is deliberately simple so that sampled notes can replace it later
without changing anything upstream. Output stays out of Git. Usage:

    python -X utf8 tools/instrument_audio.py --date 2026-09-04 [--output-dir PATH]
"""
import argparse
import hashlib
import json
import math
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(r'C:\MaloSound\handoff\instrument-audio')

SR = 44_100
SECONDS_PER_OBSERVATION = 0.5
A_HZ = 220.0
PARENT_OCTAVE = 0.5
HARMONICS = ((1, 1.0), (2, 0.35), (3, 0.15))
VOICE_GAIN = 0.5
TARGET_PEAK = 10 ** (-1.0 / 20)
STEMS = dict(
    session=dict(base_hz=A_HZ, attack=0.02, release=0.08),
    parent=dict(base_hz=A_HZ * PARENT_OCTAVE, attack=0.15, release=0.40),
)


def envelope(samples, attack, release):
    env = np.ones(samples, dtype=np.float32)
    a = min(samples, max(1, round(attack * SR)))
    r = min(samples, max(1, round(release * SR)))
    env[:a] *= np.sin(np.linspace(0, math.pi / 2, a, dtype=np.float32)) ** 2
    env[-r:] *= np.cos(np.linspace(0, math.pi / 2, r, dtype=np.float32)) ** 2
    return env


def pitch_hz(semitone, base_hz=A_HZ):
    return base_hz * 2.0 ** (semitone / 12.0)


def voice(semitone, seconds, base_hz, attack, release):
    samples = round(seconds * SR)
    t = np.arange(samples, dtype=np.float32) / SR
    tone = np.zeros(samples, dtype=np.float32)
    for multiple, weight in HARMONICS:
        tone += weight * np.sin(2 * math.pi * pitch_hz(semitone, base_hz) * multiple * t)
    return tone * envelope(samples, attack, release) * VOICE_GAIN


def stem_seconds(document):
    source = document['source']
    return (source['lastMinute'] - source['firstMinute'] + 1) * SECONDS_PER_OBSERVATION


def events_of(document, stem):
    return document['noteEvents'] if stem == 'session' else document['parent']['sessionDay']['noteEvents']


def raw_stem(document, stem):
    """One stem before the shared gain: every event voiced at its minute, silence elsewhere."""
    first = document['source']['firstMinute']
    total = round(stem_seconds(document) * SR)
    mix = np.zeros(total, dtype=np.float32)
    spec = STEMS[stem]
    for event in events_of(document, stem):
        start = round((event['startMinute'] - first) * SECONDS_PER_OBSERVATION * SR)
        if start >= total or start < 0:
            continue
        note = voice(event['semitone'], event['minutes'] * SECONDS_PER_OBSERVATION, spec['base_hz'], spec['attack'], spec['release'])
        end = min(total, start + len(note))
        mix[start:end] += note[:end - start]
    return mix


def render_stems(document):
    """Both stems under one shared gain, so that their sum peaks at -1 dBFS."""
    stems = {name: raw_stem(document, name) for name in STEMS}
    peak = float(np.max(np.abs(stems['session'] + stems['parent']))) if len(stems['session']) else 0.0
    gain = TARGET_PEAK / peak if peak > 0 else 1.0
    return {name: samples * gain for name, samples in stems.items()}


def render(document, stem='session'):
    return render_stems(document)[stem]


def write_wav(path, mono):
    stereo = np.repeat(mono[:, None], 2, axis=1)
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        for start in range(0, len(stereo), SR * 8):
            chunk = np.clip(stereo[start:start + SR * 8], -1, 1)
            handle.writeframes((chunk * 32767).astype('<i2').tobytes())


def dbfs(value):
    return round(20 * math.log10(value), 4) if value > 0 else None


def manifest(document, document_text, stems, paths):
    mix = stems['session'] + stems['parent']
    entries = {}
    for name, mono in stems.items():
        with wave.open(str(paths[name]), 'rb') as handle:
            check = dict(sample_rate=handle.getframerate(), channels=handle.getnchannels(),
                         sample_width_bytes=handle.getsampwidth(), frames=handle.getnframes(),
                         duration_seconds=handle.getnframes() / handle.getframerate())
        events = events_of(document, name)
        voiced = sum(e['minutes'] for e in events) * SECONDS_PER_OBSERVATION
        entries[name] = dict(wav=str(paths[name]), **check, note_events=len(events), voiced_seconds=voiced,
                             silent_seconds=round(stem_seconds(document) - voiced, 3),
                             peak_dbfs=dbfs(float(np.max(np.abs(mono)))), clipped_samples=int(np.count_nonzero(np.abs(mono) >= 1.0)),
                             finite_samples=bool(np.all(np.isfinite(mono))))
    return dict(
        date=document['date'], symbol=document['symbol'],
        instrumentDocumentSha256=hashlib.sha256(document_text.encode('utf-8')).hexdigest(),
        sourceSha256=document['source']['sha256'],
        stems=entries,
        mix=dict(peak_dbfs=dbfs(float(np.max(np.abs(mix)))), rms_dbfs=dbfs(float(np.sqrt(np.mean(mix ** 2)))),
                 clipped_samples=int(np.count_nonzero(np.abs(mix) >= 1.0))),
        mapping=dict(
            time=f'audio seconds = (session minute - first minute) * {SECONDS_PER_OBSERVATION}; a full session is 195 s',
            session=f'A3 = {A_HZ} Hz plus the event semitone; attack {STEMS["session"]["attack"]} s, release {STEMS["session"]["release"]} s',
            parent=f'A2 = {A_HZ * PARENT_OCTAVE} Hz plus the event semitone, one octave below; attack {STEMS["parent"]["attack"]} s, release {STEMS["parent"]["release"]} s',
            duration='each note starts at startMinute * 0.5 s and stops at (endMinute + 1) * 0.5 s; edge-loss and missing observations are silent',
            voice=f'fixed additive tone, harmonics {HARMONICS}, gain {VOICE_GAIN}; one shared gain so the two-stem sum peaks at -1 dBFS',
            determinism='same instrument document, same bytes; no randomness, no per-day choices',
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    source = ROOT / f'content/instrument/{args.date}.json'
    text = source.read_text(encoding='utf-8')
    document = json.loads(text)
    stems = render_stems(document)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: args.output_dir / f'{args.date}-{name}.wav' for name in stems}
    for name, mono in stems.items():
        write_wav(paths[name], mono)
    summary = manifest(document, text, stems, paths)
    (args.output_dir / f'{args.date}-stems.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    for name, entry in summary['stems'].items():
        print(f"{args.date} {name}: {entry['duration_seconds']:.1f} s, {entry['note_events']} notes, voiced {entry['voiced_seconds']:.1f} s, "
              f"silent {entry['silent_seconds']:.1f} s, peak {entry['peak_dbfs']} dBFS, clipped {entry['clipped_samples']}")
    print(f"{args.date} mix: peak {summary['mix']['peak_dbfs']} dBFS, clipped {summary['mix']['clipped_samples']} -> {args.output_dir}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
