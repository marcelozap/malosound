# malosound — condensed session prompt

Paste this into a fresh chat to restore full context. It replaces the whole prior
thread; nothing else needs to be carried over.

---

You own the **malosound** lane (music and audio — Max for Live devices, DSP,
Ableton, releases). Everything below is verified ground truth as of 2026-08-13.
Do not re-derive it.

## 1. Paths — the standing instructions are wrong, use these

| What | Real path | Status |
|---|---|---|
| **The repo** | `C:\Users\Green Machine\XIV\malosound` | Grantable. Request it first. |
| Cowork "malosound" folder | `C:\Users\Green Machine\Claude\Projects\malosound` | **Empty — not the repo. Ignore it.** |
| Sample library | `C:\Users\Green Machine\Music\XIV Music Library\` | Not grantable so far. Reference only, never move. |
| Ableton plan (origin) | `Documents\ChatGPT\gateKPT-conflict-fix\` | Not grantable. **No longer needed — already claimed.** |
| Victoria recording | `Desktop\00_XIV_COMMAND_CENTER\07_MALOSOUND_AUDIO_SYSTEM\vicotira9-08pm.mp3` | Not grantable. Blocked. |

Project instructions say the repo is at `C:\Users\XIV\malosound`. It is not.
The home dir is `C:\Users\Green Machine`.

**Folder access:** requesting the repo alone succeeds. Requesting it batched with
the Desktop / Documents / Music folders fails outright ("can't be granted") — the
whole batch dies, so never batch them. If you need the Victoria mp3 or the sample
library, ask Marcelo to add the folder via the desktop app's **Add folder** button.

## 2. Repo state — verified, not assumed

```
malosound/
├── .gitignore              179 B — has real problems, see §3
├── LIBRARY_PATH.md         561 B — correct, leave alone
├── ableton/{clips,racks,templates}/   all empty
├── devices/                empty
├── docs/ABLETON_PLUGIN_PLAN.md        4265 B — ALREADY CLAIMED ✅
├── dsp/{include,src,tests}/           all empty
├── projects/               empty  — Victoria not filed yet
├── releases/               empty
└── scripts/                empty
```

Two things that are easy to get wrong:

- **There is no `.git`.** `git rev-parse` fails. The repo has never been
  initialised. None of the .gitignore rules are doing anything yet.
- **There is no `.gitattributes`.**

`docs/ABLETON_PLUGIN_PLAN.md` is the *Voice Mirror Bridge* design — JUCE C++,
VST3 + AU, extracts pitch/level/bands/onset from the DAW and streams ~30 Hz
feature frames over WebSocket/OSC to a PC visual app. Lock-free audio callback,
no allocations. It belongs to the gateKPT MacBook+PC rig. **Already in `docs/` —
do not re-claim it.**

## 3. The .gitignore — current contents and what's wrong

```gitignore
projects/
Backup/
*.als.bak
Samples/Processed/
*.asd
*.maxpat.bak
*.maxhelp
*.wav
*.aiff
*.aif
*.flac
*.mp3
*.m4a
bounces/
!releases/**/masters/*
artifacts/
_to_delete/
Thumbs.db
```

Five defects, in rough order of how much work they can lose:

1. **`.amxd` / `.maxpat` policy is entirely absent.** The stated rule — freeze
   `.amxd` before committing, keep the unfrozen `.maxpat` in
   `devices/<Name>/src/` as the diffable source — is encoded nowhere. This is
   flagged as the highest-risk area in the lane and the file is silent on it.

2. **No `.gitattributes`, so binaries get mangled.** `.amxd`, `.als`, `.adg`,
   `.adv` need `binary` / `-diff -merge` marks or git will attempt text merges
   on them.

3. **`Samples/Processed/` is a dead rule, and `Samples/Imported/` is unprotected.**
   Both folders only ever exist *inside* a Live project folder, and `projects/`
   is ignored wholesale on line 1 — so neither rule can ever fire. The
   "Imported/ is not regenerable, keep it" requirement **cannot be satisfied by
   .gitignore at all.** It has to be satisfied by the backup scheme. Anyone
   reading this file will believe Imported/ is safe. It is not.

4. **`!releases/**/masters/*` contradicts "audio bytes never go in git."**
   The negation works mechanically (last-match-wins, and the excludes above it
   are file patterns not dir patterns), which is the problem — it will happily
   commit multi-MB masters. Decide: Git LFS, or keep masters out and track only
   release metadata.

5. **Missing `.DS_Store`.** The Ableton plan targets a MacBook + PC rig, so mac
   noise will land in this repo. Also worth adding: `desktop.ini`,
   `Ableton Project Info/`. And `ableton/templates/` is meant to hold binary
   `.als` templates that nothing currently covers.

## 4. Open work, highest-stakes first

- [ ] **Git foundation.** Rewrite `.gitignore` fixing §3, add `.gitattributes`,
      `git init`, first commit.
- [ ] **Backup scheme for `projects/`.** Live sets stay out of git entirely —
      propose a scheme instead, and make it cover `Samples/Imported/`, which
      §3.3 shows git will never protect.
- [ ] **Strudel house template.** Custom strudel.cc template for house, to play
      guitar over live. Lands in `devices/` or `scripts/` — **not** a new project.
- [ ] **Victoria.** `projects/2026-08-XX_victoria/Recorded/` + `notes.md` with
      key, bpm, direction. Blocked on folder access; the scaffold can be built
      now and the mp3 dropped in later.

## 5. The artist — shapes every creative call

- Guitar and bass; Alesis Crimson e-kit; records via audio interface.
- Writes in Spanish and English, **wants Spanish in the songs partly as practice.**
- Prefers **second-person / universal lyrics** over first-person confessional.
- Current direction: **dark, anthemic, half-time**, Latin flavour under consideration.
- Guitar tone he's after: the U2 "Beautiful Day" / The Fray register — electric
  but not overbearing, smooth, powerful, light, direct.
- Uses **Strudel** (strudel.cc) for live-coded backing tracks to play guitar over.

## 6. House rules for this lane

- **Audio bytes never go in git.** The repo references the library; the library
  holds the bytes. Never move `XIV Music Library` into the repo.
- `projects/` (Live sets) stay out of git entirely.
- Do not create new projects or duplicate work across XIV lanes — route to the
  correct lane.
- Visual identity (`06_XIV_VISUAL_STANDARD.md`): dark cyberpunk — near-silhouetted
  figure in an emissive wraparound visor, rain-slick neon city, cyan and magenta
  on near-black. **malosound has the most licence to go full-bloom** — cover art
  and waveform displays are where the aesthetic gets loud.
- No "fantasy village" / kid-game framing, ever.
- End every session with the handoff block from `02_ROUTING_MAP.md` (that file is
  not currently reachable — ask for it if the block is needed verbatim).

---

**Start by** requesting access to `C:\Users\Green Machine\XIV\malosound` alone,
then pick up §4.
