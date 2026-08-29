# Start here

Written 2026-08-13, for you sitting down to code.

## Do this first (2 minutes)

```powershell
cd "C:\Users\Green Machine\XIV\malosound"
.\scripts\setup-repo.ps1
.\scripts\build-dsp.ps1
```

The second command should end in `67 checks, 0 failures`. If it does, the
analysis core works on your machine and you can start from a known-good state.

For the Windows recording workflow, open the native cockpit:

```powershell
.\Open-MaloSound-Studio.bat
```

Use it to generate the local utility stem kit, open the latest kit, and run DSP
checks without remembering command names.

Fast preflight:

```powershell
.\Open-MaloSound-Doctor.bat
```

Then set the backup destination, because right now nothing is protecting your
Live projects:

```powershell
setx MALOSOUND_BACKUP_ROOT "E:\malosound-backup"    # whatever drive you use
```

## What is already built

**`dsp/` — the analysis core, done and tested.** Realtime feature extraction:
RMS/peak, three-band energy, onset detection, and monophonic pitch. It is the
engine behind the Voice Mirror Bridge in `docs/ABLETON_PLUGIN_PLAN.md`, written
as plain C++17 with zero dependencies so it builds and tests offline.

Measured: pitch tracks 41 Hz to 660 Hz within 0.2% — low E on a bass through to
the 12th fret of the high E. Costs **1.1% of one core** against the plan's 2–3%
budget. Two tests count allocations in the audio path and fail the build if
anything allocates.

One thing worth knowing, because it will look like a bug: the build deliberately
does **not** use `-ffast-math`. Turning it on deletes the NaN guard (it implies
`-ffinite-math-only`), and one NaN from an upstream plugin poisons every filter
permanently — the bridge goes silent for the rest of the set with nothing in any
log. The test suite catches it. The reasoning is in `dsp/CMakeLists.txt`.

**Git foundation.** `.gitignore` rewritten, `.gitattributes` added, repo
initialised, first commit made, pre-commit hook enforcing the rules that
`.gitignore` cannot express.

**`scripts/strudel/`.** Your three templates, folded into the repo rather than
sitting in a second `malosound` folder. `lib/parts.js`, `tracks/_TEMPLATE/` and
`samples/README.md` were missing from what you sent, so they are written.

**`docs/BACKUP.md` + `scripts/backup-projects.ps1`.** The scheme for everything
git refuses to hold.

**Release provenance fixture.** `tools/run_release_pipeline.py` runs the local
AudioAnalysisV1, Ed25519 JSONL ledger, Strudel companion, ERC-2981-compatible
manifest, and release-package steps. `docs/RELEASE_PIPELINE.md` has the exact
commands. The fixture is complete; the final goal still needs a real WAV under
`projects/<session>/Recorded/`.

## What is not built, in the order I would do it

### 1. The JUCE wrapper around `dsp/` — the biggest single unlock

The analysis core is finished and tested. What does not exist is the plugin that
carries it into Live. That is genuinely the next thing: everything downstream —
the PC visual app, the whole bridge — is blocked on it, and nothing else is.

It is a small amount of code. `dsp/README.md` has the exact integration: three
calls, `prepare` / `process` / `popLatest`.

```
plugin/
  CMakeLists.txt        JUCE via FetchContent
  Source/
    PluginProcessor.*   owns a malosound::FeatureExtractor
    PluginEditor.*      diagnostics at 10 Hz: level, pitch, connection state
    FeatureSender.*     network thread, 30 Hz, drops old frames
```

Order that keeps you unblocked: get an empty VST3 loading in Live **first**,
before writing any bridge code. Plugin scanning and format quirks are where the
time actually goes, and finding that out on an empty plugin is much cheaper than
finding it out with a codebase attached.

Watch for: JUCE's `FetchContent` needs network on first configure. The parameter
list is already specified in `ABLETON_PLUGIN_PLAN.md` — use those exact names,
the visual app will key off them.

### 2. First Max for Live device

`devices/` is empty and the conventions are in place waiting for it. Good first
one: a **feature monitor** — a device showing what the DSP core sees (level,
pitch, band energies) as a live display. It makes the analysis visible before the
plugin exists, which makes debugging the plugin much less blind.

