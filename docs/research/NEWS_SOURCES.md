# 新闻数据源配置指南

本项目支持多个新闻源，按优先级排序如下：

## 1. CryptoCompare News API ✅ 推荐
- **费用**: 完全免费
- **API Key**: ❌ 不需要
- **限制**: 无明显限制
- **覆盖**: 全球加密货币新闻，支持关键词过滤
- **历史数据**: 支持
- **文档**: https://min-api.cryptocompare.com/documentation?key=News

**配置**: 无需配置，开箱即用

---

## 2. CryptoPanic API ⭐ 可选
- **费用**: 免费层每月 20,000 请求
- **API Key**: ✅ 需要注册
- **限制**: 免费层限制 20k/月，足够日常使用
- **覆盖**: 专注加密货币新闻和社交媒体
- **质量**: 非常高，包含情绪分析
- **注册**: https://cryptopanic.com/developers/api/

**配置**: 
```bash
# 在 .env 文件中添加
CRYPTOPANIC_API_KEY=your_token_here
```

---

## 3. NewsAPI 🔒 限制较多
- **费用**: 免费层只能查询最近 **30 天**
- **API Key**: ✅ 需要注册
- **限制**: 
  - 免费版每天 100 请求
  - 只能查询最近 1 个月历史数据
  - 商业用途需付费
- **注册**: https://newsapi.org/

**配置**:
```bash
# 在 .env 文件中添加
NEWS_API_KEY=your_api_key_here
```

**⚠️ 注意**: 由于免费版限制严格，主要作为补充源使用

---

## 4. RSS 聚合 📰 Fallback
- **费用**: 完全免费
- **API Key**: ❌ 不需要
- **来源**: 
  - CoinDesk RSS
  - CryptoSlate RSS
  - CoinTelegraph RSS
- **限制**: 无，但需要爬取解析
- **覆盖**: 仅最近几天的新闻

**配置**: 无需配置，作为 fallback 自动启用

---

## 使用建议

### 推荐配置（最省事）
只使用 **CryptoCompare**，无需任何 API key：
```bash
# 不需要任何配置，直接运行
python scripts/fetch_news_data.py
```

### 增强配置（获取更多新闻）
添加 **CryptoPanic** token：
1. 访问 https://cryptopanic.com/developers/api/
2. 免费注册获取 token
3. 添加到 `.env`:
   ```
   CRYPTOPANIC_API_KEY=xxxxxxxx
   ```

### 完整配置（最全面）
同时配置所有三个 API：
```bash
# .env 文件
CRYPTOPANIC_API_KEY=your_cryptopanic_token
NEWS_API_KEY=your_newsapi_key
```

---

## API 频率限制与更新策略

### 当前配置
- **自动刷新频率**: 5 分钟（前端自动调用）
- **历史数据**: 60 天
- **去重策略**: 基于标题完全匹配

### CryptoCompare 限制
- **官方文档**: 无明确频率限制
- **建议**: 每 5 分钟刷新一次没问题
- **实测**: 无 429 错误

### CryptoPanic 限制
- **免费层**: 20,000 请求/月
- **计算**: 
  - 每 5 分钟 = 12 次/小时 = 288 次/天 = 8,640 次/月
  - ✅ 在限制范围内

### NewsAPI 限制
- **免费层**: 100 请求/天
- **计算**: 每 5 分钟会超限！
- **解决**: 脚本中仅在前两个源失败时才调用 NewsAPI

---

## 数据存储

### 本地文件
- **路径**: `data/raw/attention_zec_news.csv`
- **格式**: 
  ```csv
  timestamp,datetime,title,source,url,relevance
  1764211132000,2025-11-26T21:38:52+00:00,"Grayscale Targets...",cryptonews,https://...,direct
  ```

### 字段说明
- `timestamp`: Unix 时间戳（毫秒）
- `datetime`: ISO 8601 格式（UTC）
- `title`: 新闻标题
- `source`: 来源名称
- `url`: 原文链接
- `relevance`: 相关性（`direct`=直接提及ZEC，`related`=隐私币相关）
- `language`: 语言代码（如 `en`），默认为 `en`

---

## ⚠️ 重要说明：历史新闻数据限制

### 实际情况
ZEC/Zcash 是一个**小众隐私币**，日常新闻报道较少。只有在**重大事件**时才会有密集报道：

**示例**（2025年11月）:
- 11月25-27日：Grayscale 申请 ZEC ETF + 价格暴涨 1000%
- 新闻数量：23 条
- 之前 58 天：几乎没有新闻

### 数据覆盖说明
| 时间范围 | 预期新闻量 | 实际情况 |
|---------|-----------|---------|
| 最近 3 天 | 10-50 条 | ✅ 实际 20-30 条 |
| 最近 7 天 | 20-100 条 | ⚠️ 取决于市场波动 |
| 最近 30 天 | 50-200 条 | ⚠️ 平时可能只有 5-10 条 |
| 最近 60 天 | 100-500 条 | ❌ 平时可能只有 10-20 条 |

### 建议
1. **接受现实**：ZEC 不是热门币种，新闻本来就少
2. **添加 CryptoPanic**：历史数据更全，包含社交媒体
3. **扩大关键词**：增加 "privacy coin" 等相关新闻
4. **降低预期**：60天目标改为"尽可能获取所有历史新闻"

---

## 测试命令

### 手动运行新闻获取
```bash
python scripts/fetch_news_data.py
```

### 通过 API 触发更新
```bash
curl -X POST http://localhost:8000/api/update-data
```

### 查看新闻数据
```bash
curl "http://localhost:8000/api/news?symbol=ZEC" | jq '.[0:5]'
```

---

## 故障排查

### 问题: 没有获取到新闻
**检查**:
1. 网络连接是否正常
2. 查看日志: `tail -f logs/crypto_attention_lab.log`
3. 手动运行脚本查看详细错误

### 问题: 新闻数量太少
**解决**:
1. 添加 CryptoPanic token（增加来源）
2. 检查是否被时间范围过滤（默认 60 天）
3. 降低关键词匹配严格度

### 问题: API 超限
**解决**:
1. 延长自动刷新间隔（修改 `web/app/page.tsx` 中的 `5 * 60 * 1000`）
2. 禁用 NewsAPI（已自动处理）
3. 使用本地缓存减少 API 调用

---

## 未来扩展建议

1. **Twitter/X API**: 实时推文监控（需要付费）
2. **Reddit API**: r/zcash 子版块监控（免费）
3. **Telegram**: Zcash 官方频道监控（需要爬虫）
4. **Google News**: 通过 RSS 或自定义搜索 API
5. **CoinGecko**: 虽无专门新闻 API，但有事件日历

---

## 总结

**最佳实践**: 
- ✅ 使用 CryptoCompare（免费，无 key，稳定）
- ✅ 可选添加 CryptoPanic（提升质量）
- ❌ 避免依赖 NewsAPI（限制太多）
- ✅ RSS 作为 fallback 保底

**当前状态**:
- ✅ 已集成 CryptoCompare
- ✅ 支持 60 天历史数据
- ✅ 每 5 分钟自动更新
- ✅ 本地持久化存储
