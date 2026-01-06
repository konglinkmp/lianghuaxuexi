"""
风险指标计算模块（VaR/CVaR/最大回撤/夏普等）
"""

from statistics import NormalDist
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


class RiskMetricsCalculator:
    """风险指标计算器"""
    def __init__(self, confidence_level: float = 0.95, risk_free_rate: float = 0.03):
        self.confidence = confidence_level
        self.risk_free = risk_free_rate

    def calculate_var(self, returns: pd.Series, method: str = "historical") -> Tuple[float, Dict]:
        if len(returns) < 30:
            return 0.0, {}

        returns_clean = returns.dropna()

        if method == "historical":
            var = self._var_historical(returns_clean)
        elif method == "parametric":
            var = self._var_parametric(returns_clean)
        elif method == "monte_carlo":
            var = self._var_monte_carlo(returns_clean)
        else:
            var = self._var_historical(returns_clean)

        cvar = self._calculate_cvar(returns_clean, var)

        return var, {
            "var": var,
            "cvar": cvar,
            "method": method,
            "confidence_level": self.confidence,
        }

    def _var_historical(self, returns: pd.Series) -> float:
        return float(np.percentile(returns, (1 - self.confidence) * 100))

    def _var_parametric(self, returns: pd.Series) -> float:
        mu = returns.mean()
        sigma = returns.std()
        z_score = NormalDist().inv_cdf(1 - self.confidence)
        return float(mu + z_score * sigma)

    def _var_monte_carlo(self, returns: pd.Series, n_simulations: int = 10000) -> float:
        mu = returns.mean()
        sigma = returns.std()
        simulated_returns = np.random.normal(mu, sigma, n_simulations)
        return float(np.percentile(simulated_returns, (1 - self.confidence) * 100))

    def _calculate_cvar(self, returns: pd.Series, var_value: float) -> float:
        losses_below_var = returns[returns <= var_value]
        if len(losses_below_var) > 0:
            return float(losses_below_var.mean())
        return float(var_value)

    def calculate_max_drawdown(self, equity_curve: pd.Series) -> Tuple[float, Dict]:
        if len(equity_curve) < 2:
            return 0.0, {}

        cumulative_max = equity_curve.cummax()
        drawdown = (equity_curve - cumulative_max) / cumulative_max
        max_dd = drawdown.min()
        max_dd_date = drawdown.idxmin() if hasattr(drawdown, "idxmin") else None

        recovery_info = self._calculate_recovery_time(equity_curve, drawdown, max_dd_date)

        return float(max_dd), {
            "max_drawdown": max_dd,
            "max_drawdown_date": max_dd_date,
            "recovery_days": recovery_info["recovery_days"],
            "drawdown_duration": recovery_info["drawdown_duration"],
            "drawdown_series": drawdown,
        }

    def _calculate_recovery_time(self, equity_curve, drawdown, max_dd_date):
        if max_dd_date is None or len(equity_curve) < 10:
            return {"recovery_days": None, "drawdown_duration": None}

        try:
            peak_date = equity_curve[:max_dd_date].idxmax()
            post_dd = equity_curve[max_dd_date:]
            if len(post_dd) == 0:
                return {"recovery_days": None, "drawdown_duration": None}

            recovery_idx = (
                (post_dd >= equity_curve[peak_date]).idxmax()
                if (post_dd >= equity_curve[peak_date]).any()
                else post_dd.index[-1]
            )

            recovery_days = (recovery_idx - max_dd_date).days
            drawdown_duration = (max_dd_date - peak_date).days

            return {
                "recovery_days": recovery_days,
                "drawdown_duration": drawdown_duration,
            }
        except Exception:
            return {"recovery_days": None, "drawdown_duration": None}

    def calculate_sharpe_ratio(self, returns: pd.Series, annualization: int = 252) -> float:
        if len(returns) < 30 or returns.std() == 0:
            return 0.0

        excess_returns = returns - (self.risk_free / annualization)
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(annualization)
        return float(sharpe)

    def calculate_sortino_ratio(self, returns: pd.Series, annualization: int = 252) -> float:
        if len(returns) < 30:
            return 0.0

        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float("inf")

        downside_std = downside_returns.std()
        if downside_std == 0:
            return float("inf")

        excess_returns = returns - (self.risk_free / annualization)
        sortino = excess_returns.mean() / downside_std * np.sqrt(annualization)
        return float(sortino)

    def calculate_calmar_ratio(self, returns: pd.Series, max_drawdown: float) -> float:
        if max_drawdown == 0 or len(returns) < 30:
            return 0.0

        annual_return = returns.mean() * 252
        return float(annual_return / abs(max_drawdown))

    def calculate_omega_ratio(self, returns: pd.Series, threshold: float = 0.0) -> float:
        if len(returns) < 30:
            return 0.0

        gains = returns[returns > threshold].sum()
        losses = abs(returns[returns <= threshold].sum())
        if losses == 0:
            return float("inf")

        return float(gains / losses)

    def calculate_turnover(self, trades: List[Dict]) -> float:
        if not trades:
            return 0.0

        df_trades = pd.DataFrame(trades)
        total_traded = df_trades["entry_price"] * df_trades.get("shares", 1000)
        total_traded = total_traded.sum() * 2

        avg_position_value = total_traded / len(df_trades) / 2 if len(df_trades) > 0 else 1
        turnover = total_traded / (avg_position_value * len(df_trades)) if len(df_trades) > 0 else 0

        return float(turnover)

    def generate_risk_report(self, trades: List[Dict], initial_capital: float = 100000) -> Dict:
        if not trades:
            return {"error": "无交易数据"}

        df_trades = pd.DataFrame(trades)

        if "pnl_pct" in df_trades.columns:
            returns = df_trades["pnl_pct"]
            equity_curve = (1 + returns).cumprod() * initial_capital
        else:
            df_trades["return"] = (
                (df_trades["exit_price"] - df_trades["entry_price"]) / df_trades["entry_price"]
            )
            returns = df_trades["return"]
            equity_curve = (1 + returns).cumprod() * initial_capital

        var_result = self.calculate_var(returns)
        max_dd_result = self.calculate_max_drawdown(equity_curve)

        sharpe = self.calculate_sharpe_ratio(returns)
        sortino = self.calculate_sortino_ratio(returns)
        calmar = self.calculate_calmar_ratio(returns, max_dd_result[0])
        omega = self.calculate_omega_ratio(returns)
        turnover = self.calculate_turnover(trades)

        total_return = (equity_curve.iloc[-1] / initial_capital - 1) * 100 if len(equity_curve) > 0 else 0
        annual_return = returns.mean() * 252 * 100
        volatility = returns.std() * np.sqrt(252) * 100

        win_rate = len(returns[returns > 0]) / len(returns) * 100 if len(returns) > 0 else 0
        avg_win = returns[returns > 0].mean() if len(returns[returns > 0]) > 0 else 0
        avg_loss = abs(returns[returns < 0].mean()) if len(returns[returns < 0]) > 0 else 0
        profit_factor = avg_win / avg_loss if avg_loss > 0 else float("inf")

        return {
            "基础指标": {
                "总收益率": f"{total_return:.2f}%",
                "年化收益率": f"{annual_return:.2f}%",
                "年化波动率": f"{volatility:.2f}%",
                "夏普比率": f"{sharpe:.2f}",
                "索提诺比率": f"{sortino:.2f}",
                "卡尔玛比率": f"{calmar:.2f}",
                "欧米茄比率": f"{omega:.2f}",
                "换手率": f"{turnover:.2%}",
            },
            "风险指标": {
                "最大回撤": f"{abs(max_dd_result[0] * 100):.2f}%",
                "回撤恢复天数": max_dd_result[1].get("recovery_days", "N/A"),
                f"VaR({self.confidence*100:.0f}%)": f"{var_result[0] * 100:.2f}%",
                f"CVaR({self.confidence*100:.0f}%)": f"{var_result[1].get('cvar', 0) * 100:.2f}%",
            },
            "绩效指标": {
                "胜率": f"{win_rate:.2f}%",
                "盈亏比": f"{profit_factor:.2f}",
                "平均盈利": f"{avg_win * 100:.2f}%",
                "平均亏损": f"{avg_loss * 100:.2f}%",
                "交易次数": len(trades),
            },
            "原始数据": {
                "收益序列": returns,
                "资金曲线": equity_curve,
                "VaR明细": var_result[1],
                "回撤明细": max_dd_result[1],
            },
        }

    def print_risk_report(self, report: Dict) -> None:
        if report.get("error"):
            print("无交易数据，无法生成风险报告。")
            return

        print("\n" + "=" * 72)
        print("📊 专业风险分析报告")
        print("=" * 72)

        def _print_section(title: str, data: Dict) -> None:
            print(f"\n【{title}】")
            print("-" * 72)
            if not data:
                print("  无数据")
                return
            width = max(len(str(k)) for k in data.keys())
            for key, value in data.items():
                print(f"  {str(key):<{width}} : {value}")

        _print_section("基础指标", report.get("基础指标", {}))
        _print_section("风险指标", report.get("风险指标", {}))
        _print_section("绩效指标", report.get("绩效指标", {}))

        print("\n" + "=" * 72)


risk_calculator = RiskMetricsCalculator(confidence_level=0.95)


if __name__ == "__main__":
    np.random.seed(42)
    n_trades = 100
    dates = pd.date_range(start="2023-01-01", periods=n_trades, freq="D")
    trades = []
    equity = 100000

    for i in range(n_trades):
        pnl_pct = np.random.normal(0.001, 0.02)
        pnl = equity * pnl_pct
        equity += pnl

        trades.append(
            {
                "entry_date": dates[i],
                "exit_date": dates[i] + pd.Timedelta(days=1),
                "entry_price": 100,
                "exit_price": 100 * (1 + pnl_pct),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "shares": 1000,
            }
        )

    report = risk_calculator.generate_risk_report(trades)
    risk_calculator.print_risk_report(report)
