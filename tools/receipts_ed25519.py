#!/usr/bin/env python3
"""Append and verify local Ed25519/SHA-256 maloSound receipts.

This is an offline JSONL ledger. It does not deploy contracts, connect wallets,
or publish anything to a third-party service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO_ROOT / "data" / "receipts.jsonl"
DEFAULT_KEY = REPO_ROOT / "data" / "keys" / "malosound_ed25519_seed.hex"
P = 2**255 - 19
Q = 2**252 + 27742317777372353535851937790883648493
D = -121665 * pow(121666, -1, P) % P
I = pow(2, (P - 1) // 4, P)
B = (15112221349535400772501151409588531511454012693041857206046113283949847762202,
     46316835694926478169428394003475163141307993866256225615783033603165251855960)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha512(value: bytes) -> bytes:
    return hashlib.sha512(value).digest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inv(value: int) -> int:
    return pow(value, P - 2, P)


def xrecover(y: int) -> int:
    xx = (y * y - 1) * inv(D * y * y + 1)
    x = pow(xx, (P + 3) // 8, P)
    if (x * x - xx) % P != 0:
        x = (x * I) % P
    if x % 2 != 0:
        x = P - x
    return x


def is_on_curve(point: tuple[int, int]) -> bool:
    x, y = point
    return (-x * x + y * y - 1 - D * x * x * y * y) % P == 0


def point_add(p1: tuple[int, int], p2: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p1
    x2, y2 = p2
    denominator = inv(1 + D * x1 * x2 * y1 * y2)
    x3 = (x1 * y2 + x2 * y1) * denominator % P
    denominator = inv(1 - D * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * denominator % P
    return x3, y3


def scalar_mult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    addend = point
    while scalar:
        if scalar & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        scalar >>= 1
    return result


def encode_int(value: int) -> bytes:
    return value.to_bytes(32, byteorder="little")


def encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    bits = bytearray(encode_int(y))
    bits[31] |= (x & 1) << 7
    return bytes(bits)


def decode_point(value: bytes) -> tuple[int, int]:
    if len(value) != 32:
        raise ValueError("Ed25519 public key or R value must be 32 bytes")
    y = int.from_bytes(value, byteorder="little") & ((1 << 255) - 1)
    x = xrecover(y)
    if bool(x & 1) != bool(value[31] & 0x80):
        x = P - x
    point = (x, y)
    if not is_on_curve(point):
        raise ValueError("Decoded Ed25519 point is not on curve")
    return point


def clamp_scalar(seed_hash: bytes) -> int:
    value = bytearray(seed_hash[:32])
    value[0] &= 248
    value[31] &= 63
    value[31] |= 64
    return int.from_bytes(value, byteorder="little")


def public_key_from_seed(seed: bytes) -> bytes:
    scalar = clamp_scalar(sha512(seed))
    return encode_point(scalar_mult(B, scalar))


def sign(seed: bytes, message: bytes) -> bytes:
    expanded = sha512(seed)
    scalar = clamp_scalar(expanded)
    prefix = expanded[32:]
    public_key = encode_point(scalar_mult(B, scalar))
    r = int.from_bytes(sha512(prefix + message), byteorder="little") % Q
    encoded_r = encode_point(scalar_mult(B, r))
    h = int.from_bytes(sha512(encoded_r + public_key + message), byteorder="little") % Q
    s = (r + h * scalar) % Q
    return encoded_r + encode_int(s)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(signature) != 64:
        return False
    try:
        encoded_r = signature[:32]
        r_point = decode_point(encoded_r)
        a_point = decode_point(public_key)
    except ValueError:
        return False
    s = int.from_bytes(signature[32:], byteorder="little")
    if s >= Q:
        return False
    h = int.from_bytes(sha512(encoded_r + public_key + message), byteorder="little") % Q
    left = scalar_mult(B, s)
    right = point_add(r_point, scalar_mult(a_point, h))
    return encode_point(left) == encode_point(right)


def load_or_create_seed(path: Path) -> bytes:
    if path.exists():
        seed = bytes.fromhex(path.read_text(encoding="utf-8").strip())
        if len(seed) != 32:
            raise ValueError(f"Ed25519 seed must be 32 bytes: {path}")
        return seed
    path.parent.mkdir(parents=True, exist_ok=True)
    seed = secrets.token_bytes(32)
    path.write_text(seed.hex() + "\n", encoding="utf-8")
    return seed


def read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def latest_record_hash(ledger: Path) -> str:
    if not ledger.exists():
        return "GENESIS"
    latest = "GENESIS"
    with ledger.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            latest = value["record_hash"]
    return latest


def signed_message(receipt: dict[str, Any]) -> bytes:
    payload = {
        key: value
        for key, value in receipt.items()
        if key not in {"signature", "public_key", "signature_scheme"}
    }
    return canonical_json(payload).encode("utf-8")


SCHEMA_V1 = "malosound.receipt.v1"
SCHEMA_V2 = "malosound.receipt.v2"
SIGNATURE_SCHEME = "ed25519-sha256-local-jsonl-v1"


def record_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    """The hashed core of a receipt. v2 binds the artist identity into the hash."""
    schema = receipt.get("schema_version", SCHEMA_V1)
    payload = {
        "audio_sha256": receipt["audio"]["sha256"],
        "analysis_sha256": receipt["analysis"]["sha256"],
        "previous_record_hash": receipt["previous_record_hash"],
        "title": receipt["title"],
        "timestamp": receipt["timestamp"],
    }
    if schema == SCHEMA_V2:
        artist = receipt.get("artist") or {}
        payload["artist_slug"] = artist.get("slug", "")
        payload["artist_public_key"] = artist.get("public_key", "")
    return payload


def build_receipt(
    *,
    audio_path: Path,
    analysis_path: Path,
    ledger_path: Path,
    title: str,
    seed: bytes,
    timestamp: str | None = None,
    artist: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Bind one audio file to one analysis artifact and sign the pair.

    Passing ``artist`` emits a v2 receipt whose record hash covers the artist
    slug and public key, so a receipt cannot be re-attributed to another artist
    without breaking both the hash and the signature.
    """
    audio_hash = sha256_file(audio_path)
    analysis_hash = sha256_file(analysis_path)
    previous_hash = latest_record_hash(ledger_path)
    timestamp = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    public_key = public_key_from_seed(seed)

    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_V2 if artist else SCHEMA_V1,
        "timestamp": timestamp,
        "title": title,
        "audio": {
            "path": audio_path.as_posix(),
            "sha256": audio_hash,
        },
        "analysis": {
            "path": analysis_path.as_posix(),
            "sha256": analysis_hash,
        },
        "previous_record_hash": previous_hash,
    }
    if artist:
        declared = artist.get("public_key")
        if declared and declared != public_key.hex():
            raise ValueError(
                f"artist {artist.get('slug')!r} publishes public key {declared} "
                f"but the supplied signing key derives {public_key.hex()}"
            )
        receipt["artist"] = {
            "slug": artist["slug"],
            "name": artist.get("name", artist["slug"]),
            "public_key": public_key.hex(),
        }
        receipt["audio"]["name"] = audio_path.name
        receipt["analysis"]["name"] = analysis_path.name

    receipt["record_hash"] = sha256_bytes(canonical_json(record_payload(receipt)).encode("utf-8"))
    receipt["signature_scheme"] = SIGNATURE_SCHEME
    receipt["public_key"] = public_key.hex()
    receipt["signature"] = sign(seed, signed_message(receipt)).hex()
    return receipt


