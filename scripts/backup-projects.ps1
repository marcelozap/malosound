<#
.SYNOPSIS
    Backs up the things git deliberately cannot: Live sets and imported samples.

.DESCRIPTION
    projects/ is gitignored wholesale, and Samples/Imported/ lives inside it, so
    no .gitignore rule can ever protect either one. Imported samples are NOT
    regenerable. This script is what stands in for version control there.

    See docs/BACKUP.md for the full reasoning.

.PARAMETER Snapshot
    Write a dated snapshot under <root>\snapshots\yyyy-MM-dd\ instead of updating
    the rolling mirror. Do this before anything destructive: a big arrangement
    edit, a Live version upgrade, a library reorganisation. This is the tier that
    saves you from yourself, which is the more common failure than a dead drive.

.PARAMETER IncludeLibrary
    Also mirror the sample library. Slow and rarely changes, so it is opt-in —
    but run it after any session where you imported new material.

.PARAMETER DryRun
    List what would be copied and change nothing.

.PARAMETER Destination
    Override the backup root. Normally comes from $env:MALOSOUND_BACKUP_ROOT.

.EXAMPLE
    setx MALOSOUND_BACKUP_ROOT "E:\malosound-backup"    # one time
    .\scripts\backup-projects.ps1                        # after any session
    .\scripts\backup-projects.ps1 -Snapshot              # before anything risky
    .\scripts\backup-projects.ps1 -DryRun                # see, change nothing
#>

[CmdletBinding()]
param(
    [switch] $Snapshot,
    [switch] $IncludeLibrary,
    [switch] $DryRun,
    [string] $Destination
)

$ErrorActionPreference = 'Stop'

$RepoRoot    = Split-Path -Parent $PSScriptRoot
$ProjectsDir = Join-Path $RepoRoot 'projects'
$LibraryDir  = if ($env:XIV_MUSIC_LIBRARY) { $env:XIV_MUSIC_LIBRARY }
               else { 'C:\Users\Green Machine\Music\XIV Music Library' }

