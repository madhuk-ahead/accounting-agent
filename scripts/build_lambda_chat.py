#!/usr/bin/env python3
"""Build Lambda zip for WebSocket chat handler. Excludes strands and openai (provided by layers).

Uses Docker to install dependencies so pydantic_core is built for Linux x86_64 (Lambda).
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = PROJECT_ROOT / "build" / "chat"
DIST_DIR = PROJECT_ROOT / "dist"
ZIP_PATH = DIST_DIR / "chat_lambda.zip"


def main():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # Handler and core at zip root (handler = chat.lambda_handler)
    shutil.copy2(PROJECT_ROOT / "lambda" / "chat.py", BUILD_DIR / "chat.py")
    core_src = PROJECT_ROOT / "core"
    core_dst = BUILD_DIR / "core"
    shutil.copytree(core_src, core_dst, dirs_exist_ok=True)
    for d in BUILD_DIR.rglob("__pycache__"):
        shutil.rmtree(d)

    # Install deps in Docker (Linux x86_64) so pydantic_core is the correct .so for Lambda
    req = PROJECT_ROOT / "requirements-lambda.txt"
    if not req.exists():
        raise FileNotFoundError(f"Requirements not found: {req}")

    print("Installing dependencies in Docker (Python 3.11, linux/amd64)...")
    with tempfile.TemporaryDirectory(prefix="lambda_chat_build_") as temp_dir:
        temp_path = Path(temp_dir)
        deps_dir = temp_path / "deps"
        deps_dir.mkdir()
        shutil.copy2(req, temp_path / "requirements.txt")
        install_script = temp_path / "install.sh"
        install_script.write_text("""#!/bin/bash
set -e
pip install --upgrade pip
pip install -r requirements.txt -t deps --no-cache-dir
""")
        install_script.chmod(0o755)

        cmd = [
            "docker", "run", "--rm", "--platform", "linux/amd64",
            "--entrypoint", "",
            "-v", f"{temp_dir}:/work", "-w", "/work",
            "public.ecr.aws/lambda/python:3.11",
            "/bin/bash", "install.sh",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            raise RuntimeError("Docker pip install failed")

        # Copy installed packages into build dir (do not overwrite core/ or chat.py)
        for item in deps_dir.iterdir():
            dest = BUILD_DIR / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                if dest.exists():
                    dest.unlink()
                shutil.copy2(item, dest)

    # Verify pydantic_core has Linux .so (not Mac)
    so_files = list(BUILD_DIR.rglob("pydantic_core/_pydantic_core*.so"))
    if so_files:
        print(f"✓ pydantic_core: {so_files[0].name} (Linux x86_64)")
    else:
        print("⚠ pydantic_core .so not found (pydantic may still work if pure Python)", file=sys.stderr)

    for d in BUILD_DIR.rglob("__pycache__"):
        shutil.rmtree(d)
    for pattern in ["*.dist-info", "*.egg-info"]:
        for p in BUILD_DIR.rglob(pattern):
            if p.is_dir():
                shutil.rmtree(p)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    shutil.make_archive(str(ZIP_PATH.with_suffix("")), "zip", BUILD_DIR)
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
