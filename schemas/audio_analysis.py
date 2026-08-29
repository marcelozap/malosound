#!/usr/bin/env python3
"""Validate maloSound AudioAnalysisV1 JSON documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0.0"

REQUIRED_KEYS = {
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
    "beat_times",
}

OPTIONAL_KEYS = {
    "analysis_note",
    "band_energy",
    "bpm",
    "created_at",
    "downbeat_times",
    "rms",
    "spectral_rolloff_hz",
    "zero_crossing_rate",
}

FORBIDDEN_KEYS = {
    "lufs",
    "integrated_loudness_lufs",
    "true_peak",
    "true_peak_dbtp",
    "key",
    "harmonic_profile",
}

ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS


def read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def require_number(value: Any, label: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")


def require_number_list(value: Any, label: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    for index, item in enumerate(value):
        require_number(item, f"{label}[{index}]")


def validate_document(value: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_KEYS - value.keys())
    if missing:
        raise ValueError(f"AudioAnalysisV1 missing required keys: {', '.join(missing)}")

    extra = sorted(key for key in value if key not in ALLOWED_KEYS)
    if extra:
        raise ValueError(f"AudioAnalysisV1 contains unknown fields: {', '.join(extra)}")

    forbidden = sorted(FORBIDDEN_KEYS & {key.lower() for key in value})
    if forbidden:
        raise ValueError(f"AudioAnalysisV1 contains uncalculated fields: {', '.join(forbidden)}")

    if value["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")

    for key in ("source_id", "source_type", "source_name", "audio_sha256"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError(f"{key} must be a non-empty string")

    require_number(value["duration_s"], "duration_s")
    require_number(value["sample_rate"], "sample_rate")
    require_number(value["channels"], "channels")
    if value["bit_depth"] is not None:
        require_number(value["bit_depth"], "bit_depth")
    require_number_list(value["onset_times"], "onset_times")
    require_number_list(value["beat_times"], "beat_times")

    confidence = value["confidence"]
    if not isinstance(confidence, dict):
        raise ValueError("confidence must be an object")
    for required in ("bpm", "onsets"):
        require_number(confidence.get(required), f"confidence.{required}")

    model_versions = value["model_versions"]
    if not isinstance(model_versions, dict) or not model_versions.get("analysis"):
        raise ValueError("model_versions.analysis is required")

    provenance = value["provenance"]
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be an object")
    for required in ("owner", "license", "consent"):
        if not isinstance(provenance.get(required), str) or not provenance[required]:
            raise ValueError(f"provenance.{required} is required")

    energy_curve = value["energy_curve"]
    if not isinstance(energy_curve, dict):
        raise ValueError("energy_curve must be an object")
    require_number(energy_curve.get("hop_s"), "energy_curve.hop_s")
    require_number_list(energy_curve.get("rms"), "energy_curve.rms")

    if "zero_crossing_rate" in value:
        zcr = value["zero_crossing_rate"]
        if not isinstance(zcr, dict):
            raise ValueError("zero_crossing_rate must be an object")
        require_number(zcr.get("hop_s"), "zero_crossing_rate.hop_s")
        require_number_list(zcr.get("values"), "zero_crossing_rate.values")

    if "spectral_rolloff_hz" in value:
        rolloff = value["spectral_rolloff_hz"]
        if not isinstance(rolloff, dict):
            raise ValueError("spectral_rolloff_hz must be an object")
        require_number(rolloff.get("hop_s"), "spectral_rolloff_hz.hop_s")
        require_number(rolloff.get("percentile"), "spectral_rolloff_hz.percentile")
        require_number_list(rolloff.get("values"), "spectral_rolloff_hz.values")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AudioAnalysisV1 JSON.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    validate_document(read_json_object(args.path))
    print(f"AudioAnalysisV1 OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
