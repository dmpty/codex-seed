# export ARK_API_KEY="YOUR_API_KEY"

import argparse
import os
import sys
from openai import OpenAI

# 强制 stdout 使用 UTF-8 编码，避免中文乱码，确保工具链兼容
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Chat with an image via ARK Seed model")
    parser.add_argument(
        "file_id",
        type=str,
        help="File ID of the uploaded image (e.g. file-20260619221516-gvthw)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("Error: ARK_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("ARK_SEED_MODEL", "doubao-seed-2-0-pro-260215")
    base_url = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "file_id": args.file_id,
                        },
                    },
                    {"type": "text", "text": "这是哪里？"},
                ],
            }
        ],
    )

    print(response.choices[0])


if __name__ == "__main__":
    main()
