# MaloSound.ai website

## Identity

**How I hear the market.** MaloSound.ai is a personal artist journal exploring
the market through writing and music. XIV is the trading system product;
MaloSound is the artist's voice. The site develops a personal theory in public,
including questions and revisions; it does not present the metaphor as a
proven market model.

The central practice is one different song per market day, each the same
duration. Before the open: context, observations, and questions. After the
close: the song inspired by price action, with a written reflection.

## Public pages

- `index.html`: the journal homepage, current editions, theory, and about.
- `writings/one-song-one-session.html`: the opening essay.
- `journal.css`: shared black, gold, and blue visual design.
- `journal.js`: dated morning/closing editions and playable external audio.
- `content/editions.json`: the daily publishing source.
- `assets/brand/market-into-music.png`: the user's supplied chart/guitar artwork.
- `assets/brand/malosound-square.png`: the 1254 × 1254 LinkedIn/link-preview artwork.
- `studio.html`: the existing interactive sound/signal experiment.
- `latin-house-lab.html`: the existing Rhythm Lab.

The journal now includes the September 4 founding research and September 3 retrospective closing trial, with chart, evidence and a Bill Withers listening selection. The interactive market map and complete research are public pages. Original-song duration remains undecided; reference tracks do not count as original fixed-duration releases. See MARKET_JOURNAL_WORKFLOW.md for the active daily publication workflow.

## Publishing the two daily editions

Edit `content/editions.json`. There is one object per session date. Add `morning`
for the first edition, then add `closing` to the same object after the session.
Keep earlier dates: the homepage displays the newest date and automatically
places older sessions in the archive. Dates use `YYYY-MM-DD`; their order in
the file does not matter. The static site does not generate entries; the Codex daily automation follows MARKET_JOURNAL_WORKFLOW.md to research and publish them.

Each edition needs `title`, `summary`, and optional `paragraphs` (a list of
plain-text paragraphs). Text is rendered as text, never interpreted as HTML.
A morning-only session is valid and shows an honest closing-song empty state.

Before the first song, choose one duration in seconds and set the top-level
`songDurationSeconds`. Every original recorded closing release needs a public HTTPS `audioUrl` and
`durationSeconds` equal to that series duration. Keep this duration constant
for future sessions. The browser checks the audio's actual duration within a
one-second encoding tolerance and shows an unavailable message for an
incompatible or broken recording. It does not autoplay.

This is a schema example only; replace every example value before publication:

```json
{
  "songDurationSeconds": 240,
  "sessions": [
    {
      "date": "2026-09-04",
      "morning": {
        "title": "Your morning title",
        "summary": "Your personal reading of the session ahead.",
        "paragraphs": ["Your full morning writing."]
      },
      "closing": {
        "title": "Your song title",
        "summary": "How the session inspired the music.",
        "paragraphs": ["Your reflection on the price action and musical choices."],
        "audioUrl": "https://example.com/replace-with-your-recording.mp3",
        "durationSeconds": 240
      }
    }
  ]
}
```

The example's four-minute length is illustrative, not the chosen series
duration. Publish entries on actual market days; the exact exchange calendar
and holiday/short-session policy have not been chosen. The build accepts calendar dates; the research workflow must verify exchange holidays and label recaps.

## Preview and validation

```sh
python3 tools/build_website.py
python3 -m http.server 4173 --bind 127.0.0.1 --directory build
```

The build validates metadata, local links and anchors, edition fields, unique
weekday dates, external audio links, and equal song lengths. It stages an
explicit list of 13 public files into ignored `build/`; it never copies
private studio files, keys, receipts, unrelated drafts, or the source tree.

## Hosting

`malosound.ai` currently responds through Vercel. The repository's origin is
`marcelozap/malosound`, whose configured homepage is `malosound.vercel.app`.
The legacy `CNAME` file is retained; GitHub reports Pages is not enabled.

`.openai/hosting.json` records the Sites preview project and its static output
directory. Publishing that preview does not change the custom domain, DNS,
Vercel project, or the public site's audience. The user confirmed that the
GitHub repository is connected to Vercel. Publishing the public site uses
the existing `origin/master` deployment path. The homepage's canonical URL
and link-preview metadata point to `https://malosound.ai/` and the square
artwork, while the original wide artwork remains on the homepage.

## Audio boundary

Audio bytes never go in Git. Keep the public release URL in `audioUrl` and the
MP3's SHA-256 in `audioSha256` in the source journal. The website build downloads
those exact bytes into ignored `build/assets/audio/`, rejects missing hashes
or changed recordings, and rewrites the built journal and report players to
local MP3 paths. Source editions and reports keep their release URLs.

The Vercel configuration publishes `build/` and serves these recordings as
`audio/mpeg` with inline delivery; static hosting supplies byte-range support.
This avoids GitHub's download redirect path, which failed Apple's media loader
for the September 3 and 4 recordings despite valid MP3 bytes. Both files played
through Apple's loader when served directly over HTTP. The existing ignored
studio paths and release policies still apply. Do not force-add audio files.

## Visual-first homepage
The homepage now uses a full-height blue/gold art stage, subtle reduced-motion-aware animation, sparse navigation and compact session cards. Latest research and latest closing are shown independently, each with its own actual date. All dated sessions remain in the archive. Long summaries, paragraphs, chart captions, song rationale and sources remain available in collapsed “Behind the session” panels; never expand them by default during daily imports. Keep the chart and listening link visible, and keep complete research on its dedicated page. Original-song vs selected-recording labels remain explicit. Shared styles for essays and map pages remain intact; homepage styling is scoped to art-home.
