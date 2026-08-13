# Backup — what git deliberately cannot save

Read this before you assume the repo has your back. It does not, for the two
things most likely to hurt if you lose them.

## The gap, stated plainly

`.gitignore` line 1 is `projects/`. Ableton projects never enter git — they are
binary, they churn on every save, and they drag gigabytes of samples behind
them. That is the right call and it is not changing.

But `Samples/Imported/` — the samples Live copied into a project because you
dragged them in from somewhere — **only ever exists inside a Live project
folder**. So it is inside `projects/`. So it is ignored. So no `.gitignore` rule
can ever protect it, no matter how it is written.

Imported samples are **not regenerable**. `Samples/Processed/` is: Live rebuilds
warp markers and analysis files on demand. Imported is the actual audio you
brought in, and if the drive dies it is gone in a way that a re-render cannot fix.

An earlier version of `.gitignore` carried a `Samples/Processed/` rule that could
never fire — `projects/` above it already swallowed everything. It read as
protection and did nothing. It has been removed rather than left there looking
reassuring.

**This file, and the script it describes, are the only thing standing between you
and that loss.**

## What gets backed up

| Path | Why |
|---|---|
| `projects/` (whole tree) | Live sets, all takes, all Imported samples |
| `XIV Music Library\` | the sample library — big, slow-changing, still irreplaceable |
| `releases/` | metadata is in git; the master audio referenced from it is not |

## The scheme

`scripts/backup-projects.ps1` — robocopy mirror with dated snapshots.

Three tiers, in increasing order of how much you would regret not having them:

1. **Working mirror** — one full copy on a second physical drive. Not the same
   drive, not another partition on the same drive. Run it at the end of any
   session where you recorded something.
2. **Dated snapshot** — a full copy under `snapshots\YYYY-MM-DD\`, made before
   anything destructive: a big arrangement edit, a Live version upgrade, a
   sample-library reorganisation. This is the one that saves you from *yourself*,
   which is the more common failure than a dead drive.
3. **Offsite** — one copy that is not in the room. A drive at another address, or
   cloud. The room is a single point of failure for fire, theft, and flood, and
   a mirror sitting next to the PC does not survive any of them.

Tiers 1 and 2 are what the script does today. Tier 3 is a decision you have not
made yet — see below.

### Running it

```powershell
# one-time: point it at the drive
setx MALOSOUND_BACKUP_ROOT "E:\malosound-backup"

# working mirror, after any session where you recorded
.\scripts\backup-projects.ps1

# dated snapshot, before anything destructive
.\scripts\backup-projects.ps1 -Snapshot

# see what it would do, change nothing
.\scripts\backup-projects.ps1 -DryRun
```

The script refuses to run if the destination is missing, rather than silently
mirroring to a path that does not exist — a backup script that reports success
while writing nowhere is worse than no backup script.

### Close Live first

Robocopy will happily copy a `.als` mid-write. Ableton holds the set open and
writes it whole on save; copying during that window can produce a truncated file
that opens to an error. The script warns if Live appears to be running. Take the
warning seriously for tier 2 snapshots.

## Still open: the offsite decision

Not decided yet, deliberately — the trade-off is real and it is yours:

- **Second external drive, stored elsewhere.** No quota, no monthly cost, no sync
  daemon fighting Ableton for file locks. Costs discipline: it only protects you
  as often as you remember to carry it.
- **Cloud (Drive, Backblaze, Dropbox).** Automatic, genuinely offsite. Costs
  quota — a single Live project with a full `Imported/` folder runs to gigabytes
  — and sync clients have a habit of grabbing files Ableton has open. If you go
  this way, sync the *snapshot* folder, never the live `projects/` tree.

A reasonable default if you want one: external drive for tiers 1–2, cloud for the
`snapshots/` folder only. That keeps the fast path local and the slow path small.

## What is NOT backed up, on purpose

- `dsp/build/`, `artifacts/` — regenerable in seconds
- `Samples/Processed/`, `*.asd` — Live rebuilds these on demand
- anything already in git — that is what git is for

## Restore

There is no restore script, because restoring is `robocopy` in the other
direction and a script would only add a way to get it wrong. What matters:

1. Copy the snapshot back to `C:\Users\Green Machine\XIV\malosound\projects\`.
2. Open the set. If Live asks for missing files, point it at the library once and
   use **File → Collect All and Save**.
3. Check `Samples/Imported/` actually came back. That is the folder that matters.

**Test this before you need it.** Restore one project to a scratch folder and
open it. An untested backup is a belief, not a backup.
