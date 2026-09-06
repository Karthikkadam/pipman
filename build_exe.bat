@echo off
title Building PipMan Executables...
echo ===================================================
echo        PipMan (v2.4) - Build Executable Script
echo ===================================================
echo.

echo [1/3] Checking PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
)

echo.
echo [2/3] Building PipMan Folder Distribution (Recommended - Instant Launch, No DLL extraction errors)...
pyinstaller -y --noconsole --onedir --name "PipMan" --clean --noupx "pip manager.py"

echo.
echo [3/3] Building PipMan Standalone Single-File (with --noupx)...
pyinstaller -y --noconsole --onefile --noupx --clean --paths "C:\Python313\DLLs" --name "PipMan_Standalone" "pip manager.py"

echo.
echo ===================================================
echo BUILD COMPLETED!
echo.
echo 1. Recommended (Direct Launch, Zero extraction errors):
echo    dist\PipMan\PipMan.exe
echo.
echo 2. Single-file standalone:
echo    dist\PipMan_Standalone.exe
echo ===================================================
echo.
pause
