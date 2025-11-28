#!/bin/bash

# Git 数据库文件管理脚本
# 用于忽略或恢复跟踪数据库文件的变更

cd "$(dirname "$0")/.."

# 查找所有数据库文件
DB_FILES=$(find data/ -name "*.db*" -type f 2>/dev/null)

if [ -z "$DB_FILES" ]; then
    echo "⚠️  未找到数据库文件"
    exit 0
fi

case "$1" in
    "ignore"|"")
        echo "🔇 忽略数据库文件的变更..."
        for file in $DB_FILES; do
            git update-index --assume-unchanged "$file" 2>/dev/null && echo "  ✓ $file"
        done
        echo "✅ 已标记所有数据库文件为忽略变更"
        echo "💡 Git 将不再提示这些文件的修改"
        ;;
    
    "unignore"|"track")
        echo "🔊 恢复跟踪数据库文件的变更..."
        for file in $DB_FILES; do
            git update-index --no-assume-unchanged "$file" 2>/dev/null && echo "  ✓ $file"
        done
        echo "✅ 已恢复跟踪所有数据库文件"
        ;;
    
    "list")
        echo "📋 被忽略变更的文件列表："
        git ls-files -v | grep '^h' | cut -c 3-
        ;;
    
    *)
        echo "使用方法:"
        echo "  $0 [ignore|unignore|list]"
        echo ""
        echo "命令:"
        echo "  ignore (默认)  - 忽略数据库文件的变更"
        echo "  unignore       - 恢复跟踪数据库文件的变更"
        echo "  list           - 列出所有被忽略变更的文件"
        echo ""
        echo "示例:"
        echo "  $0              # 忽略数据库变更"
        echo "  $0 ignore       # 忽略数据库变更"
        echo "  $0 unignore     # 恢复跟踪"
        echo "  $0 list         # 查看列表"
        exit 1
        ;;
esac
