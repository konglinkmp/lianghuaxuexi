"""
市场状态识别与参数自适应模块
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from config.config import (
    STOP_LOSS_RATIO,
    TAKE_PROFIT_RATIO,
    VOLUME_RATIO_THRESHOLD,
    MAX_PRICE_DEVIATION,
    TRAILING_STOP_RATIO,
    POSITION_RATIO,
    MAX_POSITIONS,
)


class MarketRegime(Enum):
    """市场状态枚举"""
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    CONSOLIDATION = "consolidation"
    HIGH_VOLATILITY = "high_vol"
    LOW_VOLATILITY = "low_vol"


@dataclass
class AdaptiveParameters:
    """自适应参数配置"""
    stop_loss_ratio: float = STOP_LOSS_RATIO
    atr_multiplier: float = 1.5
    use_atr_stop: bool = True

    volume_threshold: float = VOLUME_RATIO_THRESHOLD
    max_price_deviation: float = MAX_PRICE_DEVIATION

    take_profit_ratio: float = TAKE_PROFIT_RATIO
    trailing_stop_ratio: float = TRAILING_STOP_RATIO

    position_ratio: float = POSITION_RATIO
    max_positions: int = MAX_POSITIONS

    @classmethod
    def for_regime(cls, regime: MarketRegime, volatility: float = 0.2) -> "AdaptiveParameters":
        if regime == MarketRegime.TREND_UP:
            return cls(
                stop_loss_ratio=0.07,
                atr_multiplier=2.0,
                take_profit_ratio=0.20,
                trailing_stop_ratio=0.10,
                volume_threshold=1.1,
                position_ratio=0.12,
            )
        if regime == MarketRegime.TREND_DOWN:
            return cls(
                stop_loss_ratio=0.03,
                atr_multiplier=1.0,
                use_atr_stop=True,
                take_profit_ratio=0.10,
                trailing_stop_ratio=0.05,
                volume_threshold=1.5,
                position_ratio=0.05,
                max_positions=5,
            )
        if regime == MarketRegime.HIGH_VOLATILITY:
            return cls(
                stop_loss_ratio=0.03,
                atr_multiplier=1.2,
                take_profit_ratio=0.12,
                trailing_stop_ratio=0.06,
                volume_threshold=1.4,
                position_ratio=0.06,
                max_positions=8,
            )
        if regime == MarketRegime.LOW_VOLATILITY:
            return cls(
                stop_loss_ratio=0.08,
                atr_multiplier=2.5,
                take_profit_ratio=0.18,
                trailing_stop_ratio=0.12,
                volume_threshold=1.1,
                position_ratio=0.15,
                max_positions=12,
            )
        return cls()


class MarketRegimeDetector:
    """市场状态识别器"""
    def __init__(self, lookback_days: int = 60):
        self.lookback = lookback_days

    def detect(self, price_series: pd.Series, volume_series: Optional[pd.Series] = None, **kwargs) -> Tuple[MarketRegime, Dict]:
        if price_series is None or len(price_series) < self.lookback:
            return MarketRegime.CONSOLIDATION, {}

        returns = price_series.pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) if len(returns) > 1 else 0.0

        ma_short = price_series.rolling(window=10).mean()
        ma_medium = price_series.rolling(window=30).mean()
        ma_long = price_series.rolling(window=60).mean()

        price_above_short = (price_series > ma_short).iloc[-20:].mean()
        price_above_medium = (price_series > ma_medium).iloc[-20:].mean()
        price_above_long = (price_series > ma_long).iloc[-20:].mean()

        adx_value = self._calculate_adx(price_series)
        market_breadth = self._estimate_market_breadth(price_series)

        # 风格偏离度计算（如果有对比指数）
        style_drift = 0.0
        if "benchmark_prices" in kwargs:
            benchmark = kwargs["benchmark_prices"]
            if benchmark is not None and len(benchmark) >= 20 and len(price_series) >= 20:
                bench_return = benchmark.iloc[-20:].pct_change().sum()
                price_return = price_series.iloc[-20:].pct_change().sum()
                style_drift = price_return - bench_return

        regime = self._decide_regime(
            volatility=volatility,
            adx=adx_value,
            price_above_short=price_above_short,
            price_above_medium=price_above_medium,
            price_above_long=price_above_long,
            market_breadth=market_breadth,
            style_drift=style_drift,
        )

        metrics = {
            "volatility": volatility,
            "adx": adx_value,
            "trend_strength": adx_value / 100 if adx_value else 0.0,
            "market_breadth": market_breadth,
            "ma_alignment": self._check_ma_alignment(ma_short, ma_medium, ma_long),
            "price_position": self._calculate_price_position(price_series, ma_medium),
            "style_drift": style_drift,
        }

        return regime, metrics

    def _calculate_adx(self, price_series: pd.Series, period: int = 14) -> float:
        """
        计算 ADX (平均趋向指数)
        简化版实现，用于衡量趋势强度
        """
        if len(price_series) < period * 2:
            return 0.0

        try:
            # 计算价格变化
            price_diff = price_series.diff()
            
            # 计算上涨和下跌的移动平均
            up_moves = (price_diff > 0).astype(float)
            down_moves = (price_diff < 0).astype(float)
            
            # 使用 rolling 计算趋势方向的比例
            trend_up_series = up_moves.rolling(window=period).mean()
            trend_down_series = down_moves.rolling(window=period).mean()
            
            # 计算 DX Series
            dx_series = pd.Series(index=price_series.index, dtype=float)
            for i in range(period, len(price_series)):
                trend_up = trend_up_series.iloc[i]
                trend_down = trend_down_series.iloc[i]
                denominator = trend_up + trend_down + 1e-10
                dx_series.iloc[i] = abs(trend_up - trend_down) / denominator * 100
            
            # 计算 ADX (DX 的移动平均)
            adx_series = dx_series.rolling(window=period).mean()
            
            # 获取最新的 ADX 值
            latest_adx = adx_series.iloc[-1]
            return float(latest_adx) if not pd.isna(latest_adx) else 0.0
            
        except Exception:
            return 0.0

    def _estimate_market_breadth(self, price_series: pd.Series) -> float:
        ma20 = price_series.rolling(window=20).mean()
        above_ma = (price_series > ma20).iloc[-20:].mean()
        up_days = (price_series.diff() > 0).iloc[-20:].mean()
        return float((above_ma + up_days) / 2)

    def _check_ma_alignment(self, ma_short, ma_medium, ma_long) -> str:
        if ma_short.iloc[-1] > ma_medium.iloc[-1] > ma_long.iloc[-1]:
            return "bullish"
        if ma_short.iloc[-1] < ma_medium.iloc[-1] < ma_long.iloc[-1]:
            return "bearish"
        return "mixed"

    def _calculate_price_position(self, price_series: pd.Series, ma_medium: pd.Series) -> float:
        if len(price_series) == 0 or pd.isna(ma_medium.iloc[-1]):
            return 0.0
        return float((price_series.iloc[-1] / ma_medium.iloc[-1] - 1) * 100)

    def _decide_regime(
        self,
        volatility: float,
        adx: float,
        price_above_short: float,
        price_above_medium: float,
        price_above_long: float,
        market_breadth: float,
        style_drift: float = 0.0,
    ) -> MarketRegime:
        # 风格踩踏判定：如果小票大幅跑输大盘（如20天跑输5%），强制进入下跌趋势
        if style_drift < -0.05:
            return MarketRegime.TREND_DOWN

        if volatility > 0.25:
            return MarketRegime.HIGH_VOLATILITY
        if volatility < 0.15 and volatility > 0:
            return MarketRegime.LOW_VOLATILITY

        if adx > 25:
            if price_above_medium > 0.6 and price_above_long > 0.55:
                return MarketRegime.TREND_UP
            if price_above_medium < 0.4 and price_above_long < 0.45:
                return MarketRegime.TREND_DOWN

        return MarketRegime.CONSOLIDATION


class AdaptiveStrategy:
    """自适应策略控制器"""
    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()
        self.current_regime = MarketRegime.CONSOLIDATION
        self.current_params = AdaptiveParameters()
        self.regime_history = []

    def update_regime(self, index_prices: pd.Series, benchmark_prices: Optional[pd.Series] = None) -> Dict:
        regime, metrics = self.regime_detector.detect(index_prices, benchmark_prices=benchmark_prices)
        self.current_regime = regime
        self.current_params = AdaptiveParameters.for_regime(regime, metrics.get("volatility", 0.2))

        self.regime_history.append(
            {
                "timestamp": pd.Timestamp.now(),
                "regime": regime.value,
                "volatility": metrics.get("volatility", 0),
                "adx": metrics.get("adx", 0),
            }
        )
        if len(self.regime_history) > 100:
            self.regime_history = self.regime_history[-100:]

        return {
            "regime": regime,
            "regime_name": regime.value,
            "metrics": metrics,
            "parameters": self.current_params,
        }

    def reset(self) -> None:
        self.current_regime = MarketRegime.CONSOLIDATION
        self.current_params = AdaptiveParameters()

    def get_current_params(self) -> AdaptiveParameters:
        return self.current_params

    def get_regime_history(self) -> pd.DataFrame:
        return pd.DataFrame(self.regime_history)

    def print_status(self) -> None:
        print("\n" + "=" * 50)
        print("自适应策略状态")
        print("=" * 50)
        print(f"市场状态: {self.current_regime.value}")
        print(f"止损比例: {self.current_params.stop_loss_ratio*100:.1f}%")
        print(f"ATR倍数: {self.current_params.atr_multiplier}")
        print(f"放量要求: {self.current_params.volume_threshold:.2f}倍")
        print(f"止盈目标: {self.current_params.take_profit_ratio*100:.1f}%")
        print(f"移动止盈: {self.current_params.trailing_stop_ratio*100:.1f}%")
        print(f"单笔仓位: {self.current_params.position_ratio*100:.1f}%")
        print(f"最大持仓: {self.current_params.max_positions}只")
        print("=" * 50)


adaptive_strategy = AdaptiveStrategy()


if __name__ == "__main__":
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    np.random.seed(42)
    trend = np.concatenate(
        [
            np.linspace(100, 150, 40),
            np.linspace(150, 120, 30),
            np.random.normal(120, 5, 30),
        ]
    )
    prices = pd.Series(trend, index=dates)

    detector = MarketRegimeDetector()
    regime, metrics = detector.detect(prices)
    print(f"识别结果: {regime.value}")
    print(f"波动率: {metrics.get('volatility', 0):.2%}")
    print(f"ADX: {metrics.get('adx', 0):.1f}")

    adaptive = AdaptiveStrategy()
    adaptive.update_regime(prices)
    adaptive.print_status()
