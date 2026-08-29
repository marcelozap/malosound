# releases — metadata, not masters

## The decision

Masters stay out of git. `releases/` holds a text record of each release and a
pointer to where the audio actually lives.

An earlier `.gitignore` carried `!releases/**/masters/*`, which re-included
master audio after the audio rules had excluded it. It worked — that was the
problem. Multi-megabyte WAVs would have gone in, permanently, in every clone,
directly contradicting the one rule this repo has.

The alternative was Git LFS. Rejected for now: it needs installing on every
machine in the rig, it burns bandwidth and storage quota on any host you push to,
and it fails in a confusing way when it is not set up — you get a small text
pointer file where a master should be, and you find out at the worst moment. If a
distributor ever requires reproducible-from-clone releases, revisit it.

## Layout

```
releases/
  2026-08-13_victoria/
    release.md         everything about the release
    art/cover.png      cover art IS committed (small, and it is source)
    lyrics/victoria.md
```

No `masters/` folder in git. The master lives in the library and is backed up by
`scripts/backup-projects.ps1`.

## release.md template

```markdown
# <title>

- **Artist:** malosound
- **Released:**
- **Lane:** half-time 152 / Latin house 122
- **Key / BPM:**
- **Length:**
- **ISRC:**
- **Language:** Spanish / English / both

## Master

- **File:** `<name>_master_v<n>_<YYYY-MM-DD>.wav`
- **Lives at:** `XIV Music Library\...`
- **Format:** 24-bit / 48 kHz
- **Mastering notes:** manual streaming target notes, not AudioAnalysisV1 fields
- **Mastered by:**

## Sources

- **Live set:** `projects/<date>_<name>/`
- **Strudel pattern:** `scripts/strudel/tracks/<name>/pattern.js`
- **Recorded takes kept:** which, and where

## Credits

- Guitar / bass / drums / vocals / production:

## Distribution

| Platform | Status | Date | Link |
|---|---|---|---|
| | | | |

## Notes

What worked, what you would do differently. Write this while you still remember —
it is the only part of a release that helps the next one.
```

## Naming

`<title>_master_v<n>_<YYYY-MM-DD>.wav` — version **and** date. When there are
nine and you need the one from before you ruined the mix, that is the only thing
that saves you.
