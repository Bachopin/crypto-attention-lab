#!/bin/bash

# ============================================
# 健康检查脚本 - 检查服务是否运行，异常时自动启动
# ============================================
# 使用方式：
# 1. 手动运行: ./scripts/health_check.sh
# 2. 定期运行: 添加到 crontab
#    0 */6 * * * /path/to/health_check.sh  # 每6小时检查一次
# ============================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_FILE="$PROJECT_ROOT/logs/health_check.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

# 检查服务状态
check_status() {
    "$PROJECT_ROOT/scripts/daemon.sh" status > /tmp/daemon_status.txt 2>&1
    
    # 检查关键服务是否运行
    if grep -q "后端 API:.*运行中" /tmp/daemon_status.txt && \
       grep -q "前端服务:.*运行中" /tmp/daemon_status.txt; then
        return 0  # 服务正常
    else
        return 1  # 服务异常
    fi
}

log "==================== 健康检查开始 ===================="

if check_status; then
    log "✅ 所有服务运行正常"
else
    log "⚠️ 检测到服务异常，尝试自动启动..."
    
    # 启动服务
    "$PROJECT_ROOT/scripts/daemon.sh" start >> "$LOG_FILE" 2>&1
    
    # 等待几秒后再次检查
    sleep 5
    
    if check_status; then
        log "✅ 服务已成功启动"
    else
        log "❌ 服务启动失败，请手动检查"
        # 可选：发送告警通知（邮件、钉钉等）
    fi
fi

log "==================== 健康检查完成 ====================\n"

# 清理临时文件
rm -f /tmp/daemon_status.txt
