#!/usr/bin/env python3
"""Release a track for any registered artist.

    python tools/release.py --artist <slug> --audio <file> --title "<title>"

One command: analyse the audio, sign the pair into that artist's own ledger,
generate the procedural companion and the ERC-2981-compatible manifest, build the
download package, drop a standalone verifier and a support page inside it, and
then verify the finished package the way a stranger would.

Nothing about this is specific to one artist. Every path, key and royalty split
comes from ``artists/<slug>/artist.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
TEMPLATES = TOOLS / "templates"
for extra in (TOOLS, REPO_ROOT / "manifests"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import artist_registry
import generator as manifest_generator
import procedural_companion
import receipts_ed25519
import release_page

PACKAGE_SCHEMA = "malosound.release_package.v2"
WAV_SUFFIXES = {".wav", ".wave"}
COVER_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def repo_path(path: Path) -> str:
    """Display form: relative to the repo when possible, so output is copy-pasteable."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


DEFAULT_LICENSE = "all-rights-reserved"
DEFAULT_CONSENT = "self-recorded/owned catalog; analysis run by the rights holder"


def analyse(
    audio: Path,
    *,
    owner: str,
    created_at: str,
    license_text: str = DEFAULT_LICENSE,
    consent: str = DEFAULT_CONSENT,
) -> dict[str, Any]:
    """Dispatch to the WAV analyser or the ffmpeg analyser by file type.

    Both emit AudioAnalysisV1; both are validated against the same schema before
    anything downstream is allowed to sign them.
    """
    schema = load_schema_validator()
    if audio.suffix.lower() in WAV_SUFFIXES:
        import audio_analysis_v1

        analysis = audio_analysis_v1.build_analysis(
            audio, source_type="recording", owner=owner, created_at=created_at
        )
    else:
        import audio_analysis_ffmpeg

        analysis = audio_analysis_ffmpeg.build_analysis(
            audio,
            source_type="recording",
            owner=owner,
            license_text=license_text,
            consent=consent,
            created_at=created_at,
        )
    schema.validate_document(analysis)
    # Canonical form: keys sorted, so the artifact and its hash are reproducible
    # regardless of which analyser produced it.
    return dict(sorted(analysis.items()))


def load_schema_validator():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "malosound_audio_analysis", REPO_ROOT / "schemas" / "audio_analysis.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_canonical_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copy_into(src: Path, dest_dir: Path, rel: str) -> dict[str, Any]:
    dst = dest_dir / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"path": rel, "sha256": sha256_file(dst), "bytes": dst.stat().st_size, "source": src.as_posix()}


def declare(dest_dir: Path, rel: str, *, source: str = "generated") -> dict[str, Any]:
    path = dest_dir / rel
    return {"path": rel, "sha256": sha256_file(path), "bytes": path.stat().st_size, "source": source}


def public_artist_record(artist: dict[str, Any]) -> dict[str, Any]:
    """The artist identity that ships in the package. Public material only."""
    return {
        "schema_version": artist["schema_version"],
        "slug": artist["slug"],
        "name": artist["name"],
        "rights_holder": artist["rights_holder"],
        "royalty_bps": artist["royalty_bps"],
        "public_key": artist["public_key"],
        "key_fingerprint": artist["key_fingerprint"],
        "links": artist.get("links", {}),
    }


