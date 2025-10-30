#!/bin/bash

# 简化版AI交易监控面板启动脚本

echo "🚀 启动简化版AI交易监控面板..."

# 检查Python版本
python_version=$(python3 --version 2>&1)
echo "Python版本: $python_version"

# 检查必要的依赖
echo "📦 检查依赖..."
python3 -c "import flask; print('✅ Flask依赖检查通过')" 2>/dev/null || {
    echo "❌ Flask依赖缺失，正在安装..."
    pip3 install Flask>=2.0.0
}

# 检查历史文件目录
if [ ! -d "history" ]; then
    echo "📁 创建history目录..."
    mkdir -p history
fi

# 创建必要的历史文件
touch history.txt input-history.txt
touch history/think.txt history/input.txt history/output.txt

echo "🌐 启动简化版Web服务器..."
echo "📱 访问地址: http://localhost:5000"
echo "📊 监控面板功能:"
echo "   - ✅ 实时账户余额和盈亏"
echo "   - ✅ 当前持仓状态"
echo "   - ✅ 主要币种价格走势"
echo "   - ✅ AI分析和交易决策显示"
echo "   - ✅ 实时折线图"
echo "   - ✅ 自动读取history/目录的AI内容"
echo ""
echo "💡 特点:"
echo "   - 🔄 数据每30秒自动更新"
echo "   - 📊 保留最近两次AI分析"
echo "   - 📈 价格和盈亏历史图表"
echo "   - 🎨 现代化响应式界面"
echo "   - 📱 支持移动设备"
echo ""
echo "⚡ 启动中..."
echo "🔄 按Ctrl+C停止服务"
echo ""

# 启动简化版监控面板
python3 simple_dashboard.py