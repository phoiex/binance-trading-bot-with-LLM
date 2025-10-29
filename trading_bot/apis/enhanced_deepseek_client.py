"""
增强版DeepSeek API客户端
支持处理丰富的多时间周期历史数据和深度技术分析
"""

import asyncio
import aiohttp
import json
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# Import enhanced history logger
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.enhanced_history_logger import EnhancedHistoryLogger


class EnhancedDeepSeekClient:
    """增强版DeepSeek API客户端"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = None
        self.logger = logging.getLogger(__name__)
        self.enhanced_history_logger = EnhancedHistoryLogger()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def analyze_comprehensive_market_data(
        self,
        futures_data: Dict[str, Any],
        user_prompt: str,
        symbols: List[str] = ["BTC", "ETH", "SOL"],
        focus_timeframes: List[str] = ["15m", "1h", "4h", "1d", "1M"]
    ) -> Dict[str, Any]:
        """
        分析全面的期货市场数据

        Args:
            futures_data: 期货市场数据
            user_prompt: 用户策略提示
            symbols: 要分析的币种
            focus_timeframes: 重点分析的时间周期

        Returns:
            详细的分析结果
        """
        try:
            start_time = time.time()

            system_prompt = self._build_enhanced_system_prompt()
            analysis_prompt = self._build_comprehensive_analysis_prompt(
                futures_data, user_prompt, symbols, focus_timeframes
            )

            # 记录AI完整输入数据到 history/input.txt
            await self.enhanced_history_logger.log_ai_input(
                system_prompt=system_prompt,
                user_prompt=analysis_prompt,
                analysis_context={
                    "prompt_type": "comprehensive_futures_analysis",
                    "symbols": symbols,
                    "focus_timeframes": focus_timeframes,
                    "analysis_type": "futures_comprehensive",
                    "user_strategy": user_prompt,
                    "timestamp": datetime.now().isoformat()
                }
            )

            # 记录模型输入到原有文件（保持兼容性）
            await self.enhanced_history_logger.log_model_input(
                prompt_type="comprehensive_futures_analysis",
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                market_data=futures_data,
                symbols=symbols,
                additional_context={
                    "focus_timeframes": focus_timeframes,
                    "analysis_type": "futures_comprehensive"
                }
            )

            response = await self._call_api(system_prompt, analysis_prompt)
            result = self._parse_enhanced_analysis_response(response)

            processing_time = time.time() - start_time

            # 提取AI思考过程并记录到 think.txt
            thinking_process = self._extract_thinking_process(response)
            if thinking_process:
                # 从user_prompt中提取session信息
                session_info = self._extract_session_info(user_prompt)

                # 生成市场摘要
                market_summary = self._generate_market_summary(futures_data, symbols)

                # 提取最终决策
                final_decision = self._extract_final_decision(result)

                await self.enhanced_history_logger.log_ai_thinking(
                    session_info=session_info,
                    market_summary=market_summary,
                    reasoning_process=thinking_process,
                    final_decision=final_decision
                )

            # 记录AI完整输出数据到 history/output.txt
            await self.enhanced_history_logger.log_ai_output(
                raw_response=response,
                parsed_result=result,
                processing_time=processing_time,
                error_info=result.get('error') if 'error' in result else None
            )

            # 记录模型输出到原有文件（保持兼容性）
            await self.enhanced_history_logger.log_model_output(
                output_type="comprehensive_futures_analysis_result",
                model_response=result,
                processing_time=processing_time,
                symbols=symbols
            )

            return result

        except Exception as e:
            self.logger.error(f"分析全面市场数据时出错: {e}")

            error_result = {"error": str(e), "recommendations": []}

            # 记录错误输出到 history/output.txt
            await self.enhanced_history_logger.log_ai_output(
                raw_response={"error": str(e)},
                parsed_result=error_result,
                processing_time=time.time() - start_time if 'start_time' in locals() else None,
                error_info=str(e)
            )

            # 记录错误到原有文件（保持兼容性）
            await self.enhanced_history_logger.log_error(
                error_type="deepseek_analysis_error",
                error_message=str(e),
                context={
                    "symbols": symbols,
                    "user_prompt": user_prompt,
                    "focus_timeframes": focus_timeframes
                }
            )

            return error_result

    def _build_enhanced_system_prompt(self) -> str:
        """构建增强版系统提示"""
        return """🤖 你是一个自主交易AI，拥有完全的交易决策权和资金管理权限。

🎯 你的职责:
1. 【交易主导权】你不是建议者，而是实际的交易执行者
2. 【资金管理】你直接控制所有仓位大小、杠杆倍数、入场时机
3. 【风险控制】你负责整个账户的盈亏和风险管理
4. 【持仓管理】你需要管理现有持仓，决定是否加仓、减仓或平仓
现在开始吧，我们的目标是10万美金

