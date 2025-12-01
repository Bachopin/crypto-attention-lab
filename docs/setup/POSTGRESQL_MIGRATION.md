# PostgreSQL 迁移指南

本指南帮助你将项目从 SQLite 迁移到 PostgreSQL + pgvector。

## 为什么迁移？

1. **性能提升**: PostgreSQL 在并发读写和大数据量场景下性能更好
2. **pgvector 支持**: 启用向量相似度搜索，用于"相似历史状态"检索
3. **生产就绪**: PostgreSQL 是生产环境的标准选择

## 快速开始 (macOS)

### 一键安装

```bash
./scripts/setup_postgresql.sh
```

这个脚本会自动：
- 安装 PostgreSQL 16
- 启动 PostgreSQL 服务
- 安装 pgvector 扩展
- 创建 `crypto_attention` 数据库

### 配置环境变量

安装完成后，将连接字符串添加到 `.env` 文件：

```bash
echo 'DATABASE_URL="postgresql://localhost/crypto_attention"' >> .env
```

### 运行迁移

```bash
# 加载环境变量
source .env

# 运行迁移脚本（会自动回填预计算字段）
python scripts/migrate_to_postgresql.py
```

## 手动安装 (其他平台)

### Ubuntu/Debian

```bash
# 安装 PostgreSQL
sudo apt install postgresql-16 postgresql-16-pgvector

# 启动服务
sudo systemctl start postgresql

# 创建数据库
sudo -u postgres createdb crypto_attention
sudo -u postgres psql -d crypto_attention -c "CREATE EXTENSION vector;"
```

### Docker

```bash
# 使用带 pgvector 的 PostgreSQL 镜像
docker run -d \
  --name crypto-attention-db \
  -e POSTGRES_DB=crypto_attention \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# 设置环境变量
export DATABASE_URL="postgresql://postgres:your_password@localhost:5432/crypto_attention"
```

## 迁移流程

迁移脚本 `scripts/migrate_to_postgresql.py` 会执行以下步骤：

1. **检查连接**: 验证 PostgreSQL 可访问
2. **设置 pgvector**: 安装向量扩展
3. **创建表结构**: 根据 models.py 创建所有表
4. **迁移数据**: 从 SQLite 复制所有记录
5. **更新序列**: 确保自增 ID 正确
6. **回填特征**: 计算预计算字段（可通过 `--skip-backfill` 跳过）

## 数据结构变化

### 统一到 AttentionFeature 表

迁移后，以下表将被弃用（数据已合并到 `attention_features`）：
- `state_snapshots` → `attention_features.feat_*` 字段
- `google_trends` → `attention_features.google_trend_*` 字段
- `twitter_volumes` → `attention_features.twitter_*` 字段

### 新增预计算字段

| 字段类别 | 字段名 | 说明 |
|---------|--------|------|
| 价格快照 | `close_price`, `open_price`, etc. | 当日 OHLCV |
| 收益率 | `return_1d/7d/30d/60d` | 滚动收益率 |
| 波动率 | `volatility_7d/30d/60d` | 年化波动率 |
| 成交量 | `volume_zscore_7d/30d` | 成交量标准化 |
| 状态特征 | `feat_ret_zscore_*`, etc. | 用于相似度搜索 |
| 前瞻收益 | `forward_return_3d/7d/30d` | 回测用 |

### pgvector 字段

`feature_vector` 列存储 12 维特征向量，用于快速相似度搜索：

```sql
-- 查找与当前状态最相似的历史时刻
SELECT datetime, 1 - (feature_vector <=> target_vector) AS similarity
FROM attention_features
WHERE symbol_id = 1
ORDER BY feature_vector <=> target_vector
LIMIT 10;
```

## 验证迁移

```bash
# 检查 PostgreSQL 连接
psql -d crypto_attention -c "SELECT COUNT(*) FROM attention_features;"

# 验证预计算字段
psql -d crypto_attention -c "SELECT symbol_id, COUNT(*) FROM attention_features WHERE close_price IS NOT NULL GROUP BY symbol_id;"
```

## 回滚到 SQLite

如果需要回滚，只需修改 `.env`：

```bash
# 注释掉 PostgreSQL
# DATABASE_URL="postgresql://localhost/crypto_attention"

# 使用 SQLite（默认）
# 删除 DATABASE_URL 或设置为 SQLite 路径
```

## 常见问题

### Q: pgvector 安装失败

```bash
# macOS
brew install pgvector

# Ubuntu
sudo apt install postgresql-16-pgvector
```

### Q: 连接被拒绝

```bash
# 确保 PostgreSQL 正在运行
brew services start postgresql@16  # macOS
sudo systemctl start postgresql    # Linux
```

### Q: 权限不足

```bash
# 创建用户并授权
sudo -u postgres psql
CREATE USER myuser WITH PASSWORD 'mypassword';
GRANT ALL PRIVILEGES ON DATABASE crypto_attention TO myuser;
```
