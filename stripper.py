#!/usr/bin/env python3
"""
Minimal image-stripping proxy — sits between Codex and CC Switch.

Does exactly ONE thing: finds ``input_image`` blocks with base64 data URIs
in the request body, saves the images to disk, and replaces them with text
file paths.  Everything else passes through to CC Switch unchanged.

Architecture::

    Codex ──► stripper :11435 ──► CC Switch :15721 ──► DeepSeek

Start via::

    python scripts/stripper.py --port 11435 --upstream http://127.0.0.1:15721/v1
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

import httpx

# ---------------------------------------------------------------------------
# Config (overridable via CLI)
# ---------------------------------------------------------------------------

LISTEN_PORT = 11435
UPSTREAM_BASE = "http://127.0.0.1:15721/v1"

_HERE = os.path.dirname(os.path.abspath(__file__))
CLIPBOARD_DIR = os.path.join(_HERE, "temp", "clipboard")
LOG_PATH = os.path.join(_HERE, "temp", "stripper.log")


def _log(*args, ctx: str = ""):
    """Append a timestamped line to the log file (and stderr).

    *ctx* is an optional short label (e.g. conversation id prefix) inserted
    after the timestamp.
    """
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = f"[{ts}]" + (f" [{ctx}]" if ctx else "")
    msg = " ".join(str(a) for a in args)
    line = f"{prefix} {msg}"
    print(line, file=sys.stderr)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _save_data_uri(uri: str) -> tuple[str, bool]:
    """Decode a ``data:image/…;base64,…`` URI and save to CLIPBOARD_DIR.

    Returns ``(path, is_new)`` — *is_new* is True only when the file was
    actually written (first time), False when deduplicated.
    """
    m = re.match(r"data:image/(\w+);base64,(.+)", uri)
    if not m:
        raise ValueError("invalid data URI")
    ext = m.group(1)
    if ext == "jpg":
        ext = "jpeg"
    raw = base64.b64decode(m.group(2))

    h = hashlib.sha256(raw).hexdigest()[:16]
    os.makedirs(CLIPBOARD_DIR, exist_ok=True)

    # Check for existing file with same hash
    for existing in os.listdir(CLIPBOARD_DIR):
        if existing.startswith(h) and existing.endswith(f".{ext}"):
            return os.path.abspath(os.path.join(CLIPBOARD_DIR, existing)), False

    # New image — hash first so dedup matches on startswith
    stem = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(CLIPBOARD_DIR, f"{h}-{stem}.{ext}")
    with open(path, "wb") as f:
        f.write(raw)
    _log(f"[stripper] saved -> {os.path.basename(path)}")
    return os.path.abspath(path), True


def _extract_img_url(block: dict) -> str | None:
    """Pull the URL string from an ``input_image`` content block."""
    raw = block.get("image_url", "")
    if isinstance(raw, dict):
        return raw.get("url", "")
    return raw if isinstance(raw, str) else None


def clean_images(body: dict) -> dict:
    """Recursively strip ALL ``data:image/…;base64,…`` URIs from anywhere in the body."""
    return _strip_recursive(body)


def _strip_recursive(obj):
    """Walk JSON tree: replace any base64 data-URI string with a file path."""
    if isinstance(obj, dict):
        # Special case: input_image block → turn into input_text
        if obj.get("type") == "input_image":
            url = _extract_img_url(obj)
            if url and url.startswith("data:image"):
                try:
                    path, is_new = _save_data_uri(url)
                    if is_new:
                        _log(f"[stripper] new image -> {path}")
                    return {"type": "input_text",
                            "text": f"[参考图片已保存到: {path}]"}
                except Exception as exc:
                    _log(f"[stripper] WARNING: save failed: {exc}")
            return obj
        return {k: _strip_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_strip_recursive(v) for v in obj]
    elif isinstance(obj, str) and "data:image/" in obj and ";base64," in obj[:200]:
        # Any string field containing a base64 data URI — save and replace
        try:
            path, is_new = _save_data_uri(obj)
            if is_new:
                _log(f"[stripper] new data URI -> {path}")
            return f"[图片已保存到: {path}]"
        except Exception:
            return obj
    else:
        return obj


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

_HOP_BY_HOP = {
    "host", "connection", "proxy-connection", "keep-alive",
    "transfer-encoding", "te", "trailer", "upgrade",
    "proxy-authorization", "proxy-authenticate",
}

_UPSTREAM = UPSTREAM_BASE  # mutable global, set by main()


class Handler(BaseHTTPRequestHandler):

    def _upstream_url(self) -> str:
        """Build full upstream URL, avoiding double ``/v1`` prefix."""
        path = self.path
        # _UPSTREAM already ends with /v1, strip from path if present
        if path.startswith("/v1/"):
            path = path[3:]
        elif path.startswith("/v1") and len(path) == 3:
            path = "/"
        return f"{_UPSTREAM}{path}"

    def _filter_headers(self) -> dict:
        return {
            k: v for k, v in self.headers.items()
            if k.lower() not in _HOP_BY_HOP
        }

    def _relay_response(self, r: httpx.Response):
        """Send upstream status + headers, then stream the body chunks."""
        resp_headers = [
            (k, v) for k, v in r.headers.items()
            if k.lower() not in _HOP_BY_HOP and k.lower() != "content-length"
        ]
        self.send_response(r.status_code)
        for k, v in resp_headers:
            self.send_header(k, v)
        self.end_headers()
        try:
            for chunk in r.iter_bytes(65536):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _error(self, code: int, msg: str):
        data = json.dumps({"error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- HTTP methods -----------------------------------------------------

    def do_GET(self):
        """Forward model discovery etc. to CC Switch."""
        try:
            with httpx.Client() as client:
                r = client.get(
                    self._upstream_url(),
                    headers=self._filter_headers(),
                    timeout=30,
                )
                self._relay_response(r)
        except httpx.RequestError as exc:
            _log(f"[stripper] upstream GET error: {exc}")
            self._error(502, f"CC Switch unreachable: {exc}")

    def do_POST(self):
        """Strip images from request, then forward to CC Switch."""
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b""

        # Try to parse JSON and strip images
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._forward_raw(raw)
            return

        # Extract a short conversation identifier for log context
        cid = (body.get("conversation_id", "")
               or body.get("prompt_cache_key", "")
               or body.get("previous_response_id", ""))
        self._ctx = cid[:8] if cid else ""

        body = clean_images(body)
        modified = json.dumps(body).encode("utf-8")

        fwd_headers = self._filter_headers()
        # Body changed → original Content-Length is wrong; let httpx compute it
        fwd_headers = {k: v for k, v in fwd_headers.items()
                       if k.lower() != "content-length"}
        fwd_headers["content-type"] = "application/json"

        try:
            with httpx.Client() as client:
                with client.stream(
                    "POST",
                    self._upstream_url(),
                    content=modified,
                    headers=fwd_headers,
                    timeout=300,
                ) as r:
                    self._relay_response(r)
        except httpx.RequestError as exc:
            _log(f"[stripper] upstream POST error: {exc}")
            self._error(502, f"CC Switch unreachable: {exc}")

    def _forward_raw(self, raw: bytes):
        """Forward a non-JSON body unchanged (fallback)."""
        fwd_headers = self._filter_headers()
        try:
            with httpx.Client() as client:
                r = client.post(
                    self._upstream_url(),
                    content=raw,
                    headers=fwd_headers,
                    timeout=300,
                )
                self._relay_response(r)
        except httpx.RequestError as exc:
            _log(f"[stripper] upstream raw error: {exc}")
            self._error(502, f"CC Switch unreachable: {exc}")

    def log_message(self, format: str, *args):
        ctx = getattr(self, "_ctx", "")
        _log(f"{args[0]}", ctx=ctx)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _UPSTREAM

    ap = argparse.ArgumentParser(
        description="Codex Image Stripper — strips base64 images before CC Switch")
    ap.add_argument("--port", type=int, default=LISTEN_PORT)
    ap.add_argument("--upstream", type=str, default=UPSTREAM_BASE,
                    help="CC Switch base URL (default: http://127.0.0.1:15721/v1)")
    args = ap.parse_args()

    _UPSTREAM = args.upstream.rstrip("/")

    # Ensure temp/ exists and truncate log on each startup
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as lf:
        pass

    _log(f"[stripper] listening on http://127.0.0.1:{args.port}")
    _log(f"[stripper]   upstream:  {_UPSTREAM}")
    _log(f"[stripper]   clipboard: {CLIPBOARD_DIR}")
    _log(f"[stripper]   log file:  {LOG_PATH}")

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("\n[stripper] shutdown.")
        server.server_close()


if __name__ == "__main__":
    main()
