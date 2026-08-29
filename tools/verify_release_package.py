#!/usr/bin/env python3
"""Verify a local maloSound release package against the provenance goal."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import procedural_companion
import receipts_ed25519


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def resolve_manifest_path(path: str | None, fallback: Path) -> Path:
    if not isinstance(path, str) or not path:
        return fallback
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def int_in_range(value: Any, low: int, high: int) -> bool:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return False
    return low <= numeric <= high


def verify_package(package_dir: Path, *, require_recorded: bool) -> tuple[bool, list[str]]:
    errors: list[str] = []
    package_manifest_path = package_dir / "PACKAGE_MANIFEST.json"
    check(package_manifest_path.exists(), f"missing {package_manifest_path}", errors)
    if errors:
        return False, errors

    package_manifest = read_json(package_manifest_path)
    schema = package_manifest.get("schema")
    if schema == "malosound.release_package.v2":
        return False, [
            "this is a v2 artist bundle; verify it with its own bundled verifier instead: "
            f"python {package_dir.as_posix()}/verify.py {package_dir.as_posix()} --fingerprint <MS1-...>"
        ]
    check(schema == "malosound.release_package.v1", "PACKAGE_MANIFEST schema mismatch", errors)
    files = package_manifest.get("files", {})
    check(isinstance(files, dict), "PACKAGE_MANIFEST files must be an object", errors)

    def package_file(name: str) -> Path:
        item = files.get(name, {})
        path = item.get("path") if isinstance(item, dict) else None
        return resolve_manifest_path(path, package_dir / "__missing__")

    def source_file(name: str) -> Path | None:
        item = files.get(name, {})
        source = item.get("source") if isinstance(item, dict) else None
        if not isinstance(source, str) or source == "generated":
            return None
        return resolve_manifest_path(source, package_dir / "__missing_source__")

    required = ["audio", "analysis", "companion", "companion_metadata", "manifest", "receipt_excerpt", "readme"]
    for name in required:
        path = package_file(name)
        check(path.exists(), f"missing packaged {name}: {path}", errors)
        expected = files.get(name, {}).get("sha256") if isinstance(files.get(name), dict) else None
        if path.exists() and expected:
            check(sha256_file(path) == expected, f"sha256 mismatch for {name}", errors)
        source = source_file(name)
        if source is not None:
            check(source.exists(), f"missing source {name}: {source}", errors)
            if source.exists() and expected and name != "receipt_excerpt":
                check(sha256_file(source) == expected, f"source/package sha256 mismatch for {name}", errors)

    declared_paths = {
        package_file(name).resolve()
        for name in files
        if isinstance(files.get(name), dict)
    }
    declared_paths.add(package_manifest_path.resolve())
    if package_dir.exists():
        extra_files = [
            path
            for path in package_dir.rglob("*")
            if path.is_file() and path.resolve() not in declared_paths
        ]
        check(
            not extra_files,
            "package contains undeclared files: " + ", ".join(str(path) for path in extra_files),
            errors,
        )

    analysis = read_json(package_file("analysis")) if package_file("analysis").exists() else {}
    manifest = read_json(package_file("manifest")) if package_file("manifest").exists() else {}
    companion_metadata = read_json(package_file("companion_metadata")) if package_file("companion_metadata").exists() else {}
    receipt_lines = package_file("receipt_excerpt").read_text(encoding="utf-8").splitlines() if package_file("receipt_excerpt").exists() else []
    receipt = json.loads(receipt_lines[-1]) if receipt_lines else {}
    receipt_source = source_file("receipt_excerpt")
    if receipt and receipt_source is not None and receipt_source.exists():
        source_receipts = {line.strip() for line in receipt_source.read_text(encoding="utf-8").splitlines() if line.strip()}
        check(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")) in source_receipts,
            "receipt excerpt is not present in source ledger",
            errors,
        )

    forbidden_analysis_keys = {"lufs", "integrated_loudness_lufs", "true_peak", "true_peak_dbtp", "key", "harmonic_profile"}
    check(not (forbidden_analysis_keys & {key.lower() for key in analysis.keys()}), "analysis contains uncalculated field keys", errors)
    check(analysis.get("source_name") == package_file("audio").name, "analysis source_name does not match packaged audio filename", errors)
    check(analysis.get("audio_sha256") == files.get("audio", {}).get("sha256"), "analysis audio_sha256 does not match packaged audio", errors)
    manifest_assets = manifest.get("assets", {})
    if isinstance(manifest_assets, dict):
        audio_asset = manifest_assets.get("audio", {})
        analysis_asset = manifest_assets.get("analysis", {})
        source_asset = manifest_assets.get("source_code", {})
        check(isinstance(audio_asset, dict) and audio_asset.get("sha256") == files.get("audio", {}).get("sha256"), "manifest audio hash does not match package", errors)
        check(isinstance(analysis_asset, dict) and analysis_asset.get("sha256") == files.get("analysis", {}).get("sha256"), "manifest analysis hash does not match package", errors)
        check(isinstance(source_asset, dict) and source_asset.get("sha256") == files.get("companion", {}).get("sha256"), "manifest source hash does not match package companion", errors)
    check(manifest.get("royalties", {}).get("erc_2981_compatible") is True, "manifest missing ERC-2981 compatibility flag", errors)
    royalties = manifest.get("royalties", {})
    splits = royalties.get("splits", []) if isinstance(royalties, dict) else []
    if isinstance(splits, list):
        split_sum = sum(item.get("share_bps", 0) for item in splits if isinstance(item, dict))
        check(split_sum == 10_000, "manifest royalty split shares must sum to 10000 bps", errors)
    check(
        int_in_range(royalties.get("royalty_fraction_bps") if isinstance(royalties, dict) else None, 0, 10_000),
        "manifest royalty fraction must be 0..10000 bps",
        errors,
    )
    check(manifest.get("_disclaimer"), "manifest missing _disclaimer", errors)
    check("no smart contract is deployed" in str(manifest.get("_disclaimer", "")).lower(), "manifest disclaimer does not state local/no-contract boundary", errors)
    check(receipt.get("signature_scheme") == "ed25519-sha256-local-jsonl-v1", "receipt is not Ed25519/SHA-256 scheme", errors)
    recorded_pattern_hash = companion_metadata.get("pattern_sha256")
    if package_file("companion").exists() and isinstance(recorded_pattern_hash, str):
        check(
            sha256_file(package_file("companion")) == recorded_pattern_hash,
            "companion metadata pattern_sha256 does not match packaged companion",
            errors,
        )
    manifest_receipt = manifest.get("ledger", {}).get("latest_receipt", {})
    if isinstance(manifest_receipt, dict):
        check(
            receipt.get("record_hash") == manifest_receipt.get("record_hash"),
            "receipt excerpt does not match manifest latest receipt",
            errors,
        )

    ledger_path = REPO_ROOT / "data" / "receipts.jsonl"
    ledger_ok, ledger_errors = receipts_ed25519.verify_ledger(ledger_path)
    check(ledger_ok, "source ledger failed verification: " + "; ".join(ledger_errors), errors)

    source_analysis = source_file("analysis") or (REPO_ROOT / "data" / "gold" / "audio_analysis" / package_file("analysis").name)
    source_companion = source_file("companion") or (REPO_ROOT / "scripts" / "strudel" / "tracks" / package_manifest["slug"] / "pattern.js")
    if source_analysis.exists() and source_companion.exists():
        companion_ok, _ = procedural_companion.verify_companion(source_analysis, source_companion)
        check(companion_ok, "source procedural companion is not deterministic against source analysis", errors)
        if isinstance(recorded_pattern_hash, str):
            check(
                sha256_file(source_companion) == recorded_pattern_hash,
                "companion metadata pattern_sha256 does not match source companion",
                errors,
            )

    audio_source = files.get("audio", {}).get("source") if isinstance(files.get("audio"), dict) else ""
    if require_recorded:
        check(
            "\\Recorded\\" in str(audio_source) or "/Recorded/" in str(audio_source),
            "final goal requires audio from a Recorded folder",
            errors,
        )
    else:
        check("Generated Stems" in str(audio_source), "fixture package should identify generated-stem source", errors)

    return not errors, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a local maloSound release package.")
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--require-recorded", action="store_true")
    args = parser.parse_args()

    ok, errors = verify_package(args.package_dir, require_recorded=args.require_recorded)
    if not ok:
        for error in errors:
            print(f"FAILED: {error}")
        return 1
    print(f"release package OK: {args.package_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
