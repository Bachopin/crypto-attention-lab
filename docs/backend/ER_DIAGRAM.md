# 数据库 ER 图（当前架构）

> 更新时间: 2025-12-01  
> 说明: 主业务数据库 (prices / attention / symbols 等) 与 新闻数据库 (news / news_stats) 物理分离；以下 ER 图逻辑上合并展示。

## Mermaid ER Diagram
```mermaid
erDiagram
    SYMBOLS ||--o{ PRICES : contains
    SYMBOLS ||--o{ ATTENTION_FEATURES : contains
    SYMBOLS ||--o{ STATE_SNAPSHOTS : contains

    ATTENTION_FEATURES }o--o{ STATE_SNAPSHOTS : contextual   

    NEWS ||--o{ NEWS_STATS : aggregated

    SYMBOLS ||--o{ NODE_ATTENTION_FEATURES : logical
    SYMBOLS ||--o{ NODE_CARRY_FACTORS : logical

    SYMBOLS {
        int id PK
        string symbol UNIQUE INDEX
        string name
        text aliases
        string coingecko_id INDEX
        bool is_active
        bool auto_update_price
        datetime last_price_update
        datetime last_attention_update
        datetime last_google_trends_update
        text event_performance_cache
        datetime event_performance_updated_at
    }

    PRICES {
        int id PK
        int symbol_id FK -> SYMBOLS.id
        string timeframe INDEX
        datetime datetime INDEX
        float open
        float high
        float low
        float close
        float volume
        UNIQUE symbol_id+timeframe+datetime
    }

    ATTENTION_FEATURES {
        int id PK
        int symbol_id FK -> SYMBOLS.id
        datetime datetime INDEX
        string timeframe INDEX ('D','4H')
        int news_count
        float attention_score
        float weighted_attention
        float bullish_attention
        float bearish_attention
        int event_intensity
        float news_channel_score
        float google_trend_value
        float google_trend_zscore
        float google_trend_change_7d
        float google_trend_change_30d
        float twitter_volume
        float twitter_volume_zscore
        float twitter_volume_change_7d
        float composite_attention_score
        float composite_attention_zscore
        int composite_attention_spike_flag
        text detected_events JSON
        float close_price
        float return_7d
        float volatility_30d
        float volume_zscore_30d
        float feat_ret_zscore_30d
        float feat_vol_zscore_30d
        float feat_att_trend_7d
        float feat_att_news_share
        float feat_att_google_share
        float feat_att_twitter_share
        float feat_bullish_minus_bearish
        float feat_sentiment_mean
        float forward_return_7d
        float max_drawdown_30d
        UNIQUE symbol_id+datetime+timeframe
    }

    %% 旧表 GOOGLE_TRENDS / TWITTER_VOLUMES 已移除，相关字段并入 ATTENTION_FEATURES

    STATE_SNAPSHOTS {
        int id PK
        int symbol_id FK -> SYMBOLS.id
        datetime datetime INDEX
        string timeframe INDEX ('1d','4h')
        int window_days (=30)
        text features JSON
        text raw_stats JSON
        UNIQUE symbol_id+datetime+timeframe+window_days
    }

    NEWS {
        int id PK
        bigint timestamp INDEX
        datetime datetime INDEX
        text title
        string source INDEX
        text url UNIQUE
        string symbols (comma list)
        string relevance
        float source_weight
        float sentiment_score
        string tags
        INDEX (datetime, symbols)
    }

    NEWS_STATS {
        int id PK
        string stat_type ('total','hourly','daily') INDEX
        string period_key INDEX ('ALL','YYYY-MM-DD','YYYY-MM-DDTHH')
        int count
        UNIQUE stat_type+period_key
    }

    NODE_ATTENTION_FEATURES {
        int id PK
        string symbol INDEX (no FK)
        string node_id INDEX
        datetime datetime INDEX
        string freq
        int news_count
        float weighted_attention
        float bullish_attention
        float bearish_attention
        float sentiment_mean
        float sentiment_std
        UNIQUE symbol+node_id+datetime
    }

    NODE_CARRY_FACTORS {
        int id PK
        string symbol INDEX
        string node_id INDEX
        int n_events
        float mean_excess_return
        float hit_rate
        float ir
        string lookahead
        int lookback_days
        datetime updated_at
        UNIQUE symbol+node_id+lookahead+lookback_days
    }
```

## 说明
- `NEWS` 与业务主库分离，减小读写锁冲突；聚合统计缓存在 `NEWS_STATS`。
- `ATTENTION_FEATURES` 集成所有滚动/派生/通道/情绪/前瞻指标，避免 API 端实时多表 join。
- 增量流程依赖唯一约束：`prices` 与 `attention_features` 保证不重复写入同时间粒度记录。
- `STATE_SNAPSHOTS` 只存 30 天窗口计算后的特征与原始统计，供相似状态 / 场景检索使用。
- 节点相关表目前使用 `symbol` 字符串而非外键，保持跨库/异步生产灵活性。
- 未来可选：开启 pgvector (`feature_vector`) 用于高维相似度检索，需要 PostgreSQL 扩展。

## 未来扩展建议
1. 为 `NODE_ATTENTION_FEATURES` 添加外键引用 `symbols` 以加强完整性（仍可选）。
2. 将 `NEWS.symbols` 拆分为关联表 (news_symbols) 支持更复杂过滤与统计。
3. 增加物化视图或聚合表：如最近 24h 注意力特征快照汇总至单表。
4. 启用向量索引后增加“状态相似度”查询 API。

---
若需要导出 PNG，可使用 Mermaid CLI：
```bash
mmdc -i docs/backend/ER_DIAGRAM.md -o er.png
```
(需本地安装 `@mermaid-js/mermaid-cli`)
