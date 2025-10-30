#!/usr/bin/env python3
"""
修复版实时交易监控Web界面
解决异步上下文管理器问题
"""

import os
import sys
import json
import asyncio
import logging
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
import re

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__), 'python-binance-master/python-binance-master'))

from trading_bot.data.futures_data import FuturesDataManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trading_dashboard_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

class TradingDashboard:
    """交易监控面板"""

    def __init__(self):
        self.config = self._load_config()
        self.futures_data_manager = None
        self.logger = logging.getLogger(__name__)

        # 数据缓存
        self._cached_account_data = {"error": "初始化中..."}
        self._cached_market_data = {"error": "初始化中..."}
        self._cached_ai_content = {"error": "初始化中..."}

        # 历史数据缓存
        self.price_history = []
        self.pnl_history = []

        # 文件路径
        self.history_file = "/home/xiaoqibpnm/bitbot/history.txt"
        self.think_file = "/home/xiaoqibpnm/bitbot/history/think.txt"
        self.input_file = "/home/xiaoqibpnm/bitbot/history/input.txt"
        self.output_file = "/home/xiaoqibpnm/bitbot/history/output.txt"
        # 报警文件路径
        self.alarm_file = os.path.join(os.path.dirname(__file__), 'alarm.txt')

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            config_path = "trading_bot/config/config.yaml"
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"加载配置失败: {e}")
            return {}

    async def initialize(self):
        """初始化数据管理器"""
        try:
            binance_config = self.config.get('apis', {}).get('binance', {})
            api_key = binance_config.get('api_key')
            api_secret = binance_config.get('api_secret')
            testnet = binance_config.get('testnet', True)

            if not api_key or not api_secret:
                self.logger.error("缺少API密钥配置")
                return False

            self.futures_data_manager = FuturesDataManager(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet
            )
            await self.futures_data_manager.__aenter__()
            self.logger.info("交易监控面板初始化成功")
            return True

        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            return False

    async def get_account_summary(self) -> Dict[str, Any]:
        """获取账户摘要信息"""
        try:
            if not self.futures_data_manager:
                return {"error": "数据管理器未初始化"}

            # 获取账户信息
            account_info = await self.futures_data_manager.get_futures_account_info()
            # 获取当前持仓
            positions = await self.futures_data_manager.get_futures_positions()

            # 调试：记录原始数据
            self.logger.info(f"原始持仓数据长度: {len(positions) if positions else 'None'}")
            if positions:
                for i, pos in enumerate(positions):
                    if i < 3:  # 只记录前3个
                        self.logger.info(f"持仓 {i}: {pos}")

            # 计算总资产 - 兼容不同的字段名格式
            total_balance = float(account_info.get('total_wallet_balance',
                                                 account_info.get('totalWalletBalance', 0)))
            # 兼容多种字段命名（数据管理器与Binance原始返回）
            unrealized_pnl = float(
                account_info.get('total_unrealized_pnl',
                account_info.get('totalUnrealizedPnl',
                account_info.get('totalUnrealizedProfit', 0)))
            )
            available_balance = float(account_info.get('available_balance',
                                                     account_info.get('availableBalance', 0)))

            # 处理持仓信息
            position_list = []
            total_position_value = 0

            for pos in positions:
                # 兼容 FuturesDataManager 格式化后的键与 Binance 原始键
                raw_amt = pos.get('positionAmt')
                fmt_amt = pos.get('position_amount')
                position_amt = float(fmt_amt if fmt_amt is not None else (raw_amt or 0))

                self.logger.info(f"检查持仓: {pos.get('symbol', 'N/A')} - 数量: {position_amt}")

                if position_amt != 0:
                    raw_mark = pos.get('markPrice')
                    fmt_mark = pos.get('mark_price')
                    mark_price = float(fmt_mark if fmt_mark is not None else (raw_mark or 0))

                    raw_entry = pos.get('entryPrice')
                    fmt_entry = pos.get('entry_price')
                    entry_price = float(fmt_entry if fmt_entry is not None else (raw_entry or 0))

                    # unrealized PnL 兼容多种命名
                    upnl_keys = [
                        'unrealized_pnl', 'unRealizedPnL', 'unRealizedProfit', 'unrealizedProfit'
                    ]
                    upnl_val = 0.0
                    for k in upnl_keys:
                        if k in pos and pos[k] is not None:
                            try:
                                upnl_val = float(pos[k])
                                break
                            except Exception:
                                pass

                    position_value = abs(position_amt * mark_price)
                    total_position_value += position_value

                    self.logger.info(
                        f"发现持仓: {pos.get('symbol', '')} - 数量: {position_amt}, 入场: {entry_price}, 价格: {mark_price}, PnL: {upnl_val}"
                    )

                    # 同时返回两套键，兼容现有前端模板与未来扩展
                    position_list.append({
                        # 现有前端模板期望的键名（Binance风格）
                        'symbol': pos.get('symbol', ''),
                        'positionAmt': position_amt,
                        'entryPrice': entry_price,
                        'markPrice': mark_price,
                        'unRealizedProfit': upnl_val,
                        'positionSide': pos.get('positionSide') or pos.get('position_side'),
                        # 扩展键名（语义化）
                        'amount': position_amt,
                        'entry_price': entry_price,
                        'mark_price': mark_price,
                        'unrealized_pnl': upnl_val,
                        'side': 'LONG' if position_amt > 0 else 'SHORT',
                        'value': position_value
                    })

            return {
                'total_balance': total_balance,
                'unrealized_pnl': unrealized_pnl,
                'available_balance': available_balance,
                'positions': position_list,
                'total_position_value': total_position_value,
                'position_count': len(position_list),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"获取账户摘要失败: {e}")
            return {"error": str(e)}

    async def get_market_data(self) -> Dict[str, Any]:
        """获取市场数据"""
        try:
            if not self.futures_data_manager:
                return {"error": "数据管理器未初始化"}

            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
            market_data = {}

            for symbol in symbols:
                try:
                    # 获取基础价格信息
                    ticker = await self.futures_data_manager.client.futures_ticker(symbol=symbol)
                    market_data[symbol] = {
                        "price": float(ticker.get('lastPrice', 0)),
                        "change": float(ticker.get('priceChangePercent', 0)),
                        "volume": float(ticker.get('volume', 0)),
                        "high": float(ticker.get('highPrice', 0)),
                        "low": float(ticker.get('lowPrice', 0))
                    }
                except Exception as e:
                    self.logger.error(f"获取{symbol}数据失败: {e}")
                    market_data[symbol] = {"error": str(e)}

            return {
                'symbols': market_data,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"获取市场数据失败: {e}")
            return {"error": str(e)}

    def get_ai_content(self) -> Dict[str, Any]:
        """获取AI相关内容"""
        try:
            # 读取最新的AI思考内容
            think_content = self.read_file_content(self.think_file, 5)

            # 提取有意义的思考内容（排除分隔线和标题）
            meaningful_think = ""
            if think_content:
                for content in reversed(think_content):
                    if content and not content.startswith('=') and not content.startswith('[') and len(content) > 50:
                        meaningful_think = content[:500] + "..." if len(content) > 500 else content
                        break

            if not meaningful_think:
                meaningful_think = "AI思考过程加载中..."

            # 读取最新的输出内容（多取一些段落，确保能解析到5条最新决策）
            output_content = self.read_file_content(self.output_file, 10)

            # 尝试解析最新决策
            latest_decisions = []
            if output_content:
                try:
                    # 合并所有输出内容来查找JSON
                    full_output = '\n'.join(output_content)

                    # 查找recommendations部分 - 更新的正则表达式
                    if '"recommendations"' in full_output:
                        import re
                        import json

                        # 尝试提取每个recommendation对象
                        pattern = r'\{\s*"symbol":\s*"([^"]*)"[^}]*"action":\s*"([^"]*)"[^}]*"confidence":\s*(\d+)[^}]*"entry_price":\s*([0-9.]+)[^}]*"leverage":\s*(\d+)[^}]*"reason":\s*"([^"]*)"[^}]*\}'
                        matches = re.findall(pattern, full_output, re.DOTALL)

                        for match in matches:
                            latest_decisions.append({
                                'symbol': match[0],
                                'action': match[1],
                                'confidence': int(match[2]),
                                'entry_price': float(match[3]),
                                'leverage': int(match[4]),
                                # 展示完整理由
                                'reason': match[5]
                            })

                        # 如果正则没匹配到，尝试简化的匹配
                        if not latest_decisions:
                            simple_pattern = r'"symbol":\s*"([^"]*)".*?"action":\s*"([^"]*)".*?"confidence":\s*(\d+)'
                            simple_matches = re.findall(simple_pattern, full_output, re.DOTALL)
                            for match in simple_matches:
                                latest_decisions.append({
                                    'symbol': match[0],
                                    'action': match[1],
                                    'confidence': int(match[2]),
                                    'entry_price': 0,
                                    'leverage': 1,
                                    'reason': "详见完整分析"
                                })

                        # 仅保留最新5条，并按从新到旧排序
                        if latest_decisions:
                            latest_decisions = latest_decisions[-5:][::-1]

                except Exception as e:
                    self.logger.warning(f"解析AI决策失败: {e}")

            # 解析think.txt中的“最终交易判断”最近5条
            final_judgments: List[str] = []
            try:
                if os.path.exists(self.think_file):
                    with open(self.think_file, 'r', encoding='utf-8') as tf:
                        think_text = tf.read()
                    # 捕获“最终交易判断:”后的内容块，直到下一个分隔线或下一段
                    # 使用非贪婪匹配，并以分隔符或文件末尾为终止
                    fj_pattern = r"最终交易判断:\s*[-=—_]*\s*(.+?)(?=\n\s*(?:=|-){3,}|\n\[\d{4}-\d{2}-\d{2}|\Z)"
                    blocks = re.findall(fj_pattern, think_text, re.DOTALL)
                    # 清洗并提取最后5条
                    cleaned: List[str] = []
                    for b in blocks:
                        s = b.strip()
                        if s:
                            cleaned.append(s)
                    if cleaned:
                        final_judgments = cleaned[-5:][::-1]  # 最新在前
            except Exception as e:
                self.logger.warning(f"解析最终交易判断失败: {e}")

            return {
                "think_content": meaningful_think,
                "latest_decisions": latest_decisions,
                "decisions_count": len(latest_decisions),
                "final_judgments": final_judgments,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"获取AI内容失败: {e}")
            return {"error": str(e)}

    def read_file_content(self, file_path: str, max_entries: int = 5) -> List[str]:
        """读取文件内容"""
        try:
            if not os.path.exists(file_path):
                return []

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if not content:
                return []

            # 按段落分割
            entries = [entry.strip() for entry in content.split('\n\n') if entry.strip()]
            return entries[-max_entries:] if entries else []

        except Exception as e:
            self.logger.error(f"读取文件{file_path}失败: {e}")
            return []

    def update_price_history(self, market_data: Dict[str, Any]):
        """更新价格历史"""
        try:
            if 'symbols' in market_data:
                timestamp = datetime.now().isoformat()
                price_point = {'timestamp': timestamp}

                for symbol, data in market_data['symbols'].items():
                    if 'price' in data:
                        price_point[symbol] = data['price']

                self.price_history.append(price_point)
                # 保持最近100个数据点
                if len(self.price_history) > 100:
                    self.price_history = self.price_history[-100:]
        except Exception as e:
            self.logger.error(f"更新价格历史失败: {e}")

    def update_pnl_history(self, account_data: Dict[str, Any]):
        """更新盈亏历史"""
        try:
            if 'total_balance' in account_data and 'unrealized_pnl' in account_data:
                timestamp = datetime.now().isoformat()
                pnl_point = {
                    'timestamp': timestamp,
                    'total_balance': account_data['total_balance'],
                    'unrealized_pnl': account_data['unrealized_pnl']
                }

                self.pnl_history.append(pnl_point)
                # 保持最近100个数据点
                if len(self.pnl_history) > 100:
                    self.pnl_history = self.pnl_history[-100:]
        except Exception as e:
            self.logger.error(f"更新盈亏历史失败: {e}")

