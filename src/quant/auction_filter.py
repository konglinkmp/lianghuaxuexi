"""
集合竞价过滤器
用于在开盘前/开盘后对买入计划进行跳空与可成交性过滤
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd

from config.config import (
    AUCTION_GAP_UP_CANCEL,
    AUCTION_GAP_DOWN_CANCEL,
    AUCTION_GAP_UP_REPRICE,
    AUCTION_REPRICE_SLIPPAGE,
    AUCTION_MIN_VOLUME_RATIO,
    AUCTION_LIMIT_BUFFER,
)


@dataclass
class AuctionDecision:
    action: str
    reason: str
    open_price: float
    ref_price: float
    gap_pct: float
    new_trigger_price: Optional[float] = None


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace("%", "").strip()
        return float(value)
    except (ValueError, TypeError):
        return None


def _find_column(df: pd.DataFrame, candidates) -> Optional[str]:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _limit_pct_by_code(code: str) -> float:
    if code.startswith("300") or code.startswith("688"):
        return 0.20
    return 0.10


def normalize_snapshot(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    """
    统一竞价快照字段命名
    """
    if snapshot_df is None or snapshot_df.empty:
        return pd.DataFrame()

    df = snapshot_df.copy()
    code_col = _find_column(df, ["代码", "code", "symbol"])
    last_col = _find_column(df, ["最新价", "现价", "price", "last"])
    open_col = _find_column(df, ["今开", "开盘", "open"])
    vol_ratio_col = _find_column(df, ["量比", "volume_ratio"])
    pct_col = _find_column(df, ["涨跌幅", "pct_chg", "涨跌幅(%)"])

    if code_col is None:
        return pd.DataFrame()

    data = pd.DataFrame()
    data["代码"] = df[code_col].astype(str)
    data["open"] = df[open_col].apply(_to_float) if open_col else None
    data["last"] = df[last_col].apply(_to_float) if last_col else None
    data["volume_ratio"] = df[vol_ratio_col].apply(_to_float) if vol_ratio_col else None
    data["pct_chg"] = df[pct_col].apply(_to_float) if pct_col else None

    if "pct_chg" in data.columns:
        data["pct_chg"] = data["pct_chg"].apply(
            lambda x: x / 100 if x is not None and abs(x) > 1 else x
        )

    return data


def evaluate_auction(
    code: str,
    open_price: float,
    ref_price: float,
    volume_ratio: Optional[float] = None,
    pct_chg: Optional[float] = None,
    gap_up_cancel: float = AUCTION_GAP_UP_CANCEL,
    gap_down_cancel: float = AUCTION_GAP_DOWN_CANCEL,
    gap_up_reprice: float = AUCTION_GAP_UP_REPRICE,
    reprice_slippage: float = AUCTION_REPRICE_SLIPPAGE,
    min_volume_ratio: float = AUCTION_MIN_VOLUME_RATIO,
    limit_buffer: float = AUCTION_LIMIT_BUFFER,
) -> AuctionDecision:
    if open_price <= 0 or ref_price <= 0:
        return AuctionDecision(
            action="keep",
            reason="竞价价格异常，跳过过滤",
            open_price=open_price,
            ref_price=ref_price,
            gap_pct=0.0,
        )

    gap_pct = open_price / ref_price - 1

    if volume_ratio is not None and volume_ratio < min_volume_ratio:
        return AuctionDecision(
            action="cancel",
            reason=f"量比{volume_ratio:.2f}低于阈值{min_volume_ratio:.2f}",
            open_price=open_price,
            ref_price=ref_price,
            gap_pct=gap_pct,
        )

    if pct_chg is not None:
        limit_pct = _limit_pct_by_code(code)
        if pct_chg >= limit_pct * limit_buffer:
            return AuctionDecision(
                action="cancel",
                reason="接近涨停，竞价不可追",
                open_price=open_price,
                ref_price=ref_price,
                gap_pct=gap_pct,
            )
        if pct_chg <= -limit_pct * limit_buffer:
            return AuctionDecision(
                action="cancel",
                reason="接近跌停，竞价不可买",
                open_price=open_price,
                ref_price=ref_price,
                gap_pct=gap_pct,
            )

    if gap_pct >= gap_up_cancel:
        return AuctionDecision(
            action="cancel",
            reason=f"高开{gap_pct*100:.1f}%超过阈值",
            open_price=open_price,
            ref_price=ref_price,
            gap_pct=gap_pct,
        )
    if gap_pct <= -gap_down_cancel:
        return AuctionDecision(
            action="cancel",
            reason=f"低开{gap_pct*100:.1f}%超过阈值",
            open_price=open_price,
            ref_price=ref_price,
            gap_pct=gap_pct,
        )

    if gap_pct >= gap_up_reprice:
        new_trigger = open_price * (1 + reprice_slippage)
        return AuctionDecision(
            action="adjust",
            reason=f"高开{gap_pct*100:.1f}%触发重定价",
            open_price=open_price,
            ref_price=ref_price,
            gap_pct=gap_pct,
            new_trigger_price=new_trigger,
        )

    return AuctionDecision(
        action="keep",
        reason="竞价过滤通过",
        open_price=open_price,
        ref_price=ref_price,
        gap_pct=gap_pct,
    )


def apply_auction_filters(plan_df: pd.DataFrame, snapshot_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    对计划进行竞价过滤

    Returns:
        tuple: (保留计划, 取消计划)
    """
    if plan_df is None or plan_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    snapshot = normalize_snapshot(snapshot_df)
    if snapshot.empty:
        plan_df = plan_df.copy()
        plan_df["竞价处理"] = "keep"
        plan_df["竞价原因"] = "无竞价数据"
        return plan_df, pd.DataFrame()

    merged = plan_df.merge(snapshot, on="代码", how="left")
    decisions = []

    for _, row in merged.iterrows():
        ref_price = _to_float(row.get("建议买入价")) or _to_float(row.get("收盘价")) or 0.0
        open_price = _to_float(row.get("open")) or _to_float(row.get("last")) or 0.0
        volume_ratio = _to_float(row.get("volume_ratio"))
        pct_chg = _to_float(row.get("pct_chg"))

        decision = evaluate_auction(
            code=str(row.get("代码")),
            open_price=open_price,
            ref_price=ref_price,
            volume_ratio=volume_ratio,
            pct_chg=pct_chg,
        )
        decisions.append(decision)

    merged["竞价处理"] = [d.action for d in decisions]
    merged["竞价原因"] = [d.reason for d in decisions]
    merged["竞价价"] = [round(d.open_price, 3) if d.open_price else None for d in decisions]
    merged["竞价偏离"] = [round(d.gap_pct * 100, 2) for d in decisions]
    merged["竞价后买入价"] = [
        round(d.new_trigger_price, 3) if d.new_trigger_price else None for d in decisions
    ]

    keep_df = merged[merged["竞价处理"].isin(["keep", "adjust"])].copy()
    cancel_df = merged[merged["竞价处理"] == "cancel"].copy()
    return keep_df, cancel_df
