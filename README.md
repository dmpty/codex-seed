# Codex Seed Image Bridge

Image generation and recognition for Codex when using models without
built-in image support (e.g. DeepSeek via CC Switch). Routes image
requests to Volcengine ARK (Seedream + Seed) through a local MCP server,
with an image stripper proxy that transparently handles pasted/uploaded
images.

## Quick Start

### 1. Start CC Switch

[CC Switch](https://github.com/farion1231/cc-switch) must be running on port
15721 before anything else.

### 2. Start the image bridge

```powershell
# Windows
.\start.ps1
```

```bash
# macOS / Linux
./start.sh
```

This auto-installs the plugin (if needed), updates `config.toml`, and
starts the image stripper proxy. Keep this terminal open.

### 3. Restart Codex

Close and reopen Codex. The plugin will register itself, the MCP server
will start, and image generation / recognition tools become available.

The stripper must be running whenever you want to paste images or use
img2img. To stop, press Ctrl+C. Codex will still work for text-to-image
without the stripper.

## How it works

```
You paste an image or type a prompt
        │
        ▼
  Codex Desktop
        │
        ▼
  Image Stripper (port 11435) ── saves pasted images, strips base64
        │
        ▼
  CC Switch (port 15721) ── routes to DeepSeek
        │
        ▼  (DeepSeek needs image gen/recognition)
  MCP Server (seed-image-bridge)
        │
        ├── generate_image ──► Seedream API (text-to-image / img2img)
        └── recognize_image ─► Seed API (image understanding)
```

| Scenario | Behaviour |
|----------|-----------|
| Text-to-image ("画一只猫") | Stripper passes through → DeepSeek → MCP `generate_image` |
| img2img (paste + "make it anime") | Stripper saves image → DeepSeek → MCP `generate_image(prompt, path)` |
| Image question (paste + "what is this?") | Stripper saves image → DeepSeek → MCP `recognize_image` |

The install and start scripts automatically handle `config.toml`:
plugin registration, MCP server registration, and environment variable
forwarding.

## Requirements

- Python 3.10+
- `pip install openai httpx mcp requests`
- [CC Switch](https://github.com/Elluifi/cc-switch) running on port 15721
- ARK API key from [Volcengine](https://console.volcengine.com/ark/)

## Environment

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARK_API_KEY` | Yes | — | Volcengine ARK API key |
| `ARK_BASE_URL` | No | `https://ark.cn-beijing.volces.com/api/v3` | ARK API base |
| `ARK_SEEDREAM_MODEL` | No | `doubao-seedream-4-5-251128` | Generation model |
| `ARK_SEED_MODEL` | No | `doubao-seed-2-0-pro-260215` | Vision model |

## Files

| File | Purpose |
|------|---------|
| `start.ps1` / `start.sh` | Entry point — auto-install + start stripper |
| `stripper.py` | Image stripper proxy |
| `scripts/mcp_server.py` | MCP server (generate_image + recognize_image) |
| `scripts/install.ps1` / `install.sh` | Plugin + skill + marketplace installer |
| `skills/seed-image.md` | Skill instructions for Codex |
| `.codex-plugin/plugin.json` | Plugin manifest |
| `.mcp.json` | MCP server config template |

## Manual install

If you prefer to install without starting the stripper:

```powershell
.\scripts\install.ps1
```

```bash
./scripts/install.sh
```

This installs the plugin, registers it in the marketplace, and configures
`config.toml`. Start the stripper separately with `python stripper.py`
when needed.