def append_receipt(receipt: dict[str, Any], ledger_path: Path) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(receipt) + "\n")


def iter_receipts(ledger_path: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    if not ledger_path.exists():
        return receipts
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"Receipt line {line_number} is not a JSON object")
            receipts.append(value)
    return receipts


def verify_ledger(ledger_path: Path) -> tuple[bool, list[str]]:
    """Verify chain linkage, record hashes, signatures, and single-key ownership."""
    previous = "GENESIS"
    errors: list[str] = []
    ledger_key: str | None = None
    for index, receipt in enumerate(iter_receipts(ledger_path), start=1):
        schema = receipt.get("schema_version")
        if schema not in {SCHEMA_V1, SCHEMA_V2}:
            errors.append(f"line {index}: unknown receipt schema {schema!r}")
            continue
        if receipt.get("signature_scheme") != SIGNATURE_SCHEME:
            errors.append(f"line {index}: unexpected signature scheme")
        if receipt.get("previous_record_hash") != previous:
            errors.append(f"line {index}: previous hash mismatch")

        expected_hash = sha256_bytes(canonical_json(record_payload(receipt)).encode("utf-8"))
        if receipt.get("record_hash") != expected_hash:
            errors.append(f"line {index}: record hash mismatch")

        try:
            public_key = bytes.fromhex(receipt["public_key"])
            signature = bytes.fromhex(receipt["signature"])
        except (KeyError, ValueError) as exc:
            errors.append(f"line {index}: invalid signature material: {exc}")
            previous = str(receipt.get("record_hash", ""))
            continue

        if not verify(public_key, signed_message(receipt), signature):
            errors.append(f"line {index}: signature verification failed")

        if schema == SCHEMA_V2:
            artist = receipt.get("artist")
            if not isinstance(artist, dict) or not artist.get("slug"):
                errors.append(f"line {index}: v2 receipt missing artist identity")
            elif artist.get("public_key") != receipt["public_key"]:
                errors.append(f"line {index}: artist public key does not match signing key")

        if ledger_key is None:
            ledger_key = receipt["public_key"]
        elif ledger_key != receipt["public_key"]:
            errors.append(
                f"line {index}: ledger signed by a second key "
                f"({receipt['public_key'][:16]}... after {ledger_key[:16]}...)"
            )

        previous = receipt["record_hash"]
    return not errors, errors


