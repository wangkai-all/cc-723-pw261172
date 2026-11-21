#!/usr/bin/env bash
# 一键启动：生成样例 + 构建前端 + 启动 FastAPI
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r backend/requirements.txt
fi

.venv/bin/python -I scripts/generate_samples.py

(
  cd frontend
  if [ ! -d node_modules ]; then
    npm install --cache .npm-cache
  fi
  npm run build
)

exec .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
