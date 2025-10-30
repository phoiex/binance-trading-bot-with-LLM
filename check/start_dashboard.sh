#!/bin/bash

echo "🚀 启动AI交易监控面板..."
echo "Python版本: $(python --version)"

# 检查依赖
echo "📦 检查依赖..."
python -c "import flask, flask_socketio, yaml" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ 依赖检查通过"
else
    echo "❌ 缺少依赖，请安装: pip install flask flask-socketio pyyaml"
    exit 1
fi

echo "🌐 启动Web服务器..."
echo "📱 访问地址: http://localhost:5001"
echo "📊 监控面板功能:"
echo "   - 实时账户余额和盈亏"
echo "   - 当前持仓状态"
echo "   - AI分析和交易决策"
echo ""
echo "⚡ 数据每30秒自动更新"
echo "🔄 按Ctrl+C停止服务"
echo ""

echo "交易监控面板启动中..."
echo "访问地址: http://localhost:5001"

# 启动监控面板
python web_dashboard.py