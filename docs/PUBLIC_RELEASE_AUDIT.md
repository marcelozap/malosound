# MaloSound Public Release Audit

Last updated: 2026-08-28

## Current public surface

- `index.html` is the public homepage for `malosound.ai`.
- `CNAME` points GitHub Pages to `malosound.ai`.
- `.nojekyll` is present so GitHub Pages serves the static site directly.

## Public-safe positioning

MaloSound is original music plus artist-tech infrastructure: recording workflow, AudioAnalysisV1 metadata, coded rhythm, visual output, release operations, and ownership records. It is the first working proof for XIV because music forces the system to handle creative, technical, publishing, feedback, and provenance work in one public-facing loop.

## Public-safe artifact types

- Released songs, snippets, and visual clips.
- AudioAnalysisV1 summaries that remove local paths and private source names.
- Coded rhythm examples written as public companions, not leaked studio exports.
- Motion-mapped visual output.
- Release pages and artist workflow diagrams.
- Ownership and provenance summaries that omit private ledger internals.
- Guides explaining why direct release infrastructure helps independent artists.

## Internal-only material

Do not publish or link the following without a separate sanitization pass:

- Raw studio files, stems, bounces, or unreleased masters.
- Local machine paths.
- Private track filenames.
- Private notes.
- Embeddings matrices or unreleased analysis internals.
- Receipt excerpts that include local paths or private source names.
- Generated proof package folders created during local testing.

## Guardrails added

The `.gitignore` now keeps local Victoria/proof artifacts out of Git by default:

- `releases/victoria/`
- `releases/*victoria*/`
- `scripts/strudel/tracks/victoria/`
- `scripts/strudel/tracks/victoria-*/`
- `manifests/victoria*.json`
- `data/receipts.jsonl`
- `data/gold/audio_analysis/vicotira*.json`

## Next safe work

1. Create a sanitized example release package using fictional or fixture data only.
2. Add a public `/proof/` page that explains the pipeline without exposing private filenames or local paths.
3. Add a short artist guide: listen free on public platforms, support directly through a verified download bundle.
4. Keep blockchain language limited to compatibility and provenance boundaries until a live deployment actually exists.
