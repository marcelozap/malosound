"""Render an original, deterministic SPY-session instrumental using NumPy + wave.

Usage:
    python render_song.py path/to/analysis.json [--stems] [--output-dir PATH]

The whole 390-minute regular session maps linearly to 195 audio seconds:
one market minute = 0.5 seconds; 80 BPM = 65 four-beat bars; one bar = six
market minutes. Lead note onsets resample the actual price contour on a
musical rhythm, so this is a musical interpretation, not a tick-for-tick
recording. Higher price_position always selects the same or a higher lead
note from a fixed D-minor pentatonic scale. Energy controls rhythmic density
and velocity; volatility controls harmonics, noise and percussion color.

The scale, chord progression, groove, intro and ending are original artistic
choices; they do not purport to explain or predict market movements. No
lyrics, artist imitation, downloaded samples, network or music API is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import wave
from pathlib import Path

import numpy as np


SR = 44_100
SEED = 9042026
DURATION = 195.0
BPM = 80.0
BEAT = 60.0 / BPM
BAR = BEAT * 4.0
PPQ = 480
# D3, F3, G3, A3, C4, D4, F4, G4, A4, C5, D5, F5.
PENTATONIC = np.array([50, 53, 55, 57, 60, 62, 65, 67, 69, 72, 74, 77])
BASS_PENTATONIC = np.array([38, 41, 43, 45, 48, 50])
CHORDS = (
    (38, (50, 53, 57, 60)),  # Dm7
    (34, (46, 50, 53, 57)),  # Bbmaj7
    (41, (48, 53, 57, 64)),  # Fmaj7, open inversion
    (36, (48, 52, 55, 62)),  # Cadd9
)


def midi_hz(note: int) -> float:
    return 440.0 * 2.0 ** ((note - 69) / 12.0)


def adsr(n: int, attack: float, release: float) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    a = min(n, max(1, round(attack * SR)))
    r = min(n, max(1, round(release * SR)))
    env[:a] *= np.sin(np.linspace(0, math.pi / 2, a)) ** 2
    env[-r:] *= np.cos(np.linspace(0, math.pi / 2, r)) ** 2
    return env


def soft_noise(rng: np.random.Generator, n: int, width: int) -> np.ndarray:
    """A short moving-average low-pass, keeping all synthesis dependency-free."""
    noise = rng.standard_normal(n).astype(np.float32)
    if width > 1:
        noise = np.convolve(noise, np.ones(width, dtype=np.float32) / width, "same")
    return noise


def lead_sound(note: int, seconds: float, brightness: float) -> np.ndarray:
    n = round(seconds * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = midi_hz(note)
    # A warm, plucked electric-piano-like voice with a quiet bell transient.
    phase = 2 * np.pi * f * t + 0.003 * np.sin(2 * np.pi * 5.1 * t)
    sig = np.sin(phase) * np.exp(-t / 0.76)
    sig += (0.23 + 0.12 * brightness) * np.sin(phase * 2) * np.exp(-t / 0.31)
    sig += (0.065 + 0.16 * brightness) * np.sin(phase * 3) * np.exp(-t / 0.15)
    sig += 0.065 * np.sin(phase * 1.003) * np.exp(-t / 1.0)
    return (sig * adsr(n, 0.008, 0.14)).astype(np.float32)


def bass_sound(note: int, seconds: float, brightness: float) -> np.ndarray:
    n = round(seconds * SR)
    t = np.arange(n, dtype=np.float32) / SR
    phase = 2 * np.pi * midi_hz(note) * t
    sig = np.sin(phase) + 0.21 * np.sin(phase * 2)
    sig += (0.04 + 0.08 * brightness) * np.sin(phase * 3)
    return (sig * np.exp(-t / 1.35) * adsr(n, 0.015, 0.11)).astype(np.float32)


def pad_sound(notes: tuple[int, ...], seconds: float, brightness: float) -> np.ndarray:
    n = round(seconds * SR)
    t = np.arange(n, dtype=np.float32) / SR
    stereo = np.zeros((n, 2), dtype=np.float32)
    for i, note in enumerate(notes):
        f = midi_hz(note)
        p = 2 * np.pi * f * t
        slow = 0.91 + 0.09 * np.sin(2 * np.pi * (0.12 + i * 0.013) * t + i)
        stereo[:, 0] += slow * (np.sin(p * 0.9991 + i) + 0.16 * np.sin(2 * p))
        stereo[:, 1] += slow * (np.sin(p * 1.0009 + i) + 0.16 * np.sin(2 * p))
        stereo[:, 0] += brightness * 0.04 * np.sin(3 * p)
        stereo[:, 1] += brightness * 0.04 * np.sin(3 * p * 1.0003)
    stereo *= (adsr(n, 0.45, 0.8) / len(notes))[:, None]
    return stereo


def kick_sound() -> np.ndarray:
    n = round(0.52 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    # Integrating the falling frequency avoids a discontinuous pitch sweep.
    phase = 2 * np.pi * (47 * t + 77 * 0.023 * (1 - np.exp(-t / 0.023)))
    sig = np.sin(phase) * np.exp(-t / 0.14)
    sig += 0.13 * np.sin(2 * np.pi * 920 * t) * np.exp(-t / 0.006)
    return (sig * adsr(n, 0.0015, 0.045)).astype(np.float32)


def snare_sound(rng: np.random.Generator, bright: float, ghost: bool = False) -> np.ndarray:
    n = round(0.29 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    raw = soft_noise(rng, n, 1)
    low = np.convolve(raw, np.ones(11, dtype=np.float32) / 11, "same")
    noise = raw - low
    body = 0.31 * np.sin(2 * np.pi * 182 * t) * np.exp(-t / 0.07)
    sig = body + (0.45 + 0.13 * bright) * noise * np.exp(-t / (0.053 if ghost else 0.085))
    return (sig * adsr(n, 0.0015, 0.03)).astype(np.float32)


def hat_sound(rng: np.random.Generator, bright: float, opened: bool = False) -> np.ndarray:
    seconds = 0.25 if opened else 0.065
    n = round(seconds * SR)
    t = np.arange(n, dtype=np.float32) / SR
    raw = soft_noise(rng, n, 1)
    high = raw - np.convolve(raw, np.ones(5, dtype=np.float32) / 5, "same")
    sig = high * np.exp(-t / (0.057 if opened else 0.016))
    return (sig * (0.6 + 0.4 * bright) * adsr(n, 0.001, 0.012)).astype(np.float32)


def add_mono(track: np.ndarray, signal: np.ndarray, start: float, gain: float, pan: float = 0.0) -> None:
    offset = round(start * SR)
    if offset >= len(track) or offset < 0:
        return
    n = min(len(signal), len(track) - offset)
    angle = (max(-1.0, min(1.0, pan)) + 1) * math.pi / 4
    track[offset:offset + n, 0] += signal[:n] * (gain * math.cos(angle))
    track[offset:offset + n, 1] += signal[:n] * (gain * math.sin(angle))


def add_stereo(track: np.ndarray, signal: np.ndarray, start: float, gain: float) -> None:
    offset = round(start * SR)
    if offset >= len(track):
        return
    n = min(len(signal), len(track) - offset)
    track[offset:offset + n] += signal[:n] * gain


def vlq(value: int) -> bytes:
    value = max(0, value)
    result = [value & 127]
    value >>= 7
    while value:
        result.insert(0, 128 | (value & 127))
        value >>= 7
    return bytes(result)


def midi_track(events: list[tuple[int, bytes]], final_tick: int) -> bytes:
    events.sort(key=lambda x: (x[0], 0 if (x[1][0] & 0xF0) == 0x80 else 1))
    result = bytearray()
    previous = 0
    for tick, message in events:
        result += vlq(tick - previous) + message
        previous = tick
    result += vlq(max(0, final_tick - previous)) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(result)) + bytes(result)


def meta_text(kind: int, value: str) -> bytes:
    payload = value.encode("utf-8")
    return bytes([0xFF, kind]) + vlq(len(payload)) + payload


def write_midi(path: Path, note_events: dict[str, list], data: dict) -> None:
    tick_per_second = PPQ * BPM / 60
    end_tick = round(DURATION * tick_per_second)
    meta = [
        (0, meta_text(3, f"SPY {data['date']} - regular session")),
        (0, b"\xff\x51\x03" + round(60_000_000 / BPM).to_bytes(3, "big")),
        (0, b"\xff\x58\x04\x04\x02\x18\x08"),
        (0, b"\xff\x59\x02\xff\x01"),  # one flat; D minor
        (0, meta_text(1, "09:30-16:00 ET; 1 market minute = 0.5 seconds; 6 minutes/bar")),
    ]
    for section in data.get("sections", []):
        tick = round(float(section["start_minute"]) * 0.5 * tick_per_second)
        meta.append((tick, meta_text(6, str(section["name"]))))
    chunks = [midi_track(meta, end_tick)]
    channels = {"lead": (0, 4), "bass": (1, 38), "pad": (2, 89), "drums": (9, 0)}
    for name, notes in note_events.items():
        channel, program = channels[name]
        events = [(0, meta_text(3, name)), (0, bytes([0xC0 | channel, program]))]
        for seconds, length, pitch, velocity in notes:
            start = round(seconds * tick_per_second)
            end = min(end_tick, round((seconds + length) * tick_per_second))
            if start < end_tick:
                events.append((start, bytes([0x90 | channel, int(pitch), int(velocity)])))
                events.append((end, bytes([0x80 | channel, int(pitch), 0])))
        chunks.append(midi_track(events, end_tick))
    path.write_bytes(b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQ) + b"".join(chunks))


def write_wav(path: Path, samples: np.ndarray) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        for start in range(0, len(samples), SR * 8):
            chunk = np.clip(samples[start:start + SR * 8], -1, 1)
            wav.writeframes((chunk * 32767).astype("<i2").tobytes())


def validate_input(data: dict) -> None:
    if float(data.get("duration_seconds", DURATION)) != DURATION:
        raise ValueError("This renderer requires duration_seconds=195.")
    if float(data.get("tempo_bpm", BPM)) != BPM:
        raise ValueError("This renderer requires tempo_bpm=80 (65 bars for the full session).")
    minutes = data["minutes"]
    if len(minutes) != 390 or [m["minute"] for m in minutes] != list(range(390)):
        raise ValueError("Exactly 390 ordered minutes, numbered 0..389, are required.")
    for m in minutes:
        for key in ("open", "high", "low", "close", "volume", "price_position", "energy", "volatility"):
            if not math.isfinite(float(m[key])):
                raise ValueError(f"Non-finite {key} at minute {m['minute']}.")
        for key in ("price_position", "energy", "volatility"):
            if not 0 <= m[key] <= 1:
                raise ValueError(f"{key} must be normalized to [0,1].")
    for section in data.get("composition", {}).get("sections", []):
        if not 0 <= float(section["start_minute"]) < float(section["end_minute"]) <= 390:
            raise ValueError("Composition section boundaries must be ordered inside minutes 0..390.")
        for key in ("drum_density", "pad_gain", "lead_gain"):
            if not 0.35 <= float(section.get(key, 1.0)) <= 1.25:
                raise ValueError(f"Composition {key} must lie in [0.35,1.25].")


def render(analysis_path: Path, output_dir: Path, stems: bool = False) -> dict:
    raw = analysis_path.read_bytes()
    data = json.loads(raw)
    validate_input(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    n = round(DURATION * SR)
    tracks = {name: np.zeros((n, 2), dtype=np.float32) for name in ("lead", "bass", "pad", "drums")}
    notes = {name: [] for name in tracks}
    arrays = {key: np.array([m[key] for m in data["minutes"]]) for key in ("energy", "volatility")}
    summary = data.get("summary", {})
    source_high = float(summary.get("high", max(m["high"] for m in data["minutes"])))
    source_low = float(summary.get("low", min(m["low"] for m in data["minutes"])))
    opening = float(summary.get("open", data["minutes"][0]["open"]))
    closing = float(data.get("closing_print", {}).get("close", data["minutes"][-1]["close"]))
    # Minute bar i closes at boundary i+1, not at its start timestamp. The
    # separate 16:00 print supplies boundary 390 only, without adding a bar.
    prices = np.array([opening] + [m["close"] for m in data["minutes"][:-1]] + [closing])
    positions = np.clip((prices - source_low) / max(source_high - source_low, 1e-9), 0, 1)

    def market(seconds: float) -> tuple[float, float, float]:
        minute = min(390.0, max(0.0, seconds * 2))
        left = int(minute)
        right = min(390, left + 1)
        frac = minute - left
        position = float(positions[left] * (1 - frac) + positions[right] * frac)
        bucket = min(389, left)
        return position, float(arrays["energy"][bucket]), float(arrays["volatility"][bucket])

    def arrangement(seconds: float) -> dict:
        minute = min(389.999, max(0, seconds * 2))
        for section in data.get("composition", {}).get("sections", []):
            if section["start_minute"] <= minute < section["end_minute"]:
                return {key: float(section.get(key, 1.0)) for key in ("drum_density", "pad_gain", "lead_gain")}
        return {"drum_density": 1.0, "pad_gain": 1.0, "lead_gain": 1.0}

    def note(track: str, at: float, length: float, pitch: int, gain: float) -> None:
        notes[track].append((at, length, int(pitch), max(1, min(127, round(gain * 127)))))

    kick = kick_sound()
    bar_map = []
    for bar in range(65):
        at = bar * BAR
        position, energy, volatility = market(at + BAR / 2)
        shape = arrangement(at)
        density = shape["drum_density"]
        root, chord = CHORDS[(bar // 4) % len(CHORDS)]
        if bar == 64:
            root, chord = CHORDS[-1]  # keep the final Cadd9 suspended; no tonic victory
        intro = min(1.0, 0.50 + bar / 6)
        ending = 0.77 if bar >= 63 else 1.0
        # The pad rearticulates once each six-market-minute bar.
        pad_len = min(4.3, DURATION - at)
        add_stereo(tracks["pad"], pad_sound(chord, pad_len, volatility), at, (0.22 + 0.08 * energy) * shape["pad_gain"])
        for pitch in chord:
            note("pad", at, min(BAR + 0.3, DURATION - at), pitch, (0.30 + 0.20 * energy) * shape["pad_gain"])

        # Repeating rhythmic cells make the sampled contour recognizable.
        motifs = (
            (0.0, 0.75, 1.5, 2.5, 3.25),
            (0.0, 1.0, 1.75, 2.5, 3.5),
            (0.0, 0.75, 1.5, 2.75, 3.5),
            (0.0, 1.5, 2.25, 3.0),
        )
        onset_beats = list(motifs[bar % 4])
        if energy < 0.25:
            onset_beats = [onset_beats[0], onset_beats[2], onset_beats[-1]]
        if energy > 0.64 and bar % 4 != 3:
            onset_beats.append(2.0)
        if bar == 64:
            onset_beats = [0.0, 1.0, 2.0]
        for j, beat in enumerate(sorted(set(onset_beats))):
            t = at + beat * BEAT
            pos, e, vol = market(t)
            pitch = int(PENTATONIC[round(pos * (len(PENTATONIC) - 1))])
            lead_gain = arrangement(t)["lead_gain"]
            gain = (0.19 + 0.075 * e) * (1.04 if j == 0 else 0.88 + 0.08 * (j % 2)) * lead_gain
            sound = lead_sound(pitch, 1.25, vol)
            pan = 0.10 * math.sin(bar * 0.7)
            add_mono(tracks["lead"], sound, t, gain, pan)
            for repeat, echo_gain in enumerate((0.23, 0.115, 0.050), 1):
                add_mono(tracks["lead"], sound, t + BEAT * 0.75 * repeat,
                         gain * echo_gain, (-0.52 if repeat % 2 else 0.52))
            note("lead", t, 0.32 if beat % 1 else 0.49, pitch, (0.50 + 0.28 * e) * lead_gain)

        for beat, length in ((0.0, 1.1), (1.75, 0.58), (2.5, .75)):
            if beat == 1.75 and (energy < 0.23 or bar < 2):
                continue
            t = at + beat * BEAT
            bass_pos, _, _ = market(t)
            bass_pitch = int(BASS_PENTATONIC[round(bass_pos * (len(BASS_PENTATONIC) - 1))])
            gain = (0.30 + 0.09 * energy) * (0.78 if beat else 1.0)
            add_mono(tracks["bass"], bass_sound(bass_pitch, length, volatility), t, gain)
            note("bass", t, length - 0.06, bass_pitch, 0.58 + 0.24 * energy)

        drum_gain = intro * ending
        kick_beats = [0.0] if density < 0.65 else [0.0, 2.75]
        if energy * density > 0.4:
            kick_beats.append(1.5 if bar % 2 else 1.75)
        if energy * density > 0.74 and bar % 4 == 3:
            kick_beats.append(3.5)
        for beat in kick_beats:
            t = at + beat * BEAT
            gain = drum_gain * (0.49 + 0.12 * energy) * (1.0 if beat == 0 else 0.80)
            add_mono(tracks["drums"], kick, t, gain)
            note("drums", t, 0.12, 36, 0.70 if beat == 0 else 0.56)
        for beat in (2.0,):
            t = at + beat * BEAT
            add_mono(tracks["drums"], snare_sound(rng, volatility), t, drum_gain * (0.27 + 0.07 * energy), 0.05)
            note("drums", t, 0.15, 38, 0.56 + 0.17 * energy)
        if energy * density > 0.48 and bar % 2:
            t = at + 3.75 * BEAT
            add_mono(tracks["drums"], snare_sound(rng, volatility, True), t, drum_gain * 0.10, -0.16)
            note("drums", t, 0.10, 38, 0.26)
        hat_step = 0.25 if energy * density > 0.78 else (1.0 if density < 0.65 else 0.5)
        for j, beat in enumerate(np.arange(0.0, 4.0, hat_step)):
            if energy * density < 0.22 and j % 2:
                continue
            # A small, fixed swing remains independent of the market clock.
            t = at + float(beat) * BEAT + (0.025 if j % 2 else 0)
            opened = bool(j == int(4 / hat_step) - 1 and volatility > 0.4)
            gain = drum_gain * (0.055 + 0.055 * energy) * (0.67 if j % 2 else 1.0)
            add_mono(tracks["drums"], hat_sound(rng, volatility, opened), t, gain, -0.29 if j % 2 else 0.25)
            note("drums", t, 0.12 if opened else 0.055, 46 if opened else 42, 0.24 + 0.20 * energy)
        bar_map.append({"bar": bar + 1, "audio_start_seconds": at, "market_start_minute": bar * 6,
                        "price_position": position, "energy": energy, "volatility": volatility,
                        "pad_root_midi": root, "lead_onsets": len(set(onset_beats)), "composition_multipliers": shape})

    # One shared envelope/gain preserves stem-to-mix reconstruction.
    fade = np.ones(n, dtype=np.float32)
    start_n, end_n = round(0.03 * SR), round(2.0 * SR)
    fade[:start_n] = np.linspace(0, 1, start_n)
    fade[-end_n:] = np.cos(np.linspace(0, math.pi / 2, end_n)) ** 2
    mix = np.zeros((n, 2), dtype=np.float32)
    for track in tracks.values():
        track *= fade[:, None]
        mix += track
    if not np.isfinite(mix).all():
        raise RuntimeError("Rendered audio contains non-finite samples.")
    peak_before = float(np.max(np.abs(mix)))
    # Transparent peak normalization: no hard clipping, no fake mastering claim.
    gain = 10 ** (-1.0 / 20) / max(peak_before, 1e-9)
    mix *= gain
    prefix = f"SPY_{data['date']}_market-to-music"
    wav_path = output_dir / f"{prefix}.wav"
    midi_path = output_dir / f"{prefix}.mid"
    write_wav(wav_path, mix)
    write_midi(midi_path, notes, data)
    stem_paths = []
    if stems:
        for name, track in tracks.items():
            track *= gain
            path = output_dir / f"{prefix}_{name}.wav"
            write_wav(path, track)
            stem_paths.append(str(path))
    with wave.open(str(wav_path), "rb") as wav:
        check = {"sample_rate": wav.getframerate(), "channels": wav.getnchannels(),
                 "sample_width_bytes": wav.getsampwidth(), "frames": wav.getnframes(),
                 "duration_seconds": wav.getnframes() / wav.getframerate()}
    if check["frames"] != n or check["channels"] != 2 or check["duration_seconds"] != DURATION:
        raise RuntimeError(f"WAV validation failed: {check}")
    summary = {
        "symbol": data.get("symbol", "SPY"), "date": data["date"],
        "title": data.get("composition", {}).get("title", "An Unfinished Return"),
        "wav": str(wav_path), "midi": str(midi_path), "stems": stem_paths,
        "analysis_sha256": hashlib.sha256(raw).hexdigest(), "seed": SEED,
        "source_url": data.get("source_url"), "tempo_bpm": BPM, "bars": 65,
        "validation": {**check, "finite_samples": True,
                       "peak_dbfs": round(20 * math.log10(float(np.max(np.abs(mix)))), 4),
                       "rms_dbfs": round(20 * math.log10(float(np.sqrt(np.mean(mix ** 2)))), 4),
                       "clipped_samples": int(np.count_nonzero(np.abs(mix) >= 1.0))},
        "mapping": {
            "time": "audio seconds = market minutes after 09:30 ET * 0.5; full session ends at 195 s",
            "lead_pitch": "round(interpolated price_position * 11) indexes D-minor pentatonic MIDI [50,53,55,57,60,62,65,67,69,72,74,77]; monotonic",
            "bass_pitch": "round(interpolated price_position * 5) indexes D-minor pentatonic MIDI [38,41,43,45,48,50]; monotonic",
            "price_boundaries": "minute 0 = session open; minute boundaries 1..389 = minute bars 0..388 close; boundary 390 = separate 16:00 closing_print (or final bar close if absent); normalized to session high/low; interpolate these boundaries for note onsets",
            "activity": "energy controls lead-onset count, kick syncopation, hat density and velocities; it is vendor-observed relative minute volume, not the complete consolidated tape",
            "timbre": "volatility controls lead harmonics and pad, bass and percussion brightness",
            "artistic_choices": "D-minor pentatonic, Dm7/Bbmaj7/Fmaj7/Cadd9 pad cycle with final Cadd9 hold, 80 BPM, rhythm cells, swing, short intro and 2-second fade",
            "llm_arrangement": "optional composition.sections set drum_density/pad_gain/lead_gain multipliers; pad/drum changes are sampled per bar, lead gain per onset; lead pitches remain data-derived",
            "midi": "five tracks (tempo/markers, lead, bass, pad, drums); dry note events; rendered synthesis and echoes are in WAV",
            "limits": "onsets interpolate correctly aligned price boundaries; volume/volatility use minute buckets; some motion between onsets is not audible; separate closing_print replaces only the price endpoint, without adding a minute; no forecast or causal claim",
        },
        "note_counts": {key: len(value) for key, value in notes.items()}, "bar_map": bar_map,
    }
    summary_path = output_dir / f"{prefix}_render.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {"wav": str(wav_path), "midi": str(midi_path), "summary": str(summary_path),
            "stems": stem_paths, "validation": summary["validation"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--stems", action="store_true", help="Also write four synchronized stereo WAV stems.")
    args = parser.parse_args()
    output_dir = args.output_dir or Path(__file__).resolve().parents[1] / "Tonight"
    print(json.dumps(render(args.analysis, output_dir, args.stems), indent=2))


if __name__ == "__main__":
    main()
