@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] 正在创建 Python 虚拟环境...
  python -m venv .venv || goto :error
  echo [2/3] 正在安装后端依赖...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q || goto :error
) else (
  echo [1/3] 已检测到虚拟环境，跳过安装
)

echo [3/3] 启动智慧居 AI Agent...
echo   控制台:  http://127.0.0.1:8000/
echo   接口文档: http://127.0.0.1:8000/docs
echo   按 Ctrl+C 停止服务
".venv\Scripts\python.exe" run.py
goto :eof

:error
echo.
echo 启动失败，请检查 Python 3.11+ 是否已安装，或手动执行:
echo   cd backend
echo   python -m venv .venv
echo   .venv\Scripts\pip install -r requirements.txt
pause
