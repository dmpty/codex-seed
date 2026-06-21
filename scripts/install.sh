#!/usr/bin/env bash
set -euo pipefail

# Install Seed Image Bridge for Codex
# Usage: ./install.sh [--skip-marketplace]

SKIP_MARKETPLACE=false
for arg in "$@"; do
  [ "$arg" = "--skip-marketplace" ] && SKIP_MARKETPLACE=true
done

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing Seed Image Bridge..."
echo "  Codex home: $CODEX_HOME"

# --- Step 1: Plugin ---
PLUGIN_DIR="$CODEX_HOME/plugins/seed-image-bridge"
echo "  Plugin → $PLUGIN_DIR"
rm -rf "$PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR/.codex-plugin" "$PLUGIN_DIR/skills" "$PLUGIN_DIR/scripts"
cp "$REPO_ROOT/.codex-plugin/plugin.json" "$PLUGIN_DIR/.codex-plugin/plugin.json"
cp "$REPO_ROOT/skills/seed-image.md" "$PLUGIN_DIR/skills/seed-image.md"
cp "$REPO_ROOT/scripts/seedream.py" "$PLUGIN_DIR/scripts/seedream.py"
cp "$REPO_ROOT/scripts/seed.py" "$PLUGIN_DIR/scripts/seed.py"
cp "$REPO_ROOT/scripts/upload.py" "$PLUGIN_DIR/scripts/upload.py"
chmod +x "$PLUGIN_DIR/scripts/"*.py
echo "  ✓ Plugin installed"

# --- Step 2: Standalone skill ---
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

# --- Step 3: Marketplace ---
if [ "$SKIP_MARKETPLACE" = false ]; then
  MARKETPLACE_DIR="$HOME/.agents/plugins"
  MARKETPLACE_FILE="$MARKETPLACE_DIR/marketplace.json"
  mkdir -p "$MARKETPLACE_DIR"
  PLUGIN_PATH="$(echo "$PLUGIN_DIR" | sed "s|$HOME|~|")"

  ENTRY=$(cat << JSON
  {
    "name": "seed-image-bridge",
    "source": { "source": "local", "path": "$PLUGIN_DIR" },
    "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
    "category": "Productivity"
  }
JSON
)

  if [ -f "$MARKETPLACE_FILE" ]; then
    # Remove existing entry and re-add
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

echo ""
echo "Installation complete!"
echo "Please restart Codex (close and reopen the app) for changes to take effect."
echo ""
echo "Don't forget to set your ARK_API_KEY:"
echo '  export ARK_API_KEY="your-key-here"'
