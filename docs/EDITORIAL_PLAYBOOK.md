# MaloSound field notes: deep preparation, a light page

## Latest direction takes priority

Music, artwork and the observed line lead. Preparation should be complete before
performance; the interface should not demand more analysis or personal opinions
from Marcelo while he is trading. Keep research under closed notes and avoid
explaining the format repeatedly. Human-interest angles, commentary and personal
reflection are optional; do not require them to complete an edition. The source
checks below still apply. Current recordings are historical session replays,
not forecasts or already-built prospective rehearsal tracks.

## Purpose and voice

Marcelo describes the ambition as the "Anthony Bourdain of trading." Interpret
that as curiosity about people, place, culture, work and the consequences of
money moving through the world. Develop Marcelo's own voice: specific,
observant, willing to be surprised, and honest about what remains unknown.

Each session is a small episode: a question before the open, a line drawn by
the market, and an original piece of music. Seek the human stakes behind the
numbers without forcing every session into a dramatic story. A quiet day or an
unresolved question is worth recording.

Research can be extensive. The visible page stays sparse: a short headline,
honest provenance, the source-backed line, the song and necessary gap labels.
Put the deeper reporting, comparisons and sources under Notes. Keep the guitar,
black, gold and electric-blue visual identity. Do not add a wall of introductory
copy or expand all notes automatically.

## Scope and schedule

This playbook supplements `DAILY_PUBLISHING.md`, which controls technical
publication, source validation and the two existing weekday slots: 08:30 and
16:00 America/New_York. These are start times, not promises of instant finished
audio. Do not add recurring jobs or restart the stopped Claude loop. The
existing Codex heartbeat performs the work, subject to the local machine being
awake and the app running. A Claude contribution is optional and may be stale,
unavailable or out of credits; publication must not depend on it.

Use the current website checkout at
`C:\MaloSound\Workspace\market-journal-site`. Save working evidence in
`C:\MaloSound\Sessions\market-journal\YYYY-MM-DD\Research`. Start from
`docs/templates/RESEARCH_PACKET.json`. Give every run an actual timestamp and
slot identifier. Preserve completed packets; corrections and retries refer to
the prior run rather than overwriting the original morning record.

Only selected public market context goes into `content/editions.json` and dated
public reports. Keep research scratchpads, raw provider responses, personal
information, account material and local paths out of the public build.

## Morning: find the question

1. **Remember the thread.** Read the previous five published sessions and their
   unresolved questions. Identify one useful continuation or change of view.
   Do not replay yesterday's narrative merely to fill today's slot. Confirm the
   date and actual exchange calendar before collecting an apparent session.
2. **Check the incoming brief.** Read fresh dated XIV analysis or a supplied
   Claude briefing if available. Verify internal date, information cutoff,
   source timestamps and missing values. A file's modification time does not
   establish freshness. Separate the brief's claimed time from when it was
   imported and checked. Do not authenticate a capture time by assumption.
3. **Build the evidence.** Start with the day's relevant original releases and
   calendars, source price data, and filings or published remarks when needed.
   Add reputable reporting for context. Usually three to six useful sources
   suffice; this is a guide, not a quota. Several outlets repeating the same
   wire story or release are one underlying source, not independent evidence.
4. **Follow the people.** Consider a worker, household, business, customer,
   supplier or place affected by the economic issue. Use a verifiable public
   account or an explicitly described economic mechanism. A reported example
   is not representative of everyone. If the connection is weak, omit it.
5. **Choose the day's tension.** Write one editorial question and at most three
   observable watch points. State a leading interpretation, a credible
   alternative, and what evidence would weaken each. These are questions and
   scenarios, not personal trade recommendations or invented conviction.
6. **Freeze the cutoff and note.** Include only information available by the recorded
   cutoff. A release that arrives while preparing the note requires a new
   cutoff and label if incorporated. Never put an 08:30 release into an 08:29
   reconstruction. Preserve the actual preparation and publication times.
   Before publication, save the exact morning note as a new, write-once local
   snapshot with its preparation time, cutoff, provenance and SHA-256. Record
   its path/hash in the packet. After publication, record the Git commit and
   verified public timestamp. At the close, compare that saved text and verify
   its hash; do not reconstruct it from memory or the latest mutable draft.
   A hash detects changes relative to the retained snapshot; by itself it
   cannot prove an earlier capture time. Genuine pre-open provenance and the
   published history remain necessary. Save corrections as new versions.

Keep a source ledger with exact URL, title/publisher, original-source identity,
publication/update time, observation period, retrieval time, units, revision
status, and the claim it supports. Use null when a timestamp is unknown.
Distinguish SPY from S&P futures, the index, and other ETFs. Distinguish a daily
return from an intraday move and a source forecast from an official release.

The ledger is the source of truth: every material claim in a draft must already
have a ledger row and supporting evidence or an explicit interpretation label.
Questions, titles and artistic choices need not pretend to be measured facts.
Tag material claims as measured fact, attributed report, interpretation or
artistic choice. Mark disagreements and unsupported claims. Verify material
numerical claims against the primary release or actual source data; do not
average conflicting figures into a new number. Omit or explicitly qualify an
unresolved claim rather than laundering it through polished prose.

