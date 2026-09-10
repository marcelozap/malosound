# Trade outcome overlays

Marcelo confirmed on September 10, 2026: gold (#e5b657) represents winning trades,
blue (#50b8f5) losing trades, during entry-to-exit windows. Neutral gray (#81929e)
marks other intervals. This supersedes the earlier green/red outcome palette.
Colors do not represent execution quality or market direction.
Execution reviews remain independent and are never inferred from P&L.

The optional `tradeSections` field in the existing private input to
`tools/record_trading_day.py` carries only these public fields per completed trade:
`startTime`, `endTime` (New York HH:MM or HH:MM:SS), `outcome`
(`profit`, `loss`, `flat`, `unrecorded`), `underlying` (`SPY`), and `sourceKind`
(`user_reported` or `imported_result`). Do not substitute the day's aggregate
outcome for each trade. Imported outcomes need matched closing records and fees;
unresolved lots, partial exits, overnight positions, or unknown timing must be
reconciled privately before supplying a session window. No amounts, account IDs,
broker filenames, or private notes belong in this public field.

The renderer clips the existing market line at supplied clock times without
adding market observations. Hourly charts remain hourly. Outside supplied windows,
breakeven/unknown outcomes, and overlapping windows with conflicting outcomes are
neutral. Only trades on the chart's underlying may color that chart.

The inspected July lot CSV headers contain opened_date and closed_date but no
entry/exit clock fields. The public trading ledger is empty. No real trade spans
were created in this change; those CSVs alone cannot supply precise overlays.

After staging evidence-backed rows, regenerate through the existing publishing
build. This source change was not built, tested, committed, or deployed. Existing
generated chart assets retain their previous colors until regeneration.
