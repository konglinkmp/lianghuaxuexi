"""
技术指标模块
提供MACD等经典技术分析指标的计算
"""

from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """
    计算指数移动平均线（EMA）

    Args:
        series: 价格序列
        period: 周期

    Returns:
        EMA序列
    """
    return series.ewm(span=period, adjust=False).mean()


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Dict[str, pd.Series]:
    """
    计算MACD指标

    MACD由三部分组成：
    - DIF (差离值): 快线EMA - 慢线EMA
    - DEA (信号线): DIF的EMA
    - MACD柱状图: (DIF - DEA) * 2

    Args:
        df: 包含 'close' 列的DataFrame
        fast: 快线周期，默认12
        slow: 慢线周期，默认26
        signal: 信号线周期，默认9

    Returns:
        Dict: {'dif': Series, 'dea': Series, 'macd_hist': Series}
    """
    close = df['close']

    # 计算快慢EMA
    ema_fast = calculate_ema(close, fast)
    ema_slow = calculate_ema(close, slow)

    # DIF = 快线EMA - 慢线EMA
    dif = ema_fast - ema_slow

    # DEA = DIF的信号线EMA
    dea = calculate_ema(dif, signal)

    # MACD柱状图 = (DIF - DEA) * 2
    macd_hist = (dif - dea) * 2

    return {
        'dif': dif,
        'dea': dea,
        'macd_hist': macd_hist
    }


def detect_macd_cross(
    df: pd.DataFrame,
    lookback: int = 3
) -> Dict[str, any]:
    """
    检测MACD金叉/死叉信号

    金叉（看涨）：DIF从下向上穿越DEA
    死叉（看跌）：DIF从上向下穿越DEA

    Args:
        df: 包含 'close' 列的DataFrame
        lookback: 向前查找的天数，默认3天

    Returns:
        Dict:
            - signal: 'golden_cross' | 'death_cross' | 'none'
            - strength: 信号强度 0-100
            - days_ago: 发生在几天前
    """
    if len(df) < 30:
        return {'signal': 'none', 'strength': 0, 'days_ago': 0}

    macd = calculate_macd(df)
    dif = macd['dif']
    dea = macd['dea']

    result = {'signal': 'none', 'strength': 0, 'days_ago': 0}

    # 检查最近lookback天是否有交叉
    for i in range(1, min(lookback + 1, len(df))):
        idx = -i
        prev_idx = idx - 1

        if prev_idx < -len(df):
            break

        # 金叉：前一天DIF < DEA，当天DIF >= DEA
        if dif.iloc[prev_idx] < dea.iloc[prev_idx] and dif.iloc[idx] >= dea.iloc[idx]:
            # 零轴之上的金叉更强
            above_zero = dif.iloc[idx] > 0
            strength = 70 if above_zero else 50
            # 柱状图放大增强信号
            hist = macd['macd_hist']
            if len(hist) > 2 and hist.iloc[-1] > hist.iloc[-2]:
                strength += 20
            result = {
                'signal': 'golden_cross',
                'strength': min(strength, 100),
                'days_ago': i - 1
            }
            break

        # 死叉：前一天DIF > DEA，当天DIF <= DEA
        if dif.iloc[prev_idx] > dea.iloc[prev_idx] and dif.iloc[idx] <= dea.iloc[idx]:
            # 零轴之下的死叉更强
            below_zero = dif.iloc[idx] < 0
            strength = 70 if below_zero else 50
            result = {
                'signal': 'death_cross',
                'strength': min(strength, 100),
                'days_ago': i - 1
            }
            break

    return result


