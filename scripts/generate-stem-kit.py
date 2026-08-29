#!/usr/bin/env python3
"""Generate local MaloSound utility stems for a recording session.

The output is deliberately simple and deterministic: click/count-in, sidechain
pulse, movement cue tones, and silence beds. These are helper stems, not music.
They are written under projects/ by default, which is ignored by git.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"


@dataclass(frozen=True)
class StemSpec:
    file_name: str
    role: str
    description: str


STEMS: tuple[StemSpec, ...] = (
    StemSpec("01_count_in_click.wav", "count_in", "One bar of count-in clicks before the take."),
    StemSpec("02_beat_grid_click.wav", "beat_grid", "Full-length click with accented downbeats."),
    StemSpec("03_sidechain_pulse.wav", "sidechain_pulse", "Low pulse on every beat for sidechain or visual testing."),
    StemSpec("04_movement_cues.wav", "movement_cues", "Short high/low cue tones for open, stop, and turn markers."),
    StemSpec("05_vocal_space_silence.wav", "vocal_space", "Silent bed for aligning a vocal recording lane."),
    StemSpec("06_movement_video_silence.wav", "movement_video", "Silent bed for aligning movement/video capture."),
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "studio-session"


def clamp16(value: float) -> int:
    return max(-32768, min(32767, int(round(value * 32767.0))))


def seconds_for_bars(bpm: float, bars: int, beats_per_bar: int) -> float:
    return (60.0 / bpm) * bars * beats_per_bar


def write_wav(path: Path, samples: list[float], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            frames.extend(int(clamp16(sample)).to_bytes(2, byteorder="little", signed=True))
        handle.writeframes(bytes(frames))


def add_tone(samples: list[float], sample_rate: int, start_seconds: float, duration_seconds: float, freq: float, amp: float) -> None:
    start = max(0, int(round(start_seconds * sample_rate)))
    length = max(1, int(round(duration_seconds * sample_rate)))
    end = min(len(samples), start + length)
    for i in range(start, end):
        t = (i - start) / sample_rate
        envelope = min(1.0, (end - i) / max(1, int(0.01 * sample_rate)))
        samples[i] += amp * envelope * math.sin(2.0 * math.pi * freq * t)


def add_click(samples: list[float], sample_rate: int, start_seconds: float, accent: bool) -> None:
    freq = 1800.0 if accent else 1200.0
    amp = 0.65 if accent else 0.42
    add_tone(samples, sample_rate, start_seconds, 0.025, freq, amp)


def add_pulse(samples: list[float], sample_rate: int, start_seconds: float) -> None:
    start = max(0, int(round(start_seconds * sample_rate)))
    length = max(1, int(round(0.12 * sample_rate)))
    end = min(len(samples), start + length)
    for i in range(start, end):
        t = (i - start) / sample_rate
        env = math.exp(-t / 0.045)
        samples[i] += 0.45 * env * math.sin(2.0 * math.pi * 72.0 * t)


def empty(duration_seconds: float, sample_rate: int) -> list[float]:
    return [0.0] * max(1, int(round(duration_seconds * sample_rate)))


def beat_times(bpm: float, bars: int, beats_per_bar: int, offset_beats: int = 0) -> list[tuple[int, float]]:
    seconds_per_beat = 60.0 / bpm
    return [
        (beat, (beat + offset_beats) * seconds_per_beat)
        for beat in range(bars * beats_per_bar)
    ]


def render_stems(output: Path, bpm: float, bars: int, beats_per_bar: int, sample_rate: int) -> list[dict[str, object]]:
    duration = seconds_for_bars(bpm, bars, beats_per_bar)
    one_bar = seconds_for_bars(bpm, 1, beats_per_bar)
    rows: list[dict[str, object]] = []

    count_in = empty(one_bar, sample_rate)
    for beat, t in beat_times(bpm, 1, beats_per_bar):
        add_click(count_in, sample_rate, t, accent=beat == 0)
    write_wav(output / STEMS[0].file_name, count_in, sample_rate)

    click = empty(duration, sample_rate)
    for beat, t in beat_times(bpm, bars, beats_per_bar):
        add_click(click, sample_rate, t, accent=beat % beats_per_bar == 0)
    write_wav(output / STEMS[1].file_name, click, sample_rate)

    pulse = empty(duration, sample_rate)
    for _, t in beat_times(bpm, bars, beats_per_bar):
        add_pulse(pulse, sample_rate, t)
    write_wav(output / STEMS[2].file_name, pulse, sample_rate)

    cues = empty(duration, sample_rate)
    cue_points = [
        (0.0, 880.0),
        (duration * 0.25, 660.0),
        (duration * 0.5, 990.0),
        (duration * 0.75, 550.0),
    ]
    for t, freq in cue_points:
        add_tone(cues, sample_rate, t, 0.08, freq, 0.35)
    write_wav(output / STEMS[3].file_name, cues, sample_rate)

    write_wav(output / STEMS[4].file_name, empty(duration, sample_rate), sample_rate)
    write_wav(output / STEMS[5].file_name, empty(duration, sample_rate), sample_rate)

    for spec in STEMS:
        path = output / spec.file_name
        rows.append(
            {
                "file": spec.file_name,
                "role": spec.role,
                "description": spec.description,
                "sample_rate": sample_rate,
                "channels": 1,
                "format": "16-bit PCM WAV",
                "duration_seconds": round(one_bar if spec.role == "count_in" else duration, 6),
                "bytes": path.stat().st_size,
            }
        )
    return rows


def write_manifest(output: Path, session_name: str, bpm: float, bars: int, beats_per_bar: int, sample_rate: int, stems: list[dict[str, object]]) -> None:
    manifest = {
        "schema": "malosound.stem_kit.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "session": session_name,
        "bpm": bpm,
        "bars": bars,
        "beats_per_bar": beats_per_bar,
        "sample_rate": sample_rate,
        "repo_rule": "audio bytes stay out of git; this folder is under ignored projects/",
        "stems": stems,
    }
    (output / "stem-kit.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = [
        "# MaloSound Stem Kit",
        "",
        f"- Session: {session_name}",
        f"- BPM: {bpm:g}",
        f"- Bars: {bars}",
        f"- Beats per bar: {beats_per_bar}",
        f"- Sample rate: {sample_rate}",
        "- Boundary: generated audio lives under ignored `projects/`; do not commit WAVs.",
        "",
        "## Stems",
        "",
        "| File | Role | Use |",
        "|---|---|---|",
    ]
    for stem in stems:
        lines.append(f"| `{stem['file']}` | {stem['role']} | {stem['description']} |")
    lines.extend(
        [
            "",
            "## DAW Move",
            "",
            "Import these as separate tracks, set the project tempo first, then record the vocal and movement pass against them.",
            "The click and pulse are disposable scaffolding. The vocal, movement, and actual drums are the record.",
            "",
        ]
    )
    (output / "STEMS.md").write_text("\n".join(lines), encoding="utf-8")


def default_output(session_name: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d")
    return PROJECTS / f"{stamp}_{slugify(session_name)}" / "Generated Stems"


def self_test() -> int:
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / "Generated Stems"
        stems = render_stems(out, bpm=106.0, bars=2, beats_per_bar=4, sample_rate=24000)
        write_manifest(out, "self-test", 106.0, 2, 4, 24000, stems)
        expected = {spec.file_name for spec in STEMS} | {"stem-kit.json", "STEMS.md"}
        actual = {path.name for path in out.iterdir()}
        if expected != actual:
            raise AssertionError(f"missing outputs: {sorted(expected - actual)}")
        with wave.open(str(out / "02_beat_grid_click.wav"), "rb") as handle:
            assert handle.getnchannels() == 1
            assert handle.getsampwidth() == 2
            assert handle.getframerate() == 24000
            assert handle.getnframes() > 0
        data = json.loads((out / "stem-kit.json").read_text(encoding="utf-8"))
        assert data["schema"] == "malosound.stem_kit.v1"
        assert len(data["stems"]) == len(STEMS)
    print("stem kit self-test OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local utility stems for a MaloSound recording session.")
    parser.add_argument("--session", default="my-friend-first-pass")
    parser.add_argument("--bpm", type=float, default=106.0)
    parser.add_argument("--bars", type=int, default=16)
    parser.add_argument("--beats-per-bar", type=int, default=4)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--output", type=Path, help="Output folder. Defaults under ignored projects/.")
    parser.add_argument("--dry-run", action="store_true", help="Print the output plan without writing files.")
    parser.add_argument("--self-test", action="store_true", help="Generate into a temp directory and validate the result.")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if args.bpm <= 0:
        raise ValueError("--bpm must be positive")
    if args.bars <= 0:
        raise ValueError("--bars must be positive")
    if args.beats_per_bar <= 0:
        raise ValueError("--beats-per-bar must be positive")
    if args.sample_rate < 8000:
        raise ValueError("--sample-rate must be at least 8000")

    output = args.output or default_output(args.session)
    if not output.is_absolute():
        output = ROOT / output

    print(f"Session: {args.session}")
    print(f"Output: {output}")
    print("Stems:")
    for spec in STEMS:
        print(f"- {spec.file_name}: {spec.description}")

    if args.dry_run:
        return 0

    output.mkdir(parents=True, exist_ok=True)
    stems = render_stems(output, args.bpm, args.bars, args.beats_per_bar, args.sample_rate)
    write_manifest(output, args.session, args.bpm, args.bars, args.beats_per_bar, args.sample_rate, stems)
    print(f"Wrote {len(stems)} WAV stems plus stem-kit.json and STEMS.md")
    print("Boundary: output is under ignored projects/ by default; audio bytes stay out of git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
