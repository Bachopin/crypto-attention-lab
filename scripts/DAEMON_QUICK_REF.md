# Daemon 快速参考 (Quick Reference)

## 常用命令

| 命令 | 功能 | 何时使用 |
|------|------|---------|
| `bash scripts/daemon.sh start` | 启动所有服务 | 初次启动或全量重启 |
| `bash scripts/daemon.sh stop` | 停止所有服务 | 关闭所有服务（不停止数据库） |
| `bash scripts/daemon.sh restart` | 重启所有服务 | 需要刷新所有服务状态 |
| `bash scripts/daemon.sh status` | 显示服务状态 | 快速检查当前状态 |
| `bash scripts/daemon.sh logs api` | 实时查看后端日志 | 调试后端问题 |
| `bash scripts/daemon.sh logs web` | 实时查看前端日志 | 调试前端问题 |
| `bash scripts/daemon.sh logs daemon` | 实时查看启动日志 | 诊断启动问题 |

## 服务地址

| 服务 | 地址 | 用途 |
|------|------|------|
| 前端应用 | http://localhost:3000 | Web Dashboard |
| 后端 API | http://localhost:8000 | RESTful API |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| 数据库 | localhost:5432 | PostgreSQL |

## 数据库故障排查

### 症状：数据库未运行
```bash
# 1. 检查 PostgreSQL 服务
brew services list | grep postgres

# 2. 重新启动数据库
brew services restart postgresql@16

# 3. 验证连接
/opt/homebrew/opt/postgresql@16/bin/pg_isready -h localhost
```

### 症状：postmaster.pid lock 错误
```bash
# 脚本已自动处理，但如果需要手动修复：
rm -f /opt/homebrew/var/postgresql@16/postmaster.pid

# 然后重新启动
bash scripts/daemon.sh start
```

### 症状：端口被占用
```bash
# 脚本会自动清理占用的端口，但也可手动检查：
lsof -i :3000    # 检查前端端口
lsof -i :8000    # 检查后端端口
lsof -i :5432    # 检查数据库端口
```

## 日志位置

| 服务 | 日志路径 |
|------|---------|
| 后端 API | `logs/api.log` |
| 前端服务 | `logs/web.log` |
| Daemon 启动 | `logs/daemon.log` |
| 监控进程 | `logs/monitor.log` |
| PID 文件 | `logs/*.pid` |

## 进程信息

| 文件 | 内容 |
|------|------|
| `logs/api.pid` | 后端 API 的 PID |
| `logs/web.pid` | 前端服务的 PID |
| `logs/monitor.pid` | 监控守护进程的 PID |

## 常见问题

### Q: 脚本启动后能否退出终端？
**A**: 是的。所有进程都以 `nohup` 方式运行，退出终端后仍会继续运行。

### Q: 如何查看实时日志？
**A**: 使用 `bash scripts/daemon.sh logs [service]`，例如：
```bash
bash scripts/daemon.sh logs api     # 查看后端日志
bash scripts/daemon.sh logs         # 查看所有日志
```

### Q: 重启整个系统后需要手动启动吗？
**A**: 是的。需要运行 `bash scripts/daemon.sh start`。

### Q: 能否部分启动（只启动后端或只启动前端）？
**A**: 可以，直接编辑 `scripts/daemon.sh` 的 `start_all()` 函数，注释掉不需要的服务。

### Q: 监控进程会自动重启前端吗？
**A**: 是的。监控进程每 30 秒检查一次前端是否运行，如果崩溃会自动重启。

## 改进日志

### 2026-01-09 版本
- ✅ 新增预检查函数，自动清理数据库僵尸进程
- ✅ 增强数据库启动逻辑，增加重试机制
- ✅ 提供详细的错误排查指南
- ✅ 改进启动流程，确保数据库最先启动
