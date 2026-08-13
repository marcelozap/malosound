# malosound

Music and audio: Max for Live devices, DSP, Ableton, releases.

**New here, or coming back after a break? → [`docs/START_HERE.md`](docs/START_HERE.md)**

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

## What is in here

| | |
|---|---|
| [`dsp/`](dsp/) | C++17 realtime analysis core — pitch, bands, onset, level. No dependencies, tests offline in a second. |
| [`devices/`](devices/) | Max for Live. Unfrozen `.maxpat` source + frozen `.amxd` build, both committed. |
| [`scripts/strudel/`](scripts/strudel/) | Live-coded backing tracks. Three lanes: half-time 152, Latin house 122, blues 88. |
| [`ableton/`](ableton/) | Templates, racks, clips. |
| [`releases/`](releases/) | Release metadata. No master audio — see the folder README. |
| `projects/` | Live sets. **Not in git.** Covered by [`docs/BACKUP.md`](docs/BACKUP.md). |

## Build and test the analysis core

```bash
cmake -S dsp -B dsp/build && cmake --build dsp/build
ctest --test-dir dsp/build --output-on-failure
```

67 checks, about a second. Windows: `.\scripts\build-dsp.ps1`.

## Back up the things git cannot

```powershell
setx MALOSOUND_BACKUP_ROOT "E:\malosound-backup"   # once
.\scripts\backup-projects.ps1                       # after any session
```

`Samples/Imported/` is not regenerable and no `.gitignore` rule can protect it.
This script is the only thing that does. [`docs/BACKUP.md`](docs/BACKUP.md)
explains why.
