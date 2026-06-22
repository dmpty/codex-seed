#!/usr/bin/env python3
"""
MCP Server for ARK Seedream image generation.

Provides a ``generate_image`` tool that:
  - accepts a text prompt, optional reference image path, optional size
  - reads the image file **server-side** (never exposes base64 to the LLM)
  - calls the ARK Seedream API
  - saves the result and returns the local file path

Run via :file:`.mcp.json` with ``"command": "python", "args": ["scripts/mcp_server.py"]``.
"""

import json
import requests
import argparse
import base64
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from openai import OpenAI

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_FORMATS = {"bmp", "gif", "heic", "heif", "jpeg", "png", "tiff", "webp"}
SIZE_MAP = {
    "2K": "2K",
    "4K": "4K",
    "1024x1024": "2K",
    "1536x1024": "2K",
    "1024x1536": "2K",
    "2048x2048": "2K",
    "2048x1152": "2K",
    "3840x2160": "4K",
    "2160x3840": "4K",
}

mcp = FastMCP("seed-image-bridge")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _encode_image(file_path: str) -> str:
    """Read a local image and return ``data:image/…;base64,…``."""
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    if ext == "jpg":
        ext = "jpeg"
    if ext not in ALLOWED_FORMATS:
        raise ValueError(
            f"Unsupported format '.{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_FORMATS))}"
        )
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/{ext};base64,{b64}"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]


def _client():
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        raise RuntimeError("ARK_API_KEY environment variable is not set.")
    base_url = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    return OpenAI(base_url=base_url, api_key=api_key), api_key, base_url


def _upload_to_ark(api_key: str, file_path: str) -> str:
    """Upload an image file to ARK and return the ``file_id``."""
    url = "https://ark.cn-beijing.volces.com/api/v3/files"
    normalized = os.path.normpath(file_path)
    if not os.path.isfile(normalized):
        raise FileNotFoundError(f"File not found: {normalized}")
    with open(normalized, "rb") as f:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": f},
            data={"purpose": "user_data"},
        )
    resp.raise_for_status()
    return resp.json()["id"]


ARK_BASE = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
SEEDREAM_MODEL = os.environ.get("ARK_SEEDREAM_MODEL", "doubao-seedream-4-5-251128")
SEED_MODEL = os.environ.get("ARK_SEED_MODEL", "doubao-seed-2-0-pro-260215")


# ---------------------------------------------------------------------------
# Tool: generate_image
# ---------------------------------------------------------------------------

@mcp.tool(
    name="generate_image",
    description=(
        "Generate or edit an image using the ARK Seedream model. "
        "For img2img (editing/transforming an existing image): pass the reference "
        "image as image_path directly. This tool handles the reference image internally "
        "— do NOT call recognize_image first. Pre-analysis of the source image is never needed. "
        "For text-to-image: call with prompt only. "
        "Accepts a text prompt and an optional local file path to a reference "
        "image for img2img. The image file is read by this tool on the server "
        "side — no base64-encoded data enters the LLM context. "
        "Returns the absolute local path of the saved image."
    ),
)
def generate_image(
    prompt: str,
    image_path: str | None = None,
    size: str = "2K",
    output_dir: str = "temp/images",
) -> str:
    """Generate an image via ARK Seedream.

    Parameters
    ----------
    prompt : str
        Text description of the desired image.
    image_path : str | None
        Absolute or relative local path to a reference image for img2img.
        When omitted, text-to-image mode is used.
    size : str
        ``"2K"`` (1920x1080) or ``"4K"`` (3840x2160). Accepts common
        resolutions as aliases (e.g. ``"2048x2048"`` → ``"2K"``).
    output_dir : str
        Directory (relative to cwd) where the result is saved.

    Returns
    -------
    str
        Absolute path to the saved image file.
    """
    _resolved = SIZE_MAP.get(size, size)
    client, api_key, base_url = _client()

    kwargs: dict = {
        "model": SEEDREAM_MODEL,
        "prompt": prompt,
        "size": _resolved,
        "response_format": "url",
        "extra_body": {"watermark": False},
    }

    if image_path:
        normalized = os.path.normpath(image_path)
        if not os.path.isfile(normalized):
            raise FileNotFoundError(f"Reference image not found: {normalized}")
        kwargs["extra_body"]["image"] = _encode_image(normalized)

    try:
        resp = client.images.generate(**kwargs)
    except Exception as exc:
        raise RuntimeError(f"ARK API call failed: {exc}") from exc

    image_url = resp.data[0].url

    out = os.path.abspath(output_dir)
    os.makedirs(out, exist_ok=True)
    stem = _stamp()
    ext = os.path.splitext(urllib.parse.urlparse(image_url).path)[1] or ".jpg"
    local = os.path.join(out, f"{stem}{ext}")

    try:
        urllib.request.urlretrieve(image_url, local)
    except Exception as exc:
        raise RuntimeError(f"Failed to download image: {exc}") from exc

    return os.path.abspath(local)


# ---------------------------------------------------------------------------
# Tool: recognize_image
# ---------------------------------------------------------------------------

@mcp.tool(
    name="recognize_image",
    description=(
        "Analyze or describe an image using the ARK Seed vision model. "
        "IMPORTANT RESTRICTION: Use this tool ONLY when the user asks a direct question "
        "about image content (e.g. 'What is this?', 'Describe this', 'Read the text'). "
        "Do NOT call this tool before generate_image. Do NOT use this to 'look at' or "
        "'understand' a reference image before editing it. For editing/transforming an "
        "image, call generate_image directly — it handles the reference image internally. "
        "This tool is purely for content questions, never as a pre-step to generation. "
        "Accepts a local file path to an image — the tool uploads it to the ARK"
        "server and sends an image-understanding request to the Seed model. "
        "Returns the model's text description or analysis of the image. "
        "The image file is read on the server side — no base64 data enters the LLM context."
    ),
)
def recognize_image(
    image_path: str,
    prompt: str = "请详细描述这张图片的内容",
    model: str = SEED_MODEL,
) -> str:
    """Analyze an image using the ARK Seed vision model.

    Parameters
    ----------
    image_path : str
        Absolute or relative local path to the image file.
    prompt : str
        Question or instruction about the image (default: describe it).
    model : str
        ARK model ID (default: from ``ARK_SEED_MODEL`` env var).

    Returns
    -------
    str
        The model's text response.
    """
    client, api_key, base_url = _client()

    # Step 1: upload the image to get a file_id
    file_id = _upload_to_ark(api_key, image_path)

    # Step 2: send to the Seed model with the file_id
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"file_id": file_id}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seedream MCP Server")
    ap.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio"],
        help="MCP transport (stdio only)."
    )
    args = ap.parse_args()
    mcp.run(transport=args.transport)
