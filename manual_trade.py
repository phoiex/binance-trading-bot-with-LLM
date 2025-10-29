#!/usr/bin/env python3
"""
手动执行单笔期货交易（使用现有交易引擎逻辑）

用途
- 将一条AI/人工给定的交易建议（JSON）转换为交易引擎可执行的决策，并下单。
- 重用 FuturesTradingEngine 的风控、数量计算、限价/市价下单、止损止盈设置等完整流程。

用法示例
- 测试网/干跑验证（推荐先验证）：
  python manual_trade.py --config trading_bot/config/config.yaml --decision-file eth_short.json --dry-run

- 真实下单（仅当配置里已开启安全开关）：
  python manual_trade.py --config trading_bot/config/config.yaml --decision-file eth_short.json --execute

JSON示例（eth_short.json）
{
  "symbol": "ETHUSDT",
  "action": "short",
  "confidence": 70,
  "timeframe": "1-4小时",
  "entry_price": 3980.0,
  "stop_loss": 4120.0,
  "take_profit": 3850.0,
  "position_size": 0.3,
  "leverage": 6,
  "order_type": "LIMIT",
  "order_reasoning": "...",
  "risk_level": "medium",
  "reason": "..."
}
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, Any

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_bot.strategies.futures_trading_engine import FuturesTradingEngine


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger("manual_trade")


def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


async def execute_manual_trade(config_path: str, decision_data: Dict[str, Any], do_execute: bool, dry_run_flag: bool):
    logger = logging.getLogger("manual_trade")

    # 1) 加载配置并初始化交易引擎
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    binance_cfg = config.get('apis', {}).get('binance', {})
    deepseek_cfg = config.get('apis', {}).get('deepseek', {})
    position_cfg = config.get('trading', {}).get('position_management', {})
    futures_cfg = config.get('trading', {}).get('futures', {})

    engine = FuturesTradingEngine(
        binance_api_key=binance_cfg.get('api_key'),
        binance_api_secret=binance_cfg.get('api_secret'),
        deepseek_api_key=deepseek_cfg.get('api_key'),
        config=config,
        testnet=binance_cfg.get('testnet', True),
        max_position_size=position_cfg.get('max_position_size', 1.0),
        default_leverage=futures_cfg.get('default_leverage', 3),
        stop_loss_percent=position_cfg.get('stop_loss_percent', 0.05),
        take_profit_percent=position_cfg.get('take_profit_percent', 0.15)
    )

    await engine.__aenter__()
    try:
        # 2) 读取当前市场数据（只取目标symbol当前价，避免访问账户等敏感接口）
        symbol = str(decision_data.get('symbol', '')).upper()
        if not symbol:
            raise Exception('decision 缺少 symbol')

        # 仅调用ticker获取最新价（无需账户权限）
        ticker = await engine.futures_data_manager.client.futures_ticker(symbol=symbol)
        current_price = float(ticker.get('lastPrice', 0))
        if not current_price:
            raise Exception(f'无法获取 {symbol} 当前价格')

        # 构造最小化的市场数据结构，足够生成决策
        sym_data = {
            'symbol': symbol,
            'basic_info': {'last_price': current_price},
            # funding_info/multi_timeframe等在此简化为空，决策函数会有默认处理
        }

        # 3) 组装AI推荐，并生成交易引擎期望的决策结构（含止盈/止损、current_price 等）
        ai_rec = dict(decision_data)
        ai_rec['symbol'] = symbol  # 允许传 ETH或ETHUSDT，统一成ETHUSDT
        ai_rec['action'] = str(ai_rec.get('action', 'hold')).lower()
        if 'order_type' in ai_rec:
            ai_rec['order_type'] = str(ai_rec['order_type']).upper()

        # 使用内置方法生成完整决策（含 should_execute、止盈止损等）
        decision = await engine._create_futures_trading_decision(
            symbol=symbol,
            ai_recommendation=ai_rec,
            market_data=sym_data,
            market_overview={},
            current_price=current_price,
        )

        if not decision:
            raise Exception('无法从输入生成有效的交易决策')

        # 强制执行（非hold）
        decision['should_execute'] = (decision.get('action') != 'hold')

        # 优先使用输入中的entry_price作为限价
        if 'entry_price' in decision_data:
            decision['entry_price'] = float(decision_data['entry_price'])

        logger.info(f"准备下单: {decision['symbol']} {decision['action'].upper()} x{decision['leverage']}  at ~{current_price}")

        # 4) 执行
        if not do_execute:
            logger.info('干跑模式：仅打印将要执行的决策（不下单）')
            print(json.dumps(decision, indent=2, ensure_ascii=False))
            return

        results = await engine.execute_futures_trading_decisions(
            decisions=[decision],
            dry_run=dry_run_flag
        )

        # 5) 输出结果
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs('data', exist_ok=True)
        out_path = f'data/manual_trade_result_{symbol}_{ts}.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f'执行结果已保存至: {out_path}')
        print(json.dumps(results, indent=2, ensure_ascii=False))

    finally:
        await engine.__aexit__(None, None, None)


def parse_args():
    p = argparse.ArgumentParser(description='手动执行单笔期货交易（复用现有引擎逻辑）')
    p.add_argument('--config', default='trading_bot/config/config.yaml', help='配置文件路径')
    p.add_argument('--decision-file', required=True, help='包含单笔交易的JSON文件')
    group = p.add_mutually_exclusive_group()
    group.add_argument('--execute', action='store_true', help='执行下单（需配置允许真实或设置dry-run为False）')
    group.add_argument('--dry-run', action='store_true', help='干跑模式（默认）')
    return p.parse_args()


if __name__ == '__main__':
    logger = setup_logging()
    args = parse_args()

    # 默认干跑，除非指定 --execute
    do_execute = bool(args.execute)
    dry_run_flag = not do_execute or args.dry_run

    # 读取JSON
    decision_data = load_json(args.decision_file)

    try:
        asyncio.run(execute_manual_trade(args.config, decision_data, do_execute, dry_run_flag))
    except KeyboardInterrupt:
        logger.warning('用户中断')
    except Exception as e:
        logger.error(f'执行失败: {e}')
        sys.exit(1)
