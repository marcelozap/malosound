#!/usr/bin/env python3
"""Play a session's instrument document as one deterministic audio stem.

The document (content/instrument/<date>.json) already decided every note: each
note event is a landmark the smoothed price held for a run of observations.
This renderer only voices it. Time is fixed at half a second per observation,
the same clock the existing recordings use (390 minutes = 195 seconds), so a
page can drive the orbit and the sound from one position. Pitch is the event's
semitone above A3 (220 Hz); duration is the event's observation count times the
clock. Minutes lost to smoothing at each edge, and minutes missing from the
source, are silent: nothing is voiced that the mapping did not derive.

The instrument is one fixed voice: a fundamental with two quiet harmonics and a
short sine-squared attack and release, mixed at a fixed gain, then peak
normalised to -1 dBFS across the whole stem without clipping. No melody is
chosen here, no rhythm is imposed, no note is random. The same document always
renders the same bytes. The voice is deliberately simple so that sampled notes
can replace it later without changing anything upstream.

Output stays out of Git. Usage:

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
HARMONICS = ((1, 1.0), (2, 0.35), (3, 0.15))
ATTACK = 0.02
RELEASE = 0.08
VOICE_GAIN = 0.5
TARGET_PEAK = 10 ** (-1.0 / 20)


def envelope(samples):
    env = np.ones(samples, dtype=np.float32)
    a = min(samples, max(1, round(ATTACK * SR)))
    r = min(samples, max(1, round(RELEASE * SR)))
    env[:a] *= np.sin(np.linspace(0, math.pi / 2, a, dtype=np.float32)) ** 2
    env[-r:] *= np.cos(np.linspace(0, math.pi / 2, r, dtype=np.float32)) ** 2
    return env


def pitch_hz(semitone):
    return A_HZ * 2.0 ** (semitone / 12.0)


def voice(semitone, seconds):
    samples = round(seconds * SR)
    t = np.arange(samples, dtype=np.float32) / SR
    tone = np.zeros(samples, dtype=np.float32)
    for multiple, weight in HARMONICS:
        tone += weight * np.sin(2 * math.pi * pitch_hz(semitone) * multiple * t)
    return tone * envelope(samples) * VOICE_GAIN


def stem_seconds(document):
    source = document['source']
    return (source['lastMinute'] - source['firstMinute'] + 1) * SECONDS_PER_OBSERVATION


def render(document):
    """Mono float32 samples covering every source observation, voiced where derived."""
    first = document['source']['firstMinute']
    total = round(stem_seconds(document) * SR)
    mix = np.zeros(total, dtype=np.float32)
    for event in document['noteEvents']:
        start = round((event['startMinute'] - first) * SECONDS_PER_OBSERVATION * SR)
        note = voice(event['semitone'], event['minutes'] * SECONDS_PER_OBSERVATION)
        end = min(total, start + len(note))
        mix[start:end] += note[:end - start]
    peak = float(np.max(np.abs(mix))) if len(mix) else 0.0
    if peak > 0:
        mix *= TARGET_PEAK / peak
    return mix


def write_wav(path, mono):
    stereo = np.repeat(mono[:, None], 2, axis=1)
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        for start in range(0, len(stereo), SR * 8):
            chunk = np.clip(stereo[start:start + SR * 8], -1, 1)
            handle.writeframes((chunk * 32767).astype('<i2').tobytes())


def manifest(document, document_text, mono, wav_path):
    with wave.open(str(wav_path), 'rb') as handle:
        check = dict(sample_rate=handle.getframerate(), channels=handle.getnchannels(),
                     sample_width_bytes=handle.getsampwidth(), frames=handle.getnframes(),
                     duration_seconds=handle.getnframes() / handle.getframerate())
    peak = float(np.max(np.abs(mono))) if len(mono) else 0.0
    rms = float(np.sqrt(np.mean(mono ** 2))) if len(mono) else 0.0
    return dict(
        date=document['date'], symbol=document['symbol'], stem='session',
        instrumentDocumentSha256=hashlib.sha256(document_text.encode('utf-8')).hexdigest(),
        sourceSha256=document['source']['sha256'],
        wav=str(wav_path),
        validation=dict(**check, finite_samples=bool(np.all(np.isfinite(mono))),
                        peak_dbfs=round(20 * math.log10(peak), 4) if peak else None,
                        rms_dbfs=round(20 * math.log10(rms), 4) if rms else None,
                        clipped_samples=int(np.count_nonzero(np.abs(mono) >= 1.0)),
                        note_events=len(document['noteEvents']),
                        voiced_seconds=sum(e['minutes'] for e in document['noteEvents']) * SECONDS_PER_OBSERVATION,
                        silent_seconds=round(stem_seconds(document) - sum(e['minutes'] for e in document['noteEvents']) * SECONDS_PER_OBSERVATION, 3)),
        mapping=dict(
            time=f'audio seconds = (observation minute - first minute) * {SECONDS_PER_OBSERVATION}; a full session is 195 s',
            pitch=f'A3 = {A_HZ} Hz plus the note event semitone; landmarks map to A B C D E F G A',
            duration='each note lasts its event observation count times the clock; edge-loss and missing minutes are silent',
            voice=f'fixed additive tone, harmonics {HARMONICS}, attack {ATTACK}s, release {RELEASE}s, gain {VOICE_GAIN}, peak normalised to -1 dBFS',
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
    mono = render(document)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    wav_path = args.output_dir / f'{args.date}-session.wav'
    write_wav(wav_path, mono)
    summary = manifest(document, text, mono, wav_path)
    (args.output_dir / f'{args.date}-session.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    v = summary['validation']
    print(f"{args.date}: {v['duration_seconds']:.1f} s, {v['note_events']} notes, voiced {v['voiced_seconds']:.1f} s, "
          f"silent {v['silent_seconds']:.1f} s, peak {v['peak_dbfs']} dBFS, clipped {v['clipped_samples']} -> {wav_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