function Write-Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   $msg"  -ForegroundColor Green }
function Write-Warn2($m)  { Write-Host "   $m"    -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "   $msg"  -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Destination. Refuse to run rather than silently mirror into nowhere — a backup
# script that reports success while writing to a path that does not exist is
# worse than no backup script at all.
# ---------------------------------------------------------------------------
if (-not $Destination) { $Destination = $env:MALOSOUND_BACKUP_ROOT }

if (-not $Destination) {
    Write-Err 'No backup destination set.'
    Write-Host ''
    Write-Host '  Point it at a drive that is not the one holding the repo:' -ForegroundColor Gray
    Write-Host '      setx MALOSOUND_BACKUP_ROOT "E:\malosound-backup"' -ForegroundColor Gray
    Write-Host '  then open a new terminal, or pass -Destination E:\path' -ForegroundColor Gray
    exit 1
}

$driveRoot = [System.IO.Path]::GetPathRoot($Destination)
if (-not (Test-Path $driveRoot)) {
    Write-Err "Backup drive $driveRoot is not available. Is it plugged in?"
    exit 1
}

$repoDrive = [System.IO.Path]::GetPathRoot($RepoRoot)
if ($driveRoot -eq $repoDrive) {
    Write-Warn2 "Destination is on the SAME DRIVE as the repo ($repoDrive)."
    Write-Warn2 'That protects you from mistakes but not from the drive dying.'
    Write-Warn2 'Tier 3 in docs/BACKUP.md exists for this reason.'
}

# ---------------------------------------------------------------------------
# Is Live holding a set open?
# ---------------------------------------------------------------------------
$live = Get-Process -Name 'Ableton*' -ErrorAction SilentlyContinue
if ($live) {
    Write-Warn2 'Ableton Live is running.'
    Write-Warn2 'Robocopy will happily copy an .als mid-write and produce a file'
    Write-Warn2 'that opens to an error. Save and close Live for snapshots.'
    if ($Snapshot -and -not $DryRun) {
        $answer = Read-Host '   Continue anyway? (y/N)'
        if ($answer -ne 'y') { Write-Host '   Aborted.'; exit 1 }
    }
}

# ---------------------------------------------------------------------------
if ($Snapshot) {
    $stamp  = Get-Date -Format 'yyyy-MM-dd_HHmm'
    $target = Join-Path $Destination "snapshots\$stamp"
    $mode   = "SNAPSHOT -> $stamp"
} else {
    $target = Join-Path $Destination 'mirror'
    $mode   = 'MIRROR (rolling)'
}

Write-Host ''
Write-Host '  malosound backup' -ForegroundColor White
Write-Host "  mode        : $mode"
Write-Host "  source      : $ProjectsDir"
Write-Host "  destination : $target"
if ($DryRun) { Write-Host '  DRY RUN — nothing will be written' -ForegroundColor Yellow }

# ---------------------------------------------------------------------------
# Robocopy.
#   /MIR   mirror (deletes at the destination what is gone at the source)
#   /E     subdirectories including empty ones — snapshots do not delete
#   /Z     restartable, survives a USB drive hiccup mid-copy
#   /R:2 /W:5   two retries, five seconds apart, instead of the default million
#   /XD    excluded dirs: regenerable, and they are the bulk of the bytes
# ---------------------------------------------------------------------------
$common = @('/Z', '/R:2', '/W:5', '/NP', '/NDL', '/TEE')
if ($DryRun) { $common += '/L' }

# Processed/ is rebuilt by Live on demand. Imported/ is NOT — it is never excluded.
$excludeDirs = @('Backup', 'Processed', 'Ableton Project Info')
$excludeFiles = @('*.asd', '*.als.bak', 'Thumbs.db', 'desktop.ini', '.DS_Store')

function Invoke-Robocopy($src, $dst, [switch]$Mirror) {
    if (-not (Test-Path $src)) {
        Write-Warn2 "source missing, skipping: $src"
        return $true
    }

    $args = @($src, $dst) + $common
    $args += if ($Mirror) { '/MIR' } else { '/E' }
    $args += '/XD'; $args += $excludeDirs
    $args += '/XF'; $args += $excludeFiles

    & robocopy @args | Out-Null
    $code = $LASTEXITCODE

    # Robocopy exit codes are a bitmask, not a status. 0-7 are success
    # (0 = nothing to do, 1 = files copied, 2 = extra files, 4 = mismatches).
    # 8 and above mean at least one file genuinely failed to copy.
    if ($code -ge 8) {
        Write-Err "robocopy failed (exit $code) for $src"
        return $false
    }
    if ($code -eq 0) { Write-Ok 'already up to date' } else { Write-Ok "done (robocopy $code)" }
    return $true
}

$ok = $true

Write-Step 'projects/ — Live sets, takes, and Samples/Imported/'
$ok = (Invoke-Robocopy $ProjectsDir (Join-Path $target 'projects') -Mirror:(-not $Snapshot)) -and $ok

Write-Step 'releases/ — masters referenced by the release metadata'
$releasesDir = Join-Path $RepoRoot 'releases'
$ok = (Invoke-Robocopy $releasesDir (Join-Path $target 'releases') -Mirror:(-not $Snapshot)) -and $ok

Write-Step 'strudel tracks/ — audio dropped next to the patterns'
$strudelTracks = Join-Path $RepoRoot 'scripts\strudel\tracks'
$ok = (Invoke-Robocopy $strudelTracks (Join-Path $target 'strudel-tracks') -Mirror:(-not $Snapshot)) -and $ok

if ($IncludeLibrary) {
    Write-Step 'XIV Music Library — the sample library'
    $ok = (Invoke-Robocopy $LibraryDir (Join-Path $target 'XIV Music Library') -Mirror:(-not $Snapshot)) -and $ok
} else {
    Write-Step 'XIV Music Library — SKIPPED'
    Write-Warn2 'Pass -IncludeLibrary after any session where you imported new material.'
}

# ---------------------------------------------------------------------------
if (-not $DryRun) {
    $manifest = Join-Path $target 'BACKUP_INFO.txt'
    $lines = @(
        "malosound backup"
        "when        : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        "mode        : $mode"
        "source repo : $RepoRoot"
        "library     : $LibraryDir$(if (-not $IncludeLibrary) { '   (NOT included in this run)' })"
        "host        : $env:COMPUTERNAME"
        ""
        "Restore: copy projects\ back to the repo, open the set, and if Live asks"
        "for missing files point it at the library once, then File > Collect All"
        "and Save. Check Samples/Imported/ actually came back — that is the folder"
        "that matters. See docs/BACKUP.md."
    )
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    $lines | Set-Content -Path $manifest -Encoding UTF8
}

Write-Host ''
if ($ok) {
    Write-Host '  backup complete.' -ForegroundColor Green
    if (-not $DryRun -and $Snapshot) {
        Write-Host "  snapshot: $target" -ForegroundColor Gray
    }
    Write-Host '  Untested backups are beliefs, not backups — restore one to a' -ForegroundColor Gray
    Write-Host '  scratch folder and open it before you need to.' -ForegroundColor Gray
    exit 0
} else {
    Write-Host '  backup finished WITH ERRORS — read the output above.' -ForegroundColor Red
    exit 1
}
