#!/usr/bin/env python3
"""
简化版实时交易监控Web界面
展示当前收益、持仓状态、AI思考内容和历史图表
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
from flask import Flask, render_template, jsonify
import threading
import time
import re

app = Flask(__name__)

class SimpleTradingDashboard:
    """简化版交易监控面板"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # 历史数据缓存
        self.price_history = []
        self.pnl_history = []

        # 文件路径
        self.history_file = "/home/xiaoqibpnm/bitbot/history.txt"
        self.input_history_file = "/home/xiaoqibpnm/bitbot/input-history.txt"
        self.think_file = "/home/xiaoqibpnm/bitbot/history/think.txt"
        self.input_file = "/home/xiaoqibpnm/bitbot/history/input.txt"
        self.output_file = "/home/xiaoqibpnm/bitbot/history/output.txt"

        # 模拟数据
        self.mock_data_enabled = True

    def get_mock_account_data(self) -> Dict[str, Any]:
        """获取模拟账户数据"""
        import random
        base_balance = 736.27
        pnl = random.uniform(-50, 100)

        return {
            "total_balance": base_balance + pnl,
            "unrealized_pnl": pnl,
            "available_balance": base_balance * 0.7,
            "total_position_value": abs(pnl) * 10,
            "total_position_pnl": pnl,
            "position_count": 1 if abs(pnl) > 10 else 0,
            "positions": [{
                "symbol": "BTCUSDT",
                "positionAmt": "0.020000" if pnl > 0 else "-0.020000",
                "entryPrice": "115380.0",
                "markPrice": "115500.0",
                "unRealizedProfit": str(pnl)
            }] if abs(pnl) > 10 else [],
            "timestamp": datetime.now().isoformat()
        }

    def get_mock_market_data(self) -> Dict[str, Any]:
        """获取模拟市场数据"""
        import random

        btc_base = 115500
        eth_base = 4140
        sol_base = 200

        return {
            "BTCUSDT": {
                "price": btc_base + random.uniform(-1000, 1000),
                "change_24h": random.uniform(-5, 5),
                "volume_24h": random.uniform(100000, 200000),
                "high_24h": btc_base + 1000,
                "low_24h": btc_base - 1000
            },
            "ETHUSDT": {
                "price": eth_base + random.uniform(-100, 100),
                "change_24h": random.uniform(-3, 3),
                "volume_24h": random.uniform(3000000, 4000000),
                "high_24h": eth_base + 100,
                "low_24h": eth_base - 100
            },
            "SOLUSDT": {
                "price": sol_base + random.uniform(-10, 10),
                "change_24h": random.uniform(-2, 2),
                "volume_24h": random.uniform(20000000, 25000000),
                "high_24h": sol_base + 10,
                "low_24h": sol_base - 10
            }
        }

    def read_file_content(self, file_path: str, max_entries: int = 2) -> List[str]:
        """读取文件内容，返回最近的条目"""
        try:
            if not os.path.exists(file_path):
                return []

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if not content:
                return []

            # 按分隔符分割条目
            entries = re.split(r'={50,}', content)
            entries = [entry.strip() for entry in entries if entry.strip()]

            # 返回最近的条目
            return entries[-max_entries:] if entries else []

        except Exception as e:
            self.logger.error(f"读取文件{file_path}失败: {e}")
            return []

    def get_ai_content(self) -> Dict[str, Any]:
        """获取AI相关内容"""
        try:
            # 读取AI输出内容（最近2条）
            output_content = self.read_file_content(self.output_file, 2)

            # 读取AI输入内容（最近2条）
            input_content = self.read_file_content(self.input_file, 2)

            # 读取AI思考内容（最近2条）
            think_content = self.read_file_content(self.think_file, 2)

            # 解析最新的AI决策
            latest_decisions = []
            if output_content:
                try:
                    # 从输出内容中提取交易决策
                    latest_output = output_content[-1]

                    # 查找JSON部分
                    json_match = re.search(r'\\{.*?"recommendations".*?\\}', latest_output, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        parsed_data = json.loads(json_str)
                        latest_decisions = parsed_data.get('recommendations', [])
                except Exception as e:
                    self.logger.warning(f"解析AI决策失败: {e}")

            # 如果没有真实数据，使用模拟数据
            if not latest_decisions and self.mock_data_enabled:
                latest_decisions = [{
                    "symbol": "BTCUSDT",
                    "action": "long",
                    "confidence": 68,
                    "entry_price": 115511.4,
                    "leverage": 8,
                    "reason": "BTC在多个时间周期均位于关键移动平均线上方，1小时级别趋势强度62.2%显示上升动能"
                }]

            return {
                "output_content": output_content,
                "input_content": input_content,
                "think_content": think_content or ["等待AI思考过程..."] if self.mock_data_enabled else [],
                "latest_decisions": latest_decisions,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"获取AI内容失败: {e}")
            return {"error": str(e)}

    def update_history_data(self):
        """更新历史数据"""
        try:
            timestamp = datetime.now()

            # 获取当前数据
            if self.mock_data_enabled:
                account_data = self.get_mock_account_data()
                market_data = self.get_mock_market_data()
            else:
                # 这里可以集成真实的API调用
                account_data = {"unrealized_pnl": 0}
                market_data = {}

            # 更新盈亏历史
            if "error" not in account_data:
                pnl_point = {
                    "timestamp": timestamp.isoformat(),
                    "total_balance": account_data.get("total_balance", 0),
                    "unrealized_pnl": account_data.get("unrealized_pnl", 0),
                    "total_position_pnl": account_data.get("total_position_pnl", 0)
                }
                self.pnl_history.append(pnl_point)

            # 更新价格历史
            if market_data:
                price_point = {"timestamp": timestamp.isoformat()}
                for symbol, data in market_data.items():
                    if "error" not in data:
                        price_point[symbol] = data.get("price", 0)
                self.price_history.append(price_point)

            # 保持最近100个数据点
            if len(self.pnl_history) > 100:
                self.pnl_history = self.pnl_history[-100:]
            if len(self.price_history) > 100:
                self.price_history = self.price_history[-100:]

        except Exception as e:
            self.logger.error(f"更新历史数据失败: {e}")

# 全局实例
dashboard = SimpleTradingDashboard()

@app.route('/')
def index():
    """主页面"""
    return render_template('dashboard.html')

@app.route('/api/account')
def api_account():
    """账户信息API"""
    if dashboard.mock_data_enabled:
        return jsonify(dashboard.get_mock_account_data())
    else:
        # 这里可以添加真实API调用
        return jsonify({"error": "真实API未配置"})

@app.route('/api/market')
def api_market():
    """市场数据API"""
    if dashboard.mock_data_enabled:
        return jsonify(dashboard.get_mock_market_data())
    else:
        # 这里可以添加真实API调用
        return jsonify({"error": "真实API未配置"})

@app.route('/api/ai_content')
def api_ai_content():
    """AI内容API"""
    return jsonify(dashboard.get_ai_content())

@app.route('/api/history/prices')
def api_price_history():
    """价格历史API"""
    return jsonify(dashboard.price_history[-50:])  # 最近50个数据点

@app.route('/api/history/pnl')
def api_pnl_history():
    """盈亏历史API"""
    return jsonify(dashboard.pnl_history[-50:])  # 最近50个数据点

def background_update():
    """后台数据更新任务"""
    while True:
        try:
            dashboard.update_history_data()
            time.sleep(30)  # 每30秒更新一次
        except Exception as e:
            dashboard.logger.error(f"后台更新失败: {e}")
            time.sleep(60)

def main():
    """主函数"""
    print("🚀 启动简化版交易监控面板...")

    # 启动后台更新线程
    update_thread = threading.Thread(target=background_update, daemon=True)
    update_thread.start()

    print("✅ 交易监控面板启动成功！")
    print("🌐 访问地址: http://localhost:5000")
    print("📊 功能包括:")
    print("   - 实时账户余额和盈亏")
    print("   - 当前持仓状态")
    print("   - 主要币种价格走势")
    print("   - AI分析和交易决策")
    print("   - 实时折线图")
    print("")
    print("⚡ 数据每30秒自动更新")
    print("📁 AI内容来自history/目录下的文件")
    print("🔄 按Ctrl+C停止服务")
    print("")

    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()