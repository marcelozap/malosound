# Repo map — where things go and why

The single organising idea: **git holds text and small source; the library holds
audio; the backup drive holds everything git refuses.** Every decision below
follows from that.

```
malosound/
├── .githooks/pre-commit     enforces the rules .gitignore cannot express
├── .gitattributes           stops git line-merging Ableton and Max binaries
├── .gitignore               the audio firewall — read its header comment
├── LIBRARY_PATH.md          where the bytes actually live
│
├── ableton/                 templates (.als), racks (.adg), clips (.alc)
├── devices/                 Max for Live — src/*.maxpat + dist/*.amxd per device
├── dsp/                     C++17 analysis core. Builds and tests offline.
├── docs/                    plans, this map, backup scheme, start-here
├── projects/                Live sets — IGNORED BY GIT ENTIRELY
├── releases/                release metadata. No master audio.
└── scripts/
    ├── backup-projects.ps1  the only thing protecting projects/
    ├── build-dsp.ps1
    ├── setup-repo.ps1/.sh   run once per clone — enables the hook
    └── strudel/             live-coded backing tracks
```

## The four homes, and how to pick

| Thing | Home | In git? |
|---|---|---|
| C++ analysis code | `dsp/` | yes |
| Max device source | `devices/<N>/src/*.maxpat` | yes |
| Max device build | `devices/<N>/dist/*.amxd` | yes, **frozen only** |
| Strudel pattern + song notes | `scripts/strudel/tracks/<song>/` | yes |
| Live set, takes, imported samples | `projects/<date>_<song>/` | **no** — backup |
| Samples, loops, stems | `XIV Music Library\` | **no** — never moves |
| Release metadata, art, lyrics | `releases/<date>_<title>/` | yes |
| Master audio | library | **no** — pointed at from release.md |

## A song exists in two places, on purpose

- **`scripts/strudel/tracks/victoria/`** — `pattern.js`, `notes.md`. Text. In git,
  diffed, and recoverable from any clone.
- **`projects/2026-08-13_victoria/`** — the Live set, the recorded takes, the
  bounces. Binary and large. Out of git, covered by the backup script.

Put a line in each pointing at the other. Splitting a song across two homes is
worth it because the two halves have opposite needs: one wants version control,
the other wants a mirror on a second drive, and no single mechanism does both
well.

Audio dropped inside a Strudel track folder is ignored automatically — every
audio extension is excluded repo-wide — so you never have to think about which
side of the line a `.wav` falls on.

## The three rules that cost work when broken

**1. Audio bytes never go in git.** Not as a master, not "just this once", not
behind a negation rule. Git keeps every version of every binary forever, in every
clone, on every machine, and there is no clean way to take it back out later.

**2. `.amxd` must be frozen, `.maxpat` must be committed.** Unfrozen devices open
to errors on the other machine in the rig. Binaries without source cannot be
reviewed or repaired. The hook checks both.

**3. `projects/` is not backed up by git and never will be.** `Samples/Imported/`
lives inside it, is not regenerable, and no `.gitignore` rule can reach it.
`scripts/backup-projects.ps1` is the whole defence. Set
`MALOSOUND_BACKUP_ROOT` or that defence does not exist.

## Where the risk actually is

Ranked by how much work is lost when it goes wrong:

1. `Samples/Imported/` with no backup configured — unrecoverable
2. An unfrozen device shipped to the other machine — silent until a live set
3. A master committed to git — repo bloats permanently, painful to undo
4. A `.maxpat` merge conflict resolved by git — corrupt patcher, opens to nothing

Items 2, 3 and 4 are blocked by the pre-commit hook. Item 1 is the one that is
still on you, which is why `docs/BACKUP.md` is written the way it is.
