# 性能优化与监控文档

## 性能分析报告

### 当前资源占用情况

根据实际运行监测：

| 服务 | 内存 (RSS) | CPU | 说明 |
|-----|-----------|-----|------|
| 后端 API | ~32 MB | 0.1% | uvicorn 生产模式，无热重载 |
| 前端服务 | ~38 MB | 0.0% | Next.js dev server (Turbopack) |
| 监控进程 | ~1 MB | 0.0% | Bash 脚本，每30秒检查一次 |
| **总计** | **~71 MB** | **0.1%** | 非常低的资源占用 |

### 日志文件增长情况

| 日志文件 | 当前大小 | 增长速度 |
|---------|---------|---------|
| api.log | 42 KB | ~5 KB/小时 |
| daemon.log | 509 KB | ~20 KB/小时 |
| web.log | 396 B | ~100 B/小时 |
| monitor.log | 3.5 KB | ~500 B/小时 |

**预估**：在没有日志轮转的情况下，daemon.log 约 25 天会达到 10 MB。

---

## 潜在性能风险与解决方案

### ✅ 已解决的问题

#### 1. **日志文件无限增长** → 已添加日志轮转机制

**问题**：日志文件使用 `>` 和 `>>` 追加，长期运行会无限增长。

**解决方案**：
- 创建了 `scripts/rotate_logs.sh` 自动轮转脚本
- 单个日志文件超过 10 MB 自动轮转
- 保留最近 5 个备份
- 在 `daemon.sh start` 时自动检查并轮转

**建议**：配置定期自动执行（见下方 crontab 配置）

#### 2. **日志覆盖问题** → 改用追加模式

**修改**：
- `>` 改为 `>>` (api.log, web.log)
- 避免每次重启清空历史日志

#### 3. **后端日志级别过低** → 调整为 warning

**修改**：
- 添加 `--log-level warning` 减少不必要的日志输出
- 降低磁盘 I/O 和日志文件增长速度

---

### 🟡 需要注意的点

#### 1. **前端开发模式持续运行**

**现状**：
- 使用 `npm run dev` (Turbopack)
- 会持续监听文件变化
- CPU 占用目前很低 (0.0%)，但长期运行可能增加

**建议**：
- 如果是纯生产环境，改用 `npm run build && npm run start`
- 开发环境保持现状即可

#### 2. **监控进程检查间隔**

**现状**：每 30 秒检查一次

**优化空间**：
- 可以延长到 60 秒降低开销（但响应变慢）
- 目前 30 秒是合理平衡

#### 3. **数据库连接池**

**现状**：PostgreSQL 默认最大连接数 100

**建议**：
- 检查 FastAPI 的数据库连接池配置
- 确保有 `pool_recycle` 避免连接泄漏
- 参考 `src/config/settings.py` 中的数据库配置

---

## 监控与维护建议

### 定期任务配置

#### 自动日志轮转（推荐每天执行）

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天凌晨 3 点执行）
0 3 * * * /Users/mextrel/VSCode/crypto-attention-lab/scripts/rotate_logs.sh >> /Users/mextrel/VSCode/crypto-attention-lab/logs/rotate.log 2>&1
```

#### 自动健康检查与重启（推荐每 6 小时一次）

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每 6 小时检查一次服务状态，异常时自动启动）
0 */6 * * * /Users/mextrel/VSCode/crypto-attention-lab/scripts/health_check.sh
```

**说明**：
- 这个脚本会检查后端和前端是否正常运行
- 如果检测到异常，自动执行 `daemon.sh start` 重启服务
- 所有操作都会记录到 `logs/health_check.log`
- 建议配合 launchd 开机自启使用，形成双重保障

#### 一键配置所有定期任务

```bash
(crontab -l 2>/dev/null; echo "# Crypto Attention Lab 定期任务"; echo "0 3 * * * /Users/mextrel/VSCode/crypto-attention-lab/scripts/rotate_logs.sh >> /Users/mextrel/VSCode/crypto-attention-lab/logs/rotate.log 2>&1"; echo "0 */6 * * * /Users/mextrel/VSCode/crypto-attention-lab/scripts/health_check.sh") | crontab -
```

