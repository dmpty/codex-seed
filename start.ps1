# Start Codex Image Bridge
#
# Single entry point: auto-installs the plugin if needed, then starts the
# image stripper proxy that sits between Codex and CC Switch.
#
# CC Switch must already be running (default port 15721).
#
# Automatically backs up config.toml and updates base_url to point at the
# stripper. Restore with: Copy-Item ~/.codex/config.toml.stripper-bak ~/.codex/config.toml

param(
    [int]$Port = 11435,
    [int]$CCPort = 15721
)

$ErrorActionPreference = "Stop"
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "$HOME\.codex" }

# ------------------------------
# 0. Auto-install plugin if missing
# ------------------------------
$PluginJson = "$CodexHome\plugins\seed-image-bridge\.codex-plugin\plugin.json"
if (-not (Test-Path $PluginJson)) {
    Write-Host "[install] Plugin not found, running install.ps1..." -ForegroundColor Cyan
    $installScript = "$PSScriptRoot\scripts\install.ps1"
    if (Test-Path $installScript) {
        & $installScript
    } else {
        Write-Host "ERROR: install.ps1 not found at $installScript" -ForegroundColor Red
        exit 1
    }
}

# ------------------------------
# 1. Check CC Switch is running
# ------------------------------
$ccCheckUrl = "http://127.0.0.1:$CCPort/v1/models"
try {
    $null = Invoke-WebRequest -Uri $ccCheckUrl -Method GET -TimeoutSec 5
    Write-Host "[check] CC Switch running on port $CCPort" -ForegroundColor Green
} catch {
    Write-Host "ERROR: CC Switch not reachable at $ccCheckUrl" -ForegroundColor Red
    Write-Host "  Please start CC Switch first." -ForegroundColor Yellow
    exit 1
}

# ------------------------------
# 2. Update config.toml
# ------------------------------
$configPath = "$CodexHome\config.toml"
if (-not (Test-Path $configPath)) {
    Write-Host "ERROR: config.toml not found at $configPath" -ForegroundColor Red
    exit 1
}

# Backup (only if not already backed up by us)
$backupPath = "$configPath.stripper-bak"
if (-not (Test-Path $backupPath)) {
    Copy-Item $configPath $backupPath -Force
    Write-Host "[config] Backup created: config.toml.stripper-bak" -ForegroundColor Cyan
}

$config = Get-Content $configPath -Raw
$config = $config -replace '(?m)^base_url\s*=\s*"[^"]*"', "base_url = `"http://127.0.0.1:$Port/v1`""
Set-Content -Path $configPath -Value $config -Force -Encoding utf8
Write-Host "[config] base_url → http://127.0.0.1:${Port}/v1" -ForegroundColor Green

# ------------------------------
# 3. Start stripper
# ------------------------------
Write-Host ""
Write-Host "[stripper] Starting on port $Port..." -ForegroundColor Green
Write-Host "[stripper]   Upstream:  http://127.0.0.1:${CCPort}/v1" -ForegroundColor Cyan
Write-Host "[stripper]   Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

$env:PYTHONUNBUFFERED = "1"
python "$PSScriptRoot\stripper.py" --port $Port --upstream "http://127.0.0.1:${CCPort}/v1"

# ------------------------------
# 4. Cleanup hint
# ------------------------------
Write-Host ""
Write-Host "[cleanup] To restore original config:" -ForegroundColor Yellow
Write-Host "  Copy-Item $backupPath $configPath" -ForegroundColor Cyan