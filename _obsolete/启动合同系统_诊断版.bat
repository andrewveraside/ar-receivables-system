@echo off
chcp 65001 >nul
title 合同管理系统
cd /d "%~dp0"

echo ================================================
echo   合同管理系统 启动中...
echo ================================================
echo.

rem ---- 找 Python（按可用性依次尝试）----
set "PY="
if exist "C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not defined PY if exist "D:\py\python3.13.1\python.exe" set "PY=D:\py\python3.13.1\python.exe"
if not defined PY if exist "D:\py\python3.12\python.exe" set "PY=D:\py\python3.12\python.exe"
if not defined PY (
  for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
)
if not defined PY (
  echo [错误] 找不到 Python 解释器。
  echo   请把 python.exe 的完整路径告诉我，或安装 Python 3.9+。
  echo.
  pause
  exit /b 1
)
echo [1/3] 解释器: %PY%

rem ---- 先测解释器能不能跑 ----
"%PY%" -c "import sys;print('      Python',sys.version.split()[0])" >nul 2>&1
if errorlevel 1 (
  echo [错误] 这个 Python 跑不起来:
  echo        %PY%
  echo   常见原因：PATH 里的 python 是 Windows 应用商店占位符，或者被杀毒拦。
  echo.
  pause
  exit /b 1
)

rem ---- 依赖检查 ----
"%PY%" -c "import sqlite3" >nul 2>&1
if errorlevel 1 (
  echo [错误] 该 Python 缺少标准库 sqlite3，换一个解释器。
  pause
  exit /b 1
)
echo [2/3] 依赖检查通过

echo [3/3] 启动服务，浏览器稍后自动打开...
echo       地址: http://127.0.0.1:8765
echo       关闭本窗口即停止服务（数据已存 data\contracts.db，不会丢）
echo ================================================
echo.

"%PY%" server.py

echo.
echo 服务已退出（返回码 %errorlevel%）。
echo 如果上面有红色报错，把窗口内容截图发我。
pause
