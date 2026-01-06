"""
风格基准模块（按持仓市值动态加权）
"""

from typing import Dict, Tuple

import pandas as pd

from config.config import (
    ENABLE_STYLE_BENCHMARK,
    STYLE_LOOKBACK_DAYS,
    STYLE_INDEX_CODES,
    STYLE_CAP_THRESHOLDS,
    STYLE_BUCKET_MAP,
    STYLE_DEFAULT_WEIGHTS,
)
from ..core.data_fetcher import get_index_daily_history, get_stock_market_caps
from ..trade.position_tracker import position_tracker


def compute_style_weights(
    market_caps: Dict[str, float],
    thresholds: Dict[str, float],
    bucket_map: Dict[str, str],
    default_weights: Dict[str, float],
) -> Dict[str, float]:
    if not market_caps:
        return _normalize_weights(default_weights.copy())

    bucket_caps = {"large": 0.0, "mid": 0.0, "small": 0.0}
    large_th = thresholds.get("large", 1e11)
    mid_th = thresholds.get("mid", 3e10)

    for cap in market_caps.values():
        if cap >= large_th:
            bucket_caps["large"] += cap
        elif cap >= mid_th:
            bucket_caps["mid"] += cap
        else:
            bucket_caps["small"] += cap

    total = sum(bucket_caps.values())
    if total <= 0:
        return _normalize_weights(default_weights.copy())

    weights: Dict[str, float] = {}
    for bucket, cap in bucket_caps.items():
        key = bucket_map.get(bucket)
        if not key:
            continue
        weights[key] = weights.get(key, 0.0) + cap / total

    return _normalize_weights(weights)


def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in weights.items()}


def get_style_benchmark_series(lookback_days: int = STYLE_LOOKBACK_DAYS) -> Tuple[pd.Series, Dict]:
    """
    获取风格基准价格序列（组合加权）
    """
    if not ENABLE_STYLE_BENCHMARK:
        return pd.Series(dtype=float), {"enabled": False}

    holdings = list(position_tracker.get_all_positions().keys())
    caps = get_stock_market_caps(holdings) if holdings else {}
    weights = compute_style_weights(
        caps,
        STYLE_CAP_THRESHOLDS,
        STYLE_BUCKET_MAP,
        STYLE_DEFAULT_WEIGHTS,
    )

    if not weights:
        weights = _normalize_weights(STYLE_DEFAULT_WEIGHTS.copy())

    series_map = {}
    for key, code in STYLE_INDEX_CODES.items():
        if key not in weights or weights[key] <= 0:
            continue
        df = get_index_daily_history(code, days=lookback_days)
        if df is None or df.empty:
            continue
        series = df["close"].astype(float)
        if series.empty:
            continue
        series_map[key] = series / series.iloc[0]

    if not series_map:
        return pd.Series(dtype=float), {"enabled": True, "weights": weights, "codes": STYLE_INDEX_CODES}

    aligned = pd.concat(series_map, axis=1).dropna()
    if aligned.empty:
        return pd.Series(dtype=float), {"enabled": True, "weights": weights, "codes": STYLE_INDEX_CODES}

    aligned_weights = {k: weights.get(k, 0.0) for k in aligned.columns}
    aligned_weights = _normalize_weights(aligned_weights)
    composite = sum(aligned[col] * aligned_weights.get(col, 0.0) for col in aligned.columns)
    composite = composite * 100
    composite.name = "style_benchmark"

    return composite, {
        "enabled": True,
        "weights": aligned_weights,
        "codes": STYLE_INDEX_CODES,
    }
