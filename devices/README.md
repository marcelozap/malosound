# devices — Max for Live

## The rule, and why it is enforced by a hook

Every device has two representations and they are not interchangeable:

```
devices/<Name>/
  src/<Name>.maxpat     UNFROZEN. Text (JSON). Diffable. The source of truth.
  dist/<Name>.amxd      FROZEN. Binary. What you actually load in Live.
  README.md             what it does, params, which set it is used in
```

**`src/` is what you edit. `dist/` is what you ship. Commit both, in the same
change.**

Freezing embeds every dependency — samples, abstractions, JS files — inside the
`.amxd`. An unfrozen device works perfectly on the machine that made it and
opens to a wall of "object not found" anywhere else. This rig is a MacBook and a
PC, so "anywhere else" is not hypothetical, it is Tuesday.

`.githooks/pre-commit` blocks a commit if:

- an `.amxd` is staged from anywhere other than `devices/<Name>/dist/`
- a staged `.amxd` has no freeze manifest inside it (i.e. it is not frozen)
- an `.amxd` is committed with no `.maxpat` source anywhere in its device folder

That last one matters more than it looks: a binary with no readable source is a
device nobody — including you in six months — can review, diff, or repair.

## Making a new device

```
devices/MyDevice/
  src/     <- save the unfrozen patcher here from Max
  dist/    <- File > Freeze Device, then export here
  README.md
```

1. In Live, drop a Max Audio Effect / Instrument / MIDI Effect on a track, edit it.
2. Save the patcher into `devices/MyDevice/src/MyDevice.maxpat`.
3. When it works: **Freeze Device** (the snowflake in the M4L toolbar), then save
   the frozen `.amxd` into `devices/MyDevice/dist/`.
4. `git add` both. The hook checks the rest.

## Reviewing a change

`.maxpat` is JSON, so `git diff` works — but Max rewrites object positions and
ids constantly, so a two-line logical change can show as a hundred-line diff.
Read the diff for `"text"` fields and box connections; ignore coordinates.

`.gitattributes` marks `.maxpat` as `-merge` on purpose. Git will not attempt to
line-merge two patchers, because the result is a file Max refuses to open. On a
conflict, take one side whole and redo the other change in Max.

## What does not belong here

- Sample content — the library holds bytes, see `LIBRARY_PATH.md`
- Compiled externals — `devices/**/externals/` is ignored
- The Strudel work — that is `scripts/strudel/`, it is not a Max device