Read `devices/README.md` first. The freeze rule is enforced by the hook, and it
will block your first commit if the device is not frozen — that is working as
intended, not a bug to route around.

### 3. Victoria

`projects/2026-08-13_victoria/` is scaffolded with a `notes.md` waiting for key,
BPM and direction. The recording itself is still out of reach:

```
Desktop\00_XIV_COMMAND_CENTER\07_MALOSOUND_AUDIO_SYSTEM\vicotira9-08pm.mp3
```

That folder is not grantable to a cloud session. To get it in, add the Desktop
folder via **Add folder** in the desktop app, or drop the file into the project
folder yourself and fill in `notes.md`.

### 4. Record the Crimson into the library

`scripts/strudel/samples/README.md` is the how. This is the change that stops the
backing tracks sounding like a drum machine — the stock one-shots have thin
plastic character baked in and no amount of filtering fixes it. Three takes per
drum minimum; that is the point where it stops sounding sampled.

## A prompt to start the next session

Paste this into a fresh Cowork chat in the malosound project:

---

> Repo is at `C:\Users\Green Machine\XIV\malosound` — request access to that path
> alone first (batching it with Desktop/Documents/Music makes the whole request
> fail). Read `docs/START_HERE.md` and `docs/REPO_MAP.md` before touching
> anything; the git foundation, the DSP core, and the Strudel scaffold are done
> and I do not want them re-derived or re-litigated.
>
> Today I want to build the JUCE plugin wrapper around `dsp/`, per
> `docs/ABLETON_PLUGIN_PLAN.md`. Start with the smallest thing that loads as a
> VST3 in Ableton Live on Windows and shows a level meter — no networking, no
> feature sending yet. Then add the `FeatureExtractor` and the 30 Hz sender once
> the plugin actually scans and loads.
>
> Rules that apply: audio bytes never go in git; `.amxd` must be frozen and live
> in `devices/<Name>/dist/` with the `.maxpat` source in `src/`; `projects/` stays
> out of git; do not create a new project folder or duplicate work from another
> XIV lane. `.githooks/pre-commit` enforces most of this — if it blocks a commit,
> fix the cause rather than using `--no-verify`.
>
> The DSP core has no dependencies on purpose and its tests must keep passing.
> Do not add `-ffast-math` to any build — it deletes the NaN guard, and
> `dsp/CMakeLists.txt` explains why.

---

Swap the middle paragraph for whichever of the four items above you want to work
on. The rest of it is the part worth keeping every time — it is what stops a
fresh session from rebuilding things that already work.

## If something looks wrong

- **A commit is blocked.** Read the message; it names the rule and the fix. The
  hook is checking for an unfrozen device, an audio file, or a >20 MB file.
- **`dsp` tests fail on NaN.** Something turned on `-ffast-math`. See above.
- **Strudel patterns die mid-session.** Almost always a `gm_` soundfont failing
  silently over the network. Every template here uses synths for that reason —
  `reference/cheatsheet.md` has the full triage list.
- **A Live set opens with missing files.** Point Live at the library once, then
  **File → Collect All and Save**.

## Housekeeping from the session that set this up

Two bits of debris, neither harmful, both trivial to clear **from Windows** —
they exist because a cloud session reaches your disk through a bridge that is not
allowed to delete files.

**`_to_delete/`** holds the transfer archive, some stale git lock files, and a
throwaway `TestDevice` used to verify the pre-commit hook actually blocks what it
claims to. Nothing in it is needed. It is gitignored. Delete the whole folder.

**`.git/objects/**/tmp_obj_*`** are orphaned temporary objects from git
operations that could not clean up after themselves. Harmless — git ignores
anything not matching an object name — but to tidy:

```powershell
git gc --prune=now
```

Also worth knowing: git run **from a cloud session over the folder bridge** leaves
a `.git/*.lock` behind after every operation, because the mount forbids unlink.
Git run **natively on Windows, by you** has no such problem. So use git yourself
as normal; if a future cloud session reports "Another git process seems to be
running", that is this, and the fix is deleting the stale `.lock` file.
