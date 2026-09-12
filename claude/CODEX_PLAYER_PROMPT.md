# Codex: build the MaloSound player page

You own the page. Claude owns generation. Everything the page needs is already
generated, tested and committed; this prompt is complete enough to execute
without asking Marcelo anything. Where a value is stated below it is fixed —
render it, do not expose it.

## Work from

- Repository: `C:\MaloSound\Workspace\market-journal-site` (GitHub `marcelozap/malosound`).
- Branch: **`claude/instrument-data-layer`**, commit **`3c1d483`** (the
  data, the build boundary and `docs/INSTRUMENT_AUDIO.md`). This prompt is the
  following commit on the same branch. Make your own worktree from that branch
  (`git worktree add ..\player-worktree claude/instrument-data-layer`); do not
  switch the shared checkout's branch and do not touch `claude/…` branches'
  history.
- Read first: `docs/INSTRUMENT_AUDIO.md`, `tools/instrument_session.py`
  (module docstring), one document such as `content/instrument/2026-09-04.json`.
- Files you change: `index.html`, `site.css`. Put the player script **inline**
  in `index.html` (one `<script>` block) so no new file needs an allowlist
  entry. Do not edit `tools/`, `content/`, `assets/orbits/`, `docs/INSTRUMENT_AUDIO.md`
  or anything under `claude/`. If you need something from Claude's lane, append
  a request to `C:\MaloSound\handoff\website\PARALLEL_WORK.md`.
- Before editing, append a claim to `PARALLEL_WORK.md` naming `index.html` and
  `site.css`.

## The data contract — every field of `content/instrument/<date>.json`

Fetched same-origin at `/content/instrument/<date>.json`. Eight documents
exist: 2026-08-31, 2026-09-01, 2026-09-02, 2026-09-03, 2026-09-04, 2026-09-08,
2026-09-09, 2026-09-10. Types are exact; array lengths shown are those of
2026-09-04 and vary per document.

```
schemaVersion: integer
date: string
symbol: string
source: object
source.path: string
source.sha256: string
source.observations: integer
source.firstMinute: integer
source.lastMinute: integer
source.missingMinutes: array [0]
method: object
method.smoothing: object
method.smoothing.kind: string
method.smoothing.window: integer
method.smoothing.degree: integer
method.smoothing.spacingMinutes: integer
method.smoothing.edgeLossEachSide: integer
method.smoothing.derivatives: string
method.smoothing.gaps: string
method.anchors: object
method.anchors.low: number
method.anchors.high: number
method.anchors.frozen: boolean
method.anchors.sessionOpenIsAnchor: boolean
method.anchors.source: string
method.landmarks: array [8]
method.notes: array [8]
method.semitones: array [8]
method.hueDegreesPerSemitone: integer
method.colour: object
method.colour.model: string
method.colour.lightness: number
method.colour.chroma: number
method.colour.note: string
method.colour.palette: array [8]
method.colour.palette[].landmark: integer
method.colour.palette[].note: string
method.colour.palette[].semitone: integer
method.colour.palette[].hue: integer
method.colour.palette[].oklch: string
method.colour.palette[].srgbFallback: string
method.tieRule: string
method.flatRule: string
method.orbit: object
method.orbit.x: string
method.orbit.y: string
method.orbit.path: string
parent: object
parent.definition: string
parent.sessions: array [5]
parent.observedSessions: array [5]
parent.missingSessions: array [0]
parent.samplingMinutes: integer
parent.observationMinutes: string
parent.observationsPerSession: integer
parent.smoothing: object
parent.smoothing.kind: string
parent.smoothing.window: integer
parent.smoothing.degree: integer
parent.smoothing.spacingMinutes: integer
parent.smoothing.edgeLossEachSide: integer
parent.smoothing.gaps: string
parent.runs: array [6]
parent.runs[].date: string
parent.runs[].startMinute: integer
parent.runs[].endMinute: integer
parent.runs[].observations: integer
parent.runs[].derivedFrom: integer
parent.runs[].derivedTo: integer
parent.runs[].points: array [68]
parent.runs[].points[].minute: integer
parent.runs[].points[].close: number
parent.runs[].points[].smoothed: number
parent.runs[].points[].velocity: number
parent.runs[].points[].acceleration: number
parent.runs[].points[].position: number
parent.runs[].points[].landmark: integer
parent.runs[].points[].note: string
parent.runs[].points[].semitone: integer
parent.runs[].points[].hue: integer
parent.derivedObservations: integer
parent.sessionDay: object
parent.sessionDay.date: string
parent.sessionDay.derivedObservations: integer
parent.sessionDay.noteEvents: array [6]
parent.sessionDay.noteEvents[].startMinute: integer
parent.sessionDay.noteEvents[].endMinute: integer
parent.sessionDay.noteEvents[].minutes: integer
parent.sessionDay.noteEvents[].landmark: integer
parent.sessionDay.noteEvents[].note: string
parent.sessionDay.noteEvents[].semitone: integer
parent.sessionDay.noteEvents[].hue: integer
flat: boolean
derivedObservations: integer
bounds: object
bounds.maxAbsVelocity: number
bounds.maxAbsAcceleration: number
runs: array [1]
runs[].startMinute: integer
runs[].endMinute: integer
runs[].observations: integer
runs[].derivedFrom: integer
runs[].derivedTo: integer
runs[].points: array [380]
runs[].points[].minute: integer
runs[].points[].close: number
runs[].points[].smoothed: number
runs[].points[].velocity: number
runs[].points[].acceleration: number
runs[].points[].position: number
runs[].points[].landmark: integer
runs[].points[].note: string
runs[].points[].semitone: integer
runs[].points[].hue: integer
noteEvents: array [12]
noteEvents[].startMinute: integer
noteEvents[].endMinute: integer
noteEvents[].minutes: integer
noteEvents[].landmark: integer
noteEvents[].note: string
noteEvents[].semitone: integer
noteEvents[].hue: integer
```

