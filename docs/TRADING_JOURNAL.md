# Personal trading record

The observed SPY path stays exact. Its color now shows how Marcelo judges he
PLAYED each stretch of the session, not what the day paid:

| color | meaning |
|---|---|
| blue `#50b8f5` | not reviewed — the default for any stretch he has not assessed |
| gold `#e5b657` | deliberately sat out |
| green `#58dfa4` | played well |
| red `#ff7188` | misplayed |

Whole-day profit/loss coloring is retired. A profitable day can be badly played
and a losing one played well, so the net result is now a text label only and
colors nothing. Never grade execution from the sign of the P&L, from SPY's
direction, from the song, or from hindsight about what price did next. A stretch
Marcelo has not reviewed stays blue; silence is not a grade.

Sections are HH:MM ET spans inside 09:30–16:00, ordered and non-overlapping,
each with `good`, `misplayed` or `sat_out` and an optional note in his words.
`executionAssessedAt` is required with them and must fall after that day's
16:00 close: execution is reviewed after the fact, not called during the session.
The drawn geometry never changes — the same observed points are split into
colored runs, sharing the boundary point so the line stays continuous, and
source gaps still break it.

Setup quality uses an optional integer 1–14. A 14 is the rarest tier, aiming for
roughly 14 exceptional opportunities a year. This is a selection goal, not a
quota, a measured frequency or a guarantee. It does not mean trade number 14.
Never derive this rating from profit, magnitude of return, the song or hindsight.
Use Marcelo's supplied rating and actual assessment timestamp; keep a later
assessment explicitly retrospective. No rating is shown until supplied.

## Intake

Raw broker exports and supporting records stay outside Git, for example under
`C:\MaloSound\Sessions\market-journal\trades\YYYY-MM-DD`. The browser is a
public read-only journal, with no anonymous editing or browser-only storage.
The current records in `content/trading-journal.json` are intentionally empty:
no September trading outcomes or ratings have been provided. Legacy P&L sources
found locally are older and cannot establish September results. Do not backfill
from them without the matching date and agreed live-trading source.

After the user supplies a result or an actual export is reconciled, prepare a
private normalized JSON input with these fields:

- `date`: actual New York trading date (`YYYY-MM-DD`).
- `mode`: `live`; `final`: `true`; `feesIncluded`: `true`.
- Either `outcome`: `profit`, `loss`, `flat`, or `no_trade` for an explicit
  owner-reported result; or `netRealizedPnl`: a finite decimal string after fees
  plus `tradeCount`: nonnegative integer. Multiple completed trades are summed
  for that day. Confirm currency/scope before aggregation; do not mix currencies.
- `sourceKind`: `user_reported` or `imported_result`. Imports require the numeric
  net result and count; the label is not an independent audit claim.
- Optional `setupRating`: integer 1–14 and `ratingAsOf`: the actual timestamp
  including timezone. Omit both when not provided. Never invent an earlier time.

### The one-command way

    python tools/log_day.py --date 2026-09-04 --outcome profit --setup 9         --sat-out   09:30 09:48 "Waited for the range to set."         --played    09:48 09:52 "Took the open cleanly."         --misplayed 12:38 12:48 "Chased the second push."         --private-note "Sized too big on that entry."

Each flag names one stretch: START END plus an optional note. Repeat for more.
`--show` prints what is public and private for a date and changes nothing;
`--replace` corrects a day already published. The command writes a private
record under `C:\MaloSound\Sessions\market-journal\<date>\day-review.json`,
outside Git, and stages only the allowlisted public summary. `--private-note`
never crosses over. `--assessed` defaults to now and is refused before the close.

Run `python tools/record_trading_day.py --input <private-json-path>` for the
file-based path, then the The importer publishes only date, outcome, setup rating,
assessment/recording timestamps and source kind. It drops account identifiers,
positions, amounts, fills, credentials and local source paths. It refuses paper,
unfinished, contradictory, nonfinite and future-completed results. An identical
retry preserves the first recorded timestamp; a changed day requires an explicit
reviewed `--replace`, with the correction recorded in Git and the private log.

Source CSV adapters are not configured yet; get the user's source choice and
check its schema before claiming automatic brokerage sync. A new result can be
published after the song without changing that day's market data or recording.

## Checks

`python -m unittest discover -s tools -p test_trade_journal.py -v` checks outcome
signs, missing/flat/no-trade distinctions, invalid inputs, privacy allowlisting,
idempotence/corrections, rating bounds and timing, plus unchanged real SPY paths,
gaps, timelines and song data across all display outcomes. Test outcomes live
only in temporary fixtures, never in the public journal.
