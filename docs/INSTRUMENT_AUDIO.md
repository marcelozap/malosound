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
