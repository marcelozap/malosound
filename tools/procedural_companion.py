#!/usr/bin/env python3
"""Generate a deterministic Strudel companion from AudioAnalysisV1 JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "scripts" / "strudel" / "tracks" / "provenance-fixture" / "pattern.js"
DEFAULT_METADATA = REPO_ROOT / "scripts" / "strudel" / "tracks" / "provenance-fixture" / "companion.json"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def source_hash(analysis: dict[str, Any]) -> str:
    audio_hash = analysis.get("audio_sha256") or analysis.get("source_id")
    if not isinstance(audio_hash, str) or not audio_hash:
        raise ValueError("AudioAnalysisV1 needs audio_sha256 or source_id for companion hashing")
    return audio_hash


def clamp_bpm(value: Any) -> int:
    try:
        bpm = float(value)
    except (TypeError, ValueError):
        bpm = 96.0
    return max(60, min(180, int(round(bpm))))


def pattern_from_hash(value: str) -> dict[str, str]:
    seed = hashlib.sha256(value.encode("utf-8")).hexdigest()
    kicks = [
        "bd ~ bd ~",
        "bd ~ ~ bd",
        "bd ~ bd bd",
        "bd [~ bd] bd ~",
    ]
    snares = [
        "~ sd ~ sd",
        "~ [sd ~] ~ sd",
        "~ clap ~ sd",
        "~ sd:2 ~ clap",
    ]
    hats = [
        "hh*8",
        "[~ hh]*4",
        "hh*4 oh*2",
        "[hh hh ~ hh]*2",
    ]
    bass = [
        "c2 ~ eb2 g1",
        "c2 bb1 ~ g1",
        "c2 ~ g1 bb1",
        "c2 eb2 g1 ~",
    ]
    return {
        "kick": kicks[int(seed[0:2], 16) % len(kicks)],
        "snare": snares[int(seed[2:4], 16) % len(snares)],
        "hat": hats[int(seed[4:6], 16) % len(hats)],
        "bass": bass[int(seed[6:8], 16) % len(bass)],
    }


def build_pattern(analysis: dict[str, Any]) -> str:
    bpm = clamp_bpm(analysis.get("bpm"))
    seed_hash = source_hash(analysis)
    parts = pattern_from_hash(seed_hash)
    source_name = str(analysis.get("source_name", "unknown"))
    source_id = str(analysis.get("source_id", seed_hash[:16]))
    return "\n".join(
        [
            "// maloSound provenance companion",
            f"// source_name: {source_name}",
            f"// source_id: {source_id}",
            f"// source_hash: {seed_hash}",
            "// Generated deterministically from AudioAnalysisV1. Edit only after re-hashing.",
            "",
            f"setcpm({bpm / 4:.6g})",
            "",
            "stack(",
            f"  s(\"{parts['kick']}\").bank(\"RolandTR909\").gain(0.9),",
            f"  s(\"{parts['snare']}\").bank(\"RolandTR909\").gain(0.55),",
            f"  s(\"{parts['hat']}\").bank(\"RolandTR909\").gain(0.32),",
            f"  note(\"{parts['bass']}\").s(\"sawtooth\").lpf(520).gain(0.38)",
            ")",
            "",
        ]
    )


def write_companion(analysis_path: Path, output_path: Path, metadata_path: Path) -> dict[str, Any]:
    analysis = read_json_object(analysis_path)
    pattern = build_pattern(analysis)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(pattern, encoding="utf-8", newline="\n")
    metadata = {
        "schema": "malosound.procedural_companion.v1",
        "analysis_path": analysis_path.as_posix(),
        "analysis_sha256": sha256_file(analysis_path),
        "pattern_path": output_path.as_posix(),
        "pattern_sha256": sha256_file(output_path),
        "determinism": "same AudioAnalysisV1 source hash produces identical pattern text",
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return metadata


def verify_companion(analysis_path: Path, output_path: Path) -> tuple[bool, str]:
    expected = build_pattern(read_json_object(analysis_path))
    actual = output_path.read_text(encoding="utf-8")
    return expected == actual, sha256_file(output_path)


def self_test() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        analysis = root / "analysis.json"
        output = root / "pattern.js"
        metadata = root / "companion.json"
        analysis.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "source_id": "fixture",
                    "source_name": "02_beat_grid_click.wav",
                    "audio_sha256": "a" * 64,
                    "bpm": 104.35,
                }
            ),
            encoding="utf-8",
        )
        first = write_companion(analysis, output, metadata)
        ok, pattern_hash = verify_companion(analysis, output)
        assert ok
        second = write_companion(analysis, output, metadata)
        assert first["pattern_sha256"] == second["pattern_sha256"] == pattern_hash
    print("procedural companion self-test OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify a deterministic Strudel companion.")
    parser.add_argument("--analysis", type=Path, required=False)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.analysis is None:
        parser.error("--analysis is required unless --self-test is set")

    if args.verify:
        ok, pattern_hash = verify_companion(args.analysis, args.output)
        if not ok:
            print(f"companion mismatch: {args.output}")
            return 1
        print(f"companion OK: {args.output} sha256={pattern_hash}")
        return 0

    metadata = write_companion(args.analysis, args.output, args.metadata)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
