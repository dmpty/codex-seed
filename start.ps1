# Start Codex Image Bridge
#
# Single entry point: auto-installs the plugin if needed, then starts the
# image stripper proxy that sits between Codex and CC Switch.
#
# Usage:
#   .\start.ps1                         # defaults: stripper=11435, CC=15721
#   .\start.ps1 -Port 12345             # custom stripper port
#   .\start.ps1 -CCPort 9999            # custom CC Switch port
#   .\start.ps1 -Port 8080 -CCPort 9999 # both custom
#
# CC Switch must already be running.
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
# 0.5. Ensure config.toml entries always present
# ------------------------------
$PluginDir = "$CodexHome\plugins\seed-image-bridge"
$configPath = "$CodexHome\config.toml"
$configNeedsSave = $false
$config = if (Test-Path $configPath) { Get-Content $configPath -Raw -Encoding UTF8 } else { "" }

# Plugin enabled
$pluginSection = '[plugins."seed-image-bridge@personal"]'
if ($config -notmatch [regex]::Escape($pluginSection)) {
    $config = $config.TrimEnd() + "`r`n`r`n${pluginSection}`r`nenabled = true`r`n"
    Write-Host "[config] Plugin enabled" -ForegroundColor Green
    $configNeedsSave = $true
}

# MCP server registration
$NormalizedPluginDir = $PluginDir -replace '\\', '/'
$mcpSection = '[mcp_servers.seed-image-bridge]'
if ($config -notmatch [regex]::Escape($mcpSection)) {
    $mcpBlock = @"

$mcpSection
args = ["$NormalizedPluginDir/scripts/mcp_server.py"]
command = "python"
cwd = "$NormalizedPluginDir"
tool_timeout_sec = 300

"@
    $config = $config -replace "(?m)^\[projects\.", "`r`n$mcpBlock`r`n[projects."
    if ($config -notmatch [regex]::Escape($mcpSection)) {
        $config = $config.TrimEnd() + "`r`n$mcpBlock`r`n"
    }
    Write-Host "[config] MCP server registered" -ForegroundColor Green
    $configNeedsSave = $true
}

# MCP env vars
$envSection = '[mcp_servers.seed-image-bridge.env]'
if ($config -notmatch [regex]::Escape($envSection)) {
    $envBlock = "$envSection`r`n"
    $hasEnvVars = $false
    foreach ($var in @('ARK_API_KEY', 'ARK_BASE_URL', 'ARK_SEEDREAM_MODEL', 'ARK_SEED_MODEL')) {
        $val = [Environment]::GetEnvironmentVariable($var)
        if ($val) { $envBlock += "$var = `"$val`"`r`n"; $hasEnvVars = $true }
    }
    if ($hasEnvVars) {
        $config = $config -replace '(tool_timeout_sec = 300)', "`$1`r`n`r`n$envBlock"
        Write-Host "[config] MCP env vars configured" -ForegroundColor Green
        $configNeedsSave = $true
    }
}

if ($configNeedsSave) {
    Set-Content -Path $configPath -Value $config -Encoding UTF8 -NoNewline
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