Reading notes:
- `runs[].points[]` is the orbit, in time order within a run. `velocity` is x,
  `acceleration` is y. Points are never joined across runs (`runs[]` are
  separated by missing minutes) and the last point is never joined to the first.
- `bounds.maxAbsVelocity` and `bounds.maxAbsAcceleration` are the per-session
  extremes for fitting the frame. Scale each axis by its own extreme.
- `method.colour.palette[landmark]` gives the segment colour: use `oklch` when
  `CSS.supports('color', 'oklch(0.5 0.1 0)')`, else `srgbFallback`. Colour a
  segment by the landmark of the point it ends at.
- `noteEvents[]` is stem 1. `parent.sessionDay.noteEvents[]` is stem 2. Both
  use session minutes; both stems start at minute 0.
- `source.missingMinutes` and `parent.missingSessions` are facts to respect,
  never to fill.

## The two stems — rules, verbatim from `docs/INSTRUMENT_AUDIO.md`

# Instrument audio: the two stems

Everything below is fixed. A page renders these rules; it does not expose them,
and a visitor cannot change them. Both stems come only from price. Neither
reads a trade record.

Source of truth: `content/instrument/<date>.json`, written by
`tools/instrument_session.py`. Reference renderer: `tools/instrument_audio.py`
(NumPy, deterministic: the same document always yields the same bytes).

## Clock

- One session minute = **0.5 s**. Minute 0 is 09:30 ET. A full session is
  **195 s** (390 minutes). Both stems share this clock and start together at
  minute 0.
- A note starts at `startMinute × 0.5 s` and stops at `(endMinute + 1) × 0.5 s`.
- Consecutive events in a stem are contiguous: no overlap, no gap. Where the
  mapping derived nothing — the edge loss at each end of every run, and any
  missing observation — the stem is **silent**. Nothing is voiced that was not
  derived.

## Stem 1 — the session

- Events: the document's top-level `noteEvents`. Each is one held landmark of
  the session's one-minute closes, smoothed by the fixed Savitzky–Golay fit
  (11 observations, cubic, one-minute spacing, five lost at each edge of each
  run) and normalised against the **parent window's** anchors.
