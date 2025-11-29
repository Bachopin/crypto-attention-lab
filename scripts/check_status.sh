#!/bin/bash
# 快速检查系统状态

cd "$(dirname "$0")/.."

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 系统状态检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 检查进程
echo "📋 运行中的服务:"
if pgrep -f "uvicorn src.api.main" > /dev/null; then
    echo "  ✅ 后端 API (PID: $(pgrep -f 'uvicorn src.api.main' | head -1))"
else
    echo "  ❌ 后端 API 未运行"
fi

if pgrep -f "next dev" > /dev/null; then
    echo "  ✅ 前端 Web (PID: $(pgrep -f 'next dev' | head -1))"
else
    echo "  ❌ 前端 Web 未运行"
fi

echo ""

# 检查端口
echo "🌐 端口监听:"
if lsof -i :8000 > /dev/null 2>&1; then
    echo "  ✅ 8000 (后端 API)"
else
    echo "  ❌ 8000 未监听"
fi

if lsof -i :3000 > /dev/null 2>&1; then
    echo "  ✅ 3000 (前端 Web)"
else
    echo "  ❌ 3000 未监听"
fi

echo ""

# 测试健康检查
echo "💓 健康检查:"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✅ 后端 API 健康"
else
    echo "  ❌ 后端 API 无响应"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -qE "200|302"; then
    echo "  ✅ 前端 Web 可访问"
else
    echo "  ❌ 前端 Web 无响应"
fi

echo ""

# 显示日志路径
echo "📝 日志文件:"
echo "  后端: logs/api.log"
echo "  前端: logs/frontend.log"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔗 快速链接:"
echo "  前端: http://localhost:3000"
echo "  API文档: http://localhost:8000/docs"
echo "  健康检查: http://localhost:8000/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
