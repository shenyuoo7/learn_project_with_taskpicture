$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvRoot = Join-Path $ProjectRoot ".venv"
$ActivateScript = Join-Path $VenvRoot "Scripts\Activate.ps1"

Set-Location $ProjectRoot

if (-not (Test-Path $ActivateScript)) {
    Write-Host "Creating virtual environment: $VenvRoot"
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -m venv $VenvRoot
    }
    else {
        python -m venv $VenvRoot
    }
}

if (-not (Test-Path $ActivateScript)) {
    Write-Error "Virtual environment activate script not found after creation: $ActivateScript"
}

& $ActivateScript
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