## Close: let the day answer

1. Follow the source/completeness checks in `DAILY_PUBLISHING.md`. Preserve
   observed bars, closing-boundary provenance, missing intervals and provider
   discrepancies. Never borrow another date to make the entry look complete.
2. Revisit the frozen morning questions. For each, record the observed result,
   supporting evidence and one of: supported, weakened, unresolved, or not
   assessable. A reconstructed or later-imported note is not a verified public
   pre-open prediction and must not be scored as one.
3. Separate the news result from the market response. The release, its
   expectation, a later revision, the price movement and a commentator's
   explanation are distinct facts. Timing and correlation alone do not prove
   causation. Reconsider the alternative interpretation rather than forcing a
   neat ending onto the day.
4. Write the closing field note around what changed, who the evidence shows
   was affected, and what remains open. No winner's hindsight, invented trades,
   or claims that the session proves a profitable system.
5. Carry one unresolved question forward, retaining its stable ID, date raised,
   interpretations, weakening conditions and status. Continue an existing
   question or close it with a reason before introducing a new one; do not
   rename the same uncertainty every day. Finish the packet with a brief
   editorial learning: what the morning frame missed or what evidence would
   improve the next episode. Do not endlessly accumulate irrelevant headlines.

## From observations to music

Describe the measured session shape before authoring the musical interpretation.
Bind the composition to the correct date, source snapshot and section boundaries.
Every numerical or directional claim about a section must refer to observations
inside that section; explicitly identify evidence spanning a boundary.

Price contour, observed volume and range can inform melody, rhythmic activity
and texture. Mood, harmony, instruments, tension and release remain artistic
choices. Do not infer measured fear, hope, conviction or a specific news cause
from those controls. No invented lyrics, borrowed melody, vocal imitation or
claim that the music predicts returns. Keep the current validated 195-second,
80-BPM workflow; renderer 1.1 is a separate local audition candidate until
explicitly adopted. The existing static chart and playhead use the same sourced
boundaries. Never interpolate a marker across a missing source interval.

## Two reviews, then publish

Perform a factual/timing review and an editorial/music review. They can be
separate passes by Codex; do not claim an independent reviewer ran when none
did. An available Claude response can challenge the frame and identify missing
evidence. Its fluency is not verification, and its suggestions remain proposals
  until checked and adopted.

Evaluate watch conditions using the relevant evidence, which may include
rates, releases, filings or sector participation as well as SPY. The price line
alone cannot answer every economic question. A human connection needs an
attributed account or a supported mechanism, not proof that it caused today's
price move.

- **Factual/timing:** source and date match, cutoff respected, numbers/units and
  section evidence correct, uncertainty visible, morning history preserved.
- **Editorial/music:** one clear question, a credible alternative, an honest
  human connection when supported, distinct artistic choices, concise visible
  copy, and chart/audio timing that fits the evidence.

Revise concrete failures, usually for one targeted round. A second targeted
round is appropriate for a remaining material conflict; after that omit the
unsupported claim or publish a clearly limited/pending entry. Do not turn
"more preparation" into an indefinite research or reviewer loop. If additional
sources no longer change the conclusion or resolve a named uncertainty, stop.
Technical retries for delayed final bars remain limited to the existing
20-minute window. No new quota of articles or reviews is proof of quality.

## What reaches the page

Treat these as editing targets rather than reasons to hide necessary context:

- Headline: about three to eight words.
- Visible morning text: headline plus honest preparation/import label. Any
  optional deck should be a single short sentence.
- Visual: the actual SPY line with session endpoints and a compact gap notice.
- Sound: title, player and 3:15 metadata. Full interpretation lives in Notes.
- Expanded field note: usually 120–250 useful words, with sources and the
  morning-to-close comparison. Add detail when evidence requires it.

Public first-person experience must come from Marcelo's supplied account.
Never fabricate visits, interviews, conversations, trades or emotional reactions
for him. Attribute reported voices and keep quotes short. Use an authored
research-note label when the automation supplies the view. Preparation may
include questions to ask Marcelo later, but scheduled publishing does not wait
for an invented reply or initiate outside outreach.

## Failure and correction rules

- No fresh briefing: research a clearly dated note from available sources;
  never reuse stale context as today's analysis.
- Thin or conflicting evidence: narrow the story and state the remaining
  uncertainty. Publish a pending state if the underlying session is not ready.
- Missing bars, unsupported early close or failed render: preserve the prior
  recordings in the calendar and label today's affected stage honestly.
- Market holiday: publish a brief closed-market entry and, when useful, a
  sourced next-session question. Do not fabricate a line or a trading day.
- Material error discovered later: add a timestamped correction describing
  what changed and why. Retain the earlier version and do not edit a forecast
  after seeing the outcome.

Finish each run by verifying the actual public date, report, chart, playback
links and deployment. Notify Marcelo briefly on verified publication, a
meaningful change, or a failure requiring action. Remain quiet on completed,
unchanged retries. This is publication and artistic research, not authorization
for trades, outside messages, new purchases or a new autonomous service.
