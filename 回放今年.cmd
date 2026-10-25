@echo off
setlocal
cd /d "%~dp0"

set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
  where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
  echo [错误] 没有找到 Python 3，请先安装。
  pause
  exit /b 1
)

echo 正在生成回放页面...
echo.
%PYEXE% "review.py" --preset 2026
if errorlevel 1 (
  echo.
  echo [失败] 生成失败，请把上面的报错发给助手。
  pause
  exit /b 1
)
start "" "review_2026.html"
ping -n 3 127.0.0.1 >nul
exit /b 0