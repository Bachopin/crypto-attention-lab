#!/bin/bash

# ============================================
# Crypto Attention Lab - 守护进程启动脚本
# ============================================
# 功能：
# 1. 后台启动后端和前端，退出终端/VSCode 后继续运行
# 2. 前端崩溃自动重启（每 30 秒检查一次）
# 3. 日志记录到 logs/ 目录
# 4. 支持 start/stop/restart/status 命令
# ============================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 检测并激活虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

API_LOG="$LOG_DIR/api.log"
WEB_LOG="$LOG_DIR/web.log"
DAEMON_LOG="$LOG_DIR/daemon.log"

API_PID_FILE="$LOG_DIR/api.pid"
WEB_PID_FILE="$LOG_DIR/web.pid"
MONITOR_PID_FILE="$LOG_DIR/monitor.pid"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$DAEMON_LOG"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$DAEMON_LOG"
}

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS:${NC} $1" | tee -a "$DAEMON_LOG"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARN:${NC} $1" | tee -a "$DAEMON_LOG"
}

# 清理占用端口的进程
kill_port() {
    local port=$1
    local name=$2
    local pid=$(lsof -ti tcp:$port 2>/dev/null)
    
    if [ -n "$pid" ]; then
        warn "检测到端口 $port 被占用 (PID: $pid)，清理中..."
        kill -9 $pid 2>/dev/null || true
        sleep 1
        success "端口 $port 已清理 ($name)"
    fi
}

# 检查进程是否运行
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# 启动后端 API
start_api() {
    if is_running "$API_PID_FILE"; then
        warn "后端 API 已在运行 (PID: $(cat $API_PID_FILE))"
        return
    fi

    # 清理端口 8000
    kill_port 8000 "后端 API"

    log "启动后端 API（生产模式，禁用热重载以降低 CPU 占用）..."
    nohup uvicorn src.api.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        > "$API_LOG" 2>&1 &
    
    echo $! > "$API_PID_FILE"
    sleep 2
    
    if is_running "$API_PID_FILE"; then
        success "后端 API 已启动 (PID: $(cat $API_PID_FILE))"
        success "访问地址: http://localhost:8000"
        success "API 文档: http://localhost:8000/docs"
    else
        error "后端 API 启动失败，查看日志: $API_LOG"
        rm -f "$API_PID_FILE"
    fi
}

# 启动前端
start_web() {
    if is_running "$WEB_PID_FILE"; then
        warn "前端服务已在运行 (PID: $(cat $WEB_PID_FILE))"
        return
    fi

    # 清理端口 3000
    kill_port 3000 "前端服务"

    log "启动前端服务..."
    cd "$PROJECT_ROOT/web"
    
    # 确保依赖已安装
    if [ ! -d "node_modules" ]; then
        log "安装前端依赖..."
        npm install
    fi
    
    nohup npm run dev > "$WEB_LOG" 2>&1 &
    echo $! > "$WEB_PID_FILE"
    cd "$PROJECT_ROOT"
    sleep 3
    
    if is_running "$WEB_PID_FILE"; then
        success "前端服务已启动 (PID: $(cat $WEB_PID_FILE))"
        success "访问地址: http://localhost:3000"
    else
        error "前端服务启动失败，查看日志: $WEB_LOG"
        rm -f "$WEB_PID_FILE"
    fi
}

# 前端监控守护进程
monitor_web() {
    log "启动前端监控守护进程..."
    
    while true; do
        sleep 30
        
        # 检查后端是否运行
        if ! is_running "$API_PID_FILE"; then
            warn "后端未运行，跳过前端检查"
            continue
        fi
        
        # 检查前端是否运行
        if ! is_running "$WEB_PID_FILE"; then
            error "检测到前端已崩溃，自动重启..."
            start_web
        fi
    done
}

