@echo off
setlocal
cd /d "%~dp0"

echo [STEP] Activating conda env: autofish
call conda activate autofish
if errorlevel 1 (
    echo [ERROR] Failed to activate conda env "autofish".
    echo [INFO] Please open Anaconda Prompt and try again.
    pause
    exit /b 1
)

echo [STEP] Building exe with PyInstaller...
pyinstaller --noconfirm --clean --name YH_AutoFish --onedir --exclude-module config --add-data "assets;assets" main.py
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo [STEP] Preparing dist runtime files...
if not exist "dist\YH_AutoFish" (
    echo [ERROR] dist\YH_AutoFish not found.
    pause
    exit /b 1
)

copy /Y "config.py" "dist\YH_AutoFish\config.py" >nul
if not exist "dist\YH_AutoFish\logs" mkdir "dist\YH_AutoFish\logs"

echo [DONE] Build completed:
echo        dist\YH_AutoFish\YH_AutoFish.exe
echo [DONE] Exiting build script automatically.
endlocal
