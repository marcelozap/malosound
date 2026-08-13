# strudel — live-coded backing tracks

Everything music-code lives here. One rule: **never start from a blank editor.**

```
scripts/strudel/
  lib/parts.js    menu of parts — copy from it, don't rewrite them
  templates/      genre starting points. COPY, never edit in place
  tracks/         one folder per song. This is where real work happens
  samples/        your own recorded one-shots + hosting notes
  reference/      cheatsheet, key/tempo tables
  ideas/          junk drawer. No rules, no naming, dump freely
```

> **Note on where this lives.** This arrived as a standalone `malosound/` folder
> meant to be unzipped into the user folder. That would have created a second
> `malosound` next to the real repo at `C:\Users\Green Machine\XIV\malosound` —
> two trees with the same name, and the XIV rule against duplicating work across
> lanes says pick one. It is folded in here instead. The Strudel template was
> always specified as a `scripts/` deliverable, not a separate project.
>
> Nothing was lost in the move: all three templates and both reference docs are
> the originals, byte for byte. `lib/parts.js`, `tracks/_TEMPLATE/` and
> `samples/README.md` were missing from the upload and have been written.

## The workflow

1. New song → copy `tracks/_TEMPLATE/` to `tracks/song-name/`
2. Copy the closest thing from `templates/` into it as `pattern.js`
3. Fill in `notes.md` **first** — BPM, key, reference track. Two minutes now
   saves you from a song with no identity later
4. Work in `tracks/song-name/pattern.js`. Never touch `templates/`

```powershell
Copy-Item -Recurse scripts\strudel\tracks\_TEMPLATE scripts\strudel\tracks\victoria
Copy-Item scripts\strudel\templates\halftime-152.js scripts\strudel\tracks\victoria\pattern.js
```

## Why templates are read-only by convention

The moment you edit a template to fit one song, it stops being a template.
Copy it every time. If you improve something in a track and it's genuinely
general, *then* fold it back into `templates/`.

## Your three lanes (they don't mix — keep them separate)

| Lane | BPM | Where | What it's for |
|---|---|---|---|
| Drake half-time | 152 | `templates/halftime-152.js` | the dark anthemic record |
| Latin house | 122 | `templates/house-122.js` | the dance record |
| Blues shuffle | 88 | `templates/blues-88.js` | building hands, not records |

Don't try to merge these. Three separate projects.

## Naming bounces

`songname_v3_2026-08-13.wav`

Version *and* date. When there are nine of them and you need the one from
before you ruined the mix, this is the only thing that saves you.

## What git does and does not keep in here

`tracks/` **is** version controlled — `pattern.js` and `notes.md` are text, they
diff, and they are the part you cannot re-derive. But every audio extension is
ignored repo-wide, so a `.wav` you drop in `tracks/song-name/audio/` stays on
disk and out of git automatically. You do not have to think about it.

Live sets are the opposite: `projects/` is ignored wholesale and is covered by
`docs/BACKUP.md` instead. So a song that exists in both worlds has its Strudel
pattern here and its Live set in `projects/`. Put a line in each pointing at the
other.

## Synths, not soundfonts

Every template uses `.sound("sawtooth")` / `"triangle"` / `"sine"` rather than
`gm_` soundfonts. Soundfonts fetch over the network and fail **silently** —
the pattern just stops halfway through a session with nothing in the console.
That is the fix for patterns dying mid-set. Keep it that way.

The sample-based drums (`bd`, `sd`, `stomp`, `bongo`) come from the one
`samples('github:tidalcycles/dirt-samples')` call at the top of each file, which
loads once and is cached. That one is fine.
