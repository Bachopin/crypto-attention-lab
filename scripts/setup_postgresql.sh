#!/bin/bash
#
# PostgreSQL + pgvector 安装和配置脚本
# 用于 macOS (Homebrew)
#
set -e

echo "============================================"
echo "PostgreSQL + pgvector 安装脚本"
echo "============================================"
echo

# 检查 Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew 未安装，请先安装 Homebrew:"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

echo "✅ Homebrew 已安装"

# Step 1: 安装 PostgreSQL
echo
echo "[1/5] 安装 PostgreSQL..."
if brew list postgresql@16 &>/dev/null; then
    echo "  PostgreSQL 16 已安装"
else
    brew install postgresql@16
fi

# Step 2: 启动 PostgreSQL 服务
echo
echo "[2/5] 启动 PostgreSQL 服务..."
brew services start postgresql@16 2>/dev/null || true
sleep 2

# 确保 psql 在 PATH 中
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

# Step 3: 安装 pgvector
echo
echo "[3/5] 安装 pgvector 扩展..."
if brew list pgvector &>/dev/null; then
    echo "  pgvector 已安装"
else
    brew install pgvector
fi

# Step 4: 创建数据库
echo
echo "[4/5] 创建数据库..."
DB_NAME="crypto_attention"

if psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "  数据库 $DB_NAME 已存在"
else
    createdb $DB_NAME
    echo "  数据库 $DB_NAME 创建成功"
fi

# Step 5: 启用 pgvector 扩展
echo
echo "[5/5] 启用 pgvector 扩展..."
psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
echo "  pgvector 扩展已启用"

# 获取连接字符串
echo
echo "============================================"
echo "安装完成!"
echo "============================================"
echo
echo "数据库连接信息:"
echo "  主机: localhost"
echo "  端口: 5432"
echo "  数据库: $DB_NAME"
echo "  用户: $(whoami)"
echo
echo "请将以下配置添加到 .env 文件:"
echo
echo "DATABASE_URL=\"postgresql://localhost/$DB_NAME\""
echo
echo "或运行:"
echo "  echo 'DATABASE_URL=\"postgresql://localhost/$DB_NAME\"' >> .env"
echo
echo "然后运行迁移:"
echo "  python scripts/migrate_to_postgresql.py"
