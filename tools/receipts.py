#!/usr/bin/env python3
"""PEM-key CLI wrapper for the local maloSound Ed25519 receipt ledger."""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import receipts_ed25519


DEFAULT_LEDGER = REPO_ROOT / "data" / "receipts.jsonl"
DEFAULT_PEM = REPO_ROOT / "data" / "malosound_ed25519.pem"
LEGACY_SEED = REPO_ROOT / "data" / "keys" / "malosound_ed25519_seed.hex"
PRIVATE_HEADER = "-----BEGIN MALOSOUND ED25519 SEED-----"
PRIVATE_FOOTER = "-----END MALOSOUND ED25519 SEED-----"
PUBLIC_HEADER = "-----BEGIN MALOSOUND ED25519 PUBLIC KEY-----"
PUBLIC_FOOTER = "-----END MALOSOUND ED25519 PUBLIC KEY-----"


def pem_body(value: bytes) -> str:
    encoded = base64.b64encode(value).decode("ascii")
    return "\n".join(encoded[index:index + 64] for index in range(0, len(encoded), 64))


def write_pem(path: Path, header: str, footer: str, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{header}\n{pem_body(value)}\n{footer}\n", encoding="utf-8", newline="\n")


def read_pem(path: Path, header: str, footer: str) -> bytes:
    text = path.read_text(encoding="utf-8").strip()
    if not text.startswith(header) or not text.endswith(footer):
        raise ValueError(f"Unexpected PEM envelope: {path}")
    body = text.removeprefix(header).removesuffix(footer)
    return base64.b64decode("".join(body.split()))


def legacy_or_random_seed() -> bytes:
    if LEGACY_SEED.exists():
        seed = bytes.fromhex(LEGACY_SEED.read_text(encoding="utf-8").strip())
        if len(seed) == 32:
            return seed
    return secrets.token_bytes(32)


def keygen(key_path: Path) -> None:
    if key_path.exists():
        seed = read_pem(key_path, PRIVATE_HEADER, PRIVATE_FOOTER)
        if len(seed) != 32:
            raise ValueError(f"Ed25519 seed must be 32 bytes: {key_path}")
    else:
        seed = legacy_or_random_seed()
        write_pem(key_path, PRIVATE_HEADER, PRIVATE_FOOTER, seed)

    public_key = receipts_ed25519.public_key_from_seed(seed)
    write_pem(key_path.with_suffix(key_path.suffix + ".pub"), PUBLIC_HEADER, PUBLIC_FOOTER, public_key)
    print(f"private key ready: {key_path}")
    print(f"public key ready: {key_path.with_suffix(key_path.suffix + '.pub')}")


def load_seed(key_path: Path) -> bytes:
    if not key_path.exists():
        keygen(key_path)
    seed = read_pem(key_path, PRIVATE_HEADER, PRIVATE_FOOTER)
    if len(seed) != 32:
        raise ValueError(f"Ed25519 seed must be 32 bytes: {key_path}")
    return seed


def main() -> int:
    parser = argparse.ArgumentParser(description="Append or verify maloSound Ed25519 receipt ledger.")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER, type=Path)
    parser.add_argument("--key", default=DEFAULT_PEM, type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("keygen")
    subparsers.add_parser("verify")

    append_parser = subparsers.add_parser("append")
    append_parser.add_argument("--audio", required=True, type=Path)
    append_parser.add_argument("--analysis", required=True, type=Path)
    append_parser.add_argument("--label", required=True)
    append_parser.add_argument("--timestamp")

    args = parser.parse_args()

    if args.command == "keygen":
        keygen(args.key)
        return 0

    if args.command == "verify":
        ok, errors = receipts_ed25519.verify_ledger(args.ledger)
        if not ok:
            for error in errors:
                print(error)
            return 1
        print("CHAIN OK")
        return 0

    seed = load_seed(args.key)
    receipt = receipts_ed25519.build_receipt(
        audio_path=args.audio,
        analysis_path=args.analysis,
        ledger_path=args.ledger,
        title=args.label,
        seed=seed,
        timestamp=args.timestamp,
    )
    receipt["label"] = args.label
    signature = receipts_ed25519.sign(seed, receipts_ed25519.signed_message(receipt))
    receipt["signature"] = signature.hex()
    receipts_ed25519.append_receipt(receipt, args.ledger)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
