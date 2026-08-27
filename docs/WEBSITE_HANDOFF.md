# maloSound.ai Website Handoff

The root `index.html` is the GitHub Pages entry point for `malosound.ai`.

## Current Shape

- Homepage: `index.html`
- Domain file: `CNAME`
- Public Victoria proof page: `releases/victoria-2026-08-26/index.html`

The homepage borrows the GateKPT visual language: full-screen dark signal field,
HUD-style top bar, proof sections, compact buttons, and evidence-forward copy.
It does not copy GateKPT product logic.

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

`maloSound.ai` is not Spotify-first and not crypto-first. It is a proof-of-
concept release surface:

- listen free through Instagram and YouTube
- support direct through downloads
- verify authenticity through hashes, manifests, and Ed25519 receipts
- keep blockchain optional until it helps the artist/community

First album frame:

```text
My Friend
3 songs about Rosco
```
