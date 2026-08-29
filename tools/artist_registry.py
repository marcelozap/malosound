#!/usr/bin/env python3
"""The maloSound artist registry.

One folder per artist under ``artists/<slug>/``. ``artist.json`` is the identity:
display name, rights holder, royalty share, published Ed25519 public key, and the
paths that artist's own key, ledger and releases live at.

Nothing here is maloSound-specific. maloSound is simply the first row.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import receipts_ed25519

ARTISTS_ROOT = REPO_ROOT / "artists"
SCHEMA_VERSION = "malosound.artist.v1"
FINGERPRINT_PREFIX = "MS1"
PATH_KEYS = ("key", "ledger", "analysis_root", "release_root", "companion_root", "manifest_root")

# Letters that carry no combining decomposition, so NFKD alone would drop them.
LETTER_FOLDS = str.maketrans({
    "\u00f0": "d", "\u00d0": "D", "\u00fe": "th", "\u00de": "Th",
    "\u00f8": "o", "\u00d8": "O", "\u00e6": "ae", "\u00c6": "Ae",
    "\u0153": "oe", "\u0152": "Oe", "\u00df": "ss",
    "\u0142": "l", "\u0141": "L", "\u0111": "d", "\u0110": "D",
})


def slugify(value: str) -> str:
    """Folder-safe id. Accents fold to their base letter rather than vanishing,
    so "Alba Rios" and "Alba Rios" do not slug to different things."""
    folded = unicodedata.normalize("NFKD", value.strip().translate(LETTER_FOLDS))
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", folded).strip("-").lower()
    if not slug:
        raise ValueError("Artist name must contain at least one alphanumeric character")
    return slug


def fingerprint(public_key_hex: str) -> str:
    """Short human-readable form of a public key, for the artist to publish."""
    digest = hashlib.sha256(bytes.fromhex(public_key_hex)).digest()[:10]
    encoded = base64.b32encode(digest).decode("ascii").rstrip("=")
    groups = [encoded[index : index + 4] for index in range(0, len(encoded), 4)]
    return "-".join([FINGERPRINT_PREFIX, *groups])


def default_paths(slug: str) -> dict[str, str]:
    base = f"artists/{slug}"
    return {
        "key": f"{base}/keys/{slug}_ed25519_seed.hex",
        "ledger": f"{base}/ledger/receipts.jsonl",
        "analysis_root": f"{base}/analysis",
        "release_root": f"{base}/releases",
        "companion_root": f"{base}/companions",
        "manifest_root": f"{base}/manifests",
    }


def artist_file(slug: str) -> Path:
    return ARTISTS_ROOT / slug / "artist.json"


def resolve(artist: dict[str, Any], key: str) -> Path:
    value = artist["paths"][key]
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def validate(artist: dict[str, Any]) -> None:
    if artist.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"artist.json schema_version must be {SCHEMA_VERSION!r}")
    for field in ("slug", "name", "rights_holder", "public_key", "key_fingerprint", "created_at"):
        if not isinstance(artist.get(field), str) or not artist[field]:
            raise ValueError(f"artist.json field {field!r} must be a non-empty string")
    if artist["slug"] != slugify(artist["slug"]):
        raise ValueError(f"artist slug {artist['slug']!r} is not a canonical slug")
    try:
        public_key = bytes.fromhex(artist["public_key"])
    except ValueError as exc:
        raise ValueError(f"artist public_key is not hex: {exc}") from exc
    if len(public_key) != 32:
        raise ValueError("artist public_key must be a 32-byte Ed25519 key")
    if artist["key_fingerprint"] != fingerprint(artist["public_key"]):
        raise ValueError("artist key_fingerprint does not match public_key")
    royalty = artist.get("royalty_bps")
    if not isinstance(royalty, int) or not 0 <= royalty <= 10_000:
        raise ValueError("artist royalty_bps must be an integer between 0 and 10000")
    paths = artist.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("artist.json paths must be an object")
    missing = [key for key in PATH_KEYS if not isinstance(paths.get(key), str) or not paths[key]]
    if missing:
        raise ValueError(f"artist.json paths missing: {', '.join(missing)}")


def load(slug: str) -> dict[str, Any]:
    path = artist_file(slug)
    if not path.exists():
        known = ", ".join(list_slugs()) or "none yet"
        raise FileNotFoundError(f"No artist {slug!r} in the registry. Known artists: {known}")
    artist = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(artist, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    validate(artist)
    return artist


def list_slugs() -> list[str]:
    if not ARTISTS_ROOT.exists():
        return []
    return sorted(child.name for child in ARTISTS_ROOT.iterdir() if (child / "artist.json").exists())


def write(artist: dict[str, Any]) -> Path:
    validate(artist)
    path = artist_file(artist["slug"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def create(
    *,
    name: str,
    slug: str | None = None,
    rights_holder: str | None = None,
    royalty_bps: int = 1000,
    paths: dict[str, str] | None = None,
    created_at: str | None = None,
    links: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Register an artist, generating their signing key if it does not exist yet."""
    slug = slug or slugify(name)
    if artist_file(slug).exists():
        raise FileExistsError(f"Artist {slug!r} is already registered: {artist_file(slug)}")

    resolved_paths = paths or default_paths(slug)
    key_path = Path(resolved_paths["key"])
    if not key_path.is_absolute():
        key_path = REPO_ROOT / key_path
    seed = receipts_ed25519.load_or_create_seed(key_path)
    public_key = receipts_ed25519.public_key_from_seed(seed).hex()

    artist = {
        "schema_version": SCHEMA_VERSION,
        "slug": slug,
        "name": name,
        "rights_holder": rights_holder or name,
        "royalty_bps": royalty_bps,
        "public_key": public_key,
        "key_fingerprint": fingerprint(public_key),
        "created_at": created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "links": {label: url for label, url in (links or {}).items() if url},
        "paths": resolved_paths,
    }
    write(artist)
    return artist


