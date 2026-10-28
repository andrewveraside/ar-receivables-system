@echo off
chcp 65001 >nul
title 更新看板
cd /d "%~dp0"
set "PY=C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=D:\py\python3.13.1\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" 更新看板.py
echo.
pause
