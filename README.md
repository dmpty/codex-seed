# Codex Seed Image Bridge

Override Codex's system `imagegen` skill with local Python scripts that use Volcengine ARK API (Seedream + Seed vision). Built for users running Codex with non-GPT models like DeepSeek that lack built-in image generation and recognition capabilities.

## Problem

Codex's system `imagegen` skill has two paths:
| Path | Requirement | Status for you |
|------|-------------|---------------|
| Built-in `image_gen` tool | Official Codex plan + GPT-4o | ❌ DeepSeek has no `image_gen` |
| CLI fallback (`scripts/image_gen.py`) | `OPENAI_API_KEY` | ❌ You use ARK, not OpenAI |

**Result:** Codex responds to image requests with "unavailable, try CLI fallback" — a dead end.

**This plugin/skill overrides `imagegen` entirely.** When Codex needs images, it runs your ARK scripts instead.

## Architecture

Two separate mechanisms ensure this is loaded in any Codex session:

```
~/.codex/
├── skills/
│   └── seed-image-bridge/          ← Standalone skill (auto-discovered)
│       ├── SKILL.md                 ← Override instructions
│       └── agents/openai.yaml       ← UI metadata
└── plugins/
    └── seed-image-bridge/           ← Plugin (marketplace-registered)
        ├── .codex-plugin/plugin.json
        ├── skills/seed-image.md
        └── scripts/
            ├── seedream.py          ← Image generation
            ├── seed.py              ← Image recognition
            └── upload.py            ← File upload helper
```

### Why both are needed

- **Standalone skill** (`~/.codex/skills/`) is auto-discovered by Codex regardless of plugin loading
- **Plugin** (`~/.codex/plugins/`) is marketplace-registered for UI visibility and management
- Both contain the same override instructions, creating redundancy so at least one path loads

## Quick install

### Windows (PowerShell)

```powershell
# Clone and install
git clone git@github.com:dmpty/codex-seed.git "$HOME\.codex\plugins\seed-image-bridge"
cd "$HOME\.codex\plugins\seed-image-bridge"
.\scripts\install.ps1

# Set your API key
$env:ARK_API_KEY = "your-ark-api-key"

# Restart Codex
```

### macOS / Linux

```bash
# Clone and install
git clone git@github.com:dmpty/codex-seed.git "$HOME/.codex/plugins/seed-image-bridge"
cd "$HOME/.codex/plugins/seed-image-bridge"
chmod +x scripts/install.sh
./scripts/install.sh

# Set your API key
export ARK_API_KEY="your-ark-api-key"

# Restart Codex
```

### Manual install

```bash
# Clone the repo anywhere
git clone git@github.com:dmpty/codex-seed.git

# Run the install script
cd codex-seed
.\scripts\install.ps1        # Windows
./scripts/install.sh          # macOS/Linux
```

This installs all three components (plugin, standalone skill, marketplace entry).

## How the override works

When any skill or workflow requests image generation:

```
User: "generate an image of a sunset"
    │
    ▼
Codex loads: imagegen (.system) + seed-image-bridge (user skill)
    │
    ├─ imagegen says: "use image_gen tool → unavailable → suggest CLI fallback"
    │
    └─ seed-image-bridge says: "OVERRIDE imagegen → use ARK scripts directly"
                            │
                            ▼
              shell_command: python scripts/seedream.py "sunset" --size 2K
                            │
                            ▼
                      ARK API → Seedream → image generated
                            │
                            ▼
                      view_image + display
```

**The key**: `seed-image-bridge`'s SKILL.md contains explicit instructions that override `imagegen` when its built-in tool is unavailable. Codex is told to **ignore** the CLI fallback suggestion and use the local scripts instead.

## Prerequisites

- [Codex](https://codex.ai) desktop app
- Python 3.10+
- A Volcengine ARK API key ([sign up](https://console.volcengine.com/ark/))

### Install Python packages

```bash
pip install openai requests
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARK_API_KEY` | Yes | — | Your Volcengine ARK API key |
| `ARK_BASE_URL` | No | `https://ark.cn-beijing.volces.com/api/v3` | ARK API base URL |
| `ARK_SEEDREAM_MODEL` | No | `doubao-seedream-4-5-251128` | Model for image generation |
| `ARK_SEED_MODEL` | No | `doubao-seed-2-0-pro-260215` | Model for image recognition |
| `SEED_SCRIPTS_DIR` | No | Plugin's `scripts/` directory | Custom path to the three scripts |

## Scripts reference

| Script | Purpose | API endpoint |
|--------|---------|-------------|
| `scripts/seedream.py` | Generate images from text prompts | `client.images.generate` |
| `scripts/seedream.py --image` | Image-to-image generation | `client.images.generate` with image input |
| `scripts/upload.py` | Upload an image, get a `file_id` | `POST /v3/files` |
| `scripts/seed.py` | Recognize/describe an uploaded image | `client.chat.completions.create` with `file_id` |

### Size mapping

| GPT convention | Seedream `--size` | Approximate resolution |
|----------------|-------------------|----------------------|
| `1024x1024`, `1536x1024`, `2048x2048` | `2K` | ~2048×2048 |
| `3840x2160`, `2160x3840` | `4K` | ~3840×2160 |

## Troubleshooting

**Q: Codex still says "image_gen tool unavailable"**
A: Restart Codex completely (close the app, reopen it). The standalone skill at `~/.codex/skills/seed-image-bridge/` is auto-discovered only on app startup.

**Q: I get "ARK_API_KEY is not set"**
A: Set the environment variable before starting Codex. On Windows: `$env:ARK_API_KEY = "..."`. Make it persistent via System Properties → Environment Variables.

**Q: Python module not found**
A: Run `pip install openai requests` in your Python environment.

## Repo structure

```
codex-seed/
├── .codex-plugin/
│   └── plugin.json              ← Plugin manifest
├── skills/
│   └── seed-image.md            ← Skill instruction (plugin + standalone)
├── scripts/
│   ├── seedream.py              ← Image generation
│   ├── seed.py                  ← Image recognition
│   ├── upload.py                ← File upload
│   ├── install.ps1              ← Windows installer
│   └── install.sh               ← macOS/Linux installer
├── .gitignore
└── README.md
```

## License

MIT
