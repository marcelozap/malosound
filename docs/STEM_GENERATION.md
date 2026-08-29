# Stem Generation

This repo can generate utility stems for a recording session, but the audio
bytes still do not belong in git.

```powershell
.\scripts\generate-stem-kit.ps1 -Session "my-friend-first-pass" -Bpm 106 -Bars 16
```

Default output:

```text
projects\<date>_<session>\Generated Stems\
```

`projects/` is ignored by git. That is intentional.

## What It Creates

| Stem | Purpose |
|---|---|
| `01_count_in_click.wav` | one bar count-in |
| `02_beat_grid_click.wav` | full-length click with accented downbeats |
| `03_sidechain_pulse.wav` | low pulse on each beat for sidechain or visual testing |
| `04_movement_cues.wav` | short cue tones for open, stop, and turn markers |
| `05_vocal_space_silence.wav` | silent bed for vocal alignment |
| `06_movement_video_silence.wav` | silent bed for movement/video alignment |

It also writes `stem-kit.json` and `STEMS.md` beside the WAV files.

## DAW Move

Import the stems as separate tracks, set the DAW tempo first, then record the
vocal and movement pass against them. The click and pulse are disposable
scaffolding. The vocal, movement, and actual drums are the record.

## Boundary

No raw recordings, masters, private takes, or generated WAV stems should be
committed. Keep generated stems in `projects/` or the XIV Music Library and use
repo text files to describe them.
