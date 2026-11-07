$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& "$PSScriptRoot\check_windows.ps1"
if ($LASTEXITCODE -ne 0) { throw "Preflight checks failed." }

Write-Host "Starting Social Video Studio at http://127.0.0.1:8000/" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
