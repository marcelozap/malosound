#!/usr/bin/env python3
"""Generate AudioAnalysisV1 from ffmpeg-decoded audio."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from schemas.audio_analysis import validate_document


SCHEMA_VERSION = "1.0.0"
ANALYSIS_VERSION = "malosound-ffmpeg-numpy/1.0.0"


@dataclass
class WindowAccumulator:
    window_size: int
    reducer: Callable[[np.ndarray], float]
    values: list[float]
    remainder: np.ndarray

    @classmethod
    def create(cls, window_size: int, reducer: Callable[[np.ndarray], float]) -> "WindowAccumulator":
        return cls(window_size=window_size, reducer=reducer, values=[], remainder=np.array([], dtype=np.float32))

    def push(self, samples: np.ndarray) -> None:
        if self.remainder.size:
            samples = np.concatenate((self.remainder, samples))
        usable = (samples.size // self.window_size) * self.window_size
        if usable:
            frames = samples[:usable].reshape((-1, self.window_size))
            for frame in frames:
                self.values.append(round(float(self.reducer(frame)), 8))
        self.remainder = samples[usable:].copy()

    def finish(self) -> None:
        if self.remainder.size:
            self.values.append(round(float(self.reducer(self.remainder)), 8))
            self.remainder = np.array([], dtype=np.float32)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} is required for MP3 decode")


def ffprobe_audio(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,format_name",
        "-show_entries",
        "stream=index,codec_name,codec_type,sample_rate,channels,bit_rate",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    streams = [stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"]
    if not streams:
        raise ValueError(f"No audio stream found: {path}")
    stream = streams[0]
    return {
        "codec": stream.get("codec_name"),
        "format": data.get("format", {}).get("format_name"),
        "duration_s": float(data.get("format", {}).get("duration", 0.0)),
        "size": int(data.get("format", {}).get("size", 0)),
        "sample_rate": int(stream.get("sample_rate")),
        "channels": int(stream.get("channels")),
        "bit_rate": int(stream.get("bit_rate", 0)) if stream.get("bit_rate") else None,
    }


def rms(frame: np.ndarray) -> float:
    if frame.size == 0:
        return 0.0
    return math.sqrt(float(np.mean(frame * frame)))


def zero_crossing_rate(frame: np.ndarray) -> float:
    if frame.size < 2:
        return 0.0
    signs = np.signbit(frame)
    return float(np.count_nonzero(signs[1:] != signs[:-1]) / (frame.size - 1))


def spectral_rolloff(frame: np.ndarray, sample_rate: int, percentile: float = 0.85) -> float:
    if frame.size < 2:
        return 0.0
    if frame.size > 4096:
        start = (frame.size - 4096) // 2
        frame = frame[start:start + 4096]
    windowed = frame * np.hanning(frame.size)
    spectrum = np.abs(np.fft.rfft(windowed))
    total = float(np.sum(spectrum))
    if total <= 0.0:
        return 0.0
    threshold = total * percentile
    cumulative = np.cumsum(spectrum)
    index = int(np.searchsorted(cumulative, threshold, side="left"))
    frequency = index * sample_rate / frame.size
    return frequency


def detect_onsets(envelope: list[float], hop_s: float) -> list[float]:
    if not envelope:
        return []
    median = statistics.median(envelope)
    peak = max(envelope)
    threshold = max(median * 3.0, peak * 0.18, 0.01)
    refractory = max(1, int(round(0.11 / hop_s)))
    onsets: list[float] = []
    last_index = -refractory
    for index, value in enumerate(envelope):
        previous = envelope[index - 1] if index else 0.0
        next_value = envelope[index + 1] if index + 1 < len(envelope) else 0.0
        if value >= threshold and value >= previous and value >= next_value and index - last_index >= refractory:
            onsets.append(round(index * hop_s, 4))
            last_index = index
    return onsets


def estimate_bpm(onsets: list[float]) -> tuple[float | None, float]:
    if len(onsets) < 4:
        return None, 0.0
    intervals = [
        onsets[index + 1] - onsets[index]
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
    confidence = max(0.0, min(1.0, 1.0 - spread / interval))
    return round(bpm, 2), round(confidence, 3)


def downbeats_from_beats(beat_times: list[float], beats_per_bar: int = 4) -> list[float]:
    return [time for index, time in enumerate(beat_times) if index % beats_per_bar == 0]


def decode_features(path: Path, sample_rate: int) -> dict[str, Any]:
    require_tool("ffmpeg")
    energy_hop_s = 0.5
    onset_hop_s = 0.025
    rolloff_hop_s = 0.5
    energy = WindowAccumulator.create(int(round(sample_rate * energy_hop_s)), rms)
    onset = WindowAccumulator.create(int(round(sample_rate * onset_hop_s)), rms)
    zcr = WindowAccumulator.create(int(round(sample_rate * energy_hop_s)), zero_crossing_rate)
    rolloff = WindowAccumulator.create(
        int(round(sample_rate * rolloff_hop_s)),
        lambda frame: spectral_rolloff(frame, sample_rate),
    )

    total_square = 0.0
    total_samples = 0
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    if process.stdout is None:
        raise RuntimeError("ffmpeg stdout was not available")

    while True:
        raw = process.stdout.read(4 * sample_rate)
        if not raw:
            break
        usable = len(raw) - (len(raw) % 4)
        if usable == 0:
            continue
        samples = np.frombuffer(raw[:usable], dtype=np.float32).copy()
        samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        total_square += float(np.sum(samples * samples))
        total_samples += int(samples.size)
        energy.push(samples)
        onset.push(samples)
        zcr.push(samples)
        rolloff.push(samples)

    code = process.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg decode failed with exit code {code}")

    for accumulator in (energy, onset, zcr, rolloff):
        accumulator.finish()

    onsets = detect_onsets(onset.values, onset_hop_s)
    bpm, bpm_confidence = estimate_bpm(onsets)
    beat_times = onsets
    return {
        "decoded_samples": total_samples,
        "overall_rms": round(math.sqrt(total_square / total_samples), 8) if total_samples else 0.0,
        "energy_curve": {"hop_s": energy_hop_s, "rms": energy.values},
        "onset_times": onsets,
        "beat_times": beat_times,
        "downbeat_times": downbeats_from_beats(beat_times),
        "bpm": bpm,
        "bpm_confidence": bpm_confidence,
        "onset_confidence": round(min(1.0, len(onsets) / max(1.0, (total_samples / sample_rate) * 2.0)), 3),
        "zero_crossing_rate": {"hop_s": energy_hop_s, "values": zcr.values},
        "spectral_rolloff_hz": {"hop_s": rolloff_hop_s, "percentile": 0.85, "values": rolloff.values},
    }


def build_analysis(
    path: Path,
    *,
    source_type: str,
    owner: str,
    license_text: str,
    consent: str,
    created_at: str,
) -> dict[str, Any]:
    probe = ffprobe_audio(path)
    features = decode_features(path, int(probe["sample_rate"]))
    audio_hash = sha256_file(path)
    analysis = {
        "schema_version": SCHEMA_VERSION,
        "source_id": audio_hash[:16],
        "source_type": source_type,
        "source_name": path.name,
        "duration_s": round(float(probe["duration_s"]), 6),
        "sample_rate": int(probe["sample_rate"]),
        "channels": int(probe["channels"]),
        "bit_depth": None,
        "audio_sha256": audio_hash,
        "rms": features["overall_rms"],
        "onset_times": features["onset_times"],
        "beat_times": features["beat_times"],
        "downbeat_times": features["downbeat_times"],
        "bpm": features["bpm"],
        "energy_curve": features["energy_curve"],
        "zero_crossing_rate": features["zero_crossing_rate"],
        "spectral_rolloff_hz": features["spectral_rolloff_hz"],
        "confidence": {
            "bpm": features["bpm_confidence"],
            "onsets": features["onset_confidence"],
        },
        "model_versions": {
            "analysis": ANALYSIS_VERSION,
            "decoder": "ffmpeg",
            "feature_runtime": f"numpy/{np.__version__}",
        },
        "provenance": {
            "owner": owner,
            "license": license_text,
            "consent": consent,
        },
        "created_at": created_at,
        "analysis_note": (
            "ffmpeg-decoded mono float32 analysis of compressed audio; bit_depth is null "
            "because MP3 has no stable PCM bit depth. LUFS, true peak, key, and harmonic "
            "profile are intentionally not calculated."
        ),
    }
    validate_document(analysis)
    return analysis


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AudioAnalysisV1 via ffmpeg decode.")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-type", default="recording")
    parser.add_argument("--owner", default="Project XIV / maloSound")
    parser.add_argument("--license", default="all-rights-reserved")
    parser.add_argument("--consent", default="self-recorded/owned catalog; analysis run by the owner")
    parser.add_argument("--created-at", default="2026-08-26T21:08:00-04:00")
    args = parser.parse_args()

    analysis = build_analysis(
        args.audio,
        source_type=args.source_type,
        owner=args.owner,
        license_text=args.license,
        consent=args.consent,
        created_at=args.created_at,
    )
    write_json(args.output, analysis)
    print(f"Wrote {args.output}")
    print(f"Audio SHA-256: {analysis['audio_sha256']}")
    print(f"BPM: {analysis.get('bpm')} confidence={analysis['confidence']['bpm']}")
    print(f"Beats: {len(analysis['beat_times'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
