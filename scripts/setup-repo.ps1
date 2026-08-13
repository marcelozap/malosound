<#
.SYNOPSIS
    One-time setup for a fresh clone of malosound.

.DESCRIPTION
    Git does not version core.hooksPath, so the pre-commit hook that enforces the
    device-freeze rule and keeps audio out of the repo has to be switched on once
    per clone. This does that, and checks the tools the repo expects.

    Run it after cloning, and on every machine in the rig.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

function Ok($m)   { Write-Host "  [ok]   $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [warn] $m" -ForegroundColor Yellow }
function Err($m)  { Write-Host "  [err]  $m" -ForegroundColor Red }

Write-Host "`nmalosound — repo setup`n" -ForegroundColor White

# --- hooks -----------------------------------------------------------------
git config core.hooksPath .githooks
Ok 'pre-commit hook enabled (core.hooksPath = .githooks)'
Write-Host '         It blocks unfrozen .amxd, audio bytes, and >20 MB files.' -ForegroundColor Gray
Write-Host '         Bypass a single commit with --no-verify if you truly mean it.' -ForegroundColor Gray

# --- line endings ----------------------------------------------------------
# .gitattributes already pins per-type behaviour; this stops git from also
# applying its own guess on top on Windows.
git config core.autocrlf false
Ok 'core.autocrlf = false (.gitattributes decides, not git)'

# --- identity --------------------------------------------------------------
$name  = git config user.name
$email = git config user.email
if (-not $name -or -not $email) {
    Warn 'git user.name / user.email not set — commits will be attributed oddly'
    Write-Host '         git config --global user.name  "..."' -ForegroundColor Gray
    Write-Host '         git config --global user.email "..."' -ForegroundColor Gray
} else {
    Ok "identity: $name <$email>"
}

# --- backup destination ----------------------------------------------------
if ($env:MALOSOUND_BACKUP_ROOT) {
    if (Test-Path ([System.IO.Path]::GetPathRoot($env:MALOSOUND_BACKUP_ROOT))) {
        Ok "backup root: $env:MALOSOUND_BACKUP_ROOT"
    } else {
        Warn "backup root set to $env:MALOSOUND_BACKUP_ROOT but that drive is not attached"
    }
} else {
    Warn 'MALOSOUND_BACKUP_ROOT not set — projects/ is NOT backed up'
    Write-Host '         setx MALOSOUND_BACKUP_ROOT "E:\malosound-backup"' -ForegroundColor Gray
    Write-Host '         This is the only thing protecting Samples/Imported/.' -ForegroundColor Gray
    Write-Host '         See docs/BACKUP.md.' -ForegroundColor Gray
}

# --- library ---------------------------------------------------------------
$lib = if ($env:XIV_MUSIC_LIBRARY) { $env:XIV_MUSIC_LIBRARY }
       else { 'C:\Users\Green Machine\Music\XIV Music Library' }
if (Test-Path $lib) { Ok "sample library: $lib" }
else { Warn "sample library not found at $lib (set XIV_MUSIC_LIBRARY)" }

# --- toolchain -------------------------------------------------------------
foreach ($tool in @('cmake', 'node')) {
    if (Get-Command $tool -ErrorAction SilentlyContinue) { Ok "$tool found" }
    else { Warn "$tool not found — needed for $(if ($tool -eq 'cmake') { 'dsp/' } else { 'strudel syntax checks' })" }
}

Pop-Location
Write-Host "`ndone. Next: docs/START_HERE.md`n" -ForegroundColor White
