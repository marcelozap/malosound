<#
.SYNOPSIS
    Build and test the malosound analysis core.

.PARAMETER Debug
    Build Debug instead of Release.

.PARAMETER Clean
    Delete the build directory first.

.EXAMPLE
    .\scripts\build-dsp.ps1
    .\scripts\build-dsp.ps1 -Clean -Debug
#>

[CmdletBinding()]
param(
    [switch] $Debug,
    [switch] $Clean
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BuildDir = Join-Path $RepoRoot 'dsp\build'
$Config   = if ($Debug) { 'Debug' } else { 'Release' }

if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Host 'cmake not found.' -ForegroundColor Red
    Write-Host ''
    Write-Host 'No CMake? One line still works, if you have g++ or clang++:' -ForegroundColor Gray
    Write-Host '  g++ -std=c++17 -O2 -Idsp/include -Idsp/tests dsp/src/*.cpp dsp/tests/test_dsp.cpp -o test_dsp' -ForegroundColor Gray
    exit 1
}

if ($Clean -and (Test-Path $BuildDir)) {
    Write-Host "cleaning $BuildDir" -ForegroundColor Gray
    Remove-Item -Recurse -Force $BuildDir
}

Push-Location $RepoRoot
try {
    cmake -S dsp -B dsp/build -DCMAKE_BUILD_TYPE=$Config
    if ($LASTEXITCODE -ne 0) { throw "cmake configure failed" }

    cmake --build dsp/build --config $Config
    if ($LASTEXITCODE -ne 0) { throw "build failed" }

    Write-Host "`nrunning tests`n" -ForegroundColor Cyan
    ctest --test-dir dsp/build --output-on-failure -C $Config
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nTests failed." -ForegroundColor Red
        Write-Host 'If the failure is "NaN input does not poison the filter state",' -ForegroundColor Gray
        Write-Host 'check whether something turned on -ffast-math / /fp:fast. That' -ForegroundColor Gray
        Write-Host 'flag deletes the NaN guard. See the comment in dsp/CMakeLists.txt.' -ForegroundColor Gray
        exit 1
    }

    Write-Host "`nall good." -ForegroundColor Green
}
finally {
    Pop-Location
}
