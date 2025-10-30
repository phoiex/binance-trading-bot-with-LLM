#!/usr/bin/env python3
"""
精简版期货交易Bot
专注于杠杆和合约交易，集成Binance Futures API和DeepSeek AI

使用方法:
python main.py --strategy aggressive --execute
"""

import os
import sys
import asyncio
import argparse
import logging
import yaml
import json
from datetime import datetime
from typing import Dict, Any, Optional

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_bot.strategies.futures_trading_engine import FuturesTradingEngine
from trading_bot.utils.risk_manager import SecurityChecker


class FuturesBot:
    """期货交易Bot"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = None
        self.futures_engine = None
        self.security_checker = None
        self.logger = None
        self.running = False
        # 托管模式的会话跟踪
        self.session_start_time = None
        self.session_call_count = 0

    async def initialize(self):
        """初始化Bot"""
        try:
            await self._load_config()
            self._setup_logging()
            self.security_checker = SecurityChecker()
            await self._validate_config()
            await self._initialize_futures_engine()
            self.logger.info("期货交易Bot初始化完成")
        except Exception as e:
            print(f"初始化失败: {e}")
            raise

    async def _load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"加载配置文件失败: {e}")

    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))

        log_file = log_config.get('file', 'logs/futures_bot.log')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    async def _validate_config(self):
        """验证配置"""
        binance_config = self.config.get('apis', {}).get('binance', {})
        api_key = binance_config.get('api_key', '')
        api_secret = binance_config.get('api_secret', '')

        if 'your_' in api_key or 'your_' in api_secret:
            raise Exception("请在配置文件中设置正确的API密钥")

        is_valid, message = self.security_checker.validate_api_keys(api_key, api_secret)
        if not is_valid:
            raise Exception(f"API密钥验证失败: {message}")

        testnet = binance_config.get('testnet', True)
        is_safe, message = self.security_checker.check_network_security(testnet)
        if not is_safe:
            self.logger.warning(message)

        self.logger.info("配置验证通过")


    async def _initialize_futures_engine(self):
        """初始化期货交易引擎"""
        binance_config = self.config.get('apis', {}).get('binance', {})
        deepseek_config = self.config.get('apis', {}).get('deepseek', {})
        position_config = self.config.get('trading', {}).get('position_management', {})
        futures_config = self.config.get('trading', {}).get('futures', {})

        self.futures_engine = FuturesTradingEngine(
            binance_api_key=binance_config.get('api_key'),
            binance_api_secret=binance_config.get('api_secret'),
            deepseek_api_key=deepseek_config.get('api_key'),
            config=self.config,
            testnet=binance_config.get('testnet', True),
            max_position_size=position_config.get('max_position_size', 1.0),
            default_leverage=futures_config.get('default_leverage', 3),
            stop_loss_percent=position_config.get('stop_loss_percent', 0.05),
            take_profit_percent=position_config.get('take_profit_percent', 0.15)
        )
        await self.futures_engine.__aenter__()


    async def analyze_and_trade_with_session(self, strategy_name: str = "aggressive", execute: bool = False) -> Dict[str, Any]:
        """带会话跟踪的分析和交易"""
        try:
            # 更新会话计数
            self.session_call_count += 1

            # 计算已运行时间
            elapsed_seconds = int((datetime.now() - self.session_start_time).total_seconds())
            elapsed_minutes = elapsed_seconds // 60

            # 构建带会话信息的提示（不再注入历史交易结果；保留“思考过程”要求）
            session_context = (
                f"自您开始交易以来已经过去了{elapsed_minutes}分钟。"
                f"当前时间是{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}，"
                f"您已被调用{self.session_call_count}次。"
                "\n\n重要：请在回复的最后包含一个\"思考过程\"部分，详细说明您的分析逻辑和决策理由。"
            )

            symbols = self.config.get('trading', {}).get('symbols', ["BTCUSDT", "ETHUSDT", "SOLUSDT"])

            self.logger.info(f"开始执行期货市场分析 (会话第{self.session_call_count}次)，策略: {strategy_name}")

            # 执行综合市场分析
            result = await self.futures_engine.analyze_comprehensive_market(
                user_prompt=session_context,
                symbols=symbols,
                timeframes=["1m", "15m", "1h", "1d", "1M"]
            )

            # 添加会话信息到结果
            result['session_info'] = {
                'call_count': self.session_call_count,
                'elapsed_minutes': elapsed_minutes,
                'session_start': self.session_start_time.isoformat(),
                'current_time': datetime.now().isoformat()
            }

            # 执行交易
            if execute:
                trading_decisions = result.get('trading_decisions', []) or result.get('recommendations', [])
                if trading_decisions:
                    self.logger.info("开始执行期货交易")
                    execution_results = await self.futures_engine.execute_futures_trading_decisions(
                        decisions=trading_decisions,
                        dry_run=self.config.get('trading', {}).get('mode', {}).get('dry_run', False)
                    )
                    result['execution_results'] = execution_results

                # 无论是否有决策执行，都做一次遗留TP/SL清理（仅真实交易模式）
                try:
                    if not self.config.get('trading', {}).get('mode', {}).get('dry_run', False):
                        await self.futures_engine.cleanup_orphan_tp_sl_orders()
                except Exception as e:
                    self.logger.warning(f"清理遗留TP/SL失败: {e}")

            # 保存结果
            if self.config.get('data_storage', {}).get('save_analysis', True):
                await self._save_result(result, f"{strategy_name}_session_{self.session_call_count}")

            return result

        except Exception as e:
            self.logger.error(f"会话分析和交易失败: {e}")
            return {"error": str(e)}


    async def run(self, strategy_name: str = "aggressive", execute: bool = False):
        """自动交易模式 - 每15分钟自动交易"""
        self.running = True
        self.session_start_time = datetime.now()
        self.session_call_count = 0

        runtime_config = self.config.get('runtime', {})
        analysis_interval = 900  # 15分钟 = 900秒
        max_runtime = runtime_config.get('max_runtime', 86400)

        self.logger.info("🤖 开始自动交易模式 - 每15分钟智能分析和交易")

        try:
            while self.running:
                # 检查最大运行时间
                elapsed_time = (datetime.now() - self.session_start_time).total_seconds()
                if elapsed_time > max_runtime:
                    self.logger.info("达到最大运行时间，停止自动交易")
                    break

                # 执行分析和交易
                result = await self.analyze_and_trade_with_session(strategy_name, execute)
                self._print_summary(result)

                # 等待下次执行
                self.logger.info("⏱️ 等待15分钟后进行下次自动分析...")
                await asyncio.sleep(analysis_interval)

        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在停止自动交易...")
        except Exception as e:
            self.logger.error(f"自动交易模式运行出错: {e}")
        finally:
            self.running = False
            await self.cleanup()

    def _get_strategy_prompt(self, strategy_name: str) -> str:
        """获取策略提示（已禁用，交给AI自主决策）"""
        return ""

    # 已移除读取历史决策并注入到提示的逻辑

    async def _save_result(self, result: Dict[str, Any], strategy_name: str):
        """保存分析结果"""
        try:
            data_dir = self.config.get('data_storage', {}).get('data_dir', 'data')
            os.makedirs(data_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{data_dir}/futures_analysis_{strategy_name}_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)

            self.logger.info(f"结果已保存到: {filename}")
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")

    def _print_summary(self, result: Dict[str, Any]):
        """打印交易摘要"""
        if 'error' in result:
            print(f"❌ 分析失败: {result['error']}")
            return

        decisions = result.get('trading_decisions', []) or result.get('recommendations', [])
        executable_decisions = [d for d in decisions if d.get('should_execute', False)]
        execution_results = result.get('execution_results', [])

        print(f"\n📊 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💡 期货交易建议: {len(decisions)} 个")
        print(f"✅ 可执行: {len(executable_decisions)} 个")
        print(f"🔄 已执行: {len(execution_results)} 个")

        for decision in executable_decisions:
            symbol = decision.get('symbol', '未知')
            action = decision.get('action', '').upper()
            confidence = decision.get('confidence', 0)
            leverage = decision.get('leverage', 1)
            print(f"   {symbol}: {action} {leverage}x (信心度: {confidence}%)")

    async def cleanup(self):
        """清理资源"""
        if self.futures_engine:
            await self.futures_engine.__aexit__(None, None, None)
        self.logger.info("资源清理完成")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='精简版期货交易Bot')
    parser.add_argument('--config', default='trading_bot/config/config.yaml', help='配置文件路径')
    parser.add_argument('--strategy', default='default',
                       help='策略标签（仅用于标记/记录，不影响AI提示）')
    parser.add_argument('--execute', action='store_true', help='执行实际交易')

    args = parser.parse_args()

    bot = FuturesBot(args.config)

    try:
        await bot.initialize()
        print(f"🤖 开始自动交易模式 - 每15分钟智能分析，策略: {args.strategy}")
        await bot.run(args.strategy, args.execute)

    except Exception as e:
        print(f"❌ 运行失败: {e}")
        return 1
    finally:
        await bot.cleanup()

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        sys.exit(0)
