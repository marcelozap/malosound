#!/usr/bin/env python3
"""Prove the whole maloSound release system, from empty to verified, in one run.

    python tools/system_selftest.py

Onboards two artists who did not exist a second ago, releases a track for each,
verifies both bundles the way a stranger would, and then tries six ways to fake
one. Everything happens in a temporary directory: your artists, ledgers and
releases are never touched.

This is the run to show someone who asks whether the thing actually works.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
for extra in (TOOLS, REPO_ROOT / "manifests"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import artist_registry
import release as release_tool

PASS = "  PASS"
FAIL = "  FAIL"


class Runner:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, ok: bool, message: str) -> bool:
        self.checks += 1
        print(f"{PASS if ok else FAIL}  {message}")
        if not ok:
            self.failures.append(message)
        return ok

    def section(self, title: str) -> None:
        print()
        print(title)
        print("-" * len(title))


def write_tone(path: Path, *, seconds: int, hz: float, seed: int) -> Path:
    """A small deterministic percussive WAV, so the run needs no audio assets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 22_050
    frames = []
    for index in range(rate * seconds):
        t = index / rate
        hit = 1.0 if (t % 0.5) < 0.03 + (seed % 3) / 200 else 0.0
        value = 0.6 * hit * math.sin(2 * math.pi * hz * t) + 0.07 * math.sin(2 * math.pi * (hz / 2) * t)
        frames.append(struct.pack("<h", int(max(-1.0, min(1.0, value)) * 31_000)))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"".join(frames))
    return path


def run_verifier(bundle: Path, *, fingerprint: str | None = None) -> tuple[int, str]:
    command = [sys.executable, str(bundle / "verify.py"), str(bundle), "--quiet"]
    if fingerprint:
        command += ["--fingerprint", fingerprint]
    completed = subprocess.run(command, capture_output=True, text=True)
    return completed.returncode, completed.stdout + completed.stderr


def component_self_tests(runner: Runner) -> None:
    runner.section("1. Component self-tests")
    for label, command in [
        ("Ed25519 receipts (v1 chain, v2 artist binding, re-attribution rejected)",
         [sys.executable, str(TOOLS / "receipts_ed25519.py"), "self-test"]),
        ("procedural companion determinism",
         [sys.executable, str(TOOLS / "procedural_companion.py"), "--self-test"]),
        ("ERC-2981-compatible manifest generator",
         [sys.executable, str(REPO_ROOT / "manifests" / "generator.py"), "--self-test"]),
        ("AudioAnalysisV1 WAV analyser",
         [sys.executable, str(TOOLS / "audio_analysis_v1.py"), "--self-test"]),
        ("support page renderer",
         [sys.executable, str(TOOLS / "release_page.py")]),
    ]:
        completed = subprocess.run(command, capture_output=True, text=True)
        runner.check(completed.returncode == 0, f"{label}{'' if completed.returncode == 0 else ': ' + completed.stderr.strip()[-200:]}")


def registered_artists(runner: Runner) -> None:
    runner.section("2. Registered artists on this machine")
    slugs = artist_registry.list_slugs()
    runner.check(bool(slugs), f"registry is populated ({len(slugs)} artist(s): {', '.join(slugs) or 'none'})")
    for slug in slugs:
        ok, problems = artist_registry.check(slug)
        runner.check(ok, f"{slug}: key, published fingerprint and ledger agree"
                         + ("" if ok else " — " + "; ".join(problems)))


def two_artists_from_scratch(runner: Runner, workspace: Path) -> dict[str, Any]:
    runner.section("3. Two brand-new artists, onboarded and released from scratch")
    original_root = artist_registry.ARTISTS_ROOT
    artist_registry.ARTISTS_ROOT = workspace / "artists"
    bundles: dict[str, Any] = {}
    try:
        for index, (slug, name) in enumerate(
            [("alba-rios", "Alba Ríos"), ("north-quarter", "North Quarter")], start=1
        ):
            base = workspace / "artists" / slug
            artist = artist_registry.create(
                name=name,
                slug=slug,
                rights_holder=name,
                royalty_bps=500 * index,
                created_at="2026-01-01T00:00:00+00:00",
                paths={
                    "key": str(base / "keys" / f"{slug}.hex"),
                    "ledger": str(base / "ledger" / "receipts.jsonl"),
                    "analysis_root": str(base / "analysis"),
                    "release_root": str(base / "releases"),
                    "companion_root": str(base / "companions"),
                    "manifest_root": str(base / "manifests"),
                },
            )
            runner.check(
                len(artist["public_key"]) == 64 and artist["key_fingerprint"].startswith("MS1-"),
                f"{name}: onboarded with their own key ({artist['key_fingerprint']})",
            )
            audio = write_tone(base / "incoming" / f"{slug}.wav", seconds=5, hz=180 + 40 * index, seed=index)
            result = release_tool.release(
                slug_artist=slug,
                audio=audio,
                title=f"{name} Demo",
                created_at=f"2026-01-01T00:00:0{index}+00:00",
            )
            bundle = Path(result["package"])
            if not bundle.is_absolute():
                bundle = REPO_ROOT / bundle
            runner.check(bundle.exists(), f"{name}: release bundle built ({bundle.name})")
            code, output = run_verifier(bundle, fingerprint=artist["key_fingerprint"])
            runner.check(code == 0, f"{name}: bundle verifies against their published fingerprint")
            bundles[slug] = {"artist": artist, "bundle": bundle, "result": result}

        first, second = bundles["alba-rios"], bundles["north-quarter"]
        runner.check(
            first["artist"]["public_key"] != second["artist"]["public_key"],
            "the two artists hold different signing keys",
        )
        runner.check(
            first["result"]["record_hash"] != second["result"]["record_hash"],
            "the two artists write to separate ledgers with independent chains",
        )
    finally:
        artist_registry.ARTISTS_ROOT = original_root
    return bundles


