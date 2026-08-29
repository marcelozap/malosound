#!/usr/bin/env python3
"""Onboard an artist onto maloSound.

Generates their Ed25519 signing key, registers their identity, creates their
folders, and prints the public key fingerprint they publish so anyone can verify
their releases without trusting this machine.

    python tools/onboard_artist.py --name "Your Name"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import artist_registry


def onboard(
    *,
    name: str,
    slug: str | None,
    rights_holder: str | None,
    royalty_bps: int,
    links: dict[str, str],
    created_at: str | None = None,
) -> dict:
    artist = artist_registry.create(
        name=name,
        slug=slug,
        rights_holder=rights_holder,
        royalty_bps=royalty_bps,
        links=links,
        created_at=created_at,
    )
    for key in ("ledger", "analysis_root", "release_root", "companion_root", "manifest_root"):
        path = artist_registry.resolve(artist, key)
        target = path.parent if key == "ledger" else path
        target.mkdir(parents=True, exist_ok=True)
    (artist_registry.ARTISTS_ROOT / artist["slug"] / "incoming").mkdir(parents=True, exist_ok=True)
    return artist


def main() -> int:
    parser = argparse.ArgumentParser(description="Onboard an artist onto maloSound.")
    parser.add_argument("--name", required=True, help="Artist or project display name.")
    parser.add_argument("--slug", help="Folder-safe id. Derived from --name when omitted.")
    parser.add_argument("--rights-holder", help="Legal person or entity holding the rights.")
    parser.add_argument(
        "--royalty-bps",
        type=int,
        default=1000,
        help="Resale royalty in basis points for the ERC-2981-compatible manifest (default 1000 = 10%%).",
    )
    parser.add_argument("--link", action="append", default=[], metavar="LABEL=URL",
                        help="Public link, repeatable. e.g. --link instagram=https://...")
    parser.add_argument("--created-at", help="Optional fixed ISO timestamp, for reproducible fixtures.")
    args = parser.parse_args()

    links: dict[str, str] = {}
    for item in args.link:
        if "=" not in item:
            parser.error(f"--link must be LABEL=URL, got {item!r}")
        label, url = item.split("=", 1)
        links[label.strip()] = url.strip()

    try:
        artist = onboard(
            name=args.name,
            slug=args.slug,
            rights_holder=args.rights_holder,
            royalty_bps=args.royalty_bps,
            links=links,
            created_at=args.created_at,
        )
    except (FileExistsError, ValueError) as exc:
        print(f"ONBOARD REFUSED: {exc}")
        return 1

    print(f"ONBOARDED: {artist['name']}")
    print()
    print(artist_registry.describe(artist))
    print()
    print("Publish this fingerprint anywhere people can find you — bio, site, video description:")
    print()
    print(f"    maloSound key {artist['key_fingerprint']}")
    print()
    print("Keep the signing key private. It is gitignored. If you lose it you cannot")
    print("sign as yourself again; if someone copies it they can sign as you.")
    print()
    print(f"    private key : {artist['paths']['key']}")
    print()
    print("Next:")
    print(f"    python tools/release.py --artist {artist['slug']} --audio <file> --title \"<title>\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
