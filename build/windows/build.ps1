# Build the one-click TV Liberator installer. Run from the repo root on Windows:
#   powershell -ExecutionPolicy Bypass -File build\windows\build.ps1
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root
$version = (Get-Content "$root\VERSION").Trim()
Write-Host "Building TV Liberator $version"

if (-not (Test-Path "$root\.venv")) { python -m venv "$root\.venv" }
$py = "$root\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r "$root\requirements.txt" pyinstaller

# Bundle Samsung's sdb so the user never installs Tizen Studio.
& $py -c "from tvlib.vendor import fetch_sdb; print(fetch_sdb.fetch('windows-64'))"

# Preload the app catalog (Jellyfin for Samsung + LG) into the installer.
& $py -m tvlib.appstore
if ($LASTEXITCODE -ne 0) { throw "app catalog download failed" }

Remove-Item -Recurse -Force "$root\build\pyi", "$root\dist" -ErrorAction SilentlyContinue
& $py -m PyInstaller --noconfirm --clean `
    --distpath "$root\dist" --workpath "$root\build\pyi" `
    "$root\build\windows\tv-liberator.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# Inno Setup produces the single-file installer.
$iscc = Get-ChildItem "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", `
                      "$env:ProgramFiles\Inno Setup 6\ISCC.exe" `
                      -ErrorAction SilentlyContinue | Select-Object -First 1
if ($iscc) {
    & $iscc.FullName "/DMyAppVersion=$version" "$root\build\windows\installer.iss"
    if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }
    Write-Host "Installer: $root\dist\TV-Liberator-Setup-$version.exe"
} else {
    Write-Warning "Inno Setup 6 not found; portable build only at dist\TV Liberator"
}
