$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Social Video Studio setup" -ForegroundColor Cyan
$PythonVersion = & py -3.12 --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12 was not found. Install Python 3.12 and enable the Python launcher."
}
Write-Host "Found $PythonVersion"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }

& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Could not install Python requirements." }

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Edit API_KEY before starting the server." -ForegroundColor Yellow
}

New-Item -ItemType Directory -Force -Path "data" | Out-Null
Write-Host "Setup complete. Next run: .\scripts\check_windows.ps1" -ForegroundColor Green
