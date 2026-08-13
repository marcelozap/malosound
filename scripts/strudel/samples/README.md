# Your own samples in Strudel

The built-in `bd`, `cp`, `perc` are 8-bit-era one-shots. The thin plastic
character is baked into the recording — filtering will not save them. The way
out is your own audio: the Crimson kit, the guitar, a chair, a door.

## Where the bytes live

**Not here.** Same rule as the rest of the repo: this folder holds the notes and
the manifest, the library holds the audio.

    C:\Users\Green Machine\Music\XIV Music Library\

Record one-shots into the library's drop inbox, then move them to a numbered
folder. See `LIBRARY_PATH.md` at the repo root.

## Getting them into Strudel

Strudel runs in a browser, so it can only load samples over HTTP. Three ways,
easiest first.

### 1. GitHub repo (recommended)

A separate **public** repo holding only audio — not this one, which must stay
free of audio bytes.

    xiv-samples/
      strudel.json
      crimson/
        kick-01.wav  kick-02.wav
        snare-01.wav snare-02.wav
        hat-cl-01.wav

`strudel.json` maps names to files:

```json
{
  "_base": "https://raw.githubusercontent.com/<user>/xiv-samples/main/",
  "crimsonkick":  ["crimson/kick-01.wav", "crimson/kick-02.wav"],
  "crimsonsnare": ["crimson/snare-01.wav", "crimson/snare-02.wav"],
  "crimsonhat":   ["crimson/hat-cl-01.wav"]
}
```

Then in a pattern:

```js
samples('github:<user>/xiv-samples')

$: s("crimsonkick ~ crimsonsnare ~").gain(0.9)
$: s("crimsonkick:1")     // :1 picks the second variant
```

Multiple files under one name is the whole point — Strudel rotates through them,
so repeated hits stop sounding machine-stamped. **Record at least three takes of
every drum you care about.** Two is noticeably better than one; three is where it
stops sounding sampled.

### 2. Local server, for fast iteration

```powershell
cd "C:\Users\Green Machine\Music\XIV Music Library"
python -m http.server 5432
```

```js
samples('http://localhost:5432/strudel.json')
```

Instant, no commit-push cycle, and it dies when you close the terminal. Good for
an evening of auditioning. Do not build a track on it — the pattern will not play
on any other machine, or on yours tomorrow.

### 3. Drag and drop

Strudel accepts files dropped onto the editor. Fine for a one-off. It does not
survive a reload, so nothing you want to keep should depend on it.

## Recording the Crimson for sampling

- One hit per file, trimmed hard to the transient. Leading silence reads as
  latency and it will not sit in the grid.
- Keep the tail. Cutting a cymbal short is audible; you can always shorten it in
  Strudel with `.release()`, but you cannot add decay back.
- Three or more takes per drum, at the velocity you actually play — not the
  hardest you can hit.
- 48 kHz to match the interface. Mono for drums, unless the overheads are the
  point.
- Name them `<drum>-<nn>.wav`. Sortable, and the numbering is what the variant
  index maps onto.

## Naming, once it is in a pattern

Lowercase, no separators — `crimsonkick`, not `crimson_kick` or `Crimson-Kick`.
Strudel's mini-notation treats `-` and `_` as pattern syntax, so a hyphen in a
sample name is a bug you will spend twenty minutes on.
