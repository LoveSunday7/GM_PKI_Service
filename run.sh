#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# GM PKI Service — 一键启动脚本
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── 颜色定义 ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── 路径 ─────────────────────────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PID_DIR="$PROJECT_DIR/.pids"
LOG_DIR="$PROJECT_DIR/.logs"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# 默认端口
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# ── 辅助函数 ─────────────────────────────────────────────────────────────────
log_info()  { echo -e "${BLUE}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $(date '+%H:%M:%S') $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date '+%H:%M:%S') $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $*"; }

# ── 清理函数 — 退出时终止子进程 ──────────────────────────────────────────────
cleanup() {
    log_info "正在停止服务..."
    if [[ -f "$BACKEND_PID_FILE" ]]; then
        local backend_pid
        backend_pid=$(cat "$BACKEND_PID_FILE")
        if kill -0 "$backend_pid" 2>/dev/null; then
            kill "$backend_pid" 2>/dev/null || true
            log_ok "后端已停止 (PID: $backend_pid)"
        fi
        rm -f "$BACKEND_PID_FILE"
    fi
    if [[ -f "$FRONTEND_PID_FILE" ]]; then
        local frontend_pid
        frontend_pid=$(cat "$FRONTEND_PID_FILE")
        if kill -0 "$frontend_pid" 2>/dev/null; then
            kill "$frontend_pid" 2>/dev/null || true
            log_ok "前端已停止 (PID: $frontend_pid)"
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi
    log_info "所有服务已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# ── 环境检查 ─────────────────────────────────────────────────────────────────
check_prerequisites() {
    log_info "检查运行环境..."

    # Python
    if ! command -v python3 &>/dev/null; then
        log_error "未找到 python3，请安装 Python ≥ 3.10"
        exit 1
    fi
    local py_ver
    py_ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log_ok "Python $py_ver"

    # Node.js
    if ! command -v node &>/dev/null; then
        log_error "未找到 node，请安装 Node.js ≥ 22.18"
        exit 1
    fi
    local node_ver
    node_ver=$(node --version)
    log_ok "Node.js $node_ver"

    # npm
    if ! command -v npm &>/dev/null; then
        log_error "未找到 npm，请安装 npm ≥ 10"
        exit 1
    fi
    log_ok "npm $(npm --version)"
}

# ── 后端启动 ─────────────────────────────────────────────────────────────────
start_backend() {
    log_info "启动后端服务..."

    mkdir -p "$LOG_DIR"

    cd "$BACKEND_DIR"

    # 创建虚拟环境（如不存在）
    if [[ ! -d ".venv" ]]; then
        log_info "创建 Python 虚拟环境..."
        python3 -m venv .venv
    fi

    # 激活虚拟环境
    source .venv/bin/activate

    # 安装依赖
    if [[ ! -f ".venv/.deps_installed" ]]; then
        log_info "安装 Python 依赖..."
        pip install -q -r requirements.txt
        touch .venv/.deps_installed
        log_ok "Python 依赖安装完成"
    fi

    # 创建 keystore 目录
    mkdir -p "$BACKEND_DIR/keystore"

    # 启动 uvicorn
    log_info "启动 FastAPI 服务 (端口: $BACKEND_PORT)..."
    nohup uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "$BACKEND_PORT" \
        --reload \
        --log-level info \
        > "$BACKEND_LOG" 2>&1 &

    local backend_pid=$!
    echo "$backend_pid" > "$BACKEND_PID_FILE"
    log_ok "后端已启动 (PID: $backend_pid)"

    cd "$PROJECT_DIR"
}

# ── 前端启动 ─────────────────────────────────────────────────────────────────
start_frontend() {
    log_info "启动前端服务..."

    cd "$FRONTEND_DIR"

    # 安装依赖
    if [[ ! -d "node_modules" ]]; then
        log_info "安装 Node.js 依赖..."
        npm install --silent
        log_ok "Node.js 依赖安装完成"
    fi

    # 启动 vite dev server
    log_info "启动 Vite 开发服务器 (端口: $FRONTEND_PORT)..."
    nohup npx vite --host 0.0.0.0 --port "$FRONTEND_PORT" \
        > "$FRONTEND_LOG" 2>&1 &

    local frontend_pid=$!
    echo "$frontend_pid" > "$FRONTEND_PID_FILE"
    log_ok "前端已启动 (PID: $frontend_pid)"

    cd "$PROJECT_DIR"
}

# ── 健康检查 ─────────────────────────────────────────────────────────────────
wait_for_backend() {
    local max_attempts=30
    local attempt=0
    log_info "等待后端就绪..."
    while (( attempt < max_attempts )); do
        if curl -s "http://localhost:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
            log_ok "后端健康检查通过"
            return 0
        fi
        sleep 1
        ((attempt++)) || true
    done
    log_warn "后端启动超时，请查看日志: $BACKEND_LOG"
    return 1
}

# ── 主流程 ───────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║          GM PKI Service — 国密PKI数字证书认证系统            ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    check_prerequisites
    echo ""

    start_backend
    start_frontend
    echo ""

    # 等待后端就绪
    wait_for_backend
    echo ""

    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                      🚀 所有服务已启动                       ║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║${NC}  前端应用:     ${BLUE}http://localhost:$FRONTEND_PORT${NC}                   ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  API 文档:     ${BLUE}http://localhost:$BACKEND_PORT/api/docs${NC}        ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  健康检查:     ${BLUE}http://localhost:$BACKEND_PORT/api/health${NC}      ${GREEN}║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║${NC}  日志目录:     ${YELLOW}$LOG_DIR${NC}                              ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  按 ${RED}Ctrl+C${NC} 停止所有服务                                  ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # 保持脚本运行，等待子进程
    wait
}

main "$@"