- Pitch: **A3 = 220 Hz** × 2^(semitone/12). Semitones by landmark:
  A 0, B 2, C 3, D 5, E 7, F 8, G 10, A′ 12. Eight landmarks, seven pitch
  classes; the top landmark is the octave return.
- Duration: `minutes × 0.5 s` — as long as the smoothed price held that
  landmark.
- Envelope: sine-squared attack **0.02 s**, cosine-squared release **0.08 s**,
  both inside the note.
- Silence: minutes 0–4 and the last five minutes of every run (2.5 s each);
  eleven minutes around any missing minute (the minute plus five lost on each
  side).

## Stem 2 — the parent window

- Events: `parent.sessionDay.noteEvents`. The parent window is the **trailing
  five trading sessions ending with the session**, each sampled as five-minute
  closes (the close of each five-minute block: session minutes 4, 9, …, 389;
  78 observations per session), smoothed by the same 11-observation cubic fit
  at five-minute spacing, five observations lost at each edge of each run.
  Each session is its own run; an overnight gap is never bridged. The stem
  voices only the observations that fall inside the session's own day.
- Anchors: the lowest and highest five-minute close across the parent's
  **observed** sessions, frozen once. The session open is not an anchor. A
  session the calendar expects but no public minute file covers is recorded
  in `parent.missingSessions` and contributes nothing; it is never invented.
  Stem 1 uses these same anchors, so both stems read one scale.
- Pitch: one octave below stem 1: **A2 = 110 Hz** × 2^(semitone/12), same
  semitones.
- Duration: each observation covers its whole five-minute block, so
  `minutes` is a multiple of 5 and a note lasts `minutes × 0.5 s` (2.5 s per
  observation held). `startMinute` is a multiple of 5; `endMinute` ends in 4.
- Envelope: attack **0.15 s**, release **0.40 s** — the slow layer.
- Silence: minutes 0–24 and 365–389 of the day (12.5 s each) from edge loss,
  plus five observations on each side of any missing block close.

## Voice (both stems)

- Additive tone: fundamental 1.0, second harmonic 0.35, third harmonic 0.15.
  Voice gain 0.5 before the shared mix gain.
- Structured so sampled notes (eight recordings of one voice singing A B C D
  E F G A′ on "ah") can replace the tone later: the pitch, start, stop and
  envelope rules above do not change; only the waveform does. Recording those
  samples is not a launch dependency.

## Mix

- One gain shared by both stems, chosen so that **session + parent peaks at
  −1 dBFS**. Each stem is written with that same gain. A page plays both at
  unity and gets the mix exactly; nothing clips.
- No compression, reverb, echo, randomness, swing, rhythm or per-day choice.

## Colour

- Hue = semitone × 30°, modulo 360, from A = 0°. Both A octaves share a hue.
- OKLCH lightness 0.80, chroma 0.16, fixed. `method.colour.palette` carries the
  exact `oklch()` string and a computed sRGB fallback for each landmark.

## Flat and empty cases

- A flat parent window (high == low) gives the tonic everywhere in both stems
  and a stationary orbit.
- A run shorter than eleven observations derives nothing and is silent.
- A document with no derived observations renders 195 s of silence at the
  shared gain of 1; nothing divides by zero.

### Implementing the rules in Web Audio (no libraries)

- Build both stems offline first so the shared mix gain is exact: an
  `OfflineAudioContext(1, 195 * 44100, 44100)` per stem. For each event create
  one `OscillatorNode` with a `PeriodicWave` of harmonics `[0, 1, 0.35, 0.15]`
  (real part zero, imaginary part those amplitudes, `disableNormalization: true`),
  frequency `base × 2^(semitone/12)` with base 220 (stem 1) or 110 (stem 2),
  feeding a `GainNode` whose value follows sine-squared attack and cosine-squared
  release (`setValueCurveAtTime` with a 128-point curve) inside the note, times
  the voice gain 0.5. Start at `startMinute × 0.5`, stop at `(endMinute + 1) × 0.5`.
- Render both, sum sample-wise to find the peak, scale **both** buffers by
  `10^(-1/20) / peak`. If the peak is zero leave them as they are.
