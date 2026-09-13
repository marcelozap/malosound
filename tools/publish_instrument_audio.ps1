param([string]$Target = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not $Target) { $Target = (git -C $root rev-parse HEAD).Trim() }
if ($Target -notmatch '^[0-9a-f]{40}$') { throw 'A committed Git SHA is required.' }
$index = Get-Content -LiteralPath "$root\config\instrument-audio.json" -Raw | ConvertFrom-Json
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'Never'
$credential = "protocol=https`nhost=github.com`n`n" | git credential fill 2>$null
$fields = @{}
foreach ($line in $credential) { $pair = $line.Split('=',2); if ($pair.Length -eq 2) { $fields[$pair[0]] = $pair[1] } }
if (-not $fields['password']) { throw 'GitHub publishing credential unavailable.' }
$headers = @{Authorization="Bearer $($fields['password'])"; Accept='application/vnd.github+json'; 'User-Agent'='MaloSound-release'}
$api = 'https://api.github.com/repos/marcelozap/malosound'
$tag = 'instrument-audio-2026-09-13'
try { $release = Invoke-RestMethod -Uri "$api/releases/tags/$tag" -Headers $headers }
catch {
    if ([int]$_.Exception.Response.StatusCode -ne 404) { throw }
    $body = @{tag_name=$tag; target_commitish=$Target; name='Instrument audio - September 2026'; draft=$true; prerelease=$true; body='Eight deterministic House arrangements for the historical price-driven instrument. Exact file and source-document hashes are recorded in config/instrument-audio.json. Audio bytes remain outside Git.'} | ConvertTo-Json
    $release = Invoke-RestMethod -Method Post -Uri "$api/releases" -Headers $headers -ContentType 'application/json' -Body $body
}
$upload = ($release.upload_url -split '\{')[0]
foreach ($entry in $index) {
    $name = "$($entry.date)-house.mp3"
    $file = "$root\assets\instrument\$name"
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower() -ne $entry.sha256) { throw "$name local hash mismatch" }
    $existing = @($release.assets | Where-Object { $_.name -eq $name })
    if ($existing.Count) {
        if ($existing[0].digest -ne "sha256:$($entry.sha256)") { throw "$name already exists with an unconfirmed hash; no overwrite performed." }
        continue
    }
    $asset = Invoke-RestMethod -Method Post -Uri "${upload}?name=$name" -Headers $headers -ContentType 'application/octet-stream' -InFile $file
    if ($asset.size -ne $entry.bytes -or ($asset.digest -and $asset.digest -ne "sha256:$($entry.sha256)")) { throw "$name upload mismatch" }
    Write-Output "Uploaded $name"
}
if ($release.draft) { $release = Invoke-RestMethod -Method Patch -Uri "$api/releases/$($release.id)" -Headers $headers -ContentType 'application/json' -Body '{"draft":false}' }
Write-Output $release.html_url