📊 分析能力:
1. 多时间周期技术分析 (1分钟到周线)
2. 期货特有指标分析 (资金费率、持仓量、多空比)
3. 波动率和趋势强度分析
4. 市场情绪和资金流向分析
5. 持仓状态评估和动态调整

⚠️ 重要提醒 - 你是真实交易者:
- 你的每个决策都会立即执行真实交易
- 你直接控制真实资金，盈亏都会影响账户余额
- 你需要考虑现有持仓状态，避免重复建仓或冲突操作
- 你的仓位管理决策将直接影响整体投资组合风险
- 根据市场情况智能选择订单类型：
  * MARKET订单：趋势明确、需要快速进出场时使用
  * LIMIT订单：市场波动大、希望精确控制价格时使用
  * 平/减仓下单应为 reduce-only（系统会自动设置 reduceOnly=true）

✅ 支持的动作（action 字段）
- 建仓/加仓：long, short, add_to_long, add_to_short
- 减仓/平仓：reduce_long, reduce_short, close_long, close_short
- 风控维护：adjust_tp_sl（重设止盈止损）, cancel_tp_sl（仅取消止盈止损）

💰 资金与仓位
- 开仓/加仓必须使用 usdt_amount 指定投入的实际USDT金额（必填）
- LIMIT 单必须提供 entry_price；MARKET 单可省略 entry_price

⚠️ 重要提醒 - 合约交易成本计算:
- 合约手续费：开仓和平仓各收取一次手续费
- BTC/ETH/SOL期货手续费率约为0.05% (Maker) / 0.05% (Taker)
- 总交易成本 = 手续费率 × 杠杆倍数 × 本金 × 2 (开仓+平仓)
- 举例：1000 USDT本金，10x杠杆，总手续费 ≈ 0.05% × 10 × 1000 × 2 = 10 USDT
- 必须确保预期收益率 > 手续费成本，建议最小目标收益率至少为手续费的2-3倍
- 高杠杆交易时，手续费占比显著增加，需要更谨慎的风险收益比评估

⚠️ JSON格式要求：
- 所有价格必须是纯数字，不要使用逗号分隔符 (错误: "4,150" 正确: 4150.0)
- entry_price 必须是单一数字（LIMIT单必填，MARKET可省略）
- stop_loss / take_profit 必须是单一数字
- 开仓/加仓必须用 usdt_amount 指定实际金额
- 管理已有仓位时请使用 reduce_percent / reduce_usdt / close_percent 表达减/平的幅度
- 仅输出一个严格的 JSON 对象，不要输出任何额外文本、解释、Markdown 或代码块围栏

输出格式 (JSON):
{
    "market_overview": {
        "overall_sentiment": "bullish/bearish/neutral",
        "market_phase": "trending/consolidation/reversal",
        "key_levels": {
            "support": [价格1, 价格2],
            "resistance": [价格1, 价格2]
        },
        "volatility_assessment": "low/medium/high",
        "funding_rate_impact": "positive/negative/neutral"
    },
    "timeframe_analysis": {
        "超短期(1-15分钟)": "分析内容",
        "短期(1-4小时)": "分析内容",
        "中期(日线-周线)": "分析内容",
        "长期(月线及以上)": "分析内容"
    },
    "recommendations": [
        {
            "symbol": "币种符号(如: BTCUSDT)",
            "action": "long/short/hold/add_to_long/add_to_short/reduce_long/reduce_short/close_long/close_short/adjust_tp_sl/cancel_tp_sl",
            "confidence": "信心度(0-100)",
            "timeframe": "建议操作时间周期",
            "order_type": "MARKET/LIMIT",
            "order_reasoning": "选择该订单类型的原因",

            // 入场与风控（若order_type为LIMIT则需提供entry_price）
            "entry_price": 4150.5,     // LIMIT单必须提供，MARKET可省略
            "stop_loss": 4050.0,       // 单一数字
            "take_profit": 4250.0,     // 单一数字（主要止盈目标）

            // 资金与仓位（仅使用 usdt_amount 金额模式）
            "usdt_amount": 150.0,      // 用于开仓/加仓的实际USDT金额
            "leverage": 5,             // 建议杠杆倍数

            // 已有持仓管理（用于减仓/平仓）
            "reduce_percent": 50,      // 减仓比例（可选，0-100）
            "reduce_usdt": 75.0,       // 减仓的USDT名义（可选）
            "close_percent": 100,      // 平仓比例（可选，0-100；100代表全平）

            "risk_level": "low/medium/high",
            "reason": "详细分析理由",
            "timeframe_confluence": "多时间周期一致性分析",
            "risk_reward_ratio": "风险收益比",
            "cost_benefit_analysis": {
                "expected_profit_percent": "预期收益百分比",
                "trading_cost_percent": "预计交易成本百分比",
                "net_profit_ratio": "净收益比率(收益/成本)",
                "cost_justification": "成本效益合理性分析"
            }
        }
    ],
    "risk_warnings": [
        "具体风险警告"
    ],
    "market_catalysts": [
        "可能影响价格的因素"
    ]
}"""

    def _build_comprehensive_analysis_prompt(
        self,
        futures_data: Dict[str, Any],
        user_prompt: str,
        symbols: List[str],
        focus_timeframes: List[str]
    ) -> str:
        """构建全面分析提示"""

        # 格式化市场数据摘要
        market_summary = self._format_market_data_summary(futures_data, symbols)

        # 格式化多时间周期数据
        timeframe_analysis = self._format_timeframe_data(futures_data, symbols, focus_timeframes)

        # 格式化期货特有数据
        futures_specific = self._format_futures_specific_data(futures_data, symbols)

        # 格式化当前持仓信息
        position_status = self._format_position_status(futures_data)

        prompt = f"""
