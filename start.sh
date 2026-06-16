#!/usr/bin/env bash
set -e

# ============================================
# Sharaku Analyze - 开发模式启动脚本
# 前端/后端代码修改后自动热加载
# ============================================

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
FRONTEND_DIR="$ROOT_DIR/frontend"
HOST="${HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-3335}"
FRONTEND_PORT="${FRONTEND_PORT:-3334}"

# 清理后台进程
cleanup() {
    echo ""
    echo "正在停止服务..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
    echo "已停止"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "=========================================="
echo "  Sharaku Analyze 开发模式"
echo "=========================================="

# ---------- Python 环境 ----------
echo ""
echo "[1/3] 配置 Python 虚拟环境..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  -> 已创建 venv: $VENV_DIR"
else
    echo "  -> venv 已存在，跳过创建"
fi

source "$VENV_DIR/bin/activate"
echo "  -> Python: $(python --version)"

# ---------- 依赖安装 ----------
echo ""
echo "[2/3] 安装依赖..."
pip install --quiet --upgrade pip
pip install --quiet -r "$ROOT_DIR/requirements.txt"
echo "  -> Python 依赖完成"

cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    npm install --silent
    echo "  -> node_modules 安装完成"
else
    echo "  -> node_modules 已存在，跳过安装"
fi

# ---------- 启动服务 ----------
cd "$ROOT_DIR"
echo ""
echo "[3/3] 启动开发服务..."
echo "=========================================="
echo "  前端 (HMR): http://localhost:$FRONTEND_PORT"
echo "  后端 (API): http://localhost:$BACKEND_PORT"
echo ""
echo "  请访问前端地址进行开发"
echo "  修改 .py 文件 -> 后端自动重载"
echo "  修改 .tsx/.css 文件 -> 前端热更新"
echo "  按 Ctrl+C 停止所有服务"
echo "=========================================="
echo ""

# 启动后端 (uvicorn --reload 监听 Python 文件变化)
python -m uvicorn app:app --host "$HOST" --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

# 启动前端 (vite dev server，HMR 热更新)
cd "$FRONTEND_DIR"
BACKEND_PORT="$BACKEND_PORT" npx vite --port "$FRONTEND_PORT" --host &
FRONTEND_PID=$!

# 等待任一进程退出
wait
