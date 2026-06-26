$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvRoot = Join-Path $ProjectRoot ".venv"
$ActivateScript = Join-Path $VenvRoot "Scripts\Activate.ps1"

Set-Location $ProjectRoot

if (-not (Test-Path $ActivateScript)) {
    Write-Error "Virtual environment activate script not found: $ActivateScript. Please run .\scripts\install_deps.ps1 first."
}

& $ActivateScript
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
