# One-time setup: Python virtual environment, backend dependencies, demo datasets and frontend packages.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==> Backend: creating virtual environment" -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\make_samples.py
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }

Write-Host "==> Frontend: installing packages" -ForegroundColor Cyan
Set-Location "$root\frontend"
npm.cmd install

Set-Location $root
Write-Host "`nSetup complete. Run .\start.ps1 to launch the app." -ForegroundColor Green
