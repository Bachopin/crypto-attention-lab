# 自动更新总览（当前版本）

最后更新: 2025-12-01  
版本: v3.3 (统一调度参数 / 数据库优先 / 增量链路)

---
## 核心频率 (可通过 .env 覆盖)
- 新闻聚合: `NEWS_UPDATE_INTERVAL=3600` 秒 (1 小时)
- 价格轮询: `PRICE_UPDATE_INTERVAL=600` 秒 (10 分钟)
- 注意力特征冷却: `FEATURE_UPDATE_COOLDOWN=3600` 秒 (1 小时)
- Google Trends 冷却: `GOOGLE_TRENDS_COOLDOWN=43200` 秒 (12 小时)

> 所有调度均统一在 `src/config/settings.py` 中声明。后台任务(`scheduled_news_update`, `scheduled_price_update`)仅从配置读取，不再硬编码。

---
## 更新链路概述
```
新闻(1h 全局) ─┐
                │          ┌───────────────────────────┐
价格(10m 轮询) ─┼─→ 增量特征更新(≥1h) ─→ Google Trends(≥12h) ─→ 预计算(EventPerformance/StateSnapshots)
                │          └───────────────────────────┘
新增代币启用 ───┘                 ↑
                                 │ (force_full 首次, 后续增量)
```

### 1. 新闻聚合 (News Aggregation)
- 多源: CryptoCompare(无限制) + CryptoPanic(有 token 则启用) + NewsAPI(30 天窗口) + RSS。
- 去重策略: 基于 URL & 标题完全匹配；源内批次内本地集合去重。
- 特征加工: `source_weight`, `sentiment_score`, `tags`, 运行时符号检测(`detect_symbols`) → `symbols` 字段（逗号分隔）。
- 存储: 独立新闻数据库 (`NEWS_DATABASE_URL`) 表: `news`。
- 统计缓存: 增量写入 `news_stats` (hourly / daily / total)。若出现历史批量导入要求，可调用重建函数 `_rebuild_*`。

### 2. 价格轮询 (Price Updater)
- 轮询集合: 所有 `auto_update_price=True` 且 `is_active=True` 的代币。
- 错峰策略: `per_symbol_interval = (PRICE_UPDATE_INTERVAL * 0.8) / N` + jitter；保证一周期内均匀分布。
- 时间粒度: `['1d','4h','1h','15m']` 全覆盖。
- 完整性检查 (`should_check_completeness`): 首次或距上次更新 >24h 时执行；严重缺失(<50%) 或首次 → 全量(500 天)，常规增量最多 3~7 天。

### 3. 注意力特征增量 (Attention Incremental)
- 最新特征时间戳来自数据库 `attention_features` 表。
- 上下文窗口: 回溯 `ROLLING_WINDOW_CONTEXT_DAYS=45` 天用于滚动 z-score、趋势等计算稳定性。
- 新数据起点: `latest_feature_dt + 1 day`。
- 数据加载: 价格(上下文区间) + 新闻(仅新段，**结束日期扩展 +1 天以捕获当天全部新闻**) + Google Trends(上下文扩展 7 天, 受冷却/force 控制) + Twitter (占位 0)。
- **日期对齐修复 (2025-12-01)**: K线的 datetime 是开盘时间（如 00:00 UTC），而新闻在当天持续产生。`load_news_data(end=candle_dt)` 会漏掉当天新闻，现已修复为 `end=candle_dt + 1 day`。
- 空新闻场景: 自动填充 `news_channel_score=0`，避免 KeyError。
- 输出: 仅新数据行写入数据库；上下文行不覆盖。

### 4. 预计算 (PrecomputationService)
| 类型 | 冷却 | 模式 | 说明 |
|------|------|------|------|
| Event Performance | 12h | 冷却控制 | lookahead 固定 `[1,3,5,10]`；使用日线价格 & 预计算事件字段 `detected_events` |
| State Snapshots 1d | 24h | 增量 | `window_days=30`，全量仅首次或强制刷新 |
| State Snapshots 4h | 4h | 增量 | 同上 |

首次 Attention 全量计算后触发一次 `force_refresh=True`；后续增量使用冷却策略。

### 5. 新增代币初始化 (Enable Auto Update)
1. 验证 Binance 上存在 (Spot→Futures fallback)。
2. 创建/更新 `symbols` 记录 (别名多源获取 CoinGecko→CryptoCompare→Binance)。
3. 若无价格或数据过旧 (>7 天) → 拉取 500 天历史。
4. 立即执行 Attention 全量计算 + 预计算。
5. 之后进入常规 10 分钟轮询 + 1 小时特征冷却模式。

---
## 数据库结构要点
- 主库: `symbols`, `prices`, `attention_features`, `state_snapshots`。
- 新闻库: `news`, `news_stats`。
- 唯一约束建议: `attention_features(symbol_id, datetime, timeframe)`（已在迁移中确保）避免多频率冲突。

---
## 配置与可调参数 (.env)
```env
PRICE_UPDATE_INTERVAL=600
NEWS_UPDATE_INTERVAL=3600
FEATURE_UPDATE_COOLDOWN=3600
GOOGLE_TRENDS_COOLDOWN=43200
# 可选：DATABASE_URL=postgresql://user:pass@host:5432/db
# 可选：NEWS_DATABASE_URL=postgresql://user:pass@host:5432/news_db
```
修改后只需重启后端即可生效，无需改代码。

---
## 失败与回退策略
| 场景 | 行为 |
|------|------|
| 新闻源单源失败 | 记录错误继续其他源；最终若全部失败返回空 DF（不写入） |
| 新闻 DB 写失败 | 回退 CSV(仅当数据库异常)，日志标记 ⚠️ |
| Google Trends 限流 | 冷却未过 → 使用缓存或填充 0；过期请求失败 → 填充 0 并记录 warning |
| Twitter 数据缺失 | 始终写 0，并可在前端标记“Unavailable” |
| 唯一约束冲突 (旧 schema) | 跳过冲突记录并打印首次警告，建议迁移 |

---
## 监控指标建议
- 最新价格时间 vs 最新注意力时间差 (目标 < PRICE_UPDATE_INTERVAL + FEATURE_UPDATE_COOLDOWN)
- 每小时新闻数平滑度 (异常激增检测重复统计问题)
- Google Trends 调用成功率 / 冷却剩余时间
- Event Performance 最近更新时间 (<=12h)
- State Snapshots 1d / 4h 最新时间戳与价格末尾对齐程度

---
## 常用运维指令
```bash
# 查看调度日志最近 200 行
grep -E "\[Scheduler]|\[Updater]" logs/app.log | tail -n 200

# PostgreSQL 中检查 attention 最新时间戳 (示例 BTC)
psql "$DATABASE_URL" -c "SELECT max(datetime) FROM attention_features WHERE timeframe='D' AND symbol_id=(SELECT id FROM symbols WHERE symbol='BTC');"

# 新闻总数与缓存一致性
psql "$NEWS_DATABASE_URL" -c "SELECT count FROM news_stats WHERE stat_type='total' AND period_key='ALL';"
psql "$NEWS_DATABASE_URL" -c "SELECT count(*) FROM news;"
```

---
## 后续优化路线
1. 增加新闻统计幂等写：按 period 查询真实行数覆盖而非累加。
2. Attention 初始化预计算拆分为异步队列，避免大批量启用时阻塞。
3. 引入 Twitter 实际数据源后，增加独立冷却与缓存表。
4. 增加健康端点扩展：返回调度频率与冷却剩余秒数。

---
如需扩展新的数据源或特征，请保持：数据库优先 / 增量优先 / 冷却可配置 / 失败可退化。