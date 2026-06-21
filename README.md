# Codex Seed Image Bridge

Image generation for Codex when using models without built-in image support (DeepSeek etc.). Routes requests to Volcengine ARK Seedream via a local Python script.

## Quick install

```bash
git clone git@github.com:dmpty/codex-seed.git "$HOME/.codex/plugins/seed-image-bridge"
```

Set `ARK_API_KEY` environment variable, restart Codex.

## Requirements

- Python 3.10+
- `pip install openai requests`
- ARK API key from [Volcengine](https://console.volcengine.com/ark/)

## Usage

Just ask for an image — Codex generates it via Seedream:

> 生成一只橘猫趴在窗台上晒太阳的图

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `ARK_API_KEY` | *(required)* | Volcengine ARK API key |
| `ARK_BASE_URL` | `https://ark.cn-beijing.volces.com/api/v3` | ARK API base |
| `ARK_SEEDREAM_MODEL` | `doubao-seedream-4-5-251128` | Generation model |
| `SEED_SCRIPTS_DIR` | plugin `scripts/` | Custom script path |

## Files

| File | Purpose |
|------|---------|
| `scripts/seedream.py` | Image generation |
| `skills/seed-image.md` | Skill instructions |
| `.codex-plugin/plugin.json` | Plugin manifest |
