$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".env")) {
    throw "Create and configure .env before building the desktop app."
}

npm ci
npm run build

if (-not (Test-Path ".venv")) {
    py -3.11 -m venv .venv
}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-desktop.txt

& ".\.venv\Scripts\pyinstaller.exe" `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name SendePro `
    --distpath ".desktop-dist" `
    --workpath ".desktop-build" `
    --add-data "dist;dist" `
    --collect-submodules backend `
    --collect-all pandas `
    --collect-all openpyxl `
    desktop.py

$ReleaseDir = Join-Path $ProjectRoot "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Copy-Item ".\.desktop-dist\SendePro.exe" "$ReleaseDir\SendePro.exe" -Force
Copy-Item ".\.env" "$ReleaseDir\.env" -Force
Write-Host "Standalone app created at: $ReleaseDir\SendePro.exe"
