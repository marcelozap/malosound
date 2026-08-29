Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectsRoot = Join-Path $Root "projects"

function Start-RepoCommand {
    param([string]$Command)
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-NoExit",
        "-Command",
        "Set-Location -LiteralPath '$Root'; $Command"
    )
}

function Open-PathIfExists {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Start-Process -FilePath $Path
    } else {
        [System.Windows.Forms.MessageBox]::Show("Not found:`n$Path", "MaloSound Studio") | Out-Null
    }
}

function Get-LatestStemKit {
    if (-not (Test-Path -LiteralPath $ProjectsRoot)) { return $null }
    $kits = Get-ChildItem -LiteralPath $ProjectsRoot -Recurse -Filter "STEMS.md" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
    if ($kits.Count -eq 0) { return $null }
    return $kits[0]
}

function New-Label($Text, $X, $Y, $W = 140) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.Location = New-Object System.Drawing.Point($X, $Y)
    $label.Size = New-Object System.Drawing.Size($W, 22)
    $label.ForeColor = [System.Drawing.Color]::FromArgb(222, 230, 240)
    return $label
}

function New-TextBox($Text, $X, $Y, $W = 360) {
    $box = New-Object System.Windows.Forms.TextBox
    $box.Text = $Text
    $box.Location = New-Object System.Drawing.Point($X, $Y)
    $box.Size = New-Object System.Drawing.Size($W, 28)
    $box.BackColor = [System.Drawing.Color]::FromArgb(22, 25, 31)
    $box.ForeColor = [System.Drawing.Color]::White
    $box.BorderStyle = "FixedSingle"
    return $box
}

function New-Button($Text, $X, $Y, $W, $Handler) {
    $button = New-Object System.Windows.Forms.Button
    $button.Text = $Text
    $button.Location = New-Object System.Drawing.Point($X, $Y)
    $button.Size = New-Object System.Drawing.Size($W, 34)
    $button.BackColor = [System.Drawing.Color]::FromArgb(34, 42, 54)
    $button.ForeColor = [System.Drawing.Color]::White
    $button.FlatStyle = "Flat"
    $button.Add_Click($Handler)
    return $button
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "MaloSound Studio"
$form.Size = New-Object System.Drawing.Size(760, 620)
$form.StartPosition = "CenterScreen"
$form.BackColor = [System.Drawing.Color]::FromArgb(9, 11, 15)
$form.ForeColor = [System.Drawing.Color]::White

$title = New-Object System.Windows.Forms.Label
$title.Text = "MaloSound Studio"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(28, 22)
$title.Size = New-Object System.Drawing.Size(520, 46)
$title.ForeColor = [System.Drawing.Color]::FromArgb(120, 220, 255)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "Local DAW prep: DSP checks, utility stems, movement cues, and repo-safe session notes."
$subtitle.Location = New-Object System.Drawing.Point(32, 72)
$subtitle.Size = New-Object System.Drawing.Size(680, 24)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(180, 190, 205)
$form.Controls.Add($subtitle)

$session = New-TextBox "my-friend-first-pass" 178 122 360
$bpm = New-TextBox "106" 178 166 100
$bars = New-TextBox "16" 178 210 100
$beats = New-TextBox "4" 178 254 100

$form.Controls.Add((New-Label "Session" 34 124))
$form.Controls.Add($session)
$form.Controls.Add((New-Label "BPM" 34 168))
$form.Controls.Add($bpm)
$form.Controls.Add((New-Label "Bars" 34 212))
$form.Controls.Add($bars)
$form.Controls.Add((New-Label "Beats / bar" 34 256))
$form.Controls.Add($beats)

$map = New-Object System.Windows.Forms.Label
$map.Text = "First pass: generate utility stems -> import into DAW -> record vocal and movement -> keep audio out of git."
$map.Location = New-Object System.Drawing.Point(34, 306)
$map.Size = New-Object System.Drawing.Size(670, 36)
$map.ForeColor = [System.Drawing.Color]::FromArgb(165, 245, 195)
$form.Controls.Add($map)

$form.Controls.Add((New-Button "Generate Stems" 34 360 160 {
    $cmd = ".\scripts\generate-stem-kit.ps1 -Session `"$($session.Text)`" -Bpm $($bpm.Text) -Bars $($bars.Text) -BeatsPerBar $($beats.Text)"
    Start-RepoCommand $cmd
}))

$form.Controls.Add((New-Button "Open Latest Kit" 210 360 160 {
    $kit = Get-LatestStemKit
    if ($null -eq $kit) {
        [System.Windows.Forms.MessageBox]::Show("No STEMS.md found yet. Generate stems first.", "MaloSound Studio") | Out-Null
    } else {
        Start-Process -FilePath $kit.FullName
    }
}))

$form.Controls.Add((New-Button "Build DSP" 386 360 132 {
    Start-RepoCommand ".\scripts\build-dsp.ps1"
}))

$form.Controls.Add((New-Button "Open Projects" 534 360 150 {
    Open-PathIfExists $ProjectsRoot
}))

$form.Controls.Add((New-Button "Stem Workflow" 34 414 160 {
    Open-PathIfExists (Join-Path $Root "docs\STEM_GENERATION.md")
}))

$form.Controls.Add((New-Button "Plugin Plan" 210 414 160 {
    Open-PathIfExists (Join-Path $Root "docs\ABLETON_PLUGIN_PLAN.md")
}))

$form.Controls.Add((New-Button "DSP Readme" 386 414 132 {
    Open-PathIfExists (Join-Path $Root "dsp\README.md")
}))

$form.Controls.Add((New-Button "Start Here" 534 414 150 {
    Open-PathIfExists (Join-Path $Root "docs\START_HERE.md")
}))

$form.Controls.Add((New-Button "Doctor" 34 468 160 {
    Start-RepoCommand ".\scripts\studio-doctor.ps1 -Fast"
}))

$form.Controls.Add((New-Button "Open Library Note" 210 468 160 {
    Open-PathIfExists (Join-Path $Root "LIBRARY_PATH.md")
}))

$form.Controls.Add((New-Button "Backup Notes" 386 468 132 {
    Open-PathIfExists (Join-Path $Root "docs\BACKUP.md")
}))

$form.Controls.Add((New-Button "Repo Map" 534 468 150 {
    Open-PathIfExists (Join-Path $Root "docs\REPO_MAP.md")
}))

$boundary = New-Object System.Windows.Forms.Label
$boundary.Text = "Boundary: local files only. No upload, no posting, no account action, no raw audio in git."
$boundary.Location = New-Object System.Drawing.Point(34, 540)
$boundary.Size = New-Object System.Drawing.Size(680, 22)
$boundary.ForeColor = [System.Drawing.Color]::FromArgb(220, 198, 126)
$form.Controls.Add($boundary)

[void]$form.ShowDialog()
