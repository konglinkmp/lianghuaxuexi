"""
回撤控制器模块
当资金回撤超过阈值时，暂停新开仓
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import os
from typing import List, Optional, Tuple

from config.config import (
    MAX_DRAWDOWN_HARD,
    DRAWDOWN_REDUCE_LEVEL_1,
    DRAWDOWN_REDUCE_LEVEL_2,
    DRAWDOWN_REDUCE_TARGET_L1,
    DRAWDOWN_REDUCE_TARGET_L2,
    MONTHLY_DRAWDOWN_SOFT,
    MONTHLY_DRAWDOWN_HARD,
    MONTHLY_RISK_SCALE,
    MONTHLY_COOLDOWN_DAYS,
    TOTAL_CAPITAL,
)


@dataclass
class RiskControlState:
    can_trade: bool = True
    risk_scale: float = 1.0
    max_total_exposure: float = 1.0
    total_drawdown: float = 0.0
    monthly_drawdown: float = 0.0
    reasons: List[str] = field(default_factory=list)
    as_of: Optional[datetime] = None

    def summary(self) -> str:
        reason_text = "；".join(self.reasons) if self.reasons else "无"
        return (
            f"总回撤{self.total_drawdown*100:.1f}%｜"
            f"月度回撤{self.monthly_drawdown*100:.1f}%｜"
            f"风险缩放{self.risk_scale:.2f}｜"
            f"总仓位上限{self.max_total_exposure*100:.0f}%｜"
            f"可交易: {'是' if self.can_trade else '否'}｜"
            f"原因: {reason_text}"
        )


class DrawdownController:
    """
    回撤控制器

    功能：
    1. 跟踪资金峰值
    2. 计算当前回撤
    3. 分级降仓与月度风控
    """

    def __init__(
        self,
        max_drawdown: float = MAX_DRAWDOWN_HARD,
        initial_capital: float = TOTAL_CAPITAL,
        state_file: str = "data/drawdown_state.json",
        reduce_level_1: float = DRAWDOWN_REDUCE_LEVEL_1,
        reduce_level_2: float = DRAWDOWN_REDUCE_LEVEL_2,
        reduce_target_l1: float = DRAWDOWN_REDUCE_TARGET_L1,
        reduce_target_l2: float = DRAWDOWN_REDUCE_TARGET_L2,
        monthly_soft: float = MONTHLY_DRAWDOWN_SOFT,
        monthly_hard: float = MONTHLY_DRAWDOWN_HARD,
        monthly_risk_scale: float = MONTHLY_RISK_SCALE,
        monthly_cooldown_days: int = MONTHLY_COOLDOWN_DAYS,
    ):
        self.max_drawdown = max_drawdown
        self.initial_capital = initial_capital
        self.state_file = state_file

        self.reduce_level_1 = reduce_level_1
        self.reduce_level_2 = reduce_level_2
        self.reduce_target_l1 = reduce_target_l1
        self.reduce_target_l2 = reduce_target_l2

        self.monthly_soft = monthly_soft
        self.monthly_hard = monthly_hard
        self.monthly_risk_scale = monthly_risk_scale
        self.monthly_cooldown_days = monthly_cooldown_days

        self._ensure_directory()
        self._load_state()

        self.last_state: Optional[RiskControlState] = None

    def _load_state(self) -> None:
        """加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    self.peak_capital = state.get("peak_capital", self.initial_capital)
                    self.current_capital = state.get("current_capital", self.initial_capital)
                    self.is_paused = state.get("is_paused", False)
                    self.pause_reason = state.get("pause_reason", "")
                    self.month_start_capital = state.get("month_start_capital", self.initial_capital)
                    self.month_start_date = state.get("month_start_date", "")
                    self.monthly_paused_until = state.get("monthly_paused_until", "")
                    return
            except Exception as exc:
                print(f"[警告] 加载回撤状态失败: {exc}")

        # 默认状态
        self.peak_capital = self.initial_capital
        self.current_capital = self.initial_capital
        self.is_paused = False
        self.pause_reason = ""
        self.month_start_capital = self.initial_capital
        self.month_start_date = ""
        self.monthly_paused_until = ""

    def _ensure_directory(self) -> None:
        """确保存储目录存在"""
        directory = os.path.dirname(self.state_file)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _save_state(self) -> None:
        """保存状态"""
        state = {
            "peak_capital": self.peak_capital,
            "current_capital": self.current_capital,
            "is_paused": self.is_paused,
            "pause_reason": self.pause_reason,
            "month_start_capital": self.month_start_capital,
            "month_start_date": self.month_start_date,
            "monthly_paused_until": self.monthly_paused_until,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[警告] 保存回撤状态失败: {exc}")

    def _parse_date(self, as_of: Optional[datetime] = None) -> datetime:
        if as_of is None:
            return datetime.now()
        if isinstance(as_of, datetime):
            return as_of
        raise ValueError("as_of 必须为 datetime 或 None")

    def _maybe_reset_month(self, as_of: datetime) -> None:
        if not self.month_start_date:
            self.month_start_date = as_of.strftime("%Y-%m-%d")
            self.month_start_capital = self.current_capital
            return

        try:
            month_start = datetime.strptime(self.month_start_date, "%Y-%m-%d")
        except ValueError:
            month_start = as_of

        if month_start.year != as_of.year or month_start.month != as_of.month:
            self.month_start_date = as_of.strftime("%Y-%m-%d")
            self.month_start_capital = self.current_capital

    def _monthly_pause_active(self, as_of: datetime) -> bool:
        if not self.monthly_paused_until:
            return False
        try:
            pause_until = datetime.strptime(self.monthly_paused_until, "%Y-%m-%d")
        except ValueError:
            return False
        return as_of.date() <= pause_until.date()

    def get_current_drawdown(self) -> float:
        """获取当前总回撤比例"""
        if self.peak_capital <= 0:
            return 0.0
        return (self.peak_capital - self.current_capital) / self.peak_capital

    def get_monthly_drawdown(self) -> float:
        """获取当前月度回撤比例"""
        if self.month_start_capital <= 0:
            return 0.0
        return (self.month_start_capital - self.current_capital) / self.month_start_capital

    def evaluate(self, new_capital: float, as_of: Optional[datetime] = None) -> RiskControlState:
        """
        更新资金并输出风控状态

        Returns:
            RiskControlState
        """
        as_of_dt = self._parse_date(as_of)
        self.current_capital = new_capital
        self._maybe_reset_month(as_of_dt)

        # 更新峰值
        if new_capital > self.peak_capital:
            self.peak_capital = new_capital
            if self.is_paused:
                self.is_paused = False
                self.pause_reason = ""
                print("✅ 资金创新高，恢复交易")

        total_dd = self.get_current_drawdown()
        monthly_dd = self.get_monthly_drawdown()

        can_trade = True
        risk_scale = 1.0
        max_total_exposure = 1.0
        reasons: List[str] = []

        # 总回撤分级
        if total_dd >= self.max_drawdown:
            can_trade = False
            max_total_exposure = 0.0
            reasons.append(f"总回撤{total_dd*100:.1f}%超过硬线{self.max_drawdown*100:.0f}%")
        elif total_dd >= self.reduce_level_2:
            max_total_exposure = self.reduce_target_l2
            reasons.append(f"总回撤{total_dd*100:.1f}%触发降仓线2")
        elif total_dd >= self.reduce_level_1:
            max_total_exposure = self.reduce_target_l1
            reasons.append(f"总回撤{total_dd*100:.1f}%触发降仓线1")

        # 月度回撤软硬线
        if monthly_dd >= self.monthly_soft:
            risk_scale = min(risk_scale, self.monthly_risk_scale)
            reasons.append(f"月度回撤{monthly_dd*100:.1f}%触发软线")

        if monthly_dd >= self.monthly_hard:
            can_trade = False
            pause_until = as_of_dt + timedelta(days=self.monthly_cooldown_days)
            self.monthly_paused_until = pause_until.strftime("%Y-%m-%d")
            reasons.append(f"月度回撤{monthly_dd*100:.1f}%触发硬线")

        if self._monthly_pause_active(as_of_dt):
            can_trade = False
            reasons.append(f"月度冷却中至{self.monthly_paused_until}")

        # 更新暂停状态
        self.is_paused = not can_trade
        self.pause_reason = "；".join(reasons) if reasons else ""

        self._save_state()

        state = RiskControlState(
            can_trade=can_trade,
            risk_scale=risk_scale,
            max_total_exposure=max_total_exposure,
            total_drawdown=total_dd,
            monthly_drawdown=monthly_dd,
            reasons=reasons,
            as_of=as_of_dt,
        )
        self.last_state = state
        return state

    def update_capital(self, new_capital: float, as_of: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        更新当前资金（兼容旧接口）

        Returns:
            tuple: (是否允许交易, 状态信息)
        """
        state = self.evaluate(new_capital, as_of=as_of)
        if state.can_trade:
            msg = f"✅ {state.summary()}"
        else:
            msg = f"⚠️ {state.summary()}"
        return state.can_trade, msg

    def can_trade(self) -> Tuple[bool, str]:
        """检查是否允许交易"""
        if self.is_paused:
            return False, f"⛔ 交易暂停: {self.pause_reason}"
        return True, "✅ 可以交易"

    def force_resume(self) -> None:
        """强制恢复交易（用于手动干预）"""
        self.is_paused = False
        self.pause_reason = ""
        self.monthly_paused_until = ""
        self._save_state()
        print("✅ 已强制恢复交易")

    def reset(self, new_capital: Optional[float] = None) -> None:
        """重置控制器状态"""
        if new_capital is not None:
            self.initial_capital = new_capital

        self.peak_capital = self.initial_capital
        self.current_capital = self.initial_capital
        self.is_paused = False
        self.pause_reason = ""
        self.month_start_capital = self.initial_capital
        self.month_start_date = ""
        self.monthly_paused_until = ""
        self._save_state()
        print(f"✅ 已重置回撤控制器，初始资金: ¥{self.initial_capital:,.2f}")

    def print_status(self) -> None:
        """打印当前状态"""
        total_dd = self.get_current_drawdown()
        monthly_dd = self.get_monthly_drawdown()
        status_emoji = "🟢" if not self.is_paused else "🔴"

        print("\n" + "=" * 60)
        print("📉 回撤控制器状态")
        print("=" * 60)
        print(f"  初始资金: ¥{self.initial_capital:,.2f}")
        print(f"  资金峰值: ¥{self.peak_capital:,.2f}")
        print(f"  当前资金: ¥{self.current_capital:,.2f}")
        print(f"  当前回撤: {total_dd*100:.2f}%")
        print(f"  月度回撤: {monthly_dd*100:.2f}%")
        print(f"  回撤硬线: {self.max_drawdown*100:.0f}%")
        print(f"  交易状态: {status_emoji} {'暂停' if self.is_paused else '正常'}")
        if self.is_paused:
            print(f"  暂停原因: {self.pause_reason}")
        if self.monthly_paused_until:
            print(f"  月度冷却: 至 {self.monthly_paused_until}")
        print("=" * 60)


drawdown_controller = DrawdownController()


if __name__ == "__main__":
    print("=== 回撤控制器测试 ===\n")

    controller = DrawdownController(
        max_drawdown=0.20,
        initial_capital=100000,
        state_file="data/test_drawdown.json",
    )

    capital_series = [100000, 105000, 100000, 92000, 88000, 85000]
    for capital in capital_series:
        can_trade, msg = controller.update_capital(capital)
        print(f"资金: ¥{capital:,} | {msg}")

    if os.path.exists("data/test_drawdown.json"):
        os.remove("data/test_drawdown.json")