def check(slug: str) -> tuple[bool, list[str]]:
    """Confirm an artist's on-disk key, published key and ledger all agree."""
    problems: list[str] = []
    artist = load(slug)

    key_path = resolve(artist, "key")
    if not key_path.exists():
        problems.append(f"signing key is missing: {key_path}")
    else:
        derived = receipts_ed25519.public_key_from_seed(
            receipts_ed25519.load_or_create_seed(key_path)
        ).hex()
        if derived != artist["public_key"]:
            problems.append(
                f"signing key derives {derived} but artist.json publishes {artist['public_key']}"
            )

    ledger_path = resolve(artist, "ledger")
    if ledger_path.exists():
        ok, errors = receipts_ed25519.verify_ledger(ledger_path)
        if not ok:
            problems.extend(f"ledger: {error}" for error in errors)
        ledger_key = receipts_ed25519.ledger_public_key(ledger_path)
        if ledger_key and ledger_key != artist["public_key"]:
            problems.append(
                f"ledger is signed by {ledger_key[:16]}... but artist.json publishes "
                f"{artist['public_key'][:16]}..."
            )
    return not problems, problems


def describe(artist: dict[str, Any]) -> str:
    ledger = resolve(artist, "ledger")
    count = 0
    if ledger.exists():
        count = len(receipts_ed25519.iter_receipts(ledger))
    lines = [
        f"{artist['name']}  ({artist['slug']})",
        f"  rights holder : {artist['rights_holder']}",
        f"  royalty       : {artist['royalty_bps']} bps of 10000",
        f"  public key    : {artist['public_key']}",
        f"  fingerprint   : {artist['key_fingerprint']}",
        f"  ledger        : {artist['paths']['ledger']}  ({count} receipt{'' if count == 1 else 's'})",
        f"  releases      : {artist['paths']['release_root']}",
    ]
    for label, url in sorted(artist.get("links", {}).items()):
        if url:
            lines.append(f"  {label:<14}: {url}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the maloSound artist registry.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list every registered artist")
    show_parser = subparsers.add_parser("show", help="show one artist")
    show_parser.add_argument("slug")
    check_parser = subparsers.add_parser("check", help="verify an artist's key and ledger agree")
    check_parser.add_argument("slug", nargs="?")
    args = parser.parse_args()

    if args.command == "list":
        slugs = list_slugs()
        if not slugs:
            print("No artists registered yet. Run: python tools/onboard_artist.py --name \"Your Name\"")
            return 0
        for slug in slugs:
            print(describe(load(slug)))
            print()
        return 0

    if args.command == "show":
        print(describe(load(args.slug)))
        return 0

    slugs = [args.slug] if args.slug else list_slugs()
    failed = False
    for slug in slugs:
        ok, problems = check(slug)
        if ok:
            print(f"ARTIST OK: {slug}")
        else:
            failed = True
            for problem in problems:
                print(f"FAILED [{slug}]: {problem}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
