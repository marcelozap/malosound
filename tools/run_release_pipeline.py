#!/usr/bin/env python3
"""Run the local maloSound release provenance pipeline end to end."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import wave
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(REPO_ROOT / "manifests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "manifests"))

import audio_analysis_v1
import generator as manifest_generator
import package_release
import procedural_companion
import receipts_ed25519


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "malosound-release"


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def run_pipeline(
    *,
    audio: Path,
    title: str,
    slug: str,
    artist: str,
    rights_holder: str,
    source_type: str,
    royalty_bps: int,
    created_at: str,
    receipt_timestamp: str | None = None,
    manifest_created_at: str | None = None,
    package_created_at: str | None = None,
    receipts_path: Path | None = None,
    key_path: Path | None = None,
    release_root: Path | None = None,
    analysis_root: Path | None = None,
    companion_root: Path | None = None,
    manifest_root: Path | None = None,
) -> dict[str, object]:
    audio = resolve(audio)
    if not audio.exists() or not audio.is_file():
        raise FileNotFoundError(audio)

    analysis_path = (analysis_root or REPO_ROOT / "data" / "gold" / "audio_analysis") / f"{audio.stem}.audioanalysis.v1.json"
    companion_dir = (companion_root or REPO_ROOT / "scripts" / "strudel" / "tracks") / slug
    companion_path = companion_dir / "pattern.js"
    companion_metadata_path = companion_dir / "companion.json"
    receipts_path = receipts_path or REPO_ROOT / "data" / "receipts.jsonl"
    key_path = key_path or receipts_ed25519.DEFAULT_KEY
    manifest_path = (manifest_root or REPO_ROOT / "manifests") / f"{slug}.release_manifest_v1.json"
    release_root = release_root or REPO_ROOT / "releases"

    analysis = audio_analysis_v1.build_analysis(
        audio,
        source_type=source_type,
        owner=rights_holder,
        created_at=created_at,
    )
    audio_analysis_v1.validate_analysis(analysis)
    audio_analysis_v1.write_json(analysis_path, analysis)

    seed = receipts_ed25519.load_or_create_seed(key_path)
    receipt = receipts_ed25519.build_receipt(
        audio_path=audio,
        analysis_path=analysis_path,
        ledger_path=receipts_path,
        title=title,
        seed=seed,
        timestamp=receipt_timestamp,
    )
    receipts_ed25519.append_receipt(receipt, receipts_path)
    ledger_ok, ledger_errors = receipts_ed25519.verify_ledger(receipts_path)
    if not ledger_ok:
        raise ValueError(f"Ledger verification failed: {ledger_errors}")

    companion_metadata = procedural_companion.write_companion(
        analysis_path,
        companion_path,
        companion_metadata_path,
    )
    companion_ok, companion_hash = procedural_companion.verify_companion(analysis_path, companion_path)
    if not companion_ok:
        raise ValueError("Procedural companion verification failed")

    manifest = manifest_generator.build_manifest(
        manifest_generator.ReleaseInput(
            title=title,
            artist=artist,
            rights_holder=rights_holder,
            audio_path=audio,
            analysis_path=analysis_path,
            source_path=companion_path,
            receipts_path=receipts_path,
            output_path=manifest_path,
            royalty_bps=royalty_bps,
            ipfs_cid_stub="ipfs://CID_NOT_ASSIGNED_LOCAL_ONLY",
            created_at=manifest_created_at,
        )
    )
    manifest_generator.write_manifest(manifest, manifest_path)

    package = package_release.assemble_package(
        slug=slug,
        audio=audio,
        analysis=analysis_path,
        companion=companion_path,
        companion_metadata=companion_metadata_path,
        manifest=manifest_path,
        receipts=receipts_path,
        output_root=release_root,
        created_at=package_created_at,
    )

    return {
        "schema": "malosound.release_pipeline_run.v1",
        "title": title,
        "slug": slug,
        "audio": audio.as_posix(),
        "analysis": analysis_path.as_posix(),
        "receipt_record_hash": receipt["record_hash"],
        "ledger_ok": ledger_ok,
        "companion": companion_path.as_posix(),
        "companion_sha256": companion_hash,
        "companion_metadata": companion_metadata,
        "manifest": manifest_path.as_posix(),
        "release_package": (release_root / slug).as_posix(),
        "package": package,
    }


def self_test() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        audio = root / "Recorded" / "02_beat_grid_click.wav"
        audio.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(audio), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24_000)
            handle.writeframes(b"\x00\x00" * 24_000)

        result = run_pipeline(
            audio=audio,
            title="02 Beat Grid Click Fixture",
            slug="self-test-release",
            artist="maloSound",
            rights_holder="Marcelo Zapata",
            source_type="stem",
            royalty_bps=1000,
            created_at="1970-01-01T00:00:00+00:00",
            receipt_timestamp="1970-01-01T00:00:00+00:00",
            manifest_created_at="1970-01-01T00:00:00+00:00",
            package_created_at="1970-01-01T00:00:00+00:00",
            receipts_path=root / "data" / "receipts.jsonl",
            key_path=root / "data" / "keys" / "seed.hex",
            release_root=root / "releases",
            analysis_root=root / "data" / "gold" / "audio_analysis",
            companion_root=root / "scripts" / "strudel" / "tracks",
            manifest_root=root / "manifests",
        )
        assert result["ledger_ok"] is True
        assert Path(str(result["release_package"]), "PACKAGE_MANIFEST.json").exists()
    print("release pipeline self-test OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local maloSound release provenance pipeline.")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--title", default="maloSound Release")
    parser.add_argument("--slug")
    parser.add_argument("--artist", default="maloSound")
    parser.add_argument("--rights-holder", default="Marcelo Zapata")
    parser.add_argument("--source-type", default="stem")
    parser.add_argument("--royalty-bps", default=1000, type=int)
    parser.add_argument("--created-at", default="1970-01-01T00:00:00+00:00")
    parser.add_argument("--receipt-timestamp", help="Optional stable ISO timestamp for deterministic receipt fixtures.")
    parser.add_argument("--manifest-created-at", help="Optional stable ISO timestamp for deterministic manifest fixtures.")
    parser.add_argument("--package-created-at", help="Optional stable ISO timestamp for deterministic package fixtures.")
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--key", type=Path)
    parser.add_argument("--release-root", type=Path)
    parser.add_argument("--analysis-root", type=Path)
    parser.add_argument("--companion-root", type=Path)
    parser.add_argument("--manifest-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.audio is None:
        parser.error("--audio is required unless --self-test is set")

    result = run_pipeline(
        audio=args.audio,
        title=args.title,
        slug=args.slug or slugify(args.title),
        artist=args.artist,
        rights_holder=args.rights_holder,
        source_type=args.source_type,
        royalty_bps=args.royalty_bps,
        created_at=args.created_at,
        receipt_timestamp=args.receipt_timestamp,
        manifest_created_at=args.manifest_created_at,
        package_created_at=args.package_created_at,
        receipts_path=args.receipts,
        key_path=args.key,
        release_root=args.release_root,
        analysis_root=args.analysis_root,
        companion_root=args.companion_root,
        manifest_root=args.manifest_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
