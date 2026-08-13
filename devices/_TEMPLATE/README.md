# <DeviceName>

Copy this folder to `devices/<DeviceName>/` when starting a new device.

## What it does

_One paragraph. What problem does this solve in a set?_

## Parameters

| Name | Range | Default | What it does |
|---|---|---|---|
| | | | |

## Files

- `src/<DeviceName>.maxpat` — unfrozen source. **Edit this.**
- `dist/<DeviceName>.amxd` — frozen build. **Load this in Live.**

Both are committed, in the same change. `.githooks/pre-commit` blocks the commit
if the `.amxd` is not frozen or has no `.maxpat` beside it — see
`devices/README.md` for why.

## Used in

_Which sets / songs. Worth keeping: it tells you what breaks if you change this._