# 启动监控
start_monitor() {
    if is_running "$MONITOR_PID_FILE"; then
        warn "监控进程已在运行 (PID: $(cat $MONITOR_PID_FILE))"
        return
    fi
    
    nohup bash -c "$(declare -f log warn error success is_running start_web); \
        API_PID_FILE='$API_PID_FILE'; \
        WEB_PID_FILE='$WEB_PID_FILE'; \
        WEB_LOG='$WEB_LOG'; \
        DAEMON_LOG='$DAEMON_LOG'; \
        PROJECT_ROOT='$PROJECT_ROOT'; \
        RED='$RED'; GREEN='$GREEN'; YELLOW='$YELLOW'; BLUE='$BLUE'; NC='$NC'; \
        $(declare -f monitor_web); \
        monitor_web" > "$LOG_DIR/monitor.log" 2>&1 &
    
    echo $! > "$MONITOR_PID_FILE"
    success "监控进程已启动 (PID: $(cat $MONITOR_PID_FILE))"
}

# 停止进程
stop_process() {
    local pid_file=$1
    local name=$2
    
    if is_running "$pid_file"; then
        local pid=$(cat "$pid_file")
        log "停止 $name (PID: $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 2
        
        # 强制停止
        if ps -p "$pid" > /dev/null 2>&1; then
            kill -9 "$pid" 2>/dev/null || true
        fi
        
        rm -f "$pid_file"
        success "$name 已停止"
    else
        warn "$name 未运行"
    fi
}

# 停止所有服务
stop_all() {
    log "停止所有服务..."
    stop_process "$MONITOR_PID_FILE" "监控进程"
    stop_process "$WEB_PID_FILE" "前端服务"
    stop_process "$API_PID_FILE" "后端 API"
}

# 查看状态
status() {
    echo ""
    echo "========================================="
    echo "  Crypto Attention Lab - 服务状态"
    echo "========================================="
    
    if is_running "$API_PID_FILE"; then
        echo -e "后端 API:    ${GREEN}运行中${NC} (PID: $(cat $API_PID_FILE))"
        echo "             http://localhost:8000"
    else
        echo -e "后端 API:    ${RED}未运行${NC}"
    fi
    
    if is_running "$WEB_PID_FILE"; then
        echo -e "前端服务:    ${GREEN}运行中${NC} (PID: $(cat $WEB_PID_FILE))"
        echo "             http://localhost:3000"
    else
        echo -e "前端服务:    ${RED}未运行${NC}"
    fi
    
    if is_running "$MONITOR_PID_FILE"; then
        echo -e "监控进程:    ${GREEN}运行中${NC} (PID: $(cat $MONITOR_PID_FILE))"
    else
        echo -e "监控进程:    ${RED}未运行${NC}"
    fi
    
    echo "========================================="
    echo ""
}

# 启动所有服务
start_all() {
    log "启动 Crypto Attention Lab 守护服务..."
    start_api
    sleep 3
    start_web
    sleep 2
    start_monitor
    echo ""
    status
    echo ""
    success "所有服务已启动完成！"
    success "日志目录: $LOG_DIR"
    success "即使关闭终端/VSCode，服务仍会继续运行"
    success "使用 '$0 stop' 停止所有服务"
    echo ""
}

# 重启所有服务
restart_all() {
    log "重启所有服务..."
    stop_all
    sleep 3
    start_all
}

# 查看日志
logs() {
    local service=${1:-all}
    case $service in
        api)
            tail -f "$API_LOG"
            ;;
        web)
            tail -f "$WEB_LOG"
            ;;
        monitor)
            tail -f "$LOG_DIR/monitor.log"
            ;;
        daemon)
            tail -f "$DAEMON_LOG"
            ;;
        *)
            echo "实时查看所有日志 (Ctrl+C 退出):"
            tail -f "$API_LOG" "$WEB_LOG" "$DAEMON_LOG"
            ;;
    esac
}

# 主命令
case "${1:-start}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        status
        ;;
    logs)
        logs "${2:-all}"
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs [api|web|monitor|daemon]}"
        echo ""
        echo "命令说明:"
        echo "  start   - 启动所有服务（后台运行，退出终端后继续）"
        echo "  stop    - 停止所有服务"
        echo "  restart - 重启所有服务"
        echo "  status  - 查看服务状态"
        echo "  logs    - 查看日志（可选: api, web, monitor, daemon）"
        echo ""
        exit 1
        ;;
esac
