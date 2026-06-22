#!/usr/bin/env bash
set -euo pipefail

# Start Codex Image Bridge
#
# Single entry point: auto-installs the plugin if needed, then starts the
# image stripper proxy that sits between Codex and CC Switch.
#
# CC Switch must already be running (default port 15721).
#
# Automatically backs up config.toml and updates base_url to point at the
# stripper. Restore with: cp ~/.codex/config.toml.stripper-bak ~/.codex/config.toml

PORT="${1:-11435}"
CC_PORT="${2:-15721}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ------------------------------
# 0. Auto-install plugin if missing
# ------------------------------
PLUGIN_JSON="$CODEX_HOME/plugins/seed-image-bridge/.codex-plugin/plugin.json"
if [ ! -f "$PLUGIN_JSON" ]; then
  echo "[install] Plugin not found, running install.sh..."
  INSTALL_SCRIPT="$SCRIPT_DIR/scripts/install.sh"
  if [ -f "$INSTALL_SCRIPT" ]; then
    bash "$INSTALL_SCRIPT"
  else
    echo "ERROR: install.sh not found at $INSTALL_SCRIPT"
    exit 1
  fi
fi

# ------------------------------
# 1. Check CC Switch is running
# ------------------------------
CC_URL="http://127.0.0.1:$CC_PORT/v1/models"
if curl -s --max-time 5 "$CC_URL" > /dev/null 2>&1; then
  echo "[check] CC Switch running on port $CC_PORT"
else
  echo "ERROR: CC Switch not reachable at $CC_URL"
  echo "  Please start CC Switch first."
  exit 1
fi

# ------------------------------
# 2. Update config.toml
# ------------------------------
CONFIG_PATH="$CODEX_HOME/config.toml"
if [ ! -f "$CONFIG_PATH" ]; then
  echo "ERROR: config.toml not found at $CONFIG_PATH"
  exit 1
fi

# Backup (only if not already backed up)
BACKUP_PATH="$CONFIG_PATH.stripper-bak"
if [ ! -f "$BACKUP_PATH" ]; then
  cp "$CONFIG_PATH" "$BACKUP_PATH"
  echo "[config] Backup created: config.toml.stripper-bak"
fi

# Update base_url
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s|^base_url = .*|base_url = \"http://127.0.0.1:$PORT/v1\"|" "$CONFIG_PATH"
else
  sed -i "s|^base_url = .*|base_url = \"http://127.0.0.1:$PORT/v1\"|" "$CONFIG_PATH"
fi
echo "[config] base_url → http://127.0.0.1:${PORT}/v1"

# ------------------------------
# 3. Start stripper
# ------------------------------
echo ""
echo "[stripper] Starting on port $PORT..."
echo "[stripper]   Upstream:  http://127.0.0.1:${CC_PORT}/v1"
echo "[stripper]   Ctrl+C to stop."
echo ""

export PYTHONUNBUFFERED=1
python3 "$SCRIPT_DIR/stripper.py" --port "$PORT" --upstream "http://127.0.0.1:${CC_PORT}/v1"

# ------------------------------
# 4. Cleanup hint
# ------------------------------
echo ""
echo "[cleanup] To restore original config:"
echo "  cp $BACKUP_PATH $CONFIG_PATH"