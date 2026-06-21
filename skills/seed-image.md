---
name: seed-image-bridge
description: "Image generation and recognition bridge using local ARK/Volcengine Seedream and Seed models. Use when Codex needs to generate images, recognize/analyze images, or provide image-related capabilities but the active model (e.g. DeepSeek) has no built-in image generation tool (image_gen) or vision capabilities, and no OPENAI_API_KEY is available for GPT Image API fallback. Replaces the system imagegen skill's built-in tool and CLI fallback paths with local Python scripts (seedream.py, seed.py, upload.py) that call the ARK API via OpenAI-compatible SDK. Triggers whenever any skill, workflow, or user request involves: (1) generating new images, (2) editing existing images, (3) recognizing or describing image content, (4) any task that would otherwise require GPT-4o's built-in image capabilities."
---
# Seed Image Bridge

## Overview

This skill bridges the gap when Codex runs on a model without built-in image generation/recognition (like DeepSeek) and needs to provide those capabilities. It replaces the system `imagegen` skill's two execution paths — built-in `image_gen` tool (unavailable) and GPT Image API CLI fallback (requires `OPENAI_API_KEY`) — with local Python scripts that call the ARK API (Volcengine/Seed models) via the OpenAI-compatible SDK.

## When this skill activates

This skill triggers whenever any workflow, skill, or user request involves:
- Generating a new image (concept art, UI mockup, product shot, game asset, etc.)
- Editing or transforming an existing image (style transfer, background replacement, etc.)
- Recognizing, analyzing, or describing image content
- Any task that the system `imagegen` skill would normally handle

## Scripts location

The scripts are bundled in this plugin at `scripts/`. When the plugin is installed to `~/.codex/plugins/seed-image-bridge/`, the scripts live at:

- `$CODEX_HOME/plugins/seed-image-bridge/scripts/seedream.py` — Image generation via Seedream model
- `$CODEX_HOME/plugins/seed-image-bridge/scripts/seed.py` — Image recognition via Seed vision model
- `$CODEX_HOME/plugins/seed-image-bridge/scripts/upload.py` — Upload a file to ARK API

If you keep your scripts elsewhere, set the env var `SEED_SCRIPTS_DIR` to the directory containing these three scripts, and the commands below will use that path instead.

## Environment

Required environment variable: `ARK_API_KEY`
Optional overrides (with defaults):
- `ARK_BASE_URL` (default: `https://ark.cn-beijing.volces.com/api/v3`)
- `ARK_SEEDREAM_MODEL` (default: `doubao-seedream-4-5-251128`)
- `ARK_SEED_MODEL` (default: `doubao-seed-2-0-pro-260215`)

## Workflow: Image generation

When any workflow or skill requests image generation, follow this sequence:

1. Collect the prompt and any optional reference image path.
2. Determine the scripts directory:
   - Use `$env:SEED_SCRIPTS_DIR` if set.
   - Otherwise use `$env:CODEX_HOME/plugins/seed-image-bridge/scripts/`.
3. Run the script via `shell_command`:
   ```powershell
   python <scripts-dir>/seedream.py "<prompt>" [--size 2K|4K] [--image <ref-path>]
   ```
   - Default output dir is the workspace `temp/images`
   - Default size is `2K` (maps to ~2K resolution); `4K` for higher resolution
   - The script downloads the generated image and prints the saved path.
4. After generation, show the image to the user with `view_image` on the saved path.
5. If the generated image is a project asset, move or copy it into the workspace before finishing.

Size mapping (when converting from GPT-style sizes to Seedream):
- `1024x1024`, `1536x1024`, `1024x1536` → `2K`
- `2048x2048`, `2048x1152` → `2K`
- `3840x2160`, `2160x3840` → `4K`

For image-to-image generation (when a reference image is provided), pass `--image <path-to-ref>`.

## Workflow: Image recognition

When any workflow or skill needs to analyze/recognize an image:

1. Determine the scripts directory as above.
2. First, upload the image file to get a `file_id`:
   ```powershell
   python <scripts-dir>/upload.py <path-to-image>
   ```
   Parse the `file_id` from the JSON response (e.g. `file-20260619221516-gvthw`).

3. Then, send the `file_id` to the vision model:
   ```powershell
   python <scripts-dir>/seed.py <file_id>
   ```
   The script prints the model's response about the image content.

4. Relay the recognition result back to the calling skill or user's request.

## Display conventions

- After generating an image, always display it to the user with `view_image` and/or markdown image link.
- Report the saved path so the user knows where the file is.
- For project-bound assets, ensure the final image is moved into the workspace, not left under `$CODEX_HOME/*`.

## Error handling

- If `ARK_API_KEY` is not set, the scripts print an error. Ask the user to set it as an environment variable.
- If a script fails, show the error output to the user and suggest the fix.
- If no Python scripts are found at the expected path, report the missing file and suggest checking `SEED_SCRIPTS_DIR`.
