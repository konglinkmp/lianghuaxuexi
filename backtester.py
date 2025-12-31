"""
回测引擎模块
用于验证策略在历史数据上的表现
"""

import pandas as pd
import numpy as np
from datetime import datetime
from data_fetcher import get_stock_daily_history
from strategy import (
    check_buy_signal,
    calculate_stop_loss,
    calculate_take_profit,
    get_latest_ma20,
    calculate_ma,
    calculate_atr
)
from config import MA_SHORT, TRAILING_STOP_RATIO
from transaction_cost import TransactionCostModel, default_cost_model


class BacktestResult:
    """回测结果类"""
    
    def __init__(self):
        self.trades = []  # 所有交易记录
        self.equity_curve = []  # 资金曲线
        
    def add_trade(self, trade: dict):
        """添加交易记录"""
        self.trades.append(trade)
        
    def get_metrics(self) -> dict:
        """计算回测指标"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'total_return': 0.0
            }
        
        df = pd.DataFrame(self.trades)
        
        # 胜率
        wins = len(df[df['pnl'] > 0])
        total = len(df)
        win_rate = wins / total if total > 0 else 0
        
        # 盈亏比 (Profit Factor)
        gross_profit = df[df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # 总收益率
        total_return = df['pnl_pct'].sum()
        
        # 最大回撤
        cumulative_returns = (1 + df['pnl_pct']).cumprod()
        rolling_max = cumulative_returns.cummax()
        drawdowns = (cumulative_returns - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min()) if len(drawdowns) > 0 else 0
        
        # 夏普比率 (假设无风险利率为3%)
        risk_free_rate = 0.03 / 252  # 日化无风险利率
        daily_returns = df['pnl_pct']
        excess_returns = daily_returns - risk_free_rate
        sharpe_ratio = (excess_returns.mean() / excess_returns.std() * np.sqrt(252)) if excess_returns.std() > 0 else 0
        
        return {
            'total_trades': total,
            'win_rate': round(win_rate * 100, 2),
            'profit_factor': round(profit_factor, 2),
            'max_drawdown': round(max_drawdown * 100, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'total_return': round(total_return * 100, 2)
        }


def backtest_stock(symbol: str, name: str = "", use_trailing_stop: bool = True,
                   use_cost_model: bool = True, shares: int = 1000) -> list:
    """
    对单只股票进行回测
    
    Args:
        symbol: 股票代码
        name: 股票名称
        use_trailing_stop: 是否使用移动止盈
        use_cost_model: 是否应用交易成本模型
        shares: 模拟交易股数
        
    Returns:
        list: 交易记录列表
    """
    trades = []
    cost_model = default_cost_model if use_cost_model else None
    
    # 获取历史数据（获取更长的数据用于回测）
    df = get_stock_daily_history(symbol, days=365)
    
    if df.empty or len(df) < MA_SHORT + 30:
        return trades
    
    # 计算均线
    df = df.copy()
    df['ma20'] = calculate_ma(df, MA_SHORT)
    
    # 模拟交易状态
    in_position = False
    entry_price = 0.0
    entry_date = None
    stop_loss = 0.0
    take_profit = 0.0
    highest_since_entry = 0.0
    
    # 从第MA_SHORT+1天开始回测
    for i in range(MA_SHORT + 1, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        current_date = current['date']
        current_price = current['close']
        
        if not in_position:
            # 检查买入信号（简化版：价格站上MA20且放量）
            price_above_ma = current_price > current['ma20']
            volume_increase = current['volume'] > prev['volume'] * 1.2
            
            if price_above_ma and volume_increase:
                # 买入
                in_position = True
                entry_price = current_price
                entry_date = current_date
                # 使用ATR动态止损（传入当前为止的历史数据）
                historical_df = df.iloc[:i+1]
                stop_loss = calculate_stop_loss(entry_price, current['ma20'], historical_df)
                take_profit = calculate_take_profit(entry_price)
                highest_since_entry = entry_price
                
        else:
            # 更新最高价
            if current_price > highest_since_entry:
                highest_since_entry = current_price
            
            # 检查出场条件
            exit_reason = None
            exit_price = current_price
            
            # 1. 止损
            if current_price <= stop_loss:
                exit_reason = "止损"
                exit_price = stop_loss
            
            # 2. 固定止盈
            elif current_price >= take_profit:
                exit_reason = "止盈"
                exit_price = take_profit
            
            # 3. 移动止盈（从最高点回落8%）
            elif use_trailing_stop and highest_since_entry > entry_price * 1.10:
                trailing_stop = highest_since_entry * (1 - TRAILING_STOP_RATIO)
                if current_price <= trailing_stop:
                    exit_reason = "移动止盈"
                    exit_price = trailing_stop
            
            if exit_reason:
                # 记录交易
                gross_pnl = exit_price - entry_price
                gross_pnl_pct = gross_pnl / entry_price
                
                # 应用交易成本模型
                if cost_model:
                    cost_result = cost_model.calculate_round_trip_cost(
                        entry_price, exit_price, shares
                    )
                    actual_pnl = cost_result['actual_profit'] / shares  # 每股实际盈亏
                    actual_pnl_pct = cost_result['actual_return_pct'] / 100
                    total_cost = cost_result['total_cost'] / shares  # 每股成本
                else:
                    actual_pnl = gross_pnl
                    actual_pnl_pct = gross_pnl_pct
                    total_cost = 0
                
                trades.append({
                    'symbol': symbol,
                    'name': name,
                    'entry_date': entry_date,
                    'entry_price': round(entry_price, 2),
                    'exit_date': current_date,
                    'exit_price': round(exit_price, 2),
                    'exit_reason': exit_reason,
                    'pnl': round(actual_pnl, 4),  # 使用实际盈亏
                    'pnl_pct': round(actual_pnl_pct, 4),
                    'gross_pnl': round(gross_pnl, 2),  # 毛利润
                    'gross_pnl_pct': round(gross_pnl_pct, 4),
                    'cost_per_share': round(total_cost, 4),  # 每股成本
                    'holding_days': (current_date - entry_date).days
                })
                
                # 重置状态
                in_position = False
                entry_price = 0.0
                highest_since_entry = 0.0
    
    return trades


def run_backtest(stock_pool: pd.DataFrame, verbose: bool = True) -> BacktestResult:
    """
    对股票池进行回测
    
    Args:
        stock_pool: 股票池DataFrame，包含 代码、名称
        verbose: 是否打印进度
        
    Returns:
        BacktestResult: 回测结果
    """
    result = BacktestResult()
    total = len(stock_pool)
    
    for idx, row in stock_pool.iterrows():
        code = row['代码']
        name = row['名称']
        
        if verbose and (idx + 1) % 10 == 0:
            print(f"[回测进度] {idx + 1}/{total} ({(idx + 1) / total * 100:.1f}%)")
        
        try:
            trades = backtest_stock(code, name)
            for trade in trades:
                result.add_trade(trade)
        except Exception as e:
            if verbose:
                print(f"[警告] 回测 {code} 时出错: {e}")
            continue
    
    return result


def print_backtest_report(result: BacktestResult):
    """打印回测报告"""
    metrics = result.get_metrics()
    
    print("\n" + "=" * 60)
    print("📊 回测报告")
    print("=" * 60)
    print(f"📈 总交易次数: {metrics['total_trades']}")
    print(f"🎯 胜率: {metrics['win_rate']}%")
    print(f"💰 盈亏比: {metrics['profit_factor']}")
    print(f"📉 最大回撤: {metrics['max_drawdown']}%")
    print(f"📐 夏普比率: {metrics['sharpe_ratio']}")
    print(f"💵 累计收益: {metrics['total_return']}%")
    print("=" * 60)
    
    # 显示最近10笔交易
    if result.trades:
        print("\n📋 最近交易记录（最多显示10笔）:")
        print("-" * 80)
        recent_trades = result.trades[-10:]
        for trade in recent_trades:
            pnl_emoji = "🟢" if trade['pnl'] > 0 else "🔴"
            print(f"{pnl_emoji} {trade['name']}({trade['symbol']}) | "
                  f"买入:{trade['entry_price']} → 卖出:{trade['exit_price']} | "
                  f"{trade['exit_reason']} | 收益:{trade['pnl_pct']*100:.2f}%")


if __name__ == "__main__":
    from stock_pool import load_custom_pool, get_all_a_stock_list
    
    print("🚀 启动回测引擎...")
    
    # 加载自定义股票池
    custom_codes = load_custom_pool("myshare.txt")
    
    if custom_codes:
        print(f"[信息] 使用自定义股票池: {custom_codes}")
        all_stocks = get_all_a_stock_list()
        if not all_stocks.empty:
            stock_pool = all_stocks[all_stocks['代码'].isin(custom_codes)].reset_index(drop=True)
        else:
            stock_pool = pd.DataFrame()
    else:
        print("[信息] 未找到自定义股票池，使用测试股票")
        stock_pool = pd.DataFrame({
            '代码': ['000001', '600000', '000002'],
            '名称': ['平安银行', '浦发银行', '万科A']
        })
    
    if stock_pool.empty:
        print("[错误] 股票池为空")
    else:
        print(f"[信息] 开始回测 {len(stock_pool)} 只股票...")
        result = run_backtest(stock_pool, verbose=True)
        print_backtest_report(result)
