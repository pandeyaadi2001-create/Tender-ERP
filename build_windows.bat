@echo off
REM ============================================================
REM  Tender ERP — Windows Build Script
REM  Run this on a Windows machine to produce:
REM    1. dist\TenderERP\TenderERP.exe  (standalone app)
REM    2. Output\TenderERP-Setup.exe    (installer, if Inno Setup is available)
REM ============================================================

echo.
echo ====================================
echo   Tender ERP — Windows Builder
echo ====================================
echo.

REM Step 1: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Step 2: Create virtual environment if needed
if not exist ".venv" (
    echo [1/5] Creating virtual environment...
    python -m venv .venv
)

REM Step 3: Activate and install dependencies
echo [2/5] Installing dependencies...
call .venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1
pip install pyinstaller >nul 2>&1

REM Step 4: Run tests
echo [3/5] Running tests...
python -m pytest -q
if errorlevel 1 (
    echo [WARNING] Some tests failed. Continuing build anyway...
)

REM Step 5: Build with PyInstaller
echo [4/5] Building application with PyInstaller...
pyinstaller --noconfirm --clean tender_erp_win.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   BUILD SUCCESSFUL!
echo   Executable: dist\TenderERP\TenderERP.exe
echo ========================================

REM Step 6: Try to build installer (optional — needs Inno Setup)
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    echo.
    echo [5/5] Building Windows installer with Inno Setup...
    %ISCC% installer.iss
    if errorlevel 1 (
        echo [WARNING] Inno Setup build failed. The standalone .exe is still available.
    ) else (
        echo.
        echo ========================================
        echo   INSTALLER CREATED!
        echo   Installer: Output\TenderERP-Setup.exe
        echo ========================================
    )
) else (
    echo.
    echo [SKIP] Inno Setup not found. To create an installer:
    echo   1. Download Inno Setup from https://jrsoftware.org/isinfo.php
    echo   2. Install it
    echo   3. Re-run this script, or manually run:
    echo      "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
    echo.
    echo You can still distribute the folder: dist\TenderERP\
    echo Or zip it: dist\TenderERP.zip
)

echo.
echo Creating distributable ZIP...
powershell -Command "Compress-Archive -Path 'dist\TenderERP\*' -DestinationPath 'dist\TenderERP-Windows.zip' -Force"
echo   ZIP: dist\TenderERP-Windows.zip
echo.

pause
