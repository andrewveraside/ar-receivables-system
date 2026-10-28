@echo off
setlocal
chcp 65001 >nul
title Update Dashboard
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

set "PY="
if exist "C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not defined PY if exist "D:\py\python3.13.1\python.exe" set "PY=D:\py\python3.13.1\python.exe"
if not defined PY if exist "D:\py\python3.12\python.exe" set "PY=D:\py\python3.12\python.exe"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

if not defined PY goto NOPY
"%PY%" -c "import sys" >nul 2>&1
if errorlevel 1 goto BADPY

"%PY%" update_dashboard.py
echo.
echo Done. Open the dashboard html in this folder.
echo.
pause
exit /b

:NOPY
echo [ERROR] Python not found.
pause
exit /b 1

:BADPY
echo [ERROR] This Python cannot run: %PY%
pause
exit /b 1
