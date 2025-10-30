"""
U本位合约市场数据获取模块
支持多时间周期历史数据和深度技术分析
"""

import sys
import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加python-binance路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../python-binance-master/python-binance-master'))

from binance import AsyncClient, Client
from binance.exceptions import BinanceAPIException


class FuturesDataManager:
    """U本位合约数据管理器"""

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.client = None
        self.logger = logging.getLogger(__name__)

        # U本位合约目标币种
        self.target_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

        # 多时间周期配置 - 保证技术指标计算准确性
        self.timeframes = {
            "1m": {"limit": 200, "description": "1分钟"},    # 确保SMA200等长期指标可计算
            "5m": {"limit": 288, "description": "5分钟"},    # 24小时数据
            "15m": {"limit": 336, "description": "15分钟"},  # 新增：3.5天数据，详细分析
            "1h": {"limit": 720, "description": "1小时"},    # 30天数据
            "4h": {"limit": 180, "description": "4小时"},    # 30天数据
            "1d": {"limit": 365, "description": "日线"},     # 1年数据
            "1w": {"limit": 104, "description": "周线"},     # 2年数据
            "1M": {"limit": 36, "description": "月线"}       # 新增：3年数据，全局视角
        }

    async def __aenter__(self):
        """异步上下文管理器入口"""
        try:
            # 配置网络参数 - 增加超时时间
            requests_params = {
                'timeout': 30  # 增加超时时间到30秒
            }

            if self.api_key and self.api_secret:
                self.client = await AsyncClient.create(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    testnet=self.testnet,
                    requests_params=requests_params
                )
            else:
                # 只读模式，不需要API密钥
                self.client = await AsyncClient.create(
                    testnet=self.testnet,
                    requests_params=requests_params
                )

            self.logger.info("Binance期货客户端初始化成功")
            return self
        except Exception as e:
            self.logger.error(f"初始化Binance期货客户端失败: {e}")
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.client:
            await self.client.close_connection()

    async def get_futures_exchange_info(self) -> Dict[str, Any]:
        """获取期货交易所信息"""
        try:
            info = await self.client.futures_exchange_info()
            return info
        except BinanceAPIException as e:
            self.logger.error(f"获取期货交易所信息失败: {e}")
            return {}

    async def get_futures_account_info(self) -> Dict[str, Any]:
        """获取期货账户信息"""
        try:
            if not self.api_key or not self.api_secret:
                return {"error": "需要API密钥获取账户信息"}

            account = await self.client.futures_account()
            return {
                "total_wallet_balance": float(account.get("totalWalletBalance", 0)),
                "total_unrealized_pnl": float(account.get("totalUnrealizedPnL", 0)),
                "total_margin_balance": float(account.get("totalMarginBalance", 0)),
                "total_position_initial_margin": float(account.get("totalPositionInitialMargin", 0)),
                "total_open_order_initial_margin": float(account.get("totalOpenOrderInitialMargin", 0)),
                "available_balance": float(account.get("availableBalance", 0)),
                "max_withdraw_amount": float(account.get("maxWithdrawAmount", 0))
            }
        except BinanceAPIException as e:
            self.logger.error(f"获取期货账户信息失败: {e}")
            return {"error": str(e)}

    async def get_futures_positions(self) -> List[Dict[str, Any]]:
        """获取期货持仓信息"""
        try:
            if not self.api_key or not self.api_secret:
                return []

            positions = await self.client.futures_position_information()
            active_positions = []

            # 账户positions 用于校准杠杆字段（部分场景接口返回不一致）
            leverage_map = {}
            try:
                account = await self.client.futures_account()
                acct_positions = account.get("positions", []) if isinstance(account, dict) else []
                for ap in acct_positions:
                    sym = ap.get("symbol")
                    if sym:
                        try:
                            leverage_map[sym] = int(float(ap.get("leverage", 0)))
                        except Exception:
                            pass
            except Exception:
                pass

            for pos in positions:
                if float(pos.get("positionAmt", 0)) != 0:
                    # 计算杠杆（优先 position_information，回退 account.positions）
                    try:
                        lev_int = int(float(pos.get("leverage", 0)))
                    except Exception:
                        lev_int = 0
                    if lev_int <= 0 and leverage_map:
                        lev_int = int(leverage_map.get(pos.get("symbol"), 0))
                    if lev_int <= 0:
                        lev_int = 1

                    active_positions.append({
                        "symbol": pos.get("symbol"),
                        "position_amount": float(pos.get("positionAmt", 0)),
                        "entry_price": float(pos.get("entryPrice", 0)),
                        "mark_price": float(pos.get("markPrice", 0)),
                        # Binance字段为 unRealizedProfit
                        "unrealized_pnl": float(pos.get("unRealizedProfit", pos.get("unRealizedPnL", 0))),
                        "percentage": float(pos.get("percentage", 0)),
                        "position_side": pos.get("positionSide"),
                        "isolated": bool(pos.get("isolated", False)),
                        "leverage": lev_int
                    })

            return active_positions
        except BinanceAPIException as e:
            self.logger.error(f"获取期货持仓失败: {e}")
            return []

    async def get_open_orders(self, symbol: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """获取未完成订单信息"""
        try:
            if not self.api_key or not self.api_secret:
                return {}

            if symbol:
                orders = await self.client.futures_get_open_orders(symbol=symbol)
                return {symbol: self._format_orders(orders)}
            else:
                # 获取所有未完成订单
                orders = await self.client.futures_get_open_orders()

                # 按币种分组
                orders_by_symbol = {}
                for order in orders:
                    symbol = order['symbol']
                    if symbol not in orders_by_symbol:
                        orders_by_symbol[symbol] = []
                    orders_by_symbol[symbol].append(order)

                # 格式化每个币种的订单
                formatted_orders = {}
                for symbol, symbol_orders in orders_by_symbol.items():
                    formatted_orders[symbol] = self._format_orders(symbol_orders)

                return formatted_orders

        except BinanceAPIException as e:
            self.logger.error(f"获取未完成订单失败: {e}")
            return {}

    def _format_orders(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化订单信息"""
        formatted_orders = []
        for order in orders:
            formatted_orders.append({
                "orderId": order.get("orderId"),
                "symbol": order.get("symbol"),
                "status": order.get("status"),
                "side": order.get("side"),
                "type": order.get("type"),
                "timeInForce": order.get("timeInForce"),
                "origQty": float(order.get("origQty", 0)),
                "price": float(order.get("price", 0)),
                "stopPrice": float(order.get("stopPrice", 0)),
                "executedQty": float(order.get("executedQty", 0)),
                "time": int(order.get("time", 0)),
                "updateTime": int(order.get("updateTime", 0))
            })
        return formatted_orders

    async def get_multi_timeframe_klines(
        self,
        symbol: str,
        timeframes: List[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        获取多时间周期K线数据

        Args:
            symbol: 币种符号
            timeframes: 时间周期列表

        Returns:
            多时间周期K线数据字典
        """
        if timeframes is None:
            timeframes = ["15m", "1h", "4h", "1d", "1M"]

        multi_klines = {}

        for timeframe in timeframes:
            if timeframe not in self.timeframes:
                continue

            try:
                config = self.timeframes[timeframe]
                klines = await self.client.futures_klines(
                    symbol=symbol,
                    interval=timeframe,
                    limit=config["limit"]
                )

                formatted_klines = []
                for kline in klines:
                    formatted_klines.append({
                        'open_time': int(kline[0]),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5]),
                        'close_time': int(kline[6]),
                        'quote_asset_volume': float(kline[7]),
                        'number_of_trades': int(kline[8]),
                        'taker_buy_base_asset_volume': float(kline[9]),
                        'taker_buy_quote_asset_volume': float(kline[10])
                    })

                multi_klines[timeframe] = {
                    'data': formatted_klines,
                    'description': config['description'],
                    'count': len(formatted_klines)
                }

                self.logger.info(f"获取到{symbol} {timeframe} {len(formatted_klines)}条K线数据")

            except BinanceAPIException as e:
                self.logger.error(f"获取{symbol} {timeframe}K线数据失败: {e}")
                multi_klines[timeframe] = {'error': str(e)}

        return multi_klines

    async def calculate_advanced_indicators(
        self,
        klines_data: List[Dict],
        timeframe: str = "1h"
    ) -> Dict[str, Any]:
        """
        计算高级技术指标

        Args:
            klines_data: K线数据
            timeframe: 时间周期

        Returns:
            高级技术指标字典
        """
        if not klines_data or len(klines_data) < 50:
            return {}

        try:
            df = pd.DataFrame(klines_data)
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')

            indicators = {}

            # 基础价格信息
            current_price = df['close'].iloc[-1]
            indicators['current_price'] = current_price
            indicators['price_change_24h'] = ((current_price - df['close'].iloc[-24]) / df['close'].iloc[-24] * 100) if len(df) >= 24 else 0

            # 移动平均线系统
            df['sma_7'] = df['close'].rolling(window=7).mean()
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['sma_200'] = df['close'].rolling(window=200).mean() if len(df) >= 200 else None

            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            df['ema_50'] = df['close'].ewm(span=50).mean()

            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))

            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            # 布林带
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100

            # 波动率计算
            df['returns'] = df['close'].pct_change()
            if timeframe == "1h" and len(df) >= 168:
                volatility_7d = df['returns'].rolling(window=168).std() * np.sqrt(24) * 100  # 7天波动率
            else:
                volatility_7d = pd.Series(dtype=float)

            if timeframe == "1h" and len(df) >= 720:
                volatility_30d = df['returns'].rolling(window=720).std() * np.sqrt(24) * 100  # 30天波动率
            else:
                volatility_30d = pd.Series(dtype=float)

            # ATR (平均真实波幅)
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift())
            df['tr3'] = abs(df['low'] - df['close'].shift())
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            df['atr'] = df['tr'].rolling(window=14).mean()

            # 成交量指标
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            volume_ratio = df['volume'].iloc[-1] / df['volume_sma'].iloc[-1] if not pd.isna(df['volume_sma'].iloc[-1]) else 1

            # 获取最新值
            latest = df.iloc[-1]

            indicators.update({
                # 移动平均线
                'sma_7': latest['sma_7'] if not pd.isna(latest['sma_7']) else None,
                'sma_20': latest['sma_20'] if not pd.isna(latest['sma_20']) else None,
                'sma_50': latest['sma_50'] if not pd.isna(latest['sma_50']) else None,
                'sma_200': latest['sma_200'] if latest['sma_200'] is not None and not pd.isna(latest['sma_200']) else None,
                'ema_12': latest['ema_12'] if not pd.isna(latest['ema_12']) else None,
                'ema_26': latest['ema_26'] if not pd.isna(latest['ema_26']) else None,
                'ema_50': latest['ema_50'] if not pd.isna(latest['ema_50']) else None,

                # 趋势指标
                'rsi': latest['rsi'] if not pd.isna(latest['rsi']) else None,
                'macd': latest['macd'] if not pd.isna(latest['macd']) else None,
                'macd_signal': latest['macd_signal'] if not pd.isna(latest['macd_signal']) else None,
                'macd_histogram': latest['macd_histogram'] if not pd.isna(latest['macd_histogram']) else None,

                # 布林带
                'bb_upper': latest['bb_upper'] if not pd.isna(latest['bb_upper']) else None,
                'bb_middle': latest['bb_middle'] if not pd.isna(latest['bb_middle']) else None,
                'bb_lower': latest['bb_lower'] if not pd.isna(latest['bb_lower']) else None,
                'bb_width': latest['bb_width'] if not pd.isna(latest['bb_width']) else None,
                'bb_position': ((current_price - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower']) * 100) if not pd.isna(latest['bb_upper']) and not pd.isna(latest['bb_lower']) else None,

                # 波动率
                'volatility_7d': volatility_7d.iloc[-1] if not volatility_7d.empty and not pd.isna(volatility_7d.iloc[-1]) else None,
                'volatility_30d': volatility_30d.iloc[-1] if not volatility_30d.empty and not pd.isna(volatility_30d.iloc[-1]) else None,
                'atr': latest['atr'] if not pd.isna(latest['atr']) else None,
                'atr_percentage': (latest['atr'] / current_price * 100) if not pd.isna(latest['atr']) else None,

                # 成交量
                'volume': latest['volume'],
                'volume_sma': latest['volume_sma'] if not pd.isna(latest['volume_sma']) else None,
                'volume_ratio': volume_ratio,

                # 价格统计
                'high_24h': df['high'].tail(24).max() if len(df) >= 24 else df['high'].max(),
                'low_24h': df['low'].tail(24).min() if len(df) >= 24 else df['low'].min(),
                'high_7d': df['high'].tail(168).max() if len(df) >= 168 and timeframe == "1h" else None,
                'low_7d': df['low'].tail(168).min() if len(df) >= 168 and timeframe == "1h" else None,

                # 趋势强度
                'trend_strength': self._calculate_trend_strength(df),
                'momentum': ((current_price - df['close'].iloc[-10]) / df['close'].iloc[-10] * 100) if len(df) >= 10 else 0
            })

            return indicators

        except Exception as e:
            self.logger.error(f"计算高级技术指标失败: {e}")
            return {}

    def _calculate_trend_strength(self, df: pd.DataFrame) -> Optional[float]:
        """计算趋势强度"""
        try:
            if len(df) < 20:
                return None

            # 使用线性回归计算趋势强度
            y = df['close'].tail(20).values
            x = np.arange(len(y))

            # 计算线性回归的R²值
            correlation_matrix = np.corrcoef(x, y)
            correlation = correlation_matrix[0, 1]
            r_squared = correlation ** 2

            return float(r_squared * 100)  # 转换为百分比
        except Exception:
            return None

    async def get_funding_rate_history(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取资金费率历史"""
        try:
            funding_rates = await self.client.futures_funding_rate(symbol=symbol, limit=limit)

            formatted_rates = []
            for rate in funding_rates:
                formatted_rates.append({
                    'symbol': rate['symbol'],
                    'funding_rate': float(rate['fundingRate']),
                    'funding_time': int(rate['fundingTime']),
                    'mark_price': float(rate.get('markPrice', 0))
                })

            return formatted_rates
        except BinanceAPIException as e:
            self.logger.error(f"获取资金费率历史失败: {e}")
            return []

    async def get_open_interest(self, symbol: str) -> Dict[str, Any]:
        """获取持仓量信息"""
        try:
            oi = await self.client.futures_open_interest(symbol=symbol)
            return {
                'symbol': oi['symbol'],
                'open_interest': float(oi['openInterest']),
                'timestamp': int(oi['time'])
            }
        except BinanceAPIException as e:
            self.logger.error(f"获取持仓量失败: {e}")
            return {}

    async def get_comprehensive_futures_data(
        self,
        symbols: List[str] = None,
        include_historical: bool = True
    ) -> Dict[str, Any]:
        """
        获取全面的期货市场数据

        Args:
            symbols: 币种列表
            include_historical: 是否包含历史数据

        Returns:
            综合期货市场数据
        """
        if symbols is None:
            symbols = self.target_symbols

        try:
            market_data = {
                'timestamp': datetime.now().isoformat(),
                'data_type': 'futures_comprehensive',
                'account_info': await self.get_futures_account_info(),
                'positions': await self.get_futures_positions(),
                'open_orders': await self.get_open_orders(),  # 添加未完成订单信息
                'symbols': {}
            }

            for symbol in symbols:
                symbol_data = {
                    'symbol': symbol,
                    'basic_info': {},
                    'technical_indicators': {},
                    'funding_info': {},
                    'market_depth': {}
                }

                # 获取24小时统计
                try:
                    ticker = await self.client.futures_ticker(symbol=symbol)
                    symbol_data['basic_info'] = {
                        'last_price': float(ticker['lastPrice']),
                        'price_change': float(ticker['priceChange']),
                        'price_change_percent': float(ticker['priceChangePercent']),
                        'high_price': float(ticker['highPrice']),
                        'low_price': float(ticker['lowPrice']),
                        'volume': float(ticker['volume']),
                        'quote_volume': float(ticker['quoteVolume']),
                        'open_price': float(ticker['openPrice']),
                        # 在期货API中，prevClosePrice字段可能不存在，使用安全访问
                        'prev_close_price': float(ticker.get('prevClosePrice', ticker.get('lastPrice'))),
                        'count': int(ticker['count'])
                    }
                except Exception as e:
                    self.logger.error(f"获取{symbol}基础信息失败: {e}")

                # 获取多时间周期数据
                if include_historical:
                    # 替换原来的 4h 为 1m，保留其它时间周期
                    multi_klines = await self.get_multi_timeframe_klines(
                        symbol, ["15m", "1h", "1m", "1d", "1M"]
                    )
                    symbol_data['multi_timeframe_data'] = multi_klines

                    # 计算每个时间周期的技术指标
                    symbol_data['timeframe_indicators'] = {}
                    for timeframe, kline_info in multi_klines.items():
                        if 'data' in kline_info and kline_info['data']:
                            indicators = await self.calculate_advanced_indicators(
                                kline_info['data'], timeframe
                            )
                            symbol_data['timeframe_indicators'][timeframe] = indicators

                # 获取资金费率
                funding_rates = await self.get_funding_rate_history(symbol, 10)
                symbol_data['funding_info'] = {
                    'recent_rates': funding_rates,
                    'current_rate': funding_rates[0] if funding_rates else None
                }

                # 获取持仓量
                open_interest = await self.get_open_interest(symbol)
                symbol_data['funding_info']['open_interest'] = open_interest

                # 获取订单簿深度
                try:
                    depth = await self.client.futures_order_book(symbol=symbol, limit=10)
                    symbol_data['market_depth'] = {
                        'bids': [[float(bid[0]), float(bid[1])] for bid in depth['bids']],
                        'asks': [[float(ask[0]), float(ask[1])] for ask in depth['asks']],
                        'last_update_id': depth['lastUpdateId']
                    }
                except Exception as e:
                    self.logger.error(f"获取{symbol}订单簿失败: {e}")

                market_data['symbols'][symbol] = symbol_data
                self.logger.info(f"获取到{symbol}的全面期货数据")

            return market_data

        except Exception as e:
            self.logger.error(f"获取综合期货数据失败: {e}")
            return {'error': str(e), 'symbols': {}}
