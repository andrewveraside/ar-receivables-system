@echo off
REM ============================================================
REM  AR Contract System  -  Launcher (ASCII only, do not add CJK)
REM  Project : D:\aiprojects\ (subfolder: see this file's location)
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo.
echo  ============================================
echo   AR Contract System  -  starting ...
echo  ============================================
echo.

set "PY="
if exist "%~dp0runtime\python.exe" set "PY=%~dp0runtime\python.exe"
if not defined PY if exist "D:\py\python3.13.1\python.exe" set "PY=D:\py\python3.13.1\python.exe"
if not defined PY if exist "D:\py\python3.12\python.exe"  set "PY=D:\py\python3.12\python.exe"
if not defined PY if exist "C:\Python313\python.exe"      set "PY=C:\Python313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

if not defined PY goto NOPY

"%PY%" -c "import sys,sqlite3" >nul 2>&1
if errorlevel 1 goto BADPY

echo  Python : %PY%
echo  Data   : %~dp0data\contracts.db
echo  URL    : http://127.0.0.1:8765
echo.
echo  Close this window to stop the service.
echo.

"%PY%" server.py
echo.
echo  Service stopped (exit code %errorlevel%).
pause
goto :EOF

:NOPY
echo  [ERROR] Python not found.
echo.
echo  Install Python 3.9+ from https://www.python.org/downloads/
echo  and tick "Add python.exe to PATH" during setup.
echo.
pause
goto :EOF

:BADPY
echo  [ERROR] This Python cannot run the service.
echo  Found: %PY%
echo  Required modules: sys, sqlite3
echo.
pause
goto :EOF
