#!/bin/bash
# ============================================================
# AI量化竞技场 - 一键启动脚本 (Linux/macOS)
# ============================================================

echo ""
echo "========================================"
echo " 🏆 AI量化竞技场 - 一键启动"
echo "========================================"
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python，请先安装Python 3.10+！"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "✓ Python环境: $PYTHON_VERSION"

# 检查依赖
echo "✓ 检查依赖..."

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 启动后端API（后台）
echo ""
echo "🚀 正在启动后端API..."
python3 api/arena_api.py > api.log 2>&1 &
API_PID=$!
echo "  进程ID: $API_PID"

# 等待API启动
echo "⏳ 等待API启动（3秒）..."
sleep 3

# 测试API是否启动成功
if curl -s http://localhost:8000/api/arena/config > /dev/null 2>&1; then
    echo "✓ API启动成功！"
else
    echo "⚠️ API可能还在启动中..."
fi

# 启动前端服务器（后台）
echo ""
echo "🚀 正在启动前端服务器..."
python3 scripts/serve_frontend.py > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  进程ID: $FRONTEND_PID"

# 等待前端启动
echo "⏳ 等待前端启动（2秒）..."
sleep 2

# 显示访问信息
echo ""
echo "========================================"
echo " ✅ 启动完成！"
echo "========================================"
echo ""
echo "📡 后端API: http://localhost:8000"
echo "🌐 前端界面: http://localhost:8080"
echo ""
echo "💡 提示:"
echo "  - 访问前端界面开始使用"
echo "  - 后端日志: api.log"
echo "  - 前端日志: frontend.log"
echo "  - 停止服务: ./stop.sh 或 Ctrl+C"
echo ""

# 保存进程ID到文件（方便停止）
echo $API_PID > .api.pid
echo $FRONTEND_PID > .frontend.pid

# 尝试打开浏览器
echo "🌐 正在打开浏览器..."
sleep 1

# 根据操作系统选择浏览器命令
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open http://localhost:8080
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8080
    elif command -v gnome-open &> /dev/null; then
        gnome-open http://localhost:8080
    fi
fi

echo ""
echo "✨ 竞技场已就绪！"
echo ""
echo "💡 提示: 按 Ctrl+C 停止服务，或运行 ./stop.sh"
echo ""

# 等待用户中断（Ctrl+C）
trap "echo ''; echo '正在停止服务...'; kill $API_PID $FRONTEND_PID 2>/dev/null; rm -f .api.pid .frontend.pid; echo '服务已停止'; exit 0" INT

# 保持脚本运行
wait
