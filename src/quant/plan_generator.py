"""
交易计划生成器
遍历股票池，生成"明日操作清单"
"""

import os
import pandas as pd
from datetime import datetime
from .data_fetcher import get_stock_daily_history
from .strategy import (
    check_buy_signal,
    calculate_stop_loss,
    calculate_take_profit,
    get_latest_ma20,
)
from .market_regime import adaptive_strategy
from config.config import POSITION_RATIO, TOTAL_CAPITAL, OUTPUT_CSV, MAX_POSITIONS
from .position_tracker import position_tracker, portfolio_manager


def generate_trading_plan(stock_pool: pd.DataFrame, verbose: bool = True,
                          use_position_limit: bool = True) -> pd.DataFrame:
    """
    生成交易计划
    
    Args:
        stock_pool: 股票池DataFrame，包含 代码、名称
        verbose: 是否打印进度
        use_position_limit: 是否应用持仓数量限制
        
    Returns:
        DataFrame: 交易计划列表
    """
    plans = []
    total = len(stock_pool)
    
    params = adaptive_strategy.get_current_params()
    position_ratio = params.position_ratio or POSITION_RATIO
    max_positions = params.max_positions or MAX_POSITIONS

    # 同步到持仓管理器（保持限制一致）
    portfolio_manager.max_positions = max_positions

    # 获取当前持仓数量
    current_positions = position_tracker.get_position_count()
    remaining_slots = max(max_positions - current_positions, 0)
    
    if verbose and use_position_limit:
        print(f"[持仓] 当前持仓 {current_positions}/{max_positions}，还可买入 {remaining_slots} 只")
    
    for idx, row in stock_pool.iterrows():
        code = row['代码']
        name = row['名称']
        
        if verbose and (idx + 1) % 50 == 0:
            progress = (idx + 1) / total * 100
            print(f"[进度] 已分析 {idx + 1}/{total} 只股票 ({progress:.1f}%)...")
        
        # 检查是否还能继续推荐
        if use_position_limit and len(plans) >= remaining_slots:
            if verbose:
                print(f"[限制] 已达可推荐上限({remaining_slots}只)，停止分析")
            break
        
        try:
            # 获取历史数据
            df = get_stock_daily_history(code)
            
            if df.empty or len(df) < 25:  # 数据不足
                continue
            
            # 检查买入信号
            if not check_buy_signal(df):
                continue
            
            # 检查是否已持有
            if use_position_limit and position_tracker.get_position(code):
                if verbose:
                    print(f"[跳过] {name}({code}) 已在持仓中")
                continue
            
            # 获取最新数据
            latest = df.iloc[-1]
            close_price = latest['close']
            
            # 计算MA20
            ma20 = get_latest_ma20(df)
            
            # 计算止损止盈（使用ATR动态止损）
            stop_loss = calculate_stop_loss(close_price, ma20, df)
            take_profit = calculate_take_profit(close_price)
            
            # 计算建议仓位金额
            position_amount = TOTAL_CAPITAL * position_ratio
            
            # 计算建议股数（A股一手100股）
            suggested_shares = int(position_amount / close_price / 100) * 100
            if suggested_shares < 100:
                suggested_shares = 100
            
            plans.append({
                '代码': code,
                '名称': name,
                '收盘价': round(close_price, 2),
                '建议买入价': round(close_price, 2),  # 以收盘价作为参考
                '止损价': round(stop_loss, 2),
                '止盈价': round(take_profit, 2),
                'MA20': round(ma20, 2),
                '建议股数': suggested_shares,
                '建议金额': round(suggested_shares * close_price, 2),
                '仓位比例': f"{position_ratio * 100:.0f}%"
            })
            
        except Exception as e:
            if verbose:
                print(f"[警告] 分析 {code} 时出错: {e}")
            continue
    
    return pd.DataFrame(plans)


def print_trading_plan(plan_df: pd.DataFrame, market_status: str = ""):
    """
    在终端打印交易计划
    
    Args:
        plan_df: 交易计划DataFrame
        market_status: 市场状态信息（可选）
    """
    if plan_df.empty:
        print("\n" + "=" * 60)
        print("📋 明日操作清单：无符合条件的股票")
        print("=" * 60)
        print("\n💡 可能原因：")
        print("   1. 当前无个股同时满足站上MA20和成交量放大1.2倍条件")
        print("   2. 符合条件的股票价格偏离均线过大（追高风险）")
        print("   3. 股票池范围较小，可尝试扩大筛选范围")
        if market_status:
            print(f"   4. 市场状态: {market_status}")
        print("\n📌 建议：可适当放宽参数或等待更好的入场时机")
        return
    
    print("\n" + "=" * 80)
    print(f"📋 明日操作清单（生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    print(f"📊 共筛选出 {len(plan_df)} 只股票符合买入条件")
    
    # 显示当前持仓状态
    current_positions = position_tracker.get_position_count()
    params = adaptive_strategy.get_current_params()
    max_positions = params.max_positions or MAX_POSITIONS
    print(f"💼 当前持仓: {current_positions}/{max_positions}")
    print("=" * 80)
    
    # 格式化打印
    for idx, row in plan_df.iterrows():
        print(f"\n【{idx + 1}】{row['名称']} ({row['代码']})")
        print(f"    收盘价: ¥{row['收盘价']:.2f}")
        print(f"    建议买入价: ¥{row['建议买入价']:.2f}")
        print(f"    止损价: ¥{row['止损价']:.2f} (跌破即卖出)")
        print(f"    止盈价: ¥{row['止盈价']:.2f} (达到即卖出)")
        print(f"    MA20: ¥{row['MA20']:.2f}")
        print(f"    建议仓位: {row['建议股数']}股 (约¥{row['建议金额']:.0f}，占{row['仓位比例']})")
    
    print("\n" + "=" * 80)
    print("⚠️ 风险提示：以上仅供参考，不构成投资建议。请结合自身风险承受能力谨慎决策。")
    print("=" * 80)


def save_trading_plan(plan_df: pd.DataFrame, filepath: str = OUTPUT_CSV):
    """
    保存交易计划到CSV文件
    """
    if plan_df.empty:
        print(f"\n[信息] 无交易计划需要保存")
        return
    
    try:
        output_dir = os.path.dirname(filepath)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        plan_df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"\n[信息] 交易计划已保存至: {filepath}")
    except Exception as e:
        print(f"\n[错误] 保存CSV失败: {e}")


if __name__ == "__main__":
    # 简单测试
    from .stock_pool import get_final_pool
    
    print("测试交易计划生成器...")
    
    # 获取一小部分股票测试
    pool = get_final_pool(use_custom=False, skip_new_stock_filter=True)
    test_pool = pool.head(20)  # 只测试前20只
    
    plan = generate_trading_plan(test_pool, verbose=True)
    print_trading_plan(plan)
    save_trading_plan(plan)
