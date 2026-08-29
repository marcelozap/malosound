#!/usr/bin/env python3
"""MaloSound local studio readiness checks."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
AUDIO_EXTS = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".m4a", ".ogg", ".wv", ".rex", ".rx2"}


@dataclass
class Check:
    name: str
    ok: bool | None
    detail: str

    def render(self) -> str:
        tag = "OK" if self.ok is True else "MISS" if self.ok is False else "CHECK"
        return f"[{tag}] {self.name}: {self.detail}"


def run(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def git_config(key: str) -> str:
    code, output = run(["git", "config", "--get", key])
    return output.strip() if code == 0 else ""


def git_status_paths() -> list[str]:
    code, output = run(["git", "status", "--porcelain"])
    if code != 0:
        return []
    paths: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        paths.append(line[3:].strip() if len(line) > 3 else line.strip())
    return paths


def staged_paths() -> list[str]:
    code, output = run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"])
    if code != 0:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def latest_stem_kit() -> Path | None:
    if not PROJECTS.exists():
        return None
    kits = list(PROJECTS.rglob("STEMS.md"))
    if not kits:
        return None
    return max(kits, key=lambda path: path.stat().st_mtime)


def load_latest_manifest(kit: Path | None) -> dict[str, object] | None:
    if kit is None:
        return None
    manifest = kit.parent / "stem-kit.json"
    if not manifest.exists():
        return None
    with manifest.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def check_repo() -> list[Check]:
    checks: list[Check] = []
    checks.append(Check("repo root", (ROOT / ".git").exists(), str(ROOT)))
    hooks = git_config("core.hooksPath")
    checks.append(Check("pre-commit hook", hooks == ".githooks", f"core.hooksPath={hooks or '<unset>'}"))
    autocrlf = git_config("core.autocrlf")
    checks.append(Check("line ending policy", autocrlf == "false", f"core.autocrlf={autocrlf or '<unset>'}"))
    checks.append(Check("git audio firewall", (ROOT / ".gitignore").exists() and (ROOT / ".githooks" / "pre-commit").exists(), ".gitignore + .githooks/pre-commit"))
    return checks


def check_tools() -> list[Check]:
    checks = [
        Check("python", shutil.which("python") is not None, shutil.which("python") or "not found"),
        Check("stem generator", (ROOT / "scripts" / "generate-stem-kit.py").exists(), "scripts/generate-stem-kit.py"),
        Check("native cockpit", (ROOT / "MaloSound-Studio.ps1").exists(), "MaloSound-Studio.ps1"),
        Check("dsp build script", (ROOT / "scripts" / "build-dsp.ps1").exists(), "scripts/build-dsp.ps1"),
    ]
    cmake = shutil.which("cmake")
    cxx = shutil.which("g++") or shutil.which("clang++")
    checks.append(Check("cmake", cmake is not None, cmake or "not found; direct compiler fallback is OK if clang++/g++ exists"))
    checks.append(Check("C++ fallback compiler", cxx is not None, cxx or "not found"))
    return checks


def check_audio_safety() -> list[Check]:
    status = git_status_paths()
    visible_audio = [path for path in status if Path(path).suffix.lower() in AUDIO_EXTS]
    staged_audio = [path for path in staged_paths() if Path(path).suffix.lower() in AUDIO_EXTS]
    return [
        Check("audio visible to git", not visible_audio, ", ".join(visible_audio) if visible_audio else "none"),
        Check("audio staged", not staged_audio, ", ".join(staged_audio) if staged_audio else "none"),
    ]


def check_paths() -> list[Check]:
    library = Path(os.environ.get("XIV_MUSIC_LIBRARY", r"C:\Users\Green Machine\Music\XIV Music Library"))
    backup = os.environ.get("MALOSOUND_BACKUP_ROOT")
    checks = [
        Check("projects folder", PROJECTS.exists(), relative(PROJECTS)),
        Check("music library", library.exists(), str(library)),
    ]
    if backup:
        root = Path(backup).anchor
        checks.append(Check("backup root", bool(root and Path(root).exists()), backup))
    else:
        checks.append(Check("backup root", None, "MALOSOUND_BACKUP_ROOT not set"))
    return checks


def check_stems() -> list[Check]:
    kit = latest_stem_kit()
    manifest = load_latest_manifest(kit)
    if kit is None:
        return [Check("latest stem kit", False, "none found; run scripts/generate-stem-kit.ps1")]
    stems = manifest.get("stems", []) if isinstance(manifest, dict) else []
    wav_count = len([path for path in kit.parent.glob("*.wav")])
    expected = len(stems) if isinstance(stems, list) and stems else 6
    return [
        Check("latest stem kit", True, relative(kit)),
        Check("stem WAV count", wav_count >= expected, f"{wav_count} WAV files in {relative(kit.parent)}"),
        Check("stem manifest", manifest is not None, relative(kit.parent / "stem-kit.json")),
    ]


def run_fast_checks() -> list[Check]:
    checks: list[Check] = []
    code, output = run([sys.executable, "-m", "py_compile", "scripts/generate-stem-kit.py", "tools/studio_curves.py"])
    checks.append(Check("python syntax", code == 0, output or "compiled"))
    code, output = run([sys.executable, "scripts/generate-stem-kit.py", "--self-test"])
    checks.append(Check("stem generator self-test", code == 0, output or "self-test passed"))
    return checks


def print_group(title: str, checks: list[Check]) -> bool:
    print()
    print(title)
    print("-" * len(title))
    for check in checks:
        print(check.render())
    return all(check.ok is not False for check in checks)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check MaloSound local studio readiness.")
    parser.add_argument("--fast", action="store_true", help="Run fast syntax/self-test checks too.")
    args = parser.parse_args()

    groups = [
        ("Repo", check_repo()),
        ("Tools", check_tools()),
        ("Paths", check_paths()),
        ("Stem Kit", check_stems()),
        ("Audio Safety", check_audio_safety()),
    ]
    if args.fast:
        groups.append(("Fast Checks", run_fast_checks()))

    ok = True
    for title, checks in groups:
        ok = print_group(title, checks) and ok

    print()
    print("Next")
    print("----")
    if latest_stem_kit() is None:
        print("1. Generate stems: .\\scripts\\generate-stem-kit.ps1 -Session \"my-friend-first-pass\" -Bpm 106 -Bars 16")
    print("2. Build/test DSP: .\\scripts\\build-dsp.ps1")
    print("3. Open cockpit: .\\Open-MaloSound-Studio.bat")
    print("4. Keep WAVs under projects/ or the XIV Music Library; never force-add audio.")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
