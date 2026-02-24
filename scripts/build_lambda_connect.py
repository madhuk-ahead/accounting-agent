#!/usr/bin/env python3
"""Build Lambda zip for WebSocket connect handler."""

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = PROJECT_ROOT / "build" / "connect"
DIST_DIR = PROJECT_ROOT / "dist"
ZIP_PATH = DIST_DIR / "connect_lambda.zip"


def main():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    src = PROJECT_ROOT / "lambda" / "connect.py"
    if not src.exists():
        print(f"Missing {src}", file=sys.stderr)
        sys.exit(1)
    shutil.copy2(src, BUILD_DIR / "connect.py")
    req = PROJECT_ROOT / "requirements-lambda.txt"
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req), "-t", str(BUILD_DIR), "-q"],
        check=True,
        cwd=PROJECT_ROOT,
    )
    for d in BUILD_DIR.rglob("__pycache__"):
        shutil.rmtree(d)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    shutil.make_archive(str(ZIP_PATH.with_suffix("")), "zip", BUILD_DIR)
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
