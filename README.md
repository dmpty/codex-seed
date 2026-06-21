# Codex Seed Image Bridge

A [Codex](https://codex.ai) plugin that bridges image generation and recognition for models without built-in image capabilities (e.g., DeepSeek) by routing requests to Volcengine ARK API using the Seedream (image generation) and Seed (image recognition) models.

## Problem

Codex's system `imagegen` skill has two execution paths:
1. **Built-in `image_gen` tool** — only available with official Codex plan + GPT-4o model
2. **CLI fallback** (`scripts/image_gen.py`) — requires `OPENAI_API_KEY`

If you use Codex with a third-party model like DeepSeek, neither path is available. This plugin provides a **third path**: local Python scripts that call Volcengine/ARK's Seedream and Seed vision models via the OpenAI-compatible SDK.

## Prerequisites

- [Codex](https://codex.ai) desktop app
- Python 3.10+
- `openai` Python package (`pip install openai`)
- `requests` Python package (`pip install requests`)
- A Volcengine ARK API key ([sign up](https://console.volcengine.com/ark/))

## Installation

### Quick install

```bash
# Clone the repo into Codex plugins directory
git clone git@github.com:dmpty/codex-seed.git "$HOME/.codex/plugins/seed-image-bridge"
```

On Windows (PowerShell):

```powershell
git clone git@github.com:dmpty/codex-seed.git "$env:USERPROFILE\.codex\plugins\seed-image-bridge"
```

### Set environment variables

```bash
export ARK_API_KEY="your-ark-api-key"           # Required
export SEED_SCRIPTS_DIR="/path/to/codex-seed/scripts"  # Optional: defaults to plugin scripts/
```

On Windows (PowerShell):

```powershell
$env:ARK_API_KEY = "your-ark-api-key"
```

For persistence, add the variable to your shell profile.

### Install Python dependencies

```bash
pip install openai requests
```

### Restart Codex

After installing the plugin, restart your Codex session so the new plugin and its skill are loaded.

## How it works

When any skill or workflow asks Codex to generate or recognize an image, the `seed-image-bridge` skill activates alongside the system `imagegen` skill. Since `imagegen`'s built-in tool and CLI fallback are unavailable in your environment, Codex follows the bridge skill's instructions instead:

```
User/Skill: "generate an image of a sunset"
    │
    ▼
Codex detects: imagegen not available, uses seed-image-bridge
    │
    ▼
shell_command: python scripts/seedream.py "a vibrant sunset over mountains" --size 2K
    │
    ▼
ARK API (Volcengine) → doubao-seedream-4-5 → image generated
    │
    ▼
view_image → display to user
```

## Usage

### Image generation

The skill handles this automatically, but you can also run the script directly:

```powershell
python scripts/seedream.py "a serene lake house in autumn" --size 2K
python scripts/seedream.py "futuristic city skyline at night" --size 4K --image reference.jpg
```

### Image recognition

```powershell
python scripts/upload.py photo.jpg           # Returns a file_id
python scripts/seed.py file-xxxxxx           # Analyzes the image
```

## Scripts reference

| Script | Purpose | API | Env vars |
|--------|---------|-----|----------|
| `scripts/seedream.py` | Image generation via Seedream | `client.images.generate` | `ARK_API_KEY`, `ARK_SEEDREAM_MODEL` |
| `scripts/seed.py` | Image recognition via Seed vision | `client.chat.completions.create` | `ARK_API_KEY`, `ARK_SEED_MODEL` |
| `scripts/upload.py` | Upload file to ARK, returns file_id | `POST /v3/files` | `ARK_API_KEY` |

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARK_API_KEY` | Yes | — | Your Volcengine ARK API key |
| `ARK_BASE_URL` | No | `https://ark.cn-beijing.volces.com/api/v3` | ARK API base URL |
| `ARK_SEEDREAM_MODEL` | No | `doubao-seedream-4-5-251128` | Seedream model ID for generation |
| `ARK_SEED_MODEL` | No | `doubao-seed-2-0-pro-260215` | Seed model ID for recognition |
| `SEED_SCRIPTS_DIR` | No | plugin's `scripts/` dir | Custom path to the scripts |

## Structure

```
codex-seed/
├── .codex-plugin/
│   └── plugin.json          # Plugin manifest
├── skills/
│   └── seed-image.md        # Bridge skill definition
├── scripts/
│   ├── seedream.py          # Image generation script
│   ├── seed.py              # Image recognition script
│   └── upload.py            # File upload helper
├── .gitignore
└── README.md
```

## License

MIT
