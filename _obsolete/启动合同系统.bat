@echo off
chcp 65001 >nul
title 合同管理系统
cd /d "%~dp0"

set "PY=C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=D:\py\python3.13.1\python.exe"
if not exist "%PY%" set "PY=python"

echo ================================================
echo   合同管理系统 启动中...
echo   浏览器会自动打开 http://127.0.0.1:8765
echo   关闭本窗口即停止服务（数据已保存在 data\contracts.db）
echo ================================================
echo.

"%PY%" server.py
pause
