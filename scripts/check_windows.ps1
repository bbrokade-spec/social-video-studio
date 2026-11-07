$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Problems = @()
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    $Problems += "Python virtual environment is missing. Run .\scripts\setup_windows.ps1."
} else {
    $Version = & .\.venv\Scripts\python.exe --version 2>&1
    Write-Host "Python: $Version"
}

$Ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
$Ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not $Ffmpeg) { $Problems += "ffmpeg.exe is not on PATH." }
if (-not $Ffprobe) { $Problems += "ffprobe.exe is not on PATH." }

if ($Ffmpeg) {
    $FilterOutput = & ffmpeg -hide_banner -filters 2>&1
    if (($FilterOutput -join "`n") -notmatch "(?m)\bsubtitles\b") {
        $Problems += "The installed FFmpeg does not advertise the subtitles filter. Install a build with libass enabled."
    } else {
        Write-Host "FFmpeg subtitles filter: available"
    }
}

if (-not (Test-Path ".env")) {
    $Problems += ".env is missing. Run setup and configure API_KEY."
} else {
    $EnvText = Get-Content ".env" -Raw
    if ($EnvText -notmatch "(?m)^API_KEY=\s*\S+") {
        $Problems += "API_KEY is blank in .env. Set a strong, unique local key."
    } else {
        Write-Host "Local API key: configured"
    }
}

if ($Problems.Count -gt 0) {
    Write-Host "`nPreflight failed:" -ForegroundColor Red
    $Problems | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
    throw "Windows preflight failed. Resolve the listed issues and run the check again."
}

Write-Host "`nPreflight passed. You can start the local server." -ForegroundColor Green
