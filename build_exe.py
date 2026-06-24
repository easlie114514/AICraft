"""AICraft 一键构建脚本 — 编译前端 → PyInstaller打包 → 创建发布ZIP"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(ROOT, "frontend")
DIST_EXE = os.path.join(ROOT, "dist", "AICraft.exe")
RELEASE_DIR = os.path.join(ROOT, "release", "AICraft")
RELEASE_ZIP = os.path.join(ROOT, "release", "AICraft.zip")
SPEC_FILE = os.path.join(ROOT, "aicraft.spec")


def run(cmd, cwd=None, desc=None):
    """运行命令并打印输出"""
    label = desc or cmd
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, cwd=cwd or ROOT,
                            capture_output=False, text=True)
    if result.returncode != 0:
        print(f"\n[ERROR] 步骤失败: {label}")
        sys.exit(result.returncode)
    print(f"[OK] 完成")


def main():
    print("=" * 60)
    print("  AICraft — 构建 & 打包脚本")
    print("=" * 60)

    # ── Step 1: 构建前端 ──
    print("\n[1/4] 构建前端 (npm run build)...")
    if not os.path.exists(os.path.join(FRONTEND_DIR, "node_modules")):
        run("npm install", cwd=FRONTEND_DIR, desc="安装前端依赖")
    run("npm run build", cwd=FRONTEND_DIR, desc="构建前端")

    index_html = os.path.join(FRONTEND_DIR, "dist", "index.html")
    if not os.path.exists(index_html):
        print(f"[ERROR] 前端构建产物不存在: {index_html}")
        sys.exit(1)
    print("[OK] 前端构建完成")

    # ── Step 2: PyInstaller 打包 ──
    print("\n[2/4] PyInstaller 打包 (可能需要几分钟)...")
    run(f'pyinstaller --clean "{SPEC_FILE}"', desc="PyInstaller 打包")

    if not os.path.exists(DIST_EXE):
        print(f"[ERROR] exe 文件未生成: {DIST_EXE}")
        sys.exit(1)
    size_mb = os.path.getsize(DIST_EXE) / (1024 * 1024)
    print(f"[OK] PyInstaller 打包完成 → {DIST_EXE} ({size_mb:.1f} MB)")

    # ── Step 3: 创建发布目录 ──
    print("\n[3/4] 创建发布目录...")
    if os.path.exists(RELEASE_DIR):
        shutil.rmtree(RELEASE_DIR)

    # 目录列表
    dirs = [
        "config/profiles",
        "config/defaults",
        "models",
        "roles",
        "skills",
        "mcp",
        "rag",
        "memory/conversations",
        "memory/project-notes",
        "chroma_db",
        "workspace",
    ]
    for d in dirs:
        os.makedirs(os.path.join(RELEASE_DIR, d), exist_ok=True)

    # 复制 exe
    shutil.copy2(DIST_EXE, os.path.join(RELEASE_DIR, "AICraft.exe"))
    print("[OK] 已复制 AICraft.exe")

    # 复制配置文件
    for f in ["config/app.json"]:
        src = os.path.join(ROOT, f)
        dst = os.path.join(RELEASE_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    # 复制出厂默认配置
    defaults_src = os.path.join(ROOT, "config", "defaults")
    defaults_dst = os.path.join(RELEASE_DIR, "config", "defaults")
    if os.path.exists(defaults_src):
        for f in os.listdir(defaults_src):
            src_path = os.path.join(defaults_src, f)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, os.path.join(defaults_dst, f))

    # 复制 README
    readme_src = os.path.join(ROOT, "RELEASE_README.md")
    if os.path.exists(readme_src):
        shutil.copy2(readme_src, os.path.join(RELEASE_DIR, "README.md"))

    print("[OK] 发布目录已创建")

    # ── Step 4: 创建 ZIP ──
    print("\n[4/4] 创建 ZIP 压缩包...")
    if os.path.exists(RELEASE_ZIP):
        os.remove(RELEASE_ZIP)

    # 压缩 release/AICraft 目录本身，使 ZIP 内部保留 AICraft/ 父目录
    # 用户解压后始终得到一个整洁的 AICraft/ 文件夹，不会散落文件
    ps_cmd = (
        f"Compress-Archive -Path '{RELEASE_DIR}' "
        f"-DestinationPath '{RELEASE_ZIP}' -Force"
    )
    result = subprocess.run(
        ["powershell", "-Command", ps_cmd],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[WARN] ZIP 创建失败: {result.stderr}")
        print(f"[INFO] 发布目录仍可用: {RELEASE_DIR}")
    else:
        zip_size_mb = os.path.getsize(RELEASE_ZIP) / (1024 * 1024)
        print(f"[OK] ZIP 已创建 → {RELEASE_ZIP} ({zip_size_mb:.1f} MB)")

    # ── 完成 ──
    print()
    print("=" * 60)
    print("  构建完成！")
    print()
    print(f"  发布文件夹: {RELEASE_DIR}")
    print(f"  ZIP 压缩包: {RELEASE_ZIP}")
    print()
    print("  用户使用方式:")
    print("    1. 解压 AICraft.zip")
    print("    2. 双击 AICraft.exe")
    print("    3. 首次启动后进入「模型」页添加 API 配置")
    print("=" * 60)


if __name__ == "__main__":
    main()
