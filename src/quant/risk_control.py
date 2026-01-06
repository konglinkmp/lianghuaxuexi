"""
风控状态读取与回撤控制集成
"""

import json
import os
from datetime import datetime
from typing import Optional

from config.config import ENABLE_DRAWDOWN_CONTROL
from .drawdown_controller import RiskControlState, drawdown_controller


ACCOUNT_STATUS_FILE = "data/account_status.json"


def load_account_status(filepath: str = ACCOUNT_STATUS_FILE) -> Optional[dict]:
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_risk_control_state(total_capital: float, filepath: str = ACCOUNT_STATUS_FILE) -> RiskControlState:
    """
    获取风险控制状态
    若未提供账户净值，则默认不启用回撤限制
    """
    if not ENABLE_DRAWDOWN_CONTROL:
        return RiskControlState(can_trade=True, risk_scale=1.0, max_total_exposure=1.0)

    status = load_account_status(filepath)
    if not status:
        return RiskControlState(
            can_trade=True,
            risk_scale=1.0,
            max_total_exposure=1.0,
            total_drawdown=0.0,
            monthly_drawdown=0.0,
            reasons=["未提供账户净值，回撤控制未启用"],
        )

    current_capital = status.get("current_capital", total_capital)
    as_of_raw = status.get("as_of")
    as_of = None
    if as_of_raw:
        try:
            as_of = datetime.strptime(as_of_raw, "%Y-%m-%d")
        except ValueError:
            as_of = None

    return drawdown_controller.evaluate(float(current_capital), as_of=as_of)
