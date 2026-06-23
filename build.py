"""AICraft build script - frontend compile + PyInstaller package"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
FRONTEND_DIR = ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
BUILD_DIR = ROOT / "build"
OUTPUT_DIR = ROOT / "dist" / "AICraft"

def step(name: str):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}\n")

def run(cmd: str, cwd: Path | None = None):
    print(f"  > {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, env=os.environ.copy())
    if result.returncode != 0:
        print(f"\n  [FAIL] command failed (exit code {result.returncode})")
        sys.exit(1)
    return result

def main():
    step("1/4 Check environment")
    run("python --version")
    run("node --version")
    run("pip show pyinstaller >nul 2>&1 && echo PyInstaller OK")

    step("2/4 Build frontend (npm run build)")
    if DIST_DIR.exists() and (DIST_DIR / "index.html").exists():
        print("  frontend/dist already exists, skipping build")
    else:
        if not (FRONTEND_DIR / "package.json").exists():
            print(f"  [FAIL] package.json not found in {FRONTEND_DIR}")
            sys.exit(1)
        run("npm install", cwd=FRONTEND_DIR)
        run("npm run build", cwd=FRONTEND_DIR)

    if not (DIST_DIR / "index.html").exists():
        print(f"  [FAIL] frontend build failed: {DIST_DIR / 'index.html'} not found")
        sys.exit(1)
    print(f"  [OK] frontend dist ready: {DIST_DIR}")

    step("3/4 Clean old build")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
        print(f"  cleaned {BUILD_DIR}")
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
        print(f"  cleaned {OUTPUT_DIR}")

    step("4/4 PyInstaller package (onedir)")
    spec_file = ROOT / "aicraft.spec"
    run(
        f'pyinstaller "{spec_file}" '
        f'--clean --noconfirm '
        f'--distpath "{ROOT / "dist"}" '
        f'--workpath "{ROOT / "build"}" '
        f'--specpath "{ROOT}"'
    )

    # Verify
    exe_path = OUTPUT_DIR / "AICraft.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        total_bytes = sum(f.stat().st_size for f in OUTPUT_DIR.rglob("*") if f.is_file())
        total_mb = total_bytes / 1024 / 1024
        print(f"\n{'='*60}")
        print(f"  [OK] Build successful!")
        print(f"  exe: {exe_path} ({size_mb:.1f} MB)")
        print(f"  total: {OUTPUT_DIR} ({total_mb:.0f} MB)")
        print(f"  Double-click AICraft.exe to launch")
        print(f"{'='*60}")
    else:
        print(f"\n  [FAIL] Build failed: {exe_path} not found")
        sys.exit(1)

if __name__ == "__main__":
    main()
