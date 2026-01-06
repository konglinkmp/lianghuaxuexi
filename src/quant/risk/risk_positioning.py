"""
风险预算与仓位计算模块
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PositionSizingResult:
    shares: int
    amount: float
    risk_budget: float
    stop_distance: float
    reasons: List[str] = field(default_factory=list)


def estimate_adv_amount(df, price: float, window: int = 20) -> Optional[float]:
    """
    估算20日平均成交额（ADV）
    """
    if df is None or df.empty:
        return None
    if "amount" in df.columns and df["amount"].tail(window).mean() > 0:
        return float(df["amount"].tail(window).mean())
    if "volume" in df.columns and df["volume"].tail(window).mean() > 0:
        return float(df["volume"].tail(window).mean() * price)
    return None


def calculate_position_size(
    price: float,
    stop_loss: float,
    total_capital: float,
    risk_budget_ratio: float,
    risk_scale: float = 1.0,
    max_position_ratio: float = 0.40,
    max_positions: int = 10,
    adv_amount: Optional[float] = None,
    liquidity_limit: float = 0.05,
    risk_contribution_limit: float = 0.25,
    remaining_capital: Optional[float] = None,
    min_lot: int = 100,
) -> PositionSizingResult:
    """
    风险预算仓位计算

    返回建议股数（100股整数倍），并附带计算原因
    """
    reasons: List[str] = []
    if risk_scale <= 0:
        return PositionSizingResult(0, 0.0, 0.0, 0.0, ["风险缩放为0，暂停开仓"])

    stop_distance = price - stop_loss
    if stop_distance <= 0:
        return PositionSizingResult(0, 0.0, 0.0, stop_distance, ["止损价异常，跳过"])

    base_risk_budget = total_capital * risk_budget_ratio
    portfolio_risk_budget = total_capital * risk_budget_ratio * max_positions
    max_single_risk = portfolio_risk_budget * risk_contribution_limit
    risk_budget = min(base_risk_budget, max_single_risk) * risk_scale

    if risk_budget <= 0:
        return PositionSizingResult(0, 0.0, 0.0, stop_distance, ["风险预算不足"])

    shares_by_risk = risk_budget / stop_distance
    shares_by_risk = int(shares_by_risk / min_lot) * min_lot

    max_value = total_capital * max_position_ratio
    if remaining_capital is not None:
        max_value = min(max_value, remaining_capital)
        if max_value <= 0:
            return PositionSizingResult(0, 0.0, risk_budget, stop_distance, ["仓位额度已用尽"])

    if adv_amount is not None and adv_amount > 0:
        max_value = min(max_value, adv_amount * liquidity_limit)

    max_shares_by_value = int(max_value / price / min_lot) * min_lot
    shares = min(shares_by_risk, max_shares_by_value)

    if shares < min_lot:
        reasons.append("建议仓位低于最小成交单位")
        return PositionSizingResult(0, 0.0, risk_budget, stop_distance, reasons)

    amount = shares * price
    return PositionSizingResult(shares, amount, risk_budget, stop_distance, reasons)
