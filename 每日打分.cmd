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

echo 正在取数并计算 515450 综合温度分 ...
echo.
%PYEXE% "daily_score.py" --open
set "RC=%errorlevel%"
echo.
if not "%RC%"=="0" (
  echo [失败] 生成失败，请把上面的报错发给助手。
  pause
  exit /b 1
)
echo [完成] 报告已打开，桌面同步一份 515450温度计.html
ping -n 3 127.0.0.1 >nul
exit /b 0