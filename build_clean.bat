@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo ============================================================
echo   AICraft Clean Build Script
echo   Creates isolated venv, installs deps, builds exe
echo ============================================================

set ROOT=%~dp0
set VENV=%ROOT%.build-venv
set DIST=%ROOT%dist

echo.
echo [1/6] Creating clean virtual environment...
if exist "%VENV%" rmdir /s /q "%VENV%"
python -m venv "%VENV%"
call "%VENV%\Scripts\activate.bat"

echo.
echo [2/6] Installing dependencies (no litellm/torch/onnxruntime)...
pip install --upgrade pip -q
pip install httpx mcp chromadb langchain-text-splitters PyPDF2 python-docx anthropic watchdog pyperclip fastapi uvicorn websockets pywebview pyinstaller -q
echo    Removing onnxruntime if pulled by chromadb...
pip uninstall onnxruntime onnx -y 2>nul

echo.
echo [3/6] Building frontend...
if exist "%ROOT%frontend\dist\index.html" (
    echo   frontend/dist already exists, skipping
) else (
    cd /d "%ROOT%frontend"
    call npm install
    call npm run build
    cd /d "%ROOT%"
)

echo.
echo [4/6] Cleaning old build...
if exist "%ROOT%build" rmdir /s /q "%ROOT%build"
if exist "%DIST%" rmdir /s /q "%DIST%"

echo.
echo [5/6] PyInstaller packaging (onedir)...
pyinstaller "%ROOT%aicraft.spec" --clean --noconfirm --distpath "%DIST%" --workpath "%ROOT%build" --specpath "%ROOT%"

echo.
echo [6/6] Verifying...
if exist "%DIST%\AICraft\AICraft.exe" (
    echo.
    echo ============================================================
    echo   [OK] Build successful!
    echo   exe: %DIST%\AICraft\AICraft.exe
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo   [FAIL] Build failed - AICraft.exe not found
    echo ============================================================
)

call deactivate
pause