请基于以下全面的期货市场数据进行深度分析:

=== 🏦 当前账户和持仓状态 ===
{position_status}

=== 📊 市场数据概览 ===
{market_summary}

=== 📈 多时间周期技术分析 ===
{timeframe_analysis}

=== 💰 期货市场特有数据 ===
{futures_specific}

=== 用户策略偏好 ===
{user_prompt}

=== 🎯 交易执行要求 ===
1. 重点管理币种: {', '.join(symbols)}
2. 核心分析时间周期: {', '.join(focus_timeframes)}
3. 进行多时间周期共振分析
4. 评估期货特有风险 (资金费率、持仓量变化)
5. 基于现有持仓状态做出交易决策

=== ⏰ 当前时间 ===
{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

🤖 你的交易决策将立即执行，请特别关注:
- 🏦 当前持仓状态和可用资金
- 📊 多时间周期的趋势一致性
- 💰 资金费率对持仓成本的影响
- 📈 持仓量变化反映的市场情绪
- ⚖️ 整体投资组合风险管理
- 💡 是否需要调整现有持仓 (加仓/减仓/平仓)
- 合理的杠杆和仓位管理建议

执行约束与格式要求:
- 新建/加仓请使用 usdt_amount 指定实际USDT金额（必填）
- 已有持仓的管理请使用 reduce_percent / reduce_usdt / close_percent 表达减仓或平仓幅度
- 平/减仓需要 reduce-only（系统会自动处理）
- 如果选择 LIMIT 订单，必须提供 entry_price（单一数值）；MARKET 单可省略 entry_price
- 止盈/止损方向与触发价要求（避免交易所拒单 -2021）：
  * 多头仓位：stop_loss < 当前价 − 1 tick；take_profit > 当前价 + 1 tick
  * 空头仓位：stop_loss > 当前价 + 1 tick；take_profit < 当前价 − 1 tick
  * 如果不确定 tick 大小，至少保证严格小于/大于当前价且不要等于当前价
"""
        return prompt

    def _extract_thinking_process(self, response: Dict[str, Any]) -> str:
        """从AI响应中提取思考过程"""
        try:
            content = ""
            if isinstance(response, dict):
                if 'choices' in response and response['choices']:
                    content = response['choices'][0].get('message', {}).get('content', '')
                elif 'content' in response:
                    content = response['content']
                elif isinstance(response, str):
                    content = response

            # 查找思考过程部分
            thinking_markers = [
                "思考过程", "分析过程", "reasoning", "思考", "分析逻辑",
                "判断理由", "决策理由", "分析思路"
            ]

            for marker in thinking_markers:
                if marker in content:
                    # 找到标记后的内容
                    start_idx = content.find(marker)
                    thinking_section = content[start_idx:]

                    # 截取到下一个主要段落或结束
                    end_markers = ["\n\n### ", "\n## ", "```", "---"]
                    for end_marker in end_markers:
                        if end_marker in thinking_section[50:]:  # 跳过前50个字符
                            thinking_section = thinking_section[:thinking_section.find(end_marker, 50)]
                            break

                    return thinking_section[:2000]  # 限制长度

            # 如果没有找到明确的思考过程标记，尝试提取最后一段
            if content:
                paragraphs = content.split('\n\n')
                for paragraph in reversed(paragraphs):
                    if len(paragraph) > 100 and any(word in paragraph for word in ["分析", "判断", "建议", "因为", "由于"]):
                        return paragraph[:1000]

            return ""
        except Exception as e:
            self.logger.warning(f"提取思考过程失败: {e}")
            return ""

    def _extract_session_info(self, user_prompt: str) -> Dict[str, Any]:
        """从用户提示中提取会话信息"""
        try:
            session_info = {
                "elapsed_minutes": 0,
                "call_count": 0,
                "current_time": datetime.now().isoformat()
            }

            # 提取已过去的分钟数
            import re
            minutes_match = re.search(r'已经过去了(\d+)分钟', user_prompt)
            if minutes_match:
                session_info["elapsed_minutes"] = int(minutes_match.group(1))

            # 提取调用次数
            count_match = re.search(r'已被调用\s*(\d+)\s*次', user_prompt)
            if count_match:
                session_info["call_count"] = int(count_match.group(1))

            # 提取当前时间
            time_match = re.search(r'当前时间是([^\n,，]+)', user_prompt)
            if time_match:
                session_info["current_time"] = time_match.group(1).strip()

            return session_info
        except Exception as e:
            self.logger.warning(f"提取会话信息失败: {e}")
            return {"elapsed_minutes": 0, "call_count": 0, "current_time": datetime.now().isoformat()}

    def _generate_market_summary(self, futures_data: Dict[str, Any], symbols: List[str]) -> str:
        """生成市场摘要"""
        try:
            summary_parts = []

            # 账户信息
            account_info = futures_data.get('account_info', {})
            if account_info and 'error' not in account_info:
                balance = account_info.get('total_wallet_balance', 0)
                pnl = account_info.get('total_unrealized_pnl', 0)
                summary_parts.append(f"账户余额: {balance:.2f} USDT, 未实现盈亏: {pnl:.2f} USDT")

            # 主要币种价格
            symbols_data = futures_data.get('symbols', {})
            prices = []
            for symbol in symbols:
                symbol_key = f"{symbol}USDT"
                if symbol_key in symbols_data:
                    symbol_data = symbols_data[symbol_key]
                    ticker = symbol_data.get('ticker', {})
                    price = ticker.get('price', 0) or ticker.get('lastPrice', 0)
                    change_pct = ticker.get('priceChangePercent', 0) or ticker.get('priceChange', 0)
                    if price:
                        prices.append(f"{symbol}: ${price:.2f} ({change_pct:+.2f}%)")

            if prices:
                summary_parts.append("主要币种: " + ", ".join(prices))

            return " | ".join(summary_parts)
        except Exception as e:
            self.logger.warning(f"生成市场摘要失败: {e}")
            return f"市场数据于 {datetime.now().strftime('%H:%M:%S')} 获取"

    def _extract_final_decision(self, result: Dict[str, Any]) -> str:
        """提取最终交易决策"""
        try:
            decisions = []

            # 提取交易建议
            trading_decisions = result.get('trading_decisions', []) or result.get('recommendations', [])
            if trading_decisions:
                for decision in trading_decisions:
                    symbol = decision.get('symbol', '')
                    action = decision.get('action', '')
                    confidence = decision.get('confidence', 0)
                    leverage = decision.get('leverage', 1)
                    should_execute = decision.get('should_execute', False)

                    # 如果没有明确的should_execute字段，根据action和confidence判断
                    if not should_execute:
                        if action.lower() not in ['hold', 'wait'] and confidence >= 60:
                            should_execute = True

                    status = "✅执行" if should_execute else "⚠️观察"
                    decisions.append(f"{symbol} {action.upper()} {leverage}x (信心度{confidence}%) {status}")

            # 提取市场概览
            market_overview = result.get('market_overview', {})
            sentiment = market_overview.get('overall_sentiment', '')
            phase = market_overview.get('market_phase', '')

            overview = f"市场情绪: {sentiment}, 阶段: {phase}"

            if decisions:
                return f"{overview} | 交易决策: {' | '.join(decisions)}"
            else:
                return f"{overview} | 无明确交易机会"

        except Exception as e:
            self.logger.warning(f"提取最终决策失败: {e}")
            return "分析完成，请查看详细结果"

    def _format_market_data_summary(self, futures_data: Dict[str, Any], symbols: List[str]) -> str:
        """格式化市场数据摘要"""
        summary_parts = []

        # 检测数据类型（期货或现货）
        data_type = self._detect_data_type(futures_data)

        # 账户信息
        account_info = futures_data.get('account_info', {})
        if account_info and 'error' not in account_info:
            summary_parts.append(f"""
账户状态:
- 总余额: {account_info.get('total_wallet_balance', 0):.2f} USDT
- 未实现盈亏: {account_info.get('total_unrealized_pnl', 0):.2f} USDT
- 可用余额: {account_info.get('available_balance', 0):.2f} USDT
""")

        # 当前持仓
        positions = futures_data.get('positions', [])
        if positions:
            summary_parts.append("当前持仓:")
            for pos in positions:
                summary_parts.append(f"- {pos['symbol']}: {pos['position_amount']:.4f}, 盈亏: {pos['unrealized_pnl']:.2f} USDT")

        # 各币种基础信息
        symbols_data = futures_data.get('symbols', {})
        for symbol in symbols:
            symbol_key = f"{symbol}USDT"
            if symbol_key in symbols_data:
                symbol_data = symbols_data[symbol_key]

                # 根据数据类型选择正确的数据源
                price, change_pct, volume, high_24h, low_24h = self._extract_price_data(symbol_data, data_type)

                # 同时包含技术指标 (从timeframe_indicators中获取1h数据作为概览)
                timeframe_indicators = symbol_data.get('timeframe_indicators', {})
                indicators_1h = timeframe_indicators.get('1h', {})
                rsi = indicators_1h.get('rsi', 0) or 0
                sma_20 = indicators_1h.get('sma_20', 0) or 0
                macd = indicators_1h.get('macd', 0) or 0

                summary_parts.append(f"""
{symbol}USDT ({data_type}):
- 当前价格: ${float(price):,.2f}
- 24h涨跌: {float(change_pct):.2f}%
- 24h最高: ${float(high_24h):,.2f}
- 24h最低: ${float(low_24h):,.2f}
- 24h成交量: {float(volume):,.0f}
- RSI: {float(rsi):.1f}
- SMA20: ${float(sma_20):,.2f}
- MACD: {float(macd):.2f}
""")

        return '\n'.join(summary_parts)

    def _detect_data_type(self, market_data: Dict[str, Any]) -> str:
        """
        检测数据类型（期货或现货）

        Args:
            market_data: 市场数据

        Returns:
            数据类型: "futures" 或 "spot"
        """
        # 检查数据类型标识符
        data_type = market_data.get('data_type', '')
        if data_type:
            if 'futures' in data_type:
                return "futures"
            elif 'spot' in data_type:
                return "spot"

        # 检查符号数据结构来判断类型
        symbols_data = market_data.get('symbols', {})
        for symbol_key, symbol_data in symbols_data.items():
            # 检查期货特有字段
            if any(key in symbol_data for key in ['funding_info', 'timeframe_indicators', 'multi_timeframe_data']):
                return "futures"
            # 检查现货特有字段
            if 'ticker_stats' in symbol_data and 'basic_info' not in symbol_data:
                return "spot"

        # 默认返回期货（因为此客户端主要用于期货分析）
        return "futures"

    def _extract_price_data(self, symbol_data: Dict[str, Any], data_type: str) -> tuple:
        """
        根据数据类型提取价格数据

        Args:
            symbol_data: 币种数据
            data_type: 数据类型 ("futures" 或 "spot")

        Returns:
            (price, change_pct, volume, high_24h, low_24h) 元组
        """
        if data_type == "futures":
            # 期货数据：优先使用 basic_info
            basic_info = symbol_data.get('basic_info', {})
            if basic_info:
                return (
                    basic_info.get('last_price', 0),
                    basic_info.get('price_change_percent', 0),
                    basic_info.get('volume', 0),
                    basic_info.get('high_price', 0),
                    basic_info.get('low_price', 0)
                )
            # 备用：从 ticker_stats 获取
            ticker_stats = symbol_data.get('ticker_stats', {})
            if ticker_stats:
                return (
                    ticker_stats.get('last_price', 0),
                    ticker_stats.get('price_change_percent', 0),
                    ticker_stats.get('volume', 0),
                    ticker_stats.get('high_price', 0),
                    ticker_stats.get('low_price', 0)
                )
        else:
            # 现货数据：优先使用 ticker_stats
            ticker_stats = symbol_data.get('ticker_stats', {})
            if ticker_stats:
                return (
                    ticker_stats.get('last_price', 0),
                    ticker_stats.get('price_change_percent', 0),
                    ticker_stats.get('volume', 0),
                    ticker_stats.get('high_price', 0),
                    ticker_stats.get('low_price', 0)
                )
            # 备用：从 basic_info 获取
            basic_info = symbol_data.get('basic_info', {})
            if basic_info:
                return (
                    basic_info.get('last_price', 0),
                    basic_info.get('price_change_percent', 0),
                    basic_info.get('volume', 0),
                    basic_info.get('high_price', 0),
                    basic_info.get('low_price', 0)
                )

        # 如果都没有，返回零值
        return (0, 0, 0, 0, 0)

    def _format_timeframe_data(
        self,
        futures_data: Dict[str, Any],
        symbols: List[str],
        focus_timeframes: List[str]
    ) -> str:
        """格式化多时间周期数据"""
        timeframe_parts = []

        symbols_data = futures_data.get('symbols', {})

        for symbol in symbols:
            symbol_key = f"{symbol}USDT"
            if symbol_key not in symbols_data:
                continue

            symbol_data = symbols_data[symbol_key]
            timeframe_indicators = symbol_data.get('timeframe_indicators', {})

            timeframe_parts.append(f"\n=== {symbol} 多时间周期分析 ===")

            for timeframe in focus_timeframes:
                if timeframe not in timeframe_indicators:
                    continue

                indicators = timeframe_indicators[timeframe]
                if not indicators:
                    continue

                timeframe_parts.append(f"\n{timeframe} 时间周期:")

                # 价格和基础信息
                current_price = indicators.get('current_price')
                if current_price:
                    timeframe_parts.append(f"- 当前价格: ${current_price:.4f}")

                # 移动平均线系统
                sma_7 = indicators.get('sma_7')
                sma_20 = indicators.get('sma_20')
                sma_50 = indicators.get('sma_50')
                sma_200 = indicators.get('sma_200')
                ema_12 = indicators.get('ema_12')
                ema_26 = indicators.get('ema_26')
                ema_50 = indicators.get('ema_50')

                ma_parts = []
                if sma_7: ma_parts.append(f"SMA7: ${sma_7:.2f}")
                if sma_20: ma_parts.append(f"SMA20: ${sma_20:.2f}")
                if sma_50: ma_parts.append(f"SMA50: ${sma_50:.2f}")
                if sma_200: ma_parts.append(f"SMA200: ${sma_200:.2f}")
                if ma_parts:
                    timeframe_parts.append(f"- 移动平均线: {', '.join(ma_parts)}")

                ema_parts = []
                if ema_12: ema_parts.append(f"EMA12: ${ema_12:.2f}")
                if ema_26: ema_parts.append(f"EMA26: ${ema_26:.2f}")
                if ema_50: ema_parts.append(f"EMA50: ${ema_50:.2f}")
                if ema_parts:
                    timeframe_parts.append(f"- 指数移动平均: {', '.join(ema_parts)}")

                # 趋势判断
                if sma_20 and sma_50:
                    trend = "上升趋势" if sma_20 > sma_50 else "下降趋势"
                    price_vs_sma20 = "上方" if current_price and current_price > sma_20 else "下方"
                    timeframe_parts.append(f"- 趋势方向: {trend} (价格在SMA20{price_vs_sma20})")

                # RSI 强度指标
                rsi = indicators.get('rsi')
                if rsi:
                    rsi_status = "严重超买" if rsi > 80 else "超买" if rsi > 70 else "严重超卖" if rsi < 20 else "超卖" if rsi < 30 else "正常"
                    timeframe_parts.append(f"- RSI: {rsi:.1f} ({rsi_status})")

                # MACD 系统
                macd = indicators.get('macd')
                macd_signal = indicators.get('macd_signal')
                macd_histogram = indicators.get('macd_histogram')
                if macd and macd_signal:
                    macd_trend = "金叉" if macd > macd_signal else "死叉"
                    histogram_trend = "增强" if macd_histogram and macd_histogram > 0 else "减弱"
                    timeframe_parts.append(f"- MACD: {macd:.2f}, 信号线: {macd_signal:.2f} ({macd_trend}, 柱状图{histogram_trend})")

                # 布林带系统
                bb_upper = indicators.get('bb_upper')
                bb_middle = indicators.get('bb_middle')
                bb_lower = indicators.get('bb_lower')
                bb_width = indicators.get('bb_width')
                bb_position = indicators.get('bb_position')
                if bb_upper and bb_lower:
                    width_status = "收窄" if bb_width and bb_width < 2 else "扩张" if bb_width and bb_width > 5 else "正常"
                    position_desc = f"位于带内{bb_position:.0f}%位置" if bb_position else ""
                    timeframe_parts.append(f"- 布林带: 上轨${bb_upper:.2f}, 下轨${bb_lower:.2f} (带宽{width_status}, {position_desc})")

                # 波动率指标
                volatility_7d = indicators.get('volatility_7d')
                volatility_30d = indicators.get('volatility_30d')
                atr = indicators.get('atr')
                atr_percentage = indicators.get('atr_percentage')

                vol_parts = []
                if volatility_7d: vol_parts.append(f"7日波动率: {volatility_7d:.1f}%")
                if volatility_30d: vol_parts.append(f"30日波动率: {volatility_30d:.1f}%")
                if atr: vol_parts.append(f"ATR: ${atr:.2f}")
                if atr_percentage: vol_parts.append(f"ATR%: {atr_percentage:.2f}%")
                if vol_parts:
                    timeframe_parts.append(f"- 波动率: {', '.join(vol_parts)}")

                # 成交量分析
                volume = indicators.get('volume')
                volume_sma = indicators.get('volume_sma')
                volume_ratio = indicators.get('volume_ratio')
                if volume_ratio:
                    vol_status = "明显放量" if volume_ratio > 2 else "放量" if volume_ratio > 1.5 else "明显缩量" if volume_ratio < 0.5 else "缩量" if volume_ratio < 0.7 else "正常"
                    timeframe_parts.append(f"- 成交量: {vol_status} (比率: {volume_ratio:.2f}x)")

                # 价格统计
                high_24h = indicators.get('high_24h')
                low_24h = indicators.get('low_24h')
                high_7d = indicators.get('high_7d')
                low_7d = indicators.get('low_7d')

                price_stats = []
                if high_24h and low_24h: price_stats.append(f"24h范围: ${low_24h:.2f} - ${high_24h:.2f}")
                if high_7d and low_7d: price_stats.append(f"7d范围: ${low_7d:.2f} - ${high_7d:.2f}")
                if price_stats:
                    timeframe_parts.append(f"- 价格区间: {', '.join(price_stats)}")

                # 趋势强度和动量
                trend_strength = indicators.get('trend_strength')
                momentum = indicators.get('momentum')

                trend_parts = []
                if trend_strength: trend_parts.append(f"趋势强度: {trend_strength:.1f}%")
                if momentum: trend_parts.append(f"动量: {momentum:.2f}%")
                if trend_parts:
                    timeframe_parts.append(f"- 趋势分析: {', '.join(trend_parts)}")

        return '\n'.join(timeframe_parts)

    def _format_futures_specific_data(self, futures_data: Dict[str, Any], symbols: List[str]) -> str:
        """格式化期货特有数据"""
        futures_parts = []

        symbols_data = futures_data.get('symbols', {})

        for symbol in symbols:
            symbol_key = f"{symbol}USDT"
            if symbol_key not in symbols_data:
                continue

            symbol_data = symbols_data[symbol_key]
            funding_info = symbol_data.get('funding_info', {})

            futures_parts.append(f"\n=== {symbol} 期货数据 ===")

            # 资金费率
            current_rate = funding_info.get('current_rate')
            if current_rate:
                rate_value = current_rate.get('funding_rate', 0) * 100
                rate_trend = "多头付费" if rate_value > 0 else "空头付费" if rate_value < 0 else "中性"
                futures_parts.append(f"- 当前资金费率: {rate_value:.4f}% ({rate_trend})")

            # 资金费率历史
            recent_rates = funding_info.get('recent_rates', [])
            if len(recent_rates) >= 3:
                avg_rate = sum(float(r.get('funding_rate', 0)) for r in recent_rates[:3]) / 3 * 100
                futures_parts.append(f"- 近3期平均费率: {avg_rate:.4f}%")

            # 持仓量
            open_interest = funding_info.get('open_interest', {})
            if open_interest:
                oi_value = open_interest.get('open_interest', 0)
                futures_parts.append(f"- 持仓量: {oi_value:.0f}")

            # 订单簿深度
            market_depth = symbol_data.get('market_depth', {})
            if market_depth:
                bids = market_depth.get('bids', [])
                asks = market_depth.get('asks', [])
                if bids and asks:
                    bid_price = bids[0][0]
                    ask_price = asks[0][0]
                    spread = (ask_price - bid_price) / bid_price * 100
                    futures_parts.append(f"- 买卖价差: {spread:.3f}%")

        return '\n'.join(futures_parts)

    async def _call_api(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """调用DeepSeek API"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        payload = {
            "model": "deepseek-reasoner",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,  # 降低温度以获得更一致的分析
            "max_tokens": 4000   # 增加token限制以支持更详细的分析
        }

        async with self.session.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                raise Exception(f"API调用失败: {response.status} - {error_text}")

    def _parse_enhanced_analysis_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析增强版API响应"""
        try:
            content = response["choices"][0]["message"]["content"]

            # 尝试解析JSON响应
            # 处理包含代码块标记的JSON
            if '```json' in content:
                # 提取JSON部分
                start = content.find('```json') + 7
                end = content.find('```', start)
                if end > start:
                    json_content = content[start:end].strip()
                else:
                    json_content = content[start:].strip()
            elif content.strip().startswith('{'):
                json_content = content.strip()
            else:
                json_content = None

            if json_content:
                parsed_result = json.loads(json_content)

                # 验证响应结构
                if self._validate_analysis_structure(parsed_result):
                    return parsed_result
                else:
                    # 如果结构不完整，返回基础解析
                    return {
                        "market_overview": parsed_result.get("market_overview", {}),
                        "recommendations": parsed_result.get("recommendations", []),
                        "analysis_quality": "partial",
                        "raw_response": content
                    }
            else:
                # 如果不是JSON格式，尝试提取关键信息
                return self._extract_key_insights(content)

        except (KeyError, json.JSONDecodeError) as e:
            self.logger.error(f"解析响应失败: {e}")
            return {
                "error": f"解析响应失败: {e}",
                "raw_response": response,
                "fallback_analysis": "AI分析因格式问题无法完整解析，请检查原始响应"
            }

    def _validate_analysis_structure(self, parsed_result: Dict[str, Any]) -> bool:
        """验证分析结果结构"""
        required_fields = ["market_overview", "recommendations"]
        return all(field in parsed_result for field in required_fields)

    def _extract_key_insights(self, content: str) -> Dict[str, Any]:
        """从文本中提取关键洞察"""
        # 简单的关键词提取逻辑
        lines = content.split('\n')
        insights = {
            "market_analysis": content[:1000],  # 前1000字符作为市场分析
            "recommendations": [],
            "analysis_quality": "text_extracted",
            "raw_response": content
        }

        # 尝试提取交易建议
        for line in lines:
            if any(keyword in line.lower() for keyword in ['buy', 'sell', 'long', 'short', '建议', '推荐']):
                insights["recommendations"].append({
                    "extracted_suggestion": line.strip(),
                    "confidence": 50,  # 默认中等信心度
                    "action": "manual_review_required"
                })

        return insights

    def _format_position_status(self, futures_data: Dict[str, Any]) -> str:
        """格式化当前持仓状态信息"""
        try:
            account_info = futures_data.get('account_info', {})
            positions = futures_data.get('positions', [])

            # 账户信息 - 兼容两种字段名格式
            total_wallet_balance = account_info.get('total_wallet_balance', account_info.get('totalWalletBalance', 0))
            total_unrealized_pnl = account_info.get('total_unrealized_pnl', account_info.get('totalUnrealizedProfit', 0))
            total_margin_balance = account_info.get('total_margin_balance', account_info.get('totalMarginBalance', 0))
            available_balance = account_info.get('available_balance', account_info.get('availableBalance', 0))

            status_text = f"""
