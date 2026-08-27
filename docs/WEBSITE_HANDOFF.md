# maloSound.ai Website Handoff

The root `index.html` is the GitHub Pages entry point for `malosound.ai`.

## Current Shape

- Homepage: `index.html`
- Domain file: `CNAME`

The homepage uses a full-screen dark signal field, HUD-style top bar, proof
sections, compact buttons, and evidence-forward copy.

## Release Boundary

Audio binaries are still ignored by Git:

```text
projects/
releases/**/audio/
```

That means GitHub Pages can publish the site shell and proof documents, but the
public download link needs a deliberate storage decision before launch:

- GitHub Release asset
- Git LFS, if acceptable for the repo
- external object storage
- later blockchain-backed download flow

Do not force-add MP3 files unless the release policy changes.

## Current Positioning

`maloSound.ai` presents MaloSound as the first proof of concept for XIV:

- XIV is the orchestrator, business, and role-based AI systems layer
- MaloSound is the music and artist-tech proof of concept
- Green Machine is the data, evidence, and risk-review lane
- public language stays focused on original music, AudioAnalysisV1 summaries,
  coded rhythm, visual output, release workflow, and ownership

First album frame:

```text
My Friend
3 original songs
```
