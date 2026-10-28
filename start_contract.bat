@echo off
setlocal
chcp 65001 >nul
title Contract System
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

set "PY="
if exist "C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not defined PY if exist "D:\py\python3.13.1\python.exe" set "PY=D:\py\python3.13.1\python.exe"
if not defined PY if exist "D:\py\python3.12\python.exe" set "PY=D:\py\python3.12\python.exe"
if not defined PY if exist "C:\Python313\python.exe" set "PY=C:\Python313\python.exe"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

if not defined PY goto NOPY

"%PY%" -c "import sys,sqlite3" >nul 2>&1
if errorlevel 1 goto BADPY

echo ================================================
echo   Contract System
echo   Python : %PY%
echo   URL    : http://127.0.0.1:8765
echo   Close this window to stop the server.
echo ================================================
echo.

"%PY%" server.py
set "RC=%errorlevel%"
echo.
echo Server exited, code = %RC%
pause
exit /b

:NOPY
echo [ERROR] Python not found.
echo   Tell me the full path of python.exe, or install Python 3.9+.
echo.
pause
exit /b 1

:BADPY
echo [ERROR] This Python cannot run (missing sqlite3):
echo   %PY%
echo   Try D:\py\python3.13.1\python.exe or reinstall Python.
echo.
pause
exit /b 1
