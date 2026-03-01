#!/usr/bin/env bash
# 启动 QQ Bot（NoneBot2 + Web 控制台）
set -e
cd "$(dirname "$0")"

# 激活虚拟环境（若存在）
if [ -d "venv" ]; then
    source venv/bin/activate
fi

pip install -q -r requirements.txt 2>/dev/null || true
echo "[QQ Bot] 启动中，监听 127.0.0.1:8080 ..."
python bot.py
