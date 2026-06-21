---
name: seed-image-bridge
description: "DEFINITIVE REPLACEMENT for the system imagegen skill when the active model (DeepSeek, etc.) has no built-in image_gen tool and no OPENAI_API_KEY is configured. Use THIS skill INSTEAD OF the system imagegen skill whenever Codex needs to: (1) generate a new image, (2) edit an existing image, (3) recognize/describe image content, (4) create game/assets/UI mockups/concept art. This skill OVERRIDES imagegen because its two default paths (built-in tool and CLI fallback with OPENAI_API_KEY) are both unavailable in this environment. When this skill is loaded alongside imagegen and imagegen`s built-in tool fails, DO NOT follow imagegen`s instructions — follow this skill`s instructions instead. Triggers on ANY image-related request."
---
# Seed Image Bridge — OVERRIDES `imagegen`

## CRITICAL: This skill replaces the system `imagegen` skill

The system `imagegen` skill has two execution paths:
1. **Built-in `image_gen` tool** → NOT AVAILABLE with this model (DeepSeek)
2. **CLI fallback** (`scripts/image_gen.py`) → NOT AVAILABLE (no `OPENAI_API_KEY`)

**When this `seed-image-bridge` skill is loaded, it OVERRIDES `imagegen` completely.**

## 🔴 ARCHITECTURAL LIMITATION: Codex runtime injects `image_url`

The active model (DeepSeek series) does **NOT** support `image_url` content type in chat completions.
Codex's **runtime layer** automatically serializes any image loaded via `view_image` or user file
uploads or even image paths mentioned in messages into `type: "image_url"` in the API request body.
When this hits DeepSeek's API, it fails with:

```
unknown variant `image_url`, expected `text`
```

**You cannot prevent this via SKILL.md instructions alone.** The only way to avoid the error is to
use **MCP tools** (Model Context Protocol). MCP tools pass file paths as JSON arguments in tool
calls — the image data never enters the chat message context, so the runtime never serializes it.

## 🟢 SOLUTION: Use MCP tools for ALL image operations

This plugin registers an MCP server (`seed-image-bridge`) with two tools. **Always use these tools
instead of `shell_command` or `view_image` or direct vision.**

| MCP Tool | What it does | Returns |
|----------|-------------|---------|
| `analyze_image(file_path)` | Uploads to ARK, calls Seed vision model | Text description of image content |
| `generate_image(prompt, size, ref_path)` | Runs Seedream, saves to temp/images/ | Path to saved image file |

The MCP server runs as a separate process — file paths are passed as JSON arguments, never
appearing in the chat message text. This completely bypasses the runtime's `image_url`
serialization.

## Mandatory workflow: Image recognition

When ANY skill, workflow, or user request asks to recognize/describe/analyze an image:

**STEP 1 — Ask the user for the image file path on disk.**
If the user uploaded an image to the chat, you cannot see it. Ask for the path.

**STEP 2 — Call the MCP tool:**

```
analyze_image(file_path="E:/path/to/image.jpg")
```

**STEP 3 —** Relay the ARK vision model's response verbatim to the user.

**DO NOT** try to analyze the image yourself via the model's vision — it will crash the API.
**DO NOT** use `view_image` — it triggers `image_url` serialization.
**DO NOT** mention the file path in your response text — keep it only as the tool argument.

## Mandatory workflow: Image generation

When ANY skill, workflow, or user request asks to generate an image:

**STEP 1 — Call the MCP tool:**

```
generate_image(prompt="a girl in JK uniform", size="2K")
```

**STEP 2 —** The tool returns the saved file path.

**STEP 3 — Display using markdown image link (NOT `view_image`):**

```markdown
![generated image](<path>)
```

**STEP 4 —** If the image is a project asset, move/copy it into the workspace.

**DO NOT** use `view_image` — it triggers `image_url` serialization and crashes the next API call.

## If the MCP tools are unavailable

If the MCP server is not loaded (e.g. plugin not installed), fall back to `shell_command`:

**Image generation (fallback):**
```powershell
python <scripts-dir>/seedream.py "<prompt>" --size 2K
```

**Image recognition (fallback):**
```powershell
python <scripts-dir>/upload.py <path>
python <scripts-dir>/seed.py <file_id>
```

When using `shell_command`, always use `sandbox_permissions: "require_escalated"` and a `prefix_rule`.
**Never** use `view_image`.

## Environment

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARK_API_KEY` | Yes | — | Volcengine ARK API key |
| `ARK_BASE_URL` | No | `https://ark.cn-beijing.volces.com/api/v3` | ARK API base URL |
| `ARK_SEEDREAM_MODEL` | No | `doubao-seedream-4-5-251128` | Seedream model for generation |
| `ARK_SEED_MODEL` | No | `doubao-seed-2-0-pro-260215` | Seed model for recognition |

## Error handling

- `ARK_API_KEY` not set → tell the user to set it.
- MCP tool returns error → show the error output.
- MCP server not available → fall back to `shell_command` (see above).
- Python module missing → `pip install openai requests mcp`.
