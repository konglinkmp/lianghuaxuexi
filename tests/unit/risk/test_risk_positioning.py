import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from quant.risk.risk_positioning import calculate_position_size


def test_calculate_position_size_basic():
    result = calculate_position_size(
        price=50,
        stop_loss=45,
        total_capital=1_000_000,
        risk_budget_ratio=0.003,
        max_positions=10,
    )
    assert result.shares == 600


def test_calculate_position_size_risk_contribution_cap():
    result = calculate_position_size(
        price=50,
        stop_loss=45,
        total_capital=1_000_000,
        risk_budget_ratio=0.005,
        max_positions=2,
        risk_contribution_limit=0.25,
    )
    assert result.shares == 500


def test_calculate_position_size_liquidity_cap():
    result = calculate_position_size(
        price=50,
        stop_loss=48,
        total_capital=1_000_000,
        risk_budget_ratio=0.005,
        max_positions=10,
        adv_amount=1_000_000,
        liquidity_limit=0.05,
    )
    assert result.shares == 1000


def test_calculate_position_size_paused():
    result = calculate_position_size(
        price=50,
        stop_loss=45,
        total_capital=1_000_000,
        risk_budget_ratio=0.003,
        risk_scale=0.0,
    )
    assert result.shares == 0