def release(
    *,
    slug_artist: str,
    audio: Path,
    title: str,
    release_slug: str | None = None,
    cover: Path | None = None,
    support_note: str | None = None,
    license_text: str | None = None,
    consent: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    artist = artist_registry.load(slug_artist)
    ok, problems = artist_registry.check(slug_artist)
    if not ok:
        raise ValueError("artist registry check failed: " + "; ".join(problems))

    audio = resolve(audio)
    if not audio.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio}")
    if cover is not None:
        cover = resolve(cover)
        if not cover.is_file():
            raise FileNotFoundError(f"Cover image not found: {cover}")
        if cover.suffix.lower() not in COVER_SUFFIXES:
            raise ValueError(f"Cover must be one of {sorted(COVER_SUFFIXES)}: {cover.name}")

    release_slug = release_slug or artist_registry.slugify(title)
    stamp = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    analysis_path = artist_registry.resolve(artist, "analysis_root") / f"{audio.stem}.audioanalysis.v1.json"
    ledger_path = artist_registry.resolve(artist, "ledger")
    key_path = artist_registry.resolve(artist, "key")
    companion_dir = artist_registry.resolve(artist, "companion_root") / release_slug
    companion_path = companion_dir / "pattern.js"
    companion_metadata_path = companion_dir / "companion.json"
    manifest_path = artist_registry.resolve(artist, "manifest_root") / f"{release_slug}.release_manifest_v1.json"
    package_dir = artist_registry.resolve(artist, "release_root") / release_slug

    # 1. Analysis
    analysis = analyse(
        audio,
        owner=artist["rights_holder"],
        created_at=stamp,
        license_text=license_text or DEFAULT_LICENSE,
        consent=consent or DEFAULT_CONSENT,
    )
    write_canonical_json(analysis_path, analysis)

    # 2. Signed receipt in this artist's own ledger
    seed = receipts_ed25519.load_or_create_seed(key_path)
    receipt = receipts_ed25519.build_receipt(
        audio_path=audio,
        analysis_path=analysis_path,
        ledger_path=ledger_path,
        title=title,
        seed=seed,
        timestamp=stamp,
        artist={"slug": artist["slug"], "name": artist["name"], "public_key": artist["public_key"]},
    )
    receipts_ed25519.append_receipt(receipt, ledger_path)
    ledger_ok, ledger_errors = receipts_ed25519.verify_ledger(ledger_path)
    if not ledger_ok:
        raise ValueError(f"Ledger verification failed after append: {ledger_errors}")

    # 3. Procedural companion
    procedural_companion.write_companion(analysis_path, companion_path, companion_metadata_path)
    companion_ok, _ = procedural_companion.verify_companion(analysis_path, companion_path)
    if not companion_ok:
        raise ValueError("Procedural companion is not deterministic against its analysis")

    # 4. ERC-2981-compatible manifest
    manifest = manifest_generator.build_manifest(
        manifest_generator.ReleaseInput(
            title=title,
            artist=artist["name"],
            rights_holder=artist["rights_holder"],
            audio_path=audio,
            analysis_path=analysis_path,
            source_path=companion_path,
            receipts_path=ledger_path,
            output_path=manifest_path,
            royalty_bps=artist["royalty_bps"],
            ipfs_cid_stub="ipfs://CID_NOT_ASSIGNED_LOCAL_ONLY",
            created_at=stamp,
            project_name=artist["name"],
            release_type="direct_release_provenance_bundle",
            artist_slug=artist["slug"],
            artist_public_key=artist["public_key"],
            artist_key_fingerprint=artist["key_fingerprint"],
        )
    )
    manifest_generator.write_manifest(manifest, manifest_path)

    # 5. Package. Every path inside is package-relative so the folder travels.
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, Any] = {
        "audio": copy_into(audio, package_dir, f"audio/{audio.name}"),
        "analysis": copy_into(analysis_path, package_dir, f"data/{analysis_path.name}"),
        "companion": copy_into(companion_path, package_dir, f"source/{companion_path.name}"),
        "companion_metadata": copy_into(companion_metadata_path, package_dir, f"source/{companion_metadata_path.name}"),
        "manifest": copy_into(manifest_path, package_dir, f"manifest/{manifest_path.name}"),
        "verifier": copy_into(TEMPLATES / "verify.py", package_dir, "verify.py"),
    }
    if cover is not None:
        files["cover"] = copy_into(cover, package_dir, f"cover{cover.suffix.lower()}")

    receipt_rel = "ledger/receipt_excerpt.jsonl"
    (package_dir / receipt_rel).parent.mkdir(parents=True, exist_ok=True)
    (package_dir / receipt_rel).write_text(
        receipts_ed25519.canonical_json(receipt) + "\n", encoding="utf-8"
    )
    files["receipt_excerpt"] = declare(package_dir, receipt_rel, source=ledger_path.as_posix())

    write_canonical_json(package_dir / "ARTIST.json", public_artist_record(artist))
    files["artist"] = declare(package_dir, "ARTIST.json")

    release_page.write_page(
        package_dir / "index.html",
        artist=artist,
        title=title,
        audio_name=audio.name,
        audio_bytes=files["audio"]["bytes"],
        audio_sha256=files["audio"]["sha256"],
        analysis=analysis,
        analysis_name=analysis_path.name,
        receipt=receipt,
        manifest_name=files["manifest"]["path"],
        cover_name=files["cover"]["path"] if cover is not None else None,
        support_note=support_note,
    )
    files["page"] = declare(package_dir, "index.html")

    (package_dir / "README.md").write_text(
        readme_text(artist=artist, title=title, files=files, receipt=receipt), encoding="utf-8"
    )
    files["readme"] = declare(package_dir, "README.md")

    package_manifest = {
        "schema": PACKAGE_SCHEMA,
        "created_at": stamp,
        "slug": release_slug,
        "title": title,
        "artist": {
            "slug": artist["slug"],
            "name": artist["name"],
            "public_key": artist["public_key"],
            "key_fingerprint": artist["key_fingerprint"],
        },
        "ledger": {"path": artist["paths"]["ledger"], "record_hash": receipt["record_hash"]},
        "files": files,
        "boundary": (
            "Local cryptographic proof only. No contract deployed, no token minted, "
            "no wallet connected, no third-party attestation."
        ),
    }
    write_canonical_json(package_dir / "PACKAGE_MANIFEST.json", package_manifest)

    return {
        "artist": artist["slug"],
        "title": title,
        "release_slug": release_slug,
        "audio": repo_path(audio),
        "analysis": repo_path(analysis_path),
        "ledger": repo_path(ledger_path),
        "ledger_ok": ledger_ok,
        "ledger_length": len(receipts_ed25519.iter_receipts(ledger_path)),
        "record_hash": receipt["record_hash"],
        "previous_record_hash": receipt["previous_record_hash"],
        "package": repo_path(package_dir),
        "package_manifest": package_manifest,
    }


