# export ARK_API_KEY="YOUR_API_KEY"

import argparse
import base64
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from openai import OpenAI


ALLOWED_FORMATS = {"jpeg", "png", "webp", "bmp", "tiff", "gif", "heic", "heif"}


def encode_image_to_base64(file_path: str) -> str:
    """读取图片文件并返回 data:image/<format>;base64,<data> 格式的字符串。"""
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    # jpg 视为 jpeg
    if ext == "jpg":
        ext = "jpeg"

    if ext not in ALLOWED_FORMATS:
        print(
            f"Error: Unsupported image format '.{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_FORMATS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(file_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")

    return f"data:image/{ext};base64,{b64_data}"


def default_filename() -> str:
    """返回默认文件名：年-月-日-时-分-秒-毫秒"""
    now = datetime.now()
    return now.strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]


def main():
    parser = argparse.ArgumentParser(description="Generate image via ARK Seedream model")
    parser.add_argument(
        "prompt",
        type=str,
        help="Text prompt for image generation",
    )
    parser.add_argument(
        "--size",
        type=str,
        default="2K",
        choices=["2K", "4K"],
        help="Output image size (default: 2K)",
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="Path to reference image for image-to-image generation (optional)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="temp/images",
        help="Directory to save the downloaded image (default: temp/images)",
    )
    parser.add_argument(
        "--filename",
        type=str,
        default=None,
        help="Filename without extension (default: YYYY-MM-DD-HH-MM-SS-mmm)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("Error: ARK_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("ARK_SEEDREAM_MODEL", "doubao-seedream-4-5-251128")
    base_url = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    # 构建请求参数
    generate_kwargs = {
        "model": model,
        "prompt": args.prompt,
        "size": args.size,
        "response_format": "url",
        "extra_body": {"watermark": False},
    }

    # 如果传了 --image，读取并编码为 base64
    if args.image:
        if not os.path.isfile(args.image):
            print(f"Error: Image file not found: {args.image}", file=sys.stderr)
            sys.exit(1)
        generate_kwargs["extra_body"]["image"] = encode_image_to_base64(args.image)

    imagesResponse = client.images.generate(**generate_kwargs)

    image_url = imagesResponse.data[0].url
    print(f"URL: {image_url}")

    # 保存图片到本地
    os.makedirs(args.output, exist_ok=True)
    stem = args.filename if args.filename else default_filename()
    ext = os.path.splitext(urllib.parse.urlparse(image_url).path)[1] or ".jpg"
    local_path = os.path.join(args.output, f"{stem}{ext}")

    try:
        urllib.request.urlretrieve(image_url, local_path)
        print(f"Saved: {os.path.abspath(local_path)}")
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
