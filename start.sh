#!/usr/bin/env bash
set -e

# ============================================
# Sharaku Analyze - 一键部署启动脚本
# ============================================

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
FRONTEND_DIR="$ROOT_DIR/frontend"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "=========================================="
echo "  Sharaku Analyze 一键部署"
echo "=========================================="

# ---------- Python 环境 ----------
echo ""
echo "[1/4] 配置 Python 虚拟环境..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  -> 已创建 venv: $VENV_DIR"
else
    echo "  -> venv 已存在，跳过创建"
fi

source "$VENV_DIR/bin/activate"
echo "  -> Python: $(python --version)"

# ---------- Python 依赖 ----------
echo ""
echo "[2/4] 安装 Python 依赖..."
pip install --quiet --upgrade pip
pip install --quiet -r "$ROOT_DIR/requirements.txt"
echo "  -> 依赖安装完成"

# ---------- 前端构建 ----------
echo ""
echo "[3/4] 构建前端..."

if ! command -v node &> /dev/null; then
    echo "  [!] 未检测到 Node.js，请先安装 Node.js >= 18"
    exit 1
fi

cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    npm install --silent
    echo "  -> node_modules 安装完成"
else
    echo "  -> node_modules 已存在，跳过安装"
fi

npx vite build
echo "  -> 前端构建完成"

# ---------- 启动服务 ----------
cd "$ROOT_DIR"
echo ""
echo "[4/4] 启动后端服务..."
echo "=========================================="
echo "  地址: http://localhost:$PORT"
echo "  按 Ctrl+C 停止"
echo "=========================================="
echo ""

exec python -m uvicorn app:app --host "$HOST" --port "$PORT" --reload
