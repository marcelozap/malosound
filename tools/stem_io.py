#!/usr/bin/env python3
"""Ingest and export MaloSound stem kit manifests.

Audio bytes stay local and outside git. This utility validates a generated stem
folder, records stable hashes, and can export a lightweight routing manifest for
Ableton/Max for Live or the XIV StateGraph.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = "malosound.stem_manifest.v1"
SUPPORTED_AUDIO = {".wav"}


@dataclass(frozen=True)
class StemRecord:
    file: str
    role: str
    sha256: str
    bytes: int
    duration_seconds: float
    sample_rate: int
    channels: int
    route_target: str
    tags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "role": self.role,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "duration_seconds": self.duration_seconds,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "route_target": self.route_target,
            "tags": list(self.tags),
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wav_metadata(path: Path) -> tuple[float, int, int]:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()
    duration = frames / sample_rate if sample_rate else 0.0
    return round(duration, 6), sample_rate, channels


def infer_role(path: Path) -> str:
    stem = path.stem.lower()
    if stem[:3].isdigit() and "_" in stem:
        stem = stem.split("_", 1)[1]
    return stem.replace("-", "_")


def route_for(role: str) -> str:
    if role in {"count_in", "beat_grid", "click"}:
        return "ableton.return.click"
    if role in {"sidechain_pulse", "sidechain"}:
        return "ableton.return.sidechain"
    if "movement" in role:
        return "maxforlive.input.movement"
    if "vocal" in role:
        return "ableton.track.vocal_reference"
    return f"ableton.track.{role}"


def tags_for(role: str) -> tuple[str, ...]:
    tags = ["malosound", "stem", role]
    if role in {"count_in", "beat_grid", "sidechain_pulse"}:
        tags.append("utility")
    if "movement" in role:
        tags.append("gesture")
    if "vocal" in role:
        tags.append("voice")
    return tuple(tags)


def ingest_stems(folder: Path) -> dict[str, Any]:
    if not folder.exists():
        raise FileNotFoundError(folder)
    records: list[StemRecord] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_AUDIO:
            continue
        role = infer_role(path)
        duration, sample_rate, channels = wav_metadata(path)
        records.append(
            StemRecord(
                file=path.name,
                role=role,
                sha256=sha256_file(path),
                bytes=path.stat().st_size,
                duration_seconds=duration,
                sample_rate=sample_rate,
                channels=channels,
                route_target=route_for(role),
                tags=tags_for(role),
            )
        )
    if not records:
        raise ValueError(f"No supported audio stems found in {folder}")
    return {
        "schema": SCHEMA,
        "folder": str(folder.resolve()),
        "stem_count": len(records),
        "stems": [record.to_dict() for record in records],
    }


def write_manifest(manifest: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def self_test() -> int:
    import importlib.util
    import sys
    import tempfile

    generator_path = Path(__file__).resolve().parents[1] / "scripts" / "generate-stem-kit.py"
    spec = importlib.util.spec_from_file_location("generate_stem_kit", generator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load stem generator: {generator_path}")
    generate_stem_kit = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = generate_stem_kit
    spec.loader.exec_module(generate_stem_kit)

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "Generated Stems"
        stems = generate_stem_kit.render_stems(folder, bpm=100.0, bars=1, beats_per_bar=4, sample_rate=24000)
        generate_stem_kit.write_manifest(folder, "stem-io-self-test", 100.0, 1, 4, 24000, stems)
        manifest = ingest_stems(folder)
        assert manifest["schema"] == SCHEMA
        assert manifest["stem_count"] == 6
        assert all(stem["sha256"] for stem in manifest["stems"])
        assert any(stem["route_target"] == "maxforlive.input.movement" for stem in manifest["stems"])
    print("stem io self-test OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest/export MaloSound stem manifests.")
    parser.add_argument("folder", nargs="?", type=Path, help="Folder containing WAV stems.")
    parser.add_argument("--output", type=Path, help="Manifest output path.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.folder is None:
        parser.error("folder is required unless --self-test is set")

    manifest = ingest_stems(args.folder)
    output = args.output or (args.folder / "stem-manifest.json")
    write_manifest(manifest, output)
    print(f"Wrote {output}")
    print(f"Stems: {manifest['stem_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
