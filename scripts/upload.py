#!/usr/bin/env python3
"""Upload a file to the ARK API."""

import argparse
import os
import sys

import requests


def main():
    parser = argparse.ArgumentParser(description="Upload a file to ARK API")
    parser.add_argument(
        "file",
        type=str,
        help="Path to the file to upload",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("Error: ARK_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    file_path = args.file
    if not os.path.isfile(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    url = "https://ark.cn-beijing.volces.com/api/v3/files"

    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": f},
                data={"purpose": "user_data"},
            )
        response.raise_for_status()
        print(response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error: Upload failed: {e}", file=sys.stderr)
        if e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
