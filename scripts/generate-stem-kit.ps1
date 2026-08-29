<#
.SYNOPSIS
    Generate local utility stems for a MaloSound recording session.

.DESCRIPTION
    Writes click/count-in, sidechain pulse, movement cue, and silence-bed WAVs
    under ignored projects/ by default. Audio bytes stay out of git.
#>

param(
    [string] $Session = 'my-friend-first-pass',
    [double] $Bpm = 106,
    [int] $Bars = 16,
    [int] $BeatsPerBar = 4,
    [int] $SampleRate = 48000,
    [string] $Output,
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $RepoRoot 'scripts\generate-stem-kit.py'

$Args = @(
    $Script,
    '--session', $Session,
    '--bpm', $Bpm,
    '--bars', $Bars,
    '--beats-per-bar', $BeatsPerBar,
    '--sample-rate', $SampleRate
)

if ($Output) { $Args += @('--output', $Output) }
if ($DryRun) { $Args += '--dry-run' }

python @Args
