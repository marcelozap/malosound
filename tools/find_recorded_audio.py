#!/usr/bin/env python3
"""Find candidate recorded audio files and print the release pipeline command."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIO_EXTENSIONS = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".m4a"}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "malosound-release"


def is_recorded_candidate(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return path.suffix.lower() in AUDIO_EXTENSIONS and "recorded" in parts


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def find_candidates(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and is_recorded_candidate(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Find recorded maloSound audio and print pipeline commands.")
    parser.add_argument("--projects", type=Path, default=REPO_ROOT / "projects")
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    candidates = find_candidates(args.projects)
    if not candidates:
        print("No recorded audio found under projects/**/Recorded/.")
        print('Expected shape: projects\\<session>\\Recorded\\<track>.wav')
        return 1

    for path in candidates:
        title = args.title or path.stem.replace("_", " ").replace("-", " ").title()
        slug = slugify(title)
        rel = relative(path)
        print(rel)
        print(f'python tools\\run_release_pipeline.py --audio "{rel}" --title "{title}" --slug "{slug}"')
        print(f'python tools\\verify_release_package.py "releases\\{slug}" --require-recorded')
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
