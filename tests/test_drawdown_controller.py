import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from quant.risk.drawdown_controller import DrawdownController


def test_drawdown_soft_and_hard(tmp_path):
    state_file = tmp_path / "dd_state.json"
    controller = DrawdownController(
        max_drawdown=0.20,
        initial_capital=100000,
        state_file=str(state_file),
        reduce_level_1=0.12,
        reduce_level_2=0.16,
        reduce_target_l1=0.60,
        reduce_target_l2=0.30,
        monthly_soft=0.08,
        monthly_hard=0.12,
        monthly_risk_scale=0.50,
        monthly_cooldown_days=5,
    )

    state = controller.evaluate(100000, as_of=datetime(2026, 1, 2))
    assert state.can_trade is True
    assert state.risk_scale == 1.0

    state = controller.evaluate(92000, as_of=datetime(2026, 1, 10))
    assert state.risk_scale == 0.5
    assert state.can_trade is True

    state = controller.evaluate(88000, as_of=datetime(2026, 1, 12))
    assert state.can_trade is False
    assert state.max_total_exposure == 0.60
