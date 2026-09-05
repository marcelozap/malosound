# MaloSound.ai

**How I hear the market.**

MaloSound.ai is my personal journal of the market as an artist. I share writings,
music, and a developing theory: one song per market day, each the same duration,
with a different expression inspired by each session.

The journal has two editions: a personal reading before the open, followed by
the day's song and reflection after the close. XIV is my trading system product;
MaloSound is my voice as an artist.

The public website starts at `index.html`. Read the opening essay at
[`One song. One session.`](writings/one-song-one-session.html). See
[`docs/WEBSITE_HANDOFF.md`](docs/WEBSITE_HANDOFF.md) for publishing the daily editions.

The studio also holds the music tools behind the practice: Max for Live devices,
DSP, Ableton workflows, and releases.

**New here, or coming back after a break? → [`docs/START_HERE.md`](docs/START_HERE.md)**

**An artist wanting to release through this? → [`docs/FOR_ARTISTS.md`](docs/FOR_ARTISTS.md)**

**Website handoff for `malosound.ai` → [`docs/WEBSITE_HANDOFF.md`](docs/WEBSITE_HANDOFF.md)**

**Creative technology proof lane → [`docs/CREATIVE_TECH_PROOF_LANE.md`](docs/CREATIVE_TECH_PROOF_LANE.md)**

## First thing, on every machine

```powershell
.\scripts\setup-repo.ps1      # macOS/Linux: ./scripts/setup-repo.sh
```

This enables the pre-commit hook. Git does not version `core.hooksPath`, so
without this step the rules that keep audio and unfrozen devices out of the repo
are not running.

## The one rule

**Audio bytes never go in git.** The repo holds code and configuration. The
library holds the audio:

```
C:\Users\Green Machine\Music\XIV Music Library\
```

See [`LIBRARY_PATH.md`](LIBRARY_PATH.md). Everything else in
[`docs/REPO_MAP.md`](docs/REPO_MAP.md) follows from this.

## Windows studio cockpit

```powershell
.\Open-MaloSound-Studio.bat
```

This opens the local cockpit for the first DAW workflow: generate utility stems,
open the latest stem kit, run DSP checks, and jump to the recording docs. See
[`docs/NATIVE_STUDIO_COCKPIT.md`](docs/NATIVE_STUDIO_COCKPIT.md).

Fast preflight:

```powershell
.\Open-MaloSound-Doctor.bat
```

## What is in here

| | |
|---|---|
| [`dsp/`](dsp/) | C++17 realtime analysis core — pitch, bands, onset, level. No dependencies, tests offline in a second. |
| [`devices/`](devices/) | Max for Live. Unfrozen `.maxpat` source + frozen `.amxd` build, both committed. |
| [`scripts/strudel/`](scripts/strudel/) | Live-coded backing tracks. Three lanes: half-time 152, Latin house 122, blues 88. |
| [`scripts/generate-stem-kit.ps1`](scripts/generate-stem-kit.ps1) | Local utility stem generator for count-in, click, sidechain pulse, movement cues, and silence beds. Writes under ignored `projects/` by default. |
| [`ableton/`](ableton/) | Templates, racks, clips. |
| [`artists/`](artists/) | The artist registry. One folder per artist: public identity, ledger, releases. Private keys never enter git. |
| [`releases/`](releases/) | maloSound's own release bundles. No master audio — see the folder README. |
| `projects/` | Live sets. **Not in git.** Covered by [`docs/BACKUP.md`](docs/BACKUP.md). |

## Build and test the analysis core

```bash
cmake -S dsp -B dsp/build && cmake --build dsp/build
ctest --test-dir dsp/build --output-on-failure
```

67 checks, about a second. Windows: `.\scripts\build-dsp.ps1`.

## Generate local utility stems

```powershell
.\scripts\generate-stem-kit.ps1 -Session "my-friend-first-pass" -Bpm 106 -Bars 16
```

The WAVs are generated under ignored `projects/` by default. See
[`docs/STEM_GENERATION.md`](docs/STEM_GENERATION.md).

## Run the local release provenance pipeline

```powershell
python tools\run_release_pipeline.py --self-test
```

That proves the fixture path only. The real release audit requires a WAV under
`projects\<session>\Recorded\`. See [`docs/RELEASE_PIPELINE.md`](docs/RELEASE_PIPELINE.md).

## Back up the things git cannot

```powershell
setx MALOSOUND_BACKUP_ROOT "E:\malosound-backup"   # once
.\scripts\backup-projects.ps1                       # after any session
```

`Samples/Imported/` is not regenerable and no `.gitignore` rule can protect it.
This script is the only thing that does. [`docs/BACKUP.md`](docs/BACKUP.md)
explains why.
