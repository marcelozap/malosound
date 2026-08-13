# ableton — templates, racks, clips

Reusable Live material. Small binaries that are genuinely source, as opposed to
Live *sets*, which are neither small nor reusable and live in `projects/`
outside git entirely.

```
ableton/
  templates/   .als starting points — the default set you open a new song into
  racks/       .adg instrument/effect racks, .adv single-device presets
  clips/       .alc clips worth reusing
```

## What belongs here

An `.als` in `ableton/templates/` is intentional and correct — it is a template,
it changes rarely, and it is a few hundred KB. The pre-commit hook warns about
`.als` files staged anywhere *else*, because outside this folder an `.als` is
almost always a song set that should be in `projects/`.

`.gitattributes` marks all of these `binary`. They are gzipped XML: git must
never try to line-merge them, and a diff would be noise anyway.

## Templates worth building

- **half-time 152** — tracks armed for guitar, bass, and the Crimson kit, at the
  tempo you actually write at, with the interface inputs already routed
- **Latin house 122** — same, plus a return with the delay set to dotted-eighth
- **tracking** — minimum set for capturing an idea before it evaporates: one
  armed input, one metronome, nothing else to click on

The third one matters most. The cost of an idea is the time between having it and
recording it, and a template with twenty tracks on it adds to that time.

## Before committing a template

**File → Collect All and Save** first, then check what it pulled in. Collecting
copies referenced samples into the project folder — which is right for a Live
project and wrong for a git-tracked template, because those samples are audio
bytes and the hook will block the commit.

A template should reference stock devices and library paths, not carry audio.