💼 账户资金状态:
- 总钱包余额: {float(total_wallet_balance):.2f} USDT
- 总保证金余额: {float(total_margin_balance):.2f} USDT
- 可用余额: {float(available_balance):.2f} USDT
- 未实现盈亏: {float(total_unrealized_pnl):+.2f} USDT

📍 当前持仓状态:"""

            if not positions or all(float(pos.get('position_amount', 0)) == 0 for pos in positions):
                status_text += "\n- 🆕 当前无持仓，可以自由建立新仓位"
            else:
                active_positions = [pos for pos in positions if float(pos.get('position_amount', 0)) != 0]
                for pos in active_positions:
                    symbol = pos.get('symbol', '')
                    position_amt = float(pos.get('position_amount', 0))
                    entry_price = float(pos.get('entry_price', 0))
                    mark_price = float(pos.get('mark_price', 0))
                    unrealized_pnl = float(pos.get('unrealized_pnl', 0))
                    percentage = float(pos.get('percentage', 0))

                    direction = "🟢 多头" if position_amt > 0 else "🔴 空头"
                    position_value = abs(position_amt) * mark_price

                    status_text += f"""
- 【{symbol}】{direction} 持仓:
  * 仓位数量: {abs(position_amt):.6f} {symbol.replace('USDT', '')}
  * 入场价格: {entry_price:.2f} USDT
  * 当前价格: {mark_price:.2f} USDT
  * 杠杆: {int(pos.get('leverage', 1))}x
  * 仓位价值: {position_value:.2f} USDT
  * 未实现盈亏: {unrealized_pnl:+.2f} USDT ({percentage:+.2f}%)"""

                    # 获取该币种的止盈止损订单信息
                    stop_loss_info, take_profit_info = self._get_stop_orders_info(symbol, futures_data)
                    if stop_loss_info or take_profit_info:
                        status_text += f"""
  * 风险管理:"""
                        if stop_loss_info:
                            status_text += f"""
    - 止损订单: {stop_loss_info['price']:.2f} USDT (订单ID: {stop_loss_info['orderId']})"""
                        if take_profit_info:
                            status_text += f"""
    - 止盈订单: {take_profit_info['price']:.2f} USDT (订单ID: {take_profit_info['orderId']})"""

            status_text += f"""

