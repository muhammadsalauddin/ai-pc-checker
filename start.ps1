# ============================================================
#  AI PC Suitability Checker — Windows Start Script
#  Usage:
#    powershell -ExecutionPolicy Bypass -File start.ps1
#    powershell -ExecutionPolicy Bypass -File start.ps1 --cli
# ============================================================
param([string]$Mode = "")

function Info    { param($m); Write-Host "  [INFO]  $m" -ForegroundColor Cyan }
function Success { param($m); Write-Host "  [ OK ]  $m" -ForegroundColor Green }
function Warn    { param($m); Write-Host "  [WARN]  $m" -ForegroundColor Yellow }
function Err     { param($m); Write-Host "  [ERR ]  $m" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  ==============================================" -ForegroundColor Cyan
Write-Host "   AI PC SUITABILITY CHECKER  - STARTING       " -ForegroundColor Cyan
Write-Host "  ==============================================" -ForegroundColor Cyan
Write-Host ""

if ($Mode -eq "--help" -or $Mode -eq "-h") {
    Write-Host "  .\start.ps1             Web dashboard (browser opens automatically)"
    Write-Host "  .\start.ps1 --cli       CLI terminal version"
    exit 0
}

# Always work from the folder this script lives in
$Here = Split-Path $MyInvocation.MyCommand.Definition -Parent
if (-not $Here) { $Here = (Get-Location).ProviderPath }
Set-Location $Here

# Activate .venv if it exists
$act = Join-Path $Here ".venv\Scripts\Activate.ps1"
if (Test-Path $act) {
    . $act
    Success "Virtual environment activated"
}

# Find Python 3.9+
$py = $null
foreach ($c in "python","python3","python3.11","python3.10","python3.9") {
    $found = Get-Command $c -ErrorAction SilentlyContinue
    if ($found) {
        $v = & $c -c "import sys; print(sys.version_info.major*100+sys.version_info.minor)" 2>$null
        if ($v -and [int]$v -ge 309) { $py = $c; break }
    }
}
if (-not $py) { Err "Python 3.9+ not found. Download: https://www.python.org/downloads/" }
Info "Python: $(& $py --version)"
Write-Host ""

if ($Mode -eq "--cli") {
    $f = Join-Path $Here "ai_pc_checker.py"
    if (-not (Test-Path $f)) { Err "ai_pc_checker.py not found in $Here" }
    Info "Running CLI version..."
    Write-Host ""
    & $py $f
} else {
    $f = Join-Path $Here "ai_pc_web.py"
    if (-not (Test-Path $f)) { Err "ai_pc_web.py not found in $Here" }
    Info "Starting web dashboard - browser will open automatically."
    Info "Press Ctrl+C to stop."
    Write-Host ""
    & $py $f
}

