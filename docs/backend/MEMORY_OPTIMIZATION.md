# 内存泄露优化记录

## 优化时间
2025-12-01

## 发现的问题

### 后端问题
1. **后台任务异常处理不完善**
   - `scheduled_news_update()` 和 `scheduled_price_update()` 缺少 `asyncio.CancelledError` 处理
   - 异常后没有清理资源，可能导致任务泄露

2. **生命周期管理不完善**
   - 任务取消后没有等待完成（`gather`）
   - 数据库连接池未在关闭时释放

3. **开发模式 CPU 占用过高**
   - `--reload` 模式导致持续 ~99% CPU 占用
   - 文件监控开销过大

### 前端问题
1. **WebSocket 连接清理不完善**
   - `disconnect()` 时未清除所有事件监听器
   - `pingInterval` 可能在连接断开后继续运行
   - 订阅的 symbols 未清理

2. **监听器内存泄露**
   - `listeners` Map 中的空 Set 未清理
   - 缺少统一的 `dispose()` 方法

## 已实施的优化

### 后端优化

#### 1. 后台任务异常处理 (`src/api/main.py`)
```python
# 添加 CancelledError 处理
except asyncio.CancelledError:
    logger.info("[Scheduler] Task cancelled")
    break
except Exception as e:
    logger.error(f"[Scheduler] Error: {e}", exc_info=True)
finally:
    await asyncio.sleep(interval)  # 确保异常后也能继续调度
```

#### 2. 生命周期管理优化
```python
# 优雅关闭所有任务
tasks = [news_task, price_task, warmup_task]
for task in tasks:
    task.cancel()
await asyncio.gather(*tasks, return_exceptions=True)

# 关闭数据库连接池
from src.database.models import engine
if engine:
    engine.dispose()
```

#### 3. 生产模式优化 (`scripts/daemon.sh`)
- 移除 `--reload` 标志，降低 CPU 占用从 ~99% 到 <10%
- 开发时使用 `./scripts/dev.sh`，生产/后台使用 `./scripts/daemon.sh`

### 前端优化

#### 1. WebSocket 连接清理 (`web/lib/websocket.ts`)
```typescript
disconnect(): void {
    this._isManualDisconnect = true;
    this.stopPing();
    this.clearConnectionTimeout();
    
    if (this.ws) {
        // 移除所有事件监听器
        this.ws.onclose = null;
        this.ws.onerror = null;
        this.ws.onmessage = null;
        this.ws.onopen = null;
        this.ws.close();
        this.ws = null;
    }
    
    // 清理订阅记录
    this.subscribedSymbols.clear();
    this.setStatus('disconnected');
}
```

#### 2. 监听器自动清理
```typescript
on(type: string, callback: Function): () => void {
    // ...
    return () => {
        const listeners = this.listeners.get(type);
        if (listeners) {
            listeners.delete(callback);
            // 清理空集合
            if (listeners.size === 0) {
                this.listeners.delete(type);
            }
        }
    };
}
```

#### 3. 完整资源释放
```typescript
dispose(): void {
    this.disconnect();
    this.listeners.clear();
    this.statusListeners.clear();
}
```

### 新增工具

#### 内存监控脚本 (`scripts/monitor_memory.py`)
- 实时监控进程内存、CPU、线程数
- 检测内存泄露（增长率超过 50% 告警）
- 检测 CPU 异常（>80% 告警）
- 检测线程泄露（>50 个告警）

使用方法：
```bash
# 监控后端 60 秒
python scripts/monitor_memory.py -i 5 -d 60

# 监控前端
python scripts/monitor_memory.py -p "node.*next" -i 5 -d 60

# 持续监控
python scripts/monitor_memory.py -i 10
```

## 优化效果

### 后端
- **内存**: 27MB 左右，稳定无增长 ✅
- **CPU**: 从 ~99% 降至 <10%（禁用 reload 后）✅
- **线程数**: 1-2 个，无泄露 ✅

### 前端
- **WebSocket 连接**: 断开时完全清理，无残留 ✅
- **监听器**: 自动清理空集合，无累积 ✅

## 最佳实践建议

### 开发环境
```bash
# 使用开发脚本（支持热重载）
./scripts/dev.sh
```

### 生产/后台运行
```bash
# 使用守护脚本（禁用热重载，降低 CPU）
./scripts/daemon.sh start
```

### 定期监控
```bash
# 每小时检查一次内存
watch -n 3600 'python scripts/monitor_memory.py -d 60'
```

## 遗留问题

无已知内存泄露问题。

## 测试验证

- [x] 后端内存稳定性测试（60s）
- [x] 后端 CPU 占用测试
- [x] WebSocket 连接/断开测试
- [x] 前端页面长时间运行测试
- [ ] 压力测试（建议定期执行）

## 相关文件

- `src/api/main.py` - 后台任务优化
- `web/lib/websocket.ts` - WebSocket 资源清理
- `scripts/daemon.sh` - 生产模式优化
- `scripts/monitor_memory.py` - 内存监控工具