def readme_text(*, artist: dict[str, Any], title: str, files: dict[str, Any], receipt: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            f"{artist['name']} — direct release bundle.",
            "",
            "Open `index.html` to listen, download, and read what the receipt means.",
            "",
            "## Verify this bundle",
            "",
            "Python 3, this folder, no install and no internet:",
            "",
            "```",
            f"python verify.py . --fingerprint {artist['key_fingerprint']}",
            "```",
            "",
            "A pass means the audio here is byte-for-byte what was signed, and it was",
            f"signed by the key published as `{artist['key_fingerprint']}`.",
            "",
            "## What is in here",
            "",
            f"- `{files['audio']['path']}` — the track",
            f"- `{files['analysis']['path']}` — AudioAnalysisV1 measurements of that exact file",
            f"- `{files['manifest']['path']}` — release manifest with the ERC-2981-compatible royalty split",
            f"- `{files['receipt_excerpt']['path']}` — the signed receipt",
            f"- `{files['companion']['path']}` — deterministic Strudel companion pattern",
            "- `ARTIST.json` — the artist's public key and fingerprint",
            "- `verify.py` — the verifier, standalone",
            "",
            "## Receipt",
            "",
            "```",
            f"record hash   {receipt['record_hash']}",
            f"previous      {receipt['previous_record_hash']}",
            f"signed at     {receipt['timestamp']}",
            f"public key    {artist['public_key']}",
            f"fingerprint   {artist['key_fingerprint']}",
            "```",
            "",
            "## Boundary",
            "",
            "This is local file-based proof. No smart contract is deployed, no token is",
            "minted, no wallet is connected, and no third party has attested to anything.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Release a track for a registered artist.")
    parser.add_argument("--artist", required=True, help="Artist slug from the registry.")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--release-slug", help="Folder name for the bundle. Derived from --title when omitted.")
    parser.add_argument("--cover", type=Path, help="Optional cover image.")
    parser.add_argument("--support-note", help="One line on the support page about how to support this release.")
    parser.add_argument("--license", dest="license_text", help="Licence string recorded in the analysis provenance.")
    parser.add_argument("--consent", help="Consent/ownership statement recorded in the analysis provenance.")
    parser.add_argument("--created-at", help="Optional fixed ISO timestamp, for reproducible fixtures.")
    parser.add_argument("--json", action="store_true", help="Print the machine-readable run record.")
    args = parser.parse_args()

    try:
        result = release(
            slug_artist=args.artist,
            audio=args.audio,
            title=args.title,
            release_slug=args.release_slug,
            cover=args.cover,
            support_note=args.support_note,
            license_text=args.license_text,
            consent=args.consent,
            created_at=args.created_at,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"RELEASE REFUSED: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    artist = artist_registry.load(args.artist)
    print(f"RELEASED: {result['title']}")
    print(f"  artist       : {artist['name']} ({artist['slug']})")
    print(f"  bundle       : {result['package']}")
    print(f"  ledger       : {result['ledger']}  (record {result['ledger_length']})")
    print(f"  record_hash  : {result['record_hash']}")
    print(f"  previous     : {result['previous_record_hash']}")
    print(f"  fingerprint  : {artist['key_fingerprint']}")
    print()
    print("Verify it the way anyone else would:")
    print(f"  python {result['package']}/verify.py {result['package']} --fingerprint {artist['key_fingerprint']}")
    print()
    print("Share it:")
    print(f"  open {result['package']}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