def forgery_attempts(runner: Runner, workspace: Path, bundles: dict[str, Any]) -> None:
    runner.section("4. Six attempts to pass off a fake — every one must be caught")
    victim = bundles["alba-rios"]
    other = bundles["north-quarter"]
    fingerprint = victim["artist"]["key_fingerprint"]
    lab = workspace / "forgery"
    lab.mkdir(parents=True, exist_ok=True)

    def clone(name: str) -> Path:
        target = lab / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(victim["bundle"], target)
        return target

    def restate(bundle: Path, role: str) -> None:
        """Update the package manifest so only the attacked property is wrong."""
        manifest_path = bundle / "PACKAGE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        target = bundle / manifest["files"][role]["path"]
        manifest["files"][role]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest["files"][role]["bytes"] = target.stat().st_size
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # 1. Swap the audio for something else.
    tampered = clone("swapped-audio")
    audio_file = next((tampered / "audio").iterdir())
    data = bytearray(audio_file.read_bytes())
    data[5000] = (data[5000] + 1) % 256
    audio_file.write_bytes(bytes(data))
    code, output = run_verifier(tampered, fingerprint=fingerprint)
    runner.check(code != 0 and "signed audio hash" in output, "1. audio swapped for a different file — caught")

    # 2. Swap the audio AND restate its hash in the package manifest.
    tampered = clone("swapped-audio-restated")
    audio_file = next((tampered / "audio").iterdir())
    data = bytearray(audio_file.read_bytes())
    data[5000] = (data[5000] + 1) % 256
    audio_file.write_bytes(bytes(data))
    restate(tampered, "audio")
    code, output = run_verifier(tampered, fingerprint=fingerprint)
    runner.check(code != 0 and "signed audio hash" in output, "2. audio swapped and the manifest rewritten to match — caught")

    # 3. Edit the signed title.
    tampered = clone("retitled")
    receipt_path = tampered / "ledger" / "receipt_excerpt.jsonl"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8").strip())
    receipt["title"] = "Someone Else's Song"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    restate(tampered, "receipt_excerpt")
    code, output = run_verifier(tampered, fingerprint=fingerprint)
    runner.check(code != 0 and "signature is valid" in output, "3. the signed title edited — caught")

    # 4. Re-label the bundle as a different artist.
    tampered = clone("relabelled")
    artist_path = tampered / "ARTIST.json"
    identity = json.loads(artist_path.read_text(encoding="utf-8"))
    identity["name"] = other["artist"]["name"]
    identity["slug"] = other["artist"]["slug"]
    artist_path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    restate(tampered, "artist")
    code, output = run_verifier(tampered)
    runner.check(code != 0 and "names this artist" in output, "4. bundle re-labelled as another artist — caught")

    # 5. Claim another artist's key outright.
    tampered = clone("key-claimed")
    artist_path = tampered / "ARTIST.json"
    identity = json.loads(artist_path.read_text(encoding="utf-8"))
    identity["public_key"] = other["artist"]["public_key"]
    identity["key_fingerprint"] = other["artist"]["key_fingerprint"]
    artist_path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    restate(tampered, "artist")
    code, output = run_verifier(tampered, fingerprint=other["artist"]["key_fingerprint"])
    runner.check(code != 0 and "published key" in output, "5. another artist's key pasted in — caught")

    # 6. A genuine bundle presented as a different artist's work.
    code, output = run_verifier(other["bundle"], fingerprint=fingerprint)
    runner.check(
        code != 0 and "fingerprint matches the one you supplied" in output,
        "6. a real bundle offered under the wrong artist's fingerprint — caught",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove the maloSound release system end to end.")
    parser.add_argument("--keep", action="store_true", help="Keep the temporary workspace and print its path.")
    args = parser.parse_args()

    print("maloSound system self-test")
    print("==========================")
    print("Nothing below touches your real artists, ledgers or releases.")

    runner = Runner()
    workspace = Path(tempfile.mkdtemp(prefix="malosound-selftest-"))
    try:
        component_self_tests(runner)
        registered_artists(runner)
        bundles = two_artists_from_scratch(runner, workspace)
        forgery_attempts(runner, workspace, bundles)
    finally:
        if args.keep:
            print(f"\nworkspace kept at {workspace}")
        else:
            shutil.rmtree(workspace, ignore_errors=True)

    print()
    if runner.failures:
        print(f"SYSTEM SELF-TEST FAILED: {len(runner.failures)} of {runner.checks} checks failed")
        for failure in runner.failures:
            print(f"  - {failure}")
        return 1
    print(f"SYSTEM SELF-TEST OK: {runner.checks}/{runner.checks} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