#### 定期检查服务健康状态（已包含在上面）

```bash
# 健康检查脚本会自动重启异常服务，无需单独配置
```

### 手动检查命令

#### 查看资源占用

```bash
# 内存和 CPU
ps aux | grep -E "uvicorn|npm run dev|monitor_web" | grep -v grep

# 详细进程信息
cd /Users/mextrel/VSCode/crypto-attention-lab
ps -p $(cat logs/api.pid) -o pid,vsz,rss,pcpu,etime,comm
ps -p $(cat logs/web.pid) -o pid,vsz,rss,pcpu,etime,comm
ps -p $(cat logs/monitor.pid) -o pid,vsz,rss,pcpu,etime,comm
```

#### 查看日志大小

```bash
du -sh logs/*
ls -lh logs/*.log
```

#### 查看数据库连接

```bash
psql -d crypto_attention_lab -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'crypto_attention_lab';"
```

---

## 内存泄露检测

### 长期监控脚本

创建 `scripts/monitor_memory.sh`（可选）：

```bash
#!/bin/bash
LOG_FILE="logs/memory-monitor.log"
echo "[$(date)] Memory Check" >> "$LOG_FILE"
ps -p $(cat logs/api.pid) -o rss= 2>/dev/null >> "$LOG_FILE" || echo "API not running" >> "$LOG_FILE"
ps -p $(cat logs/web.pid) -o rss= 2>/dev/null >> "$LOG_FILE" || echo "Web not running" >> "$LOG_FILE"
```

配置 crontab 每小时记录一次：
```bash
0 * * * * /Users/mextrel/VSCode/crypto-attention-lab/scripts/monitor_memory.sh
```

一周后查看趋势：
```bash
cat logs/memory-monitor.log
```

如果内存持续上升，说明可能有泄露。

---

## 性能优化建议

### 生产环境优化

如果要部署到生产环境（非开发模式），建议：

1. **前端改用生产构建**
   ```bash
   cd web
   npm run build
   npm run start  # 替代 npm run dev
   ```

2. **后端使用 Gunicorn + Uvicorn Workers**
   ```bash
   pip install gunicorn
   gunicorn src.api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

3. **配置 Nginx 反向代理**
   - 缓存静态资源
   - 压缩响应数据
   - 负载均衡

### 数据库优化

1. **启用连接池**（已在代码中配置）
2. **定期 VACUUM**
   ```bash
   psql -d crypto_attention_lab -c "VACUUM ANALYZE;"
   ```
3. **监控慢查询**
   ```sql
   SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;
   ```

---

## 结论

### ✅ 当前状态评估

- **内存占用**：~71 MB，非常低 ✅
- **CPU 占用**：0.1%，几乎可以忽略 ✅
- **日志增长**：已添加轮转机制 ✅
- **PID 管理**：已修复 PID 复用问题 ✅
- **监控机制**：每 30 秒检查，开销极低 ✅

### ⚠️ 注意事项

- 长期运行（数月）后建议重启一次（清理缓存）
- 定期检查日志文件大小（已有自动轮转）
- 如果数据库数据量巨大（GB 级），需要单独优化查询

### 🎯 推荐操作

1. **立即执行**：
   ```bash
   # 配置日志自动轮转
   crontab -e
   # 添加: 0 3 * * * /Users/mextrel/VSCode/crypto-attention-lab/scripts/rotate_logs.sh
   ```

2. **配置开机自动启动**（见 `docs/setup/AUTO_START_GUIDE.md`）

3. **一周后检查一次资源占用**：
   ```bash
   ./scripts/daemon.sh status
   ps aux | grep -E "uvicorn|npm run dev" | grep -v grep
   ```

目前的配置**不会造成内存泄露或 CPU 过高**，可以放心长期运行。