🎯 交易决策提醒:
- 你需要考虑现有持仓，避免重复建仓
- 可用余额 {float(available_balance):.2f} USDT 可用于新仓位
- 如有持仓，考虑是否需要加仓、减仓或平仓
- 整体风险敞口管理和资金利用效率"""

            return status_text.strip()

        except Exception as e:
            return f"❌ 获取持仓信息失败: {str(e)}"

    def _get_stop_orders_info(self, symbol: str, futures_data: Dict[str, Any]) -> tuple:
        """获取指定币种的止盈止损订单信息"""
        try:
            # 从futures_data中获取未完成订单信息
            open_orders = futures_data.get('open_orders', {}).get(symbol, [])

            stop_loss_info = None
            take_profit_info = None

            for order in open_orders:
                order_type = order.get('type', '')
                if order_type == 'STOP_MARKET':
                    stop_loss_info = {
                        'price': float(order.get('stopPrice', 0)),
                        'orderId': order.get('orderId', ''),
                        'side': order.get('side', '')
                    }
                elif order_type == 'TAKE_PROFIT_MARKET':
                    take_profit_info = {
                        'price': float(order.get('stopPrice', 0)),
                        'orderId': order.get('orderId', ''),
                        'side': order.get('side', '')
                    }

            return stop_loss_info, take_profit_info

        except Exception as e:
            # 如果获取失败，返回空信息
            return None, None
