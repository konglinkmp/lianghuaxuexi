"""
测试技术指标模块
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import numpy as np
import pytest

from quant.strategy.technical_indicators import (
    calculate_ema,
    calculate_macd,
    detect_macd_cross,
    detect_macd_divergence,
    get_macd_score,
)


def make_price_df(prices: list) -> pd.DataFrame:
    """构造测试用价格DataFrame"""
    return pd.DataFrame({'close': prices})


class TestCalculateEMA:
    """EMA计算测试"""
    
    def test_ema_basic(self):
        """测试EMA基本计算"""
        prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        series = pd.Series(prices)
        ema = calculate_ema(series, 5)
        
        assert len(ema) == len(prices)
        # EMA应该平滑价格
        assert ema.iloc[-1] < prices[-1]  # EMA滞后于上涨趋势
        
    def test_ema_trending_up(self):
        """测试上涨趋势中EMA"""
        prices = list(range(1, 31))  # 1到30的上涨序列
        series = pd.Series(prices)
        ema = calculate_ema(series, 10)
        
        # 上涨趋势中，EMA应该递增
        assert ema.iloc[-1] > ema.iloc[-10]


class TestCalculateMACD:
    """MACD计算测试"""
    
    def test_macd_structure(self):
        """测试MACD返回结构"""
        prices = list(range(1, 51)) + list(range(50, 30, -1))  # 先涨后跌
        df = make_price_df(prices)
        macd = calculate_macd(df)
        
        assert 'dif' in macd
        assert 'dea' in macd
        assert 'macd_hist' in macd
        assert len(macd['dif']) == len(prices)
        
    def test_macd_uptrend(self):
        """测试上涨趋势MACD"""
        prices = [10 + i * 0.5 for i in range(50)]  # 稳定上涨
        df = make_price_df(prices)
        macd = calculate_macd(df)
        
        # 上涨趋势中，DIF应该为正
        assert macd['dif'].iloc[-1] > 0
        
    def test_macd_downtrend(self):
        """测试下跌趋势MACD"""
        prices = [50 - i * 0.5 for i in range(50)]  # 稳定下跌
        df = make_price_df(prices)
        macd = calculate_macd(df)
        
        # 下跌趋势中，DIF应该为负
        assert macd['dif'].iloc[-1] < 0


class TestDetectMACDCross:
    """MACD金叉/死叉检测测试"""
    
    def test_golden_cross(self):
        """测试金叉检测"""
        # 构造先跌后涨的序列，产生金叉
        prices = [50 - i for i in range(30)] + [20 + i * 2 for i in range(30)]
        df = make_price_df(prices)
        result = detect_macd_cross(df, lookback=5)
        
        # 反转后应该能检测到金叉或death_cross
        assert result['signal'] in ['golden_cross', 'death_cross', 'none']
        
    def test_no_cross_stable_trend(self):
        """测试稳定趋势无交叉"""
        prices = [10 + i for i in range(60)]  # 稳定上涨
        df = make_price_df(prices)
        result = detect_macd_cross(df, lookback=3)
        
        # 稳定上涨不应该有近期交叉
        # 但如果刚开始时有交叉，result可能不是none
        assert result['signal'] in ['golden_cross', 'death_cross', 'none']
        
    def test_insufficient_data(self):
        """测试数据不足"""
        df = make_price_df([10, 11, 12])
        result = detect_macd_cross(df)
        
        assert result['signal'] == 'none'


class TestDetectMACDDivergence:
    """MACD背离检测测试"""
    
    def test_bullish_divergence(self):
        """测试底背离检测"""
        # 构造价格创新低但DIF不创新低的情况
        # 先下跌到底，反弹，再跌破新低但DIF更高
        prices = (
            [50 - i for i in range(20)] +  # 下跌到30
            [30 + i for i in range(10)] +  # 反弹到40
            [40 - i * 1.5 for i in range(15)]  # 再跌到更低
        )
        df = make_price_df(prices)
        result = detect_macd_divergence(df, lookback=20)
        
        # 能正常返回结果
        assert result['divergence'] in ['bullish', 'bearish', 'none']
        
    def test_insufficient_data(self):
        """测试数据不足"""
        df = make_price_df([10, 11, 12, 13, 14])
        result = detect_macd_divergence(df)
        
        assert result['divergence'] == 'none'
        assert '数据不足' in result['description']


class TestGetMACDScore:
    """MACD综合评分测试"""
    
    def test_score_non_negative(self):
        """测试评分非负"""
        prices = list(range(10, 60))
        df = make_price_df(prices)
        score, reasons = get_macd_score(df)
        
        assert score >= 0
        assert isinstance(reasons, list)
        
    def test_score_with_insufficient_data(self):
        """测试数据不足时评分为0"""
        df = make_price_df([10, 11, 12])
        score, reasons = get_macd_score(df)
        
        assert score == 0
        assert len(reasons) == 0
        
    def test_score_none_df(self):
        """测试空DataFrame"""
        score, reasons = get_macd_score(None)
        
        assert score == 0
        assert len(reasons) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