# 全局实例
dashboard = TradingDashboard()

# Flask路由
@app.route('/')
def index():
    """主页面"""
    return render_template('dashboard.html')

@app.route('/api/account')
def api_account():
    """账户信息API"""
    try:
        return jsonify(dashboard._cached_account_data)
    except Exception as e:
        return jsonify({"error": f"获取账户数据失败: {str(e)}"})

@app.route('/api/market')
def api_market():
    """市场数据API"""
    try:
        return jsonify(dashboard._cached_market_data)
    except Exception as e:
        return jsonify({"error": f"获取市场数据失败: {str(e)}"})

@app.route('/api/ai_content')
def api_ai_content():
    """AI内容API"""
    try:
        ai_content = dashboard.get_ai_content()
        return jsonify(ai_content)
    except Exception as e:
        return jsonify({"error": f"获取AI内容失败: {str(e)}"})

@app.route('/api/history/prices')
def api_price_history():
    """价格历史API"""
    try:
        return jsonify(dashboard.price_history[-50:])  # 最近50个数据点
    except Exception as e:
        return jsonify({"error": f"获取价格历史失败: {str(e)}"})

@app.route('/api/history/pnl')
def api_pnl_history():
    """盈亏历史API"""
    try:
        return jsonify(dashboard.pnl_history[-50:])  # 最近50个数据点
    except Exception as e:
        return jsonify({"error": f"获取盈亏历史失败: {str(e)}"})