def ledger_public_key(ledger_path: Path) -> str | None:
    receipts = iter_receipts(ledger_path)
    return receipts[0]["public_key"] if receipts else None


def self_test() -> int:
    message = b"maloSound Ed25519 self-test"
    seed = bytes(range(32))
    public_key = public_key_from_seed(seed)
    signature = sign(seed, message)
    assert verify(public_key, message, signature)
    assert not verify(public_key, message + b"!", signature)

    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        audio = root / "a.wav"
        analysis = root / "a.json"
        ledger = root / "receipts.jsonl"
        audio.write_bytes(b"RIFFfixture")
        analysis.write_text("{}\n", encoding="utf-8")
        first = build_receipt(
            audio_path=audio,
            analysis_path=analysis,
            ledger_path=ledger,
            title="fixture",
            seed=seed,
            timestamp="1970-01-01T00:00:00+00:00",
            artist={"slug": "fixture-artist", "name": "Fixture Artist"},
        )
        append_receipt(first, ledger)
        assert first["schema_version"] == SCHEMA_V2
        ok, errors = verify_ledger(ledger)
        assert ok, errors

        # Re-attributing a signed receipt to another artist must break it.
        tampered = json.loads(canonical_json(first))
        tampered["artist"]["slug"] = "someone-else"
        tampered_ledger = root / "tampered.jsonl"
        append_receipt(tampered, tampered_ledger)
        ok, errors = verify_ledger(tampered_ledger)
        assert not ok and any("record hash mismatch" in item for item in errors), errors

    print("ed25519 receipt self-test OK (v1 chain, v2 artist binding, re-attribution rejected)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Append or verify local maloSound Ed25519 receipts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    append_parser = subparsers.add_parser("append")
    append_parser.add_argument("--audio", required=True, type=Path)
    append_parser.add_argument("--analysis", required=True, type=Path)
    append_parser.add_argument("--title", required=True)
    append_parser.add_argument("--ledger", default=DEFAULT_LEDGER, type=Path)
    append_parser.add_argument("--key", default=DEFAULT_KEY, type=Path)
    append_parser.add_argument("--timestamp", help="Optional stable ISO timestamp for deterministic test fixtures.")
    append_parser.add_argument("--artist-slug", help="Emit a v2 receipt bound to this artist slug.")
    append_parser.add_argument("--artist-name", help="Artist display name for a v2 receipt.")

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--ledger", default=DEFAULT_LEDGER, type=Path)

    subparsers.add_parser("self-test")
    args = parser.parse_args()

    if args.command == "self-test":
        return self_test()
    if args.command == "verify":
        ok, errors = verify_ledger(args.ledger)
        if not ok:
            for error in errors:
                print(error)
            return 1
        print(f"ledger OK: {args.ledger}")
        return 0

    seed = load_or_create_seed(args.key)
    artist = None
    if args.artist_slug:
        artist = {"slug": args.artist_slug, "name": args.artist_name or args.artist_slug}
    receipt = build_receipt(
        audio_path=args.audio,
        analysis_path=args.analysis,
        ledger_path=args.ledger,
        title=args.title,
        seed=seed,
        timestamp=args.timestamp,
        artist=artist,
    )
    append_receipt(receipt, args.ledger)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
