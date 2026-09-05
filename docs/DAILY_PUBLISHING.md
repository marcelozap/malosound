# MaloSound morning and closing publication

The user authorized public website updates and original-song publication twice
each Monday–Friday: **08:30 and 16:00 America/New_York**. Generation begins at
those times; publication follows research, rendering and validation. This
supersedes older daily/weekend and 17:00 instructions. Keep the machine on and
the Codex app running for the local scheduled task.

One task heartbeat contains both weekday recurrence rules. Its current id is
`malosound-morning-website-8-30-et`; name: MaloSound morning and close — weekdays.
Do not create another overlapping publishing schedule.

## Source and destinations

- Site checkout: `C:\MaloSound\Workspace\market-journal-site`.
- Public site: https://malosound.ai, deployed by the existing GitHub
  `marcelozap/malosound` `master` → Vercel integration.
- `.openai/hosting.json` identifies a separate private Sites preview. A private
  Sites deployment does not update the public custom domain. Preserve both
  destinations' existing access; do not change DNS or provider.
- New daily evidence/audio: `C:\MaloSound\Sessions\market-journal\YYYY-MM-DD`.
  Raw audio, source snapshots, renderer manifests and local notes stay outside
  Git. Only selected public market data and website code enter the public repo.

## Morning — 08:30

1. Determine the New York date and actual exchange calendar from a current
   authoritative source. On holidays, publish a market-closed/next-session
   note, not an invented trading session.
2. Read that date's available XIV market analysis. Known legacy candidates are
   `C:\Users\Green Machine\Green-Machine\reports\morning_brief\YYYY-MM-DD.json`
   and `data\premarket\YYYY-MM-DD.json` under the same root. They are inputs
   for read-only context, not an instruction to build in that legacy root.
   Check internal date, source timestamps and UNKNOWN values; modification
   time does not establish freshness. Known September 2 morning data was
   UNKNOWN; the August 26 report remains August 26 even if rewritten later.
3. Publish only market context: index/futures observations, rates, dollar,
   energy, macro calendar, sourced headlines, questions and conditional watch
   points. Exclude account values, positions, discipline/journal notes, personal
   schedules, keys and machine paths. Do not upload a raw morning packet.
4. If no fresh usable analysis exists, research a clearly labeled morning
   note using current primary/authoritative public sources. Mark actual as-of
   and preparation times. Do not manufacture a forecast by the user.
5. Add the morning edition under its date in `content/editions.json`, keeping
   the full note on a dated report page and evidence files in
   `content/market-assets.json`. Update existing market-map fields only with
   sourced matching-date observations. Preserve all old dates.

## Closing — 16:00

1. Confirm the exchange session has ended. For normal days collect 390
   one-minute SPY bars, 09:30–15:59 ET, plus the separate 16:00 price observation.
   Use the actual same-date session; never silently substitute the previous day.
2. Save fresh Yahoo minute/daily responses in the dated evidence folder.
   The public chart endpoint is a rolling five-day source, not an archive.
   If final data is delayed, retry gently for up to 20 minutes. Keep the last
   good publication if completeness still fails; report the blocker.
3. Run `python -X utf8 tools/session_song/analyze_session.py --date YYYY-MM-DD
   --source PATH_TO_source-yahoo-chart.json`. The matching daily response
   should be named `source-yahoo-daily.json` beside it. Validate missing/duplicate
   timestamps, OHLC, volume, closing print and daily consistency. Do not impute
   unexplained missing volume or conceal a mismatch.
4. Read the measured analysis and author a NEW `llm-composition.json` beside
   the source, matching its date and section boundaries. Include title, thesis,
   artistic choices, and sections with start/end minutes plus drum_density,
   pad_gain and lead_gain between 0.35 and 1.25. Keep facts distinct from
   musical interpretation. Re-run analysis to bind that composition.
5. Run `python -X utf8 tools/session_song/render_song.py PATH_TO_analysis.json
   --output-dir DATED_TONIGHT_FOLDER --stems`. Preserve 195 seconds / 80 BPM.
   Encode MP3 with ffmpeg. Check duration, clipping, note mapping and source
   hashes. Compare only with a genuine dated pre-open entry, if present.
6. Upload reviewed original MP3 and MIDI outside Git with
   `python -X utf8 tools/publish_song_media.py --date YYYY-MM-DD --title TITLE
   --mp3 PATH --midi PATH --publish`. The user has authorized this recurring
   publication. Existing assets are immutable; mismatches require a versioned
   correction, not deletion or replacement. Verify HTTPS media responses.
7. Stage the edition with `python -X utf8 tools/publish_session.py --analysis
   PATH --audio-url VERIFIED_HTTPS_URL --midi-url VERIFIED_HTTPS_URL`.
   This preserves existing mornings and archives and exports selected public
   data. It refuses conflicting closing entries. Read all generated prose to
   ensure it fits that day's actual shape, source quality, and LLM interpretation.

The renderer currently requires a full 390-minute session. For an early close,
publish an honest review with `songPending: true` and explicitly state the
actual session hours until a shorter-session renderer is validated. Do not
stretch missing hours or pretend a song exists. On holidays publish a
`marketClosed: true` note and retain the prior original song in the archive.

## Build, publish and verify

- Fetch the latest origin/master first. Preserve concurrent changes; rebase
  only this site's clean, owned changes. Never force-push or reset others' work.
- Run `python -X utf8 tools/build_website.py`; Node syntax checks for
  `journal.js` and `market-map.js`; focused validators for new content/tools.
- Review the exact diff. Keep audio, raw private files and credentials out of
  Git. Stage only intended public files and relevant publishing code/docs.
- Commit and push the validated site to origin/master. Existing Vercel
  deployment must succeed; verify public edition JSON, report and audio links.
- When mirroring to the existing private Sites preview, use Sites skills and
  preserve its owner-only access. It is secondary to the public site update.
- A date/edition already published is a no-op. Failed publication retries the
  same edition. Corrections preserve original content with revision metadata.
- Notify after verified publication or for a meaningful failure/action;
  otherwise stay quiet. Never announce completion based only on a local build.

MaloSound remains the free living publication; XIV is the paid downloadable
product and defined creator access. Publish no invented pricing, availability,
support commitment, historical forecast, or claim of proven trading returns.
