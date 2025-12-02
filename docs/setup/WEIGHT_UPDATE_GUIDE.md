# 新闻源权重更新后的数据重算指南

## 背景

在 2025年12月2日，我们更新了中文新闻源的权重配置，确保其与英文新闻源相当：

### 主要改进

1. **新增主要中文新闻源**
   - `PANews`: 1.0（数据库中有 5万+ 条，现在权重等同 CoinDesk）
   - `金色财经`: 0.95（等同 Cointelegraph）
   - `Odaily`: 0.92（等同 The Block）

2. **权重对齐**
   - 顶级源（1.0）: PANews = CoinDesk
   - 一线源（0.95）: 金色财经 = Cointelegraph  
   - 二线源（0.88-0.92）: 巴比特/Odaily = Decrypt/The Block

3. **语言权重统一**
   - 中文 (zh): 1.0
   - 英文 (en): 1.0

## 受影响的数据

权重更新后，数据库中以下字段需要重新计算：

### ✅ 需要更新的字段
- `weighted_attention` - 基于 source_weight 计算
- `bullish_attention` - 基于 source_weight × sentiment
- `bearish_attention` - 基于 source_weight × sentiment
- `news_channel_score` - weighted_attention 的 z-score
- `composite_attention_score` - 包含 news_channel_score
- `composite_attention_zscore` - composite 的 z-score
- `composite_attention_spike_flag` - 基于 composite 分位数
- `detected_events` - 基于上述特征检测的事件

### ❌ 不需要更新的字段
- `google_trend_*` - 外部数据，不依赖权重
- `twitter_volume_*` - 外部数据，不依赖权重
- `news_count` - 纯计数，不涉及权重
- `attention_score` - 仅基于 news_count 的归一化

## 影响程度示例（ZEC）

以下是实际的权重更新影响（2025年12月1日数据）：

```
weighted_attention:  4.4250 -> 9.7500  (+120%)
bullish_attention:   0.5000 -> 0.7200  (+44%)
bearish_attention:   0.9250 -> 3.5500  (+284%)
composite_score:     0.3621 -> 0.7696  (+112%)
```

**结论**: 由于中文新闻（主要是 PANews）数量众多且权重大幅提升，相关注意力特征会显著增加。

## 重算步骤

### 1. 试运行（推荐先执行）

查看单个 symbol 的影响：

```bash
python3 scripts/recompute_after_weight_update.py --dry-run --symbols ZEC
```

查看多个 symbols 的影响：

```bash
python3 scripts/recompute_after_weight_update.py --dry-run --symbols ZEC BTC ETH
```

查看所有 symbols 的影响：

```bash
python3 scripts/recompute_after_weight_update.py --dry-run
```

### 2. 实际更新

**⚠️ 注意**: 此操作会修改数据库，建议先备份！

更新单个 symbol：

```bash
python3 scripts/recompute_after_weight_update.py --symbols ZEC
```

更新所有 symbols：

```bash
python3 scripts/recompute_after_weight_update.py
```

更新特定时间粒度：

```bash
# 更新日线数据（默认）
python3 scripts/recompute_after_weight_update.py --timeframe 1d

# 更新4小时线数据
python3 scripts/recompute_after_weight_update.py --timeframe 4h
```

### 3. 验证更新结果

检查特定 symbol 的数据：

```python
from src.data.db_storage import get_db

db = get_db()
features = db.get_attention_features('ZEC', timeframe='1d')

# 查看最近的特征值
print(features[['datetime', 'weighted_attention', 'composite_attention_score']].tail(10))
```

## 常见问题

### Q1: 需要更新所有 symbols 吗？

**A**: 是的，建议更新所有包含新闻数据的 symbols，尤其是与中文新闻相关的币种。

### Q2: 更新需要多长时间？

**A**: 取决于数据量：
- 单个 symbol（~500天数据）: ~5-10秒
- 所有 symbols: ~1-2分钟

### Q3: 可以只更新最近的数据吗？

**A**: 当前脚本会重算所有历史数据。如果只需要更新最近数据，可以修改脚本添加 `start` 参数。

### Q4: 如果更新出错怎么办？

**A**: 脚本使用事务机制，单个 symbol 失败不会影响其他 symbols。可以：
1. 查看错误日志
2. 重新运行失败的 symbol
3. 如有必要，从备份恢复

## 技术细节

### 计算逻辑

脚本会：

1. 从数据库加载原始新闻数据
2. 使用新权重配置重新计算特征：
   ```python
   effective_weight = source_base_weight × language_weight × node_adjustment
   weighted_attention = Σ(effective_weight × relevance_weight)
   bullish_attention = Σ(positive_sentiment × weighted)
   bearish_attention = Σ(negative_sentiment × weighted)
   ```
3. 重新计算复合特征和事件检测
4. 只更新受影响的字段，保留 Google/Twitter 数据

### 数据完整性

- ✅ 保留所有原始新闻数据
- ✅ 保留 Google Trends 和 Twitter 数据
- ✅ 保留价格数据
- ✅ 仅更新基于权重计算的派生特征

## 相关文件

- 权重配置: `src/config/attention_channels.py`
- 重算脚本: `scripts/recompute_after_weight_update.py`
- 计算逻辑: `src/features/calculators.py`
- 事件检测: `src/features/event_detectors.py`

## 更新记录

- **2025-12-02**: 首次权重调整，提升中文新闻源权重至与英文相当
