@echo off

set PYTHON="C:\Users\Curry\miniconda3\envs\autofish\python.exe"

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

:start
%PYTHON% main.py

pause
goto start