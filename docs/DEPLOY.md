# Publish MaloSound.ai

Production is https://malosound.ai on Vercel, from GitHub master at
https://github.com/marcelozap/malosound.git. Vercel runs
`python3 tools/build_website.py` and serves only `build/`.

## Integration and publishing

Use an isolated checkout when another agent is editing. Never stage all files in
the shared music workspace. Coordinate source ownership through
`C:\MaloSound\handoff\website\PARALLEL_WORK.md`.

1. Fetch and review current production plus the intended commits.
2. Integrate intended source in a separate worktree. Preserve the orbit cover and
   journal. Do not include another agent's uncommitted data.
3. Run `python -X utf8 tools/build_website.py` in that isolated checkout. It
   regenerates chart/index files and downloads two checksum-verified recordings.
   Inspect generated source changes before including them in a commit.
4. Check the journal and desktop/mobile preview. Commit only intended paths.
5. Record `git rev-parse HEAD` and push that exact SHA with
   `git push origin <SHA>:master`. Never force-push production.
6. Wait for Vercel success for that SHA, then check actual malosound.ai.

A rejected push means production advanced: fetch and inspect before proceeding.
A Git push or a separate Sites preview is not production verification.

## Preview

```sh
python -X utf8 tools/build_website.py
python -m http.server 4178 --bind 127.0.0.1 --directory build
```

Open http://127.0.0.1:4178/. Use a fresh build, not another agent's output.

## Production checks

- Cover image, wordmark and Open sessions link load.
- /#journal opens the calendar and a selected-date chart.
- /content/journal-index.json, representative May/June/July/September day files,
  their charts, both recorded-session reports and their local audio return 200.
- /#session-2026-09-04 loads its chart and recording; play and seek on desktop and
  mobile. Distinguish untested playback from a verified advancing audio clock.
- An absent entry differs from an entry with no chart. Hourly data stays labelled.
- /#ahead shows sourced scheduled events with dates and freshness; no automatic
  ongoing feed is promised.
- Retired studio/music-lab pages and /content/trades.json remain unavailable.
- Artwork is not described as measured data or reactive playback.

## Publication boundary and recovery

The explicit allowlist in tools/build_website.py stages journal assets and the
visual identity. content/trading-journal.json is the sanitized publication ledger
used to derive public overlays: dates, documented times, outcomes and coverage.
It stays tracked for reproducible builds. Never add broker balances, quantities,
account identifiers, raw statements or private reviews. Keep private evidence and
raw fills outside the published build and Git.

Git source does not contain MP3 bytes. The build fetches approved release URLs and
checks their hashes. Back up original recordings, source music projects and their
samples separately; they cannot be recovered from a source-only Git export. The
private Sessions evidence archive also needs its own backup.

For a portable source snapshot, use `git archive --format=zip --output=<path> <SHA>`.
Build from that same SHA to capture a separate deployable build including audio.
Do not call a source ZIP an audio or private-evidence backup.

`.openai/hosting.json` describes a separate private preview, not production. It
must not replace the Vercel deployment above.
