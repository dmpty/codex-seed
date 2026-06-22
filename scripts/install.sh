#!/usr/bin/env bash
set -euo pipefail

# Install Seed Image Bridge plugin for Codex
# Usage: ./install.sh [--skip-marketplace]
#
# This script installs the plugin to Codex plugins directory and the standalone
# skill to Codex skills directory. It also registers the plugin in the personal
# marketplace for Codex UI discovery and ensures the plugin + MCP server are
# enabled in config.toml.

SKIP_MARKETPLACE=false
for arg in "$@"; do
  [ "$arg" = "--skip-marketplace" ] && SKIP_MARKETPLACE=true
done

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -d "$CODEX_HOME" ]; then
  echo "ERROR: Codex home not found: $CODEX_HOME"
  exit 1
fi

echo "Installing Seed Image Bridge..."
echo "  Codex home: $CODEX_HOME"

# --- Step 1: Install plugin ---
PLUGIN_DIR="$CODEX_HOME/plugins/seed-image-bridge"
echo "  Plugin → $PLUGIN_DIR"
rm -rf "$PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR/.codex-plugin" "$PLUGIN_DIR/skills" "$PLUGIN_DIR/scripts"

cp "$REPO_ROOT/.codex-plugin/plugin.json" "$PLUGIN_DIR/.codex-plugin/plugin.json"
cp "$REPO_ROOT/skills/seed-image.md" "$PLUGIN_DIR/skills/seed-image.md"
cp "$REPO_ROOT/scripts/mcp_server.py" "$PLUGIN_DIR/scripts/mcp_server.py"
chmod +x "$PLUGIN_DIR/scripts/"*.py

# Generate .mcp.json with resolved absolute paths (placed in .codex-plugin/ alongside plugin.json)
cat > "$PLUGIN_DIR/.codex-plugin/.mcp.json" << MCPEOF
{
  "mcpServers": {
    "seed-image-bridge": {
      "command": "python3",
      "args": ["$PLUGIN_DIR/scripts/mcp_server.py"],
      "cwd": "$PLUGIN_DIR",
      "tool_timeout_sec": 300
    }
  }
}
MCPEOF
echo "  ✓ Plugin installed"

# --- Step 2: Install standalone skill ---
SKILL_DIR="$CODEX_HOME/skills/seed-image-bridge"
echo "  Skill → $SKILL_DIR"
rm -rf "$SKILL_DIR"
mkdir -p "$SKILL_DIR/agents"
cp "$REPO_ROOT/skills/seed-image.md" "$SKILL_DIR/SKILL.md"
cat > "$SKILL_DIR/agents/openai.yaml" << 'YAML'
interface:
  display_name: "Seed Image Bridge"
  short_description: "Replace imagegen with local ARK scripts for non-GPT models"
  default_prompt: "Use $seed-image-bridge to generate or recognize images using local ARK scripts."
YAML
echo "  ✓ Standalone skill installed"

# --- Step 3: Register in marketplace ---
if [ "$SKIP_MARKETPLACE" = false ]; then
  MARKETPLACE_DIR="$HOME/.agents/plugins"
  MARKETPLACE_FILE="$MARKETPLACE_DIR/marketplace.json"
  mkdir -p "$MARKETPLACE_DIR"
  RELATIVE_PATH="$(echo "$PLUGIN_DIR" | sed "s|^$HOME|.|")"

  ENTRY=$(cat << JSON
  {
    "name": "seed-image-bridge",
    "source": { "source": "local", "path": "$RELATIVE_PATH" },
    "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
    "category": "Productivity"
  }
JSON
)

  if [ -f "$MARKETPLACE_FILE" ]; then
    python3 -c "
import json
with open('$MARKETPLACE_FILE') as f: m = json.load(f)
m['plugins'] = [p for p in m['plugins'] if p['name'] != 'seed-image-bridge']
m['plugins'].append($ENTRY)
with open('$MARKETPLACE_FILE', 'w') as f: json.dump(m, f, indent=2)
"
  else
    cat > "$MARKETPLACE_FILE" << JSON
{
  "name": "personal",
  "interface": { "displayName": "Personal" },
  "plugins": [$ENTRY]
}
JSON
  fi
  echo "  ✓ Marketplace entry created"
fi

# --- Step 4: Ensure plugin + MCP server + env vars in config.toml ---
CONFIG_TOML="$CODEX_HOME/config.toml"
if [ -f "$CONFIG_TOML" ]; then
  PLUGIN_SECTION='[plugins."seed-image-bridge@personal"]'
  MCP_SECTION='[mcp_servers.seed-image-bridge]'
  ENV_SECTION='[mcp_servers.seed-image-bridge.env]'

  # Plugin enabled
  if grep -qF "$PLUGIN_SECTION" "$CONFIG_TOML"; then
    echo "  ✓ Plugin already in config.toml"
  else
    printf '\n%s\nenabled = true\n' "$PLUGIN_SECTION" >> "$CONFIG_TOML"
    echo "  ✓ Plugin enabled in config.toml"
  fi

  # MCP server registered
  if grep -qF "$MCP_SECTION" "$CONFIG_TOML"; then
    echo "  ✓ MCP server already registered"
  else
    cat >> "$CONFIG_TOML" << MCPEOF

$MCP_SECTION
args = ["$PLUGIN_DIR/scripts/mcp_server.py"]
command = "python3"
cwd = "$PLUGIN_DIR"
tool_timeout_sec = 300
MCPEOF
    echo "  ✓ MCP server registered in config.toml"
  fi

  # MCP env vars (only add if not already present)
  if grep -qF "$ENV_SECTION" "$CONFIG_TOML"; then
    echo "  ✓ MCP env vars already configured"
  else
    ENV_BLOCK=""
    [ -n "$ARK_API_KEY" ] && ENV_BLOCK="${ENV_BLOCK}ARK_API_KEY = \"$ARK_API_KEY\"
"
    [ -n "$ARK_BASE_URL" ] && ENV_BLOCK="${ENV_BLOCK}ARK_BASE_URL = \"$ARK_BASE_URL\"
"
    [ -n "$ARK_SEEDREAM_MODEL" ] && ENV_BLOCK="${ENV_BLOCK}ARK_SEEDREAM_MODEL = \"$ARK_SEEDREAM_MODEL\"
"
    [ -n "$ARK_SEED_MODEL" ] && ENV_BLOCK="${ENV_BLOCK}ARK_SEED_MODEL = \"$ARK_SEED_MODEL\"
"
    if [ -n "$ENV_BLOCK" ]; then
      printf '\n%s\n%s' "$ENV_SECTION" "$ENV_BLOCK" >> "$CONFIG_TOML"
      echo "  ✓ MCP env vars configured"
    fi
  fi
fi

echo ""
echo "Installation complete!"
echo "Please restart Codex (close and reopen the app) for changes to take effect."
echo ""
echo "To start the image stripper:"
echo "  ./start.sh"
echo ""
echo "Don't forget to set your ARK_API_KEY:"
echo '  export ARK_API_KEY="your-key-here"'
