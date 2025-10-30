"""
期货交易引擎
支持U本位合约交易、多时间周期分析和增强的AI决策
"""

import sys
import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json
import math
import aiohttp

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../python-binance-master/python-binance-master'))

from binance import AsyncClient
from binance.exceptions import BinanceAPIException

from trading_bot.apis.enhanced_deepseek_client import EnhancedDeepSeekClient
from trading_bot.data.futures_data import FuturesDataManager


class FuturesTradingEngine:
    """期货交易引擎"""

    def __init__(
        self,
        binance_api_key: str,
        binance_api_secret: str,
        deepseek_api_key: str,
        config: dict = None,
        testnet: bool = True,
        max_position_size: float = 0.1,
        default_leverage: int = 3,
        stop_loss_percent: float = 0.05,
        take_profit_percent: float = 0.15
    ):
        self.binance_api_key = binance_api_key
        self.binance_api_secret = binance_api_secret
        self.deepseek_api_key = deepseek_api_key
        self.testnet = testnet
        self.config = config or {}

        # 期货交易参数
        self.max_position_size = max_position_size
        self.default_leverage = default_leverage
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent

        # 实例
        self.futures_data_manager = None
        self.deepseek_client = None
        self.binance_client = None

        # 状态跟踪
        self.current_positions = {}
        self.trade_history = []
        self.last_analysis_time = None
        self.leverage_settings = {}  # 每个币种的杠杆设置

        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        try:
            # 初始化期货数据管理器
            self.futures_data_manager = FuturesDataManager(
                api_key=self.binance_api_key,
                api_secret=self.binance_api_secret,
                testnet=self.testnet
            )
            await self.futures_data_manager.__aenter__()

            # 初始化增强版DeepSeek客户端
            self.deepseek_client = EnhancedDeepSeekClient(api_key=self.deepseek_api_key)
            await self.deepseek_client.__aenter__()

            # 初始化Binance期货客户端
            self.binance_client = await AsyncClient.create(
                api_key=self.binance_api_key,
                api_secret=self.binance_api_secret,
                testnet=self.testnet
            )

            # 不在启动时批量设置杠杆，避免干预账户默认设置

            self.logger.info("期货交易引擎初始化成功")
            return self

        except Exception as e:
            self.logger.error(f"期货交易引擎初始化失败: {e}")
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.futures_data_manager:
            await self.futures_data_manager.__aexit__(exc_type, exc_val, exc_tb)
        if self.deepseek_client:
            await self.deepseek_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.binance_client:
            await self.binance_client.close_connection()

    async def _initialize_leverage_settings(self):
        """初始化杠杆设置"""
        default_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

        for symbol in default_symbols:
            try:
                # 设置杠杆
                try:
                    await self._retry_api_call(
                        self.binance_client.futures_change_leverage,
                        symbol=symbol,
                        leverage=self.default_leverage
                    )
                except Exception as e:
                    # 网络/临时错误已在重试内处理；保持兼容逻辑
                    raise e
                self.leverage_settings[symbol] = self.default_leverage
                self.logger.info(f"设置{symbol}杠杆为{self.default_leverage}x")

            except BinanceAPIException as e:
                self.logger.warning(f"设置{symbol}杠杆失败: {e}")
                self.leverage_settings[symbol] = 1  # 默认1x
            except Exception as e:
                self.logger.warning(f"设置{symbol}杠杆时发生错误: {e}")
                self.leverage_settings[symbol] = 1

    async def analyze_comprehensive_market(
        self,
        user_prompt: str,
        symbols: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        timeframes: List[str] = ["1h", "4h", "1d"]
    ) -> Dict[str, Any]:
        """
        全面市场分析

        Args:
            user_prompt: 用户策略提示
            symbols: 要分析的币种
            timeframes: 重点分析的时间周期

        Returns:
            全面的分析结果
        """
        try:
            # 获取全面的期货数据
            self.logger.info("获取全面期货市场数据...")
            futures_data = await self.futures_data_manager.get_comprehensive_futures_data(
                symbols=symbols,
                include_historical=True
            )

            # 使用增强版DeepSeek进行分析
            self.logger.info("使用AI进行深度市场分析...")
            ai_analysis = await self.deepseek_client.analyze_comprehensive_market_data(
                futures_data=futures_data,
                user_prompt=user_prompt,
                symbols=[s.replace("USDT", "") for s in symbols],
                focus_timeframes=timeframes
            )

            # 生成期货交易决策
            trading_decisions = await self._generate_futures_trading_decisions(
                ai_analysis, futures_data, symbols
            )

            # 获取当前持仓信息
            current_positions = await self.get_current_positions()

            self.last_analysis_time = datetime.now()

            return {
                "timestamp": datetime.now().isoformat(),
                "analysis_type": "comprehensive_futures",
                "futures_data": futures_data,
                "ai_analysis": ai_analysis,
                "trading_decisions": trading_decisions,
                "current_positions": current_positions,
                "account_summary": futures_data.get("account_info", {}),
                "timeframes_analyzed": timeframes
            }

        except Exception as e:
            self.logger.error(f"全面市场分析失败: {e}")
            return {"error": str(e)}

    async def _generate_futures_trading_decisions(
        self,
        ai_analysis: Dict[str, Any],
        futures_data: Dict[str, Any],
        symbols: List[str]
    ) -> List[Dict[str, Any]]:
        """
        生成期货交易决策

        Args:
            ai_analysis: AI分析结果
            futures_data: 期货数据
            symbols: 币种列表

        Returns:
            期货交易决策列表
        """
        decisions = []

        try:
            recommendations = ai_analysis.get("recommendations", [])
            market_overview = ai_analysis.get("market_overview", {})

            for symbol in symbols:
                # 查找对应的AI推荐
                ai_recommendation = None
                symbol_clean = symbol.replace("USDT", "")

                for rec in recommendations:
                    if rec.get("symbol", "").upper() in [symbol_clean, symbol]:
                        ai_recommendation = rec
                        break

                if not ai_recommendation:
                    continue

                # 获取当前市场数据
                symbol_data = futures_data.get("symbols", {}).get(symbol, {})
                basic_info = symbol_data.get("basic_info", {})
                current_price = basic_info.get("last_price")

                if not current_price:
                    continue

                # 生成期货交易决策
                decision = await self._create_futures_trading_decision(
                    symbol=symbol,
                    ai_recommendation=ai_recommendation,
                    market_data=symbol_data,
                    market_overview=market_overview,
                    current_price=current_price
                )

                if decision:
                    decisions.append(decision)

        except Exception as e:
            self.logger.error(f"生成期货交易决策失败: {e}")

        return decisions

    async def _create_futures_trading_decision(
        self,
        symbol: str,
        ai_recommendation: Dict[str, Any],
        market_data: Dict[str, Any],
        market_overview: Dict[str, Any],
        current_price: float
    ) -> Optional[Dict[str, Any]]:
        """
        创建期货交易决策

        Args:
            symbol: 币种符号
            ai_recommendation: AI推荐
            market_data: 市场数据
            market_overview: 市场概览
            current_price: 当前价格

        Returns:
            期货交易决策字典
        """
        try:
            action = ai_recommendation.get("action", "hold").lower()
            confidence = float(ai_recommendation.get("confidence", 0))
            risk_level = ai_recommendation.get("risk_level", "medium")
            suggested_leverage = int(ai_recommendation.get("leverage", self.default_leverage))

            # 期货特有数据分析
            funding_info = market_data.get("funding_info", {})
            current_funding_rate = funding_info.get("current_rate", {}).get("funding_rate", 0)

            # 使用AI推荐的资金金额（强制使用金额模式）
            usdt_amount = None
            try:
                if ai_recommendation.get("usdt_amount") is not None:
                    usdt_amount = float(ai_recommendation.get("usdt_amount"))
            except Exception:
                usdt_amount = None

            # 计算止损止盈（期货模式）
            stop_loss_price, take_profit_prices = await self._calculate_futures_stop_levels(
                current_price, action, ai_recommendation, suggested_leverage
            )

            # 风险评估（期货特有）
            risk_assessment = await self._assess_futures_risk(
                symbol, market_data, market_overview, suggested_leverage
            )

            # 执行阈值：仅在confidence大于配置阈值时执行
            min_conf = 60.0
            try:
                min_conf = float(self.config.get("trading", {}).get("safety", {}).get("min_confidence", 60))
            except Exception:
                min_conf = 60.0

            decision = {
                "symbol": symbol,
                "action": action,  # long/short/hold
                "confidence": confidence,
                "risk_level": risk_level,
                "current_price": current_price,
                "usdt_amount": usdt_amount,
                "leverage": suggested_leverage,
                "stop_loss_price": stop_loss_price,
                "take_profit_prices": take_profit_prices,
                "funding_rate": current_funding_rate * 100,  # 转换为百分比
                "funding_impact": self._assess_funding_impact(current_funding_rate, action),
                "risk_assessment": risk_assessment,
                "timeframe": ai_recommendation.get("timeframe", "4h"),
                "ai_reason": ai_recommendation.get("reason", ""),
                "timeframe_confluence": ai_recommendation.get("timeframe_confluence", ""),
                "risk_reward_ratio": ai_recommendation.get("risk_reward_ratio", ""),
                "order_type": ai_recommendation.get("order_type", ""),
                "order_reasoning": ai_recommendation.get("order_reasoning", ""),
                "entry_price": ai_recommendation.get("entry_price"),
                # 减仓/平仓相关可选字段（AI可提供）
                "reduce_percent": ai_recommendation.get("reduce_percent"),
                "reduce_usdt": ai_recommendation.get("reduce_usdt"),
                "close_percent": ai_recommendation.get("close_percent"),
                "cost_benefit_analysis": ai_recommendation.get("cost_benefit_analysis", {}),
                "should_execute": (action != "hold" and confidence >= min_conf),
                "timestamp": datetime.now().isoformat()
            }

            return decision

        except Exception as e:
            self.logger.error(f"创建期货交易决策失败: {e}")
            return None

    # 旧版比例仓位函数已废弃（以usdt_amount为准）

    async def _calculate_futures_stop_levels(
        self,
        current_price: float,
        action: str,
        ai_recommendation: Dict[str, Any],
        leverage: int
    ) -> Tuple[Optional[float], List[float]]:
        """计算期货止损止盈"""
        if action == "hold":
            return None, []

        try:
            # 根据杠杆调整止损止盈比例
            adjusted_stop_loss = self.stop_loss_percent / leverage
            adjusted_take_profit = self.take_profit_percent / leverage

            # 优先使用AI推荐的价格
            ai_stop_loss = ai_recommendation.get("stop_loss")
            ai_take_profit = ai_recommendation.get("take_profit")

            if action in ["long", "buy"]:
                # 多头止损止盈
                stop_loss = (
                    float(ai_stop_loss) if ai_stop_loss
                    else current_price * (1 - adjusted_stop_loss)
                )

                if ai_take_profit:
                    if isinstance(ai_take_profit, list):
                        # 兼容旧格式：列表
                        take_profit_prices = [float(tp) for tp in ai_take_profit]
                    else:
                        # 新格式：单一数字
                        take_profit_prices = [float(ai_take_profit)]
                else:
                    take_profit_prices = [
                        current_price * (1 + adjusted_take_profit),
                        current_price * (1 + adjusted_take_profit * 2)
                    ]

            else:  # short/sell
                # 空头止损止盈
                stop_loss = (
                    float(ai_stop_loss) if ai_stop_loss
                    else current_price * (1 + adjusted_stop_loss)
                )

                if ai_take_profit:
                    if isinstance(ai_take_profit, list):
                        # 兼容旧格式：列表
                        take_profit_prices = [float(tp) for tp in ai_take_profit]
                    else:
                        # 新格式：单一数字
                        take_profit_prices = [float(ai_take_profit)]
                else:
                    take_profit_prices = [
                        current_price * (1 - adjusted_take_profit),
                        current_price * (1 - adjusted_take_profit * 2)
                    ]

            return stop_loss, take_profit_prices

        except Exception as e:
            self.logger.error(f"计算期货止损止盈失败: {e}")
            return None, []

    def _assess_funding_impact(self, funding_rate: float, action: str) -> str:
        """评估资金费率影响"""
        if abs(funding_rate) < 0.0001:  # 0.01%
            return "neutral"

        if action in ["long", "buy"]:
            return "negative" if funding_rate > 0 else "positive"
        else:  # short
            return "positive" if funding_rate > 0 else "negative"

    async def _assess_futures_risk(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        market_overview: Dict[str, Any],
        leverage: int
    ) -> Dict[str, Any]:
        """评估期货风险"""
        try:
            risk_score = 5.0  # 基础风险分数

            # 杠杆风险
            leverage_risk = min(leverage / 10.0 * 3, 3)  # 最高3分
            risk_score += leverage_risk

            # 波动率风险
            timeframe_indicators = market_data.get("timeframe_indicators", {})
            volatility = None
            for tf in ["1h", "4h", "1d"]:
                if tf in timeframe_indicators:
                    vol = timeframe_indicators[tf].get("volatility_7d")
                    if vol:
                        volatility = vol
                        break

            if volatility:
                if volatility > 80:
                    risk_score += 2
                elif volatility > 50:
                    risk_score += 1

            # 资金费率风险
            funding_info = market_data.get("funding_info", {})
            current_rate = funding_info.get("current_rate", {}).get("funding_rate", 0)
            if abs(current_rate) > 0.001:  # 0.1%
                risk_score += 1

            # 市场整体风险
            overall_volatility = market_overview.get("volatility_assessment", "medium")
            if overall_volatility == "high":
                risk_score += 1.5

            return {
                "total_risk_score": min(risk_score, 10),
                "leverage_risk": leverage_risk,
                "volatility_risk": volatility or 0,
                "funding_rate_risk": abs(current_rate) * 1000,
                "market_risk": overall_volatility
            }

        except Exception as e:
            self.logger.error(f"评估期货风险失败: {e}")
            return {"total_risk_score": 8}

    async def _should_execute_futures_trade(
        self,
        symbol: str,
        action: str,
        confidence: float,
        risk_assessment: Dict[str, Any],
        leverage: int
    ) -> bool:
        """判断是否执行期货交易 - 完全由AI决策"""
        # 只排除明确的hold操作，其他一切交给AI决策
        return action != "hold"

    async def get_current_positions(self) -> List[Dict[str, Any]]:
        """获取当前期货持仓"""
        try:
            return await self.futures_data_manager.get_futures_positions()
        except Exception as e:
            self.logger.error(f"获取当前持仓失败: {e}")
            return []

    async def execute_futures_trading_decisions(
        self,
        decisions: List[Dict[str, Any]],
        dry_run: bool = True
    ) -> List[Dict[str, Any]]:
        """
        执行期货交易决策

        Args:
            decisions: 交易决策列表
            dry_run: 是否为模拟交易

        Returns:
            执行结果列表
        """
        execution_results = []

        for decision in decisions:
            if not decision.get("should_execute", False):
                continue

            try:
                result = await self._execute_single_futures_trade(decision, dry_run)
                execution_results.append(result)

            except Exception as e:
                self.logger.error(f"执行期货交易失败: {e}")
                execution_results.append({
                    "symbol": decision.get("symbol"),
                    "error": str(e),
                    "success": False
                })
        # 执行完毕后做一次遗留TP/SL清理，避免仓位关闭后订单堆积
        try:
            if not dry_run:
                await self.cleanup_orphan_tp_sl_orders()
        except Exception as e:
            self.logger.warning(f"清理遗留TP/SL时出错: {e}")

        return execution_results

    async def _execute_single_futures_trade(
        self,
        decision: Dict[str, Any],
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """执行单个期货交易"""
        symbol = decision["symbol"]
        action = decision["action"].lower()
        usdt_amount = decision.get("usdt_amount")
        leverage = decision["leverage"]

        if dry_run:
            # 模拟期货交易
            self.logger.info(f"[模拟期货交易] {action.upper()} {symbol}, 金额: {usdt_amount if usdt_amount is not None else 'N/A'} USDT, 杠杆: {leverage}x")

            # 更新模拟持仓
            if action in ["long", "short", "buy", "sell", "add_to_long", "add_to_short", "close_long", "close_short", "reduce_long", "reduce_short", "adjust_tp_sl", "cancel_tp_sl"]:
                if action in ["long", "buy", "add_to_long"]:
                    side = "LONG"
                elif action in ["short", "sell", "add_to_short"]:
                    side = "SHORT"
                elif action in ["close_long", "reduce_long"]:
                    side = "SELL"
                elif action in ["close_short", "reduce_short"]:
                    side = "BUY"
                else:
                    side = "N/A"
                self.current_positions[symbol] = {
                    "action": action,
                    "side": side,
                    "amount_usdt": usdt_amount,
                    "leverage": leverage,
                    "entry_price": decision["current_price"],
                    "stop_loss": decision["stop_loss_price"],
                    "take_profit": decision["take_profit_prices"],
                    "timestamp": datetime.now().isoformat()
                }

            return {
                "symbol": symbol,
                "action": action,
                "side": side,
                "usdt_amount": usdt_amount,
                "leverage": leverage,
                "price": decision["current_price"],
                "success": True,
                "dry_run": True,
                "timestamp": datetime.now().isoformat()
            }

        else:
            # 实际期货交易
            return await self._execute_real_futures_trade(decision)

    async def _execute_real_futures_trade(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """执行真实的期货交易下单"""
        symbol = decision["symbol"]
        action = decision["action"].lower()
        usdt_amount = decision.get("usdt_amount")
        leverage = decision["leverage"]
        current_price = decision["current_price"]
        usdt_amount = decision.get("usdt_amount")

        try:
            # 1. 检查安全配置
            safety_config = self.config.get("trading", {}).get("safety", {})
            if not safety_config.get("real_trading_enabled", False):
                self.logger.error("真实交易未启用，请在配置中设置 trading.safety.real_trading_enabled: true")
                return {
                    "symbol": symbol,
                    "action": action,
                    "success": False,
                    "error": "真实交易未启用",
                    "timestamp": datetime.now().isoformat()
                }

            # 2. 执行交易前安全检查（仅开仓/加仓检查余额）
            open_like_actions = ["long", "buy", "short", "sell", "add_to_long", "add_to_short"]
            if action in open_like_actions:
                safety_check = await self._perform_pre_trade_safety_checks(decision, safety_config)
                if not safety_check["passed"]:
                    self.logger.error(f"交易前安全检查失败: {safety_check['reason']}")
                    return {
                        "symbol": symbol,
                        "action": action,
                        "success": False,
                        "error": f"安全检查失败: {safety_check['reason']}",
                        "timestamp": datetime.now().isoformat()
                    }

            # 3. 设置杠杆（仅开/加仓动作设置，避免在风控维护或减/平仓时触发多余错误）
            if action in open_like_actions:
                await self._set_leverage(symbol, leverage)

            # 4. 确定订单方向 + reduceOnly
            reduce_only = False
            if action in ["long", "buy", "add_to_long"]:
                side = "BUY"
            elif action in ["short", "sell", "add_to_short"]:
                side = "SELL"
            elif action in ["close_long", "reduce_long"]:
                side = "SELL"; reduce_only = True
            elif action in ["close_short", "reduce_short"]:
                side = "BUY"; reduce_only = True
            elif action in ["adjust_tp_sl", "cancel_tp_sl"]:
                side = "BUY"  # 占位
            else:
                side = "BUY"

            # 5. 计算实际交易数量
            if action in ["close_long", "close_short", "reduce_long", "reduce_short"]:
                # 无持仓视为错误，按失败与告警处理
                pos = await self._get_position_info(symbol)
                if not pos or abs(float(pos.get("position_amount", 0))) <= 0:
                    raise Exception("无持仓可减/平")
                quantity = await self._calculate_reduce_quantity(symbol, action, current_price, decision)
            elif action in ["adjust_tp_sl", "cancel_tp_sl"]:
                quantity = 0.0
            else:
                quantity = await self._calculate_trade_quantity(symbol, 0.0, current_price, leverage, usdt_amount=usdt_amount)

            # 6. 根据AI建议选择订单类型
            order_settings = self.config.get("trading", {}).get("order_settings", {})
            ai_order_type = decision.get("order_type", "").upper()

            # AI建议优先，配置文件作为备用
            if ai_order_type in ["MARKET", "LIMIT"]:
                order_type = ai_order_type
                self.logger.info(f"使用AI建议的订单类型: {order_type}")
                if decision.get("order_reasoning"):
                    self.logger.info(f"AI选择理由: {decision['order_reasoning']}")
            else:
                order_type = order_settings.get("default_order_type", "MARKET")
                self.logger.info(f"使用配置文件默认订单类型: {order_type}")

            # 7. 如果是仅调整/取消止盈止损
            if action in ["adjust_tp_sl", "cancel_tp_sl"]:
                await self._cancel_tp_sl_orders(symbol)
                if action == "adjust_tp_sl":
                    pos = await self._get_position_info(symbol)
                    if not pos:
                        return {"symbol": symbol, "action": action, "success": False, "error": "无持仓可调整"}
                    pos_qty = abs(float(pos.get("position_amount", 0)))
                    if pos_qty <= 0:
                        return {"symbol": symbol, "action": action, "success": False, "error": "持仓数量为0"}
                    await self._set_stop_loss_take_profit_orders(
                        symbol,
                        side="BUY" if pos.get("position_amount", 0) > 0 else "SELL",
                        quantity=pos_qty,
                        stop_loss_price=decision.get("stop_loss_price"),
                        take_profit_prices=decision.get("take_profit_prices") or []
                    )
                return {
                    "symbol": symbol,
                    "action": action,
                    "side": side,
                    "usdt_amount": usdt_amount,
                    "leverage": leverage,
                    "price": current_price,
                    "quantity": quantity,
                    "order_type": order_type,
                    "success": True,
                    "dry_run": False,
                    "timestamp": datetime.now().isoformat()
                }

            # 8. 执行下单（确保名义价值最小，reduceOnly时不强制）
            min_notional = float(order_settings.get("min_notional_usdt", 5.0))
            if not reduce_only:
                notional_value = quantity * current_price
                if notional_value < min_notional:
                    adj_qty = min_notional / max(current_price, 1e-9)
                    self.logger.warning(f"[{symbol}] 订单名义价值({notional_value:.2f})低于最小({min_notional}), 调整数量 -> {adj_qty:.6f}")
                    quantity = adj_qty

            if order_type == "MARKET":
                order_result = await self._place_market_order(symbol, side, quantity, order_settings, reduce_only=reduce_only)
            else:
                ai_entry_price = decision.get("entry_price", current_price)
                order_result = await self._place_limit_order(symbol, side, quantity, ai_entry_price, order_settings, reduce_only=reduce_only)

            # 8. 处理下单结果
            if order_result["success"]:
                self.logger.info(f"[真实交易成功] {side} {symbol}, 数量: {quantity:.6f}, 订单类型: {order_type}")

                # 更新内部持仓记录
                self.current_positions[symbol] = {
                    "action": action,
                    "side": "LONG" if side == "BUY" else "SHORT",
                    "amount_usdt": usdt_amount,
                    "leverage": leverage,
                    "entry_price": order_result.get("price", current_price),
                    "stop_loss": decision["stop_loss_price"],
                    "take_profit": decision["take_profit_prices"],
                    "order_id": order_result.get("order_id"),
                    "timestamp": datetime.now().isoformat()
                }

                # 仅对开/加仓类动作设置止盈止损；
                # 减/平仓或风控维护类不自动挂新TP/SL，避免无持仓时触发 -2021（订单将立即触发）
                if action in ["long", "buy", "short", "sell", "add_to_long", "add_to_short"]:
                    # 先清理历史TP/SL，避免堆积；随后基于最新持仓总量挂新TP/SL
                    await self._cancel_tp_sl_orders(symbol)
                    total_qty = quantity
                    try:
                        pos = await self._get_position_info(symbol)
                        if pos:
                            pq = abs(float(pos.get("position_amount", 0)))
                            if pq > 0:
                                total_qty = pq
                    except Exception:
                        pass
                    await self._set_stop_loss_take_profit_orders(
                        symbol,
                        side,
                        total_qty,
                        decision["stop_loss_price"],
                        decision["take_profit_prices"]
                    )
                elif action in ["close_long", "close_short", "reduce_long", "reduce_short"]:
                    # 减/平仓成功后，如仓位为0，清理遗留TP/SL
                    try:
                        pos = await self._get_position_info(symbol)
                        if not pos or abs(float(pos.get("position_amount", 0))) <= 0:
                            await self._cancel_tp_sl_orders(symbol)
                    except Exception:
                        pass

                return {
                    "symbol": symbol,
                    "action": action,
                    "side": side,
                    "usdt_amount": usdt_amount,
                    "leverage": leverage,
                    "price": order_result.get("price", current_price),
                    "quantity": quantity,
                    "order_id": order_result.get("order_id"),
                    "order_type": order_type,
                    "success": True,
                    "dry_run": False,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                self.logger.error(f"[真实交易失败] {side} {symbol}, 错误: {order_result['error']}")
                await self._trigger_alarm(f"下单失败 {symbol} {side}: {order_result['error']}")
                return {
                    "symbol": symbol,
                    "action": action,
                    "success": False,
                    "error": order_result["error"],
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            self.logger.error(f"执行真实期货交易失败: {e}")
            await self._trigger_alarm(f"执行真实期货交易失败 {symbol}: {e}")
            return {
                "symbol": symbol,
                "action": action,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def _set_stop_loss_take_profit_orders(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss_price: float,
        take_profit_prices: List[float]
    ):
        """设置止盈止损订单"""
        try:
            # 获取tick size和当前价格，用于校验与对齐
            exchange_info = await self.futures_data_manager.get_futures_exchange_info()
            tick_size = 0.01
            price_precision = 2
            for s in exchange_info.get("symbols", []):
                if s.get("symbol") == symbol:
                    for f in s.get("filters", []):
                        if f.get("filterType") == "PRICE_FILTER":
                            try:
                                tick_size = float(f.get("tickSize", 0.01))
                                # 计算精度
                                tick_str = f"{tick_size:.10f}".rstrip('0')
                                price_precision = len(tick_str.split('.')[-1]) if '.' in tick_str else 0
                            except Exception:
                                tick_size = 0.01
                                price_precision = 2
                            break
                    break

            # 当前价格（用于方向校验与“避免立即触发”）
            try:
                tk = await self.futures_data_manager.client.futures_ticker(symbol=symbol)
                current_price = float(tk.get("lastPrice") or tk.get("price") or tk.get("markPrice") or 0)
            except Exception:
                current_price = 0

            def round_up_to_tick(p: float) -> float:
                if tick_size <= 0:
                    return round(p, price_precision)
                return round(math.ceil(p / tick_size) * tick_size, price_precision)

            def round_down_to_tick(p: float) -> float:
                if tick_size <= 0:
                    return round(p, price_precision)
                return round(math.floor(p / tick_size) * tick_size, price_precision)

            # 设置止损订单
            if stop_loss_price:
                stop_side = "SELL" if side == "BUY" else "BUY"

                # 方向与距离校验，避免立即触发
                if current_price > 0:
                    if side == "BUY":  # 多头，止损应低于当前价至少1 tick
                        target = min(stop_loss_price, current_price - tick_size)
                        if target != stop_loss_price:
                            self.logger.info(f"[{symbol}] 止损价调整: {stop_loss_price} -> {target} (避免立即触发)")
                        stop_loss_price = round_down_to_tick(target)
                    else:  # 空头，止损应高于当前价至少1 tick
                        target = max(stop_loss_price, current_price + tick_size)
                        if target != stop_loss_price:
                            self.logger.info(f"[{symbol}] 止损价调整: {stop_loss_price} -> {target} (避免立即触发)")
                        stop_loss_price = round_up_to_tick(target)

                stop_order = await self._retry_api_call(
                    self.binance_client.futures_create_order,
                    symbol=symbol,
                    side=stop_side,
                    type="STOP_MARKET",
                    quantity=quantity,
                    stopPrice=stop_loss_price,
                    timeInForce="GTC",
                    reduceOnly=True
                )

                self.logger.info(f"[止损订单] {symbol} 止损价格: {stop_loss_price}, 订单ID: {stop_order.get('orderId')}")

            # 设置止盈订单
            if take_profit_prices and len(take_profit_prices) > 0:
                take_profit_side = "SELL" if side == "BUY" else "BUY"

                # 使用第一个止盈价格设置主要止盈订单
                tp_price = take_profit_prices[0]

                # 方向与距离校验，避免立即触发
                if current_price > 0:
                    if side == "BUY":  # 多头，止盈应高于当前价至少1 tick
                        target = max(tp_price, current_price + tick_size)
                        if target != tp_price:
                            self.logger.info(f"[{symbol}] 止盈价调整: {tp_price} -> {target} (避免立即触发)")
                        tp_price = round_up_to_tick(target)
                    else:  # 空头，止盈应低于当前价至少1 tick
                        target = min(tp_price, current_price - tick_size)
                        if target != tp_price:
                            self.logger.info(f"[{symbol}] 止盈价调整: {tp_price} -> {target} (避免立即触发)")
                        tp_price = round_down_to_tick(target)

                tp_order = await self._retry_api_call(
                    self.binance_client.futures_create_order,
                    symbol=symbol,
                    side=take_profit_side,
                    type="TAKE_PROFIT_MARKET",
                    quantity=quantity,
                    stopPrice=tp_price,
                    timeInForce="GTC",
                    reduceOnly=True
                )

                self.logger.info(f"[止盈订单] {symbol} 止盈价格: {tp_price}, 订单ID: {tp_order.get('orderId')}")

        except Exception as e:
            self.logger.error(f"设置止盈止损订单失败 {symbol}: {e}")
            await self._trigger_alarm(f"设置止盈止损失败 {symbol}: {e}")
            # 不抛出异常，因为主订单已经成功了

    async def _perform_pre_trade_safety_checks(self, decision: Dict[str, Any], safety_config: Dict[str, Any]) -> Dict[str, Any]:
        """执行交易前安全检查"""
        checks = safety_config.get("pre_trade_checks", {})
        symbol = decision["symbol"]
        current_price = decision["current_price"]
        leverage = decision.get("leverage", 1)  # 获取杠杆倍数
        usdt_amount = decision.get("usdt_amount")

        try:
            # 检查账户余额
            if checks.get("check_balance", True):
                account_info = await self.futures_data_manager.get_futures_account_info()
                if "error" in account_info:
                    return {"passed": False, "reason": f"无法获取账户信息: {account_info['error']}"}

                available_balance = float(account_info.get("available_balance", 0))
                # 以实际投入金额检查保证金（usdt_amount为准；没有金额时不拦截）
                if usdt_amount is not None:
                    try:
                        required_margin = float(usdt_amount)
                    except Exception:
                        required_margin = 0.0
                else:
                    required_margin = 0.0
                if available_balance < required_margin:
                    return {"passed": False, "reason": f"可用余额不足: 需要{required_margin:.2f} USDT，可用{available_balance:.2f} USDT"}

            # 检查价格异常
            if checks.get("check_price_anomaly", True):
                # 获取24小时价格统计
                try:
                    ticker = await self.futures_data_manager.client.futures_ticker(symbol=symbol)
                    price_change_percent = float(ticker.get("priceChangePercent", 0))

                    # 如果24小时价格变动超过20%，认为存在异常
                    if abs(price_change_percent) > 20:
                        return {"passed": False, "reason": f"价格异常波动: {price_change_percent:.2f}%"}
                except Exception as e:
                    self.logger.warning(f"检查价格异常失败: {e}")

            # 检查市场流动性
            if checks.get("check_liquidity", True):
                try:
                    depth = await self.futures_data_manager.client.futures_order_book(symbol=symbol, limit=5)
                    best_bid = float(depth['bids'][0][0]) if depth['bids'] else 0
                    best_ask = float(depth['asks'][0][0]) if depth['asks'] else 0

                    if best_bid == 0 or best_ask == 0:
                        return {"passed": False, "reason": "市场流动性不足"}

                    spread_percent = (best_ask - best_bid) / best_bid * 100
                    if spread_percent > 1:  # 价差超过1%认为流动性不足
                        return {"passed": False, "reason": f"价差过大: {spread_percent:.3f}%"}
                except Exception as e:
                    self.logger.warning(f"检查市场流动性失败: {e}")

            return {"passed": True, "reason": "所有安全检查通过"}

        except Exception as e:
            return {"passed": False, "reason": f"安全检查异常: {str(e)}"}

    async def _set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆倍数"""
        try:
            await self._retry_api_call(
                self.futures_data_manager.client.futures_change_leverage,
                symbol=symbol,
                leverage=leverage
            )
            self.logger.info(f"设置 {symbol} 杠杆为 {leverage}x")
            return True
        except Exception as e:
            self.logger.error(f"设置杠杆失败 {symbol}: {e}")
            return False

    async def _calculate_trade_quantity(self, symbol: str, position_size: float, current_price: float, leverage: int, usdt_amount: Optional[float] = None) -> float:
        """计算实际交易数量"""
        try:
            # 获取可用余额
            account_info = await self.futures_data_manager.get_futures_account_info()
            if isinstance(account_info, dict) and account_info.get("error"):
                raise Exception(f"无法获取账户信息: {account_info['error']}")
            available_balance = float(account_info.get("available_balance", 0))

            mode = "金额" if usdt_amount is not None else "金额(默认0)"
            specified = (usdt_amount if usdt_amount is not None else 0.0)
            self.logger.info(
                f"[{symbol}] 计算交易数量: 可用余额={available_balance:.2f} USDT, 模式={mode}, 指定金额={specified:.2f}, 杠杆={leverage}x"
            )

            if available_balance <= 0:
                raise Exception(f"可用余额不足: {available_balance}")

            # 计算实际投入的USDT（以金额为准）
            if usdt_amount is None:
                usdt_amount = 0.0
            else:
                if usdt_amount > available_balance:
                    self.logger.warning(f"指定金额 {usdt_amount:.2f} 超过可用余额 {available_balance:.2f}，调整为可用余额")
                    usdt_amount = available_balance

            # 计算合约名义价值（考虑杠杆）
            notional_value = usdt_amount * leverage

            # 计算实际交易数量
            quantity = notional_value / current_price

            self.logger.info(f"[{symbol}] 投入金额={usdt_amount:.2f} USDT, 名义价值={notional_value:.2f} USDT, 原始数量={quantity:.6f}")

            # 获取交易所信息，确定精度
            exchange_info = await self.futures_data_manager.get_futures_exchange_info()
            symbol_info = None

            for s in exchange_info.get("symbols", []):
                if s["symbol"] == symbol:
                    symbol_info = s
                    break

            if not symbol_info:
                raise Exception(f"找不到 {symbol} 的交易所信息")

            # 获取数量精度和最小数量
            quantity_precision = 3  # 默认精度
            min_qty = 0.001  # 默认最小数量
            step_size = 0.001  # 默认步长

            for filter_info in symbol_info.get("filters", []):
                if filter_info["filterType"] == "LOT_SIZE":
                    step_size = float(filter_info["stepSize"])
                    min_qty = float(filter_info.get("minQty", step_size))
                    # 计算精度：步长的小数位数
                    if step_size >= 1:
                        quantity_precision = 0
                    else:
                        step_size_str = f"{step_size:.10f}".rstrip('0')
                        if '.' in step_size_str:
                            quantity_precision = len(step_size_str.split('.')[-1])
                        else:
                            quantity_precision = 0
                    break

            # 确保数量符合交易所要求
            if quantity < min_qty:
                self.logger.warning(f"[{symbol}] 计算数量 {quantity:.6f} 小于最小数量 {min_qty}，调整为最小数量")
                quantity = min_qty

            # 确保数量是步长的整数倍
            if step_size > 0:
                quantity = round(quantity / step_size) * step_size
                # 再次应用精度
                quantity = round(quantity, quantity_precision)

            # 最终检查
            if quantity < min_qty:
                quantity = min_qty

            self.logger.info(f"[{symbol}] 最终交易数量={quantity:.6f}, 精度={quantity_precision}, 最小数量={min_qty}, 步长={step_size}")

            if quantity <= 0:
                raise Exception(f"计算出的交易数量为零或负数: {quantity}")

            return quantity

        except Exception as e:
            self.logger.error(f"计算交易数量失败: {e}")
            # 抛出异常，不使用错误的fallback逻辑
            raise Exception(f"无法计算交易数量: {e}")

    async def _calculate_reduce_quantity(self, symbol: str, action: str, current_price: float, decision: Dict[str, Any]) -> float:
        """计算减仓/平仓数量，基于当前持仓和AI给定参数"""
        try:
            pos = await self._get_position_info(symbol)
            if not pos:
                raise Exception("无持仓可减/平")

            current_amt = float(pos.get("position_amount", 0))
            abs_amt = abs(current_amt)
            if abs_amt <= 0:
                raise Exception("持仓数量为0")

            # 计算目标数量
            qty = abs_amt

            # 支持 reduce_percent / close_percent / reduce_usdt
            reduce_percent = decision.get("reduce_percent") or decision.get("close_percent")
            reduce_usdt = decision.get("reduce_usdt")
            if reduce_percent is not None:
                try:
                    rp = float(reduce_percent)
                    rp = max(0.0, min(100.0, rp))
                    qty = abs_amt * (rp / 100.0)
                except Exception:
                    pass
            elif reduce_usdt is not None:
                try:
                    ru = float(reduce_usdt)
                    qty = max(0.0, ru / max(current_price, 1e-9))
                except Exception:
                    pass

            # 不超过当前持仓
            if qty > abs_amt:
                qty = abs_amt

            # 适配交易所数量步长
            exchange_info = await self.futures_data_manager.get_futures_exchange_info()
            symbol_info = next((s for s in exchange_info.get("symbols", []) if s.get("symbol") == symbol), None)
            step_size = 0.001
            quantity_precision = 3
            if symbol_info:
                for f in symbol_info.get("filters", []):
                    if f.get("filterType") == "LOT_SIZE":
                        step_size = float(f.get("stepSize", 0.001))
                        if step_size >= 1:
                            quantity_precision = 0
                        else:
                            step_size_str = f"{step_size:.10f}".rstrip('0')
                            quantity_precision = len(step_size_str.split('.')[-1]) if '.' in step_size_str else 0
                        break
            if step_size > 0:
                qty = round(qty / step_size) * step_size
                qty = round(qty, quantity_precision)
            if qty <= 0:
                raise Exception("计算的减仓数量为0")

            self.logger.info(f"[{symbol}] 计算减仓/平仓数量={qty:.6f} (当前持仓={abs_amt:.6f})")
            return qty
        except Exception as e:
            self.logger.error(f"计算减仓/平仓数量失败: {e}")
            raise

    async def _get_position_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取单个币种的当前持仓信息"""
        try:
            positions = await self.get_current_positions()
            for p in positions:
                if p.get("symbol") == symbol and float(p.get("position_amount", 0)) != 0:
                    return p
            return None
        except Exception:
            return None

    async def _place_market_order(self, symbol: str, side: str, quantity: float, order_settings: Dict[str, Any], reduce_only: bool = False) -> Dict[str, Any]:
        """下市价单"""
        try:
            # 获取市价单设置
            market_settings = order_settings.get("market_order", {})

            order = await self._retry_api_call(
                self.futures_data_manager.client.futures_create_order,
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                reduceOnly=reduce_only
            )

            return {
                "success": True,
                "order_id": order.get("orderId"),
                "price": float(order.get("avgPrice", 0)) if order.get("avgPrice") else None,
                "quantity": float(order.get("executedQty", quantity)),
                "order": order
            }

        except Exception as e:
            self.logger.error(f"下市价单失败: {e}")
            await self._trigger_alarm(f"下市价单失败 {symbol}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _place_limit_order(self, symbol: str, side: str, quantity: float, ai_entry_price: float, order_settings: Dict[str, Any], reduce_only: bool = False) -> Dict[str, Any]:
        """下限价单"""
        try:
            # 获取限价单设置
            limit_settings = order_settings.get("limit_order", {})
            max_wait_time = limit_settings.get("max_wait_time", 300)

            # 使用AI指定的entry_price作为limit_price
            limit_price = ai_entry_price
            self.logger.info(f"使用AI指定的限价: {limit_price}")

            # 获取价格精度
            exchange_info = await self.futures_data_manager.get_futures_exchange_info()
            price_precision = 2  # 默认精度

            for s in exchange_info.get("symbols", []):
                if s["symbol"] == symbol:
                    for filter_info in s.get("filters", []):
                        if filter_info["filterType"] == "PRICE_FILTER":
                            tick_size = float(filter_info["tickSize"])
                            price_precision = len(str(tick_size).split('.')[-1].rstrip('0'))
                            break
                    break

            limit_price = round(limit_price, price_precision)

            order = await self._retry_api_call(
                self.futures_data_manager.client.futures_create_order,
                symbol=symbol,
                side=side,
                type="LIMIT",
                timeInForce="GTC",
                quantity=quantity,
                price=limit_price,
                reduceOnly=reduce_only
            )

            order_id = order.get("orderId")

            # 等待订单成交或超时
            start_time = datetime.now()
            while (datetime.now() - start_time).seconds < max_wait_time:
                await asyncio.sleep(1)

                # 检查订单状态
                order_status = await self._retry_api_call(
                    self.futures_data_manager.client.futures_get_order,
                    symbol=symbol,
                    orderId=order_id
                )

                if order_status["status"] == "FILLED":
                    return {
                        "success": True,
                        "order_id": order_id,
                        "price": float(order_status.get("avgPrice", limit_price)),
                        "quantity": float(order_status.get("executedQty", quantity)),
                        "order": order_status
                    }
                elif order_status["status"] in ["CANCELED", "REJECTED", "EXPIRED"]:
                    return {
                        "success": False,
                        "error": f"订单状态: {order_status['status']}"
                    }

            # 超时：取消订单并返回失败（无回退市价逻辑）
            try:
                await self._retry_api_call(
                    self.futures_data_manager.client.futures_cancel_order,
                    symbol=symbol,
                    orderId=order_id
                )
                self.logger.warning(f"限价单超时，已取消订单 {order_id}")
            except Exception:
                pass

            return {
                "success": False,
                "error": f"限价单超时未成交，已取消"
            }

        except Exception as e:
            self.logger.error(f"下限价单失败: {e}")
            await self._trigger_alarm(f"下限价单失败 {symbol}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def check_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """检查订单状态"""
        try:
            order_info = await self._retry_api_call(
                self.futures_data_manager.client.futures_get_order,
                symbol=symbol,
                orderId=order_id
            )

            return {
                "success": True,
                "order_id": order_id,
                "symbol": symbol,
                "status": order_info["status"],
                "side": order_info["side"],
                "type": order_info["type"],
                "original_quantity": float(order_info["origQty"]),
                "executed_quantity": float(order_info["executedQty"]),
                "avg_price": float(order_info.get("avgPrice", 0)),
                "time": int(order_info["time"]),
                "update_time": int(order_info["updateTime"]),
                "raw_order": order_info
            }

        except Exception as e:
            self.logger.error(f"检查订单状态失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "order_id": order_id,
                "symbol": symbol
            }

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """取消订单"""
        try:
            cancel_result = await self._retry_api_call(
                self.futures_data_manager.client.futures_cancel_order,
                symbol=symbol,
                orderId=order_id
            )

            self.logger.info(f"成功取消订单 {order_id}")
            return {
                "success": True,
                "order_id": order_id,
                "symbol": symbol,
                "cancel_result": cancel_result
            }

        except Exception as e:
            self.logger.error(f"取消订单失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "order_id": order_id,
                "symbol": symbol
            }

    async def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """获取所有未完成订单"""
        try:
            if symbol:
                orders = await self._retry_api_call(self.futures_data_manager.client.futures_get_open_orders, symbol=symbol)
            else:
                orders = await self._retry_api_call(self.futures_data_manager.client.futures_get_open_orders)

            formatted_orders = []
            for order in orders:
                formatted_orders.append({
                    "order_id": order["orderId"],
                    "symbol": order["symbol"],
                    "status": order["status"],
                    "side": order["side"],
                    "type": order["type"],
                    "original_quantity": float(order["origQty"]),
                    "executed_quantity": float(order["executedQty"]),
                    "price": float(order.get("price", 0)),
                    "avg_price": float(order.get("avgPrice", 0)),
                    "time": int(order["time"]),
                    "update_time": int(order["updateTime"])
                })

            return formatted_orders

        except Exception as e:
            self.logger.error(f"获取未完成订单失败: {e}")
            return []

    async def _cancel_tp_sl_orders(self, symbol: str) -> None:
        """取消某个币种的所有止盈/止损订单"""
        try:
            open_orders = await self._retry_api_call(self.futures_data_manager.client.futures_get_open_orders, symbol=symbol)
            for order in open_orders or []:
                otype = order.get("type", "")
                if otype in ("STOP_MARKET", "TAKE_PROFIT_MARKET"):
                    try:
                        await self._retry_api_call(self.futures_data_manager.client.futures_cancel_order, symbol=symbol, orderId=order.get("orderId"))
                        self.logger.info(f"已取消{symbol} {otype} 订单 {order.get('orderId')}")
                    except Exception as ce:
                        self.logger.warning(f"取消{symbol} {otype} 订单失败: {ce}")
        except Exception as e:
            self.logger.warning(f"获取/取消TP/SL订单失败 {symbol}: {e}")

    async def cleanup_orphan_tp_sl_orders(self) -> None:
        """清理无持仓币种上的遗留止盈/止损订单。
        典型场景：仓位被TP/SL触发后已关闭，但另一侧订单仍遗留在当前委托里。
        """
        try:
            # 收集当前仍有持仓的币种
            positions = await self.get_current_positions()
            active_symbols = set()
            for p in positions or []:
                try:
                    if p.get("symbol") and abs(float(p.get("position_amount", 0))) > 0:
                        active_symbols.add(p.get("symbol"))
                except Exception:
                    continue

            # 拉取所有未完成订单
            try:
                open_orders = await self._retry_api_call(self.futures_data_manager.client.futures_get_open_orders)
            except Exception as e:
                self.logger.warning(f"获取所有未完成订单失败: {e}")
                return

            # 对无持仓的币种，撤销所有TP/SL
            for order in open_orders or []:
                try:
                    sym = order.get("symbol")
                    if not sym or sym in active_symbols:
                        continue
                    otype = order.get("type", "")
                    if otype in ("STOP_MARKET", "TAKE_PROFIT_MARKET"):
                        try:
                            await self._retry_api_call(
                                self.futures_data_manager.client.futures_cancel_order,
                                symbol=sym,
                                orderId=order.get("orderId")
                            )
                            self.logger.info(f"[清理] 无持仓 {sym} 撤销{otype}订单 {order.get('orderId')}")
                        except Exception as ce:
                            self.logger.warning(f"[清理] 撤销{sym} {otype} 订单失败: {ce}")
                except Exception:
                    continue
        except Exception as e:
            self.logger.warning(f"执行TP/SL孤儿清理失败: {e}")

    async def _retry_api_call(self, func, *args, retries: int = 3, delay: float = 2.0, backoff: float = 2.0, **kwargs):
        """带重试的API调用。
        - 网络连接失败（aiohttp/超时/系统网络错误）：统一在5分钟内尝试5次（间隔约 15s,30s,60s,120s）。
        - 业务类错误（BinanceAPIException）：不做长时间重试，直接抛出（由上层逻辑处理）。
        - 其他异常：按原始短重试策略（默认3次、指数退避）。
        """
        # 网络错误重试策略：5次内完成，总等待<=~225s
        network_max_attempts = 5
        network_delays = [15, 30, 60, 120]  # between attempts

        attempt = 1
        last_err = None
        while True:
            try:
                return await func(*args, **kwargs)
            except BinanceAPIException as e:  # 业务错误不做长重试
                last_err = e
                self.logger.error(f"API业务错误: {e}")
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                last_err = e
                if attempt >= network_max_attempts:
                    self.logger.error(f"网络错误重试耗尽({attempt}/{network_max_attempts}): {e}")
                    break
                # 计算下一次等待
                wait = network_delays[attempt-1] if attempt-1 < len(network_delays) else network_delays[-1]
                self.logger.warning(f"网络错误({attempt}/{network_max_attempts})，{e}，{wait}s后重试…")
                await asyncio.sleep(wait)
                attempt += 1
                continue
            except Exception as e:
                # 其他未知异常：保留原始短重试策略
                last_err = e
                if attempt >= retries:
                    self.logger.error(f"异常重试耗尽({attempt}/{retries}): {e}")
                    break
                self.logger.warning(f"异常({attempt}/{retries})，{e}，{delay:.1f}s后重试…")
                await asyncio.sleep(delay)
                attempt += 1
                delay *= backoff
                continue

        # 最终失败，触发报警
        await self._trigger_alarm(f"API调用重试失败: {last_err}")
        raise last_err

    async def _trigger_alarm(self, message: str) -> None:
        """写入报警信息到 alarm.txt，并记录日志"""
        try:
            alarm_path = os.path.join(os.getcwd(), "alarm.txt")
            with open(alarm_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()} - {message}\n")
            self.logger.error(f"[ALARM] {message}")
        except Exception as e:
            self.logger.error(f"写入报警文件失败: {e}")

    async def wait_for_order_completion(self, symbol: str, order_id: str, max_wait_time: int = 300) -> Dict[str, Any]:
        """等待订单完成"""
        start_time = datetime.now()
        check_interval = 2  # 每2秒检查一次

        self.logger.info(f"开始监控订单 {order_id} 状态，最大等待时间: {max_wait_time}秒")

        while (datetime.now() - start_time).seconds < max_wait_time:
            try:
                order_status = await self.check_order_status(symbol, order_id)

                if not order_status["success"]:
                    return {
                        "completed": False,
                        "error": f"无法获取订单状态: {order_status['error']}",
                        "order_id": order_id
                    }

                status = order_status["status"]
                self.logger.debug(f"订单 {order_id} 状态: {status}")

                if status == "FILLED":
                    self.logger.info(f"订单 {order_id} 已完全成交")
                    return {
                        "completed": True,
                        "status": "FILLED",
                        "order_info": order_status,
                        "order_id": order_id
                    }
                elif status in ["CANCELED", "REJECTED", "EXPIRED"]:
                    self.logger.warning(f"订单 {order_id} 状态: {status}")
                    return {
                        "completed": True,
                        "status": status,
                        "order_info": order_status,
                        "order_id": order_id
                    }
                elif status == "PARTIALLY_FILLED":
                    executed_qty = order_status["executed_quantity"]
                    original_qty = order_status["original_quantity"]
                    fill_percent = (executed_qty / original_qty) * 100 if original_qty > 0 else 0
                    self.logger.info(f"订单 {order_id} 部分成交: {fill_percent:.1f}%")

                await asyncio.sleep(check_interval)

            except Exception as e:
                self.logger.error(f"监控订单状态时发生错误: {e}")
                await asyncio.sleep(check_interval)

        # 超时
        self.logger.warning(f"订单 {order_id} 监控超时，开始检查最终状态")
        final_status = await self.check_order_status(symbol, order_id)

        return {
            "completed": False,
            "timeout": True,
            "final_status": final_status,
            "order_id": order_id
        }

    async def confirm_trade_execution(self, trade_result: Dict[str, Any]) -> Dict[str, Any]:
        """确认交易执行结果"""
        if not trade_result.get("success", False) or trade_result.get("dry_run", True):
            return {
                "confirmed": False,
                "reason": "交易未成功或为模拟交易",
                "trade_result": trade_result
            }

        symbol = trade_result["symbol"]
        order_id = trade_result.get("order_id")

        if not order_id:
            return {
                "confirmed": False,
                "reason": "缺少订单ID",
                "trade_result": trade_result
            }

        try:
            # 检查订单最终状态
            order_status = await self.check_order_status(symbol, order_id)

            if not order_status["success"]:
                return {
                    "confirmed": False,
                    "reason": f"无法确认订单状态: {order_status['error']}",
                    "trade_result": trade_result,
                    "order_id": order_id
                }

            # 验证实际持仓变化
            current_positions = await self.get_current_positions()
            position_found = False

            for pos in current_positions:
                if pos["symbol"] == symbol and float(pos.get("position_amount", 0)) != 0:
                    position_found = True
                    break

            confirmation = {
                "confirmed": True,
                "order_status": order_status,
                "position_updated": position_found,
                "trade_result": trade_result,
                "confirmation_time": datetime.now().isoformat()
            }

            if order_status["status"] == "FILLED":
                confirmation["execution_confirmed"] = True
                self.logger.info(f"交易执行确认成功: {symbol} 订单 {order_id}")
            else:
                confirmation["execution_confirmed"] = False
                confirmation["reason"] = f"订单状态: {order_status['status']}"
                self.logger.warning(f"交易执行确认失败: {symbol} 订单 {order_id}, 状态: {order_status['status']}")

            return confirmation

        except Exception as e:
            self.logger.error(f"确认交易执行时发生错误: {e}")
            return {
                "confirmed": False,
                "reason": f"确认过程异常: {str(e)}",
                "trade_result": trade_result,
                "order_id": order_id
            }
