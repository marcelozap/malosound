#!/usr/bin/env python3
"""Verify this maloSound release package. Standalone.

    python verify.py .
    python verify.py . --fingerprint MS1-XXXX-XXXX-XXXX-XXXX

This file needs nothing but Python 3.9+. No internet, no install, no maloSound
repo, and no reason to trust whoever handed you the folder. It re-hashes every
file, recomputes the receipt, and checks the Ed25519 signature against the
artist's public key.

If you know the artist's published fingerprint, pass it with --fingerprint. That
is what turns "this package is internally consistent" into "this package was
signed by that artist".
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# --- Ed25519 verification, from the RFC 8032 reference construction ----------

P = 2**255 - 19
Q = 2**252 + 27742317777372353535851937790883648493
D = -121665 * pow(121666, -1, P) % P
I = pow(2, (P - 1) // 4, P)
B = (
    15112221349535400772501151409588531511454012693041857206046113283949847762202,
    46316835694926478169428394003475163141307993866256225615783033603165251855960,
)


def _inv(value: int) -> int:
    return pow(value, P - 2, P)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(D * y * y + 1)
    x = pow(xx, (P + 3) // 8, P)
    if (x * x - xx) % P != 0:
        x = (x * I) % P
    if x % 2 != 0:
        x = P - x
    return x


def _on_curve(point: tuple[int, int]) -> bool:
    x, y = point
    return (-x * x + y * y - 1 - D * x * x * y * y) % P == 0


def _add(p1: tuple[int, int], p2: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p1
    x2, y2 = p2
    d1 = _inv(1 + D * x1 * x2 * y1 * y2)
    d2 = _inv(1 - D * x1 * x2 * y1 * y2)
    return (x1 * y2 + x2 * y1) * d1 % P, (y1 * y2 + x1 * x2) * d2 % P


def _mult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    addend = point
    while scalar:
        if scalar & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        scalar >>= 1
    return result


def _encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    bits = bytearray(y.to_bytes(32, "little"))
    bits[31] |= (x & 1) << 7
    return bytes(bits)


def _decode_point(value: bytes) -> tuple[int, int]:
    if len(value) != 32:
        raise ValueError("Ed25519 point must be 32 bytes")
    y = int.from_bytes(value, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if bool(x & 1) != bool(value[31] & 0x80):
        x = P - x
    point = (x, y)
    if not _on_curve(point):
        raise ValueError("point is not on the curve")
    return point


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(signature) != 64 or len(public_key) != 32:
        return False
    try:
        encoded_r = signature[:32]
        r_point = _decode_point(encoded_r)
        a_point = _decode_point(public_key)
    except ValueError:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= Q:
        return False
    h = int.from_bytes(hashlib.sha512(encoded_r + public_key + message).digest(), "little") % Q
    return _encode_point(_mult(B, s)) == _encode_point(_add(r_point, _mult(a_point, h)))


# --- Package checks ----------------------------------------------------------

SIGNATURE_SCHEME = "ed25519-sha256-local-jsonl-v1"
FINGERPRINT_PREFIX = "MS1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def fingerprint(public_key_hex: str) -> str:
    digest = hashlib.sha256(bytes.fromhex(public_key_hex)).digest()[:10]
    encoded = base64.b32encode(digest).decode("ascii").rstrip("=")
    groups = [encoded[index : index + 4] for index in range(0, len(encoded), 4)]
    return "-".join([FINGERPRINT_PREFIX, *groups])


def record_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "audio_sha256": receipt["audio"]["sha256"],
        "analysis_sha256": receipt["analysis"]["sha256"],
        "previous_record_hash": receipt["previous_record_hash"],
        "title": receipt["title"],
        "timestamp": receipt["timestamp"],
    }
    if receipt.get("schema_version") == "malosound.receipt.v2":
        artist = receipt.get("artist") or {}
        payload["artist_slug"] = artist.get("slug", "")
        payload["artist_public_key"] = artist.get("public_key", "")
    return payload


def signed_message(receipt: dict[str, Any]) -> bytes:
    payload = {
        key: value
        for key, value in receipt.items()
        if key not in {"signature", "public_key", "signature_scheme"}
    }
    return canonical_json(payload).encode("utf-8")


class Report:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def check(self, ok: bool, message: str) -> bool:
        (self.passed if ok else self.failed).append(message)
        return ok


def verify_package(package_dir: Path, expected_fingerprint: str | None) -> Report:
    report = Report()
    manifest_path = package_dir / "PACKAGE_MANIFEST.json"
    if not report.check(manifest_path.exists(), f"package manifest present ({manifest_path.name})"):
        return report

    package = read_json(manifest_path)
    files = package.get("files", {})
    report.check(isinstance(files, dict) and bool(files), "package manifest lists files")

    def packaged(name: str) -> Path:
        item = files.get(name) or {}
        return package_dir / str(item.get("path", "__missing__"))

    # 1. Every declared file is present and hashes to its declared value.
    for name in sorted(files):
        entry = files[name]
        if not isinstance(entry, dict):
            report.check(False, f"file entry {name} is malformed")
            continue
        path = packaged(name)
        if not report.check(path.exists(), f"{name}: file present ({entry.get('path')})"):
            continue
        report.check(sha256_file(path) == entry.get("sha256"), f"{name}: sha256 matches the manifest")

    # 2. Nothing extra is hiding in the folder.
    declared = {packaged(name).resolve() for name in files if isinstance(files.get(name), dict)}
    declared.add(manifest_path.resolve())
    extra = sorted(
        str(path.relative_to(package_dir))
        for path in package_dir.rglob("*")
        if path.is_file() and path.resolve() not in declared
    )
    report.check(not extra, "no undeclared files in the package" + (f" (found: {', '.join(extra)})" if extra else ""))

    # 3. The artist identity.
    artist_path = packaged("artist") if "artist" in files else package_dir / "ARTIST.json"
    if not report.check(artist_path.exists(), "artist identity present (ARTIST.json)"):
        return report
    artist = read_json(artist_path)
    public_key_hex = str(artist.get("public_key", ""))
    report.check(
        len(public_key_hex) == 64,
        f"artist public key is a 32-byte Ed25519 key ({artist.get('name')})",
    )
    report.check(
        artist.get("key_fingerprint") == fingerprint(public_key_hex),
        f"artist fingerprint matches their public key ({artist.get('key_fingerprint')})",
    )
    if expected_fingerprint:
        report.check(
            artist.get("key_fingerprint") == expected_fingerprint.strip().upper(),
            f"artist fingerprint matches the one you supplied ({expected_fingerprint})",
        )

    # 4. The receipt: hash, signature, and who signed it.
    receipt_path = packaged("receipt_excerpt") if "receipt_excerpt" in files else package_dir / "ledger" / "receipt_excerpt.jsonl"
    if not report.check(receipt_path.exists(), "signed receipt present"):
        return report
    lines = [line for line in receipt_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not report.check(bool(lines), "receipt file is not empty"):
        return report
    receipt = json.loads(lines[-1])

    report.check(receipt.get("signature_scheme") == SIGNATURE_SCHEME, "receipt uses Ed25519/SHA-256")
    expected_record_hash = hashlib.sha256(canonical_json(record_payload(receipt)).encode("utf-8")).hexdigest()
    report.check(
        receipt.get("record_hash") == expected_record_hash,
        "receipt record hash recomputes exactly (nothing in it was edited)",
    )
    try:
        signature_ok = ed25519_verify(
            bytes.fromhex(receipt["public_key"]),
            signed_message(receipt),
            bytes.fromhex(receipt["signature"]),
        )
    except (KeyError, ValueError):
        signature_ok = False
    report.check(signature_ok, "Ed25519 signature is valid for the signing key in the receipt")
    report.check(
        receipt.get("public_key") == public_key_hex,
        "receipt was signed by this artist's published key",
    )
    if receipt.get("schema_version") == "malosound.receipt.v2":
        report.check(
            (receipt.get("artist") or {}).get("slug") == artist.get("slug"),
            "receipt names this artist, and that name is inside the signed hash",
        )

    # 5. The receipt is about the audio actually in this folder.
    audio_path = packaged("audio")
    analysis_path = packaged("analysis")
    if audio_path.exists():
        audio_hash = sha256_file(audio_path)
        report.check(receipt["audio"]["sha256"] == audio_hash, "the signed audio hash is the audio in this folder")
        if analysis_path.exists():
            analysis = read_json(analysis_path)
            report.check(
                analysis.get("audio_sha256") == audio_hash,
                "the analysis describes this exact audio file",
            )
    if analysis_path.exists():
        report.check(
            receipt["analysis"]["sha256"] == sha256_file(analysis_path),
            "the signed analysis hash is the analysis in this folder",
        )

    # 6. The royalty manifest agrees with the package.
    manifest_asset_path = packaged("manifest")
    if manifest_asset_path.exists():
        release_manifest = read_json(manifest_asset_path)
        assets = release_manifest.get("assets", {})
        if isinstance(assets, dict) and audio_path.exists():
            report.check(
                (assets.get("audio") or {}).get("sha256") == sha256_file(audio_path),
                "release manifest points at this audio",
            )
        royalties = release_manifest.get("royalties", {})
        splits = royalties.get("splits", []) if isinstance(royalties, dict) else []
        total = sum(item.get("share_bps", 0) for item in splits if isinstance(item, dict))
        report.check(total == 10_000, f"royalty splits sum to 100% ({total} of 10000 bps)")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a maloSound release package.")
    parser.add_argument("package_dir", nargs="?", default=".", type=Path)
    parser.add_argument("--fingerprint", help="The artist's published key fingerprint, e.g. MS1-XXXX-XXXX-XXXX-XXXX")
    parser.add_argument("--quiet", action="store_true", help="Only print the verdict.")
    args = parser.parse_args()

    package_dir = args.package_dir.resolve()
    report = verify_package(package_dir, args.fingerprint)

    if not args.quiet:
        for message in report.passed:
            print(f"  ok    {message}")
        print()
    for message in report.failed:
        print(f"  FAIL  {message}")

    if report.failed:
        print()
        print(f"NOT VERIFIED: {package_dir}")
        print(f"{len(report.failed)} check(s) failed. Do not treat this package as authentic.")
        return 1

    print(f"VERIFIED: {package_dir}")
    print(f"All {len(report.passed)} checks passed.")
    if not args.fingerprint:
        print()
        print("Note: this proves the package is internally consistent and signed by the key")
        print("it carries. To prove it is the artist you think it is, re-run with their")
        print("published fingerprint:  python verify.py . --fingerprint MS1-...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
