# 🚀 Quick Start Guide - Crypto Attention Lab

本指南帮助你快速启动完整的全栈应用。

---

## ⚡ 一键启动 (推荐)

```bash
# 确保在项目根目录
cd /Users/mextrel/VSCode/crypto-attention-lab

# 一键启动后端 + 前端
./scripts/start_dev.sh
```

启动后访问:
- **前端:** http://localhost:3000
- **后端 API:** http://localhost:8000
- **API 文档:** http://localhost:8000/docs

按 `Ctrl+C` 停止所有服务。

---

## 📋 手动启动步骤

### 准备工作 (仅首次运行)

#### 1. 安装 Python 依赖

```bash
# 创建虚拟环境 (可选但推荐)
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
.venv\Scripts\activate    # Windows

# 安装依赖
pip install -r requirements.txt
```

#### 2. 安装 Node.js 依赖

```bash
cd web
npm install
cd ..
```

#### 3. 配置环境变量

```bash
# 前端环境变量 (已预配置,无需修改)
cat web/.env.local
# 应该包含: NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

### 启动应用

#### 方式 1: 使用启动脚本

```bash
# 仅启动 FastAPI 后端
./scripts/start_api.sh

# 或启动完整应用 (后端 + 前端)
./scripts/start_dev.sh
```

#### 方式 2: 分别启动

**终端 1 - 启动后端:**
```bash
source venv/bin/activate  # 激活虚拟环境 (如果有)
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**终端 2 - 启动前端:**
```bash
cd web
npm run dev
```

---

## 📊 验证安装

### 1. 检查后端 API

```bash
# 健康检查
curl http://localhost:8000/health

# 预期输出: {"status":"healthy"}
```

访问 API 文档: http://localhost:8000/docs

### 2. 检查前端

打开浏览器访问: http://localhost:3000

应该看到:
- ✅ 深色主题的交易面板
- ✅ ZEC/USDT 价格图表
- ✅ 注意力分数曲线
- ✅ 新闻列表
- ✅ 统计卡片

---

## ⚠️ 常见问题

### 问题 1: 端口被占用

```bash
# 后端端口冲突 (8000)
uvicorn src.api.main:app --port 8001 --reload

# 前端端口冲突 (3000)
cd web
npm run dev -- -p 3001
```

### 问题 2: 数据加载失败

**症状:** 前端显示错误 "Failed to load data from backend"

**解决方案:**

1. 确保后端正在运行:
```bash
curl http://localhost:8000/health
```

2. 检查数据文件是否存在:
```bash
ls data/raw/price_data_ZECUSDT_1d.csv
ls data/processed/zec_attention_scores.csv
```

3. 如果数据不存在,后端会自动获取 (首次启动可能需要几分钟)

### 问题 3: FastAPI 未安装

```bash
pip install fastapi uvicorn[standard]
```

### 问题 4: Next.js 依赖问题

```bash
cd web
rm -rf node_modules package-lock.json
npm install
```

### 问题 5: CORS 错误

确保 `src/api/main.py` 中 CORS 配置正确:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有源
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🔍 测试 API 端点

### 获取价格数据

```bash
curl "http://localhost:8000/api/price?symbol=ZECUSDT&timeframe=1d" | jq
```

### 获取注意力数据

```bash
curl "http://localhost:8000/api/attention?symbol=ZEC" | jq
```

### 获取新闻数据

```bash
curl "http://localhost:8000/api/news?symbol=ZEC" | jq
```

---

## 📚 下一步

1. **查看 API 文档:** [API_DOCS.md](./API_DOCS.md)
2. **了解前端架构:** [WEB_OVERVIEW.md](./WEB_OVERVIEW.md)
3. **阅读完整 README:** [README.md](./README.md)

---

## 🛠️ 开发模式特性

- ✅ **热重载:** 代码更改自动生效
  - Python: `--reload` 标志
  - Next.js: 内置 Fast Refresh
- ✅ **详细日志:** 终端显示所有请求
- ✅ **错误提示:** 前端显示友好的错误信息
- ✅ **API 文档:** Swagger UI 交互式测试

---

## 🎯 生产部署 (未来)

当前配置适用于开发环境。生产部署需要:

1. 更新 CORS 配置 (限制允许的域名)
2. 添加 API 认证
3. 使用 Gunicorn/多进程部署 FastAPI
4. 构建 Next.js 静态资源
5. 配置 Nginx 反向代理
6. 添加速率限制
7. 设置日志系统

参考: [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)

---

## 💡 提示

- 首次启动可能需要等待数据下载 (Binance API + 新闻数据)
- 数据会缓存在 `data/` 目录,后续启动更快
- 如需重新获取数据,删除 CSV 文件即可
- 使用 `--reload` 开发时修改代码会自动重启服务器
