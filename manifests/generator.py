#!/usr/bin/env python3
"""Generate local maloSound release manifests.

The manifest is an offline provenance artifact. It keeps ERC-2981-compatible
royalty metadata in a file shape without deploying contracts, connecting
wallets, minting tokens, or uploading assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "manifests" / "release_manifest_v1.json"
DEFAULT_RECEIPTS = REPO_ROOT / "data" / "receipts.jsonl"
SCHEMA_VERSION = "malosound.release_manifest.v1"
ROYALTY_DENOMINATOR_BPS = 10_000

AUDIO_ANALYSIS_REQUIRED_KEYS = {
    "schema_version",
    "source_id",
    "source_type",
    "source_name",
    "duration_s",
    "sample_rate",
    "confidence",
    "model_versions",
    "provenance",
}

AUDIO_ANALYSIS_OPTIONAL_VERIFIED_KEYS = {
    "audio_sha256",
    "bit_depth",
    "bpm",
    "beat_times",
    "channels",
    "created_at",
    "downbeat_times",
    "onset_times",
    "energy_curve",
    "band_energy",
    "rms",
    "spectral_rolloff_hz",
    "zero_crossing_rate",
    "analysis_note",
}


@dataclass(frozen=True)
class ReleaseInput:
    title: str
    artist: str
    rights_holder: str
    audio_path: Path
    analysis_path: Path
    source_path: Path
    receipts_path: Path
    output_path: Path
    royalty_bps: int
    ipfs_cid_stub: str
    created_at: str | None = None
    project_name: str = "Project XIV / maloSound"
    release_type: str = "bedroom_funk_rnb_provenance_poc"
    artist_slug: str | None = None
    artist_public_key: str | None = None
    artist_key_fingerprint: str | None = None


def resolve_path(path: Path, *, root: Path = REPO_ROOT) -> Path:
    return path if path.is_absolute() else root / path


def portable_path(path: Path, *, root: Path = REPO_ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_latest_jsonl(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    latest: dict[str, Any] | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"Receipt line {line_number} is not a JSON object: {path}")
            latest = value
    return latest


def require_existing_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{label} is not a file: {path}")


def wav_fact_summary(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() != ".wav":
        return None
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
    return {
        "container": "wav",
        "channels": channels,
        "sample_rate": sample_rate,
        "bit_depth": sample_width * 8,
        "duration_s": round(frames / sample_rate, 6) if sample_rate else 0.0,
    }


def validate_audio_analysis(analysis: dict[str, Any], expected_source_name: str) -> dict[str, Any]:
    missing = sorted(AUDIO_ANALYSIS_REQUIRED_KEYS - analysis.keys())
    if missing:
        raise ValueError(f"AudioAnalysisV1 missing required keys: {', '.join(missing)}")

    source_name = analysis.get("source_name")
    if source_name != expected_source_name:
        raise ValueError(
            "AudioAnalysisV1 source_name does not match audio file name: "
            f"{source_name!r} != {expected_source_name!r}"
        )

    allowed = AUDIO_ANALYSIS_REQUIRED_KEYS | AUDIO_ANALYSIS_OPTIONAL_VERIFIED_KEYS
    calculated = {
        key: analysis[key]
        for key in sorted(AUDIO_ANALYSIS_OPTIONAL_VERIFIED_KEYS)
        if key in analysis
    }
    extra = sorted(key for key in analysis.keys() if key not in allowed)
    if extra:
        raise ValueError(f"AudioAnalysisV1 contains unknown fields: {', '.join(extra)}")

    return {
        "schema_contract": "AudioAnalysisV1",
        "schema_version": analysis["schema_version"],
        "source_id": analysis["source_id"],
        "source_type": analysis["source_type"],
        "source_name": analysis["source_name"],
        "duration_s": analysis["duration_s"],
        "sample_rate": analysis["sample_rate"],
        "confidence": analysis["confidence"],
        "model_versions": analysis["model_versions"],
        "provenance": analysis["provenance"],
        "calculated_fields": calculated,
        "strict_field_contract": "no unknown AudioAnalysisV1 top-level fields accepted",
    }


def validate_release_input(release: ReleaseInput) -> None:
    require_existing_file(release.audio_path, "audio")
    require_existing_file(release.analysis_path, "analysis")
    require_existing_file(release.source_path, "source")
    if not 0 <= release.royalty_bps <= ROYALTY_DENOMINATOR_BPS:
        raise ValueError("--royalty-bps must be between 0 and 10000")


def build_manifest(release: ReleaseInput) -> dict[str, Any]:
    validate_release_input(release)
    analysis = read_json_object(release.analysis_path)
    analysis_summary = validate_audio_analysis(analysis, release.audio_path.name)
    latest_receipt = read_latest_jsonl(release.receipts_path)

    audio_hash = sha256_file(release.audio_path)
    analysis_hash = sha256_file(release.analysis_path)
    source_hash = sha256_file(release.source_path)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": release.created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": {
            "name": release.project_name,
            "proof_scope": "local_file_based_release_provenance",
        },
        "release": {
            "title": release.title,
            "artist": release.artist,
            "artist_slug": release.artist_slug,
            "artist_public_key": release.artist_public_key,
            "artist_key_fingerprint": release.artist_key_fingerprint,
            "rights_holder": release.rights_holder,
            "release_type": release.release_type,
        },
        "assets": {
            "audio": {
                "path": portable_path(release.audio_path),
                "sha256": audio_hash,
                "facts": wav_fact_summary(release.audio_path),
            },
            "analysis": {
                "path": portable_path(release.analysis_path),
                "sha256": analysis_hash,
                "summary": analysis_summary,
            },
            "source_code": {
                "path": portable_path(release.source_path),
                "sha256": source_hash,
            },
        },
        "ledger": {
            "path": portable_path(release.receipts_path),
            "latest_receipt": latest_receipt,
            "latest_receipt_present": latest_receipt is not None,
        },
        "royalties": {
            "erc_2981_compatible": True,
            "receiver": release.rights_holder,
            "royalty_fraction_bps": release.royalty_bps,
            "denominator_bps": ROYALTY_DENOMINATOR_BPS,
            "splits": [
                {
                    "name": release.rights_holder,
                    "role": "artist_producer_creator",
                    "share_bps": ROYALTY_DENOMINATOR_BPS,
                }
            ],
        },
        "asset_pointers": {
            "local_audio_path": portable_path(release.audio_path),
            "ipfs_cid_stub": release.ipfs_cid_stub,
        },
        "compound_hashes": {
            "audio_sha256": audio_hash,
            "analysis_sha256": analysis_hash,
            "source_sha256": source_hash,
        },
        "_disclaimer": (
            "This manifest is a local cryptographic proof package only. "
            "ERC-2981 compatibility describes metadata fields for future use; "
            "no smart contract is deployed, no token is minted, no wallet is "
            "connected, and no third-party chain or storage provider has "
            "verified this release."
        ),
    }
    manifest["manifest_payload_sha256"] = sha256_json(manifest)
    return manifest


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> ReleaseInput:
    parser = argparse.ArgumentParser(description="Generate a maloSound local release manifest.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--artist", default="maloSound")
    parser.add_argument("--rights-holder", default="Marcelo Zapata")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--receipts", default=DEFAULT_RECEIPTS, type=Path)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--royalty-bps", default=1000, type=int)
    parser.add_argument("--ipfs-cid-stub", default="ipfs://CID_NOT_ASSIGNED_LOCAL_ONLY")
    parser.add_argument("--created-at", help="Optional stable ISO timestamp for deterministic manifests.")
    args = parser.parse_args()

    return ReleaseInput(
        title=args.title,
        artist=args.artist,
        rights_holder=args.rights_holder,
        audio_path=resolve_path(args.audio),
        analysis_path=resolve_path(args.analysis),
        source_path=resolve_path(args.source),
        receipts_path=resolve_path(args.receipts),
        output_path=resolve_path(args.output),
        royalty_bps=args.royalty_bps,
        ipfs_cid_stub=args.ipfs_cid_stub,
        created_at=args.created_at,
    )


def self_test() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        audio = root / "02_beat_grid_click.wav"
        analysis = root / "02_beat_grid_click.audioanalysis.v1.json"
        source = root / "companion.py"
        receipts = root / "receipts.jsonl"
        output = root / "release_manifest_v1.json"

        with wave.open(str(audio), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24_000)
            handle.writeframes(b"\x00\x00" * 24_000)

        analysis.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "source_id": "fixture",
                    "source_type": "stem",
                    "source_name": audio.name,
                    "duration_s": 1.0,
                    "sample_rate": 24_000,
                    "bpm": 120.0,
                    "beat_times": [0.0, 0.5],
                    "confidence": {"bpm": 1.0},
                    "model_versions": {"analysis": "fixture"},
                    "provenance": {"owner": "Marcelo Zapata"},
                }
            ),
            encoding="utf-8",
        )
        source.write_text("print('maloSound companion fixture')\n", encoding="utf-8")
        receipts.write_text(json.dumps({"record_hash": "0" * 64, "signature": "1" * 128}) + "\n", encoding="utf-8")

        manifest = build_manifest(
            ReleaseInput(
                title="Self Test",
                artist="maloSound",
                rights_holder="Marcelo Zapata",
                audio_path=audio,
                analysis_path=analysis,
                source_path=source,
                receipts_path=receipts,
                output_path=output,
                royalty_bps=1000,
                ipfs_cid_stub="ipfs://CID_NOT_ASSIGNED_LOCAL_ONLY",
                created_at="1970-01-01T00:00:00+00:00",
            )
        )
        write_manifest(manifest, output)
        reread = read_json_object(output)
        assert reread["royalties"]["erc_2981_compatible"] is True
        assert reread["royalties"]["splits"][0]["share_bps"] == 10_000
        assert "lufs" not in canonical_json(reread).lower()
        assert "true_peak" not in canonical_json(reread).lower()
    print("release manifest generator self-test OK")
    return 0


def main() -> int:
    if "--self-test" in __import__("sys").argv:
        return self_test()

    release = parse_args()
    manifest = build_manifest(release)
    write_manifest(manifest, release.output_path)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
