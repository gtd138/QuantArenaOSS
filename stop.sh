#!/bin/bash
# ============================================================
# AI量化竞技场 - 停止脚本 (Linux/macOS)
# ============================================================

echo ""
echo "========================================"
echo " 🛑 停止 AI量化竞技场"
echo "========================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 从PID文件读取进程ID
if [ -f .api.pid ]; then
    API_PID=$(cat .api.pid)
    if kill -0 $API_PID 2>/dev/null; then
        echo "🔴 停止后端API (PID: $API_PID)..."
        kill $API_PID
    else
        echo "⚠️ 后端API进程不存在"
    fi
    rm -f .api.pid
else
    # 尝试通过端口查找进程
    API_PID=$(lsof -ti:8000 2>/dev/null)
    if [ ! -z "$API_PID" ]; then
        echo "🔴 停止后端API (PID: $API_PID)..."
        kill $API_PID
    else
        echo "⚠️ 未找到后端API进程"
    fi
fi

if [ -f .frontend.pid ]; then
    FRONTEND_PID=$(cat .frontend.pid)
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "🔴 停止前端服务器 (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID
    else
        echo "⚠️ 前端服务器进程不存在"
    fi
    rm -f .frontend.pid
else
    # 尝试通过端口查找进程
    FRONTEND_PID=$(lsof -ti:8080 2>/dev/null)
    if [ ! -z "$FRONTEND_PID" ]; then
        echo "🔴 停止前端服务器 (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID
    else
        echo "⚠️ 未找到前端服务器进程"
    fi
fi

# 等待进程完全停止
sleep 1

echo ""
echo "✅ 所有服务已停止"
echo ""
