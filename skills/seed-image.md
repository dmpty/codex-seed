---
name: seed-image-bridge
description: "Generates images using ARK Seedream model when the active model (DeepSeek) has no built-in image_gen tool. Use THIS skill INSTEAD OF the system imagegen skill. Overrides imagegen's two unavailable paths (built-in tool and CLI fallback requiring OPENAI_API_KEY) with a local Python script that calls ARK API via OpenAI-compatible SDK. Triggers on ANY image generation request."
---
# Seed Image Bridge — Image generation only

## What this does

The system `imagegen` skill has two paths, both unavailable in this environment:
1. **Built-in `image_gen` tool** → requires GPT-4o model
2. **CLI fallback** (`scripts/image_gen.py`) → requires `OPENAI_API_KEY`

This skill overrides `imagegen` and routes generation requests to `seedream.py`, which calls Volcengine ARK's Seedream model.

## Script location

| Path | Description |
|------|-------------|
| `<scripts-dir>/seedream.py` | Image generation via ARK Seedream (`client.images.generate`) |

The scripts directory is resolved in this order:
1. `$env:SEED_SCRIPTS_DIR` if set
2. `$CODEX_HOME/plugins/seed-image-bridge/scripts/` (plugin-installed)
3. Workspace root

## Environment

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARK_API_KEY` | Yes | — | Volcengine ARK API key |
| `ARK_BASE_URL` | No | `https://ark.cn-beijing.volces.com/api/v3` | ARK API base URL |
| `ARK_SEEDREAM_MODEL` | No | `doubao-seedream-4-5-251128` | Seedream model |

## Workflow

When any skill or request asks for image generation:

**1 — Resolve `<scripts-dir>`** (see above).

**2 — Run `seedream.py` via `shell_command`:**

```
python <scripts-dir>/seedream.py "<prompt>" [--size 2K|4K] [--image <ref-path>]
```

The script outputs the saved image path.

**3 — Display the result** with a markdown image link:

```markdown
![generated](<saved-path>)
```

Size mapping:
- `1024x1024` / `1536x1024` / `1024x1536` / `2048x2048` / `2048x1152` → `2K`
- `3840x2160` / `2160x3840` → `4K`

## Sandbox

The script needs network access to `ark.cn-beijing.volces.com`. Always use:

| Parameter | Value |
|-----------|-------|
| `sandbox_permissions` | `"require_escalated"` |
| `justification` | `"Need network to call ARK API for image generation"` |
| `prefix_rule` | `["python", "<resolved-absolute-path>/seedream.py"]` |

Do not attempt to run inside the sandbox first — it will fail.

## Prohibited

- Do NOT use `view_image` — it injects `image_url` into API messages and crashes DeepSeek.
- Do NOT suggest CLI fallback or `OPENAI_API_KEY`.
- Do NOT offer GPT Image models.
