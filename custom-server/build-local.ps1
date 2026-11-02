# Builds the patched Telegram Desktop (custom MTProto server) on this machine.
#
# Requirements (one time, needs an administrator):
#   * Visual Studio 2026 (or 2022) with the "Desktop development with C++"
#     workload + Windows SDK 10.0.26100.0
#   * Python 3.10+ and Git in PATH
#   * ~12 GB of free disk space on the build drive
#
# Everything else (Qt, OpenSSL, ffmpeg, ...) is downloaded by the official
# prepare script, so no manual Qt installation is needed.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File build-local.ps1
#   powershell -ExecutionPolicy Bypass -File build-local.ps1 -BuildPath D:\TBuild

param(
    [string]$BuildPath  = "E:\TBuild",
    [string]$SourcePath = "E:\tdesktop",
    [string]$ApiId      = "2040",
    [string]$ApiHash    = "b18441a1ff607e10a989891a5462e627",
    [switch]$SkipPrepare
)

$ErrorActionPreference = "Stop"

function Fail($message) {
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

# --- 1. Locate Visual Studio -------------------------------------------------
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    Fail "vswhere.exe not found. Install Visual Studio with the C++ workload first."
}
$vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsPath) {
    Fail "Visual Studio with the C++ workload not found."
}
$vcvars = Join-Path $vsPath "VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $vcvars)) {
    Fail "vcvars64.bat not found in $vsPath"
}
Write-Host "Visual Studio : $vsPath" -ForegroundColor Green

if (-not (Test-Path (Join-Path $SourcePath "Telegram\build\prepare\win.bat"))) {
    Fail "Source tree not found at $SourcePath"
}

# --- 2. Build folders --------------------------------------------------------
$librariesPath = Join-Path $BuildPath "Libraries\win64"
New-Item -ItemType Directory -Force -Path (Join-Path $BuildPath "ThirdParty") | Out-Null
New-Item -ItemType Directory -Force -Path $librariesPath | Out-Null

$env:TBUILD = $BuildPath
$env:LibrariesPath = $librariesPath

# --- 3. Third party libraries (Qt, OpenSSL, ffmpeg, ...) ---------------------
# NOTE: no 'skip-release' here. That flag drops every Release-scoped command
# from the library build scripts, and a Release app build then fails to link
# with LNK1181 (missing openssl3/out/libssl.lib, tg_angle, libavif) and
# LNK2038 (MT vs MTd in Qt static plugins).
if (-not $SkipPrepare) {
    Write-Host "`n=== Preparing third party libraries (60-150 min, ~10 GB) ===" -ForegroundColor Cyan
    cmd /c "call `"$vcvars`" -vcvars_ver=14.44 && `"$SourcePath\Telegram\build\prepare\win.bat`" silent"
    if ($LASTEXITCODE -ne 0) { Fail "prepare step failed" }
}

# --- 4. Configure ------------------------------------------------------------
Write-Host "`n=== Configure ===" -ForegroundColor Cyan
Push-Location (Join-Path $SourcePath "Telegram")
cmd /c "call `"$vcvars`" -vcvars_ver=14.44 && configure.bat x64 -D TDESKTOP_API_ID=$ApiId -D TDESKTOP_API_HASH=$ApiHash -D CMAKE_CONFIGURATION_TYPES=Release -D DESKTOP_APP_DISABLE_AUTOUPDATE=ON -D DESKTOP_APP_DISABLE_CRASH_REPORTS=ON"
$configureExit = $LASTEXITCODE
Pop-Location
if ($configureExit -ne 0) { Fail "configure step failed" }

# --- 5. Build ----------------------------------------------------------------
Write-Host "`n=== Build (Release, 30-90 min) ===" -ForegroundColor Cyan
cmd /c "call `"$vcvars`" -vcvars_ver=14.44 && cmake --build `"$SourcePath\out`" --config Release --parallel"
if ($LASTEXITCODE -ne 0) { Fail "build failed" }

$exe = Join-Path $SourcePath "out\Release\Telegram.exe"
if (-not (Test-Path $exe)) { Fail "Telegram.exe was not produced" }

Write-Host "`nDONE: $exe" -ForegroundColor Green
Write-Host "Run it once and check that it connects to the custom server." -ForegroundColor Green
