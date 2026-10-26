# Build the Windows release: a portable zip and an installer.
# Run from the repository root in PowerShell:  .\packaging\windows\build.ps1
# Needs Python 3.10+; Inno Setup 6 (iscc) for the installer step.

param(
    [string]$Version = "",
    [switch]$SkipMpv
)

$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

if (-not $Version) {
    $Version = (python -c "import re,pathlib; print(re.search(r'__version__ = \""(.+?)\""', pathlib.Path('src/limpaper/__init__.py').read_text()).group(1))")
}
Write-Host "==> limpaper $Version"

Write-Host "==> Python dependencies"
python -m pip install --upgrade pip
python -m pip install pyinstaller "PySide6-Essentials>=6.5" "PySide6-Addons>=6.5" "textual>=0.47" .

Write-Host "==> PyInstaller"
pyinstaller --noconfirm --clean --distpath dist --workpath build packaging\windows\limpaper.spec
$app = "dist\limpaper"

if (-not $SkipMpv) {
    Write-Host "==> Bundling mpv"
    try {
        $headers = @{ "User-Agent" = "limpaper-build" }
        if ($env:GITHUB_TOKEN) { $headers["Authorization"] = "Bearer $env:GITHUB_TOKEN" }
        $release = Invoke-RestMethod -Headers $headers `
            "https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest"
        # Plain x86_64 build (not -v3, which needs a newer CPU)
        $asset = $release.assets | Where-Object { $_.name -match '^mpv-x86_64-\d{8}-git-[0-9a-f]+\.7z$' } |
            Select-Object -First 1
        if (-not $asset) { throw "no matching mpv asset in $($release.tag_name)" }
        Write-Host "    $($asset.name)"
        Invoke-WebRequest -Headers $headers $asset.browser_download_url -OutFile "build\mpv.7z"
        7z x "build\mpv.7z" "-o$app\mpv" -y | Out-Null
        if (-not (Test-Path "$app\mpv\mpv.exe")) { throw "mpv.exe missing after extraction" }
        @"
mpv is free software (GPLv2+/LGPLv2.1+), bundled unmodified so limpaper can
play video wallpapers. Build from https://github.com/shinchiro/mpv-winbuild-cmake
($($release.tag_name)). Source code: https://github.com/mpv-player/mpv
"@ | Set-Content "$app\mpv\README-limpaper.txt"
    } catch {
        Write-Warning "Could not bundle mpv ($_). The app will ask users to install it."
    }
}

Write-Host "==> Portable zip"
$zip = "dist\limpaper-windows-x64-portable.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $app -DestinationPath $zip

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc -and (Test-Path "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe")) {
    $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
}
if ($iscc) {
    Write-Host "==> Installer"
    & $iscc "/DAppVersion=$Version" packaging\windows\installer.iss
} else {
    Write-Warning "Inno Setup not found; skipped the installer (portable zip is ready)."
}

Get-ChildItem dist -File | Format-Table Name, Length
