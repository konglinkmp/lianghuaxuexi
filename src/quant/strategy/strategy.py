"""
量化策略模块
实现动能+趋势策略
"""

import pandas as pd
from ..core.data_fetcher import get_index_daily_history
from .style_benchmark import get_style_benchmark_series
from ..analysis.market_regime import adaptive_strategy, AdaptiveParameters
from config.config import MA_SHORT, MA_LONG


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


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    计算ATR（平均真实波幅）
    
    Args:
        df: 包含 high, low, close 的DataFrame
        period: ATR周期，默认14日
        
    Returns:
        最新的ATR值
    """
    if len(df) < period + 1:
        return 0.0
    
    df = df.copy()
    # 计算真实波幅的三个分量
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift(1))
    low_close = abs(df['low'] - df['close'].shift(1))
    
    # 真实波幅 = 三者中的最大值
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # ATR = TR的移动平均
    atr = tr.rolling(window=period).mean()
    
    return atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0.0


def _get_adaptive_params() -> AdaptiveParameters:
    try:
        return adaptive_strategy.get_current_params()
    except Exception:
        return AdaptiveParameters()


class MultiStrategyValidator:
    """
    复合策略验证器
    
    至少需要2个策略同时触发才发出买入信号，以提高胜率
    """
    
    def __init__(self, required_votes: int = 2):
        self.required_votes = required_votes
    
    def validate(self, df: pd.DataFrame) -> tuple:
        """
        验证是否满足买入条件
        
        Returns:
            tuple: (是否买入, 触发的策略列表)
        """
        if df.empty or len(df) < MA_SHORT + 1:
            return False, []
        
        df = df.copy()
        df['ma20'] = calculate_ma(df, MA_SHORT)
        
        params = _get_adaptive_params()
        triggered_strategies = []
        
        # 策略1: 原动能趋势（站上MA20 + 放量）
        if self._momentum_trend(df, params.volume_threshold, params.max_price_deviation):
            triggered_strategies.append("动能趋势")
        
        # 策略2: 突破回踩确认
        if self._breakout_confirmation(df):
            triggered_strategies.append("突破确认")
        
        # 策略3: 排除量价背离（作为过滤条件）
        if self._no_volume_price_divergence(df):
            triggered_strategies.append("量价健康")
        
        # 判断是否达到所需票数
        is_valid = len(triggered_strategies) >= self.required_votes
        
        return is_valid, triggered_strategies
    
    def _momentum_trend(self, df: pd.DataFrame, volume_threshold: float, max_price_deviation: float) -> bool:
        """原动能趋势策略：站上MA20 + 成交量放大"""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 收盘价站上20日均线
        price_above_ma = latest['close'] > latest['ma20']
        
        # 成交量较前日放大1.2倍以上
        volume_increase = latest['volume'] > prev['volume'] * volume_threshold
        
        # 价格未过分远离均线（防止追高）
        price_not_too_high = latest['close'] <= latest['ma20'] * (1 + max_price_deviation)
        
        return price_above_ma and volume_increase and price_not_too_high
    
    def _breakout_confirmation(self, df: pd.DataFrame) -> bool:
        """突破回踩确认策略：价格突破后回踩不破"""
        if len(df) < 5:
            return False
        
        recent = df.tail(5)
        ma20 = recent['ma20'].iloc[-1]
        
        # 检查前4日是否都在MA20之上
        prev_4_above = all(recent['close'].iloc[:-1] > recent['ma20'].iloc[:-1])
        
        # 最新一日回踩但未跌破（允许1%的容差）
        latest_above = recent['close'].iloc[-1] > ma20 * 0.99
        
        return prev_4_above and latest_above
    
    def _no_volume_price_divergence(self, df: pd.DataFrame) -> bool:
        """排除量价背离：价涨量缩时不买入"""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        price_up = latest['close'] > prev['close']
        volume_down = latest['volume'] < prev['volume'] * 0.9
        
        # 如果价涨量缩，返回False（存在背离）
        if price_up and volume_down:
            return False
        
        return True


# 创建全局验证器实例
strategy_validator = MultiStrategyValidator(required_votes=2)


def check_buy_signal(df: pd.DataFrame) -> bool:
    """
    判断是否满足买入条件（使用复合策略验证）
    
    买入条件：
    1. 收盘价站上 20 日均线
    2. 成交量较前一日放大 1.2 倍以上
    3. 至少2个策略同时触发
    
    Args:
        df: 历史K线数据DataFrame
        
    Returns:
        bool: 是否触发买入信号
    """
    is_valid, strategies = strategy_validator.validate(df)
    return is_valid


def calculate_stop_loss(
    buy_price: float,
    ma20: float,
    df: pd.DataFrame = None,
    atr_multiplier: float = None,
    stop_loss_ratio: float = None,
) -> float:
    """
    计算止损价（支持ATR波动率自适应）
    
    止损逻辑：
    1. ATR止损 = 买入价 - N倍ATR（如提供df）
    2. 固定止损 = 买入价 * 0.95
    3. 均线止损 = MA20 * 0.99
    取三者中的较高值（更严格的止损）
    
    Args:
        buy_price: 买入价格
        ma20: 20日均线价格
        df: 历史数据（用于计算ATR，可选）
        atr_multiplier: ATR倍数，默认1.5
        
    Returns:
        止损触发价
    """
    params = _get_adaptive_params()
    if atr_multiplier is None:
        atr_multiplier = params.atr_multiplier
    if stop_loss_ratio is None:
        stop_loss_ratio = params.stop_loss_ratio

    # 固定止损价
    fixed_stop = buy_price * (1 - stop_loss_ratio)
    
    # 均线止损价（略低于均线，给予一定容差）
    ma_stop = ma20 * 0.99
    
    # ATR波动率止损（如果提供了历史数据）
    if df is not None and not df.empty:
        atr = calculate_atr(df)
        if atr > 0:
            atr_stop = buy_price - atr_multiplier * atr
            # 取三者中的较高值
            return max(fixed_stop, ma_stop, atr_stop)
    
    # 未提供df时，取固定止损和均线止损的较高者
    return max(fixed_stop, ma_stop)


def calculate_take_profit(buy_price: float, take_profit_ratio: float = None) -> float:
    """
    计算止盈价
    
    固定止盈：买入价上涨15%
    
    Args:
        buy_price: 买入价格
        
    Returns:
        止盈触发价
    """
    params = _get_adaptive_params()
    ratio = take_profit_ratio if take_profit_ratio is not None else params.take_profit_ratio
    return buy_price * (1 + ratio)


def calculate_trailing_stop(highest_price: float, trailing_stop_ratio: float = None) -> float:
    """
    计算移动止盈价
    
    当股价从历史最高点回落 TRAILING_STOP_RATIO 时触发止盈
    
    Args:
        highest_price: 持仓期间的最高价
        
    Returns:
        移动止盈触发价
    """
    params = _get_adaptive_params()
    ratio = trailing_stop_ratio if trailing_stop_ratio is not None else params.trailing_stop_ratio
    return highest_price * (1 - ratio)


def check_market_risk() -> tuple:
    """
    检查大盘风险
    
    风险条件：沪深300跌破60日均线
    
    Returns:
        tuple: (是否有风险, 风险提示信息)
    """
    try:
        benchmark_series, info = get_style_benchmark_series()
        if benchmark_series is not None and not benchmark_series.empty and len(benchmark_series) >= MA_LONG:
            ma60 = benchmark_series.rolling(window=MA_LONG).mean()
            latest = benchmark_series.iloc[-1]
            latest_ma = ma60.iloc[-1]
            if latest < latest_ma:
                return True, f"⚠️ 风险警告：风格基准({latest:.2f})跌破60日均线({latest_ma:.2f})，环境风险大，停止买入，仅处理止损"
            return False, f"✅ 大盘正常：风格基准({latest:.2f})位于60日均线({latest_ma:.2f})之上"

        # 兜底：沪深300
        index_df = get_index_daily_history()
        if index_df.empty or len(index_df) < MA_LONG:
            return False, "无法获取指数数据，暂不限制"

        index_df['ma60'] = calculate_ma(index_df, MA_LONG)
        latest = index_df.iloc[-1]

        if latest['close'] < latest['ma60']:
            return True, f"⚠️ 风险警告：沪深300({latest['close']:.2f})跌破60日均线({latest['ma60']:.2f})，环境风险大，停止买入，仅处理止损"
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
    from .data_fetcher import get_stock_daily_history
    
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
