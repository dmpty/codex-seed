#!/usr/bin/env python3
"""MCP server: wraps ARK image scripts as MCP tools for Codex.

This server exposes two tools:
  - analyze_image(file_path)  → describe image content via ARK Seed vision
  - generate_image(prompt, size, ref_path) → generate image via ARK Seedream

The MCP protocol runs over stdin/stdout (stdio transport).
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ListToolsResult,
    CallToolResult,
)


# Locate sibling scripts.
SCRIPTS_DIR = Path(__file__).resolve().parent
UPLOAD_PY = SCRIPTS_DIR / "upload.py"
SEED_PY = SCRIPTS_DIR / "seed.py"
SEEDREAM_PY = SCRIPTS_DIR / "seedream.py"

server = Server("seed-image-bridge")


def _env() -> dict:
    """Return environment with ARK keys forwarded."""
    return {k: v for k, v in os.environ.items() if k.startswith("ARK_")}


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze_image",
            description="Analyze/recognize an image file using ARK Seed vision model. Returns a text description of the image content. The image file must exist on local disk.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the image file on disk"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="generate_image",
            description="Generate an image from a text prompt using ARK Seedream model. Saves the image to temp/images/ and returns the saved file path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Text prompt for image generation"
                    },
                    "size": {
                        "type": "string",
                        "enum": ["2K", "4K"],
                        "description": "Output image size. 2K (~2048x2048) or 4K (~3840x2160)"
                    },
                    "ref_path": {
                        "type": "string",
                        "description": "Optional path to a reference image for image-to-image generation"
                    }
                },
                "required": ["prompt"]
            }
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "analyze_image":
        return await _analyze_image(arguments)
    elif name == "generate_image":
        return await _generate_image(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def _analyze_image(args: dict) -> list[TextContent]:
    file_path = args.get("file_path", "").strip()
    if not file_path:
        return [TextContent(type="text", text="Error: file_path is required")]
    if not os.path.isfile(file_path):
        return [TextContent(type="text", text=f"Error: file not found: {file_path}")]

    # Step 1: upload to ARK
    proc_upload = await asyncio.create_subprocess_exec(
        sys.executable, str(UPLOAD_PY), file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ}
    )
    stdout_u, stderr_u = await proc_upload.communicate()
    if proc_upload.returncode != 0:
        return [TextContent(type="text", text=f"Upload failed:\n{stderr_u.decode('utf-8', errors='replace')}")]

    # Parse file_id
    raw_u = stdout_u.decode("utf-8").strip()
    try:
        upload_data = json.loads(raw_u)
        file_id = upload_data.get("id", raw_u)
    except json.JSONDecodeError:
        file_id = raw_u

    if not file_id:
        return [TextContent(type="text", text=f"Upload returned no file_id:\n{raw_u}")]

    # Step 2: analyze via Seed vision
    proc_seed = await asyncio.create_subprocess_exec(
        sys.executable, str(SEED_PY), file_id,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ}
    )
    stdout_s, stderr_s = await proc_seed.communicate()
    if proc_seed.returncode != 0:
        return [TextContent(type="text", text=f"Analysis failed:\n{stderr_s.decode('utf-8', errors='replace')}")]

    result = stdout_s.decode("utf-8").strip()
    return [TextContent(type="text", text=result)]


async def _generate_image(args: dict) -> list[TextContent]:
    prompt = args.get("prompt", "").strip()
    if not prompt:
        return [TextContent(type="text", text="Error: prompt is required")]

    size = args.get("size", "2K")
    ref_path = args.get("ref_path", "").strip()

    cmd = [sys.executable, str(SEEDREAM_PY), prompt, "--size", size]
    if ref_path:
        cmd.extend(["--image", ref_path])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ}
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return [TextContent(type="text", text=f"Generation failed:\n{stderr.decode('utf-8', errors='replace')}")]

    result = stdout.decode("utf-8").strip()
    return [TextContent(type="text", text=result)]


async def main():
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


if __name__ == "__main__":
    asyncio.run(main())
