#!/bin/bash

# ============================================
# 日志轮转脚本 - 防止日志文件无限增长
# ============================================
# 使用方式：
# 1. 手动运行: ./scripts/rotate_logs.sh
# 2. 定期运行: 添加到 crontab
#    0 3 * * * /path/to/rotate_logs.sh  # 每天凌晨3点运行
# ============================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"

# 单个日志文件大小限制（字节），超过此值则轮转
MAX_LOG_SIZE=$((10 * 1024 * 1024))  # 10MB

# 保留的旧日志文件数量
KEEP_ROTATIONS=5

rotate_log() {
    local log_file=$1
    
    if [ ! -f "$log_file" ]; then
        return
    fi
    
    local file_size=$(stat -f%z "$log_file" 2>/dev/null || echo 0)
    
    if [ "$file_size" -gt "$MAX_LOG_SIZE" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 轮转日志: $log_file ($(numfmt --to=iec-i --suffix=B $file_size 2>/dev/null || echo ${file_size}B))"
        
        # 删除最旧的日志
        if [ -f "${log_file}.${KEEP_ROTATIONS}" ]; then
            rm -f "${log_file}.${KEEP_ROTATIONS}"
        fi
        
        # 循环重命名现有备份
        for i in $(seq $((KEEP_ROTATIONS - 1)) -1 1); do
            if [ -f "${log_file}.$i" ]; then
                mv "${log_file}.$i" "${log_file}.$((i + 1))"
            fi
        done
        
        # 轮转当前日志
        mv "$log_file" "${log_file}.1"
        touch "$log_file"
        
        echo "  -> 已保存为 ${log_file}.1"
    fi
}

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始日志轮转检查..."

rotate_log "$LOG_DIR/api.log"
rotate_log "$LOG_DIR/web.log"
rotate_log "$LOG_DIR/daemon.log"
rotate_log "$LOG_DIR/monitor.log"
rotate_log "$LOG_DIR/fetch_notion_news.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 日志轮转检查完成"
