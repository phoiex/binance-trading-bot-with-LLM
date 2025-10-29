"""
增强版历史记录管理器
负责记录交易历史和模型输入输出到独立的txt文件
"""

import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import logging


class EnhancedHistoryLogger:
    """增强版历史记录记录器"""

    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.history_dir = os.path.join(base_dir, "history")
        self.history_file = os.path.join(base_dir, "history.txt")
        self.input_history_file = os.path.join(base_dir, "input-history.txt")

        # 新的AI输入输出文件
        self.ai_input_file = os.path.join(self.history_dir, "input.txt")
        self.ai_output_file = os.path.join(self.history_dir, "output.txt")
        self.ai_think_file = os.path.join(self.history_dir, "think.txt")

        self.logger = logging.getLogger(__name__)

        # 确保目录存在
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(self.history_dir, exist_ok=True)

        # 初始化文件（如果不存在）
        self._initialize_files()

    def _initialize_files(self):
        """初始化历史文件"""
        # 初始化 history.txt
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', encoding='utf-8') as f:
                f.write("=== 交易历史和模型输出记录 ===\n")
                f.write(f"创建时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write("=" * 50 + "\n\n")

        # 初始化 input-history.txt
        if not os.path.exists(self.input_history_file):
            with open(self.input_history_file, 'w', encoding='utf-8') as f:
                f.write("=== 模型输入历史记录 ===\n")
                f.write(f"创建时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write("=" * 50 + "\n\n")

        # 初始化 history/input.txt
        if not os.path.exists(self.ai_input_file):
            with open(self.ai_input_file, 'w', encoding='utf-8') as f:
                f.write("=== AI模型输入数据记录 ===\n")
                f.write(f"创建时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write("说明: 此文件记录最终发送给AI模型的完整输入数据\n")
                f.write("=" * 50 + "\n\n")

        # 初始化 history/output.txt
        if not os.path.exists(self.ai_output_file):
            with open(self.ai_output_file, 'w', encoding='utf-8') as f:
                f.write("=== AI模型输出数据记录 ===\n")
                f.write(f"创建时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write("说明: 此文件记录AI模型返回的原始和处理后的输出数据\n")
                f.write("=" * 50 + "\n\n")

        # 初始化 history/think.txt
        if not os.path.exists(self.ai_think_file):
            with open(self.ai_think_file, 'w', encoding='utf-8') as f:
                f.write("=== AI交易判断思考过程记录 ===\n")
                f.write(f"创建时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write("说明: 此文件记录AI分析师的思考过程和判断依据\n")
                f.write("=" * 50 + "\n\n")

    async def log_model_input(self,
                             prompt_type: str,
                             user_prompt: str,
                             system_prompt: str,
                             market_data: Optional[Dict[str, Any]] = None,
                             symbols: Optional[List[str]] = None,
                             additional_context: Optional[Dict[str, Any]] = None):
        """
        记录模型输入到input-history.txt

        Args:
            prompt_type: 提示类型 (market_analysis, trading_decision, etc.)
            user_prompt: 用户提示
            system_prompt: 系统提示
            market_data: 市场数据
            symbols: 交易币种
            additional_context: 额外上下文信息
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.input_history_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] 模型输入记录\n")
                f.write(f"提示类型: {prompt_type}\n")
                f.write(f"交易币种: {', '.join(symbols) if symbols else 'N/A'}\n")
                f.write("-" * 30 + "\n")

                f.write("用户提示:\n")
                f.write(f"{user_prompt}\n\n")

                f.write("系统提示:\n")
                f.write(f"{system_prompt}\n\n")

                if market_data:
                    f.write("市场数据摘要:\n")
                    # 记录关键市场数据信息，避免文件过大
                    summary = self._generate_market_data_summary(market_data)
                    f.write(summary)
                    f.write("\n")

                if additional_context:
                    f.write("额外上下文:\n")
                    f.write(f"{json.dumps(additional_context, indent=2, ensure_ascii=False)}\n\n")

                f.write("=" * 60 + "\n\n")

            self.logger.info(f"模型输入已记录到 {self.input_history_file}")

        except Exception as e:
            self.logger.error(f"记录模型输入失败: {e}")

    async def log_ai_input(self,
                          system_prompt: str,
                          user_prompt: str,
                          analysis_context: Optional[Dict[str, Any]] = None):
        """
        记录最终发送给AI的完整输入数据到 history/input.txt

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            analysis_context: 分析上下文信息
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.ai_input_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] AI模型输入\n")
                f.write("=" * 60 + "\n\n")

                if analysis_context:
                    f.write("分析上下文:\n")
                    f.write(json.dumps(analysis_context, indent=2, ensure_ascii=False))
                    f.write("\n\n")

                f.write("系统提示词:\n")
                f.write("-" * 30 + "\n")
                f.write(system_prompt)
                f.write("\n\n")

                f.write("用户提示词:\n")
                f.write("-" * 30 + "\n")
                f.write(user_prompt)
                f.write("\n\n")

                f.write("=" * 80 + "\n\n")

            self.logger.info(f"AI输入数据已记录到 {self.ai_input_file}")

        except Exception as e:
            self.logger.error(f"记录AI输入数据失败: {e}")

    async def log_ai_output(self,
                           raw_response: Dict[str, Any],
                           parsed_result: Optional[Dict[str, Any]] = None,
                           processing_time: Optional[float] = None,
                           error_info: Optional[str] = None):
        """
        记录AI模型的输出数据到 history/output.txt

        Args:
            raw_response: API原始响应
            parsed_result: 解析后的结果
            processing_time: 处理时间
            error_info: 错误信息（如果有）
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.ai_output_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] AI模型输出\n")
                f.write("=" * 60 + "\n\n")

                if processing_time:
                    f.write(f"处理时间: {processing_time:.2f} 秒\n\n")

                if error_info:
                    f.write("错误信息:\n")
                    f.write(f"{error_info}\n\n")

                f.write("原始API响应:\n")
                f.write("-" * 30 + "\n")
                f.write(json.dumps(raw_response, indent=2, ensure_ascii=False))
                f.write("\n\n")

                if parsed_result:
                    f.write("解析后结果:\n")
                    f.write("-" * 30 + "\n")
                    f.write(json.dumps(parsed_result, indent=2, ensure_ascii=False))
                    f.write("\n\n")

                f.write("=" * 80 + "\n\n")

            self.logger.info(f"AI输出数据已记录到 {self.ai_output_file}")

        except Exception as e:
            self.logger.error(f"记录AI输出数据失败: {e}")

    async def log_ai_thinking(self,
                             session_info: Dict[str, Any],
                             market_summary: str,
                             reasoning_process: str,
                             final_decision: str):
        """
        记录AI的思考过程到 history/think.txt

        Args:
            session_info: 会话信息（开始时间、调用次数等）
            market_summary: 市场状况摘要
            reasoning_process: AI的推理过程
            final_decision: 最终决策
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.ai_think_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] AI交易判断思考过程\n")
                f.write("=" * 60 + "\n\n")

                f.write("会话信息:\n")
                f.write(f"- 交易开始时间: {session_info.get('start_time', 'N/A')}\n")
                f.write(f"- 已运行时长: {session_info.get('elapsed_minutes', 0)} 分钟\n")
                f.write(f"- 调用次数: {session_info.get('call_count', 0)} 次\n")
                f.write(f"- 当前时间: {timestamp}\n\n")

                f.write("市场状况摘要:\n")
                f.write("-" * 30 + "\n")
                f.write(market_summary)
                f.write("\n\n")

                f.write("AI分析师思考过程:\n")
                f.write("-" * 30 + "\n")
                f.write(reasoning_process)
                f.write("\n\n")

                f.write("最终交易判断:\n")
                f.write("-" * 30 + "\n")
                f.write(final_decision)
                f.write("\n\n")

                f.write("=" * 80 + "\n\n")

            self.logger.info(f"AI思考过程已记录到 {self.ai_think_file}")

        except Exception as e:
            self.logger.error(f"记录AI思考过程失败: {e}")

    def _generate_market_data_summary(self, market_data: Dict[str, Any]) -> str:
        """生成市场数据摘要"""
        try:
            summary_lines = []

            # 检查数据类型
            data_type = market_data.get('data_type', 'unknown')
            summary_lines.append(f"数据类型: {data_type}")

            # 账户信息
            account_info = market_data.get('account_info', {})
            if account_info and 'error' not in account_info:
                total_balance = account_info.get('total_wallet_balance', 0)
                available_balance = account_info.get('available_balance', 0)
                unrealized_pnl = account_info.get('total_unrealized_pnl', 0)
                summary_lines.append(f"账户余额: {total_balance:.2f} USDT, 可用: {available_balance:.2f} USDT, 盈亏: {unrealized_pnl:.2f} USDT")

            # 持仓信息
            positions = market_data.get('positions', [])
            if positions:
                active_positions = [pos for pos in positions if float(pos.get('position_amount', 0)) != 0]
                summary_lines.append(f"当前持仓: {len(active_positions)} 个")
                for pos in active_positions[:3]:  # 最多显示3个
                    symbol = pos.get('symbol', 'N/A')
                    amount = pos.get('position_amount', 0)
                    pnl = pos.get('unrealized_pnl', 0)
                    summary_lines.append(f"  {symbol}: {amount}, 盈亏: {pnl:.2f} USDT")

            # 币种价格信息
            symbols_data = market_data.get('symbols', {})
            if symbols_data:
                summary_lines.append("币种价格:")
                for symbol_key, symbol_data in list(symbols_data.items())[:5]:  # 最多显示5个币种
                    # 提取基础信息
                    basic_info = symbol_data.get('basic_info', {})
                    if basic_info:
                        price = basic_info.get('last_price', 0)
                        change_pct = basic_info.get('price_change_percent', 0)
                        volume = basic_info.get('volume', 0)
                        summary_lines.append(f"  {symbol_key}: ${float(price):,.2f} ({float(change_pct):+.2f}%), 成交量: {float(volume):,.0f}")

                    # 简要技术指标
                    timeframe_indicators = symbol_data.get('timeframe_indicators', {})
                    if timeframe_indicators and '1h' in timeframe_indicators:
                        indicators_1h = timeframe_indicators['1h']
                        rsi = indicators_1h.get('rsi', 0)
                        sma_20 = indicators_1h.get('sma_20', 0)
                        macd = indicators_1h.get('macd', 0)
                        if rsi or sma_20 or macd:
                            summary_lines.append(f"    1h指标 - RSI: {float(rsi):.1f}, SMA20: ${float(sma_20):,.2f}, MACD: {float(macd):.2f}")

            # 时间戳
            timestamp = market_data.get('timestamp', 'N/A')
            summary_lines.append(f"数据时间: {timestamp}")

            return '\n'.join(summary_lines)

        except Exception as e:
            self.logger.error(f"生成市场数据摘要失败: {e}")
            return f"市场数据摘要生成失败: {e}"

    async def log_model_output(self,
                              output_type: str,
                              model_response: Dict[str, Any],
                              processing_time: Optional[float] = None,
                              symbols: Optional[List[str]] = None):
        """
        记录模型输出到history.txt

        Args:
            output_type: 输出类型 (analysis_result, trading_decisions, etc.)
            model_response: 模型响应
            processing_time: 处理时间（秒）
            symbols: 相关交易币种
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] 模型输出记录\n")
                f.write(f"输出类型: {output_type}\n")
                f.write(f"相关币种: {', '.join(symbols) if symbols else 'N/A'}\n")
                if processing_time:
                    f.write(f"处理时间: {processing_time:.2f}秒\n")
                f.write("-" * 30 + "\n")

                # 格式化模型响应
                f.write("模型响应:\n")
                if isinstance(model_response, dict):
                    f.write(json.dumps(model_response, indent=2, ensure_ascii=False))
                else:
                    f.write(str(model_response))
                f.write("\n\n")

                f.write("=" * 60 + "\n\n")

            self.logger.info(f"模型输出已记录到 {self.history_file}")

        except Exception as e:
            self.logger.error(f"记录模型输出失败: {e}")

    async def log_trading_action(self,
                                action_type: str,
                                symbol: str,
                                action_details: Dict[str, Any],
                                execution_result: Optional[Dict[str, Any]] = None,
                                is_dry_run: bool = True):
        """
        记录交易行为到history.txt

        Args:
            action_type: 行为类型 (buy, sell, stop_loss, take_profit, etc.)
            symbol: 交易币种
            action_details: 行为详情
            execution_result: 执行结果
            is_dry_run: 是否为模拟交易
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] 交易行为记录\n")
                f.write(f"交易模式: {'模拟交易' if is_dry_run else '🔴 实盘交易'}\n")
                f.write(f"行为类型: {action_type}\n")
                f.write(f"交易币种: {symbol}\n")
                f.write("-" * 30 + "\n")

                f.write("行为详情:\n")
                f.write(json.dumps(action_details, indent=2, ensure_ascii=False))
                f.write("\n\n")

                if execution_result:
                    f.write("执行结果:\n")
                    # 添加真实交易的特别标记
                    if not is_dry_run:
                        f.write("🔴 实盘交易执行结果:\n")
                        if execution_result.get("success", False):
                            f.write(f"✅ 交易成功 - 订单ID: {execution_result.get('order_id', 'N/A')}\n")
                            f.write(f"订单类型: {execution_result.get('order_type', 'N/A')}")
                            # 显示AI决策的订单类型
                            if action_details.get("order_type"):
                                f.write(f" (AI建议: {action_details['order_type']})")
                            if action_details.get("order_reasoning"):
                                f.write(f" - {action_details['order_reasoning']}")
                            f.write("\n")
                            f.write(f"成交价格: ${execution_result.get('price', 0):,.4f}\n")
                            f.write(f"成交数量: {execution_result.get('quantity', 0):,.6f}\n")
                        else:
                            f.write(f"❌ 交易失败 - 错误: {execution_result.get('error', 'N/A')}\n")
                        f.write("-" * 20 + "\n")

                    f.write(json.dumps(execution_result, indent=2, ensure_ascii=False))
                    f.write("\n\n")

                f.write("=" * 60 + "\n\n")

            self.logger.info(f"交易行为已记录到 {self.history_file}")

        except Exception as e:
            self.logger.error(f"记录交易行为失败: {e}")

    async def log_market_analysis(self,
                                 analysis_result: Dict[str, Any],
                                 strategy_name: str,
                                 symbols: List[str],
                                 timeframes: Optional[List[str]] = None):
        """
        记录市场分析结果到history.txt

        Args:
            analysis_result: 分析结果
            strategy_name: 策略名称
            symbols: 分析的币种
            timeframes: 分析的时间周期
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] 市场分析记录\n")
                f.write(f"策略名称: {strategy_name}\n")
                f.write(f"分析币种: {', '.join(symbols)}\n")
                if timeframes:
                    f.write(f"时间周期: {', '.join(timeframes)}\n")
                f.write("-" * 30 + "\n")

                # 提取关键信息
                if 'market_overview' in analysis_result:
                    overview = analysis_result['market_overview']
                    f.write("市场概述:\n")
                    f.write(f"  整体情绪: {overview.get('overall_sentiment', 'N/A')}\n")
                    f.write(f"  市场阶段: {overview.get('market_phase', 'N/A')}\n")
                    f.write(f"  波动性评估: {overview.get('volatility_assessment', 'N/A')}\n")
                    f.write("\n")

                if 'trading_decisions' in analysis_result:
                    decisions = analysis_result['trading_decisions']
                    f.write(f"交易决策: {len(decisions)} 个\n")
                    for i, decision in enumerate(decisions, 1):
                        f.write(f"  决策 {i}:\n")
                        f.write(f"    币种: {decision.get('symbol', 'N/A')}\n")
                        f.write(f"    行为: {decision.get('action', 'N/A')}\n")
                        f.write(f"    信心度: {decision.get('confidence', 'N/A')}%\n")
                        f.write(f"    是否执行: {decision.get('should_execute', False)}\n")

                        # 显示成本效益分析
                        cost_analysis = decision.get('cost_benefit_analysis', {})
                        if cost_analysis:
                            f.write(f"    成本效益分析:\n")
                            if cost_analysis.get('expected_profit_percent'):
                                f.write(f"      预期收益: {cost_analysis['expected_profit_percent']}\n")
                            if cost_analysis.get('trading_cost_percent'):
                                f.write(f"      交易成本: {cost_analysis['trading_cost_percent']}\n")
                            if cost_analysis.get('net_profit_ratio'):
                                f.write(f"      净收益比: {cost_analysis['net_profit_ratio']}\n")
                    f.write("\n")

                f.write("完整分析结果:\n")
                f.write(json.dumps(analysis_result, indent=2, ensure_ascii=False))
                f.write("\n\n")

                f.write("=" * 60 + "\n\n")

            self.logger.info(f"市场分析已记录到 {self.history_file}")

        except Exception as e:
            self.logger.error(f"记录市场分析失败: {e}")

    async def log_error(self,
                       error_type: str,
                       error_message: str,
                       context: Optional[Dict[str, Any]] = None):
        """
        记录错误信息到history.txt

        Args:
            error_type: 错误类型
            error_message: 错误消息
            context: 错误上下文
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] 错误记录\n")
                f.write(f"错误类型: {error_type}\n")
                f.write(f"错误消息: {error_message}\n")
                f.write("-" * 30 + "\n")

                if context:
                    f.write("错误上下文:\n")
                    f.write(json.dumps(context, indent=2, ensure_ascii=False))
                    f.write("\n\n")

                f.write("=" * 60 + "\n\n")

            self.logger.error(f"错误信息已记录到 {self.history_file}")

        except Exception as e:
            self.logger.error(f"记录错误信息失败: {e}")

    def get_history_summary(self) -> Dict[str, Any]:
        """
        获取历史记录摘要

        Returns:
            历史记录摘要信息
        """
        try:
            summary = {
                "history_file": {
                    "path": self.history_file,
                    "exists": os.path.exists(self.history_file),
                    "size_bytes": 0,
                    "last_modified": None
                },
                "input_history_file": {
                    "path": self.input_history_file,
                    "exists": os.path.exists(self.input_history_file),
                    "size_bytes": 0,
                    "last_modified": None
                },
                "ai_input_file": {
                    "path": self.ai_input_file,
                    "exists": os.path.exists(self.ai_input_file),
                    "size_bytes": 0,
                    "last_modified": None
                },
                "ai_output_file": {
                    "path": self.ai_output_file,
                    "exists": os.path.exists(self.ai_output_file),
                    "size_bytes": 0,
                    "last_modified": None
                }
            }

            # 获取文件信息
            for file_key, file_path in [("history_file", self.history_file),
                                       ("input_history_file", self.input_history_file),
                                       ("ai_input_file", self.ai_input_file),
                                       ("ai_output_file", self.ai_output_file)]:
                if os.path.exists(file_path):
                    stat = os.stat(file_path)
                    summary[file_key]["size_bytes"] = stat.st_size
                    summary[file_key]["last_modified"] = datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).strftime('%Y-%m-%d %H:%M:%S UTC')

            return summary

        except Exception as e:
            self.logger.error(f"获取历史记录摘要失败: {e}")
            return {"error": str(e)}

    async def log_real_trade_confirmation(self,
                                         symbol: str,
                                         trade_result: Dict[str, Any],
                                         confirmation_result: Dict[str, Any]):
        """
        记录真实交易确认结果

        Args:
            symbol: 交易币种
            trade_result: 交易执行结果
            confirmation_result: 交易确认结果
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] 🔴 实盘交易确认记录\n")
                f.write(f"交易币种: {symbol}\n")
                f.write(f"订单ID: {trade_result.get('order_id', 'N/A')}\n")
                f.write("-" * 30 + "\n")

                # 交易执行摘要
                f.write("交易执行摘要:\n")
                f.write(f"  执行状态: {'✅ 成功' if trade_result.get('success', False) else '❌ 失败'}\n")
                f.write(f"  订单类型: {trade_result.get('order_type', 'N/A')}\n")
                f.write(f"  交易方向: {trade_result.get('side', 'N/A')}\n")
                f.write(f"  杠杆倍数: {trade_result.get('leverage', 'N/A')}x\n")
                f.write(f"  成交价格: ${trade_result.get('price', 0):,.4f}\n")
                f.write(f"  成交数量: {trade_result.get('quantity', 0):,.6f}\n")
                # 交易金额以 usdt_amount 为准
                amt = trade_result.get('usdt_amount')
                if amt is None:
                    amt = 0
                f.write(f"  交易金额: ${amt:,.2f}\n")
                f.write("\n")

                # 确认结果
                f.write("交易确认结果:\n")
                if confirmation_result.get("confirmed", False):
                    f.write("  ✅ 交易已确认\n")
                    if confirmation_result.get("execution_confirmed", False):
                        f.write("  ✅ 订单执行已确认\n")
                    else:
                        f.write(f"  ⚠️  订单执行待确认: {confirmation_result.get('reason', 'N/A')}\n")

                    if confirmation_result.get("position_updated", False):
                        f.write("  ✅ 持仓已更新\n")
                    else:
                        f.write("  ⚠️  持仓更新待确认\n")
                else:
                    f.write(f"  ❌ 交易确认失败: {confirmation_result.get('reason', 'N/A')}\n")

                f.write("\n")

                # 详细数据
                f.write("完整确认数据:\n")
                f.write(json.dumps(confirmation_result, indent=2, ensure_ascii=False))
                f.write("\n\n")

                f.write("=" * 60 + "\n\n")

            self.logger.info(f"实盘交易确认已记录到 {self.history_file}")

        except Exception as e:
            self.logger.error(f"记录实盘交易确认失败: {e}")

    async def log_trading_session_summary(self,
                                         session_info: Dict[str, Any],
                                         total_trades: int,
                                         successful_trades: int,
                                         real_trades: int,
                                         trading_results: List[Dict[str, Any]]):
        """
        记录交易会话摘要

        Args:
            session_info: 会话信息
            total_trades: 总交易次数
            successful_trades: 成功交易次数
            real_trades: 实盘交易次数
            trading_results: 交易结果列表
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] 📊 交易会话摘要\n")
                f.write("=" * 50 + "\n")

                # 会话统计
                f.write("会话统计:\n")
                f.write(f"  开始时间: {session_info.get('start_time', 'N/A')}\n")
                f.write(f"  结束时间: {timestamp}\n")
                f.write(f"  运行时长: {session_info.get('elapsed_minutes', 0)} 分钟\n")
                f.write(f"  AI分析次数: {session_info.get('call_count', 0)} 次\n")
                f.write("\n")

                # 交易统计
                f.write("交易统计:\n")
                f.write(f"  总交易次数: {total_trades}\n")
                f.write(f"  成功交易: {successful_trades}\n")
                f.write(f"  失败交易: {total_trades - successful_trades}\n")
                f.write(f"  🔴 实盘交易: {real_trades}\n")
                f.write(f"  模拟交易: {total_trades - real_trades}\n")
                if total_trades > 0:
                    success_rate = (successful_trades / total_trades) * 100
                    f.write(f"  成功率: {success_rate:.1f}%\n")
                f.write("\n")

                # 实盘交易详情
                if real_trades > 0:
                    f.write("🔴 实盘交易详情:\n")
                    real_trade_results = [r for r in trading_results if not r.get("dry_run", True)]
                    for i, result in enumerate(real_trade_results, 1):
                        symbol = result.get("symbol", "N/A")
                        side = result.get("side", "N/A")
                        success = result.get("success", False)
                        price = result.get("price", 0)
                        quantity = result.get("quantity", 0)
                        order_id = result.get("order_id", "N/A")

                        status_icon = "✅" if success else "❌"
                        f.write(f"  {i}. {status_icon} {symbol} {side} - 价格: ${price:,.4f}, 数量: {quantity:,.6f}, 订单: {order_id}\n")
                    f.write("\n")

                f.write("=" * 60 + "\n\n")

            self.logger.info(f"交易会话摘要已记录到 {self.history_file}")

        except Exception as e:
            self.logger.error(f"记录交易会话摘要失败: {e}")