def detect_macd_divergence(
    df: pd.DataFrame,
    lookback: int = 20
) -> Dict[str, any]:
    """
    检测MACD背离

    底背离（看涨）：价格创新低，但MACD/DIF不创新低
    顶背离（看跌）：价格创新高，但MACD/DIF不创新高

    Args:
        df: 包含 'close' 列的DataFrame
        lookback: 向前查找的天数，默认20天

    Returns:
        Dict:
            - divergence: 'bullish' | 'bearish' | 'none'
            - confidence: 置信度 0-100
            - description: 描述信息
    """
    if len(df) < lookback + 10:
        return {'divergence': 'none', 'confidence': 0, 'description': '数据不足'}

    macd = calculate_macd(df)
    dif = macd['dif']
    close = df['close']

    result = {'divergence': 'none', 'confidence': 0, 'description': '无背离'}

    # 获取最近lookback天的数据
    recent_close = close.iloc[-lookback:]
    recent_dif = dif.iloc[-lookback:]

    # 找到价格的波谷和波峰
    # 简化方法：比较前半段和后半段的极值
    half = lookback // 2
    first_half_close = recent_close.iloc[:half]
    second_half_close = recent_close.iloc[half:]
    first_half_dif = recent_dif.iloc[:half]
    second_half_dif = recent_dif.iloc[half:]

    # 底背离检测：后半段价格更低，但DIF更高
    if (second_half_close.min() < first_half_close.min() and 
        second_half_dif.min() > first_half_dif.min()):
        # 计算置信度
        price_drop = (first_half_close.min() - second_half_close.min()) / first_half_close.min()
        dif_rise = second_half_dif.min() - first_half_dif.min()
        confidence = min(50 + price_drop * 200 + abs(dif_rise) * 100, 100)
        result = {
            'divergence': 'bullish',
            'confidence': confidence,
            'description': f'底背离：价格创新低但DIF未创新低'
        }

    # 顶背离检测：后半段价格更高，但DIF更低
    elif (second_half_close.max() > first_half_close.max() and 
          second_half_dif.max() < first_half_dif.max()):
        price_rise = (second_half_close.max() - first_half_close.max()) / first_half_close.max()
        dif_drop = first_half_dif.max() - second_half_dif.max()
        confidence = min(50 + price_rise * 200 + abs(dif_drop) * 100, 100)
        result = {
            'divergence': 'bearish',
            'confidence': confidence,
            'description': f'顶背离：价格创新高但DIF未创新高'
        }

    return result


def get_macd_score(
    df: pd.DataFrame,
    cross_lookback: int = 3,
    divergence_lookback: int = 20
) -> Tuple[float, list]:
    """
    综合MACD信号评分

    用于股票分类器的评分整合

    Args:
        df: 历史价格数据
        cross_lookback: 金叉/死叉检测天数
        divergence_lookback: 背离检测天数

    Returns:
        Tuple[float, list]: (总分, 原因列表)
    """
    score = 0.0
    reasons = []

    if df is None or len(df) < 30:
        return score, reasons

    # 检测金叉/死叉
    cross = detect_macd_cross(df, cross_lookback)
    if cross['signal'] == 'golden_cross':
        pts = 15 if cross['days_ago'] == 0 else 10
        score += pts
        reasons.append(f"MACD金叉+{pts}分")
    elif cross['signal'] == 'death_cross':
        # 死叉作为风险提示，不减分
        reasons.append(f"⚠️MACD死叉(风险提示)")

    # 检测背离
    divergence = detect_macd_divergence(df, divergence_lookback)
    if divergence['divergence'] == 'bullish' and divergence['confidence'] >= 60:
        pts = 20
        score += pts
        reasons.append(f"MACD底背离+{pts}分")
    elif divergence['divergence'] == 'bearish' and divergence['confidence'] >= 60:
        reasons.append(f"⚠️MACD顶背离(风险提示)")

    # DIF/DEA在零轴之上额外加分
    macd = calculate_macd(df)
    if macd['dif'].iloc[-1] > 0 and macd['dea'].iloc[-1] > 0:
        score += 5
        reasons.append("DIF/DEA零轴之上+5分")

    return score, reasons


if __name__ == "__main__":
    # 测试代码
    from ..core.data_fetcher import get_stock_daily_history
    
    print("测试MACD指标计算...")
    
    # 测试股票
    test_codes = ['000001', '300750']
    for code in test_codes:
        df = get_stock_daily_history(code)
        if df is not None and not df.empty:
            print(f"\n===== {code} =====")
            
            # MACD计算
            macd = calculate_macd(df)
            print(f"最新DIF: {macd['dif'].iloc[-1]:.4f}")
            print(f"最新DEA: {macd['dea'].iloc[-1]:.4f}")
            print(f"最新MACD柱: {macd['macd_hist'].iloc[-1]:.4f}")
            
            # 金叉/死叉检测
            cross = detect_macd_cross(df)
            print(f"交叉信号: {cross}")
            
            # 背离检测
            div = detect_macd_divergence(df)
            print(f"背离信号: {div}")
            
            # 综合评分
            score, reasons = get_macd_score(df)
            print(f"MACD评分: {score}, 原因: {reasons}")
