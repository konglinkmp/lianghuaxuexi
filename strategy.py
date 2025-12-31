"""
量化策略模块
实现动能+趋势策略
"""

import pandas as pd
from data_fetcher import get_index_daily_history
from config import (
    MA_SHORT, MA_LONG, 
    VOLUME_RATIO_THRESHOLD,
    STOP_LOSS_RATIO, TAKE_PROFIT_RATIO,
    MAX_PRICE_DEVIATION, TRAILING_STOP_RATIO
)


def calculate_ma(df: pd.DataFrame, period: int) -> pd.Series:
    """
    计算移动平均线
    
    Args:
        df: 包含 'close' 列的DataFrame
        period: 均线周期
        
    Returns:
        均线Series
    """
    return df['close'].rolling(window=period).mean()


def check_buy_signal(df: pd.DataFrame) -> bool:
    """
    判断是否满足买入条件
    
    买入条件：
    1. 收盘价站上 20 日均线
    2. 成交量较前一日放大 1.2 倍以上
    
    Args:
        df: 历史K线数据DataFrame
        
    Returns:
        bool: 是否触发买入信号
    """
    if df.empty or len(df) < MA_SHORT + 1:
        return False
    
    # 计算20日均线
    df = df.copy()
    df['ma20'] = calculate_ma(df, MA_SHORT)
    
    # 获取最新数据
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 条件1: 收盘价站上20日均线
    price_above_ma = latest['close'] > latest['ma20']
    
    # 条件2: 成交量较前日放大1.2倍以上
    volume_increase = latest['volume'] > prev['volume'] * VOLUME_RATIO_THRESHOLD
    
    # 条件3: 价格未过分远离均线（防止追高）
    price_not_too_high = latest['close'] <= latest['ma20'] * (1 + MAX_PRICE_DEVIATION)
    
    return price_above_ma and volume_increase and price_not_too_high


def calculate_stop_loss(buy_price: float, ma20: float) -> float:
    """
    计算止损价
    
    止损逻辑：买入价跌破5%或跌破20日均线，取较高者
    
    Args:
        buy_price: 买入价格
        ma20: 20日均线价格
        
    Returns:
        止损触发价
    """
    # 固定止损价
    fixed_stop = buy_price * (1 - STOP_LOSS_RATIO)
    
    # 均线止损价（略低于均线，给予一定容差）
    ma_stop = ma20 * 0.99
    
    # 取较高者作为止损价（更严格的止损）
    return max(fixed_stop, ma_stop)


def calculate_take_profit(buy_price: float) -> float:
    """
    计算止盈价
    
    固定止盈：买入价上涨15%
    
    Args:
        buy_price: 买入价格
        
    Returns:
        止盈触发价
    """
    return buy_price * (1 + TAKE_PROFIT_RATIO)


def calculate_trailing_stop(highest_price: float) -> float:
    """
    计算移动止盈价
    
    当股价从历史最高点回落 TRAILING_STOP_RATIO 时触发止盈
    
    Args:
        highest_price: 持仓期间的最高价
        
    Returns:
        移动止盈触发价
    """
    return highest_price * (1 - TRAILING_STOP_RATIO)


def check_market_risk() -> tuple:
    """
    检查大盘风险
    
    风险条件：沪深300跌破60日均线
    
    Returns:
        tuple: (是否有风险, 风险提示信息)
    """
    try:
        # 获取沪深300指数数据
        index_df = get_index_daily_history()
        
        if index_df.empty or len(index_df) < MA_LONG:
            return False, "无法获取指数数据，暂不限制"
        
        # 计算60日均线
        index_df['ma60'] = calculate_ma(index_df, MA_LONG)
        
        latest = index_df.iloc[-1]
        
        # 判断是否跌破60日均线
        if latest['close'] < latest['ma60']:
            return True, f"⚠️ 风险警告：沪深300({latest['close']:.2f})跌破60日均线({latest['ma60']:.2f})，环境风险大，停止买入，仅处理止损"
        else:
            return False, f"✅ 大盘正常：沪深300({latest['close']:.2f})位于60日均线({latest['ma60']:.2f})之上"
            
    except Exception as e:
        return False, f"检查大盘风险时出错: {e}"


def get_latest_ma20(df: pd.DataFrame) -> float:
    """
    获取最新的20日均线值
    
    Args:
        df: 历史K线数据
        
    Returns:
        20日均线值
    """
    if df.empty or len(df) < MA_SHORT:
        return 0.0
    
    df = df.copy()
    df['ma20'] = calculate_ma(df, MA_SHORT)
    return df.iloc[-1]['ma20']


if __name__ == "__main__":
    # 测试策略
    from data_fetcher import get_stock_daily_history
    
    print("测试大盘风险检查...")
    is_risky, msg = check_market_risk()
    print(msg)
    
    print("\n测试个股买入信号...")
    df = get_stock_daily_history("000001")
    if not df.empty:
        signal = check_buy_signal(df)
        print(f"000001 买入信号: {signal}")
        
        latest_price = df.iloc[-1]['close']
        ma20 = get_latest_ma20(df)
        stop_loss = calculate_stop_loss(latest_price, ma20)
        take_profit = calculate_take_profit(latest_price)
        
        print(f"当前价: {latest_price:.2f}")
        print(f"MA20: {ma20:.2f}")
        print(f"止损价: {stop_loss:.2f}")
        print(f"止盈价: {take_profit:.2f}")
