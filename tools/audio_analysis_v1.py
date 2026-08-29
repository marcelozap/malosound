#!/usr/bin/env python3
"""Generate deterministic AudioAnalysisV1 JSON for local WAV files.

This analyzer intentionally reports only fields it can derive from bytes with
the Python standard library. It does not estimate LUFS, true peak, key, or
harmonic profile.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0.0"
ANALYSIS_VERSION = "malosound-baseline/1.0.0 (deterministic stdlib wav)"
SUPPORTED_SAMPLE_WIDTHS = {1, 2, 3, 4}
AUDIO_ANALYSIS_REQUIRED_KEYS = {
    "schema_version",
    "source_id",
    "source_type",
    "source_name",
    "duration_s",
    "sample_rate",
    "channels",
    "bit_depth",
    "audio_sha256",
    "onset_times",
    "energy_curve",
    "confidence",
    "model_versions",
    "provenance",
}
AUDIO_ANALYSIS_OPTIONAL_KEYS = {
    "analysis_note",
    "beat_times",
    "bpm",
    "created_at",
    "downbeat_times",
}
AUDIO_ANALYSIS_ALLOWED_KEYS = AUDIO_ANALYSIS_REQUIRED_KEYS | AUDIO_ANALYSIS_OPTIONAL_KEYS


@dataclass(frozen=True)
class WavData:
    path: Path
    frames: list[float]
    sample_rate: int
    channels: int
    sample_width: int

    @property
    def duration_s(self) -> float:
        return len(self.frames) / self.sample_rate if self.sample_rate else 0.0

    @property
    def bit_depth(self) -> int:
        return self.sample_width * 8


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def analysis_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def decode_sample(raw: bytes, sample_width: int) -> int:
    if sample_width == 1:
        return raw[0] - 128
    return int.from_bytes(raw, byteorder="little", signed=True)


def max_abs_for_width(sample_width: int) -> float:
    if sample_width == 1:
        return 128.0
    return float(2 ** ((sample_width * 8) - 1))


def read_wav_mono(path: Path) -> WavData:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frame_count = handle.getnframes()
        raw = handle.readframes(frame_count)

    if channels <= 0:
        raise ValueError(f"Invalid channel count: {channels}")
    if sample_rate <= 0:
        raise ValueError(f"Invalid sample rate: {sample_rate}")
    if sample_width not in SUPPORTED_SAMPLE_WIDTHS:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    stride = sample_width * channels
    scale = max_abs_for_width(sample_width)
    samples: list[float] = []
    for frame_start in range(0, len(raw), stride):
        total = 0.0
        for channel in range(channels):
            start = frame_start + channel * sample_width
            end = start + sample_width
            total += decode_sample(raw[start:end], sample_width) / scale
        samples.append(max(-1.0, min(1.0, total / channels)))
    return WavData(path=path, frames=samples, sample_rate=sample_rate, channels=channels, sample_width=sample_width)


def rms(values: list[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(value * value for value in values) / len(values))


def energy_curve(data: WavData, hop_s: float = 0.5) -> dict[str, Any]:
    hop = max(1, int(round(hop_s * data.sample_rate)))
    values = [
        round(rms(data.frames[start:start + hop]), 8)
        for start in range(0, len(data.frames), hop)
    ]
    return {"hop_s": hop_s, "rms": values}


def envelope_windows(data: WavData, window_s: float = 0.025) -> tuple[float, list[float]]:
    window = max(1, int(round(window_s * data.sample_rate)))
    envelope = [
        rms(data.frames[start:start + window])
        for start in range(0, len(data.frames), window)
    ]
    return window / data.sample_rate, envelope


def detect_onsets(data: WavData) -> list[float]:
    hop_s, envelope = envelope_windows(data)
    if not envelope:
        return []
    median = statistics.median(envelope)
    peak = max(envelope)
    threshold = max(median * 4.0, peak * 0.35, 0.02)
    refractory_windows = max(1, int(round(0.12 / hop_s)))
    onsets: list[float] = []
    last_index = -refractory_windows
    for index, value in enumerate(envelope):
        previous = envelope[index - 1] if index else 0.0
        next_value = envelope[index + 1] if index + 1 < len(envelope) else 0.0
        is_peak = value >= threshold and value >= previous and value >= next_value
        if is_peak and index - last_index >= refractory_windows:
            onsets.append(round(index * hop_s, 4))
            last_index = index
    return onsets


def estimate_bpm(onsets: list[float]) -> tuple[float | None, float]:
    if len(onsets) < 3:
        return None, 0.0
    intervals = [
        round(onsets[index + 1] - onsets[index], 4)
        for index in range(len(onsets) - 1)
        if 0.2 <= onsets[index + 1] - onsets[index] <= 2.0
    ]
    if not intervals:
        return None, 0.0
    interval = statistics.median(intervals)
    if interval <= 0:
        return None, 0.0
    bpm = 60.0 / interval
    while bpm < 60.0:
        bpm *= 2.0
    while bpm > 180.0:
        bpm /= 2.0
    spread = statistics.pstdev(intervals) if len(intervals) > 1 else 0.0
    confidence = max(0.0, min(1.0, 1.0 - (spread / interval if interval else 1.0)))
    return round(bpm, 2), round(confidence, 3)


def downbeats_from_beats(beat_times: list[float], beats_per_bar: int = 4) -> list[float]:
    return [time for index, time in enumerate(beat_times) if index % beats_per_bar == 0]


def build_analysis(path: Path, *, source_type: str, owner: str, created_at: str) -> dict[str, Any]:
    data = read_wav_mono(path)
    audio_hash = sha256_file(path)
    onsets = detect_onsets(data)
    bpm, bpm_confidence = estimate_bpm(onsets)
    beat_times = onsets if bpm else []

    analysis: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_id": audio_hash[:16],
        "source_type": source_type,
        "source_name": path.name,
        "duration_s": round(data.duration_s, 6),
        "sample_rate": data.sample_rate,
        "channels": data.channels,
        "bit_depth": data.bit_depth,
        "audio_sha256": audio_hash,
        "onset_times": onsets,
        "energy_curve": energy_curve(data),
        "confidence": {
            "bpm": bpm_confidence,
            "onsets": round(min(1.0, len(onsets) / max(1.0, data.duration_s * 2.0)), 3),
        },
        "model_versions": {
            "analysis": ANALYSIS_VERSION,
        },
        "provenance": {
            "owner": owner,
            "license": "all-rights-reserved",
            "consent": "self-recorded/owned catalog; analysis run by the owner",
        },
        "created_at": created_at,
        "analysis_note": "deterministic stdlib WAV analysis; loudness, peak, key, and harmonic profile not calculated",
    }
    if bpm is not None:
        analysis["bpm"] = bpm
        analysis["beat_times"] = beat_times
        analysis["downbeat_times"] = downbeats_from_beats(beat_times)
    return analysis


def validate_analysis(value: dict[str, Any]) -> None:
    missing = sorted(AUDIO_ANALYSIS_REQUIRED_KEYS - value.keys())
    if missing:
        raise ValueError(f"AudioAnalysisV1 missing required keys: {', '.join(missing)}")
    extra = sorted(key for key in value.keys() if key not in AUDIO_ANALYSIS_ALLOWED_KEYS)
    if extra:
        raise ValueError(f"AudioAnalysisV1 contains unknown fields: {', '.join(extra)}")
    forbidden = {"lufs", "integrated_loudness_lufs", "true_peak", "true_peak_dbtp", "key", "harmonic_profile"}
    present_forbidden = sorted(forbidden & {key.lower() for key in value.keys()})
    if present_forbidden:
        raise ValueError(f"AudioAnalysisV1 contains uncalculated fields: {', '.join(present_forbidden)}")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def self_test() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "02_beat_grid_click.wav"
        sample_rate = 24_000
        samples = bytearray()
        for index in range(sample_rate * 2):
            t = index / sample_rate
            phase = t % 0.5
            sample = 0.0
            if phase < 0.025:
                sample = 0.7 * math.sin(2.0 * math.pi * 1200.0 * phase)
            samples.extend(int(sample * 32767.0).to_bytes(2, byteorder="little", signed=True))
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(bytes(samples))
        analysis = build_analysis(
            path,
            source_type="stem",
            owner="Marcelo Zapata",
            created_at="1970-01-01T00:00:00+00:00",
        )
        validate_analysis(analysis)
        assert analysis_sha256(analysis) == analysis_sha256(analysis)
        assert analysis["source_name"] == path.name
        assert analysis["sample_rate"] == sample_rate
        assert analysis.get("bpm") == 120.0
        lower_keys = {key.lower() for key in analysis}
        assert "lufs" not in lower_keys
        assert "true_peak" not in lower_keys
    print("audio analysis v1 self-test OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic AudioAnalysisV1 JSON for a WAV file.")
    parser.add_argument("audio", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-type", default="stem")
    parser.add_argument("--owner", default="Marcelo Zapata")
    parser.add_argument(
        "--created-at",
        default="1970-01-01T00:00:00+00:00",
        help="Stable timestamp to keep analysis JSON byte-deterministic. Pass an explicit ISO value to override.",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.audio is None:
        parser.error("audio is required unless --self-test is set")

    audio = args.audio.resolve()
    output = args.output or (Path.cwd() / f"{audio.stem}.audioanalysis.v1.json")
    analysis = build_analysis(audio, source_type=args.source_type, owner=args.owner, created_at=args.created_at)
    validate_analysis(analysis)
    write_json(output, analysis)
    print(f"Wrote {output}")
    print(f"SHA-256: {analysis['audio_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
