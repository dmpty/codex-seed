---
name: seed-image-bridge
description: "Provides image generation (Seedream) and image understanding (Seed) via a local MCP server. For img2img (edit/transform an image), call generate_image with image_path directly — do NOT pre-analyze with recognize_image. Use THIS skill INSTEAD OF the system imagegen skill."
---
# Seed Image Bridge — Image Stripper + MCP


## MANDATORY: img2img = one tool, one call

When the user provides an image AND wants to edit/transform it ("改成冬天", "make it anime", "turn this into a painting", etc.):

1. Call `generate_image(prompt, image_path)` — nothing else.
2. Do NOT call `recognize_image` first. Do NOT try to "understand" or "see" the image.
3. Seedream processes the reference image internally — pre-analysis is wasted.

This is the single most important rule in this skill.

## Architecture overview

```
User pastes image or types "画一只猫"
  │
  ▼
Codex Image Stripper (port 11435)              ← 格式修正层
  ├── input_image 存在 → 保存到 temp/clipboard/，替换为文件路径
  └── 无图片 → 透传
  │
  ▼
CC Switch → DeepSeek                          ← 推理层
  │
  └── DeepSeek 需要生图/识图 → 调用 MCP 工具
      │
      ▼
  MCP Server (seed-image-bridge)              ← 图片处理层
    ├── generate_image(prompt, image_path?)   → 调用 Seedream API
    └── recognize_image(image_path, prompt)   → 上传 → 调用 Seed API
```

The Image Stripper is a transparent HTTP proxy that does ONE thing:
intercept `input_image` blocks with base64 data before they reach CC Switch,
save the images to disk, and replace them with text file paths. All other
requests pass through unchanged.

## Routing rules

**Decision tree — read this first:**

```
User request includes an image?
├── NO  → text-to-image: call generate_image(prompt) only
└── YES → what does the user want?
    ├── "What is this?" / "Describe this" / "Read this" → call recognize_image
    └── "Make it ..." / "Turn this into ..." / "Edit ..." → img2img: call generate_image(prompt, image_path) ONLY
```

**CRITICAL**: img2img does NOT need pre-analysis. Do not call `recognize_image` before `generate_image` when the user wants to edit/transform an image. Seedream handles the reference image directly.

| 场景 | 图片数据流向 | 调用方式 |
|------|-------------|---------|
| 纯文本对话 | Stripper 透传 → CC Switch → DeepSeek | 正常对话 |
| 粘贴截图 + "这是什么？" | Stripper 保存图片 → DeepSeek 看到路径 → MCP `recognize_image` | 传入路径 |
| "画一只猫"（纯文本生图） | Stripper 透传 → DeepSeek → MCP `generate_image` | 只传 prompt |
| 粘贴截图 + "改成冬天" | Stripper 保存图片 → DeepSeek 看到路径 → MCP `generate_image(prompt, path)` | 文+图 |

## MCP tools

### `generate_image(prompt, image_path?, size?)`
Generate or edit an image. When `image_path` is provided, Seedream performs img2img.
Returns the absolute path to the saved result.

### `recognize_image(image_path, prompt?)`
Analyze an image. Uploads the file to ARK and sends an image-understanding request to Seed.
Returns the model's text description.

## Display results

```markdown
![generated](<saved-path>)
```

## Starting the stripper

```powershell
# Windows — auto-installs plugin then starts the stripper
.\start.ps1
```

```bash
# macOS / Linux
./start.sh
```

The start script automatically runs the installer if the plugin is not yet installed.
It updates `config.toml` to point Codex at the stripper (`base_url = "http://127.0.0.1:11435/v1"`).
Stop with Ctrl+C, then restore config:

```powershell
# Windows
Copy-Item ~/.codex/config.toml.stripper-bak ~/.codex/config.toml
```

```bash
# macOS / Linux
cp ~/.codex/config.toml.stripper-bak ~/.codex/config.toml
```

## Environment

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARK_API_KEY` | Yes | — | Volcengine ARK API key |
| `ARK_BASE_URL` | No | `https://ark.cn-beijing.volces.com/api/v3` | ARK API base URL |
| `ARK_SEEDREAM_MODEL` | No | `doubao-seedream-4-5-251128` | Seedream model |
| `ARK_SEED_MODEL` | No | `doubao-seed-2-0-pro-260215` | Seed vision model |

## Rules

- **img2img = generate_image ONLY.** When the user provides an image plus an edit/transform prompt (e.g. "改成冬天", "make it anime style"), call `generate_image(prompt, image_path)` directly. Do NOT call `recognize_image` first. The model does not need to "see" the source image before editing it — Seedream handles the reference image internally.
- **recognize_image is ONLY for questions.** Use `recognize_image` only when the user explicitly asks a question about image content (e.g. "这是什么?", "What does this image show?", "Read the text in this image").
- **Use MCP tools** for ALL image operations. Never use `view_image`, `shell_command`, or CLI scripts.
- **Do NOT** base64-encode any image data. Pass file paths to MCP tools.
- **Do NOT** attempt to read or describe image contents from base64. If the stripper has already saved the image to `temp/clipboard/`, use that path.
- **Do NOT** suggest CLI fallback or `OPENAI_API_KEY`.
- **Do NOT** offer GPT Image models.

## Note

The MCP server is started automatically by Codex via `.mcp.json`. The Image Stripper must be started manually before launching Codex.
