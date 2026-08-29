<#
.SYNOPSIS
    Check MaloSound local studio readiness.
#>

param(
    [switch] $Fast
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $RepoRoot 'scripts\studio-doctor.py'
$Args = @($Script)
if ($Fast) { $Args += '--fast' }

python @Args
