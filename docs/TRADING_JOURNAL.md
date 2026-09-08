# Personal trading record

The observed SPY path stays exact. Its color shows Marcelo's own final net
realized trading result after fees for that New York date: green profit, red
loss, neutral gray for flat/no trade/unrecorded, with separate text labels.
Do not infer personal performance from SPY's direction, the song, a simulation,
account market value, unrealized P&L, or missing data. The line is not an equity
curve. The calendar marks reported profitable/loss-making days with the same
colors; playback keeps the matching color and the existing source-gap behavior.

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

Run `python tools/record_trading_day.py --input <private-json-path>`, then the
normal website build. The importer publishes only date, outcome, setup rating,
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
