# 🔑 获取真实新闻数据指南

## 问题说明

如果你看到前端显示的新闻都是 "ZEC News Sample XXXX" 这种格式,说明系统正在使用 **Mock 数据**,而不是真实的新闻数据。

这是因为:
1. ❌ 没有配置新闻 API 密钥
2. ❌ API 请求失败
3. ❌ 使用了缓存的 mock 数据

---

## ✅ 解决方案

### 方案 1: 配置 CryptoPanic API (推荐)

**CryptoPanic** 是专门的加密货币新闻聚合平台,免费版每天 1000 次请求。

#### 步骤 1: 注册并获取 API Key

1. 访问: https://cryptopanic.com/developers/api/
2. 点击 "Register" 注册账号
3. 登录后进入 Dashboard
4. 复制你的 **API Token**

#### 步骤 2: 配置环境变量

```bash
# 在项目根目录创建 .env 文件
cd /Users/mextrel/VSCode/crypto-attention-lab
nano .env
```

添加以下内容:
```bash
CRYPTOPANIC_API_KEY=your_actual_api_key_here
```

保存并退出 (Ctrl+O, Enter, Ctrl+X)

#### 步骤 3: 删除旧的 Mock 数据

```bash
rm data/raw/attention_zec_news.csv
rm data/processed/attention_features_zec.csv
```

#### 步骤 4: 重新获取数据

```bash
# 方式 1: 使用 Python 脚本
source venv/bin/activate  # 或 source .venv/bin/activate
python -c "from src.data.attention_fetcher import fetch_zec_news; fetch_zec_news()"

# 方式 2: 启动 API 会自动获取
./scripts/start_api.sh
```

---

### 方案 2: 配置 NewsAPI (备选)

**NewsAPI** 是通用新闻 API,免费版每天 100 次请求。

#### 步骤 1: 注册并获取 API Key

1. 访问: https://newsapi.org/register
2. 填写表单注册
3. 验证邮箱后登录
4. 在 Dashboard 复制 **API Key**

#### 步骤 2: 配置环境变量

```bash
# 编辑 .env 文件
nano .env
```

添加:
```bash
NEWS_API_KEY=your_newsapi_key_here
```

#### 步骤 3-4: 同上 (删除旧数据并重新获取)

---

### 方案 3: 同时使用两个 API (最佳)

可以同时配置两个 API,系统会合并数据:

```bash
# .env 文件
CRYPTOPANIC_API_KEY=your_cryptopanic_key
NEWS_API_KEY=your_newsapi_key
```

---

## 🧪 验证数据获取

### 1. 检查新闻数据文件

```bash
cat data/raw/attention_zec_news.csv
```

**真实数据示例:**
```csv
timestamp,datetime,title,source,url
1700000000000,2023-11-15 12:00:00,Zcash Foundation Announces New Privacy Features,CryptoPanic,https://...
```

**Mock 数据示例 (需要替换):**
```csv
timestamp,datetime,title,source,url
1763595497465,2025-11-19 23:38:17,ZEC News Sample 8967,Twitter,https://example.com/news
```

### 2. 测试 API 端点

```bash
# 获取新闻数据
curl -s 'http://localhost:8000/api/news?symbol=ZEC' | jq '.[0]'
```

**真实数据响应:**
```json
{
  "datetime": "2023-11-15T12:00:00Z",
  "source": "CryptoPanic",
  "title": "Zcash Foundation Announces New Privacy Features",
  "url": "https://..."
}
```

### 3. 检查前端显示

访问 http://localhost:3000,查看:
- ✅ Recent News 卡片显示真实新闻标题
- ✅ All News 列表显示多条真实新闻
- ✅ 注意力分数曲线与新闻事件对应

---

## 📊 数据更新频率

### 自动更新
- FastAPI 后端会在启动时检查数据
- 如果数据文件不存在,会自动调用 fetcher

### 手动更新

```bash
# 重新获取最近 7 天的新闻
python -c "
from datetime import datetime, timedelta, timezone
from src.data.attention_fetcher import fetch_zec_news

end = datetime.now(timezone.utc)
start = end - timedelta(days=7)
fetch_zec_news(start, end)
"

# 或删除文件让系统自动获取
rm data/raw/attention_zec_news.csv
rm data/processed/attention_features_zec.csv
```

### 定时任务 (可选)

创建 cron job 每天更新:
```bash
# 编辑 crontab
crontab -e

# 添加每天凌晨 2 点更新
0 2 * * * cd /Users/mextrel/VSCode/crypto-attention-lab && source venv/bin/activate && python -c "from src.data.attention_fetcher import fetch_zec_news; fetch_zec_news()" >> logs/fetch.log 2>&1
```

---

## ⚠️ 常见问题

### 问题 1: API 请求失败

**症状:** 仍然显示 Mock 数据

**解决方案:**
1. 检查 API key 是否正确
2. 检查网络连接
3. 查看日志:
```bash
tail -f logs/app.log  # 如果有的话
# 或启动时观察终端输出
```

### 问题 2: 数据太少

**CryptoPanic 返回的数据可能有限**,特别是对于 ZEC 这种相对小众的币种。

**解决方案:**
- 同时配置 NewsAPI
- 扩大时间范围
- 添加更多数据源

### 问题 3: 超出 API 限制

**症状:** API 返回 429 错误

**解决方案:**
- 减少请求频率
- 使用缓存的数据
- 升级到付费版 API

---

## 🎯 快速开始 (完整流程)

```bash
# 1. 配置 API key
echo "CRYPTOPANIC_API_KEY=your_key_here" > .env

# 2. 删除旧数据
rm data/raw/attention_zec_news.csv data/processed/attention_features_zec.csv

# 3. 启动应用 (会自动获取数据)
./scripts/start_dev.sh

# 4. 访问前端查看
# http://localhost:3000
```

---

## 📚 相关文档

- [CryptoPanic API 文档](https://cryptopanic.com/developers/api/)
- [NewsAPI 文档](https://newsapi.org/docs)
- [项目主 README](./README.md)
- [API 文档](./API_DOCS.md)

---

## 💡 提示

- CryptoPanic 更适合加密货币新闻
- NewsAPI 覆盖范围更广,但需要过滤无关新闻
- 建议同时使用两个 API 获取更全面的数据
- 真实数据获取后,注意力分数会更准确地反映市场情绪