- Play with two `AudioBufferSourceNode`s started at the same `context.currentTime`
  through one master `GainNode` (mute sets it to 0). Pause = stop both sources
  and remember the offset; play again = new sources from that offset, same
  start time. Replay from the end restarts at 0. The AudioContext is created or
  resumed only inside the click handler.
- Verify against the reference: `python -X utf8 tools/instrument_audio.py --date 2026-09-04 --output-dir <temp>`
  writes the two stems and a manifest with peak and silence figures; your
  offline render should match its peaks within 0.1 dB and its silences exactly.

## The page

- **Replace the static image** `assets/brand/orbit-violet-ice.png` with a
  `<canvas>` drawn from the JSON: velocity across, acceleration up (invert
  canvas y), chronological polyline within each run, nothing closed, each
  segment stroked in its note's colour. Black ground. Fit with the document's
  `bounds` and a fixed margin; account for `devicePixelRatio`. Square, full
  width on a phone.
- **One play button.** Pressing it starts both stems in sync and moves the dot.
  The dot's position at time `t` is the point at session minute `t / 0.5`,
  linearly interpolated between the two consecutive points of the same run that
  bracket that minute; where no derived point exists for that minute (edge
  loss, missing minute, before the first run) the dot is hidden. Pause stops
  both stems and the dot. Replay allowed. **Mute allowed** (one toggle). No
  other controls, no inputs, no settings, no seek bar, no volume slider.
- **Date shown** with the orbit, exactly the document's `date`.
- **A plain list of the eight dates as links**, `#2026-09-04` style hash routes
  on the same page; the latest date (2026-09-10) is the default. Switching dates
  stops playback.
- Keep the wordmark **`malosound`** and the tagline **`price, played back.`**
  exactly. Keep the black ground and the typography of the current cover.
- The current "in development" sentence stays until playback works locally;
  remove it in the same commit that makes playback work, not before.
- `prefers-reduced-motion`: the dot still follows playback (it is the
  instrument's reading, not decoration); no other motion on the page.
- Nothing else on the page: no journal, calendar, dashboard, forms, events,
  trade colouring, marketing sections or links to retired pages. Do not link to
  `market-map.html`, `reports/`, `writings/` or any chart under `assets/charts/`.
- Web Audio and Canvas only. No libraries, no model, no API, no fetch beyond the
  same-origin JSON. Static output that deploys on Vercel as-is.

## Acceptance test — the build boundary

Run the build into an isolated output and prove the boundary. Do not build into
the shared `build/`.

```
python -X utf8 -c "import sys, pathlib, tempfile; sys.path.insert(0,'tools'); import build_website as b; b.OUTPUT = pathlib.Path(tempfile.mkdtemp())/'build'; b.main(); print(b.OUTPUT)"
```

Then, with `<out>` being the printed directory (Git Bash):

```
find <out>/content -type f
grep -rl "trades.json\|trading-journal" <out> ; echo "exit $?"
```

Pass criteria: `find` lists exactly the eight files
`content/instrument/2026-08-31.json` … `content/instrument/2026-09-10.json`
and nothing else under `content/`; `grep` prints no path and exits 1. The build
itself raises `content/ boundary violated` or `Trade record in public output`
if either ever fails, so a green build is part of the proof. Also check
`index.html` in `<out>` contains `malosound` and `price, played back.` and no
`img` pointing at `orbit-violet-ice.png`.

Additional checks before you hand over: `node --check` on the inline script
extracted to a temp file; the page on a 375-px viewport with no horizontal
scroll; play, pause, replay, mute and date switching exercised in a browser;
the session and parent silences audible where `docs/INSTRUMENT_AUDIO.md` says
they are.

## Hand-over

Return the diff, a local preview command
(`python -m http.server 4178 --bind 127.0.0.1 --directory <out>`), and the exact
deploy command from `docs/DEPLOY.md` (`git push origin <sha>:master` after
Marcelo's explicit yes). **Do not merge or push before Marcelo sees the diff.**
Record in `PARALLEL_WORK.md` what changed and release the claim.
