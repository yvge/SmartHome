#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/backend"

if [ ! -x ".venv/bin/python" ] && [ ! -x ".venv/Scripts/python.exe" ]; then
  echo "[1/3] 创建 Python 虚拟环境..."
  python3 -m venv .venv
  PYTHON=".venv/bin/python"
  [ -x "$PYTHON" ] || PYTHON=".venv/Scripts/python.exe"
  echo "[2/3] 安装后端依赖..."
  "$PYTHON" -m pip install --upgrade pip -q
  "$PYTHON" -m pip install -r requirements.txt -q
else
  PYTHON=".venv/bin/python"
  [ -x "$PYTHON" ] || PYTHON=".venv/Scripts/python.exe"
  echo "[1/3] 已检测到虚拟环境"
fi

echo "[3/3] 启动智慧居 AI Agent —— http://127.0.0.1:8000/"
exec "$PYTHON" run.py