@app.route('/api/alerts')
def api_alerts():
    try:
        alarm_path = os.path.join(os.path.dirname(__file__), 'alarm.txt')
        if not os.path.exists(alarm_path):
            return jsonify([])
        # 读取末尾最近50条
        with open(alarm_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-50:]
        alerts = [line.strip() for line in lines if line.strip()]
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": f"获取报警失败: {str(e)}"})

# WebSocket事件
@socketio.on('connect')
def handle_connect():
    """WebSocket连接处理"""
    print('客户端已连接')

@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket断开处理"""
    print('客户端已断开')

async def background_update_async():
    """异步后台更新任务"""
    while True:
        try:
            # 获取最新数据
            account_data = await dashboard.get_account_summary()
            market_data = await dashboard.get_market_data()
            ai_content = dashboard.get_ai_content()

            # 缓存数据
            dashboard._cached_account_data = account_data
            dashboard._cached_market_data = market_data
            dashboard._cached_ai_content = ai_content

            # 更新历史数据
            dashboard.update_pnl_history(account_data)
            dashboard.update_price_history(market_data)

            # 通过WebSocket发送更新
            socketio.emit('data_update', {
                'account': account_data,
                'market': market_data,
                'ai_content': ai_content,
                'price_history': dashboard.price_history[-20:],
                'pnl_history': dashboard.pnl_history[-20:]
            })

            # 等待30秒
            await asyncio.sleep(30)

        except Exception as e:
            dashboard.logger.error(f"后台更新失败: {e}")
            await asyncio.sleep(60)  # 出错时等待更长时间

def run_flask():
    """运行Flask应用"""
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)

async def main():
    """主函数"""
    # 初始化监控面板
    success = await dashboard.initialize()
    if not success:
        print("❌ 初始化失败，退出程序")
        return

    print("✅ 监控面板初始化成功")

    # 启动Flask应用（在子线程中）
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("🌐 Web服务器已启动")
    print("📱 访问地址: http://localhost:5001")

    # 启动后台更新任务
    await background_update_async()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  监控面板已停止")
