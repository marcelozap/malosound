#!/usr/bin/env python3
"""Assemble a local maloSound release package from verified artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASES = REPO_ROOT / "releases"


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


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{label} is not a file: {path}")


def clean_release_dir(release_dir: Path, output_root: Path) -> None:
    resolved_release = release_dir.resolve()
    resolved_root = output_root.resolve()
    if resolved_release == resolved_root or resolved_root not in resolved_release.parents:
        raise ValueError(f"Refusing to clean release directory outside output root: {release_dir}")
    if release_dir.exists():
        shutil.rmtree(release_dir)


def copy_file(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {
        "path": dst.as_posix(),
        "source": src.as_posix(),
        "sha256": sha256_file(dst),
        "bytes": dst.stat().st_size,
    }


def repo_display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def powershell_quote(value: str) -> str:
    return '"' + value.replace('"', '`"') + '"'


def latest_receipt_for_manifest(receipts_path: Path, manifest: dict[str, Any]) -> str:
    latest = manifest.get("ledger", {}).get("latest_receipt")
    if not isinstance(latest, dict):
        raise ValueError("Manifest does not contain ledger.latest_receipt")
    record_hash = latest.get("record_hash")
    if not isinstance(record_hash, str) or not record_hash:
        raise ValueError("Manifest latest receipt does not contain record_hash")
    for line in receipts_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        receipt = json.loads(line)
        if receipt.get("record_hash") == record_hash:
            return json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    raise ValueError(f"Receipt {record_hash} not found in {receipts_path}")


def assemble_package(
    *,
    slug: str,
    audio: Path,
    analysis: Path,
    companion: Path,
    companion_metadata: Path,
    manifest: Path,
    receipts: Path,
    output_root: Path,
    created_at: str | None = None,
) -> dict[str, Any]:
    for label, path in {
        "audio": audio,
        "analysis": analysis,
        "companion": companion,
        "companion metadata": companion_metadata,
        "manifest": manifest,
        "receipts": receipts,
    }.items():
        require_file(path, label)

    manifest_data = read_json_object(manifest)
    release_dir = output_root / slug
    clean_release_dir(release_dir, output_root)

    files = {
        "audio": copy_file(audio, release_dir / "audio" / audio.name),
        "analysis": copy_file(analysis, release_dir / "data" / analysis.name),
        "companion": copy_file(companion, release_dir / "source" / companion.name),
        "companion_metadata": copy_file(companion_metadata, release_dir / "source" / companion_metadata.name),
        "manifest": copy_file(manifest, release_dir / "manifest" / manifest.name),
    }

    receipt_excerpt = latest_receipt_for_manifest(receipts, manifest_data)
    receipt_excerpt_path = release_dir / "ledger" / "receipt_excerpt.jsonl"
    receipt_excerpt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_excerpt_path.write_text(receipt_excerpt, encoding="utf-8")
    files["receipt_excerpt"] = {
        "path": receipt_excerpt_path.as_posix(),
        "source": receipts.as_posix(),
        "sha256": sha256_file(receipt_excerpt_path),
        "bytes": receipt_excerpt_path.stat().st_size,
    }

    readme_path = release_dir / "README.md"
    package_display = repo_display_path(release_dir)
    analysis_source = repo_display_path(analysis)
    companion_source = repo_display_path(companion)
    readme_path.write_text(
        "\n".join(
            [
                f"# maloSound Release Package: {slug}",
                "",
                "Local provenance package for a maloSound audio artifact.",
                "",
                "## Contents",
                "",
                f"- Audio: `{files['audio']['path']}`",
                f"- Analysis: `{files['analysis']['path']}`",
                f"- Procedural companion: `{files['companion']['path']}`",
                f"- Release manifest: `{files['manifest']['path']}`",
                f"- Ledger excerpt: `{files['receipt_excerpt']['path']}`",
                "",
                "## Verification",
                "",
                "From the maloSound repo root:",
                "",
                "```powershell",
                "python tools\\receipts_ed25519.py verify --ledger data\\receipts.jsonl",
                f"python tools\\procedural_companion.py --analysis {powershell_quote(analysis_source)} --output {powershell_quote(companion_source)} --verify",
                f"python tools\\verify_release_package.py {powershell_quote(package_display)} --require-recorded",
                "```",
                "",
                "## Boundary",
                "",
                "This is local file-based proof. No smart contract is deployed, no token is minted, and no wallet is connected.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    files["readme"] = {
        "path": readme_path.as_posix(),
        "source": "generated",
        "sha256": sha256_file(readme_path),
        "bytes": readme_path.stat().st_size,
    }

    package_manifest = {
        "schema": "malosound.release_package.v1",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "slug": slug,
        "files": files,
        "boundary": "audio is packaged locally under releases/**/audio and remains ignored by git",
    }
    package_manifest_path = release_dir / "PACKAGE_MANIFEST.json"
    package_manifest_path.write_text(json.dumps(package_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return package_manifest


def self_test() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        audio = root / "audio.wav"
        analysis = root / "analysis.json"
        companion = root / "pattern.js"
        companion_metadata = root / "companion.json"
        manifest = root / "release_manifest_v1.json"
        receipts = root / "receipts.jsonl"
        output_root = root / "releases"
        audio.write_bytes(b"RIFFfixture")
        analysis.write_text("{}\n", encoding="utf-8")
        companion.write_text("stack()\n", encoding="utf-8")
        companion_metadata.write_text("{}\n", encoding="utf-8")
        receipt = {"record_hash": "a" * 64, "signature": "b" * 128}
        receipts.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        manifest.write_text(json.dumps({"ledger": {"latest_receipt": receipt}}), encoding="utf-8")
        package = assemble_package(
            slug="self-test",
            audio=audio,
            analysis=analysis,
            companion=companion,
            companion_metadata=companion_metadata,
            manifest=manifest,
            receipts=receipts,
            output_root=output_root,
            created_at="1970-01-01T00:00:00+00:00",
        )
        assert (output_root / "self-test" / "PACKAGE_MANIFEST.json").exists()
        assert package["files"]["receipt_excerpt"]["bytes"] > 0
    print("release package self-test OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a local maloSound release package.")
    parser.add_argument("--slug", required=False, default="2026-08-26-beat-grid-click-fixture")
    parser.add_argument("--audio", required=False, type=Path)
    parser.add_argument("--analysis", required=False, type=Path)
    parser.add_argument("--companion", required=False, type=Path)
    parser.add_argument("--companion-metadata", required=False, type=Path)
    parser.add_argument("--manifest", required=False, type=Path)
    parser.add_argument("--receipts", required=False, type=Path)
    parser.add_argument("--output-root", default=DEFAULT_RELEASES, type=Path)
    parser.add_argument("--created-at", help="Optional stable ISO timestamp for deterministic package manifests.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    required = {
        "--audio": args.audio,
        "--analysis": args.analysis,
        "--companion": args.companion,
        "--companion-metadata": args.companion_metadata,
        "--manifest": args.manifest,
        "--receipts": args.receipts,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error(f"missing required arguments: {', '.join(missing)}")

    package = assemble_package(
        slug=args.slug,
        audio=args.audio,
        analysis=args.analysis,
        companion=args.companion,
        companion_metadata=args.companion_metadata,
        manifest=args.manifest,
        receipts=args.receipts,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(package, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
