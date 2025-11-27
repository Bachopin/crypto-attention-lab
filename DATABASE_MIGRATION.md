# 数据库迁移说明

## 📊 数据存储架构升级

本项目已从 **CSV 文件存储** 升级到 **SQLite 数据库存储**。

### 当前状态

✅ **主存储**: SQLite 数据库 (`data/crypto_attention.db`)
- 价格数据 (Price)
- 新闻数据 (News)
- 注意力特征 (AttentionFeature)
- 币种信息 (Symbol)

✅ **CSV 文件已清理**: `data/raw/` 和 `data/processed/` 目录已清空
- 备份位置: `data/csv_backup_YYYYMMDD_HHMMSS/`

### 数据库优势

1. **更好的查询性能**: 索引支持，快速范围查询
2. **数据完整性**: 主键、外键约束
3. **去重机制**: URL/时间戳唯一约束
4. **并发访问**: 支持多进程读写
5. **空间效率**: 更紧凑的存储格式

### 数据库结构

```sql
-- 币种表
Symbol (id, symbol, name, category)

-- 价格表 (索引: symbol_id, timeframe, timestamp)
Price (id, symbol_id, timeframe, datetime, timestamp, open, high, low, close, volume)

-- 新闻表 (索引: datetime, source, 唯一约束: url)
News (id, datetime, source, title, url, relevance, source_weight, sentiment_score, tags, symbols)

-- 注意力特征表 (索引: symbol_id, datetime)
AttentionFeature (id, symbol_id, datetime, attention_score, news_count, weighted_attention, ...)
```

### 查看数据库统计

```bash
cd /Users/mextrel/VSCode/crypto-attention-lab
source /Users/mextrel/VSCode/.venv/bin/activate

python -c "
from src.database.models import init_database, get_session, Price, News, AttentionFeature
engine = init_database()
session = get_session(engine)
print(f'Price records: {session.query(Price).count()}')
print(f'News records: {session.query(News).count()}')
print(f'Attention records: {session.query(AttentionFeature).count()}')
"
```

### 清理旧 CSV 文件

数据已完全迁移到数据库，CSV 文件可以删除：

```bash
# 安全清理脚本（会自动备份）
./scripts/cleanup_csv_files.sh

# 或手动删除
rm data/raw/*.csv
```

**注意**: 清理脚本会自动创建备份到 `data/csv_backup_YYYYMMDD_HHMMSS/`

### API 行为

所有 API 端点现在：
1. **优先读取数据库**
2. CSV 文件仅作为紧急 fallback（如果数据库读取失败）

相关代码: `src/data/db_storage.py`

### 数据更新流程

当执行数据更新时（点击"刷新数据"按钮或运行脚本）：

```python
# 旧方式（已废弃）
df.to_csv('data/raw/price_ZECUSDT_1d.csv')

# 新方式（当前）
from src.data.db_storage import save_price_data
save_price_data('ZECUSDT', '1d', records)
```

### 脚本更新状态

| 脚本 | 状态 | 存储方式 |
|------|------|----------|
| `fetch_price_data.py` | ✅ 已更新 | 仅数据库 |
| `fetch_news_data.py` | ✅ 已更新 | 数据库优先，失败才用 CSV |
| `generate_attention_data.py` | ✅ 已更新 | 仅数据库 |
| `migrate_to_database.py` | ℹ️ 迁移工具 | 一次性使用 |

### 回退到 CSV 模式（不推荐）

如果需要临时回退到 CSV 模式，编辑 `src/data/db_storage.py`:

```python
# 设置为 False 将回退到 CSV 模式
USE_DATABASE = False
```

### 常见问题

**Q: 删除 CSV 文件安全吗？**
A: 是的，所有数据都已在数据库中，且有备份机制。

**Q: 如何查看数据库文件？**
A: 使用 SQLite 客户端:
```bash
# 命令行
sqlite3 data/crypto_attention.db

# 或使用 GUI 工具
# - DB Browser for SQLite
# - DBeaver
# - VS Code SQLite extension
```

**Q: 数据库文件会不会太大？**
A: SQLite 自动压缩，通常比 CSV 更小。当前大小约 1.3MB。

**Q: 可以手动编辑数据吗？**
A: 不推荐。使用 API 或 Python ORM 更安全：
```python
from src.database.models import get_session, init_database, News
session = get_session(init_database())
news_item = session.query(News).filter_by(id=1).first()
news_item.title = "Updated Title"
session.commit()
```

### 相关文件

- 数据库定义: `src/database/models.py`
- 存储接口: `src/data/db_storage.py`
- 迁移脚本: `scripts/migrate_to_database.py`
- 清理脚本: `scripts/cleanup_csv_files.sh`
