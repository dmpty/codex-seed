#Requires -Version 5.1

<#
.SYNOPSIS
    Install Seed Image Bridge plugin for Codex
.DESCRIPTION
    This script installs the plugin to Codex plugins directory and the standalone
    skill to Codex skills directory. It also registers the plugin in the personal
    marketplace for Codex UI discovery.
.PARAMETER CodexHome
    Codex home directory. Defaults to $env:CODEX_HOME or ~/.codex.
.PARAMETER SkipMarketplace
    Skip creating the marketplace entry.
.EXAMPLE
    .\install.ps1
    .\install.ps1 -SkipMarketplace
#>

param(
    [string]$CodexHome = "",
    [switch]$SkipMarketplace
)

# Resolve Codex home
if (-not $CodexHome) {
    $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "$HOME\.codex" }
}
if (-not (Test-Path $CodexHome)) {
    Write-Error "Codex home not found: $CodexHome"
    exit 1
}

Write-Host "Installing Seed Image Bridge..." -ForegroundColor Cyan

# Get this repo root
$RepoRoot = Split-Path -Parent $PSScriptRoot

# --- Step 1: Install plugin ---
$PluginDir = "$CodexHome\plugins\seed-image-bridge"
Write-Host "  Plugin → $PluginDir" -ForegroundColor Gray

# Remove existing if any
if (Test-Path $PluginDir) {
    Remove-Item -Recurse -Force $PluginDir
}

# Create directories
New-Item -ItemType Directory -Path "$PluginDir\.codex-plugin" -Force | Out-Null
New-Item -ItemType Directory -Path "$PluginDir\skills" -Force | Out-Null
New-Item -ItemType Directory -Path "$PluginDir\scripts" -Force | Out-Null

# Copy files
Copy-Item "$RepoRoot\.codex-plugin\plugin.json" "$PluginDir\.codex-plugin\plugin.json" -Force
Copy-Item "$RepoRoot\skills\seed-image.md" "$PluginDir\skills\seed-image.md" -Force
Copy-Item "$RepoRoot\scripts\seedream.py" "$PluginDir\scripts\seedream.py" -Force
Copy-Item "$RepoRoot\scripts\seed.py" "$PluginDir\scripts\seed.py" -Force
Copy-Item "$RepoRoot\scripts\upload.py" "$PluginDir\scripts\upload.py" -Force

Write-Host "  ✓ Plugin installed" -ForegroundColor Green

# --- Step 2: Install standalone skill ---
$SkillDir = "$CodexHome\skills\seed-image-bridge"
Write-Host "  Skill → $SkillDir" -ForegroundColor Gray

if (Test-Path $SkillDir) {
    Remove-Item -Recurse -Force $SkillDir
}

New-Item -ItemType Directory -Path "$SkillDir\agents" -Force | Out-Null
Copy-Item "$RepoRoot\skills\seed-image.md" "$SkillDir\SKILL.md" -Force

# Create agents/openai.yaml (reuse plugin's interface metadata)
@"
interface:
  display_name: "Seed Image Bridge"
  short_description: "Replace imagegen with local ARK scripts for non-GPT models"
  default_prompt: "Use `$seed-image-bridge to generate or recognize images using local ARK scripts."
"@ | Set-Content -Path "$SkillDir\agents\openai.yaml" -Encoding UTF8

Write-Host "  ✓ Standalone skill installed" -ForegroundColor Green

# --- Step 3: Register in marketplace ---
if (-not $SkipMarketplace) {
    $MarketplaceDir = "$HOME\.agents\plugins"
    $MarketplaceFile = "$MarketplaceDir\marketplace.json"

    New-Item -ItemType Directory -Path $MarketplaceDir -Force | Out-Null

    $PluginPath = $PluginDir -replace '\\', '/'
    $Entry = @{
        name   = "seed-image-bridge"
        source = @{
            source = "local"
            path   = $PluginPath
        }
        policy = @{
            installation   = "AVAILABLE"
            authentication = "ON_INSTALL"
        }
        category = "Productivity"
    }

    if (Test-Path $MarketplaceFile) {
        $Existing = Get-Content $MarketplaceFile -Raw | ConvertFrom-Json
        $Existing.plugins = @($Existing.plugins | Where-Object { $_.name -ne "seed-image-bridge" })
        $Existing.plugins += $Entry
        $Existing | ConvertTo-Json -Depth 5 | Set-Content $MarketplaceFile -Encoding UTF8
    } else {
        $Marketplace = @{
            name      = "personal"
            interface = @{
                displayName = "Personal"
            }
            plugins   = @($Entry)
        }
        $Marketplace | ConvertTo-Json -Depth 5 | Set-Content $MarketplaceFile -Encoding UTF8
    }
    Write-Host "  ✓ Marketplace entry created" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "Please restart Codex (close and reopen the app) for changes to take effect." -ForegroundColor Yellow
Write-Host ""
Write-Host "Don't forget to set your ARK_API_KEY:" -ForegroundColor Cyan
Write-Host '  $env:ARK_API_KEY = "your-key-here"' -ForegroundColor Gray
